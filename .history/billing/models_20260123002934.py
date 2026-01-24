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

    # Premium Features (Business/Enterprise)
    advanced_analytics = models.BooleanField(default=False)  # Charts, trends, exports
    auto_sms_campaigns = models.BooleanField(default=False)  # Scheduled/triggered SMS
    webhook_notifications = models.BooleanField(default=False)  # Real-time callbacks
    data_export = models.BooleanField(default=False)  # Export to CSV/Excel/PDF

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
    nextsms_base_url = models.CharField(
        max_length=255, blank=True, default="https://messaging-service.co.tz"
    )

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


class RouterMonitoringSnapshot(models.Model):
    """
    Periodic snapshots of router health metrics for monitoring
    """

    router = models.ForeignKey(
        Router, on_delete=models.CASCADE, related_name="monitoring_snapshots"
    )

    # System resources
    cpu_load = models.IntegerField(default=0)  # Percentage
    memory_used = models.BigIntegerField(default=0)  # Bytes
    memory_total = models.BigIntegerField(default=0)  # Bytes
    disk_used = models.BigIntegerField(default=0)  # Bytes
    disk_total = models.BigIntegerField(default=0)  # Bytes
    uptime = models.BigIntegerField(default=0)  # Seconds

    # Network metrics
    active_hotspot_users = models.IntegerField(default=0)
    total_interfaces = models.IntegerField(default=0)
    interfaces_up = models.IntegerField(default=0)

    # Bandwidth (aggregated from interfaces)
    rx_bytes = models.BigIntegerField(default=0)  # Total received
    tx_bytes = models.BigIntegerField(default=0)  # Total transmitted

    # Status
    is_reachable = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["router", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.router.name} - {self.created_at}"

    @property
    def memory_percent(self):
        if self.memory_total > 0:
            return round((self.memory_used / self.memory_total) * 100, 1)
        return 0

    @property
    def disk_percent(self):
        if self.disk_total > 0:
            return round((self.disk_used / self.disk_total) * 100, 1)
        return 0


class RouterBandwidthLog(models.Model):
    """
    Hourly bandwidth usage logs per router
    """

    router = models.ForeignKey(
        Router, on_delete=models.CASCADE, related_name="bandwidth_logs"
    )

    # Time period
    hour_start = models.DateTimeField()  # Start of the hour

    # Bandwidth data
    rx_bytes = models.BigIntegerField(default=0)
    tx_bytes = models.BigIntegerField(default=0)
    peak_users = models.IntegerField(default=0)
    avg_users = models.FloatField(default=0)

    # Calculated rates (bytes per second average)
    avg_rx_rate = models.BigIntegerField(default=0)
    avg_tx_rate = models.BigIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-hour_start"]
        unique_together = ["router", "hour_start"]
        indexes = [
            models.Index(fields=["router", "-hour_start"]),
        ]

    def __str__(self):
        return f"{self.router.name} - {self.hour_start}"

    @property
    def total_bytes(self):
        return self.rx_bytes + self.tx_bytes

    @property
    def rx_mb(self):
        return round(self.rx_bytes / (1024 * 1024), 2)

    @property
    def tx_mb(self):
        return round(self.tx_bytes / (1024 * 1024), 2)


class RouterHotspotCustomization(models.Model):
    """
    Per-router hotspot page customization settings
    """

    router = models.OneToOneField(
        Router, on_delete=models.CASCADE, related_name="hotspot_customization"
    )

    # Page title and text
    page_title = models.CharField(max_length=200, blank=True)
    welcome_message = models.TextField(blank=True)
    footer_text = models.TextField(blank=True)

    # Branding
    logo_url = models.URLField(blank=True)
    background_image_url = models.URLField(blank=True)
    favicon_url = models.URLField(blank=True)

    # Colors (hex values)
    primary_color = models.CharField(max_length=7, default="#3B82F6")
    secondary_color = models.CharField(max_length=7, default="#1E40AF")
    background_color = models.CharField(max_length=7, default="#F3F4F6")
    text_color = models.CharField(max_length=7, default="#1F2937")
    button_color = models.CharField(max_length=7, default="#3B82F6")
    button_text_color = models.CharField(max_length=7, default="#FFFFFF")

    # Layout options
    show_logo = models.BooleanField(default=True)
    show_bundles = models.BooleanField(default=True)
    show_social_login = models.BooleanField(default=False)
    show_terms_link = models.BooleanField(default=True)
    show_support_contact = models.BooleanField(default=True)

    # Custom content
    terms_url = models.URLField(blank=True)
    support_email = models.EmailField(blank=True)
    support_phone = models.CharField(max_length=20, blank=True)

    # Custom CSS and JS
    custom_css = models.TextField(blank=True)
    custom_js = models.TextField(blank=True)

    # Custom HTML sections
    header_html = models.TextField(blank=True)
    footer_html = models.TextField(blank=True)

    # Template override (if using custom HTML template)
    use_custom_template = models.BooleanField(default=False)
    custom_login_html = models.TextField(blank=True)
    custom_logout_html = models.TextField(blank=True)
    custom_status_html = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Router Hotspot Customization"
        verbose_name_plural = "Router Hotspot Customizations"

    def __str__(self):
        return f"Hotspot customization for {self.router.name}"


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
        """Mark payment as completed and extend user access (idempotent)."""
        # If already completed, do nothing (prevents duplicate extensions)
        if self.status == "completed" and self.completed_at:
            logger.info(
                f"Payment {getattr(self, 'order_reference', self.id)} already marked completed, skipping duplicate processing"
            )
            return

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
        ("broadcast", "Broadcast Message"),
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
            users = (
                User.objects.filter(tenant=self.tenant, phone_number__isnull=False)
                .exclude(phone_number="")
                .values("phone_number", "name")
            )
            recipients = list(users)

        elif self.target_type == "active_users":
            # Only users with active access
            now = timezone.now()
            users = (
                User.objects.filter(
                    tenant=self.tenant,
                    phone_number__isnull=False,
                    is_active=True,
                    paid_until__gte=now,
                )
                .exclude(phone_number="")
                .values("phone_number", "name")
            )
            recipients = list(users)

        elif self.target_type == "expired_users":
            # Users whose access has expired
            now = timezone.now()
            users = (
                User.objects.filter(
                    tenant=self.tenant,
                    phone_number__isnull=False,
                    paid_until__lt=now,
                )
                .exclude(phone_number="")
                .values("phone_number", "name")
            )
            recipients = list(users)

        elif self.target_type == "expiring_soon":
            # Users expiring within 24 hours
            now = timezone.now()
            expiry_threshold = now + timedelta(hours=24)
            users = (
                User.objects.filter(
                    tenant=self.tenant,
                    phone_number__isnull=False,
                    is_active=True,
                    paid_until__gte=now,
                    paid_until__lte=expiry_threshold,
                )
                .exclude(phone_number="")
                .values("phone_number", "name")
            )
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
            return (
                False,
                "NextSMS credentials not configured. Please configure SMS settings first.",
            )

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


# =============================================================================
# AUTO SMS CAMPAIGNS (Business/Enterprise Feature)
# =============================================================================


class AutoSMSCampaign(models.Model):
    """
    Automated SMS campaigns that trigger based on events or schedules.
    Available for Business and Enterprise plans only.
    """

    TRIGGER_TYPE_CHOICES = [
        # Event-based triggers
        ("new_user", "New User Registration"),
        ("payment_success", "Successful Payment"),
        ("payment_failed", "Failed Payment"),
        ("access_expiring", "Access Expiring Soon"),
        ("access_expired", "Access Expired"),
        ("voucher_redeemed", "Voucher Redeemed"),
        # Time-based triggers
        ("scheduled", "Scheduled (One-time)"),
        ("recurring_daily", "Daily Recurring"),
        ("recurring_weekly", "Weekly Recurring"),
        ("recurring_monthly", "Monthly Recurring"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("paused", "Paused"),
        ("completed", "Completed"),
        ("draft", "Draft"),
    ]

    # Campaign Info
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="auto_sms_campaigns",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Trigger Configuration
    trigger_type = models.CharField(max_length=30, choices=TRIGGER_TYPE_CHOICES)

    # For expiring triggers: hours before expiry
    hours_before_expiry = models.IntegerField(
        default=24,
        help_text="For 'access_expiring' trigger: hours before expiry to send SMS",
    )

    # For scheduled/recurring triggers
    scheduled_time = models.TimeField(
        null=True, blank=True, help_text="Time of day to send (for scheduled/recurring)"
    )
    scheduled_date = models.DateField(
        null=True, blank=True, help_text="Date to send (for one-time scheduled)"
    )
    day_of_week = models.IntegerField(
        null=True, blank=True, help_text="0=Monday, 6=Sunday (for weekly recurring)"
    )
    day_of_month = models.IntegerField(
        null=True, blank=True, help_text="Day of month 1-28 (for monthly recurring)"
    )

    # Message Template
    message_template = models.TextField(
        max_length=320,
        help_text="SMS template. Variables: {name}, {phone}, {expiry_date}, {amount}, {bundle}",
    )

    # Target Audience (for scheduled campaigns)
    target_all_users = models.BooleanField(default=True)
    target_active_only = models.BooleanField(default=False)
    target_expired_only = models.BooleanField(default=False)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    is_active = models.BooleanField(default=True)

    # Statistics
    total_sent = models.IntegerField(default=0)
    total_failed = models.IntegerField(default=0)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Auto SMS Campaign"
        verbose_name_plural = "Auto SMS Campaigns"

    def __str__(self):
        return f"{self.tenant.slug} - {self.name} ({self.get_trigger_type_display()})"

    def render_message(self, context: dict) -> str:
        """Render the message template with context variables"""
        message = self.message_template
        for key, value in context.items():
            message = message.replace(f"{{{key}}}", str(value) if value else "")
        return message

    def get_recipients_for_scheduled(self):
        """Get recipients for scheduled/recurring campaigns"""
        now = timezone.now()
        users = User.objects.filter(
            tenant=self.tenant, phone_number__isnull=False
        ).exclude(phone_number="")

        if self.target_active_only:
            users = users.filter(is_active=True, paid_until__gte=now)
        elif self.target_expired_only:
            users = users.filter(paid_until__lt=now)

        return users

    def calculate_next_run(self):
        """Calculate next run time for recurring campaigns"""
        now = timezone.now()

        if self.trigger_type == "scheduled":
            # One-time: combine date and time
            if self.scheduled_date and self.scheduled_time:
                from datetime import datetime

                next_run = timezone.make_aware(
                    datetime.combine(self.scheduled_date, self.scheduled_time)
                )
                if next_run > now:
                    self.next_run_at = next_run
                else:
                    self.next_run_at = None
                    self.status = "completed"

        elif self.trigger_type == "recurring_daily" and self.scheduled_time:
            # Daily: next occurrence of scheduled_time
            next_run = now.replace(
                hour=self.scheduled_time.hour,
                minute=self.scheduled_time.minute,
                second=0,
                microsecond=0,
            )
            if next_run <= now:
                next_run += timedelta(days=1)
            self.next_run_at = next_run

        elif (
            self.trigger_type == "recurring_weekly"
            and self.scheduled_time
            and self.day_of_week is not None
        ):
            # Weekly: next occurrence of day_of_week at scheduled_time
            days_ahead = self.day_of_week - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_run = now.replace(
                hour=self.scheduled_time.hour,
                minute=self.scheduled_time.minute,
                second=0,
                microsecond=0,
            ) + timedelta(days=days_ahead)
            self.next_run_at = next_run

        elif (
            self.trigger_type == "recurring_monthly"
            and self.scheduled_time
            and self.day_of_month
        ):
            # Monthly: next occurrence of day_of_month at scheduled_time
            from calendar import monthrange

            next_run = now.replace(
                day=min(self.day_of_month, monthrange(now.year, now.month)[1]),
                hour=self.scheduled_time.hour,
                minute=self.scheduled_time.minute,
                second=0,
                microsecond=0,
            )
            if next_run <= now:
                # Move to next month
                if now.month == 12:
                    next_run = next_run.replace(year=now.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=now.month + 1)
            self.next_run_at = next_run

        self.save(update_fields=["next_run_at", "status"])


class AutoSMSLog(models.Model):
    """Log of auto SMS campaign executions"""

    campaign = models.ForeignKey(
        AutoSMSCampaign, on_delete=models.CASCADE, related_name="execution_logs"
    )
    trigger_event = models.CharField(max_length=50)
    recipient_phone = models.CharField(max_length=15)
    message_sent = models.TextField()
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    triggered_at = models.DateTimeField(auto_now_add=True)

    # Related objects (optional)
    related_user = models.ForeignKey(
        "User", on_delete=models.SET_NULL, null=True, blank=True
    )
    related_payment = models.ForeignKey(
        Payment, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["-triggered_at"]

    def __str__(self):
        return f"{self.campaign.name} -> {self.recipient_phone} ({'OK' if self.success else 'FAIL'})"


# =============================================================================
# WEBHOOK NOTIFICATIONS (Business/Enterprise Feature)
# =============================================================================


class TenantWebhook(models.Model):
    """
    Webhook configuration for tenants to receive real-time event notifications.
    Available for Business and Enterprise plans only.
    """

    EVENT_CHOICES = [
        ("payment.success", "Payment Successful"),
        ("payment.failed", "Payment Failed"),
        ("user.created", "New User Created"),
        ("user.expired", "User Access Expired"),
        ("user.activated", "User Activated"),
        ("voucher.redeemed", "Voucher Redeemed"),
        ("voucher.created", "Vouchers Generated"),
        ("router.online", "Router Came Online"),
        ("router.offline", "Router Went Offline"),
        ("subscription.expiring", "Subscription Expiring"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("paused", "Paused"),
        ("failing", "Failing (Retrying)"),
        ("disabled", "Disabled (Too Many Failures)"),
    ]

    # Webhook Configuration
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="webhooks"
    )
    name = models.CharField(max_length=100)
    url = models.URLField(
        max_length=500, help_text="HTTPS URL to receive webhook events"
    )

    # Authentication
    secret_key = models.CharField(
        max_length=64,
        blank=True,
        help_text="Secret key for HMAC signature verification",
    )
    auth_header = models.CharField(
        max_length=255, blank=True, help_text="Optional Authorization header value"
    )

    # Event Subscription
    events = models.JSONField(
        default=list, help_text="List of event types to subscribe to"
    )

    # Status & Health
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    is_active = models.BooleanField(default=True)
    consecutive_failures = models.IntegerField(default=0)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_failure_at = models.DateTimeField(null=True, blank=True)
    last_failure_reason = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Tenant Webhook"
        verbose_name_plural = "Tenant Webhooks"

    def __str__(self):
        return f"{self.tenant.slug} - {self.name} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.secret_key:
            self.secret_key = secrets.token_hex(32)
        super().save(*args, **kwargs)

    def record_success(self):
        """Record successful webhook delivery"""
        self.last_success_at = timezone.now()
        self.consecutive_failures = 0
        if self.status == "failing":
            self.status = "active"
        self.save(update_fields=["last_success_at", "consecutive_failures", "status"])

    def record_failure(self, reason: str):
        """Record failed webhook delivery"""
        self.last_failure_at = timezone.now()
        self.last_failure_reason = reason
        self.consecutive_failures += 1

        if self.consecutive_failures >= 3:
            self.status = "failing"
        if self.consecutive_failures >= 10:
            self.status = "disabled"
            self.is_active = False

        self.save(
            update_fields=[
                "last_failure_at",
                "last_failure_reason",
                "consecutive_failures",
                "status",
                "is_active",
            ]
        )


class WebhookDelivery(models.Model):
    """Log of webhook delivery attempts"""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Delivered"),
        ("failed", "Failed"),
        ("retrying", "Retrying"),
    ]

    webhook = models.ForeignKey(
        TenantWebhook, on_delete=models.CASCADE, related_name="deliveries"
    )

    # Event Data
    event_type = models.CharField(max_length=50)
    event_id = models.UUIDField(default=uuid.uuid4)
    payload = models.JSONField()

    # Delivery Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=5)

    # Response
    response_status_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    response_time_ms = models.IntegerField(null=True, blank=True)

    # Error Tracking
    error_message = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["webhook", "status"]),
            models.Index(fields=["status", "next_retry_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} -> {self.webhook.name} ({self.status})"

    def schedule_retry(self):
        """Schedule next retry with exponential backoff"""
        if self.attempts >= self.max_attempts:
            self.status = "failed"
            self.save()
            return

        # Exponential backoff: 1min, 5min, 15min, 30min, 60min
        delays = [60, 300, 900, 1800, 3600]
        delay = delays[min(self.attempts, len(delays) - 1)]

        self.status = "retrying"
        self.next_retry_at = timezone.now() + timedelta(seconds=delay)
        self.save()


# =============================================================================
# ANALYTICS DATA MODELS (Business/Enterprise Feature)
# =============================================================================


class TenantAnalyticsSnapshot(models.Model):
    """
    Daily analytics snapshots for trend analysis.
    Stores aggregated metrics for efficient querying.
    """

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="analytics_snapshots"
    )
    date = models.DateField(db_index=True)

    # User Metrics
    total_users = models.IntegerField(default=0)
    active_users = models.IntegerField(default=0)
    new_users = models.IntegerField(default=0)
    expired_users = models.IntegerField(default=0)

    # Revenue Metrics
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_count = models.IntegerField(default=0)
    avg_payment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Voucher Metrics
    vouchers_generated = models.IntegerField(default=0)
    vouchers_redeemed = models.IntegerField(default=0)

    # Device Metrics
    total_devices = models.IntegerField(default=0)
    unique_devices_connected = models.IntegerField(default=0)

    # Bundle Performance
    bundle_breakdown = models.JSONField(
        default=dict, help_text="Revenue and sales count per bundle"
    )

    # Payment Channel Breakdown
    payment_channel_breakdown = models.JSONField(
        default=dict, help_text="Revenue per payment channel (M-Pesa, TigoPesa, etc.)"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        unique_together = ["tenant", "date"]
        verbose_name = "Analytics Snapshot"
        verbose_name_plural = "Analytics Snapshots"

    def __str__(self):
        return f"{self.tenant.slug} - {self.date}"

    @classmethod
    def generate_for_date(cls, tenant, date):
        """Generate or update analytics snapshot for a specific date"""
        from django.db.models import Count, Sum, Avg
        from datetime import datetime

        start_of_day = timezone.make_aware(datetime.combine(date, datetime.min.time()))
        end_of_day = start_of_day + timedelta(days=1)

        # Get or create snapshot
        snapshot, _ = cls.objects.get_or_create(tenant=tenant, date=date)

        # User metrics
        snapshot.total_users = User.objects.filter(tenant=tenant).count()
        snapshot.active_users = User.objects.filter(
            tenant=tenant, is_active=True, paid_until__gte=start_of_day
        ).count()
        snapshot.new_users = User.objects.filter(
            tenant=tenant, created_at__gte=start_of_day, created_at__lt=end_of_day
        ).count()
        snapshot.expired_users = User.objects.filter(
            tenant=tenant, paid_until__lt=start_of_day
        ).count()

        # Revenue metrics
        payments = Payment.objects.filter(
            tenant=tenant,
            status="completed",
            completed_at__gte=start_of_day,
            completed_at__lt=end_of_day,
        )
        revenue_data = payments.aggregate(
            total=Sum("amount"), count=Count("id"), avg=Avg("amount")
        )
        snapshot.total_revenue = revenue_data["total"] or 0
        snapshot.payment_count = revenue_data["count"] or 0
        snapshot.avg_payment_amount = revenue_data["avg"] or 0

        # Voucher metrics
        snapshot.vouchers_generated = Voucher.objects.filter(
            tenant=tenant, created_at__gte=start_of_day, created_at__lt=end_of_day
        ).count()
        snapshot.vouchers_redeemed = Voucher.objects.filter(
            tenant=tenant, used_at__gte=start_of_day, used_at__lt=end_of_day
        ).count()

        # Device metrics
        snapshot.total_devices = Device.objects.filter(tenant=tenant).count()
        snapshot.unique_devices_connected = Device.objects.filter(
            tenant=tenant, last_seen__gte=start_of_day, last_seen__lt=end_of_day
        ).count()

        # Bundle breakdown
        bundle_data = payments.values("bundle__name").annotate(
            revenue=Sum("amount"), count=Count("id")
        )
        snapshot.bundle_breakdown = {
            item["bundle__name"]
            or "Unknown": {
                "revenue": float(item["revenue"] or 0),
                "count": item["count"],
            }
            for item in bundle_data
        }

        # Payment channel breakdown
        channel_data = payments.values("payment_channel").annotate(
            revenue=Sum("amount"), count=Count("id")
        )
        snapshot.payment_channel_breakdown = {
            item["payment_channel"]
            or "Unknown": {
                "revenue": float(item["revenue"] or 0),
                "count": item["count"],
            }
            for item in channel_data
        }

        snapshot.save()
        return snapshot
