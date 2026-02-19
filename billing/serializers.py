"""
Serializers for API requests and responses
"""

from rest_framework import serializers
from .models import (
    User,
    Payment,
    AccessLog,
    Voucher,
    Bundle,
    Device,
    SubscriptionPlan,
    Tenant,
    TenantStaff,
    TenantSubscriptionPayment,
    Router,
    Location,
    PPPProfile,
    PPPPlan,
    PPPCustomer,
)
from .utils import normalize_phone_number, validate_tanzania_phone_number


def validate_phone_number_field(phone_number):
    """
    Validator for phone number fields in serializers
    """
    if not phone_number:
        raise serializers.ValidationError("Phone number is required")

    try:
        # Normalize the phone number
        normalized = normalize_phone_number(phone_number)

        # Validate it's a Tanzania number
        is_valid, network, normalized = validate_tanzania_phone_number(normalized)
        if not is_valid:
            raise serializers.ValidationError(
                f"Invalid Tanzania phone number: {phone_number}"
            )

        return normalized

    except ValueError as e:
        raise serializers.ValidationError(f"Invalid phone number format: {e}")


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = [
            "id",
            "mac_address",
            "ip_address",
            "device_name",
            "is_active",
            "first_seen",
            "last_seen",
        ]
        read_only_fields = ["id", "first_seen", "last_seen"]


class BundleSerializer(serializers.ModelSerializer):
    duration_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = Bundle
        fields = [
            "id",
            "name",
            "duration_hours",
            "duration_days",
            "price",
            "description",
            "is_active",
            "display_order",
        ]
        read_only_fields = ["id"]


class UserSerializer(serializers.ModelSerializer):
    has_active_access = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()
    active_devices = serializers.SerializerMethodField()
    device_limit_reached = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "phone_number",
            "paid_until",
            "is_active",
            "has_active_access",
            "time_remaining",
            "total_payments",
            "max_devices",
            "active_devices",
            "device_limit_reached",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "total_payments"]

    def get_has_active_access(self, obj):
        return obj.has_active_access()

    def get_time_remaining(self, obj):
        if obj.has_active_access():
            from django.utils import timezone

            remaining = obj.paid_until - timezone.now()
            return {
                "hours": int(remaining.total_seconds() // 3600),
                "minutes": int((remaining.total_seconds() % 3600) // 60),
            }
        return None

    def get_active_devices(self, obj):
        return obj.get_active_devices().count()

    def get_device_limit_reached(self, obj):
        return not obj.can_add_device()


class PaymentSerializer(serializers.ModelSerializer):
    bundle_name = serializers.CharField(source="bundle.name", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "amount",
            "phone_number",
            "payment_reference",
            "transaction_id",
            "order_reference",
            "payment_channel",
            "bundle",
            "bundle_name",
            "status",
            "created_at",
            "completed_at",
        ]
        read_only_fields = ["id", "created_at", "completed_at", "payment_reference"]


class InitiatePaymentSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    bundle_id = serializers.IntegerField(required=False)
    router_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Router ID to auto-detect tenant from captive portal",
    )
    mac_address = serializers.CharField(max_length=17, required=False)
    ip_address = serializers.IPAddressField(required=False)

    def validate_phone_number(self, value):
        """Validate and normalize phone number"""
        return validate_phone_number_field(value)

    def validate_bundle_id(self, value):
        if value is not None:
            from .models import Bundle

            try:
                Bundle.objects.get(id=value, is_active=True)
            except Bundle.DoesNotExist:
                raise serializers.ValidationError("Invalid bundle selected")
        return value


class VerifyAccessSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    ip_address = serializers.IPAddressField(required=False)
    mac_address = serializers.CharField(max_length=17, required=False)
    router_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Router ID for specific router authorization",
    )

    def validate_phone_number(self, value):
        """Validate and normalize phone number"""
        return validate_phone_number_field(value)


class VoucherSerializer(serializers.ModelSerializer):
    used_by_phone = serializers.CharField(source="used_by.phone_number", read_only=True)
    duration_display = serializers.CharField(
        source="get_duration_hours_display", read_only=True
    )

    class Meta:
        model = Voucher
        fields = [
            "id",
            "code",
            "duration_hours",
            "duration_display",
            "is_used",
            "created_at",
            "created_by",
            "used_at",
            "used_by_phone",
            "batch_id",
            "notes",
        ]
        read_only_fields = [
            "id",
            "code",
            "is_used",
            "created_at",
            "used_at",
            "used_by_phone",
        ]


class GenerateVouchersSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=1000)
    duration_hours = serializers.ChoiceField(choices=[24, 168, 720])
    batch_id = serializers.CharField(max_length=50, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)
    admin_phone_number = serializers.CharField(max_length=15, required=True)
    language = serializers.ChoiceField(
        choices=["en", "sw"], default="en", required=False
    )

    def validate_admin_phone_number(self, value):
        """Validate and normalize admin phone number"""
        return validate_phone_number_field(value)


class RedeemVoucherSerializer(serializers.Serializer):
    voucher_code = serializers.CharField(max_length=16)
    phone_number = serializers.CharField(max_length=15)
    # Optional device information for immediate access setup
    ip_address = serializers.IPAddressField(required=False)
    mac_address = serializers.CharField(max_length=17, required=False)
    router_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Router ID to auto-detect tenant from captive portal",
    )

    def validate_voucher_code(self, value):
        # Remove extra spaces and convert to uppercase, but preserve the original format
        value = value.strip().upper()

        # Don't modify the voucher code format - use it as provided
        # Just clean up any extra whitespace
        value = " ".join(value.split())

        return value

    def validate_phone_number(self, value):
        """Validate and normalize phone number"""
        return validate_phone_number_field(value)

    def validate_mac_address(self, value):
        if value:
            # Basic MAC address format validation
            import re

            if not re.match(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", value):
                raise serializers.ValidationError("Invalid MAC address format")
        return value


# =============================================================================
# SAAS SUBSCRIPTION SERIALIZERS
# =============================================================================


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Serializer for subscription plans"""

    features = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPlan
        fields = [
            "id",
            "name",
            "display_name",
            "description",
            "monthly_price",
            "yearly_price",
            "currency",
            "max_routers",
            "max_wifi_users",
            "max_vouchers_per_month",
            "max_locations",
            "max_staff_accounts",
            "features",
            "revenue_share_percentage",
            "is_active",
        ]

    def get_features(self, obj):
        return {
            "custom_branding": obj.custom_branding,
            "custom_domain": obj.custom_domain,
            "api_access": obj.api_access,
            "white_label": obj.white_label,
            "priority_support": obj.priority_support,
            "analytics_dashboard": obj.analytics_dashboard,
            "sms_notifications": obj.sms_notifications,
        }


class TenantSerializer(serializers.ModelSerializer):
    """Serializer for tenant details"""

    subscription_plan_name = serializers.CharField(
        source="subscription_plan.display_name", read_only=True
    )
    subscription_valid = serializers.SerializerMethodField()
    usage_stats = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = [
            "id",
            "slug",
            "business_name",
            "business_email",
            "business_phone",
            "business_address",
            "country",
            "timezone",
            "subscription_plan",
            "subscription_plan_name",
            "subscription_status",
            "subscription_started_at",
            "subscription_ends_at",
            "billing_cycle",
            "trial_ends_at",
            "subscription_valid",
            "logo",
            "primary_color",
            "secondary_color",
            "custom_domain",
            "usage_stats",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "slug", "api_key", "created_at"]

    def get_subscription_valid(self, obj):
        return obj.is_subscription_valid()

    def get_usage_stats(self, obj):
        return obj.get_usage_stats()


class TenantRegistrationSerializer(serializers.Serializer):
    """Serializer for new tenant registration"""

    # Business information
    business_name = serializers.CharField(max_length=200)
    business_email = serializers.EmailField()
    business_phone = serializers.CharField(max_length=20)
    business_address = serializers.CharField(required=False, allow_blank=True)

    # Admin user
    admin_email = serializers.EmailField()
    admin_password = serializers.CharField(min_length=8, write_only=True)
    admin_first_name = serializers.CharField(max_length=100, required=False)
    admin_last_name = serializers.CharField(max_length=100, required=False)

    # Optional
    slug = serializers.SlugField(max_length=50, required=False)
    plan_id = serializers.IntegerField(required=False)

    def validate_business_phone(self, value):
        """Validate and normalize phone number"""
        return validate_phone_number_field(value)

    def validate_slug(self, value):
        if value and Tenant.objects.filter(slug=value).exists():
            raise serializers.ValidationError("This subdomain is already taken")
        return value

    def validate_admin_email(self, value):
        from django.contrib.auth.models import User as DjangoUser

        if DjangoUser.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "An account with this email already exists"
            )
        return value


class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    """Serializer for subscription payment records"""

    plan_name = serializers.CharField(source="plan.display_name", read_only=True)

    class Meta:
        model = TenantSubscriptionPayment
        fields = [
            "id",
            "tenant",
            "plan",
            "plan_name",
            "amount",
            "currency",
            "billing_cycle",
            "transaction_id",
            "payment_reference",
            "payment_method",
            "status",
            "period_start",
            "period_end",
            "created_at",
            "completed_at",
        ]
        read_only_fields = ["id", "created_at", "completed_at", "transaction_id"]


class CreateSubscriptionPaymentSerializer(serializers.Serializer):
    """Serializer for creating a subscription payment"""

    plan_id = serializers.IntegerField()
    billing_cycle = serializers.ChoiceField(
        choices=["monthly", "yearly"], default="monthly"
    )

    def validate_plan_id(self, value):
        try:
            SubscriptionPlan.objects.get(id=value, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError("Invalid subscription plan")
        return value


class RouterSerializer(serializers.ModelSerializer):
    """Serializer for router configuration"""

    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = Router
        fields = [
            "id",
            "name",
            "description",
            "location",
            "location_name",
            "host",
            "port",
            "username",
            "password",
            "use_ssl",
            "hotspot_interface",
            "hotspot_profile",
            "router_model",
            "router_version",
            "router_identity",
            "status",
            "is_active",
            "last_seen",
            "last_error",
            "created_at",
        ]
        extra_kwargs = {
            "password": {"write_only": True, "required": False},
            "router_model": {"read_only": True},
            "router_version": {"read_only": True},
            "router_identity": {"read_only": True},
            "status": {"read_only": True},
            "last_seen": {"read_only": True},
            "last_error": {"read_only": True},
            "created_at": {"read_only": True},
        }


class LocationSerializer(serializers.ModelSerializer):
    """Serializer for tenant locations"""

    router_count = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = [
            "id",
            "name",
            "address",
            "city",
            "manager_name",
            "manager_phone",
            "is_active",
            "router_count",
            "created_at",
        ]

    def get_router_count(self, obj):
        return obj.routers.filter(is_active=True).count()


class TenantStaffSerializer(serializers.ModelSerializer):
    """Serializer for tenant staff members"""

    email = serializers.CharField(source="user.email", read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = TenantStaff
        fields = [
            "id",
            "user",
            "email",
            "full_name",
            "role",
            "can_manage_routers",
            "can_manage_users",
            "can_manage_payments",
            "can_manage_vouchers",
            "can_view_reports",
            "can_manage_staff",
            "can_manage_settings",
            "is_active",
            "invited_at",
            "joined_at",
        ]

    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email


class UsageSummarySerializer(serializers.Serializer):
    """Serializer for usage summary response"""

    routers = serializers.DictField()
    wifi_users = serializers.DictField()
    vouchers_this_month = serializers.DictField()
    locations = serializers.DictField()
    staff = serializers.DictField()
    subscription_valid = serializers.BooleanField()


class RevenueReportSerializer(serializers.Serializer):
    """Serializer for revenue report response"""

    tenant = serializers.CharField()
    period = serializers.CharField()
    total_payments = serializers.IntegerField()
    total_revenue = serializers.FloatField()
    revenue_share_percentage = serializers.FloatField()
    platform_share = serializers.FloatField()
    tenant_share = serializers.FloatField()
    currency = serializers.CharField()


# =============================================================================
# TENANT PORTAL SERIALIZERS (Phase 3)
# =============================================================================


class RouterWizardSerializer(serializers.Serializer):
    """Serializer for router connection test"""

    host = serializers.CharField(max_length=255)
    port = serializers.IntegerField(default=8728, min_value=1, max_value=65535)
    username = serializers.CharField(max_length=100, default="admin")
    password = serializers.CharField(
        max_length=255, write_only=True, required=False, allow_blank=True
    )
    use_ssl = serializers.BooleanField(default=False)


class RouterConfigSerializer(serializers.Serializer):
    """Serializer for saving router configuration"""

    name = serializers.CharField(max_length=100)
    host = serializers.CharField(max_length=255)
    port = serializers.IntegerField(default=8728, min_value=1, max_value=65535)
    username = serializers.CharField(max_length=100, default="admin")
    password = serializers.CharField(
        max_length=255, write_only=True, required=False, allow_blank=True
    )
    use_ssl = serializers.BooleanField(default=False)
    location_id = serializers.IntegerField(required=False, allow_null=True)
    hotspot_interface = serializers.CharField(max_length=50, default="bridge")
    hotspot_profile = serializers.CharField(max_length=50, default="default")
    description = serializers.CharField(required=False, allow_blank=True)


class HotspotAutoConfigSerializer(serializers.Serializer):
    """Serializer for hotspot auto-configuration"""

    router_id = serializers.IntegerField()
    interface = serializers.CharField(max_length=50, default="bridge")
    server_name = serializers.CharField(max_length=50, default="kitonga-hotspot")
    profile_name = serializers.CharField(max_length=50, default="kitonga-profile")


class BrandingUpdateSerializer(serializers.Serializer):
    """Serializer for updating tenant branding"""

    primary_color = serializers.RegexField(
        regex=r"^#[0-9A-Fa-f]{6}$",
        required=False,
        error_messages={"invalid": "Color must be in hex format (e.g., #3B82F6)"},
    )
    secondary_color = serializers.RegexField(
        regex=r"^#[0-9A-Fa-f]{6}$",
        required=False,
        error_messages={"invalid": "Color must be in hex format (e.g., #1E40AF)"},
    )
    business_name = serializers.CharField(max_length=200, required=False)


class CustomDomainSerializer(serializers.Serializer):
    """Serializer for custom domain configuration"""

    domain = serializers.RegexField(
        regex=r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$",
        error_messages={"invalid": "Invalid domain format"},
    )


class AnalyticsQuerySerializer(serializers.Serializer):
    """Serializer for analytics query parameters"""

    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=["hour", "day", "week", "month"], default="day", required=False
    )


class ExportRequestSerializer(serializers.Serializer):
    """Serializer for data export requests"""

    export_type = serializers.ChoiceField(choices=["payments", "users", "vouchers"])
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    format = serializers.ChoiceField(
        choices=["csv", "json"], default="csv", required=False
    )
    batch_id = serializers.CharField(max_length=50, required=False, allow_blank=True)


class TenantSettingsSerializer(serializers.ModelSerializer):
    """Serializer for tenant settings update"""

    class Meta:
        model = Tenant
        fields = [
            "business_name",
            "business_email",
            "business_phone",
            "business_address",
            "timezone",
            "primary_color",
            "secondary_color",
            "nextsms_username",
            "nextsms_password",
            "nextsms_sender_id",
            "clickpesa_client_id",
            "clickpesa_api_key",
        ]
        extra_kwargs = {
            "nextsms_password": {"write_only": True},
            "clickpesa_api_key": {"write_only": True},
        }


class StaffInviteSerializer(serializers.Serializer):
    """Serializer for inviting new staff members"""

    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=100, required=False)
    last_name = serializers.CharField(max_length=100, required=False)
    role = serializers.ChoiceField(
        choices=["admin", "manager", "support", "viewer"], default="support"
    )
    can_manage_routers = serializers.BooleanField(default=False)
    can_manage_users = serializers.BooleanField(default=True)
    can_manage_payments = serializers.BooleanField(default=True)
    can_manage_vouchers = serializers.BooleanField(default=True)
    can_view_reports = serializers.BooleanField(default=True)
    can_manage_staff = serializers.BooleanField(default=False)
    can_manage_settings = serializers.BooleanField(default=False)


class StaffUpdateSerializer(serializers.Serializer):
    """Serializer for updating staff permissions"""

    role = serializers.ChoiceField(
        choices=["admin", "manager", "support", "viewer"], required=False
    )
    can_manage_routers = serializers.BooleanField(required=False)
    can_manage_users = serializers.BooleanField(required=False)
    can_manage_payments = serializers.BooleanField(required=False)
    can_manage_vouchers = serializers.BooleanField(required=False)
    can_view_reports = serializers.BooleanField(required=False)
    can_manage_staff = serializers.BooleanField(required=False)
    can_manage_settings = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)


class DashboardSummarySerializer(serializers.Serializer):
    """Serializer for dashboard summary response"""

    overview = serializers.DictField()
    today = serializers.DictField()
    this_week = serializers.DictField()
    this_month = serializers.DictField()
    active_users = serializers.DictField()
    revenue_trend = serializers.ListField()
    top_bundles = serializers.ListField()
    device_breakdown = serializers.DictField()
    router_status = serializers.ListField()


# =============================================================================
# TENANT AUTHENTICATION SERIALIZERS
# =============================================================================


class EmailOTPVerifySerializer(serializers.Serializer):
    """Serializer for verifying email OTP"""

    email = serializers.EmailField()
    otp_code = serializers.CharField(min_length=6, max_length=6)

    def validate_otp_code(self, value):
        # Ensure OTP is numeric
        if not value.isdigit():
            raise serializers.ValidationError("OTP must be 6 digits")
        return value


class ResendOTPSerializer(serializers.Serializer):
    """Serializer for resending OTP"""

    email = serializers.EmailField()
    purpose = serializers.ChoiceField(
        choices=["registration", "password_reset", "login"], default="registration"
    )


class TenantLoginSerializer(serializers.Serializer):
    """Serializer for tenant login"""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class TenantPasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request"""

    email = serializers.EmailField()


class TenantPasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for password reset confirmation"""

    email = serializers.EmailField()
    otp_code = serializers.CharField(min_length=6, max_length=6)
    new_password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(min_length=8, write_only=True)

    def validate(self, data):
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match"}
            )
        return data

    def validate_otp_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must be 6 digits")
        return value


class TenantChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing password (authenticated)"""

    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(min_length=8, write_only=True)

    def validate(self, data):
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match"}
            )
        return data


class ContactFormSerializer(serializers.Serializer):
    """Serializer for contact form submissions"""

    SUBJECT_CHOICES = [
        ("general", "General Inquiry"),
        ("sales", "Sales Inquiry"),
        ("support", "Technical Support"),
        ("partnership", "Partnership Opportunity"),
        ("demo", "Request Demo"),
        ("other", "Other"),
    ]

    name = serializers.CharField(max_length=200, min_length=2)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    subject = serializers.ChoiceField(choices=SUBJECT_CHOICES, default="general")
    message = serializers.CharField(min_length=10, max_length=5000)

    def validate_name(self, value):
        # Basic name validation - at least 2 characters
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Please enter your full name")
        return value.strip()

    def validate_phone(self, value):
        if value:
            # Remove spaces and dashes for validation
            cleaned = value.replace(" ", "").replace("-", "").replace("+", "")
            if not cleaned.isdigit():
                raise serializers.ValidationError("Please enter a valid phone number")
        return value

    def validate_message(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError(
                "Please provide more details in your message"
            )
        return value.strip()


# =============================================================================
# TENANT SMS BROADCAST SERIALIZERS
# =============================================================================


class TenantSMSConfigSerializer(serializers.Serializer):
    """Serializer for tenant SMS configuration"""

    nextsms_username = serializers.CharField(max_length=255, required=True)
    nextsms_password = serializers.CharField(
        max_length=255, required=True, write_only=True
    )
    nextsms_sender_id = serializers.CharField(
        max_length=11, required=False, allow_blank=True
    )
    nextsms_base_url = serializers.URLField(required=False, allow_blank=True)

    def validate_nextsms_sender_id(self, value):
        if value and len(value) > 11:
            raise serializers.ValidationError("Sender ID must be 11 characters or less")
        return value


class TenantSMSBroadcastCreateSerializer(serializers.Serializer):
    """Serializer for creating tenant SMS broadcast"""

    TARGET_TYPE_CHOICES = [
        ("all_users", "All My WiFi Users"),
        ("active_users", "Active Users Only"),
        ("expired_users", "Expired Users"),
        ("expiring_soon", "Expiring Within 24 Hours"),
        ("custom", "Custom Phone Numbers"),
    ]

    title = serializers.CharField(max_length=200)
    message = serializers.CharField(max_length=320)
    target_type = serializers.ChoiceField(
        choices=TARGET_TYPE_CHOICES, default="all_users"
    )
    custom_recipients = serializers.ListField(
        child=serializers.CharField(max_length=15), required=False, allow_empty=True
    )
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_message(self, value):
        if len(value.strip()) < 5:
            raise serializers.ValidationError("Message must be at least 5 characters")
        if len(value) > 320:
            raise serializers.ValidationError(
                "Message must be 320 characters or less (2 SMS max)"
            )
        return value.strip()

    def validate(self, data):
        if data.get("target_type") == "custom":
            recipients = data.get("custom_recipients", [])
            if not recipients:
                raise serializers.ValidationError(
                    {
                        "custom_recipients": 'Custom recipients are required when target_type is "custom"'
                    }
                )
        return data


class TenantSMSBroadcastSerializer(serializers.Serializer):
    """Serializer for tenant SMS broadcast response"""

    id = serializers.UUIDField(read_only=True)
    title = serializers.CharField()
    message = serializers.CharField()
    target_type = serializers.CharField()
    status = serializers.CharField()
    total_recipients = serializers.IntegerField()
    sent_count = serializers.IntegerField()
    failed_count = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    scheduled_at = serializers.DateTimeField(allow_null=True)
    started_at = serializers.DateTimeField(allow_null=True)
    completed_at = serializers.DateTimeField(allow_null=True)
    error_message = serializers.CharField(allow_blank=True)


class TenantSendSingleSMSSerializer(serializers.Serializer):
    """Serializer for sending a single SMS"""

    phone_number = serializers.CharField(max_length=15)
    message = serializers.CharField(max_length=320)

    def validate_phone_number(self, value):
        return validate_phone_number_field(value)

    def validate_message(self, value):
        if len(value.strip()) < 5:
            raise serializers.ValidationError("Message must be at least 5 characters")
        return value.strip()


# =============================================================================
# AUTO SMS CAMPAIGN SERIALIZERS (Business/Enterprise)
# =============================================================================


class AutoSMSCampaignSerializer(serializers.Serializer):
    """Serializer for Auto SMS Campaign"""

    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(allow_blank=True, required=False)

    trigger_type = serializers.ChoiceField(
        choices=[
            ("new_user", "New User Registration"),
            ("payment_success", "Successful Payment"),
            ("payment_failed", "Failed Payment"),
            ("access_expiring", "Access Expiring Soon"),
            ("access_expired", "Access Expired"),
            ("voucher_redeemed", "Voucher Redeemed"),
            ("scheduled", "Scheduled (One-time)"),
            ("recurring_daily", "Daily Recurring"),
            ("recurring_weekly", "Weekly Recurring"),
            ("recurring_monthly", "Monthly Recurring"),
        ]
    )

    hours_before_expiry = serializers.IntegerField(
        default=24, min_value=1, max_value=168
    )
    scheduled_time = serializers.TimeField(required=False, allow_null=True)
    scheduled_date = serializers.DateField(required=False, allow_null=True)
    day_of_week = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=6
    )
    day_of_month = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=28
    )

    message_template = serializers.CharField(max_length=320)

    target_all_users = serializers.BooleanField(default=True)
    target_active_only = serializers.BooleanField(default=False)
    target_expired_only = serializers.BooleanField(default=False)

    status = serializers.ChoiceField(
        choices=[("active", "Active"), ("paused", "Paused"), ("draft", "Draft")],
        default="draft",
    )

    # Read-only stats
    total_sent = serializers.IntegerField(read_only=True)
    total_failed = serializers.IntegerField(read_only=True)
    last_triggered_at = serializers.DateTimeField(read_only=True, allow_null=True)
    next_run_at = serializers.DateTimeField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)

    def validate_message_template(self, value):
        if len(value.strip()) < 5:
            raise serializers.ValidationError(
                "Message template must be at least 5 characters"
            )
        return value.strip()


class AutoSMSCampaignCreateSerializer(serializers.Serializer):
    """Serializer for creating Auto SMS Campaign"""

    name = serializers.CharField(max_length=200)
    description = serializers.CharField(allow_blank=True, required=False, default="")
    trigger_type = serializers.ChoiceField(
        choices=[
            ("new_user", "New User Registration"),
            ("payment_success", "Successful Payment"),
            ("payment_failed", "Failed Payment"),
            ("access_expiring", "Access Expiring Soon"),
            ("access_expired", "Access Expired"),
            ("voucher_redeemed", "Voucher Redeemed"),
            ("scheduled", "Scheduled (One-time)"),
            ("recurring_daily", "Daily Recurring"),
            ("recurring_weekly", "Weekly Recurring"),
            ("recurring_monthly", "Monthly Recurring"),
        ]
    )

    hours_before_expiry = serializers.IntegerField(
        default=24, min_value=1, max_value=168
    )
    scheduled_time = serializers.TimeField(required=False, allow_null=True)
    scheduled_date = serializers.DateField(required=False, allow_null=True)
    day_of_week = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=6
    )
    day_of_month = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=28
    )

    message_template = serializers.CharField(max_length=320)

    target_all_users = serializers.BooleanField(default=True)
    target_active_only = serializers.BooleanField(default=False)
    target_expired_only = serializers.BooleanField(default=False)

    def validate(self, data):
        trigger_type = data.get("trigger_type")

        # Validate scheduled campaigns have required fields
        if trigger_type == "scheduled":
            if not data.get("scheduled_date") or not data.get("scheduled_time"):
                raise serializers.ValidationError(
                    {
                        "scheduled_date": "Date and time are required for scheduled campaigns"
                    }
                )

        if trigger_type == "recurring_weekly":
            if data.get("day_of_week") is None:
                raise serializers.ValidationError(
                    {
                        "day_of_week": "Day of week (0-6) is required for weekly campaigns"
                    }
                )

        if trigger_type == "recurring_monthly":
            if not data.get("day_of_month"):
                raise serializers.ValidationError(
                    {
                        "day_of_month": "Day of month (1-28) is required for monthly campaigns"
                    }
                )

        if trigger_type in ["recurring_daily", "recurring_weekly", "recurring_monthly"]:
            if not data.get("scheduled_time"):
                raise serializers.ValidationError(
                    {"scheduled_time": "Time is required for recurring campaigns"}
                )

        return data


# =============================================================================
# WEBHOOK SERIALIZERS (Business/Enterprise)
# =============================================================================


class TenantWebhookSerializer(serializers.Serializer):
    """Serializer for Tenant Webhook"""

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
    ]

    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(max_length=100)
    url = serializers.URLField(max_length=500)

    secret_key = serializers.CharField(read_only=True)
    auth_header = serializers.CharField(
        max_length=255, allow_blank=True, required=False
    )

    events = serializers.ListField(
        child=serializers.ChoiceField(choices=[e[0] for e in EVENT_CHOICES]),
        min_length=1,
    )

    status = serializers.ChoiceField(
        choices=[("active", "Active"), ("paused", "Paused")],
        default="active",
        read_only=True,
    )
    is_active = serializers.BooleanField(default=True)

    # Health stats (read-only)
    consecutive_failures = serializers.IntegerField(read_only=True)
    last_success_at = serializers.DateTimeField(read_only=True, allow_null=True)
    last_failure_at = serializers.DateTimeField(read_only=True, allow_null=True)
    last_failure_reason = serializers.CharField(read_only=True, allow_blank=True)

    created_at = serializers.DateTimeField(read_only=True)

    def validate_url(self, value):
        if not value.startswith("https://"):
            raise serializers.ValidationError("Webhook URL must use HTTPS")
        return value


class TenantWebhookCreateSerializer(serializers.Serializer):
    """Serializer for creating Tenant Webhook"""

    name = serializers.CharField(max_length=100)
    url = serializers.URLField(max_length=500)
    auth_header = serializers.CharField(
        max_length=255, allow_blank=True, required=False, default=""
    )
    events = serializers.ListField(
        child=serializers.CharField(max_length=50), min_length=1
    )

    def validate_url(self, value):
        if not value.startswith("https://"):
            raise serializers.ValidationError("Webhook URL must use HTTPS")
        return value

    def validate_events(self, value):
        valid_events = [
            "payment.success",
            "payment.failed",
            "user.created",
            "user.expired",
            "user.activated",
            "voucher.redeemed",
            "voucher.created",
            "router.online",
            "router.offline",
        ]
        for event in value:
            if event not in valid_events:
                raise serializers.ValidationError(f"Invalid event type: {event}")
        return value


class WebhookDeliverySerializer(serializers.Serializer):
    """Serializer for Webhook Delivery logs"""

    id = serializers.IntegerField(read_only=True)
    event_type = serializers.CharField()
    event_id = serializers.UUIDField()
    status = serializers.CharField()
    attempts = serializers.IntegerField()
    response_status_code = serializers.IntegerField(allow_null=True)
    response_time_ms = serializers.IntegerField(allow_null=True)
    error_message = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()
    delivered_at = serializers.DateTimeField(allow_null=True)


# =============================================================================
# ANALYTICS SERIALIZERS (Business/Enterprise)
# =============================================================================


class AnalyticsSnapshotSerializer(serializers.Serializer):
    """Serializer for Analytics Snapshot"""

    date = serializers.DateField()

    # User Metrics
    total_users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    new_users = serializers.IntegerField()
    expired_users = serializers.IntegerField()

    # Revenue Metrics
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_count = serializers.IntegerField()
    avg_payment_amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    # Voucher Metrics
    vouchers_generated = serializers.IntegerField()
    vouchers_redeemed = serializers.IntegerField()

    # Device Metrics
    total_devices = serializers.IntegerField()
    unique_devices_connected = serializers.IntegerField()

    # Breakdowns
    bundle_breakdown = serializers.JSONField()
    payment_channel_breakdown = serializers.JSONField()


class AnalyticsTrendSerializer(serializers.Serializer):
    """Serializer for Analytics Trend data"""

    period = serializers.CharField()  # daily, weekly, monthly
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    # Trend data points
    dates = serializers.ListField(child=serializers.DateField())
    revenue = serializers.ListField(
        child=serializers.DecimalField(max_digits=12, decimal_places=2)
    )
    users = serializers.ListField(child=serializers.IntegerField())
    payments = serializers.ListField(child=serializers.IntegerField())

    # Summary
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_users = serializers.IntegerField()
    total_payments = serializers.IntegerField()

    # Growth rates
    revenue_growth_percent = serializers.DecimalField(
        max_digits=6, decimal_places=2, allow_null=True
    )
    user_growth_percent = serializers.DecimalField(
        max_digits=6, decimal_places=2, allow_null=True
    )


# =============================================================================
# PPP (Point-to-Point Protocol) SERIALIZERS — Enterprise Plan
# =============================================================================


class PPPProfileSerializer(serializers.ModelSerializer):
    """Serializer for PPP Profile (read)"""

    customer_count = serializers.SerializerMethodField()

    class Meta:
        model = PPPProfile
        fields = [
            "id",
            "router",
            "name",
            "rate_limit",
            "local_address",
            "remote_address",
            "dns_server",
            "service_type",
            "session_timeout",
            "idle_timeout",
            "address_pool",
            "monthly_price",
            "is_active",
            "synced_to_router",
            "mikrotik_id",
            "customer_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "synced_to_router",
            "mikrotik_id",
            "created_at",
            "updated_at",
        ]

    def get_customer_count(self, obj):
        return obj.customers.count()


class PPPProfileCreateSerializer(serializers.Serializer):
    """Serializer for creating / updating a PPP Profile"""

    router_id = serializers.IntegerField()
    name = serializers.CharField(max_length=100)
    rate_limit = serializers.CharField(max_length=100, required=False, default="")
    local_address = serializers.IPAddressField(required=False, allow_null=True)
    remote_address = serializers.CharField(max_length=100, required=False, default="")
    dns_server = serializers.CharField(max_length=255, required=False, default="")
    service_type = serializers.ChoiceField(
        choices=["pppoe", "l2tp", "pptp", "any"], default="pppoe"
    )
    session_timeout = serializers.CharField(max_length=20, required=False, default="")
    idle_timeout = serializers.CharField(max_length=20, required=False, default="")
    address_pool = serializers.CharField(max_length=100, required=False, default="")
    monthly_price = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = serializers.BooleanField(default=True)
    sync_to_router = serializers.BooleanField(
        default=False,
        help_text="If true, immediately push profile to MikroTik router",
    )


# ---- PPP PLANS ----


class PPPPlanSerializer(serializers.ModelSerializer):
    """Serializer for PPP Plan (read)"""

    profile_name = serializers.CharField(source="profile.name", read_only=True)
    profile_rate_limit = serializers.CharField(
        source="profile.rate_limit", read_only=True
    )
    router_name = serializers.CharField(source="profile.router.name", read_only=True)
    effective_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    speed_display = serializers.CharField(read_only=True)
    data_display = serializers.CharField(read_only=True)
    customer_count = serializers.IntegerField(read_only=True)
    price_per_day = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = PPPPlan
        fields = [
            "id",
            "profile",
            "profile_name",
            "profile_rate_limit",
            "router_name",
            "name",
            "description",
            "price",
            "currency",
            "billing_cycle",
            "billing_days",
            "data_limit_gb",
            "download_speed",
            "upload_speed",
            "speed_display",
            "data_display",
            "features",
            "display_order",
            "is_popular",
            "is_active",
            "promo_price",
            "promo_label",
            "effective_price",
            "price_per_day",
            "customer_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class PPPPlanCreateSerializer(serializers.Serializer):
    """Serializer for creating / updating a PPP Plan"""

    profile_id = serializers.IntegerField(
        help_text="ID of the PPPProfile (speed tier) this plan uses"
    )
    name = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, default="")
    price = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField(max_length=3, required=False, default="TZS")
    billing_cycle = serializers.ChoiceField(
        choices=[
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "biannual",
            "annual",
            "custom",
        ],
        default="monthly",
    )
    billing_days = serializers.IntegerField(required=False, default=30)
    data_limit_gb = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    download_speed = serializers.CharField(max_length=20, required=False, default="")
    upload_speed = serializers.CharField(max_length=20, required=False, default="")
    features = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    display_order = serializers.IntegerField(required=False, default=0)
    is_popular = serializers.BooleanField(required=False, default=False)
    is_active = serializers.BooleanField(required=False, default=True)
    promo_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    promo_label = serializers.CharField(max_length=50, required=False, default="")


class PPPCustomerSerializer(serializers.ModelSerializer):
    """Serializer for PPP Customer (read)"""

    profile_name = serializers.CharField(source="profile.name", read_only=True)
    profile_rate_limit = serializers.CharField(
        source="profile.rate_limit", read_only=True
    )
    router_name = serializers.CharField(source="router.name", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True, default=None)
    plan_billing_cycle = serializers.CharField(
        source="plan.billing_cycle", read_only=True, default=None
    )
    effective_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = PPPCustomer
        fields = [
            "id",
            "router",
            "router_name",
            "profile",
            "profile_name",
            "profile_rate_limit",
            "plan",
            "plan_name",
            "plan_billing_cycle",
            "username",
            "service",
            "full_name",
            "phone_number",
            "email",
            "address",
            "static_ip",
            "mac_address",
            "caller_id",
            "billing_type",
            "monthly_price",
            "effective_price",
            "paid_until",
            "last_payment_date",
            "last_payment_amount",
            "status",
            "comment",
            "synced_to_router",
            "mikrotik_id",
            "is_expired",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "synced_to_router",
            "mikrotik_id",
            "last_payment_date",
            "last_payment_amount",
            "created_at",
            "updated_at",
        ]


class PPPCustomerCreateSerializer(serializers.Serializer):
    """Serializer for creating / updating a PPP Customer"""

    router_id = serializers.IntegerField()
    profile_id = serializers.IntegerField()
    plan_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="PPP Plan ID (optional). If set, billing_type and price are derived from the plan.",
    )
    username = serializers.CharField(max_length=100)
    password = serializers.CharField(max_length=255)
    service = serializers.CharField(max_length=50, required=False, default="")

    # Customer info
    full_name = serializers.CharField(max_length=200, required=False, default="")
    phone_number = serializers.CharField(max_length=20, required=False, default="")
    email = serializers.EmailField(required=False, default="")
    address = serializers.CharField(required=False, default="")

    # IP & access control
    static_ip = serializers.IPAddressField(required=False, allow_null=True)
    mac_address = serializers.CharField(max_length=17, required=False, default="")
    caller_id = serializers.CharField(max_length=100, required=False, default="")

    # Billing
    billing_type = serializers.ChoiceField(
        choices=["monthly", "prepaid", "unlimited"], default="monthly"
    )
    monthly_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    paid_until = serializers.DateTimeField(required=False, allow_null=True)

    # Notes
    comment = serializers.CharField(required=False, default="")

    # Sync option
    sync_to_router = serializers.BooleanField(
        default=False,
        help_text="If true, immediately push secret to MikroTik router",
    )
