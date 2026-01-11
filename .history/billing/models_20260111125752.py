"""
Database models for Kitonga Wi-Fi Billing System
Multi-tenant SaaS Platform for Hotspot Operators
"""

from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User as DjangoUser
from datetime import timedelta
import uuid
import secrets


# =============================================================================
# MULTI-TENANT SAAS MODELS
# =============================================================================


class SubscriptionPlan(models.Model):
    """
    SaaS subscription plans for hotspot operators (tenants)
    """

    PLAN_CHOICES = [
        ("starter", "Starter"),
        ("business", "Business"),
        ("enterprise", "Enterprise"),
    ]

    BILLING_CYCLE_CHOICES = [
        ("monthly", "Monthly"),
        ("yearly", "Yearly"),
    ]

    name = models.CharField(max_length=50, choices=PLAN_CHOICES, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    # Pricing
    monthly_price = models.DecimalField(max_digits=12, decimal_places=2)
    yearly_price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="TZS")

    # Limits
    max_routers = models.IntegerField(default=1)
    max_wifi_users = models.IntegerField(default=100)  # WiFi end-users
    max_vouchers_per_month = models.IntegerField(default=500)
    max_locations = models.IntegerField(default=1)
    max_staff_accounts = models.IntegerField(default=2)

    # Features
    custom_branding = models.BooleanField(default=False)
    custom_domain = models.BooleanField(default=False)
    api_access = models.BooleanField(default=False)
    white_label = models.BooleanField(default=False)
    priority_support = models.BooleanField(default=False)
    analytics_dashboard = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=True)
    sms_broadcast = models.BooleanField(default=False)  # Allow tenant SMS broadcasts

    # Revenue sharing (platform takes percentage of WiFi payments)
    revenue_share_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )

    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["display_order"]

    def __str__(self):
        return f"{self.display_name} - TZS {self.monthly_price:,.0f}/mo"


class Tenant(models.Model):
    """
    Tenant model - represents a hotspot business/operator (your customer)
    Each tenant has their own routers, users, bundles, payments, etc.
    """

    STATUS_CHOICES = [
        ("trial", "Trial"),
        ("active", "Active"),
        ("suspended", "Suspended"),
        ("cancelled", "Cancelled"),
    ]

    # Unique identifier
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(
        max_length=50, unique=True, db_index=True
    )  # Used for subdomain: {slug}.kitonga.com

    # Business Information
    business_name = models.CharField(max_length=200)
    business_email = models.EmailField()
    business_phone = models.CharField(max_length=20)
    business_address = models.TextField(blank=True)
    country = models.CharField(max_length=2, default="TZ")  # ISO country code
    timezone = models.CharField(max_length=50, default="Africa/Dar_es_Salaam")

    # Owner (Django User who created this tenant)
    owner = models.ForeignKey(
        DjangoUser, on_delete=models.PROTECT, related_name="owned_tenants"
    )

    # Subscription
    subscription_plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.PROTECT, null=True, blank=True
    )
    subscription_status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="trial"
    )
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    subscription_started_at = models.DateTimeField(null=True, blank=True)
    subscription_ends_at = models.DateTimeField(null=True, blank=True)
    billing_cycle = models.CharField(max_length=10, default="monthly")

    # Branding
    logo = models.ImageField(upload_to="tenant_logos/", null=True, blank=True)
    primary_color = models.CharField(max_length=7, default="#3B82F6")  # Hex color
    secondary_color = models.CharField(max_length=7, default="#1E40AF")
    custom_domain = models.CharField(max_length=255, blank=True, null=True, unique=True)

    # Payment Configuration (tenant's own payment gateway credentials)
    clickpesa_client_id = models.CharField(max_length=255, blank=True)
    clickpesa_api_key = models.CharField(max_length=255, blank=True)
    nextsms_username = models.CharField(max_length=255, blank=True)
    nextsms_password = models.CharField(max_length=255, blank=True)
    nextsms_sender_id = models.CharField(max_length=20, blank=True)

    # API Access
    api_key = models.CharField(max_length=64, unique=True, blank=True)
    api_secret = models.CharField(max_length=128, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)  # Internal notes for super admin

    # Email Verification
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.business_name} ({self.slug})"

    def save(self, *args, **kwargs):
        # Generate API key if not exists
        if not self.api_key:
            self.api_key = secrets.token_hex(32)
        if not self.api_secret:
            self.api_secret = secrets.token_hex(64)

        # Set trial end date for new tenants
        if not self.pk and not self.trial_ends_at:
            self.trial_ends_at = timezone.now() + timedelta(days=14)

        super().save(*args, **kwargs)

    def is_subscription_valid(self):
        """Check if tenant has valid subscription"""
        now = timezone.now()

        if self.subscription_status == "active":
            if self.subscription_ends_at and self.subscription_ends_at > now:
                return True

        if self.subscription_status == "trial":
            if self.trial_ends_at and self.trial_ends_at > now:
                return True

        return False

    def get_usage_stats(self):
        """Get current usage vs limits"""
        plan = self.subscription_plan
        if not plan:
            return None

        return {
            "routers": {
                "used": self.routers.filter(is_active=True).count(),
                "limit": plan.max_routers,
            },
            "wifi_users": {
                "used": self.wifi_users.count(),
                "limit": plan.max_wifi_users,
            },
            "locations": {
                "used": self.locations.count(),
                "limit": plan.max_locations,
            },
            "staff": {
                "used": self.staff_members.filter(is_active=True).count(),
                "limit": plan.max_staff_accounts,
            },
        }

    def can_add_router(self):
        """Check if tenant can add another router"""
        if not self.subscription_plan:
            return False
        return (
            self.routers.filter(is_active=True).count()
            < self.subscription_plan.max_routers
        )

    def can_add_wifi_user(self):
        """Check if tenant can add another WiFi user"""
        if not self.subscription_plan:
            return False
        return self.wifi_users.count() < self.subscription_plan.max_wifi_users


class EmailOTP(models.Model):
    """
    Email OTP for tenant email verification and password reset
    """

    PURPOSE_CHOICES = [
        ("registration", "Registration Verification"),
        ("password_reset", "Password Reset"),
        ("email_change", "Email Change"),
        ("login", "Two-Factor Login"),
    ]

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="email_otps",
        null=True,
        blank=True,
    )
    email = models.EmailField()
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(
        max_length=20, choices=PURPOSE_CHOICES, default="registration"
    )
    is_used = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0)  # Track failed attempts
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email", "otp_code", "is_used"]),
        ]

    def __str__(self):
        return f"OTP for {self.email} - {self.purpose}"

    def save(self, *args, **kwargs):
        # Set expiry to 15 minutes from now if not set
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=15)
        super().save(*args, **kwargs)

    def is_valid(self):
        """Check if OTP is still valid"""
        if self.is_used:
            return False
        if self.attempts >= 5:  # Max 5 attempts
            return False
        if timezone.now() > self.expires_at:
            return False
        return True

    def verify(self, code):
        """Verify OTP code"""
        if not self.is_valid():
            return False, "OTP has expired or been used"

        self.attempts += 1
        self.save(update_fields=["attempts"])

        if self.otp_code != code:
            if self.attempts >= 5:
                return False, "Too many failed attempts. Request a new OTP."
            return False, f"Invalid OTP. {5 - self.attempts} attempts remaining."

        # Mark as used
        self.is_used = True
        self.used_at = timezone.now()
        self.save(update_fields=["is_used", "used_at"])

        return True, "OTP verified successfully"

    @staticmethod
    def generate_otp():
        """Generate a 6-digit OTP"""
        import random

        return "".join([str(random.randint(0, 9)) for _ in range(6)])

    @classmethod
    def create_for_email(cls, email, purpose="registration", tenant=None):
        """Create a new OTP for an email"""
        # Invalidate any existing unused OTPs for this email and purpose
        cls.objects.filter(email=email, purpose=purpose, is_used=False).update(
            is_used=True
        )

        # Create new OTP
        otp = cls.objects.create(
            tenant=tenant,
            email=email,
            otp_code=cls.generate_otp(),
            purpose=purpose,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        return otp


class TenantStaff(models.Model):
    """
    Staff members for a tenant (additional admin accounts)
    """

    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("admin", "Administrator"),
        ("manager", "Manager"),
        ("support", "Support Staff"),
        ("viewer", "View Only"),
    ]

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="staff_members"
    )
    user = models.ForeignKey(
        DjangoUser, on_delete=models.CASCADE, related_name="tenant_memberships"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="admin")

    # Permissions
    can_manage_routers = models.BooleanField(default=False)
    can_manage_users = models.BooleanField(default=True)
    can_manage_payments = models.BooleanField(default=True)
    can_manage_vouchers = models.BooleanField(default=True)
    can_view_reports = models.BooleanField(default=True)
    can_manage_staff = models.BooleanField(default=False)
    can_manage_settings = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    invited_at = models.DateTimeField(auto_now_add=True)
    joined_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["tenant", "user"]
        ordering = ["role", "user__email"]

    def __str__(self):
        return f"{self.user.email} - {self.tenant.business_name} ({self.role})"


class Location(models.Model):
    """
    Physical locations for a tenant (optional, for multi-location businesses)
    """

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="locations"
    )
    name = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)

    # Contact
    manager_name = models.CharField(max_length=100, blank=True)
    manager_phone = models.CharField(max_length=20, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = ["tenant", "name"]

    def __str__(self):
        return f"{self.tenant.business_name} - {self.name}"


class Router(models.Model):
    """
    MikroTik router configuration per tenant
    Each tenant can have multiple routers
    """

    STATUS_CHOICES = [
        ("online", "Online"),
        ("offline", "Offline"),
        ("configuring", "Configuring"),
        ("error", "Error"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="routers")
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="routers",
    )

    # Router identification
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    # Connection settings
    host = models.CharField(max_length=255)  # IP or hostname
    port = models.IntegerField(default=8728)
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=255)  # Should be encrypted in production
    use_ssl = models.BooleanField(default=False)

    # Router info (populated from router)
    router_model = models.CharField(max_length=100, blank=True)
    router_version = models.CharField(max_length=50, blank=True)
    router_identity = models.CharField(max_length=100, blank=True)

    # Status
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="configuring"
    )
    last_seen = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    # Hotspot settings
    hotspot_interface = models.CharField(max_length=50, default="bridge")
    hotspot_profile = models.CharField(max_length=50, default="default")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["tenant", "name"]
        unique_together = ["tenant", "name"]

    def __str__(self):
        return f"{self.tenant.business_name} - {self.name} ({self.host})"


class TenantSubscriptionPayment(models.Model):
    """
    Track subscription payments from tenants to the platform
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="subscription_payments"
    )
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="TZS")
    billing_cycle = models.CharField(max_length=10)  # monthly/yearly

    # Payment details
    payment_method = models.CharField(
        max_length=50, blank=True
    )  # clickpesa, mpesa, tigopesa
    payment_reference = models.CharField(max_length=255, blank=True)
    transaction_id = models.CharField(max_length=255, unique=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Period this payment covers
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tenant.business_name} - {self.plan.display_name} - {self.status}"


# =============================================================================
# EXISTING MODELS (MODIFIED FOR MULTI-TENANCY)
# =============================================================================


class Bundle(models.Model):
    """
    Bundle packages for different access durations
    Now tenant-specific: each tenant has their own bundles/pricing
    """

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="bundles", null=True
    )
    name = models.CharField(max_length=50)
    duration_hours = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="TZS")
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["display_order", "duration_hours"]

    def __str__(self):
        if self.tenant:
            return f"{self.tenant.slug} - {self.name} - {self.duration_hours}hrs - {self.currency} {self.price}"
        return f"{self.name} - {self.duration_hours}hrs - {self.currency} {self.price}"

    @property
    def duration_days(self):
        """Get duration in days"""
        return self.duration_hours // 24


class User(models.Model):
    """
    WiFi end-user model - identified by phone number
    Phone numbers are automatically normalized to international format
    Now tenant-specific: each tenant has their own WiFi users
    """

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="wifi_users", null=True
    )
    phone_number = models.CharField(max_length=15, db_index=True)
    name = models.CharField(max_length=100, blank=True)  # Optional user name
    email = models.EmailField(blank=True)  # Optional email

    created_at = models.DateTimeField(auto_now_add=True)
    paid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    total_payments = models.IntegerField(default=0)
    total_amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expiry_notification_sent = models.BooleanField(default=False)
    max_devices = models.IntegerField(default=1)

    # Optional: link to router (for multi-router setups)
    primary_router = models.ForeignKey(
        Router,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wifi_users",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        if self.tenant:
            return (
                f"{self.tenant.slug} - {self.phone_number} - Active: {self.is_active}"
            )
        return f"{self.phone_number} - Active: {self.is_active}"

    def clean(self):
        """Validate and normalize phone number"""
        if self.phone_number:
            from .utils import normalize_phone_number, validate_tanzania_phone_number

            try:
                # Normalize the phone number
                normalized = normalize_phone_number(self.phone_number)

                # Validate it's a valid phone number (Tanzania or international)
                is_valid, network, normalized = validate_tanzania_phone_number(
                    self.phone_number
                )
                if not is_valid:
                    raise ValidationError(f"Invalid phone number: {self.phone_number}")

                # Check for existing user with same normalized number within same tenant (excluding self)
                existing_user = (
                    User.objects.filter(tenant=self.tenant, phone_number=normalized)
                    .exclude(pk=self.pk)
                    .first()
                )
                if existing_user:
                    raise ValidationError(
                        f"User with phone number {normalized} already exists for this tenant"
                    )

                self.phone_number = normalized

            except ValueError as e:
                raise ValidationError(f"Invalid phone number format: {e}")

    def save(self, *args, **kwargs):
        """Override save to ensure phone number normalization and max_devices defaults"""
        # Normalize phone number before saving
        self.clean()

        # Always ensure max_devices has a value (for both new and existing users)
        if self.max_devices is None:
            self.max_devices = 1
        super().save(*args, **kwargs)

    def has_active_access(self):
        """
        Check if user has valid paid access

        This method works for both payment and voucher users since both
        access methods set the paid_until field through extend_access()

        Returns:
            bool: True if user has active access, False otherwise
        """
        if not self.is_active:
            return False
        if not self.paid_until:
            return False
        return timezone.now() < self.paid_until

    def extend_access(self, hours=24, source="payment"):
        """
        Extend user access by specified hours

        Args:
            hours (int): Number of hours to extend access
            source (str): Source of extension ('payment', 'voucher', 'manual')
        """
        now = timezone.now()
        if self.paid_until and self.paid_until > now:
            # Extend from current expiry
            self.paid_until = self.paid_until + timedelta(hours=hours)
        else:
            # Start fresh from now
            self.paid_until = now + timedelta(hours=hours)

        self.is_active = True

        # Only increment total_payments for actual payments, not vouchers
        if source == "payment":
            self.total_payments += 1

        self.expiry_notification_sent = False
        self.save()

    def deactivate_access(self):
        """Deactivate user access"""
        self.is_active = False
        self.save()

    def get_active_devices(self):
        """Get list of currently active devices"""
        return self.devices.filter(is_active=True)

    def can_add_device(self):
        """Check if user can add another device"""
        return self.get_active_devices().count() < self.max_devices


# Backwards compatibility alias
WifiUser = User


class Device(models.Model):
    """
    Device model to track user devices
    Now includes tenant reference for easier querying
    """

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="devices", null=True
    )
    user = models.ForeignKey("User", on_delete=models.CASCADE, related_name="devices")
    router = models.ForeignKey(
        Router, on_delete=models.SET_NULL, null=True, blank=True, related_name="devices"
    )

    mac_address = models.CharField(max_length=17, db_index=True)
    ip_address = models.GenericIPAddressField()
    device_name = models.CharField(max_length=100, blank=True)
    device_type = models.CharField(
        max_length=50, blank=True
    )  # phone, laptop, tablet, etc.
    is_active = models.BooleanField(default=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_seen"]
        unique_together = ["tenant", "mac_address"]  # MAC unique per tenant

    def __str__(self):
        return f"{self.user.phone_number} - {self.mac_address} - {'Active' if self.is_active else 'Inactive'}"

    def save(self, *args, **kwargs):
        # Auto-set tenant from user if not set
        if not self.tenant_id and self.user_id:
            self.tenant = self.user.tenant
        super().save(*args, **kwargs)


class Payment(models.Model):
    """
    Payment transaction model for WiFi access purchases
    Now includes tenant reference and tracks platform revenue share
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded"),
    ]

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="wifi_payments", null=True
    )
    user = models.ForeignKey("User", on_delete=models.CASCADE, related_name="payments")
    bundle = models.ForeignKey(
        Bundle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    router = models.ForeignKey(
        Router,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=15)
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    transaction_id = models.CharField(max_length=100, unique=True)
    order_reference = models.CharField(
        max_length=100, unique=True, null=True, blank=True
    )
    payment_channel = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.phone_number} - TSh {self.amount} - {self.status}"

    def mark_completed(self, payment_reference=None, channel=None):
        """Mark payment as completed and extend user access"""
        self.status = "completed"
        self.payment_reference = payment_reference
        self.payment_channel = channel
        self.completed_at = timezone.now()
        self.save()

        # Extend user access based on bundle duration, specify source as payment
        if self.bundle:
            self.user.extend_access(hours=self.bundle.duration_hours, source="payment")
        else:
            # Default to 24 hours if no bundle specified
            self.user.extend_access(hours=24, source="payment")

    def mark_failed(self):
        """Mark payment as failed"""
        self.status = "failed"
        self.save()

    def save(self, *args, **kwargs):
        # Auto-set tenant from user if not set
        if not self.tenant_id and self.user_id:
            self.tenant = self.user.tenant
        super().save(*args, **kwargs)


class AccessLog(models.Model):
    """
    Log of user access attempts and sessions
    Now includes tenant reference for easier querying
    """

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="access_logs", null=True
    )
    user = models.ForeignKey(
        "User", on_delete=models.CASCADE, related_name="access_logs"
    )
    device = models.ForeignKey(
        Device,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="access_logs",
    )
    router = models.ForeignKey(
        Router,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="access_logs",
    )

    ip_address = models.GenericIPAddressField()
    mac_address = models.CharField(max_length=17, blank=True)
    access_granted = models.BooleanField(default=False)
    denial_reason = models.CharField(max_length=100, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.user.phone_number} - {self.ip_address} - {'Granted' if self.access_granted else 'Denied'}"

    def save(self, *args, **kwargs):
        # Auto-set tenant from user if not set
        if not self.tenant_id and self.user_id:
            self.tenant = self.user.tenant
        super().save(*args, **kwargs)


class Voucher(models.Model):
    """
    Voucher code model for offline access
    Allows users to redeem codes for Wi-Fi access without online payment
    Now tenant-specific: each tenant has their own vouchers
    """

    DURATION_CHOICES = [
        (1, "1 Hour"),
        (3, "3 Hours"),
        (6, "6 Hours"),
        (12, "12 Hours"),
        (24, "24 Hours (1 Day)"),
        (72, "72 Hours (3 Days)"),
        (168, "168 Hours (7 Days)"),
        (720, "720 Hours (30 Days)"),
    ]

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="vouchers", null=True
    )
    code = models.CharField(max_length=16, db_index=True)
    duration_hours = models.IntegerField(choices=DURATION_CHOICES, default=24)

    # Optional: link to specific bundle for pricing
    bundle = models.ForeignKey(
        Bundle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vouchers",
    )

    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=100, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vouchers_used",
    )
    batch_id = models.CharField(max_length=50, blank=True, db_index=True)
    notes = models.TextField(blank=True)

    # Track which router this voucher was used on
    used_on_router = models.ForeignKey(
        Router,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="redeemed_vouchers",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        if self.tenant:
            return f"{self.tenant.slug} - {self.code} - {self.duration_hours}hrs - {'Used' if self.is_used else 'Available'}"
        return f"{self.code} - {self.duration_hours}hrs - {'Used' if self.is_used else 'Available'}"

    def redeem(self, user):
        """Redeem voucher for a user and extend their access"""
        if self.is_used:
            return False, "Voucher has already been used"

        # Ensure user belongs to same tenant as voucher (if tenant is set)
        if self.tenant_id and user.tenant_id != self.tenant_id:
            return False, "Voucher not valid for this network"

        self.is_used = True
        self.used_at = timezone.now()
        self.used_by = user
        self.save()

        # Extend user access, specify source as voucher
        user.extend_access(hours=self.duration_hours, source="voucher")

        return (
            True,
            f"Voucher redeemed successfully. Access granted for {self.duration_hours} hours.",
        )

    @staticmethod
    def generate_code(tenant=None):
        """Generate a unique voucher code for a tenant"""
        import random
        import string

        while True:
            # Generate format: XXXX-XXXX-XXXX
            code = "-".join(
                [
                    "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
                    for _ in range(3)
                ]
            )

            # Check if code already exists for this tenant
            if tenant:
                if not Voucher.objects.filter(tenant=tenant, code=code).exists():
                    return code
            else:
                # Global check if no tenant specified
                if not Voucher.objects.filter(code=code).exists():
                    return code


class SMSLog(models.Model):
    """
    Log of SMS notifications sent
    Now tenant-specific
    """

    SMS_TYPE_CHOICES = [
        ("payment", "Payment Confirmation"),
        ("expiry_warning", "Expiry Warning"),
        ("expired", "Access Expired"),
        ("voucher", "Voucher Redemption"),
        ("welcome", "Welcome Message"),
        ("admin", "Admin Notification"),
        ("other", "Other"),
    ]

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="sms_logs", null=True
    )
    phone_number = models.CharField(max_length=15, db_index=True)
    message = models.TextField()
    sms_type = models.CharField(
        max_length=20, choices=SMS_TYPE_CHOICES, default="other"
    )
    success = models.BooleanField(default=False)
    response_data = models.JSONField(null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        if self.tenant:
            return f"{self.tenant.slug} - {self.phone_number} - {self.sms_type} - {'Sent' if self.success else 'Failed'}"
        return f"{self.phone_number} - {self.sms_type} - {'Sent' if self.success else 'Failed'}"


class PaymentWebhook(models.Model):
    """
    Log of payment webhooks received from ClickPesa
    Tracks all webhook events for debugging and audit purposes
    Now tenant-specific
    """

    WEBHOOK_EVENT_CHOICES = [
        ("PAYMENT RECEIVED", "Payment Received"),
        ("PAYMENT FAILED", "Payment Failed"),
        ("PAYMENT PENDING", "Payment Pending"),
        ("PAYMENT CANCELLED", "Payment Cancelled"),
        ("OTHER", "Other"),
    ]

    PROCESSING_STATUS_CHOICES = [
        ("received", "Received"),
        ("processed", "Processed Successfully"),
        ("failed", "Processing Failed"),
        ("ignored", "Ignored"),
    ]

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="payment_webhooks",
        null=True,
        blank=True,
    )

    # Webhook metadata
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_status = models.CharField(
        max_length=20, choices=PROCESSING_STATUS_CHOICES, default="received"
    )
    processing_error = models.TextField(blank=True)

    # ClickPesa webhook data
    event_type = models.CharField(
        max_length=50, choices=WEBHOOK_EVENT_CHOICES, default="OTHER"
    )
    order_reference = models.CharField(max_length=100, db_index=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    payment_status = models.CharField(max_length=50, blank=True, null=True)
    channel = models.CharField(max_length=50, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Raw webhook payload for debugging
    raw_payload = models.JSONField()

    # Related payment record (if found)
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="webhook_logs",
    )

    # Request metadata
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["order_reference", "-received_at"]),
            models.Index(fields=["event_type", "-received_at"]),
            models.Index(fields=["processing_status", "-received_at"]),
        ]

    def __str__(self):
        return f"{self.order_reference} - {self.event_type} - {self.processing_status}"

    def mark_processed(self, payment=None):
        """Mark webhook as successfully processed"""
        self.processing_status = "processed"
        self.processed_at = timezone.now()
        if payment:
            self.payment = payment
        self.save()

    def mark_failed(self, error_message):
        """Mark webhook processing as failed"""
        self.processing_status = "failed"
        self.processed_at = timezone.now()
        self.processing_error = error_message
        self.save()

    def mark_ignored(self, reason):
        """Mark webhook as ignored (e.g., duplicate, invalid)"""
        self.processing_status = "ignored"
        self.processed_at = timezone.now()
        self.processing_error = reason
        self.save()

    @property
    def is_duplicate(self):
        """Check if this webhook is a duplicate"""
        return PaymentWebhook.objects.filter(
            order_reference=self.order_reference,
            event_type=self.event_type,
            processing_status="processed",
            received_at__lt=self.received_at,
        ).exists()


class TenantPayout(models.Model):
    """
    Track tenant payout requests and status
    Tenants can request payouts from their available balance
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    PAYOUT_METHODS = [
        ("bank_transfer", "Bank Transfer"),
        ("mobile_money", "Mobile Money"),
        ("mpesa", "M-Pesa"),
        ("tigopesa", "TigoPesa"),
        ("airtel_money", "Airtel Money"),
        ("halopesa", "HaloPesa"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="payouts")

    # Payout details
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payout_method = models.CharField(
        max_length=50, choices=PAYOUT_METHODS, default="mobile_money"
    )

    # Destination details
    account_number = models.CharField(max_length=100)  # Phone number or bank account
    account_name = models.CharField(max_length=200, blank=True)  # Account holder name
    bank_name = models.CharField(max_length=100, blank=True)  # For bank transfers
    bank_branch = models.CharField(max_length=100, blank=True)

    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    reference = models.CharField(max_length=100, unique=True)  # Unique payout reference
    transaction_id = models.CharField(
        max_length=100, blank=True
    )  # External transaction ID

    # Timestamps
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Notes and errors
    notes = models.TextField(blank=True)
    error_message = models.TextField(blank=True)

    # Requested by (staff member if applicable)
    requested_by = models.CharField(max_length=200, blank=True)
    processed_by = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["reference"]),
            models.Index(fields=["-requested_at"]),
        ]

    def __str__(self):
        return f"{self.tenant.business_name} - TSh {self.amount} - {self.status}"

    def save(self, *args, **kwargs):
        if not self.reference:
            import uuid

            # ClickPesa requires alphanumeric only - no hyphens or special chars
            self.reference = f"PO{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)

    def mark_processing(self, processed_by=""):
        """Mark payout as being processed"""
        self.status = "processing"
        self.processed_at = timezone.now()
        self.processed_by = processed_by
        self.save()

    def mark_completed(self, transaction_id=""):
        """Mark payout as completed"""
        self.status = "completed"
        self.completed_at = timezone.now()
        self.transaction_id = transaction_id
        self.save()

    def mark_failed(self, error_message):
        """Mark payout as failed"""
        self.status = "failed"
        self.error_message = error_message
        self.save()

    def cancel(self, reason=""):
        """Cancel the payout request"""
        self.status = "cancelled"
        self.error_message = reason
        self.save()


class ContactSubmission(models.Model):
    """
    Contact form submissions from potential customers or users
    """

    STATUS_CHOICES = [
        ("new", "New"),
        ("read", "Read"),
        ("replied", "Replied"),
        ("closed", "Closed"),
    ]

    SUBJECT_CHOICES = [
        ("general", "General Inquiry"),
        ("sales", "Sales Inquiry"),
        ("support", "Technical Support"),
        ("partnership", "Partnership Opportunity"),
        ("demo", "Request Demo"),
        ("other", "Other"),
    ]

    # Contact info
    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)

    # Message details
    subject = models.CharField(
        max_length=50, choices=SUBJECT_CHOICES, default="general"
    )
    message = models.TextField()

    # Tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Response tracking
    replied_at = models.DateTimeField(null=True, blank=True)
    replied_by = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)  # Internal notes

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.get_subject_display()} ({self.status})"

    def mark_read(self):
        """Mark submission as read"""
        if self.status == "new":
            self.status = "read"
            self.save()

    def mark_replied(self, replied_by=""):
        """Mark submission as replied"""
        self.status = "replied"
        self.replied_at = timezone.now()
        self.replied_by = replied_by
        self.save()

    def close(self):
        """Close the submission"""
        self.status = "closed"
        self.save()


# =============================================================================
# SMS BROADCAST MODEL
# =============================================================================


class SMSBroadcast(models.Model):
    """
    SMS Broadcast campaigns for admin to send bulk SMS to users/tenants
    """

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("sending", "Sending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    TARGET_TYPE_CHOICES = [
        ("all_users", "All WiFi Users"),
        ("all_tenants", "All Tenants"),
        ("tenant_users", "Specific Tenant's Users"),
        ("active_users", "Active Users Only"),
        ("expired_users", "Expired Users"),
        ("custom", "Custom Phone Numbers"),
    ]

    # Campaign Info
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(
        max_length=200, help_text="Internal title for this campaign"
    )
    message = models.TextField(
        max_length=320, help_text="SMS message (max 320 chars for 2 SMS)"
    )

    # Targeting
    target_type = models.CharField(
        max_length=20, choices=TARGET_TYPE_CHOICES, default="all_users"
    )
    target_tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_broadcasts",
        help_text="Required when target_type is 'tenant_users'",
    )
    custom_recipients = models.JSONField(
        null=True, blank=True, help_text="List of phone numbers for custom targeting"
    )

    # Status & Progress
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    total_recipients = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)

    # Creator (platform admin)
    created_by = models.ForeignKey(
        DjangoUser, on_delete=models.SET_NULL, null=True, related_name="sms_broadcasts"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    scheduled_at = models.DateTimeField(
        null=True, blank=True, help_text="Schedule for later sending"
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Error tracking
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "SMS Broadcast"
        verbose_name_plural = "SMS Broadcasts"

    def __str__(self):
        return f"{self.title} - {self.get_status_display()} ({self.sent_count}/{self.total_recipients})"

    def get_recipients(self):
        """
        Get list of phone numbers based on target_type
        Returns list of dicts with phone_number and optional name
        """
        recipients = []

        if self.target_type == "all_users":
            # All WiFi users across all tenants
            users = User.objects.filter(phone_number__isnull=False).values(
                "phone_number", "name"
            )
            recipients = list(users)

        elif self.target_type == "all_tenants":
            # All tenant business phones
            tenants = Tenant.objects.filter(is_active=True).values(
                "business_phone", "business_name"
            )
            recipients = [
                {"phone_number": t["business_phone"], "name": t["business_name"]}
                for t in tenants
            ]

        elif self.target_type == "tenant_users":
            # Specific tenant's WiFi users
            if self.target_tenant:
                users = User.objects.filter(
                    tenant=self.target_tenant, phone_number__isnull=False
                ).values("phone_number", "name")
                recipients = list(users)

        elif self.target_type == "active_users":
            # Only users with active access
            now = timezone.now()
            users = User.objects.filter(
                phone_number__isnull=False, is_active=True, paid_until__gte=now
            ).values("phone_number", "name")
            recipients = list(users)

        elif self.target_type == "expired_users":
            # Users whose access has expired
            now = timezone.now()
            users = User.objects.filter(
                phone_number__isnull=False, paid_until__lt=now
            ).values("phone_number", "name")
            recipients = list(users)

        elif self.target_type == "custom":
            # Custom phone numbers from JSON field
            if self.custom_recipients:
                if isinstance(self.custom_recipients, list):
                    recipients = [
                        {"phone_number": p, "name": ""} for p in self.custom_recipients
                    ]

        return recipients

    def send_broadcast(self):
        """
        Execute the SMS broadcast
        """
        from .nextsms import NextSMSAPI

        if self.status not in ["draft", "pending"]:
            return False, f"Cannot send broadcast in {self.status} status"

        self.status = "sending"
        self.started_at = timezone.now()
        self.save()

        sms_api = NextSMSAPI()
        recipients = self.get_recipients()
        self.total_recipients = len(recipients)
        self.save()

        if not recipients:
            self.status = "failed"
            self.error_message = "No recipients found for this target type"
            self.completed_at = timezone.now()
            self.save()
            return False, "No recipients found"

        for recipient in recipients:
            phone = recipient.get("phone_number", "")
            if not phone:
                continue

            try:
                result = sms_api.send_sms(
                    phone, self.message, reference=f"BROADCAST-{self.id}"
                )

                # Log the SMS
                SMSLog.objects.create(
                    phone_number=phone,
                    message=self.message,
                    sms_type="admin",
                    success=result.get("success", False),
                    response_data=result.get("data"),
                )

                if result.get("success"):
                    self.sent_count += 1
                else:
                    self.failed_count += 1

            except Exception as e:
                self.failed_count += 1
                SMSLog.objects.create(
                    phone_number=phone,
                    message=self.message,
                    sms_type="admin",
                    success=False,
                    response_data={"error": str(e)},
                )

        self.status = "completed"
        self.completed_at = timezone.now()
        self.save()

        return (
            True,
            f"Broadcast completed: {self.sent_count} sent, {self.failed_count} failed",
        )


# =============================================================================
# TENANT SMS BROADCAST MODEL
# =============================================================================


class TenantSMSBroadcast(models.Model):
    """
    SMS Broadcast campaigns for tenants to send bulk SMS to their WiFi users
    Available for Business and Enterprise plans only
    """

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("sending", "Sending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    TARGET_TYPE_CHOICES = [
        ("all_users", "All My WiFi Users"),
        ("active_users", "Active Users Only"),
        ("expired_users", "Expired Users"),
        ("expiring_soon", "Expiring Within 24 Hours"),
        ("custom", "Custom Phone Numbers"),
    ]

    # Campaign Info
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="tenant_sms_broadcasts",
    )
    title = models.CharField(
        max_length=200, help_text="Internal title for this campaign"
    )
    message = models.TextField(
        max_length=320, help_text="SMS message (max 320 chars for 2 SMS)"
    )

    # Targeting
    target_type = models.CharField(
        max_length=20, choices=TARGET_TYPE_CHOICES, default="all_users"
    )
    custom_recipients = models.JSONField(
        null=True, blank=True, help_text="List of phone numbers for custom targeting"
    )

    # Status & Progress
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    total_recipients = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    scheduled_at = models.DateTimeField(
        null=True, blank=True, help_text="Schedule for later sending"
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Error tracking
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Tenant SMS Broadcast"
        verbose_name_plural = "Tenant SMS Broadcasts"

    def __str__(self):
        return f"{self.tenant.slug} - {self.title} - {self.get_status_display()}"

    def get_recipients(self):
        """
        Get list of phone numbers based on target_type (only tenant's users)
        Returns list of dicts with phone_number and optional name
        """
        recipients = []

        if self.target_type == "all_users":
            # All WiFi users for this tenant
            users = User.objects.filter(
                tenant=self.tenant, phone_number__isnull=False
            ).exclude(phone_number="").values("phone_number", "name")
            recipients = list(users)

        elif self.target_type == "active_users":
            # Only users with active access
            now = timezone.now()
            users = User.objects.filter(
                tenant=self.tenant,
                phone_number__isnull=False,
                is_active=True,
                paid_until__gte=now,
            ).exclude(phone_number="").values("phone_number", "name")
            recipients = list(users)

        elif self.target_type == "expired_users":
            # Users whose access has expired
            now = timezone.now()
            users = User.objects.filter(
                tenant=self.tenant,
                phone_number__isnull=False,
                paid_until__lt=now,
            ).exclude(phone_number="").values("phone_number", "name")
            recipients = list(users)

        elif self.target_type == "expiring_soon":
            # Users expiring within 24 hours
            now = timezone.now()
            expiry_threshold = now + timedelta(hours=24)
            users = User.objects.filter(
                tenant=self.tenant,
                phone_number__isnull=False,
                is_active=True,
                paid_until__gte=now,
                paid_until__lte=expiry_threshold,
            ).exclude(phone_number="").values("phone_number", "name")
            recipients = list(users)

        elif self.target_type == "custom":
            # Custom phone numbers from JSON field
            if self.custom_recipients:
                if isinstance(self.custom_recipients, list):
                    recipients = [
                        {"phone_number": p, "name": ""} for p in self.custom_recipients
                    ]

        return recipients

    def send_broadcast(self):
        """
        Execute the SMS broadcast using tenant's NextSMS credentials
        """
        from .nextsms import TenantNextSMSAPI

        if self.status not in ["draft", "pending"]:
            return False, f"Cannot send broadcast in {self.status} status"

        # Check if tenant has SMS credentials configured
        if not self.tenant.nextsms_username or not self.tenant.nextsms_password:
            self.status = "failed"
            self.error_message = "NextSMS credentials not configured"
            self.save()
            return False, "NextSMS credentials not configured. Please configure SMS settings first."

        self.status = "sending"
        self.started_at = timezone.now()
        self.save()

        # Use tenant-specific SMS API
        sms_api = TenantNextSMSAPI(self.tenant)
        recipients = self.get_recipients()
        self.total_recipients = len(recipients)
        self.save()

        if not recipients:
            self.status = "failed"
            self.error_message = "No recipients found for this target type"
            self.completed_at = timezone.now()
            self.save()
            return False, "No recipients found"

        for recipient in recipients:
            phone = recipient.get("phone_number", "")
            if not phone:
                continue

            try:
                result = sms_api.send_sms(
                    phone, self.message, reference=f"TENANT-BROADCAST-{self.id}"
                )

                # Log the SMS
                SMSLog.objects.create(
                    tenant=self.tenant,
                    phone_number=phone,
                    message=self.message,
                    sms_type="broadcast",
                    success=result.get("success", False),
                    response_data=result.get("data"),
                )

                if result.get("success"):
                    self.sent_count += 1
                else:
                    self.failed_count += 1

            except Exception as e:
                self.failed_count += 1
                SMSLog.objects.create(
                    tenant=self.tenant,
                    phone_number=phone,
                    message=self.message,
                    sms_type="broadcast",
                    success=False,
                    response_data={"error": str(e)},
                )

        self.status = "completed"
        self.completed_at = timezone.now()
        self.save()

        return (
            True,
            f"Broadcast completed: {self.sent_count} sent, {self.failed_count} failed",
        )
