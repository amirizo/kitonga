"""
Background tasks for Kitonga Wi-Fi Billing System
Handles automatic disconnection of expired users from MikroTik
"""
import logging
from django.utils import timezone
from .models import User, Device
from .mikrotik import revoke_user_access, logout_user_from_mikrotik, disconnect_user_from_mikrotik, disconnect_user_from_tenant_routers

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
    """
    try:
        now = timezone.now()
        
        # Find users whose access has expired
        expired_users = User.objects.filter(
            is_active=True,
            paid_until__lte=now
        )
        
        disconnected_count = 0
        failed_count = 0
        devices_deactivated = 0
        sms_sent = 0
        
        for user in expired_users:
            try:
                logger.info(f'Processing expired user: {user.phone_number} (paid_until: {user.paid_until})')
                
                # Send SMS notification BEFORE disconnecting
                if _send_expiry_sms(user):
                    sms_sent += 1
                
                # Get all active devices for this user
                devices = user.devices.filter(is_active=True)
                
                # Check if user belongs to a tenant (multi-tenant mode)
                if user.tenant:
                    # Use tenant-aware disconnect for multi-tenant SaaS
                    for device in devices:
                        try:
                            result = disconnect_user_from_tenant_routers(
                                user=user,
                                mac_address=device.mac_address
                            )
                            
                            if result.get('success'):
                                logger.info(f'Successfully disconnected {user.phone_number} - {device.mac_address} from tenant routers')
                                logger.debug(f'  - Routers succeeded: {result.get("routers_succeeded", 0)}')
                            else:
                                logger.warning(f'Disconnect result for {user.phone_number} - {device.mac_address}: {result}')
                            
                            # Mark device as inactive in database
                            device.is_active = False
                            device.save()
                            devices_deactivated += 1
                            
                        except Exception as device_error:
                            logger.error(f'Error disconnecting device {device.mac_address} for {user.phone_number}: {str(device_error)}')
                            failed_count += 1
                    
                    # Also try to disconnect by username only (for orphaned sessions)
                    try:
                        disconnect_user_from_tenant_routers(user=user, mac_address=None)
                    except Exception:
                        pass
                else:
                    # Fallback to legacy global router for users without tenant
                    for device in devices:
                        try:
                            result = disconnect_user_from_mikrotik(
                                username=user.phone_number,
                                mac_address=device.mac_address
                            )
                            
                            if result.get('success'):
                                logger.info(f'Successfully disconnected {user.phone_number} - {device.mac_address} from MikroTik')
                            else:
                                logger.warning(f'Disconnect result for {user.phone_number} - {device.mac_address}: {result}')
                            
                            # Mark device as inactive in database
                            device.is_active = False
                            device.save()
                            devices_deactivated += 1
                            
                        except Exception as device_error:
                            logger.error(f'Error disconnecting device {device.mac_address} for {user.phone_number}: {str(device_error)}')
                            failed_count += 1
                    
                    # Also try to disconnect by username only (for orphaned sessions)
                    try:
                        disconnect_user_from_mikrotik(username=user.phone_number, mac_address=None)
                    except Exception:
                        pass
                
                # Deactivate user in database
                user.deactivate_access()
                disconnected_count += 1
                logger.info(f'User {user.phone_number} deactivated after expiration')
                
            except Exception as user_error:
                logger.error(f'Error processing expired user {user.phone_number}: {str(user_error)}')
                failed_count += 1
        
        logger.info(f'Expired user cleanup complete: {disconnected_count} users disconnected, {devices_deactivated} devices deactivated, {sms_sent} SMS sent, {failed_count} failures')
        
        return {
            'success': True,
            'disconnected': disconnected_count,
            'devices_deactivated': devices_deactivated,
            'sms_sent': sms_sent,
            'failed': failed_count,
            'total_checked': expired_users.count()
        }
        
    except Exception as e:
        logger.error(f'Error in disconnect_expired_users task: {str(e)}')
        return {
            'success': False,
            'error': str(e)
        }


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
        if not hasattr(settings, 'NEXTSMS_USERNAME') or not settings.NEXTSMS_USERNAME:
            logger.debug("NextSMS not configured, skipping SMS")
            return False
        
        sms_api = NextSMSAPI()
        result = sms_api.send_access_expired(phone_number)
        
        if result.get('success'):
            logger.info(f'📱 Sent expiry SMS to {phone_number}')
            
            # Log the SMS
            SMSLog.objects.create(
                tenant=user.tenant if hasattr(user, 'tenant') else None,
                phone_number=phone_number,
                message="Access expired notification",
                sms_type="expired",
                success=True,
                response_data=result
            )
            return True
        else:
            logger.warning(f'Failed to send expiry SMS to {phone_number}: {result.get("message")}')
            return False
            
    except Exception as e:
        logger.error(f'Error sending expiry SMS to {user.phone_number}: {str(e)}')
        return False


def cleanup_inactive_devices():
    """
    Clean up devices that haven't been seen in a while
    """
    try:
        from datetime import timedelta
        threshold = timezone.now() - timedelta(days=30)
        
        old_devices = Device.objects.filter(
            last_seen__lt=threshold,
            is_active=True
        )
        
        count = 0
        for device in old_devices:
            try:
                device.is_active = False
                device.save()
                count += 1
                logger.info(f'Deactivated old device {device.mac_address} for user {device.user.phone_number}')
            except Exception as e:
                logger.error(f'Error deactivating device {device.id}: {str(e)}')
        
        logger.info(f'Inactive device cleanup: {count} devices deactivated')
        
        return {
            'success': True,
            'deactivated': count
        }
        
    except Exception as e:
        logger.error(f'Error in cleanup_inactive_devices task: {str(e)}')
        return {
            'success': False,
            'error': str(e)
        }


def send_expiry_notifications():
    """
    Send SMS notifications to users whose access is about to expire.
    This should be run hourly via cron.
    
    Notifies users 1 hour before their access expires.
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
            expiry_notification_sent=False
        )
        
        notified_count = 0
        failed_count = 0
        
        nextsms = NextSMSAPI()
        
        for user in users_to_notify:
            try:
                # Calculate remaining time
                remaining = user.paid_until - now
                remaining_minutes = int(remaining.total_seconds() / 60)
                
                # Send SMS notification
                message = f"Kitonga WiFi: Your internet access expires in {remaining_minutes} minutes. To continue using WiFi, please make a payment or redeem a voucher."
                
                result = nextsms.send_sms(user.phone_number, message)
                
                if result.get('success'):
                    user.expiry_notification_sent = True
                    user.save()
                    notified_count += 1
                    logger.info(f'Sent expiry notification to {user.phone_number}')
                    
                    # Log SMS
                    SMSLog.objects.create(
                        phone_number=user.phone_number,
                        message=message,
                        sms_type='expiry_notification',
                        success=True,
                        response_data=result
                    )
                else:
                    failed_count += 1
                    logger.warning(f'Failed to send expiry notification to {user.phone_number}: {result}')
                    
            except Exception as user_error:
                failed_count += 1
                logger.error(f'Error sending notification to {user.phone_number}: {str(user_error)}')
        
        logger.info(f'Expiry notifications: {notified_count} sent, {failed_count} failed')
        
        return {
            'success': True,
            'notified': notified_count,
            'failed': failed_count,
            'total_checked': users_to_notify.count()
        }
        
    except Exception as e:
        logger.error(f'Error in send_expiry_notifications task: {str(e)}')
        return {
            'success': False,
            'error': str(e)
        }