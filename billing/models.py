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
    max_remote_users = models.IntegerField(default=0)  # 0 = feature disabled

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
    ppp_support = models.BooleanField(
        default=False
    )  # PPPoE customer management & billing
    remote_user_access = models.BooleanField(
        default=False
    )  # Per-tenant VPN exit for remote users

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
    snippe_api_key = models.CharField(
        max_length=255, blank=True, help_text="Snippe API key (snp_...)"
    )
    snippe_webhook_secret = models.CharField(
        max_length=255, blank=True, help_text="Snippe webhook signing secret"
    )
    preferred_payment_gateway = models.CharField(
        max_length=20,
        choices=[("clickpesa", "ClickPesa"), ("snippe", "Snippe")],
        default="clickpesa",
        help_text="Which payment gateway to use for collecting WiFi payments",
    )
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
            "remote_users": {
                "used": (
                    self.remote_users.filter(is_active=True).count()
                    if hasattr(self, "remote_users")
                    else 0
                ),
                "limit": plan.max_remote_users,
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

    def can_add_remote_user(self):
        """Check if tenant can add another remote VPN user"""
        if not self.subscription_plan:
            return False
        if not self.subscription_plan.remote_user_access:
            return False
        if self.subscription_plan.max_remote_users <= 0:
            return False
        return (
            self.remote_users.filter(is_active=True).count()
            < self.subscription_plan.max_remote_users
        )


# =========================================================================
# APP USER PROFILE — links Django User to a phone number (for mobile app)
# =========================================================================


class AppUserProfile(models.Model):
    """
    Extended profile for mobile-app users (Kitonga WiFi Remote App).
    Links a Django User to a phone number used for login & SMS OTP.
    """

    user = models.OneToOneField(
        DjangoUser,
        on_delete=models.CASCADE,
        related_name="app_profile",
    )
    phone_number = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="Normalized phone e.g. 255712345678",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "App User Profile"
        verbose_name_plural = "App User Profiles"

    def __str__(self):
        return f"{self.phone_number} → {self.user.get_full_name() or self.user.email}"


class PhoneOTP(models.Model):
    """
    SMS OTP for app-user password reset (sent via NextSMS).
    """

    PURPOSE_CHOICES = [
        ("password_reset", "Password Reset"),
        ("phone_verify", "Phone Verification"),
    ]

    phone_number = models.CharField(max_length=20, db_index=True)
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(
        max_length=20, choices=PURPOSE_CHOICES, default="password_reset"
    )
    is_used = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["phone_number", "otp_code", "is_used"]),
        ]

    def __str__(self):
        return f"OTP for {self.phone_number} - {self.purpose}"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=10)
        super().save(*args, **kwargs)

    def is_valid(self):
        if self.is_used:
            return False
        if self.attempts >= 5:
            return False
        if timezone.now() > self.expires_at:
            return False
        return True

    def verify(self, code):
        if not self.is_valid():
            return False, "OTP has expired or been used."

        self.attempts += 1
        self.save(update_fields=["attempts"])

        if self.otp_code != code:
            if self.attempts >= 5:
                return False, "Too many failed attempts. Request a new OTP."
            return False, f"Invalid OTP. {5 - self.attempts} attempts remaining."

        self.is_used = True
        self.used_at = timezone.now()
        self.save(update_fields=["is_used", "used_at"])
        return True, "OTP verified successfully."

    @staticmethod
    def generate_otp():
        import random

        return "".join([str(random.randint(0, 9)) for _ in range(6)])

    @classmethod
    def create_for_phone(cls, phone_number, purpose="password_reset"):
        # Invalidate existing unused OTPs
        cls.objects.filter(
            phone_number=phone_number, purpose=purpose, is_used=False
        ).update(is_used=True)

        otp = cls.objects.create(
            phone_number=phone_number,
            otp_code=cls.generate_otp(),
            purpose=purpose,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        return otp


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


# =============================================================================
# REMOTE USER ACCESS (VPN) MODELS
# =============================================================================


class TenantVPNConfig(models.Model):
    """
    Per-tenant WireGuard VPN configuration.
    Each tenant gets one WireGuard interface on their router.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.OneToOneField(
        Tenant, on_delete=models.CASCADE, related_name="vpn_config"
    )
    router = models.ForeignKey(
        "Router",
        on_delete=models.CASCADE,
        related_name="vpn_configs",
        help_text="Router where WireGuard interface is configured",
    )

    # WireGuard Interface Settings
    interface_name = models.CharField(
        max_length=15,
        default="wg-remote",
        help_text="WireGuard interface name on the router (max 15 chars)",
    )
    listen_port = models.IntegerField(
        default=51820, help_text="UDP port for WireGuard on the router"
    )

    # Server Keys (stored encrypted in production)
    server_private_key = models.CharField(
        max_length=64, help_text="WireGuard server private key (base64)"
    )
    server_public_key = models.CharField(
        max_length=64, help_text="WireGuard server public key (base64)"
    )

    # Network Configuration
    address_pool = models.CharField(
        max_length=18,
        default="10.100.0.0/24",
        help_text="VPN address pool CIDR (e.g. 10.100.0.0/24)",
    )
    server_address = models.GenericIPAddressField(
        default="10.100.0.1", help_text="Server-side VPN IP address"
    )
    dns_servers = models.CharField(
        max_length=100,
        default="1.1.1.1, 8.8.8.8",
        help_text="DNS servers pushed to clients",
    )
    mtu = models.IntegerField(default=1420, help_text="MTU for WireGuard tunnel")
    persistent_keepalive = models.IntegerField(
        default=25, help_text="Keepalive interval in seconds (0 to disable)"
    )

    # Router-side configuration flags
    enable_nat = models.BooleanField(
        default=True, help_text="Enable NAT/masquerade for VPN traffic to reach LAN"
    )
    enable_firewall_rules = models.BooleanField(
        default=True, help_text="Auto-create firewall rules for VPN traffic"
    )

    # Allowed traffic / routing
    allowed_ips = models.CharField(
        max_length=500,
        default="0.0.0.0/0",
        help_text="Default allowed IPs for clients (full tunnel or split)",
    )

    # Status
    is_active = models.BooleanField(default=True)
    is_configured_on_router = models.BooleanField(
        default=False,
        help_text="Whether the WireGuard interface has been pushed to the router",
    )
    last_synced_at = models.DateTimeField(
        null=True, blank=True, help_text="Last time config was synced to the router"
    )
    last_sync_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tenant VPN Configuration"
        verbose_name_plural = "Tenant VPN Configurations"

    def __str__(self):
        return f"VPN Config: {self.tenant.business_name} ({self.interface_name})"

    def get_next_available_ip(self):
        """
        Get the next available IP address from the address pool.
        Skips the server address and any already-assigned addresses.
        We check ALL remote users regardless of status because the DB
        has a unique constraint on (vpn_config_id, assigned_ip).
        Revoked users still physically hold their IP row in the DB.
        """
        import ipaddress

        network = ipaddress.ip_network(self.address_pool, strict=False)
        # Include ALL statuses — the unique constraint doesn't care about status
        used_ips = set(self.remote_users.values_list("assigned_ip", flat=True))
        used_ips.add(str(self.server_address))

        # Skip network address and broadcast
        for host in network.hosts():
            ip_str = str(host)
            if ip_str not in used_ips:
                return ip_str

        return None  # Pool exhausted


class RemoteUser(models.Model):
    """
    A remote VPN user (WireGuard peer) assigned to a tenant.
    Each remote user gets a unique key pair and IP from the tenant's VPN pool.
    """

    STATUS_CHOICES = [
        ("active", "Active"),
        ("disabled", "Disabled"),
        ("expired", "Expired"),
        ("revoked", "Revoked"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="remote_users"
    )
    vpn_config = models.ForeignKey(
        TenantVPNConfig,
        on_delete=models.CASCADE,
        related_name="remote_users",
        help_text="The VPN configuration this user belongs to",
    )

    # User identification
    name = models.CharField(
        max_length=100, help_text="Display name for this remote user"
    )
    email = models.EmailField(
        blank=True, help_text="Optional email for config delivery"
    )
    phone = models.CharField(
        max_length=20, blank=True, help_text="Optional phone number"
    )
    notes = models.TextField(blank=True, help_text="Admin notes about this user")

    # Plan (optional — links to the commercial plan this user purchased)
    plan = models.ForeignKey(
        "RemoteAccessPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="remote_users",
        help_text="The remote access plan this user is subscribed to",
    )

    # WireGuard Peer Keys
    public_key = models.CharField(
        max_length=64, help_text="Client WireGuard public key (base64)"
    )
    private_key = models.CharField(
        max_length=64,
        blank=True,
        help_text="Client private key (only stored temporarily for config generation)",
    )
    preshared_key = models.CharField(
        max_length=64, blank=True, help_text="Optional preshared key for extra security"
    )

    # Network
    assigned_ip = models.GenericIPAddressField(
        help_text="IP address assigned to this peer from the VPN pool"
    )
    allowed_ips = models.CharField(
        max_length=500,
        blank=True,
        help_text="Override allowed IPs for this specific peer",
    )

    # Access Control
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this user's access expires (null = never)",
    )

    # Bandwidth limits (in kbps, 0 = unlimited)
    bandwidth_limit_up = models.IntegerField(
        default=0, help_text="Upload bandwidth limit in kbps (0 = unlimited)"
    )
    bandwidth_limit_down = models.IntegerField(
        default=0, help_text="Download bandwidth limit in kbps (0 = unlimited)"
    )

    # Tracking
    config_downloaded = models.BooleanField(
        default=False, help_text="Whether the user has downloaded their config file"
    )
    is_configured_on_router = models.BooleanField(
        default=False, help_text="Whether this peer has been pushed to the router"
    )
    last_handshake = models.DateTimeField(
        null=True, blank=True, help_text="Last WireGuard handshake time from router"
    )

    # Audit
    created_by = models.ForeignKey(
        DjangoUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_remote_users",
        help_text="Staff user who created this remote user",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Remote User"
        verbose_name_plural = "Remote Users"
        ordering = ["-created_at"]
        unique_together = [
            ("vpn_config", "assigned_ip"),
            ("vpn_config", "public_key"),
        ]

    def __str__(self):
        return f"{self.name} ({self.assigned_ip}) - {self.tenant.business_name}"

    @property
    def is_expired(self):
        if self.expires_at and self.expires_at < timezone.now():
            return True
        return False

    def generate_client_config(self):
        """
        Generate a WireGuard client configuration string for this user.
        Uses the VPS relay endpoint if configured (clients connect to the
        VPS, not directly to the MikroTik behind NAT).
        """
        from django.conf import settings as _settings

        vpn = self.vpn_config

        # Use VPS relay keys/endpoint if configured, otherwise fall back
        # to the vpn_config/router values.
        server_public_key = (
            getattr(_settings, "WG_VPS_PUBLIC_KEY", "") or vpn.server_public_key
        )
        vps_endpoint = getattr(_settings, "WG_VPS_ENDPOINT", "")
        if not vps_endpoint:
            vps_endpoint = f"{vpn.router.host}:{vpn.listen_port}"

        config_lines = [
            "[Interface]",
            (
                f"PrivateKey = {self.private_key}"
                if self.private_key
                else "# PrivateKey = <INSERT_YOUR_PRIVATE_KEY>"
            ),
            f"Address = {self.assigned_ip}/32",
            f"DNS = {vpn.dns_servers}",
            f"MTU = {vpn.mtu}",
            "",
            "[Peer]",
            f"PublicKey = {server_public_key}",
        ]
        if self.preshared_key:
            config_lines.append(f"PresharedKey = {self.preshared_key}")

        # Use peer-specific allowed_ips or fall back to VPN config default
        allowed = self.allowed_ips or vpn.allowed_ips
        config_lines.append(f"AllowedIPs = {allowed}")

        # Endpoint = VPS public relay or router direct
        config_lines.append(f"Endpoint = {vps_endpoint}")

        if vpn.persistent_keepalive > 0:
            config_lines.append(f"PersistentKeepalive = {vpn.persistent_keepalive}")

        return "\n".join(config_lines)


class RemoteAccessLog(models.Model):
    """
    Logs for remote user VPN connection events.
    Used for auditing, analytics, and troubleshooting.
    """

    EVENT_CHOICES = [
        ("connected", "Connected"),
        ("disconnected", "Disconnected"),
        ("handshake", "Handshake"),
        ("config_generated", "Config Generated"),
        ("config_downloaded", "Config Downloaded"),
        ("peer_added", "Peer Added to Router"),
        ("peer_removed", "Peer Removed from Router"),
        ("expired", "Access Expired"),
        ("revoked", "Access Revoked"),
        ("reactivated", "Access Reactivated"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    remote_user = models.ForeignKey(
        RemoteUser,
        on_delete=models.CASCADE,
        related_name="access_logs",
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="remote_access_logs",
        help_text="Denormalized for faster querying",
    )

    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    event_details = models.TextField(
        blank=True, help_text="Additional event details/JSON"
    )

    # Connection metadata
    client_endpoint = models.CharField(
        max_length=50, blank=True, help_text="Client IP:port as seen by the server"
    )
    bytes_sent = models.BigIntegerField(default=0, help_text="Bytes sent to client")
    bytes_received = models.BigIntegerField(
        default=0, help_text="Bytes received from client"
    )

    timestamp = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Remote Access Log"
        verbose_name_plural = "Remote Access Logs"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["tenant", "-timestamp"]),
            models.Index(fields=["remote_user", "-timestamp"]),
            models.Index(fields=["event_type"]),
        ]

    def __str__(self):
        return f"{self.remote_user.name} - {self.event_type} @ {self.timestamp}"


class RemoteAccessPlan(models.Model):
    """
    Commercial remote access (VPN) plan that tenants sell to their remote users.
    Analogous to Bundle (hotspot) and PPPPlan (PPPoE), but for WireGuard VPN.
    Defines pricing, duration, bandwidth limits, and device caps per plan tier.
    """

    BILLING_CYCLE_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly (3 months)"),
        ("biannual", "Bi-Annual (6 months)"),
        ("annual", "Annual (12 months)"),
        ("custom", "Custom Days"),
        ("unlimited", "Unlimited (No Expiry)"),
    ]

    CYCLE_DAYS_MAP = {
        "daily": 1,
        "weekly": 7,
        "monthly": 30,
        "quarterly": 90,
        "biannual": 180,
        "annual": 365,
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="remote_access_plans"
    )

    # Plan identification
    name = models.CharField(
        max_length=150,
        help_text="Customer-facing plan name, e.g. 'Remote Basic Monthly'",
    )
    description = models.TextField(
        blank=True,
        help_text="Customer-facing description of the plan",
    )

    # Pricing
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Price per billing cycle",
    )
    currency = models.CharField(max_length=3, default="TZS")

    # Promotional pricing
    promo_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Promotional/discounted price. Null = no promo.",
    )
    promo_label = models.CharField(
        max_length=50,
        blank=True,
        help_text="Promo badge text, e.g. 'Save 20%' or 'Launch Offer'",
    )

    # Billing cycle & duration
    billing_cycle = models.CharField(
        max_length=20,
        choices=BILLING_CYCLE_CHOICES,
        default="monthly",
    )
    billing_days = models.IntegerField(
        default=30,
        help_text="Duration in days this plan grants. Auto-set from billing_cycle unless custom.",
    )

    # Bandwidth limits (kbps, 0 = unlimited)
    bandwidth_limit_down = models.IntegerField(
        default=0,
        help_text="Download bandwidth limit in kbps (0 = unlimited)",
    )
    bandwidth_limit_up = models.IntegerField(
        default=0,
        help_text="Upload bandwidth limit in kbps (0 = unlimited)",
    )

    # Speed display (human-readable, for portal/invoices)
    download_speed = models.CharField(
        max_length=20,
        blank=True,
        help_text="Human-readable download speed e.g. '10 Mbps'",
    )
    upload_speed = models.CharField(
        max_length=20,
        blank=True,
        help_text="Human-readable upload speed e.g. '5 Mbps'",
    )

    # Data cap (optional, GB per cycle)
    data_limit_gb = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Data cap in GB per cycle. Null = unlimited.",
    )

    # Device / connection limits per user on this plan
    max_devices_per_user = models.IntegerField(
        default=1,
        help_text="Number of simultaneous WireGuard peers allowed per remote user",
    )

    # Access scope
    allowed_ips = models.CharField(
        max_length=500,
        blank=True,
        help_text="Override allowed IPs for users on this plan (empty = use VPN config default)",
    )
    full_tunnel = models.BooleanField(
        default=True,
        help_text="True = route all traffic through VPN (0.0.0.0/0). False = split tunnel.",
    )

    # Plan features / selling points (JSON list)
    features = models.JSONField(
        default=list,
        blank=True,
        help_text='Feature strings shown in portal, e.g. ["Full tunnel", "10 Mbps", "Unlimited data"]',
    )

    # Display & ordering
    display_order = models.IntegerField(
        default=0,
        help_text="Lower number = shown first in portal",
    )
    is_popular = models.BooleanField(
        default=False,
        help_text="Mark as popular/recommended to highlight in portal",
    )
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["tenant", "display_order", "price"]
        verbose_name = "Remote Access Plan"
        verbose_name_plural = "Remote Access Plans"

    def __str__(self):
        return f"{self.tenant.business_name} — {self.name} (TSh {self.price:,.0f}/{self.billing_cycle})"

    def save(self, *args, **kwargs):
        # Auto-set billing_days from cycle if not custom/unlimited
        if (
            self.billing_cycle not in ("custom", "unlimited")
            and self.billing_cycle in self.CYCLE_DAYS_MAP
        ):
            self.billing_days = self.CYCLE_DAYS_MAP[self.billing_cycle]
        elif self.billing_cycle == "unlimited":
            self.billing_days = 0  # 0 means no expiry
        super().save(*args, **kwargs)

    @property
    def effective_price(self):
        """Return promo price if set, otherwise regular price."""
        if self.promo_price is not None:
            return self.promo_price
        return self.price

    @property
    def price_per_day(self):
        """Calculate the per-day cost for comparison."""
        if self.billing_days and self.billing_days > 0:
            return self.effective_price / self.billing_days
        return self.effective_price

    @property
    def speed_display(self):
        """Human-readable speed string."""
        if self.download_speed and self.upload_speed:
            return f"↓{self.download_speed} / ↑{self.upload_speed}"
        if self.download_speed:
            return f"↓{self.download_speed}"
        return "Unlimited"

    @property
    def data_display(self):
        """Human-readable data limit string."""
        if self.data_limit_gb is not None:
            return f"{self.data_limit_gb} GB"
        return "Unlimited"

    @property
    def duration_display(self):
        """Human-readable duration string."""
        if self.billing_cycle == "unlimited":
            return "Unlimited"
        if self.billing_days >= 365:
            years = self.billing_days // 365
            return f"{years} year{'s' if years > 1 else ''}"
        if self.billing_days >= 30:
            months = self.billing_days // 30
            return f"{months} month{'s' if months > 1 else ''}"
        if self.billing_days >= 7:
            weeks = self.billing_days // 7
            return f"{weeks} week{'s' if weeks > 1 else ''}"
        return f"{self.billing_days} day{'s' if self.billing_days != 1 else ''}"

    @property
    def subscriber_count(self):
        """Number of active remote users currently on this plan."""
        return self.remote_users.filter(is_active=True).count()


class RemoteAccessPayment(models.Model):
    """
    Payment record for remote access VPN plans.
    Tracks payments from remote users for their VPN access.
    Follows the same pattern as PPPPayment.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("expired", "Expired"),
        ("refunded", "Refunded"),
    ]

    CHANNEL_CHOICES = [
        ("snippe", "Snippe"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="remote_access_payments"
    )
    remote_user = models.ForeignKey(
        RemoteUser,
        on_delete=models.CASCADE,
        related_name="payments",
        help_text="The remote user this payment is for",
    )
    plan = models.ForeignKey(
        "RemoteAccessPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
        help_text="The plan purchased",
    )

    # Payment details
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="TZS")
    billing_days = models.IntegerField(
        default=30,
        help_text="Number of days this payment grants",
    )

    # References
    order_reference = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique order reference for this payment",
    )
    payment_reference = models.CharField(
        max_length=255,
        blank=True,
        help_text="External payment reference (from gateway)",
    )
    transaction_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Transaction ID from payment gateway",
    )

    # Payment method
    payment_channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
        default="snippe",
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Phone number used for mobile money payment",
    )

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Remote Access Payment"
        verbose_name_plural = "Remote Access Payments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.order_reference} - {self.remote_user.name} - {self.status}"

    def generate_order_reference(self):
        """Generate a unique order reference."""
        import random
        import string

        prefix = "KTN"
        random_part = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=8)
        )
        return f"{prefix}-{random_part}"

    def save(self, *args, **kwargs):
        if not self.order_reference:
            self.order_reference = self.generate_order_reference()
        super().save(*args, **kwargs)

    def mark_completed(self):
        """
        Mark payment as completed and extend the remote user's access.
        """
        if self.status == "completed":
            return  # Already processed

        self.status = "completed"
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at", "updated_at"])

        # Extend remote user access
        remote_user = self.remote_user
        now = timezone.now()

        if self.billing_days > 0:
            if remote_user.expires_at and remote_user.expires_at > now:
                # Still has time — extend from current expiry
                remote_user.expires_at = remote_user.expires_at + timedelta(
                    days=self.billing_days
                )
            else:
                # Expired or new — start from now
                remote_user.expires_at = now + timedelta(days=self.billing_days)
        else:
            # Unlimited plan — set no expiry
            remote_user.expires_at = None

        # Apply bandwidth limits from plan if available
        if self.plan:
            remote_user.bandwidth_limit_down = self.plan.bandwidth_limit_down
            remote_user.bandwidth_limit_up = self.plan.bandwidth_limit_up

        remote_user.status = "active"
        remote_user.is_active = True
        remote_user.save(
            update_fields=[
                "expires_at",
                "status",
                "is_active",
                "bandwidth_limit_down",
                "bandwidth_limit_up",
                "updated_at",
            ]
        )

    def mark_failed(self):
        """Mark payment as failed."""
        self.status = "failed"
        self.save(update_fields=["status", "updated_at"])


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
    # Persist phone number so it survives user deletion (SET_NULL)
    used_by_phone = models.CharField(max_length=20, blank=True, default="")
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
        self.used_by_phone = user.phone_number  # Persist phone even if user deleted
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


# =============================================================================
# PPP (Point-to-Point Protocol) MODELS — Enterprise Plan Feature
# =============================================================================


class PPPProfile(models.Model):
    """
    PPP speed/service profile synced to MikroTik /ppp/profile.
    Defines bandwidth tiers and connection parameters for PPPoE customers.
    """

    SERVICE_TYPE_CHOICES = [
        ("pppoe", "PPPoE"),
        ("l2tp", "L2TP"),
        ("pptp", "PPTP"),
        ("any", "Any"),
    ]

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="ppp_profiles"
    )
    router = models.ForeignKey(
        Router,
        on_delete=models.CASCADE,
        related_name="ppp_profiles",
        help_text="Router where this profile is provisioned",
    )

    # Profile identification
    name = models.CharField(
        max_length=100,
        help_text="Profile name (synced to MikroTik /ppp/profile name)",
    )

    # Bandwidth limits
    rate_limit = models.CharField(
        max_length=100,
        blank=True,
        help_text="MikroTik rate-limit format: upload/download e.g. '5M/10M'",
    )

    # IP addressing
    local_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Gateway IP assigned to router side of the PPP tunnel",
    )
    remote_address = models.CharField(
        max_length=100,
        blank=True,
        help_text="IP pool name or static IP for the customer side",
    )
    dns_server = models.CharField(
        max_length=255,
        blank=True,
        help_text="DNS servers, comma-separated e.g. '8.8.8.8,8.8.4.4'",
    )

    # Connection parameters
    service_type = models.CharField(
        max_length=10,
        choices=SERVICE_TYPE_CHOICES,
        default="pppoe",
    )
    session_timeout = models.CharField(
        max_length=20,
        blank=True,
        help_text="Session timeout e.g. '00:00:00' (0 = unlimited)",
    )
    idle_timeout = models.CharField(
        max_length=20,
        blank=True,
        help_text="Idle timeout e.g. '00:05:00'",
    )
    address_pool = models.CharField(
        max_length=100,
        blank=True,
        help_text="MikroTik IP pool name for dynamic assignment",
    )

    # Billing reference
    monthly_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Default monthly price (TSh) for customers on this profile",
    )

    # Metadata
    is_active = models.BooleanField(default=True)
    synced_to_router = models.BooleanField(
        default=False,
        help_text="Whether this profile has been pushed to the MikroTik router",
    )
    mikrotik_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="MikroTik internal ID (.id) of this profile on the router",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["tenant", "name"]
        unique_together = ["tenant", "router", "name"]
        verbose_name = "PPP Profile"
        verbose_name_plural = "PPP Profiles"

    def __str__(self):
        return f"{self.tenant.business_name} — {self.name} ({self.rate_limit or 'unlimited'})"


class PPPPlan(models.Model):
    """
    Commercial PPPoE billing plan (the package customers buy).
    Links a PPPProfile (MikroTik speed tier) to pricing, duration, and data caps.
    This is analogous to Bundle for hotspot, but designed for PPPoE subscribers.
    """

    BILLING_CYCLE_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly (3 months)"),
        ("biannual", "Bi-Annual (6 months)"),
        ("annual", "Annual (12 months)"),
        ("custom", "Custom Days"),
    ]

    # Map cycle to days for auto-calculation
    CYCLE_DAYS_MAP = {
        "daily": 1,
        "weekly": 7,
        "monthly": 30,
        "quarterly": 90,
        "biannual": 180,
        "annual": 365,
    }

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="ppp_plans"
    )
    profile = models.ForeignKey(
        PPPProfile,
        on_delete=models.CASCADE,
        related_name="plans",
        help_text="The MikroTik PPP profile (speed tier) this plan uses",
    )

    # Plan identification
    name = models.CharField(
        max_length=150,
        help_text="Customer-facing plan name, e.g. 'Home 10Mbps Monthly'",
    )
    description = models.TextField(
        blank=True,
        help_text="Customer-facing description of the plan",
    )

    # Pricing
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Price (TSh) per billing cycle",
    )
    currency = models.CharField(max_length=3, default="TZS")

    # Billing cycle
    billing_cycle = models.CharField(
        max_length=20,
        choices=BILLING_CYCLE_CHOICES,
        default="monthly",
    )
    billing_days = models.IntegerField(
        default=30,
        help_text="Duration in days this plan grants. Auto-set from billing_cycle unless custom.",
    )

    # Data caps (optional)
    data_limit_gb = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Data cap in GB per cycle. Null = unlimited.",
    )

    # Speed display (human-readable, for invoices/SMS)
    download_speed = models.CharField(
        max_length=20,
        blank=True,
        help_text="Human-readable download speed e.g. '10 Mbps'",
    )
    upload_speed = models.CharField(
        max_length=20,
        blank=True,
        help_text="Human-readable upload speed e.g. '5 Mbps'",
    )

    # Plan features / selling points (JSON list)
    features = models.JSONField(
        default=list,
        blank=True,
        help_text='List of feature strings, e.g. ["Unlimited data", "Static IP", "24/7 support"]',
    )

    # Popularity / display
    display_order = models.IntegerField(
        default=0,
        help_text="Lower number = shown first",
    )
    is_popular = models.BooleanField(
        default=False,
        help_text="Mark as popular/recommended to highlight in customer portal",
    )
    is_active = models.BooleanField(default=True)

    # Promotional pricing
    promo_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Promotional/discounted price (TSh). Null = no promo.",
    )
    promo_label = models.CharField(
        max_length=50,
        blank=True,
        help_text="Promo badge text, e.g. 'Save 20%' or 'New Customer Offer'",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["tenant", "display_order", "price"]
        verbose_name = "PPP Plan"
        verbose_name_plural = "PPP Plans"

    def __str__(self):
        return f"{self.tenant.business_name} — {self.name} (TSh {self.price:,.0f}/{self.billing_cycle})"

    def save(self, *args, **kwargs):
        # Auto-set billing_days from cycle if not custom
        if self.billing_cycle != "custom" and self.billing_cycle in self.CYCLE_DAYS_MAP:
            self.billing_days = self.CYCLE_DAYS_MAP[self.billing_cycle]
        super().save(*args, **kwargs)

    @property
    def effective_price(self):
        """Return promo price if set, otherwise regular price."""
        if self.promo_price is not None:
            return self.promo_price
        return self.price

    @property
    def price_per_day(self):
        """Calculate the per-day cost for comparison."""
        if self.billing_days and self.billing_days > 0:
            return self.effective_price / self.billing_days
        return self.effective_price

    @property
    def customer_count(self):
        """Number of customers currently on this plan."""
        return self.customers.count()

    @property
    def speed_display(self):
        """Human-readable speed string."""
        if self.download_speed and self.upload_speed:
            return f"↓{self.download_speed} / ↑{self.upload_speed}"
        if self.download_speed:
            return f"↓{self.download_speed}"
        # Fall back to profile rate_limit
        return self.profile.rate_limit or "Unlimited"

    @property
    def data_display(self):
        """Human-readable data limit string."""
        if self.data_limit_gb is not None:
            return f"{self.data_limit_gb} GB"
        return "Unlimited"


class PPPCustomer(models.Model):
    """
    PPPoE customer account synced to MikroTik /ppp/secret.
    Represents a dedicated subscriber with username/password authentication.
    """

    STATUS_CHOICES = [
        ("active", "Active"),
        ("suspended", "Suspended"),
        ("disabled", "Disabled"),
        ("expired", "Expired"),
    ]

    BILLING_TYPE_CHOICES = [
        ("monthly", "Monthly Recurring"),
        ("prepaid", "Prepaid (days)"),
        ("unlimited", "Unlimited / Manual"),
    ]

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="ppp_customers"
    )
    router = models.ForeignKey(
        Router,
        on_delete=models.CASCADE,
        related_name="ppp_customers",
        help_text="Router where this secret is provisioned",
    )
    profile = models.ForeignKey(
        PPPProfile,
        on_delete=models.PROTECT,
        related_name="customers",
        help_text="PPP profile (speed tier) for this customer",
    )
    plan = models.ForeignKey(
        PPPPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customers",
        help_text="Billing plan this customer is subscribed to",
    )

    # PPP credentials (synced to /ppp/secret)
    username = models.CharField(max_length=100, help_text="PPPoE login username")
    password = models.CharField(max_length=255, help_text="PPPoE login password")
    service = models.CharField(
        max_length=50,
        blank=True,
        help_text="PPPoE service name filter (blank = any)",
    )

    # Customer info
    full_name = models.CharField(max_length=200, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True, help_text="Physical address / location")

    # IP & access control
    static_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Fixed remote-address (leave blank for dynamic from pool)",
    )
    mac_address = models.CharField(
        max_length=17,
        blank=True,
        help_text="MAC binding for caller-id e.g. 'AA:BB:CC:DD:EE:FF'",
    )
    caller_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Caller-ID restriction (MAC or other identifier)",
    )

    # Billing
    billing_type = models.CharField(
        max_length=20,
        choices=BILLING_TYPE_CHOICES,
        default="monthly",
    )
    monthly_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Override price (TSh). If blank, uses profile default.",
    )
    paid_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Service expiry date. Null = never expires (unlimited).",
    )
    last_payment_date = models.DateTimeField(null=True, blank=True)
    last_payment_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    comment = models.TextField(
        blank=True, help_text="Internal notes (also synced to MikroTik comment)"
    )

    # MikroTik sync
    synced_to_router = models.BooleanField(
        default=False,
        help_text="Whether this secret has been pushed to the MikroTik router",
    )
    mikrotik_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="MikroTik internal ID (.id) of this secret on the router",
    )

    # ClickPesa BillPay
    control_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="ClickPesa BillPay control number for recurring payments",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["tenant", "username"]
        unique_together = ["tenant", "router", "username"]
        verbose_name = "PPP Customer"
        verbose_name_plural = "PPP Customers"

    def __str__(self):
        label = self.full_name or self.username
        return f"{self.tenant.business_name} — {label} ({self.profile.name})"

    @property
    def effective_price(self):
        """Return customer-level override, plan price, or profile default."""
        if self.monthly_price is not None:
            return self.monthly_price
        if self.plan_id:
            return self.plan.effective_price
        return self.profile.monthly_price

    @property
    def is_expired(self):
        """Check if the customer's paid period has lapsed."""
        if self.billing_type == "unlimited" or self.paid_until is None:
            return False
        return timezone.now() > self.paid_until

    def suspend(self, reason=""):
        """Mark customer as suspended (should also disable on router)."""
        self.status = "suspended"
        if reason:
            self.comment = f"{self.comment}\n[Suspended] {reason}".strip()
        self.save(update_fields=["status", "comment", "updated_at"])

    def activate(self):
        """Re-activate a suspended customer."""
        self.status = "active"
        self.save(update_fields=["status", "updated_at"])


class PPPPayment(models.Model):
    """
    Payment record for PPPoE customer subscriptions.
    Tracks monthly/prepaid payments and triggers auto-enable on MikroTik.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("expired", "Expired"),
    ]

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="ppp_payments"
    )
    customer = models.ForeignKey(
        PPPCustomer, on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    phone_number = models.CharField(max_length=20, help_text="Phone used for payment")
    order_reference = models.CharField(max_length=100, unique=True)
    payment_reference = models.CharField(
        max_length=100, blank=True, help_text="External reference from Snippe"
    )
    payment_channel = models.CharField(max_length=50, default="snippe")
    control_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="ClickPesa BillPay control number for this payment",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    billing_days = models.IntegerField(
        default=30, help_text="Number of days this payment covers"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "PPP Payment"
        verbose_name_plural = "PPP Payments"

    def __str__(self):
        return f"{self.customer.username} — TSh {self.amount} — {self.status}"

    def mark_completed(self, payment_reference="", channel=""):
        """
        Mark payment as completed.
        Extends the customer's paid_until and activates on router.
        """
        from datetime import timedelta
        from .mikrotik import activate_ppp_customer_on_router

        if self.status == "completed" and self.completed_at:
            return  # Idempotent

        self.status = "completed"
        self.payment_reference = payment_reference or self.payment_reference
        if channel:
            self.payment_channel = channel
        self.completed_at = timezone.now()
        self.save()

        # Extend paid_until
        customer = self.customer
        now = timezone.now()
        if customer.paid_until and customer.paid_until > now:
            # Still has time — extend from current expiry
            customer.paid_until = customer.paid_until + timedelta(
                days=self.billing_days
            )
        else:
            # Expired or new — start from now
            customer.paid_until = now + timedelta(days=self.billing_days)

        customer.last_payment_date = now
        customer.last_payment_amount = self.amount
        customer.status = "active"
        customer.save(
            update_fields=[
                "paid_until",
                "last_payment_date",
                "last_payment_amount",
                "status",
                "updated_at",
            ]
        )

        # Enable on MikroTik router
        try:
            activate_ppp_customer_on_router(customer)
        except Exception as e:
            import logging

            logging.getLogger(__name__).error(
                f"Failed to activate PPP customer {customer.username} on router: {e}"
            )

    def mark_failed(self):
        self.status = "failed"
        self.save(update_fields=["status", "updated_at"])
