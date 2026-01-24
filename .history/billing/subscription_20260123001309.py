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
    Tenant, SubscriptionPlan, TenantSubscriptionPayment,
    Bundle, User, Voucher, Router, Device
)   SubscriptionPlan,
from .clickpesa import ClickPesaAPI
    Bundle,
logger = logging.getLogger(__name__)
    Voucher,
    Router,
# =============================================================================
# SUBSCRIPTION PAYMENT MANAGEMENT
# =============================================================================

class SubscriptionManager:(__name__)
    """
    Manages tenant subscriptions: payments, renewals, and status updates
    """========================================================================
    BSCRIPTION PAYMENT MANAGEMENT
    def __init__(self, tenant: Tenant):========================================
        self.tenant = tenant
        # Use platform ClickPesa API (uses settings for credentials)
        self.clickpesa = ClickPesaAPI()
    """
    def create_subscription_payment(self, plan: SubscriptionPlan, billing_cycle: str = 'monthly') -> dict:
        """
        Create a ClickPesa payment request for subscription
        __init__(self, tenant: Tenant):
        Args:tenant = tenant
            plan: The subscription plan to purchase for credentials)
            billing_cycle: 'monthly' or 'yearly'
        
        Returns:ubscription_payment(
            dict with payment details including checkout URLmonthly"
        """ct:
        # Calculate amount based on billing cycle
        if billing_cycle == 'yearly':quest for subscription
            amount = plan.yearly_price
            period_days = 365
        else:lan: The subscription plan to purchase
            amount = plan.monthly_price 'yearly'
            period_days = 30
        Returns:
        # Generate unique transaction ID (alphanumeric only for ClickPesa)
        transaction_id = f"SUB{self.tenant.slug.replace('-', '').upper()}{uuid.uuid4().hex[:8].upper()}"
        # Calculate amount based on billing cycle
        # Calculate subscription period
        now = timezone.now()arly_price
            period_days = 365
        # If tenant has active subscription, extend from end date
        if self.tenant.subscription_ends_at and self.tenant.subscription_ends_at > now:
            period_start = self.tenant.subscription_ends_at
        else:
            period_start = nowsaction ID (alphanumeric only for ClickPesa)
        transaction_id = f"SUB{self.tenant.slug.replace('-', '').upper()}{uuid.uuid4().hex[:8].upper()}"
        period_end = period_start + timedelta(days=period_days)
        # Calculate subscription period
        # Create payment record
        payment = TenantSubscriptionPayment.objects.create(
            tenant=self.tenant,subscription, extend from end date
            plan=plan,.subscription_ends_at and self.tenant.subscription_ends_at > now:
            amount=amount, self.tenant.subscription_ends_at
            currency=plan.currency,
            billing_cycle=billing_cycle,
            transaction_id=transaction_id,
            period_start=period_start,medelta(days=period_days)
            period_end=period_end,
            status='pending'ord
        )ayment = TenantSubscriptionPayment.objects.create(
            tenant=self.tenant,
        # Create ClickPesa payment request
        try:amount=amount,
            response = self.clickpesa.initiate_payment(
                phone_number=self.tenant.business_phone,
                amount=float(amount),n_id,
                order_reference=transaction_id
            )eriod_end=period_end,
            status="pending",
            if response.get('success'):
                payment.payment_reference = response.get('order_reference', '')
                payment.save()ment request
                
                return {elf.clickpesa.initiate_payment(
                    'success': True,nant.business_phone,
                    'payment_id': payment.id,
                    'transaction_id': transaction_id,
                    'amount': float(amount),
                    'currency': plan.currency,
                    'order_reference': response.get('order_reference'),
                    'plan': plan.display_name,sponse.get("order_reference", "")
                    'billing_cycle': billing_cycle,
                    'period_start': period_start.isoformat(),
                    'period_end': period_end.isoformat(),
                    'message': response.get('message', 'Payment request sent to your phone'),
                }   "payment_id": payment.id,
            else:   "transaction_id": transaction_id,
                payment.status = 'failed't),
                payment.save(): plan.currency,
                return {er_reference": response.get("order_reference"),
                    'success': False,lay_name,
                    'error': response.get('message', 'Payment initiation failed')
                }   "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
        except Exception as e: response.get(
            payment.status = 'failed'ayment request sent to your phone"
            payment.save()
            logger.error(f"Failed to create subscription payment for {self.tenant.slug}: {e}")
            return {
                'success': False,"failed"
                'error': str(e)
            }   return {
                    "success": False,
    def process_payment_callback(self, transaction_id: str, status: str, failed"),
                                  payment_reference: str = None, channel: str = None) -> bool:
        """
        Process payment callback from ClickPesa
            payment.status = "failed"
        Returns:ent.save()
            bool: True if subscription was activated/renewed
        """     f"Failed to create subscription payment for {self.tenant.slug}: {e}"
        try:)
            payment = TenantSubscriptionPayment.objects.get(transaction_id=transaction_id)
        except TenantSubscriptionPayment.DoesNotExist:
            logger.error(f"Subscription payment not found: {transaction_id}")
            return False
        transaction_id: str,
        # Normalize status - ClickPesa may send different formats
        status_upper = status.upper(),
        if status_upper in ['PAYMENT RECEIVED', 'COMPLETED', 'SUCCESS', 'SUCCESSFUL']:
            return self._activate_subscription(payment, payment_reference, channel)
        elif status_upper in ['PAYMENT FAILED', 'PAYMENT CANCELLED', 'FAILED', 'CANCELLED']:
            payment.status = 'failed' ClickPesa
            payment.save()
            return False
            bool: True if subscription was activated/renewed
        return False
        try:
    @transaction.atomicenantSubscriptionPayment.objects.get(
    def _activate_subscription(self, payment: TenantSubscriptionPayment, 
                               payment_reference: str = None, channel: str = None) -> bool:
        """ept TenantSubscriptionPayment.DoesNotExist:
        Activate or renew subscription after successful paymentnsaction_id}")
        """ return False
        payment.status = 'completed'
        payment.completed_at = timezone.now()nd different formats
        payment.payment_reference = payment_reference or payment.payment_reference
        payment.payment_method = channel or 'clickpesa'TED", "SUCCESS", "SUCCESSFUL"]:
        payment.save()f._activate_subscription(payment, payment_reference, channel)
        elif status_upper in [
        # Update tenant subscription
        tenant = payment.tenant,
        tenant.subscription_plan = payment.plan
        tenant.subscription_status = 'active'
        tenant.billing_cycle = payment.billing_cycle
        tenant.subscription_started_at = tenant.subscription_started_at or payment.period_start
        tenant.subscription_ends_at = payment.period_end
        tenant.save()lse
        
        logger.info(f"Subscription activated for {tenant.slug}: {payment.plan.display_name} until {payment.period_end}")
        
        # Send confirmation SMS
        self._send_subscription_confirmation(tenant, payment)
        self,
        return TruenantSubscriptionPayment,
        payment_reference: str = None,
    def _send_subscription_confirmation(self, tenant: Tenant, payment: TenantSubscriptionPayment):
        """Send SMS confirmation for subscription payment"""
        try:
            from .nextsms import NextSMSAPIr successful payment
            
            message = (= "completed"
                f"Kitonga Subscription Confirmed!\n"
                f"Plan: {payment.plan.display_name}\n"or payment.payment_reference
                f"Amount: TZS {payment.amount:,.0f}\n""
                f"Valid until: {payment.period_end.strftime('%d/%m/%Y')}\n"
                f"Thank you for choosing Kitonga!"
            )ate tenant subscription
            nt = payment.tenant
            sms_client = NextSMSAPI()yment.plan
            sms_client.send_sms(tenant.business_phone, message)
            nt.billing_cycle = payment.billing_cycle
        except Exception as e:arted_at = (
            logger.error(f"Failed to send subscription confirmation SMS: {e}")
        )
    def check_subscription_status(self) -> dict:riod_end
        """ant.save()
        Check current subscription status and return details
        """ger.info(
        tenant = self.tenantctivated for {tenant.slug}: {payment.plan.display_name} until {payment.period_end}"
        now = timezone.now()
        
        status = {firmation SMS
            'tenant_slug': tenant.slug,ation(tenant, payment)
            'business_name': tenant.business_name,
            'subscription_status': tenant.subscription_status,
            'plan': None,
            'is_valid': False,firmation(
            'days_remaining': 0,yment: TenantSubscriptionPayment
            'is_trial': False,
            'trial_days_remaining': 0,ubscription payment"""
        }ry:
            from .nextsms import NextSMSAPI
        if tenant.subscription_plan:
            status['plan'] = {
                'name': tenant.subscription_plan.name,
                'display_name': tenant.subscription_plan.display_name,
                'monthly_price': float(tenant.subscription_plan.monthly_price),
            }   f"Valid until: {payment.period_end.strftime('%d/%m/%Y')}\n"
                f"Thank you for choosing Kitonga!"
        # Check trial status
        if tenant.subscription_status == 'trial' and tenant.trial_ends_at:
            if tenant.trial_ends_at > now:
                status['is_trial'] = Truesiness_phone, message)
                status['is_valid'] = True
                status['trial_days_remaining'] = (tenant.trial_ends_at - now).days
            logger.error(f"Failed to send subscription confirmation SMS: {e}")
        # Check active subscription
        if tenant.subscription_status == 'active' and tenant.subscription_ends_at:
            if tenant.subscription_ends_at > now:
                status['is_valid'] = True and return details
                status['days_remaining'] = (tenant.subscription_ends_at - now).days
        tenant = self.tenant
        return statuse.now()
    
    def get_renewal_reminder(self) -> dict | None:
        """ "tenant_slug": tenant.slug,
        Check if tenant needs renewal reminder (7 days before expiry)
        """ "subscription_status": tenant.subscription_status,
        tenant = self.tenant
        now = timezone.now()e,
            "days_remaining": 0,
        if tenant.subscription_status != 'active' or not tenant.subscription_ends_at:
            return None_remaining": 0,
        }
        days_remaining = (tenant.subscription_ends_at - now).days
        if tenant.subscription_plan:
        if 0 < days_remaining <= 7:
            return {e": tenant.subscription_plan.name,
                'days_remaining': days_remaining,on_plan.display_name,
                'expires_at': tenant.subscription_ends_at.isoformat(),y_price),
                'plan': tenant.subscription_plan.display_name if tenant.subscription_plan else None,
                'renewal_amount': float(tenant.subscription_plan.monthly_price) if tenant.subscription_plan else 0,
            }ck trial status
        if tenant.subscription_status == "trial" and tenant.trial_ends_at:
        return Nonent.trial_ends_at > now:
                status["is_trial"] = True
                status["is_valid"] = True
# =============================================================================ays
# USAGE METERING & LIMIT ENFORCEMENT
# =============================================================================
        if tenant.subscription_status == "active" and tenant.subscription_ends_at:
class UsageMeter:nant.subscription_ends_at > now:
    """         status["is_valid"] = True
    Track and enforce usage limits based on subscription planon_ends_at - now).days
    """
        return status
    def __init__(self, tenant: Tenant):
        self.tenant = tenant(self) -> dict | None:
        self.plan = tenant.subscription_plan
        Check if tenant needs renewal reminder (7 days before expiry)
    def get_usage_summary(self) -> dict:
        """ant = self.tenant
        Get complete usage summary for the tenant
        """
        if not self.plan:ption_status != "active" or not tenant.subscription_ends_at:
            return {'error': 'No subscription plan assigned'}
        
        now = timezone.now()nant.subscription_ends_at - now).days
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if 0 < days_remaining <= 7:
        return {rn {
            'routers': self._get_router_usage(),,
            'wifi_users': self._get_wifi_user_usage(),_at.isoformat(),
            'vouchers_this_month': self._get_voucher_usage(month_start),
            'locations': self._get_location_usage(),_name
            'staff': self._get_staff_usage(),an
            'subscription_valid': self.tenant.is_subscription_valid(),
        }       ),
                "renewal_amount": (
    def _get_router_usage(self) -> dict:ption_plan.monthly_price)
        used = self.tenant.routers.filter(is_active=True).count()
        limit = self.plan.max_routers if self.plan else 0
        return {),
            'used': used,
            'limit': limit if limit < 999999 else 'Unlimited',
            'available': max(0, limit - used) if limit < 999999 else 'Unlimited',
            'percentage': round((used / limit) * 100, 1) if limit and limit < 999999 else 0,
        }
    ===========================================================================
    def _get_wifi_user_usage(self) -> dict:
        used = self.tenant.wifi_users.count()==================================
        limit = self.plan.max_wifi_users if self.plan else 0
        return {
            'used': used,
            'limit': limit if limit < 999999 else 'Unlimited',
            'available': max(0, limit - used) if limit < 999999 else 'Unlimited',
            'percentage': round((used / limit) * 100, 1) if limit and limit < 999999 else 0,
        }
    def __init__(self, tenant: Tenant):
    def _get_voucher_usage(self, month_start) -> dict:
        used = self.tenant.vouchers.filter(created_at__gte=month_start).count()
        limit = self.plan.max_vouchers_per_month if self.plan else 0
        return {e_summary(self) -> dict:
            'used': used,
            'limit': limit if limit < 999999 else 'Unlimited',
            'available': max(0, limit - used) if limit < 999999 else 'Unlimited',
            'percentage': round((used / limit) * 100, 1) if limit and limit < 999999 else 0,
        }   return {"error": "No subscription plan assigned"}
    
    def _get_location_usage(self) -> dict:
        used = self.tenant.locations.count()r=0, minute=0, second=0, microsecond=0)
        limit = self.plan.max_locations if self.plan else 0
        return {
            'used': used,lf._get_router_usage(),
            'limit': limit if limit < 999999 else 'Unlimited',
            'available': max(0, limit - used) if limit < 999999 else 'Unlimited',
        }   "locations": self._get_location_usage(),
            "staff": self._get_staff_usage(),
    def _get_staff_usage(self) -> dict:tenant.is_subscription_valid(),
        used = self.tenant.staff_members.filter(is_active=True).count()
        limit = self.plan.max_staff_accounts if self.plan else 0
        return {ter_usage(self) -> dict:
            'used': used,t.routers.filter(is_active=True).count()
            'limit': limit if limit < 999999 else 'Unlimited',
            'available': max(0, limit - used) if limit < 999999 else 'Unlimited',
        }   "used": used,
            "limit": limit if limit < 999999 else "Unlimited",
    # Limit Check Methodsmax(0, limit - used) if limit < 999999 else "Unlimited",
            "percentage": (
    def can_add_router(self) -> tuple[bool, str]: limit and limit < 999999 else 0
        """Check if tenant can add another router"""
        if not self._check_subscription_valid():
            return False, "Subscription expired or invalid"
        _get_wifi_user_usage(self) -> dict:
        usage = self._get_router_usage()unt()
        if usage['limit'] == 'Unlimited':if self.plan else 0
            return True, ""
            "used": used,
        if usage['used'] >= usage['limit']:9 else "Unlimited",
            return False, f"Router limit reached ({usage['limit']}). Upgrade your plan to add more routers."
            "percentage": (
        return True, ""used / limit) * 100, 1) if limit and limit < 999999 else 0
            ),
    def can_add_wifi_user(self) -> tuple[bool, str]:
        """Check if tenant can add another WiFi user"""
        if not self._check_subscription_valid(): dict:
            return False, "Subscription expired or invalid"month_start).count()
        limit = self.plan.max_vouchers_per_month if self.plan else 0
        usage = self._get_wifi_user_usage()
        if usage['limit'] == 'Unlimited':
            return True, ""if limit < 999999 else "Unlimited",
            "available": max(0, limit - used) if limit < 999999 else "Unlimited",
        if usage['used'] >= usage['limit']:
            return False, f"WiFi user limit reached ({usage['limit']}). Upgrade your plan."
            ),
        return True, ""
    
    def can_create_voucher(self) -> tuple[bool, str]:
        """Check if tenant can create more vouchers this month"""
        if not self._check_subscription_valid():plan else 0
            return False, "Subscription expired or invalid"
            "used": used,
        now = timezone.now()f limit < 999999 else "Unlimited",
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        usage = self._get_voucher_usage(month_start)
        
        if usage['limit'] == 'Unlimited':
            return True, ""staff_members.filter(is_active=True).count()
        limit = self.plan.max_staff_accounts if self.plan else 0
        if usage['used'] >= usage['limit']:
            return False, f"Monthly voucher limit reached ({usage['limit']}). Upgrade your plan or wait until next month."
            "limit": limit if limit < 999999 else "Unlimited",
        return True, "": max(0, limit - used) if limit < 999999 else "Unlimited",
        }
    def can_add_location(self) -> tuple[bool, str]:
        """Check if tenant can add another location"""
        if not self._check_subscription_valid():
            return False, "Subscription expired or invalid"
        """Check if tenant can add another router"""
        usage = self._get_location_usage()lid():
        if usage['limit'] == 'Unlimited':xpired or invalid"
            return True, ""
        usage = self._get_router_usage()
        if usage['used'] >= usage['limit']:
            return False, f"Location limit reached ({usage['limit']}). Upgrade to add more locations."
        
        return True, ""] >= usage["limit"]:
            return (
    def can_add_staff(self) -> tuple[bool, str]:
        """Check if tenant can add another staff member""" Upgrade your plan to add more routers.",
        if not self._check_subscription_valid():
            return False, "Subscription expired or invalid"
        return True, ""
        usage = self._get_staff_usage()
        if usage['limit'] == 'Unlimited':bool, str]:
            return True, ""can add another WiFi user"""
        if not self._check_subscription_valid():
        if usage['used'] >= usage['limit']:ired or invalid"
            return False, f"Staff account limit reached ({usage['limit']}). Upgrade your plan."
        usage = self._get_wifi_user_usage()
        return True, """] == "Unlimited":
            return True, ""
    def has_feature(self, feature_name: str) -> bool:
        """Check if tenant's plan includes a specific feature"""
        if not self.plan:
            return False
                f"WiFi user limit reached ({usage['limit']}). Upgrade your plan.",
        feature_map = {
            'custom_branding': self.plan.custom_branding,
            'custom_domain': self.plan.custom_domain,
            'api_access': self.plan.api_access,
            'white_label': self.plan.white_label,tr]:
            'priority_support': self.plan.priority_support,nth"""
            'analytics_dashboard': self.plan.analytics_dashboard,
            'sms_notifications': self.plan.sms_notifications,
        }
        now = timezone.now()
        return feature_map.get(feature_name, False)nute=0, second=0, microsecond=0)
        usage = self._get_voucher_usage(month_start)
    def _check_subscription_valid(self) -> bool:
        """Check if subscription is valid (active or in trial)"""
        return self.tenant.is_subscription_valid()

        if usage["used"] >= usage["limit"]:
# =============================================================================
# REVENUE SHARINGalse,
# =============================================================================r plan or wait until next month.",
            )
class RevenueCalculator:
    """ return True, ""
    Calculate platform revenue share from tenant WiFi payments
    """ can_add_location(self) -> tuple[bool, str]:
        """Check if tenant can add another location"""
    def __init__(self, tenant: Tenant):_valid():
        self.tenant = tenantubscription expired or invalid"
        self.plan = tenant.subscription_plan
        usage = self._get_location_usage()
    def get_revenue_share_percentage(self) -> Decimal:
        """Get the revenue share percentage for this tenant's plan"""
        if not self.plan:
            return Decimal('5.00')  # Default 5% for no plan
        return self.plan.revenue_share_percentage
                False,
    def calculate_platform_share(self, payment_amount: Decimal) -> dict:add more locations.",
        """ )
        Calculate platform share from a WiFi payment
        return True, ""
        Args:
            payment_amount: The total payment amount
        """Check if tenant can add another staff member"""
        Returns:elf._check_subscription_valid():
            dict with platform_share, tenant_share, and percentage
        """
        percentage = self.get_revenue_share_percentage()
        platform_share = (payment_amount * percentage) / Decimal('100')
        tenant_share = payment_amount - platform_share
        
        return {["used"] >= usage["limit"]:
            'total_amount': float(payment_amount),
            'revenue_share_percentage': float(percentage),
            'platform_share': float(platform_share),e['limit']}). Upgrade your plan.",
            'tenant_share': float(tenant_share),
        }
        return True, ""
    def get_monthly_revenue_report(self, year: int = None, month: int = None) -> dict:
        """_feature(self, feature_name: str) -> bool:
        Generate monthly revenue report for a tenantc feature"""
        """not self.plan:
        from .models import Payment
        
        now = timezone.now()
        year = year or now.yearself.plan.custom_branding,
        month = month or now.monthplan.custom_domain,
            "api_access": self.plan.api_access,
        # Get all completed payments for the month
        payments = Payment.objects.filter(priority_support,
            tenant=self.tenant,d": self.plan.analytics_dashboard,
            status='completed',: self.plan.sms_notifications,
            completed_at__year=year,
            completed_at__month=month
        )eturn feature_map.get(feature_name, False)
        
        total_revenue = sum(p.amount for p in payments)
        percentage = self.get_revenue_share_percentage()trial)"""
        platform_share = (total_revenue * percentage) / Decimal('100')
        tenant_share = total_revenue - platform_share
        
        return {===============================================================
            'tenant': self.tenant.business_name,
            'period': f"{year}-{month:02d}",===================================
            'total_payments': payments.count(),
            'total_revenue': float(total_revenue),
            'revenue_share_percentage': float(percentage),
            'platform_share': float(platform_share),
            'tenant_share': float(tenant_share), WiFi payments
            'currency': 'TZS',
        }
    def __init__(self, tenant: Tenant):
        self.tenant = tenant
# =============================================================================
# SUBSCRIPTION TASKS (for cron jobs)
# =============================================================================
        """Get the revenue share percentage for this tenant's plan"""
def check_expiring_subscriptions():
    """     return Decimal("5.00")  # Default 5% for no plan
    Check for subscriptions expiring in 7 days and send reminders
    Called daily via cron
    """ calculate_platform_share(self, payment_amount: Decimal) -> dict:
    from .nextsms import NextSMSAPI
        Calculate platform share from a WiFi payment
    now = timezone.now()
    warning_date = now + timedelta(days=7)
            payment_amount: The total payment amount
    expiring_tenants = Tenant.objects.filter(
        subscription_status='active',
        subscription_ends_at__lte=warning_date,are, and percentage
        subscription_ends_at__gt=now,
        is_active=Trueelf.get_revenue_share_percentage()
    )   platform_share = (payment_amount * percentage) / Decimal("100")
        tenant_share = payment_amount - platform_share
    sms_client = NextSMSAPI()
        return {
    for tenant in expiring_tenants:ayment_amount),
        days_left = (tenant.subscription_ends_at - now).days
            "platform_share": float(platform_share),
        try:"tenant_share": float(tenant_share),
            message = (
                f"Kitonga Subscription Reminder\n"
                f"Your {tenant.subscription_plan.display_name} plan expires in {days_left} days.\n"
                f"Renew now to avoid service interruption.\n"
                f"Amount: TZS {tenant.subscription_plan.monthly_price:,.0f}/month"
            )
             .models import Payment
            sms_client.send_sms(tenant.business_phone, message)
            logger.info(f"Sent expiry reminder to {tenant.slug} ({days_left} days left)")
             = year or now.year
        except Exception as e:onth
            logger.error(f"Failed to send expiry reminder to {tenant.slug}: {e}")
        # Get all completed payments for the month
    return len(expiring_tenants)ts.filter(
            tenant=self.tenant,
            status="completed",
def suspend_expired_subscriptions(grace_days: int = 0) -> dict:
    """     completed_at__month=month,
    Suspend tenants whose subscription has ended.

    Args: total_revenue = sum(p.amount for p in payments)
        grace_days: number of days to wait AFTER subscription_ends_at before suspending.ue_share_percentage()
                    e.g. grace_days=3 will suspend tenants whose subscription_ends_at <= now - 3 days.    platform_share = (total_revenue * percentage) / Decimal("100")
otal_revenue - platform_share
    Behavior:
    - Marks tenant.subscription_status = 'suspended'.
    - Disconnects and deactivates all active users for that tenant using tenant-aware Mikrotik routines.iness_name,
    - Sends an SMS to the tenant business phone informing them of suspension.:02d}",
ments": payments.count(),
    Returns:       "total_revenue": float(total_revenue),
        summary dict with counts and any errors encountered.        "revenue_share_percentage": float(percentage),
    """ float(platform_share),
    from django.utils import timezonere": float(tenant_share),
    from datetime import timedelta        "currency": "TZS",
    logger.info(f"Checking for tenants to suspend (grace_days={grace_days})")

    now = timezone.now()
    cutoff = now - timedelta(days=grace_days)===================================================
IPTION TASKS (for cron jobs)
    summary = {"checked_at": now.isoformat(), "grace_days": grace_days, "suspended": [], "errors": []}========================================================

    try:
        expired_tenants = Tenant.objects.filter(
            subscription_status="active",
            subscription_ends_at__isnull=False,eminders
            subscription_ends_at__lte=cutoff,
        )
xtsms import NextSMSAPI
        if not expired_tenants.exists():
            logger.info("No tenants found for suspension at this time")mezone.now()
            return summaryelta(days=7)

        # Import tenant-aware disconnect and SMS helpers locally to avoid circular importsring_tenants = Tenant.objects.filter(
        from .mikrotik import disconnect_user_from_tenant_routers
        from .nextsms import NextSMSAPI    subscription_ends_at__lte=warning_date,
        from .models import User, AccessLogat__gt=now,
        is_active=True,
        sms_client = None    )

        for tenant in expired_tenants.select_related().all():_client = NextSMSAPI()
            try:
                logger.info(f"Suspending tenant {tenant.slug} (ended: {tenant.subscription_ends_at})")g_tenants:
 days_left = (tenant.subscription_ends_at - now).days
                # Mark tenant suspended
                tenant.subscription_status = "suspended"    try:
                tenant.save()
            f"Kitonga Subscription Reminder\n"
                # Disconnect and deactivate all active users for this tenant_plan.display_name} plan expires in {days_left} days.\n"
                active_users = User.objects.filter(tenant=tenant, is_active=True) service interruption.\n"
                disconnected_count = 0{tenant.subscription_plan.monthly_price:,.0f}/month"
                for user in active_users:
                    try:
                        # Attempt tenant-scoped disconnect of all sessions        sms_client.send_sms(tenant.business_phone, message)
                        try:
                            disconnect_user_from_tenant_routers(user=user, mac_address=None)t expiry reminder to {tenant.slug} ({days_left} days left)"
                        except Exception as disconn_err:        )
                            logger.warning(
                                f"Failed tenant-scoped disconnect for user {user.phone_number} on tenant {tenant.slug}: {disconn_err}"
                            )ror(f"Failed to send expiry reminder to {tenant.slug}: {e}")

                        # Deactivate user access in DBrn len(expiring_tenants)
                        try:
                            user.deactivate_access()
                        except Exception as deactivate_err:
                            logger.warning(
                                f"Failed to deactivate access for user {user.phone_number}: {deactivate_err}"ns that have expired
                            )

                        # Create an AccessLog entry for auditing
                        try:
                            AccessLog.objects.create(ezone.now()
                                tenant=tenant,
                                user=user,filter(
                                device=None,e
                                router=None,
                                ip_address="0.0.0.0",
                                mac_address="",
                                access_granted=False,ended_count = 0
                                denial_reason="Tenant subscription suspended - auto action",
                            )for tenant in expired_tenants:
                        except Exception as log_err:ion_status = "suspended"
                            logger.debug(f"Could not create AccessLog for {user.phone_number}: {log_err}")        tenant.save()















































































    return expired_count            logger.info(f"Expired trial for {tenant.slug}")                    logger.error(f"Failed to send trial expiry notification to {tenant.slug}: {e}")        except Exception as e:                        sms_client.send_sms(tenant.business_phone, message, sms_type='admin')            sms_client = NextSMSAPI()                        )                f"Plans start at TZS 30,000/month."                f"Subscribe now to continue using Kitonga!\n"                f"Your 14-day free trial has ended.\n"                f"Kitonga Trial Ended\n"            message = (                        from .nextsms import NextSMSAPI        try:        # Notify tenant                expired_count += 1        tenant.save()        tenant.subscription_status = 'suspended'    for tenant in expired_trials:        expired_count = 0    sms_client = NextSMSAPI()        )        is_active=True        trial_ends_at__lt=now,        subscription_status='trial',    expired_trials = Tenant.objects.filter(        now = timezone.now()        from .nextsms import NextSMSAPI    """    Called daily via cron    Handle trial expirations    """def expire_trials():    return summary        summary["errors"].append({"general": str(e)})        logger.error(f"Error checking expired tenants for suspension: {e}")    except Exception as e:                summary["errors"].append({"tenant": tenant.slug, "error": str(t_err)})                logger.error(f"Failed to suspend tenant {tenant.slug}: {t_err}")            except Exception as t_err:                summary["suspended"].append({"tenant": tenant.slug, "users_deactivated": disconnected_count})                    logger.warning(f"Failed to send suspension SMS for tenant {tenant.slug}: {sms_err}")                except Exception as sms_err:                        logger.info(f"Sent suspension SMS to tenant {tenant.slug} at {phone}")                        sms_client.send_sms(phone, message)                        )                            f"Please renew to restore service.\nIf you believe this is a mistake, contact support."                            f"Kitonga: Your subscription for {tenant.business_name} has expired and your account has been suspended. "                        message = (                    if phone:                    phone = tenant.business_phone                        sms_client = NextSMSAPI()                    if not sms_client:                try:                # Send SMS notification to tenant contact                        logger.error(f"Error processing user {user.phone_number} for suspension: {u_err}")                    except Exception as u_err:                        disconnected_count += 1        suspended_count += 1

        # Notify tenant
        try:
            message = (
                f"Kitonga Subscription Expired\n"
                f"Your subscription has expired. WiFi services are now limited.\n"
                f"Please renew to restore full access.\n"
                f"Contact: support@kitonga.com"
            )

            sms_client.send_sms(tenant.business_phone, message)

        except Exception as e:
            logger.error(f"Failed to send expiry notification to {tenant.slug}: {e}")

        logger.info(f"Suspended expired subscription for {tenant.slug}")

    return suspended_count


def expire_trials():
    """
    Handle trial expirations
    Called daily via cron
    """
    from .nextsms import NextSMSAPI

    now = timezone.now()

    expired_trials = Tenant.objects.filter(
        subscription_status="trial", trial_ends_at__lt=now, is_active=True
    )

    sms_client = NextSMSAPI()
    expired_count = 0

    for tenant in expired_trials:
        tenant.subscription_status = "suspended"
        tenant.save()
        expired_count += 1

        # Notify tenant
        try:
            from .nextsms import NextSMSAPI

            message = (
                f"Kitonga Trial Ended\n"
                f"Your 14-day free trial has ended.\n"
                f"Subscribe now to continue using Kitonga!\n"
                f"Plans start at TZS 30,000/month."
            )

            sms_client = NextSMSAPI()
            sms_client.send_sms(tenant.business_phone, message, sms_type="admin")

        except Exception as e:
            logger.error(
                f"Failed to send trial expiry notification to {tenant.slug}: {e}"
            )

        logger.info(f"Expired trial for {tenant.slug}")

    return expired_count
