"""
Serializers for API requests and responses
"""
from rest_framework import serializers
from .models import (
    User, Payment, AccessLog, Voucher, Bundle, Device,
    SubscriptionPlan, Tenant, TenantStaff, TenantSubscriptionPayment, Router, Location
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
            raise serializers.ValidationError(f"Invalid Tanzania phone number: {phone_number}")
        
        return normalized
        
    except ValueError as e:
        raise serializers.ValidationError(f"Invalid phone number format: {e}")


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ['id', 'mac_address', 'ip_address', 'device_name', 'is_active', 
                  'first_seen', 'last_seen']
        read_only_fields = ['id', 'first_seen', 'last_seen']


class BundleSerializer(serializers.ModelSerializer):
    duration_days = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Bundle
        fields = ['id', 'name', 'duration_hours', 'duration_days', 'price', 
                  'description', 'is_active', 'display_order']
        read_only_fields = ['id']


class UserSerializer(serializers.ModelSerializer):
    has_active_access = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()
    active_devices = serializers.SerializerMethodField()
    device_limit_reached = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'phone_number', 'paid_until', 'is_active', 
                  'has_active_access', 'time_remaining', 'total_payments', 
                  'max_devices', 'active_devices', 'device_limit_reached', 'created_at'
                 ]
        read_only_fields = ['id', 'created_at', 'total_payments']
    
    def get_has_active_access(self, obj):
        return obj.has_active_access()
    
    def get_time_remaining(self, obj):
        if obj.has_active_access():
            from django.utils import timezone
            remaining = obj.paid_until - timezone.now()
            return {
                'hours': int(remaining.total_seconds() // 3600),
                'minutes': int((remaining.total_seconds() % 3600) // 60)
            }
        return None
    
    def get_active_devices(self, obj):
        return obj.get_active_devices().count()
    
    def get_device_limit_reached(self, obj):
        return not obj.can_add_device()


class PaymentSerializer(serializers.ModelSerializer):
    bundle_name = serializers.CharField(source='bundle.name', read_only=True)
    
    class Meta:
        model = Payment
        fields = ['id', 'amount', 'phone_number', 'payment_reference', 
                  'transaction_id', 'order_reference', 'payment_channel',
                  'bundle', 'bundle_name', 'status', 'created_at', 'completed_at']
        read_only_fields = ['id', 'created_at', 'completed_at', 'payment_reference']


class InitiatePaymentSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    bundle_id = serializers.IntegerField(required=False)
    
    def validate_phone_number(self, value):
        """Validate and normalize phone number"""
        return validate_phone_number_field(value)
    
    def validate_bundle_id(self, value):
        if value is not None:
            from .models import Bundle
            try:
                Bundle.objects.get(id=value, is_active=True)
            except Bundle.DoesNotExist:
                raise serializers.ValidationError('Invalid bundle selected')
        return value


class VerifyAccessSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    ip_address = serializers.IPAddressField(required=False)
    mac_address = serializers.CharField(max_length=17, required=False)
    router_id = serializers.IntegerField(required=False, allow_null=True, help_text="Router ID for specific router authorization")
    
    def validate_phone_number(self, value):
        """Validate and normalize phone number"""
        return validate_phone_number_field(value)


class VoucherSerializer(serializers.ModelSerializer):
    used_by_phone = serializers.CharField(source='used_by.phone_number', read_only=True)
    duration_display = serializers.CharField(source='get_duration_hours_display', read_only=True)
    
    class Meta:
        model = Voucher
        fields = ['id', 'code', 'duration_hours', 'duration_display', 'is_used', 
                  'created_at', 'created_by', 'used_at', 'used_by_phone', 
                  'batch_id', 'notes']
        read_only_fields = ['id', 'code', 'is_used', 'created_at', 'used_at', 'used_by_phone']


class GenerateVouchersSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=1000)
    duration_hours = serializers.ChoiceField(choices=[24, 168, 720])
    batch_id = serializers.CharField(max_length=50, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)
    admin_phone_number = serializers.CharField(max_length=15, required=True)
    language = serializers.ChoiceField(choices=['en', 'sw'], default='en', required=False)
    
    def validate_admin_phone_number(self, value):
        """Validate and normalize admin phone number"""
        return validate_phone_number_field(value)


class RedeemVoucherSerializer(serializers.Serializer):
    voucher_code = serializers.CharField(max_length=16)
    phone_number = serializers.CharField(max_length=15)
    # Optional device information for immediate access setup
    ip_address = serializers.IPAddressField(required=False)
    mac_address = serializers.CharField(max_length=17, required=False)
    
    def validate_voucher_code(self, value):
        # Remove extra spaces and convert to uppercase, but preserve the original format
        value = value.strip().upper()
        
        # Don't modify the voucher code format - use it as provided
        # Just clean up any extra whitespace
        value = ' '.join(value.split())
        
        return value
    
    def validate_phone_number(self, value):
        """Validate and normalize phone number"""
        return validate_phone_number_field(value)
    
    def validate_mac_address(self, value):
        if value:
            # Basic MAC address format validation
            import re
            if not re.match(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', value):
                raise serializers.ValidationError('Invalid MAC address format')
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
            'id', 'name', 'display_name', 'description',
            'monthly_price', 'yearly_price', 'currency',
            'max_routers', 'max_wifi_users', 'max_vouchers_per_month',
            'max_locations', 'max_staff_accounts',
            'features', 'revenue_share_percentage', 'is_active'
        ]
    
    def get_features(self, obj):
        return {
            'custom_branding': obj.custom_branding,
            'custom_domain': obj.custom_domain,
            'api_access': obj.api_access,
            'white_label': obj.white_label,
            'priority_support': obj.priority_support,
            'analytics_dashboard': obj.analytics_dashboard,
            'sms_notifications': obj.sms_notifications,
        }


class TenantSerializer(serializers.ModelSerializer):
    """Serializer for tenant details"""
    subscription_plan_name = serializers.CharField(source='subscription_plan.display_name', read_only=True)
    subscription_valid = serializers.SerializerMethodField()
    usage_stats = serializers.SerializerMethodField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'slug', 'business_name', 'business_email', 'business_phone',
            'business_address', 'country', 'timezone',
            'subscription_plan', 'subscription_plan_name', 'subscription_status',
            'subscription_started_at', 'subscription_ends_at', 'billing_cycle',
            'trial_ends_at', 'subscription_valid',
            'logo', 'primary_color', 'secondary_color', 'custom_domain',
            'usage_stats', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'slug', 'api_key', 'created_at']
    
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
            raise serializers.ValidationError("An account with this email already exists")
        return value


class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    """Serializer for subscription payment records"""
    plan_name = serializers.CharField(source='plan.display_name', read_only=True)
    
    class Meta:
        model = TenantSubscriptionPayment
        fields = [
            'id', 'tenant', 'plan', 'plan_name', 'amount', 'currency',
            'billing_cycle', 'transaction_id', 'payment_reference',
            'payment_method', 'status', 'period_start', 'period_end',
            'created_at', 'completed_at'
        ]
        read_only_fields = ['id', 'created_at', 'completed_at', 'transaction_id']


class CreateSubscriptionPaymentSerializer(serializers.Serializer):
    """Serializer for creating a subscription payment"""
    plan_id = serializers.IntegerField()
    billing_cycle = serializers.ChoiceField(choices=['monthly', 'yearly'], default='monthly')
    
    def validate_plan_id(self, value):
        try:
            SubscriptionPlan.objects.get(id=value, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError("Invalid subscription plan")
        return value


class RouterSerializer(serializers.ModelSerializer):
    """Serializer for router configuration"""
    location_name = serializers.CharField(source='location.name', read_only=True)
    
    class Meta:
        model = Router
        fields = [
            'id', 'name', 'description', 'location', 'location_name', 'host', 'port',
            'username', 'password', 'use_ssl', 'hotspot_interface', 'hotspot_profile',
            'router_model', 'router_version', 'router_identity',
            'status', 'is_active', 'last_seen', 'last_error', 'created_at'
        ]
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
            'router_model': {'read_only': True},
            'router_version': {'read_only': True},
            'router_identity': {'read_only': True},
            'status': {'read_only': True},
            'last_seen': {'read_only': True},
            'last_error': {'read_only': True},
            'created_at': {'read_only': True},
        }


class LocationSerializer(serializers.ModelSerializer):
    """Serializer for tenant locations"""
    router_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Location
        fields = [
            'id', 'name', 'address', 'city', 'manager_name', 'manager_phone',
            'is_active', 'router_count', 'created_at'
        ]
    
    def get_router_count(self, obj):
        return obj.routers.filter(is_active=True).count()


class TenantStaffSerializer(serializers.ModelSerializer):
    """Serializer for tenant staff members"""
    email = serializers.CharField(source='user.email', read_only=True)
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantStaff
        fields = [
            'id', 'user', 'email', 'full_name', 'role',
            'can_manage_routers', 'can_manage_users', 'can_manage_payments',
            'can_manage_vouchers', 'can_view_reports', 'can_manage_staff',
            'can_manage_settings', 'is_active', 'invited_at', 'joined_at'
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
    username = serializers.CharField(max_length=100, default='admin')
    password = serializers.CharField(max_length=255, write_only=True, required=False, allow_blank=True)
    use_ssl = serializers.BooleanField(default=False)


class RouterConfigSerializer(serializers.Serializer):
    """Serializer for saving router configuration"""
    name = serializers.CharField(max_length=100)
    host = serializers.CharField(max_length=255)
    port = serializers.IntegerField(default=8728, min_value=1, max_value=65535)
    username = serializers.CharField(max_length=100, default='admin')
    password = serializers.CharField(max_length=255, write_only=True, required=False, allow_blank=True)
    use_ssl = serializers.BooleanField(default=False)
    location_id = serializers.IntegerField(required=False, allow_null=True)
    hotspot_interface = serializers.CharField(max_length=50, default='bridge')
    hotspot_profile = serializers.CharField(max_length=50, default='default')
    description = serializers.CharField(required=False, allow_blank=True)


class HotspotAutoConfigSerializer(serializers.Serializer):
    """Serializer for hotspot auto-configuration"""
    router_id = serializers.IntegerField()
    interface = serializers.CharField(max_length=50, default='bridge')
    server_name = serializers.CharField(max_length=50, default='kitonga-hotspot')
    profile_name = serializers.CharField(max_length=50, default='kitonga-profile')


class BrandingUpdateSerializer(serializers.Serializer):
    """Serializer for updating tenant branding"""
    primary_color = serializers.RegexField(
        regex=r'^#[0-9A-Fa-f]{6}$',
        required=False,
        error_messages={'invalid': 'Color must be in hex format (e.g., #3B82F6)'}
    )
    secondary_color = serializers.RegexField(
        regex=r'^#[0-9A-Fa-f]{6}$',
        required=False,
        error_messages={'invalid': 'Color must be in hex format (e.g., #1E40AF)'}
    )
    business_name = serializers.CharField(max_length=200, required=False)


class CustomDomainSerializer(serializers.Serializer):
    """Serializer for custom domain configuration"""
    domain = serializers.RegexField(
        regex=r'^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$',
        error_messages={'invalid': 'Invalid domain format'}
    )


class AnalyticsQuerySerializer(serializers.Serializer):
    """Serializer for analytics query parameters"""
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=['hour', 'day', 'week', 'month'],
        default='day',
        required=False
    )


class ExportRequestSerializer(serializers.Serializer):
    """Serializer for data export requests"""
    export_type = serializers.ChoiceField(
        choices=['payments', 'users', 'vouchers']
    )
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    format = serializers.ChoiceField(
        choices=['csv', 'json'],
        default='csv',
        required=False
    )
    batch_id = serializers.CharField(max_length=50, required=False, allow_blank=True)


class TenantSettingsSerializer(serializers.ModelSerializer):
    """Serializer for tenant settings update"""
    
    class Meta:
        model = Tenant
        fields = [
            'business_name', 'business_email', 'business_phone',
            'business_address', 'timezone',
            'primary_color', 'secondary_color',
            'nextsms_username', 'nextsms_password', 'nextsms_sender_id',
            'clickpesa_client_id', 'clickpesa_api_key',
        ]
        extra_kwargs = {
            'nextsms_password': {'write_only': True},
            'clickpesa_api_key': {'write_only': True},
        }


class StaffInviteSerializer(serializers.Serializer):
    """Serializer for inviting new staff members"""
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=100, required=False)
    last_name = serializers.CharField(max_length=100, required=False)
    role = serializers.ChoiceField(
        choices=['admin', 'manager', 'support', 'viewer'],
        default='support'
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
        choices=['admin', 'manager', 'support', 'viewer'],
        required=False
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
        choices=['registration', 'password_reset', 'login'],
        default='registration'
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
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'Passwords do not match'
            })
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
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'Passwords do not match'
            })
        return data


class ContactFormSerializer(serializers.Serializer):
    """Serializer for contact form submissions"""
    SUBJECT_CHOICES = [
        ('general', 'General Inquiry'),
        ('sales', 'Sales Inquiry'),
        ('support', 'Technical Support'),
        ('partnership', 'Partnership Opportunity'),
        ('demo', 'Request Demo'),
        ('other', 'Other'),
    ]
    
    name = serializers.CharField(max_length=200, min_length=2)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    subject = serializers.ChoiceField(choices=SUBJECT_CHOICES, default='general')
    message = serializers.CharField(min_length=10, max_length=5000)
    
    def validate_name(self, value):
        # Basic name validation - at least 2 characters
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Please enter your full name")
        return value.strip()
    
    def validate_phone(self, value):
        if value:
            # Remove spaces and dashes for validation
            cleaned = value.replace(' ', '').replace('-', '').replace('+', '')
            if not cleaned.isdigit():
                raise serializers.ValidationError("Please enter a valid phone number")
        return value
    
    def validate_message(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError("Please provide more details in your message")
        return value.strip()
