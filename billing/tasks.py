"""
Background tasks for Kitonga Wi-Fi Billing System
Handles automatic disconnection of expired users from MikroTik
"""

import logging
from django.utils import timezone
from .models import User, Device
from .mikrotik import (
    revoke_user_access,
    logout_user_from_mikrotik,
    disconnect_user_from_mikrotik,
    disconnect_user_from_tenant_routers,
)

logger = logging.getLogger(__name__)


def disconnect_expired_users():
    """
    Disconnect users whose access has expired.
    This should be run periodically (e.g., every 5 minutes via cron or celery beat).

    This function:
    1. Finds users whose paid_until has passed
    2. Sends SMS notification about expiration
    3. Disconnects them from MikroTik (removes active sessions, IP bindings, disables user)
    4. Deactivates their access in the database
    5. Marks their devices as inactive

    IMPORTANT: This tracks which router each user is connected to for accurate disconnection
    """
    try:
        from .models import Router

        now = timezone.now()

        # Find users whose access has expired
        expired_users = User.objects.filter(is_active=True, paid_until__lte=now)

        disconnected_count = 0
        failed_count = 0
        devices_deactivated = 0
        sms_sent = 0
        routers_processed = {}

        logger.info(f"🔍 Found {expired_users.count()} expired users to disconnect")

        for user in expired_users:
            try:
                # Calculate how long they've been expired
                time_expired = now - user.paid_until if user.paid_until else None
                expired_hours = (
                    int(time_expired.total_seconds() / 3600) if time_expired else 0
                )

                logger.info(
                    f"⏰ Processing expired user: {user.phone_number} "
                    f"(tenant: {user.tenant.slug if user.tenant else 'platform'}, "
                    f"paid_until: {user.paid_until}, expired {expired_hours}h ago)"
                )

                # Send SMS notification BEFORE disconnecting
                if _send_expiry_sms(user):
                    sms_sent += 1

                # Get all active devices for this user
                devices = user.devices.filter(is_active=True)

                # Track which routers this user's devices are connected to
                user_routers = set()
                for device in devices:
                    if device.router:
                        user_routers.add(device.router)
                        logger.info(
                            f"  📱 Device {device.mac_address} connected to router: {device.router.name} (ID: {device.router.id})"
                        )
                    else:
                        logger.warning(
                            f"  ⚠️  Device {device.mac_address} has no router association"
                        )

                # Check if user belongs to a tenant (multi-tenant mode)
                if user.tenant:
                    tenant_routers = list(
                        Router.objects.filter(tenant=user.tenant, is_active=True)
                    )
                    # Use tenant-aware disconnect for multi-tenant SaaS
                    for device in devices:
                        try:
                            result = disconnect_user_from_tenant_routers(
                                user=user, mac_address=device.mac_address
                            )

                            if result.get("success"):
                                logger.info(
                                    f"Successfully disconnected {user.phone_number} - {device.mac_address} from tenant routers"
                                )
                                logger.debug(
                                    f'  - Routers succeeded: {result.get("routers_succeeded", 0)}'
                                )
                            else:
                                logger.warning(
                                    f"Disconnect result for {user.phone_number} - {device.mac_address}: {result}"
                                )

                            # Mark device as inactive in database
                            device.is_active = False
                            device.save()
                            devices_deactivated += 1

                        except Exception as device_error:
                            logger.error(
                                f"Error disconnecting device {device.mac_address} for {user.phone_number}: {str(device_error)}"
                            )
                            failed_count += 1

                    # Also try to disconnect by username only (for orphaned sessions)
                    try:
                        disconnect_user_from_tenant_routers(user=user, mac_address=None)
                    except Exception:
                        pass
                else:
                    # Fallback to legacy global router for users without tenant
                    logger.info(
                        f"  🌐 Using legacy global router for {user.phone_number}"
                    )

                    for device in devices:
                        try:
                            logger.info(
                                f"  🔌 Disconnecting device {device.mac_address} from global router..."
                            )

                            result = disconnect_user_from_mikrotik(
                                username=user.phone_number,
                                mac_address=device.mac_address,
                            )

                            if result.get("success"):
                                logger.info(
                                    f"  ✅ Successfully disconnected {user.phone_number} - {device.mac_address} from global MikroTik"
                                )
                                routers_processed["global"] = (
                                    routers_processed.get("global", 0) + 1
                                )
                            else:
                                logger.warning(
                                    f"  ⚠️  Disconnect result for {user.phone_number} - {device.mac_address}: {result}"
                                )

                            # Mark device as inactive in database
                            device.is_active = False
                            device.save()
                            devices_deactivated += 1
                            logger.info(
                                f"  ✅ Device {device.mac_address} marked as inactive"
                            )

                        except Exception as device_error:
                            logger.error(
                                f"  ❌ Error disconnecting device {device.mac_address} for {user.phone_number}: {str(device_error)}"
                            )
                            failed_count += 1

                    # Also try to disconnect by username only (for orphaned sessions)
                    try:
                        logger.info(
                            f"  🧹 Cleaning up orphaned sessions for {user.phone_number}..."
                        )
                        disconnect_user_from_mikrotik(
                            username=user.phone_number, mac_address=None
                        )
                    except Exception as cleanup_error:
                        logger.warning(
                            f"  ⚠️  Orphaned session cleanup failed: {cleanup_error}"
                        )

                # Deactivate user in database
                user.deactivate_access()
                disconnected_count += 1
                logger.info(f"✅ User {user.phone_number} deactivated after expiration")

            except Exception as user_error:
                logger.error(
                    f"❌ Error processing expired user {user.phone_number}: {str(user_error)}"
                )
                failed_count += 1

        # Log router-level statistics
        if routers_processed:
            logger.info("📊 Router disconnect statistics:")
            for router_key, count in routers_processed.items():
                logger.info(f"  - {router_key}: {count} users disconnected")

        logger.info(
            f"🎯 Expired user cleanup complete: {disconnected_count} users disconnected, "
            f"{devices_deactivated} devices deactivated, {sms_sent} SMS sent, {failed_count} failures"
        )

        return {
            "success": True,
            "disconnected": disconnected_count,
            "devices_deactivated": devices_deactivated,
            "sms_sent": sms_sent,
            "failed": failed_count,
            "total_checked": expired_users.count(),
            "routers_processed": routers_processed,
        }

    except Exception as e:
        logger.error(f"Error in disconnect_expired_users task: {str(e)}")
        return {"success": False, "error": str(e)}


def _send_expiry_sms(user):
    """
    Send SMS notification when user access expires.
    Uses global NextSMS configuration from settings.py

    Returns True if SMS was sent successfully, False otherwise.
    """
    try:
        from .nextsms import NextSMSAPI
        from .models import SMSLog
        from django.conf import settings

        phone_number = user.phone_number

        if not phone_number:
            logger.debug("User has no phone number, skipping SMS")
            return False

        # Check if NextSMS is configured
        if not hasattr(settings, "NEXTSMS_USERNAME") or not settings.NEXTSMS_USERNAME:
            logger.debug("NextSMS not configured, skipping SMS")
            return False

        sms_api = NextSMSAPI()
        result = sms_api.send_access_expired(phone_number)

        if result.get("success"):
            logger.info(f"📱 Sent expiry SMS to {phone_number}")

            # Log the SMS
            SMSLog.objects.create(
                tenant=user.tenant if hasattr(user, "tenant") else None,
                phone_number=phone_number,
                message="Access expired notification",
                sms_type="expired",
                success=True,
                response_data=result,
            )
            return True
        else:
            logger.warning(
                f'Failed to send expiry SMS to {phone_number}: {result.get("message")}'
            )
            return False

    except Exception as e:
        logger.error(f"Error sending expiry SMS to {user.phone_number}: {str(e)}")
        return False


def cleanup_inactive_devices():
    """
    Clean up devices that haven't been seen in a while
    """
    try:
        from datetime import timedelta

        threshold = timezone.now() - timedelta(days=30)

        old_devices = Device.objects.filter(last_seen__lt=threshold, is_active=True)

        count = 0
        for device in old_devices:
            try:
                device.is_active = False
                device.save()
                count += 1
                logger.info(
                    f"Deactivated old device {device.mac_address} for user {device.user.phone_number}"
                )
            except Exception as e:
                logger.error(f"Error deactivating device {device.id}: {str(e)}")

        logger.info(f"Inactive device cleanup: {count} devices deactivated")

        return {"success": True, "deactivated": count}

    except Exception as e:
        logger.error(f"Error in cleanup_inactive_devices task: {str(e)}")
        return {"success": False, "error": str(e)}


def send_expiry_notifications():
    """
    Send SMS notifications to users whose access is about to expire.
    This should be run hourly via cron.

    Notifies users 1 hour before their access expires.

    IMPORTANT: This only sends notifications. Actual disconnection happens in disconnect_expired_users()
    """
    try:
        from datetime import timedelta
        from .nextsms import NextSMSAPI
        from .models import SMSLog

        now = timezone.now()

        # Find users expiring in the next hour who haven't been notified
        expiry_window_start = now
        expiry_window_end = now + timedelta(hours=1)

        users_to_notify = User.objects.filter(
            is_active=True,
            paid_until__gte=expiry_window_start,
            paid_until__lte=expiry_window_end,
            expiry_notification_sent=False,
        )

        logger.info(
            f"📢 Found {users_to_notify.count()} users to notify about upcoming expiry"
        )

        notified_count = 0
        failed_count = 0

        nextsms = NextSMSAPI()

        for user in users_to_notify:
            try:
                # Calculate remaining time
                remaining = user.paid_until - now
                remaining_minutes = int(remaining.total_seconds() / 60)

                logger.info(
                    f"⏰ Notifying {user.phone_number} "
                    f"(tenant: {user.tenant.slug if user.tenant else 'platform'}, "
                    f"expires in {remaining_minutes} minutes)"
                )

                # Customize message based on tenant
                if user.tenant:
                    business_name = user.tenant.business_name
                    message = f"{business_name} WiFi: Your internet access expires in {remaining_minutes} minutes. To continue using WiFi, please make a payment or redeem a voucher."
                else:
                    message = f"Kitonga WiFi: Your internet access expires in {remaining_minutes} minutes. To continue using WiFi, please make a payment or redeem a voucher."

                result = nextsms.send_sms(user.phone_number, message)

                if result.get("success"):
                    user.expiry_notification_sent = True
                    user.save()
                    notified_count += 1
                    logger.info(f"✅ Sent expiry notification to {user.phone_number}")

                    # Log SMS
                    SMSLog.objects.create(
                        tenant=user.tenant if hasattr(user, "tenant") else None,
                        phone_number=user.phone_number,
                        message=message,
                        sms_type="expiry_notification",
                        success=True,
                        response_data=result,
                    )
                else:
                    failed_count += 1
                    logger.warning(
                        f"❌ Failed to send expiry notification to {user.phone_number}: {result}"
                    )

            except Exception as user_error:
                failed_count += 1
                logger.error(
                    f"❌ Error sending notification to {user.phone_number}: {str(user_error)}"
                )

        logger.info(
            f"📢 Expiry notifications complete: {notified_count} sent, {failed_count} failed"
        )

        # Show warning if users were notified but might not get disconnected
        if notified_count > 0:
            logger.warning(
                f"⚠️  REMINDER: {notified_count} users were notified. "
                f"Make sure disconnect_expired_users() task is running every 5 minutes to actually disconnect them!"
            )

        return {
            "success": True,
            "notified": notified_count,
            "failed": failed_count,
            "total_checked": users_to_notify.count(),
        }

    except Exception as e:
        logger.error(f"Error in send_expiry_notifications task: {str(e)}")
        return {"success": False, "error": str(e)}


# ==================== PPP (PPPoE) TASKS ====================


def disconnect_expired_ppp_customers():
    """
    Disconnect PPPoE customers whose paid_until has passed.
    Runs every 5 minutes via cron.

    1. Find PPP customers whose status='active' and paid_until has passed
    2. Suspend/disable them on MikroTik router (disable secret + kick active session)
    3. Update status to 'expired' in database
    4. Send SMS notification that their internet has been disabled
    """
    try:
        from .models import PPPCustomer
        from .mikrotik import suspend_ppp_customer_on_router, kick_ppp_session

        now = timezone.now()

        # Find active PPP customers whose subscription has expired
        expired_customers = PPPCustomer.objects.filter(
            status="active",
            paid_until__lte=now,
        ).exclude(billing_type="unlimited")

        disconnected_count = 0
        failed_count = 0
        sms_sent = 0

        logger.info(
            f"🔍 PPP: Found {expired_customers.count()} expired PPP customers to disconnect"
        )

        for customer in expired_customers:
            try:
                time_expired = (
                    now - customer.paid_until if customer.paid_until else None
                )
                expired_hours = (
                    int(time_expired.total_seconds() / 3600) if time_expired else 0
                )

                logger.info(
                    f"⏰ PPP: Processing expired customer: {customer.username} "
                    f"(tenant: {customer.tenant.slug}, "
                    f"paid_until: {customer.paid_until}, expired {expired_hours}h ago)"
                )

                # 1) Suspend on MikroTik (disables the PPP secret)
                suspend_result = suspend_ppp_customer_on_router(customer)
                if suspend_result.get("success"):
                    logger.info(
                        f"  ✅ PPP secret disabled on router for {customer.username}"
                    )
                else:
                    logger.warning(
                        f"  ⚠️  Router suspend failed for {customer.username}: "
                        f"{suspend_result.get('message')}"
                    )

                # 2) Kick active PPP session (force disconnect immediately)
                try:
                    kick_result = kick_ppp_session(customer.router, customer.username)
                    if kick_result.get("success"):
                        logger.info(f"  ✅ PPP session kicked for {customer.username}")
                    else:
                        logger.info(
                            f"  ℹ️  No active PPP session to kick for {customer.username}"
                        )
                except Exception as kick_err:
                    logger.warning(
                        f"  ⚠️  Error kicking PPP session for {customer.username}: {kick_err}"
                    )

                # 3) Update database status to expired
                customer.status = "expired"
                customer.save(update_fields=["status", "updated_at"])
                disconnected_count += 1

                # 4) Send SMS notification
                try:
                    from .portal_views import _send_ppp_disabled_sms

                    result = _send_ppp_disabled_sms(customer)
                    if result.get("success"):
                        sms_sent += 1
                except Exception as sms_err:
                    logger.error(
                        f"  ❌ Failed to send PPP disabled SMS to {customer.phone_number}: {sms_err}"
                    )

                logger.info(
                    f"✅ PPP customer {customer.username} disabled after expiry"
                )

            except Exception as cust_error:
                logger.error(
                    f"❌ Error processing expired PPP customer {customer.username}: {cust_error}"
                )
                failed_count += 1

        logger.info(
            f"🎯 PPP expired customer cleanup: {disconnected_count} disconnected, "
            f"{sms_sent} SMS sent, {failed_count} failures"
        )

        return {
            "success": True,
            "disconnected": disconnected_count,
            "sms_sent": sms_sent,
            "failed": failed_count,
            "total_checked": expired_customers.count(),
        }

    except Exception as e:
        logger.error(f"Error in disconnect_expired_ppp_customers task: {e}")
        return {"success": False, "error": str(e)}


def send_ppp_expiry_notifications():
    """
    Send SMS warnings to PPP customers whose subscription is about to expire.
    Runs hourly via cron.

    Sends notifications at:
    - 24 hours before expiry
    - 3 hours before expiry
    """
    try:
        from datetime import timedelta
        from .models import PPPCustomer

        now = timezone.now()
        notified_count = 0
        failed_count = 0

        # Notify customers expiring in 24 hours (±30 min window to avoid duplicates)
        expiry_24h_start = now + timedelta(hours=23, minutes=30)
        expiry_24h_end = now + timedelta(hours=24, minutes=30)

        customers_24h = PPPCustomer.objects.filter(
            status="active",
            paid_until__gte=expiry_24h_start,
            paid_until__lte=expiry_24h_end,
        ).exclude(billing_type="unlimited")

        logger.info(f"📢 PPP: Found {customers_24h.count()} customers expiring in ~24h")

        for customer in customers_24h:
            try:
                from .portal_views import _send_ppp_expiry_warning_sms

                result = _send_ppp_expiry_warning_sms(customer, hours_remaining=24)
                if result.get("success"):
                    notified_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                failed_count += 1
                logger.error(
                    f"Error sending 24h PPP expiry notification to {customer.username}: {e}"
                )

        # Notify customers expiring in 3 hours (±30 min window)
        expiry_3h_start = now + timedelta(hours=2, minutes=30)
        expiry_3h_end = now + timedelta(hours=3, minutes=30)

        customers_3h = PPPCustomer.objects.filter(
            status="active",
            paid_until__gte=expiry_3h_start,
            paid_until__lte=expiry_3h_end,
        ).exclude(billing_type="unlimited")

        logger.info(f"📢 PPP: Found {customers_3h.count()} customers expiring in ~3h")

        for customer in customers_3h:
            try:
                from .portal_views import _send_ppp_expiry_warning_sms

                result = _send_ppp_expiry_warning_sms(customer, hours_remaining=3)
                if result.get("success"):
                    notified_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                failed_count += 1
                logger.error(
                    f"Error sending 3h PPP expiry notification to {customer.username}: {e}"
                )

        logger.info(
            f"📢 PPP expiry notifications: {notified_count} sent, {failed_count} failed"
        )

        return {
            "success": True,
            "notified": notified_count,
            "failed": failed_count,
        }

    except Exception as e:
        logger.error(f"Error in send_ppp_expiry_notifications task: {e}")
        return {"success": False, "error": str(e)}


# ==================== REMOTE ACCESS (VPN) TASKS ====================


def disconnect_expired_remote_users():
    """
    Disable WireGuard peers for remote users whose access has expired.
    Runs every 5 minutes via cron.

    1. Find RemoteUser records with status='active' and expires_at in the past
    2. Disable the peer on the MikroTik router
    3. Remove bandwidth queue
    4. Update status to 'expired' in database
    5. Log the event
    6. Optionally trigger webhook notification
    """
    try:
        from .models import RemoteUser, RemoteAccessLog
        from .mikrotik import disable_wireguard_peer, remove_wireguard_bandwidth_queue

        now = timezone.now()

        expired_users = RemoteUser.objects.filter(
            status="active",
            is_active=True,
            expires_at__isnull=False,
            expires_at__lte=now,
        ).select_related("vpn_config", "tenant")

        disabled_count = 0
        failed_count = 0
        webhook_sent = 0

        logger.info(
            f"🔍 VPN: Found {expired_users.count()} expired remote users to disable"
        )

        for remote_user in expired_users:
            try:
                time_expired = now - remote_user.expires_at
                expired_hours = int(time_expired.total_seconds() / 3600)

                logger.info(
                    f"⏰ VPN: Processing expired remote user: {remote_user.name} "
                    f"(tenant: {remote_user.tenant.slug}, "
                    f"IP: {remote_user.assigned_ip}, expired {expired_hours}h ago)"
                )

                # 1) Disable peer on router
                disable_result = disable_wireguard_peer(remote_user)
                if disable_result.get("success"):
                    logger.info(
                        f"  ✅ WireGuard peer disabled on router for {remote_user.name}"
                    )
                else:
                    logger.warning(
                        f"  ⚠️  Router disable failed for {remote_user.name}: "
                        f"{disable_result.get('message')}"
                    )

                # 2) Remove bandwidth queue
                try:
                    remove_wireguard_bandwidth_queue(remote_user)
                except Exception as q_err:
                    logger.warning(
                        f"  ⚠️  Queue removal failed for {remote_user.name}: {q_err}"
                    )

                # 3) Update database
                remote_user.status = "expired"
                remote_user.is_active = False
                remote_user.save(update_fields=["status", "is_active", "updated_at"])
                disabled_count += 1

                # 4) Log the event
                RemoteAccessLog.objects.create(
                    tenant=remote_user.tenant,
                    remote_user=remote_user,
                    event_type="expired",
                    event_details=(
                        f"Access expired. Was active until {remote_user.expires_at}. "
                        f"Peer disabled on router."
                    ),
                )

                # 5) Trigger webhook notification
                try:
                    from .webhook_service import WebhookService

                    WebhookService.dispatch_event(
                        tenant=remote_user.tenant,
                        event_type="user.expired",
                        data={
                            "user_type": "remote_vpn",
                            "remote_user_id": str(remote_user.id),
                            "name": remote_user.name,
                            "assigned_ip": remote_user.assigned_ip,
                            "expired_at": remote_user.expires_at.isoformat(),
                        },
                    )
                    webhook_sent += 1
                except Exception as wh_err:
                    logger.debug(
                        f"  ℹ️  Webhook trigger skipped for {remote_user.name}: {wh_err}"
                    )

                logger.info(
                    f"✅ VPN remote user {remote_user.name} disabled after expiry"
                )

            except Exception as user_error:
                logger.error(
                    f"❌ Error processing expired remote user {remote_user.name}: {user_error}"
                )
                failed_count += 1

        logger.info(
            f"🎯 VPN expired user cleanup: {disabled_count} disabled, "
            f"{webhook_sent} webhooks sent, {failed_count} failures"
        )

        return {
            "success": True,
            "disabled": disabled_count,
            "webhook_sent": webhook_sent,
            "failed": failed_count,
            "total_checked": expired_users.count(),
        }

    except Exception as e:
        logger.error(f"Error in disconnect_expired_remote_users task: {e}")
        return {"success": False, "error": str(e)}


def send_remote_user_expiry_notifications():
    """
    Send notifications to remote users whose VPN access is about to expire.
    Runs hourly via cron.

    Notifications sent at:
    - 24 hours before expiry
    - 3 hours before expiry
    """
    try:
        from datetime import timedelta
        from .models import RemoteUser, RemoteAccessLog

        now = timezone.now()
        notified_count = 0
        failed_count = 0

        # 24-hour warning window (±30 min to avoid duplicates)
        window_24h_start = now + timedelta(hours=23, minutes=30)
        window_24h_end = now + timedelta(hours=24, minutes=30)

        users_24h = RemoteUser.objects.filter(
            status="active",
            is_active=True,
            expires_at__gte=window_24h_start,
            expires_at__lte=window_24h_end,
        ).select_related("tenant")

        logger.info(f"📢 VPN: Found {users_24h.count()} remote users expiring in ~24h")

        for user in users_24h:
            try:
                _send_vpn_expiry_notification(user, hours_remaining=24)
                notified_count += 1
            except Exception as e:
                failed_count += 1
                logger.error(f"VPN expiry notification error for {user.name}: {e}")

        # 3-hour warning window
        window_3h_start = now + timedelta(hours=2, minutes=30)
        window_3h_end = now + timedelta(hours=3, minutes=30)

        users_3h = RemoteUser.objects.filter(
            status="active",
            is_active=True,
            expires_at__gte=window_3h_start,
            expires_at__lte=window_3h_end,
        ).select_related("tenant")

        logger.info(f"📢 VPN: Found {users_3h.count()} remote users expiring in ~3h")

        for user in users_3h:
            try:
                _send_vpn_expiry_notification(user, hours_remaining=3)
                notified_count += 1
            except Exception as e:
                failed_count += 1
                logger.error(f"VPN expiry notification error for {user.name}: {e}")

        logger.info(
            f"📢 VPN expiry notifications: {notified_count} sent, {failed_count} failed"
        )

        return {
            "success": True,
            "notified": notified_count,
            "failed": failed_count,
        }

    except Exception as e:
        logger.error(f"Error in send_remote_user_expiry_notifications: {e}")
        return {"success": False, "error": str(e)}


def _send_vpn_expiry_notification(remote_user, hours_remaining=24):
    """
    Send an SMS or email notification to a remote user about upcoming expiry.
    Uses the tenant's NextSMS configuration.
    """
    from .models import RemoteAccessLog

    tenant = remote_user.tenant

    # Try SMS notification if phone is available
    if remote_user.phone:
        try:
            from .nextsms import NextSMSAPI

            sms_api = NextSMSAPI(tenant=tenant)
            message = (
                f"{tenant.business_name} VPN: Your remote access expires in "
                f"{hours_remaining} hours. Contact your provider to renew."
            )
            result = sms_api.send_sms(remote_user.phone, message)
            if result.get("success"):
                logger.info(f"📱 VPN expiry SMS sent to {remote_user.phone}")
        except Exception as e:
            logger.debug(f"VPN expiry SMS failed for {remote_user.name}: {e}")

    # Log the notification
    RemoteAccessLog.objects.create(
        tenant=tenant,
        remote_user=remote_user,
        event_type="expired",
        event_details=f"Expiry notification sent ({hours_remaining}h warning)",
    )


def health_check_vpn_interfaces():
    """
    Health check for all active VPN interfaces across all tenants.
    Runs every 15-30 minutes via cron.

    1. For each active TenantVPNConfig, fetch live peer status from router
    2. Update last_handshake data for each remote user
    3. Detect peers that are configured but not reachable
    4. Log any router connectivity issues
    """
    try:
        from .models import TenantVPNConfig, RemoteUser, RemoteAccessLog
        from .mikrotik import (
            get_wireguard_peer_status,
            update_peer_handshake_data,
            get_tenant_mikrotik_api,
        )

        configs = TenantVPNConfig.objects.filter(
            is_active=True,
            is_configured_on_router=True,
        ).select_related("tenant", "router")

        total_configs = configs.count()
        healthy = 0
        unhealthy = 0
        peers_updated = 0
        errors = []

        logger.info(f"🏥 VPN Health Check: Checking {total_configs} VPN interfaces")

        for vpn_config in configs:
            try:
                # Test router connectivity first
                api = get_tenant_mikrotik_api(vpn_config.router)
                if api is None:
                    unhealthy += 1
                    error_msg = f"Router unreachable: {vpn_config.router.host}"
                    vpn_config.last_sync_error = error_msg
                    vpn_config.save(update_fields=["last_sync_error", "updated_at"])
                    errors.append(f"{vpn_config.tenant.slug}: {error_msg}")

                    # Trigger webhook for router offline
                    try:
                        from .webhook_service import WebhookService

                        WebhookService.dispatch_event(
                            tenant=vpn_config.tenant,
                            event_type="router.offline",
                            data={
                                "router_id": vpn_config.router.id,
                                "router_name": vpn_config.router.name,
                                "vpn_interface": vpn_config.interface_name,
                                "error": error_msg,
                            },
                        )
                    except Exception:
                        pass

                    continue

                from .mikrotik import safe_close

                safe_close(api)

                # Update handshake data for all peers
                handshake_result = update_peer_handshake_data(vpn_config)
                if handshake_result["success"]:
                    peers_updated += handshake_result.get("updated_count", 0)
                    healthy += 1

                    # Clear any previous error
                    if vpn_config.last_sync_error:
                        vpn_config.last_sync_error = ""
                        vpn_config.last_synced_at = timezone.now()
                        vpn_config.save(
                            update_fields=[
                                "last_sync_error",
                                "last_synced_at",
                                "updated_at",
                            ]
                        )
                else:
                    unhealthy += 1
                    errors.append(
                        f"{vpn_config.tenant.slug}: "
                        f"Handshake update failed - {handshake_result.get('errors')}"
                    )

            except Exception as e:
                unhealthy += 1
                errors.append(f"{vpn_config.tenant.slug}: {str(e)}")
                logger.error(
                    f"VPN health check failed for {vpn_config.tenant.slug}: {e}"
                )

        logger.info(
            f"🏥 VPN Health Check complete: {healthy} healthy, {unhealthy} unhealthy, "
            f"{peers_updated} peers updated out of {total_configs} total interfaces"
        )

        return {
            "success": True,
            "total_interfaces": total_configs,
            "healthy": healthy,
            "unhealthy": unhealthy,
            "peers_updated": peers_updated,
            "errors": errors,
        }

    except Exception as e:
        logger.error(f"Error in health_check_vpn_interfaces task: {e}")
        return {"success": False, "error": str(e)}
