"""
Subscription Management for Kitonga SaaS Platform
Handles tenant subscription payments via ClickPesa, usage metering, and limits
"""

import logging
import uuid
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.conf import settings

from .models import (
    Tenant,
    SubscriptionPlan,
    TenantSubscriptionPayment,
    Bundle,
    User,
    Voucher,
    Router,
    Device,
)
from .clickpesa import ClickPesaAPI

logger = logging.getLogger(__name__)


# =============================================================================
# SUBSCRIPTION PAYMENT MANAGEMENT
# =============================================================================


class SubscriptionManager:
    """
    Manages tenant subscriptions: payments, renewals, and status updates
    """

    def __init__(self, tenant: Tenant):
        self.tenant = tenant
        # Use platform ClickPesa API (uses settings for credentials)
        self.clickpesa = ClickPesaAPI()

    def create_subscription_payment(
        self, plan: SubscriptionPlan, billing_cycle: str = "monthly"
    ) -> dict:
        """
        Create a ClickPesa payment request for subscription

        Args:
            plan: The subscription plan to purchase
            billing_cycle: 'monthly' or 'yearly'

        Returns:
            dict with payment details including checkout URL
        """
        # Calculate amount based on billing cycle
        if billing_cycle == "yearly":
            amount = plan.yearly_price
            period_days = 365
        else:
            amount = plan.monthly_price
            period_days = 30

        # Generate unique transaction ID (alphanumeric only for ClickPesa)
        # ClickPesa requires orderReference ≤ 20 characters
        # Format: "SUB" (3) + slug (up to 9) + uuid (8) = max 20 chars
        slug_part = self.tenant.slug.replace('-', '').upper()[:9]
        transaction_id = f"SUB{slug_part}{uuid.uuid4().hex[:8].upper()}"

        # Calculate subscription period
        now = timezone.now()

        # If tenant has active subscription, extend from end date
        if self.tenant.subscription_ends_at and self.tenant.subscription_ends_at > now:
            period_start = self.tenant.subscription_ends_at
        else:
            period_start = now

        period_end = period_start + timedelta(days=period_days)

        # Create payment record
        payment = TenantSubscriptionPayment.objects.create(
            tenant=self.tenant,
            plan=plan,
            amount=amount,
            currency=plan.currency,
            billing_cycle=billing_cycle,
            transaction_id=transaction_id,
            period_start=period_start,
            period_end=period_end,
            status="pending",
        )

        # Create ClickPesa payment request
        try:
            # Validate phone number before calling ClickPesa
            phone = self.tenant.business_phone
            if not phone or not str(phone).strip():
                payment.status = "failed"
                payment.save()
                logger.error(
                    f"Cannot create subscription payment for {self.tenant.slug}: "
                    "business_phone is empty"
                )
                return {
                    "success": False,
                    "error": (
                        "No business phone number configured for this tenant. "
                        "Please update your business phone in settings."
                    ),
                }

            response = self.clickpesa.initiate_payment(
                phone_number=phone,
                amount=float(amount),
                order_reference=transaction_id,
            )

            if response.get("success"):
                payment.payment_reference = response.get("order_reference", "")
                payment.save()

                return {
                    "success": True,
                    "payment_id": payment.id,
                    "transaction_id": transaction_id,
                    "amount": float(amount),
                    "currency": plan.currency,
                    "order_reference": response.get("order_reference"),
                    "plan": plan.display_name,
                    "billing_cycle": billing_cycle,
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "message": response.get(
                        "message", "Payment request sent to your phone"
                    ),
                }
            else:
                payment.status = "failed"
                payment.save()
                return {
                    "success": False,
                    "error": response.get("message", "Payment initiation failed"),
                }

        except Exception as e:
            payment.status = "failed"
            payment.save()
            logger.error(
                f"Failed to create subscription payment for {self.tenant.slug}: {e}"
            )
            return {"success": False, "error": str(e)}

    def process_payment_callback(
        self,
        transaction_id: str,
        status: str,
        payment_reference: str = None,
        channel: str = None,
    ) -> bool:
        """
        Process payment callback from ClickPesa

        Returns:
            bool: True if subscription was activated/renewed
        """
        try:
            payment = TenantSubscriptionPayment.objects.get(
                transaction_id=transaction_id
            )
        except TenantSubscriptionPayment.DoesNotExist:
            logger.error(f"Subscription payment not found: {transaction_id}")
            return False

        # Normalize status - ClickPesa may send different formats
        status_upper = status.upper()
        if status_upper in ["PAYMENT RECEIVED", "COMPLETED", "SUCCESS", "SUCCESSFUL"]:
            return self._activate_subscription(payment, payment_reference, channel)
        elif status_upper in [
            "PAYMENT FAILED",
            "PAYMENT CANCELLED",
            "FAILED",
            "CANCELLED",
        ]:
            payment.status = "failed"
            payment.save()
            return False

        return False

    @transaction.atomic
    def _activate_subscription(
        self,
        payment: TenantSubscriptionPayment,
        payment_reference: str = None,
        channel: str = None,
    ) -> bool:
        """
        Activate or renew subscription after successful payment
        """
        payment.status = "completed"
        payment.completed_at = timezone.now()
        payment.payment_reference = payment_reference or payment.payment_reference
        payment.payment_method = channel or "clickpesa"
        payment.save()

        # Update tenant subscription
        tenant = payment.tenant
        tenant.subscription_plan = payment.plan
        tenant.subscription_status = "active"
        tenant.billing_cycle = payment.billing_cycle
        tenant.subscription_started_at = (
            tenant.subscription_started_at or payment.period_start
        )
        tenant.subscription_ends_at = payment.period_end
        tenant.save()

        logger.info(
            f"Subscription activated for {tenant.slug}: {payment.plan.display_name} until {payment.period_end}"
        )

        # Send confirmation SMS
        self._send_subscription_confirmation(tenant, payment)

        return True

    def _send_subscription_confirmation(
        self, tenant: Tenant, payment: TenantSubscriptionPayment
    ):
        """Send SMS confirmation for subscription payment"""
        try:
            from .nextsms import NextSMSAPI

            message = (
                f"Kitonga Subscription Confirmed!\n"
                f"Plan: {payment.plan.display_name}\n"
                f"Amount: TZS {payment.amount:,.0f}\n"
                f"Valid until: {payment.period_end.strftime('%d/%m/%Y')}\n"
                f"Thank you for choosing Kitonga!"
            )

            sms_client = NextSMSAPI()
            sms_client.send_sms(tenant.business_phone, message)

        except Exception as e:
            logger.error(f"Failed to send subscription confirmation SMS: {e}")

    def check_subscription_status(self) -> dict:
        """
        Check current subscription status and return details
        """
        tenant = self.tenant
        now = timezone.now()

        status = {
            "tenant_slug": tenant.slug,
            "business_name": tenant.business_name,
            "subscription_status": tenant.subscription_status,
            "plan": None,
            "is_valid": False,
            "days_remaining": 0,
            "is_trial": False,
            "trial_days_remaining": 0,
        }

        if tenant.subscription_plan:
            status["plan"] = {
                "name": tenant.subscription_plan.name,
                "display_name": tenant.subscription_plan.display_name,
                "monthly_price": float(tenant.subscription_plan.monthly_price),
            }

        # Check trial status
        if tenant.subscription_status == "trial" and tenant.trial_ends_at:
            if tenant.trial_ends_at > now:
                status["is_trial"] = True
                status["is_valid"] = True
                status["trial_days_remaining"] = (tenant.trial_ends_at - now).days

        # Check active subscription
        if tenant.subscription_status == "active" and tenant.subscription_ends_at:
            if tenant.subscription_ends_at > now:
                status["is_valid"] = True
                status["days_remaining"] = (tenant.subscription_ends_at - now).days

        return status

    def get_renewal_reminder(self) -> dict | None:
        """
        Check if tenant needs renewal reminder (7 days before expiry)
        """
        tenant = self.tenant
        now = timezone.now()

        if tenant.subscription_status != "active" or not tenant.subscription_ends_at:
            return None

        days_remaining = (tenant.subscription_ends_at - now).days

        if 0 < days_remaining <= 7:
            return {
                "days_remaining": days_remaining,
                "expires_at": tenant.subscription_ends_at.isoformat(),
                "plan": (
                    tenant.subscription_plan.display_name
                    if tenant.subscription_plan
                    else None
                ),
                "renewal_amount": (
                    float(tenant.subscription_plan.monthly_price)
                    if tenant.subscription_plan
                    else 0
                ),
            }

        return None


# =============================================================================
# USAGE METERING & LIMIT ENFORCEMENT
# =============================================================================


class UsageMeter:
    """
    Track and enforce usage limits based on subscription plan
    """

    def __init__(self, tenant: Tenant):
        self.tenant = tenant
        self.plan = tenant.subscription_plan

    def get_usage_summary(self) -> dict:
        """
        Get complete usage summary for the tenant
        """
        if not self.plan:
            return {"error": "No subscription plan assigned"}

        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        return {
            "routers": self._get_router_usage(),
            "wifi_users": self._get_wifi_user_usage(),
            "vouchers_this_month": self._get_voucher_usage(month_start),
            "locations": self._get_location_usage(),
            "staff": self._get_staff_usage(),
            "subscription_valid": self.tenant.is_subscription_valid(),
        }

    def _get_router_usage(self) -> dict:
        used = self.tenant.routers.filter(is_active=True).count()
        limit = self.plan.max_routers if self.plan else 0
        return {
            "used": used,
            "limit": limit if limit < 999999 else "Unlimited",
            "available": max(0, limit - used) if limit < 999999 else "Unlimited",
            "percentage": (
                round((used / limit) * 100, 1) if limit and limit < 999999 else 0
            ),
        }

    def _get_wifi_user_usage(self) -> dict:
        used = self.tenant.wifi_users.count()
        limit = self.plan.max_wifi_users if self.plan else 0
        return {
            "used": used,
            "limit": limit if limit < 999999 else "Unlimited",
            "available": max(0, limit - used) if limit < 999999 else "Unlimited",
            "percentage": (
                round((used / limit) * 100, 1) if limit and limit < 999999 else 0
            ),
        }

    def _get_voucher_usage(self, month_start) -> dict:
        used = self.tenant.vouchers.filter(created_at__gte=month_start).count()
        limit = self.plan.max_vouchers_per_month if self.plan else 0
        return {
            "used": used,
            "limit": limit if limit < 999999 else "Unlimited",
            "available": max(0, limit - used) if limit < 999999 else "Unlimited",
            "percentage": (
                round((used / limit) * 100, 1) if limit and limit < 999999 else 0
            ),
        }

    def _get_location_usage(self) -> dict:
        used = self.tenant.locations.count()
        limit = self.plan.max_locations if self.plan else 0
        return {
            "used": used,
            "limit": limit if limit < 999999 else "Unlimited",
            "available": max(0, limit - used) if limit < 999999 else "Unlimited",
        }

    def _get_staff_usage(self) -> dict:
        used = self.tenant.staff_members.filter(is_active=True).count()
        limit = self.plan.max_staff_accounts if self.plan else 0
        return {
            "used": used,
            "limit": limit if limit < 999999 else "Unlimited",
            "available": max(0, limit - used) if limit < 999999 else "Unlimited",
        }

    # Limit Check Methods

    def can_add_router(self) -> tuple[bool, str]:
        """Check if tenant can add another router"""
        if not self._check_subscription_valid():
            return False, "Subscription expired or invalid"

        usage = self._get_router_usage()
        if usage["limit"] == "Unlimited":
            return True, ""

        if usage["used"] >= usage["limit"]:
            return (
                False,
                f"Router limit reached ({usage['limit']}). Upgrade your plan to add more routers.",
            )

        return True, ""

    def can_add_wifi_user(self) -> tuple[bool, str]:
        """Check if tenant can add another WiFi user"""
        if not self._check_subscription_valid():
            return False, "Subscription expired or invalid"

        usage = self._get_wifi_user_usage()
        if usage["limit"] == "Unlimited":
            return True, ""

        if usage["used"] >= usage["limit"]:
            return (
                False,
                f"WiFi user limit reached ({usage['limit']}). Upgrade your plan.",
            )

        return True, ""

    def can_create_voucher(self) -> tuple[bool, str]:
        """Check if tenant can create more vouchers this month"""
        if not self._check_subscription_valid():
            return False, "Subscription expired or invalid"

        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        usage = self._get_voucher_usage(month_start)

        if usage["limit"] == "Unlimited":
            return True, ""

        if usage["used"] >= usage["limit"]:
            return (
                False,
                f"Monthly voucher limit reached ({usage['limit']}). Upgrade your plan or wait until next month.",
            )

        return True, ""

    def can_add_location(self) -> tuple[bool, str]:
        """Check if tenant can add another location"""
        if not self._check_subscription_valid():
            return False, "Subscription expired or invalid"

        usage = self._get_location_usage()
        if usage["limit"] == "Unlimited":
            return True, ""

        if usage["used"] >= usage["limit"]:
            return (
                False,
                f"Location limit reached ({usage['limit']}). Upgrade to add more locations.",
            )

        return True, ""

    def can_add_staff(self) -> tuple[bool, str]:
        """Check if tenant can add another staff member"""
        if not self._check_subscription_valid():
            return False, "Subscription expired or invalid"

        usage = self._get_staff_usage()
        if usage["limit"] == "Unlimited":
            return True, ""

        if usage["used"] >= usage["limit"]:
            return (
                False,
                f"Staff account limit reached ({usage['limit']}). Upgrade your plan.",
            )

        return True, ""

    def has_feature(self, feature_name: str) -> bool:
        """Check if tenant's plan includes a specific feature"""
        if not self.plan:
            return False

        feature_map = {
            "custom_branding": self.plan.custom_branding,
            "custom_domain": self.plan.custom_domain,
            "api_access": self.plan.api_access,
            "white_label": self.plan.white_label,
            "priority_support": self.plan.priority_support,
            "analytics_dashboard": self.plan.analytics_dashboard,
            "sms_notifications": self.plan.sms_notifications,
        }

        return feature_map.get(feature_name, False)

    def _check_subscription_valid(self) -> bool:
        """Check if subscription is valid (active or in trial)"""
        return self.tenant.is_subscription_valid()


# =============================================================================
# REVENUE SHARING
# =============================================================================


class RevenueCalculator:
    """
    Calculate platform revenue share from tenant WiFi payments
    """

    def __init__(self, tenant: Tenant):
        self.tenant = tenant
        self.plan = tenant.subscription_plan

    def get_revenue_share_percentage(self) -> Decimal:
        """Get the revenue share percentage for this tenant's plan"""
        if not self.plan:
            return Decimal("5.00")  # Default 5% for no plan
        return self.plan.revenue_share_percentage

    def calculate_platform_share(self, payment_amount: Decimal) -> dict:
        """
        Calculate platform share from a WiFi payment

        Args:
            payment_amount: The total payment amount

        Returns:
            dict with platform_share, tenant_share, and percentage
        """
        percentage = self.get_revenue_share_percentage()
        platform_share = (payment_amount * percentage) / Decimal("100")
        tenant_share = payment_amount - platform_share

        return {
            "total_amount": float(payment_amount),
            "revenue_share_percentage": float(percentage),
            "platform_share": float(platform_share),
            "tenant_share": float(tenant_share),
        }

    def get_monthly_revenue_report(self, year: int = None, month: int = None) -> dict:
        """
        Generate monthly revenue report for a tenant
        """
        from .models import Payment

        now = timezone.now()
        year = year or now.year
        month = month or now.month

        # Get all completed payments for the month
        payments = Payment.objects.filter(
            tenant=self.tenant,
            status="completed",
            completed_at__year=year,
            completed_at__month=month,
        )

        total_revenue = sum(p.amount for p in payments)
        percentage = self.get_revenue_share_percentage()
        platform_share = (total_revenue * percentage) / Decimal("100")
        tenant_share = total_revenue - platform_share

        return {
            "tenant": self.tenant.business_name,
            "period": f"{year}-{month:02d}",
            "total_payments": payments.count(),
            "total_revenue": float(total_revenue),
            "revenue_share_percentage": float(percentage),
            "platform_share": float(platform_share),
            "tenant_share": float(tenant_share),
            "currency": "TZS",
        }


# =============================================================================
# SUBSCRIPTION TASKS (for cron jobs)
# =============================================================================


def check_expiring_subscriptions():
    """
    Check for subscriptions expiring in 7 days and send reminders
    Called daily via cron
    """
    from .nextsms import NextSMSAPI

    now = timezone.now()
    warning_date = now + timedelta(days=7)

    expiring_tenants = Tenant.objects.filter(
        subscription_status="active",
        subscription_ends_at__lte=warning_date,
        subscription_ends_at__gt=now,
        is_active=True,
    )

    sms_client = NextSMSAPI()

    for tenant in expiring_tenants:
        days_left = (tenant.subscription_ends_at - now).days

        try:
            message = (
                f"Kitonga Subscription Reminder\n"
                f"Your {tenant.subscription_plan.display_name} plan expires in {days_left} days.\n"
                f"Renew now to avoid service interruption.\n"
                f"Amount: TZS {tenant.subscription_plan.monthly_price:,.0f}/month"
            )

            sms_client.send_sms(tenant.business_phone, message)
            logger.info(
                f"Sent expiry reminder to {tenant.slug} ({days_left} days left)"
            )

        except Exception as e:
            logger.error(f"Failed to send expiry reminder to {tenant.slug}: {e}")

    return len(expiring_tenants)


def suspend_expired_subscriptions(grace_days: int = 0) -> dict:
    """
    Suspend tenants whose subscription has ended.

    Args:
        grace_days: number of days to wait AFTER subscription_ends_at before suspending.
                    e.g. grace_days=3 will suspend tenants whose subscription_ends_at <= now - 3 days.

    Behavior:
    - Marks tenant.subscription_status = 'suspended'.
    - Disconnects and deactivates all active users for that tenant.
    - Sends an SMS to the tenant business phone informing them of suspension.

    Returns:
        summary dict with counts and any errors encountered.
    """
    now = timezone.now()
    cutoff = now - timedelta(days=grace_days)

    logger.info(f"Checking for tenants to suspend (grace_days={grace_days})")

    summary = {
        "checked_at": now.isoformat(),
        "grace_days": grace_days,
        "suspended": [],
        "errors": [],
    }

    try:
        expired_tenants = Tenant.objects.filter(
            subscription_status="active",
            subscription_ends_at__isnull=False,
            subscription_ends_at__lte=cutoff,
        )

        if not expired_tenants.exists():
            logger.info("No tenants found for suspension at this time")
            return summary

        # Import helpers locally to avoid circular imports
        from .mikrotik import disconnect_user_from_tenant_routers
        from .nextsms import NextSMSAPI
        from .models import AccessLog

        sms_client = None

        for tenant in expired_tenants:
            try:
                logger.info(
                    f"Suspending tenant {tenant.slug} (ended: {tenant.subscription_ends_at})"
                )

                # Mark tenant suspended
                tenant.subscription_status = "suspended"
                tenant.save()

                # Disconnect and deactivate all active users for this tenant
                active_users = User.objects.filter(tenant=tenant, is_active=True)
                disconnected_count = 0

                for user in active_users:
                    try:
                        # Attempt tenant-scoped disconnect
                        try:
                            disconnect_user_from_tenant_routers(
                                user=user, mac_address=None
                            )
                        except Exception as disconn_err:
                            logger.warning(
                                f"Failed tenant-scoped disconnect for user {user.phone_number}: {disconn_err}"
                            )

                        # Deactivate user access in DB
                        try:
                            user.deactivate_access()
                        except Exception as deactivate_err:
                            logger.warning(
                                f"Failed to deactivate access for user {user.phone_number}: {deactivate_err}"
                            )

                        # Create an AccessLog entry for auditing
                        try:
                            AccessLog.objects.create(
                                tenant=tenant,
                                user=user,
                                device=None,
                                router=None,
                                ip_address="0.0.0.0",
                                mac_address="",
                                access_granted=False,
                                denial_reason="Tenant subscription suspended - auto action",
                            )
                        except Exception as log_err:
                            logger.debug(
                                f"Could not create AccessLog for {user.phone_number}: {log_err}"
                            )

                        disconnected_count += 1

                    except Exception as u_err:
                        logger.error(
                            f"Error processing user {user.phone_number} for suspension: {u_err}"
                        )

                # Send SMS notification to tenant contact
                try:
                    if not sms_client:
                        sms_client = NextSMSAPI()

                    phone = tenant.business_phone
                    if phone:
                        message = (
                            f"Kitonga: Your subscription for {tenant.business_name} has expired "
                            f"and your account has been suspended. "
                            f"Please renew to restore service.\n"
                            f"If you believe this is a mistake, contact support."
                        )
                        sms_client.send_sms(phone, message)
                        logger.info(
                            f"Sent suspension SMS to tenant {tenant.slug} at {phone}"
                        )
                except Exception as sms_err:
                    logger.warning(
                        f"Failed to send suspension SMS for tenant {tenant.slug}: {sms_err}"
                    )

                summary["suspended"].append(
                    {"tenant": tenant.slug, "users_deactivated": disconnected_count}
                )

            except Exception as t_err:
                logger.error(f"Failed to suspend tenant {tenant.slug}: {t_err}")
                summary["errors"].append({"tenant": tenant.slug, "error": str(t_err)})

    except Exception as e:
        logger.error(f"Error checking expired tenants for suspension: {e}")
        summary["errors"].append({"general": str(e)})

    return summary


def expire_trials():
    """
    Handle trial expirations
    Called daily via cron
    """
    from .nextsms import NextSMSAPI

    now = timezone.now()

    expired_trials = Tenant.objects.filter(
        subscription_status="trial",
        trial_ends_at__lt=now,
        is_active=True,
    )

    sms_client = NextSMSAPI()
    expired_count = 0

    for tenant in expired_trials:
        tenant.subscription_status = "suspended"
        tenant.save()
        expired_count += 1

        # Notify tenant
        try:
            message = (
                f"Kitonga Trial Ended\n"
                f"Your 14-day free trial has ended.\n"
                f"Subscribe now to continue using Kitonga!\n"
                f"Plans start at TZS 30,000/month."
            )

            sms_client.send_sms(tenant.business_phone, message, sms_type="admin")

        except Exception as e:
            logger.error(
                f"Failed to send trial expiry notification to {tenant.slug}: {e}"
            )

        logger.info(f"Expired trial for {tenant.slug}")

    return expired_count
