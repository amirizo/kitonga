"""
Django admin configuration for Kitonga Wi-Fi SaaS Platform with Jazzmin
Includes multi-tenant management and existing WiFi billing models
"""

from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html
from django.utils import timezone
import csv
from .models import (
    # SaaS Models
    SubscriptionPlan,
    Tenant,
    TenantStaff,
    Location,
    Router,
    TenantSubscriptionPayment,
    # Router Monitoring
    RouterMonitoringSnapshot,
    RouterBandwidthLog,
    RouterHotspotCustomization,
    # WiFi Billing Models (now multi-tenant)
    User,
    Payment,
    AccessLog,
    Voucher,
    Bundle,
    Device,
    SMSLog,
    PaymentWebhook,
    # SMS Broadcast
    SMSBroadcast,
    TenantSMSBroadcast,
    # Premium Features
    AutoSMSCampaign,
    TenantWebhook,
    WebhookDelivery,
    TenantAnalyticsSnapshot,
    AutoSMSLog,
    # Contact & Support
    ContactSubmission,
    # PPP Models
    PPPProfile,
    PPPPlan,
    PPPCustomer,
    PPPPayment,
    # Remote Access (VPN) Models
    TenantVPNConfig,
    RemoteUser,
    RemoteAccessLog,
    RemoteAccessPlan,
    RemoteAccessPayment,
)


# =============================================================================
# SAAS PLATFORM ADMIN (Super Admin Only)
# =============================================================================


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    """Manage SaaS subscription plans"""

    list_display = [
        "display_name",
        "monthly_price_formatted",
        "yearly_price_formatted",
        "max_routers",
        "max_vouchers_display",
        "features_summary",
        "is_active",
    ]
    list_filter = ["is_active"]
    ordering = ["display_order"]

    fieldsets = (
        (
            "Plan Info",
            {
                "fields": (
                    "name",
                    "display_name",
                    "description",
                    "is_active",
                    "display_order",
                )
            },
        ),
        (
            "Pricing (TZS)",
            {
                "fields": (
                    "monthly_price",
                    "yearly_price",
                    "currency",
                    "revenue_share_percentage",
                )
            },
        ),
        (
            "Limits",
            {
                "fields": (
                    "max_routers",
                    "max_wifi_users",
                    "max_vouchers_per_month",
                    "max_locations",
                    "max_staff_accounts",
                    "max_remote_users",
                )
            },
        ),
        (
            "Basic Features",
            {
                "fields": (
                    "custom_branding",
                    "custom_domain",
                    "api_access",
                    "white_label",
                    "priority_support",
                    "analytics_dashboard",
                    "sms_notifications",
                    "sms_broadcast",
                )
            },
        ),
        (
            "Premium Features (Business/Enterprise)",
            {
                "fields": (
                    "advanced_analytics",
                    "auto_sms_campaigns",
                    "webhook_notifications",
                    "data_export",
                    "ppp_support",
                    "remote_user_access",
                ),
                "description": "PPPoE support enables PPP customer management. Remote user access enables WireGuard VPN.",
            },
        ),
    )

    def monthly_price_formatted(self, obj):
        return f"TZS {obj.monthly_price:,.0f}"

    monthly_price_formatted.short_description = "Monthly"

    def yearly_price_formatted(self, obj):
        return f"TZS {obj.yearly_price:,.0f}"

    yearly_price_formatted.short_description = "Yearly"

    def max_vouchers_display(self, obj):
        if obj.max_vouchers_per_month >= 999999:
            return "Unlimited"
        return f"{obj.max_vouchers_per_month:,}"

    max_vouchers_display.short_description = "Vouchers/Month"

    def features_summary(self, obj):
        features = []
        if obj.custom_branding:
            features.append("Branding")
        if obj.custom_domain:
            features.append("Custom Domain")
        if obj.api_access:
            features.append("API")
        if obj.white_label:
            features.append("White Label")
        if obj.ppp_support:
            features.append("PPPoE")
        if obj.remote_user_access:
            features.append("VPN/Remote")
        return ", ".join(features) if features else "Basic"

    features_summary.short_description = "Features"


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    """Manage tenant businesses"""

    list_display = [
        "business_name",
        "slug",
        "owner_email",
        "subscription_plan",
        "subscription_status_badge",
        "router_count",
        "user_count",
        "created_at",
    ]
    list_filter = [
        "subscription_status",
        "subscription_plan",
        "country",
        "is_active",
        "created_at",
    ]
    search_fields = ["business_name", "slug", "business_email", "owner__email"]
    readonly_fields = ["id", "api_key", "api_secret", "created_at", "updated_at"]
    ordering = ["-created_at"]

    fieldsets = (
        (
            "Tenant Info",
            {
                "fields": (
                    "id",
                    "slug",
                    "business_name",
                    "business_email",
                    "business_phone",
                    "business_address",
                    "country",
                    "timezone",
                )
            },
        ),
        ("Owner", {"fields": ("owner",)}),
        (
            "Subscription",
            {
                "fields": (
                    "subscription_plan",
                    "subscription_status",
                    "billing_cycle",
                    "trial_ends_at",
                    "subscription_started_at",
                    "subscription_ends_at",
                )
            },
        ),
        (
            "Branding",
            {
                "fields": ("logo", "primary_color", "secondary_color", "custom_domain"),
                "classes": ("collapse",),
            },
        ),
        (
            "Payment Gateway (Tenant's Own)",
            {
                "fields": (
                    "preferred_payment_gateway",
                    "clickpesa_client_id",
                    "clickpesa_api_key",
                    "snippe_api_key",
                    "snippe_webhook_secret",
                    "nextsms_username",
                    "nextsms_password",
                    "nextsms_sender_id",
                ),
                "classes": ("collapse",),
            },
        ),
        ("API Access", {"fields": ("api_key", "api_secret"), "classes": ("collapse",)}),
        ("Status", {"fields": ("is_active", "notes", "created_at", "updated_at")}),
    )

    def owner_email(self, obj):
        return obj.owner.email

    owner_email.short_description = "Owner"

    def subscription_status_badge(self, obj):
        colors = {
            "trial": "orange",
            "active": "green",
            "suspended": "red",
            "cancelled": "gray",
        }
        color = colors.get(obj.subscription_status, "gray")
        return format_html(
            f'<span style="background: {color}; color: white; padding: 2px 8px; border-radius: 4px;">{obj.subscription_status.upper()}</span>'
        )

    subscription_status_badge.short_description = "Status"

    def router_count(self, obj):
        return obj.routers.filter(is_active=True).count()

    router_count.short_description = "Routers"

    def user_count(self, obj):
        return obj.wifi_users.count()

    user_count.short_description = "WiFi Users"


@admin.register(TenantStaff)
class TenantStaffAdmin(admin.ModelAdmin):
    """Manage tenant staff members"""

    list_display = ["user_email", "tenant_name", "role", "is_active", "invited_at"]
    list_filter = ["role", "is_active", "tenant"]
    search_fields = ["user__email", "tenant__business_name"]

    def user_email(self, obj):
        return obj.user.email

    user_email.short_description = "User"

    def tenant_name(self, obj):
        return obj.tenant.business_name

    tenant_name.short_description = "Tenant"


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    """Manage tenant locations"""

    list_display = ["name", "tenant_name", "city", "manager_name", "is_active"]
    list_filter = ["is_active", "tenant"]
    search_fields = ["name", "tenant__business_name", "city"]

    def tenant_name(self, obj):
        return obj.tenant.business_name

    tenant_name.short_description = "Tenant"


@admin.register(Router)
class RouterAdmin(admin.ModelAdmin):
    """Manage MikroTik routers"""

    list_display = [
        "name",
        "tenant_name",
        "host",
        "status_badge",
        "router_model",
        "last_seen",
        "is_active",
    ]
    list_filter = ["status", "is_active", "tenant"]
    search_fields = ["name", "host", "tenant__business_name", "router_identity"]
    readonly_fields = [
        "router_model",
        "router_version",
        "router_identity",
        "last_seen",
        "last_error",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        ("Router Info", {"fields": ("tenant", "location", "name", "description")}),
        ("Connection", {"fields": ("host", "port", "username", "password", "use_ssl")}),
        (
            "Router Details (Auto-detected)",
            {
                "fields": ("router_model", "router_version", "router_identity"),
                "classes": ("collapse",),
            },
        ),
        ("Hotspot Settings", {"fields": ("hotspot_interface", "hotspot_profile")}),
        (
            "Status",
            {
                "fields": (
                    "status",
                    "last_seen",
                    "last_error",
                    "is_active",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def tenant_name(self, obj):
        return obj.tenant.business_name

    tenant_name.short_description = "Tenant"

    def status_badge(self, obj):
        colors = {
            "online": "green",
            "offline": "red",
            "configuring": "orange",
            "error": "red",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            f'<span style="background: {color}; color: white; padding: 2px 8px; border-radius: 4px;">{obj.status.upper()}</span>'
        )

    status_badge.short_description = "Status"


@admin.register(RouterMonitoringSnapshot)
class RouterMonitoringSnapshotAdmin(admin.ModelAdmin):
    """View router monitoring snapshots"""

    list_display = [
        "router_name",
        "is_reachable",
        "cpu_load",
        "memory_display",
        "active_hotspot_users",
        "created_at",
    ]
    list_filter = ["is_reachable", "router__tenant", "created_at"]
    search_fields = ["router__name", "router__tenant__business_name"]
    readonly_fields = ["created_at"]
    date_hierarchy = "created_at"

    def router_name(self, obj):
        return f"{obj.router.tenant.business_name} - {obj.router.name}"

    router_name.short_description = "Router"

    def memory_display(self, obj):
        return f"{obj.memory_percent}%"

    memory_display.short_description = "Memory"


@admin.register(RouterBandwidthLog)
class RouterBandwidthLogAdmin(admin.ModelAdmin):
    """View router bandwidth logs"""

    list_display = [
        "router_name",
        "hour_start",
        "rx_display",
        "tx_display",
        "peak_users",
        "avg_users",
    ]
    list_filter = ["router__tenant", "hour_start"]
    search_fields = ["router__name", "router__tenant__business_name"]
    date_hierarchy = "hour_start"

    def router_name(self, obj):
        return f"{obj.router.tenant.business_name} - {obj.router.name}"

    router_name.short_description = "Router"

    def rx_display(self, obj):
        return f"{obj.rx_mb} MB"

    rx_display.short_description = "Downloaded"

    def tx_display(self, obj):
        return f"{obj.tx_mb} MB"

    tx_display.short_description = "Uploaded"


@admin.register(RouterHotspotCustomization)
class RouterHotspotCustomizationAdmin(admin.ModelAdmin):
    """Manage router hotspot customization"""

    list_display = [
        "router_name",
        "page_title",
        "primary_color",
        "use_custom_template",
        "updated_at",
    ]
    list_filter = ["use_custom_template", "router__tenant"]
    search_fields = ["router__name", "router__tenant__business_name", "page_title"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Router", {"fields": ("router",)}),
        ("Text Content", {"fields": ("page_title", "welcome_message", "footer_text")}),
        (
            "Branding",
            {"fields": ("logo_url", "background_image_url", "favicon_url")},
        ),
        (
            "Colors",
            {
                "fields": (
                    "primary_color",
                    "secondary_color",
                    "background_color",
                    "text_color",
                    "button_color",
                    "button_text_color",
                )
            },
        ),
        (
            "Layout Options",
            {
                "fields": (
                    "show_logo",
                    "show_bundles",
                    "show_social_login",
                    "show_terms_link",
                    "show_support_contact",
                )
            },
        ),
        (
            "Contact Info",
            {"fields": ("terms_url", "support_email", "support_phone")},
        ),
        (
            "Custom Code (Advanced)",
            {
                "fields": ("custom_css", "custom_js", "header_html", "footer_html"),
                "classes": ("collapse",),
            },
        ),
        (
            "Custom Templates (Advanced)",
            {
                "fields": (
                    "use_custom_template",
                    "custom_login_html",
                    "custom_logout_html",
                    "custom_status_html",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def router_name(self, obj):
        return f"{obj.router.tenant.business_name} - {obj.router.name}"

    router_name.short_description = "Router"


@admin.register(TenantSubscriptionPayment)
class TenantSubscriptionPaymentAdmin(admin.ModelAdmin):
    """Track subscription payments from tenants"""

    list_display = [
        "tenant_name",
        "plan_name",
        "amount",
        "billing_cycle",
        "status",
        "period_start",
        "period_end",
        "created_at",
    ]
    list_filter = ["status", "billing_cycle", "plan", "created_at"]
    search_fields = ["tenant__business_name", "transaction_id"]
    readonly_fields = ["created_at", "completed_at"]

    def tenant_name(self, obj):
        return obj.tenant.business_name

    tenant_name.short_description = "Tenant"

    def plan_name(self, obj):
        return obj.plan.display_name

    plan_name.short_description = "Plan"


# =============================================================================
# WIFI BILLING ADMIN (Modified for Multi-Tenancy)
# =============================================================================


# Note: Custom admin dashboard URL is registered via apps.py ready() method
# The billing_statistics URL is accessible at /admin/dashboard/


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = [
        "phone_number",
        "tenant_name",
        "is_active",
        "access_status",
        "paid_until",
        "total_payments",
        "device_count",
        "created_at",
    ]
    list_filter = ["is_active", "tenant", "created_at"]
    search_fields = ["phone_number", "tenant__business_name"]
    readonly_fields = ["created_at", "total_payments", "total_amount_paid"]
    ordering = ["-created_at"]

    def tenant_name(self, obj):
        if obj.tenant:
            return obj.tenant.business_name
        return "-"

    tenant_name.short_description = "Tenant"

    def access_status(self, obj):
        """Display access status with color coding"""
        if obj.is_active and obj.paid_until and obj.paid_until > timezone.now():
            return format_html('<span style="color: green;">✓ Active</span>')
        else:
            return format_html('<span style="color: red;">✗ Inactive</span>')

    access_status.short_description = "Access Status"

    def device_count(self, obj):
        """Count of active devices"""
        return obj.devices.filter(is_active=True).count()

    device_count.short_description = "Active Devices"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("devices").select_related("tenant")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "phone_number",
        "tenant_name",
        "amount_formatted",
        "status_badge",
        "payment_reference",
        "payment_channel",
        "bundle_name",
        "created_at",
    ]
    list_filter = ["status", "payment_channel", "tenant", "created_at", "bundle"]
    search_fields = [
        "phone_number",
        "payment_reference",
        "transaction_id",
        "order_reference",
        "tenant__business_name",
    ]
    readonly_fields = ["created_at", "completed_at"]
    ordering = ["-created_at"]

    def tenant_name(self, obj):
        return obj.tenant.business_name if obj.tenant else "-"

    tenant_name.short_description = "Tenant"

    def amount_formatted(self, obj):
        """Format amount with currency"""
        return f"TSh {obj.amount:,}"

    amount_formatted.short_description = "Amount"

    def status_badge(self, obj):
        """Display status with color badges"""
        colors = {
            "completed": "green",
            "pending": "orange",
            "failed": "red",
            "cancelled": "gray",
            "refunded": "purple",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            f'<span style="background: {color}; color: white; padding: 2px 8px; border-radius: 4px;">{obj.status.upper()}</span>'
        )

    status_badge.short_description = "Status"

    def bundle_name(self, obj):
        """Display bundle name"""
        return obj.bundle.name if obj.bundle else "-"

    bundle_name.short_description = "Bundle"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user", "bundle", "tenant")


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = [
        "user_phone",
        "tenant_name",
        "device_name",
        "mac_address",
        "ip_address",
        "is_active",
        "first_seen",
        "last_seen",
    ]
    list_filter = ["is_active", "tenant", "first_seen"]
    search_fields = [
        "user__phone_number",
        "mac_address",
        "ip_address",
        "device_name",
        "tenant__business_name",
    ]
    readonly_fields = ["first_seen", "last_seen"]
    ordering = ["-last_seen"]

    def tenant_name(self, obj):
        return obj.tenant.business_name if obj.tenant else "-"

    tenant_name.short_description = "Tenant"

    def user_phone(self, obj):
        """Display user phone number"""
        return obj.user.phone_number

    user_phone.short_description = "User Phone"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user", "tenant")


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = [
        "user_phone",
        "tenant_name",
        "ip_address",
        "mac_address",
        "access_granted_badge",
        "denial_reason",
        "timestamp",
    ]
    list_filter = ["access_granted", "tenant", "timestamp", "denial_reason"]
    search_fields = [
        "user__phone_number",
        "ip_address",
        "mac_address",
        "tenant__business_name",
    ]
    readonly_fields = ["timestamp"]
    ordering = ["-timestamp"]

    def tenant_name(self, obj):
        return obj.tenant.business_name if obj.tenant else "-"

    tenant_name.short_description = "Tenant"

    def user_phone(self, obj):
        """Display user phone number"""
        return obj.user.phone_number if obj.user else "-"

    user_phone.short_description = "User Phone"

    def access_granted_badge(self, obj):
        """Display access status with badges"""
        if obj.access_granted:
            return format_html(
                '<span style="background: green; color: white; padding: 2px 8px; border-radius: 4px;">GRANTED</span>'
            )
        else:
            return format_html(
                '<span style="background: red; color: white; padding: 2px 8px; border-radius: 4px;">DENIED</span>'
            )

    access_granted_badge.short_description = "Access"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user", "tenant")


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = [
        "phone_number",
        "tenant_name",
        "sms_type",
        "success_badge",
        "sent_at",
    ]
    list_filter = ["sms_type", "success", "tenant", "sent_at"]
    search_fields = ["phone_number", "message", "tenant__business_name"]
    readonly_fields = ["sent_at"]
    ordering = ["-sent_at"]

    def tenant_name(self, obj):
        return obj.tenant.business_name if obj.tenant else "-"

    tenant_name.short_description = "Tenant"

    def success_badge(self, obj):
        """Display success status with badges"""
        if obj.success:
            return format_html(
                '<span style="background: green; color: white; padding: 2px 8px; border-radius: 4px;">SUCCESS</span>'
            )
        else:
            return format_html(
                '<span style="background: red; color: white; padding: 2px 8px; border-radius: 4px;">FAILED</span>'
            )

    success_badge.short_description = "Status"


@admin.register(SMSBroadcast)
class SMSBroadcastAdmin(admin.ModelAdmin):
    """Manage SMS broadcast campaigns"""

    list_display = [
        "title",
        "target_type_display",
        "status_badge",
        "progress_display",
        "created_by_name",
        "created_at",
    ]
    list_filter = ["status", "target_type", "created_at"]
    search_fields = ["title", "message", "created_by__username"]
    readonly_fields = [
        "id",
        "sent_count",
        "failed_count",
        "total_recipients",
        "started_at",
        "completed_at",
        "error_message",
    ]
    ordering = ["-created_at"]

    fieldsets = (
        (
            "Campaign Info",
            {
                "fields": (
                    "title",
                    "message",
                    "target_type",
                    "target_tenant",
                    "custom_recipients",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "status",
                    "total_recipients",
                    "sent_count",
                    "failed_count",
                    "error_message",
                )
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_by", "scheduled_at", "started_at", "completed_at")},
        ),
    )

    actions = ["send_broadcast"]

    def target_type_display(self, obj):
        return obj.get_target_type_display()

    target_type_display.short_description = "Target"

    def status_badge(self, obj):
        """Display status with colored badges"""
        colors = {
            "draft": "#6c757d",
            "pending": "#ffc107",
            "sending": "#17a2b8",
            "completed": "#28a745",
            "failed": "#dc3545",
            "cancelled": "#6c757d",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 4px;">{}</span>',
            color,
            obj.get_status_display().upper(),
        )

    status_badge.short_description = "Status"

    def progress_display(self, obj):
        """Display sent/total progress"""
        if obj.total_recipients > 0:
            percentage = (obj.sent_count / obj.total_recipients) * 100
            return f"{obj.sent_count}/{obj.total_recipients} ({percentage:.0f}%)"
        return f"{obj.sent_count}/0"

    progress_display.short_description = "Progress"

    def created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else "-"

    created_by_name.short_description = "Created By"

    def send_broadcast(self, request, queryset):
        """Send selected broadcasts"""
        for broadcast in queryset:
            if broadcast.status in ["draft", "pending"]:
                success, message = broadcast.send_broadcast()
                if success:
                    self.message_user(
                        request,
                        f"Broadcast '{broadcast.title}' sent successfully: {message}",
                    )
                else:
                    self.message_user(
                        request,
                        f"Broadcast '{broadcast.title}' failed: {message}",
                        level="ERROR",
                    )

    send_broadcast.short_description = "Send selected broadcasts"


@admin.register(TenantSMSBroadcast)
class TenantSMSBroadcastAdmin(admin.ModelAdmin):
    """Manage tenant SMS broadcast campaigns"""

    list_display = [
        "title",
        "tenant_name",
        "target_type_display",
        "status_badge",
        "progress_display",
        "created_at",
    ]
    list_filter = ["status", "target_type", "tenant", "created_at"]
    search_fields = ["title", "message", "tenant__business_name"]
    readonly_fields = [
        "id",
        "sent_count",
        "failed_count",
        "total_recipients",
        "started_at",
        "completed_at",
        "error_message",
    ]
    ordering = ["-created_at"]

    fieldsets = (
        (
            "Campaign Info",
            {
                "fields": (
                    "tenant",
                    "title",
                    "message",
                    "target_type",
                    "custom_recipients",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "status",
                    "total_recipients",
                    "sent_count",
                    "failed_count",
                    "error_message",
                )
            },
        ),
        (
            "Timestamps",
            {"fields": ("scheduled_at", "started_at", "completed_at")},
        ),
    )

    def tenant_name(self, obj):
        return obj.tenant.business_name if obj.tenant else "-"

    tenant_name.short_description = "Tenant"

    def target_type_display(self, obj):
        return obj.get_target_type_display()

    target_type_display.short_description = "Target"

    def status_badge(self, obj):
        """Display status with colored badges"""
        colors = {
            "draft": "#6c757d",
            "pending": "#ffc107",
            "sending": "#17a2b8",
            "completed": "#28a745",
            "failed": "#dc3545",
            "cancelled": "#6c757d",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 4px;">{}</span>',
            color,
            obj.get_status_display().upper(),
        )

    status_badge.short_description = "Status"

    def progress_display(self, obj):
        """Display sent/total progress"""
        if obj.total_recipients > 0:
            percentage = (obj.sent_count / obj.total_recipients) * 100
            return f"{obj.sent_count}/{obj.total_recipients} ({percentage:.0f}%)"
        return f"{obj.sent_count}/0"

    progress_display.short_description = "Progress"


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "tenant_name",
        "duration_display",
        "status_badge",
        "batch_id",
        "created_at",
        "used_at",
        "used_by_phone",
    ]
    list_filter = ["is_used", "duration_hours", "tenant", "created_at", "batch_id"]
    search_fields = [
        "code",
        "batch_id",
        "used_by__phone_number",
        "tenant__business_name",
    ]
    readonly_fields = ["code", "created_at", "used_at", "is_used"]
    ordering = ["-created_at"]

    actions = ["export_vouchers_csv", "mark_as_used", "mark_as_unused"]

    def tenant_name(self, obj):
        return obj.tenant.business_name if obj.tenant else "-"

    tenant_name.short_description = "Tenant"

    def duration_display(self, obj):
        """Display duration in human-readable format"""
        if obj.duration_hours >= 24:
            days = obj.duration_hours // 24
            return f"{days} day{'s' if days > 1 else ''}"
        return f"{obj.duration_hours}h"

    duration_display.short_description = "Duration"

    def status_badge(self, obj):
        """Display voucher status with badges"""
        if obj.is_used:
            return format_html(
                '<span style="background: red; color: white; padding: 2px 8px; border-radius: 4px;">USED</span>'
            )
        else:
            return format_html(
                '<span style="background: green; color: white; padding: 2px 8px; border-radius: 4px;">AVAILABLE</span>'
            )

    status_badge.short_description = "Status"

    def used_by_phone(self, obj):
        """Display phone number of user who redeemed voucher"""
        return obj.used_by.phone_number if obj.used_by else "-"

    used_by_phone.short_description = "Used By"

    def export_vouchers_csv(self, request, queryset):  # noqa: ARG002
        """Export selected vouchers to CSV"""
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="vouchers.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "Tenant",
                "Code",
                "Duration (Hours)",
                "Status",
                "Batch ID",
                "Created At",
                "Used At",
                "Used By",
            ]
        )

        for voucher in queryset:
            writer.writerow(
                [
                    voucher.tenant.business_name if voucher.tenant else "-",
                    voucher.code,
                    voucher.duration_hours,
                    "Used" if voucher.is_used else "Available",
                    voucher.batch_id,
                    voucher.created_at.strftime("%Y-%m-%d %H:%M"),
                    (
                        voucher.used_at.strftime("%Y-%m-%d %H:%M")
                        if voucher.used_at
                        else "-"
                    ),
                    voucher.used_by.phone_number if voucher.used_by else "-",
                ]
            )

        return response

    export_vouchers_csv.short_description = "Export selected vouchers to CSV"

    def mark_as_used(self, request, queryset):
        """Mark selected vouchers as used (for testing)"""
        updated = queryset.update(is_used=True)
        self.message_user(request, f"{updated} vouchers marked as used.")

    mark_as_used.short_description = "Mark as used"

    def mark_as_unused(self, request, queryset):
        """Mark selected vouchers as unused (for testing)"""
        updated = queryset.filter(is_used=True).update(
            is_used=False, used_at=None, used_by=None
        )
        self.message_user(request, f"{updated} vouchers marked as unused.")

    mark_as_unused.short_description = "Mark as unused"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("used_by", "tenant")


@admin.register(PaymentWebhook)
class PaymentWebhookAdmin(admin.ModelAdmin):
    list_display = [
        "order_reference",
        "event_type",
        "processing_status_badge",
        "payment_status",
        "amount_formatted",
        "received_at",
        "processed_at",
    ]
    list_filter = ["event_type", "processing_status", "payment_status", "received_at"]
    search_fields = ["order_reference", "transaction_id", "source_ip"]
    readonly_fields = [
        "received_at",
        "processed_at",
        "raw_payload",
        "source_ip",
        "user_agent",
    ]
    ordering = ["-received_at"]

    fieldsets = (
        (
            "Webhook Information",
            {
                "fields": (
                    "event_type",
                    "processing_status",
                    "processing_error",
                    "received_at",
                    "processed_at",
                )
            },
        ),
        (
            "Payment Data",
            {
                "fields": (
                    "order_reference",
                    "transaction_id",
                    "payment_status",
                    "channel",
                    "amount",
                    "payment",
                )
            },
        ),
        (
            "Request Metadata",
            {"fields": ("source_ip", "user_agent"), "classes": ("collapse",)},
        ),
        ("Raw Data", {"fields": ("raw_payload",), "classes": ("collapse",)}),
    )

    def processing_status_badge(self, obj):
        """Display processing status with color badges"""
        colors = {
            "received": "blue",
            "processed": "green",
            "failed": "red",
            "ignored": "gray",
        }
        color = colors.get(obj.processing_status, "gray")
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 4px; text-transform: uppercase;">{}</span>',
            color,
            obj.processing_status,
        )

    processing_status_badge.short_description = "Processing Status"

    def amount_formatted(self, obj):
        """Format amount with currency"""
        if obj.amount:
            return f"TSh {obj.amount:,}"
        return "-"

    amount_formatted.short_description = "Amount"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("payment", "tenant")


@admin.register(Bundle)
class BundleAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "tenant_name",
        "duration_display",
        "price_formatted",
        "currency",
        "is_active_badge",
        "display_order",
        "payment_count",
    ]
    list_filter = ["is_active", "tenant", "currency"]
    search_fields = ["name", "description", "tenant__business_name"]
    list_editable = ["display_order"]
    ordering = ["tenant", "display_order"]

    def tenant_name(self, obj):
        return obj.tenant.business_name if obj.tenant else "-"

    tenant_name.short_description = "Tenant"

    def duration_display(self, obj):
        """Display duration in human-readable format"""
        if obj.duration_hours >= 24:
            days = obj.duration_hours // 24
            return f"{days} day{'s' if days > 1 else ''}"
        return f"{obj.duration_hours} hour{'s' if obj.duration_hours > 1 else ''}"

    duration_display.short_description = "Duration"

    def price_formatted(self, obj):
        """Format price with currency"""
        return f"{obj.currency} {obj.price:,}"

    price_formatted.short_description = "Price"

    def is_active_badge(self, obj):
        """Display active status with badges"""
        if obj.is_active:
            return format_html(
                '<span style="background: green; color: white; padding: 2px 8px; border-radius: 4px;">ACTIVE</span>'
            )
        else:
            return format_html(
                '<span style="background: gray; color: white; padding: 2px 8px; border-radius: 4px;">INACTIVE</span>'
            )

    is_active_badge.short_description = "Status"

    def payment_count(self, obj):
        """Count of payments for this bundle"""
        return obj.payments.filter(status="completed").count()

    payment_count.short_description = "Sales"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("tenant")


# =============================================================================
# CONTACT SUBMISSIONS ADMIN
# =============================================================================


@admin.register(ContactSubmission)
class ContactSubmissionAdmin(admin.ModelAdmin):
    """Manage contact form submissions"""

    list_display = [
        "name",
        "email",
        "phone",
        "subject_display",
        "status_badge",
        "created_at",
        "replied_at",
    ]
    list_filter = ["status", "subject", "created_at"]
    search_fields = ["name", "email", "phone", "message"]
    readonly_fields = ["ip_address", "user_agent", "created_at", "updated_at"]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"
    list_per_page = 50

    fieldsets = (
        ("Contact Info", {"fields": ("name", "email", "phone")}),
        ("Message", {"fields": ("subject", "message")}),
        ("Status", {"fields": ("status", "replied_at", "replied_by")}),
        ("Internal Notes", {"fields": ("notes",), "classes": ("collapse",)}),
        (
            "Metadata",
            {
                "fields": ("ip_address", "user_agent", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["mark_as_read", "mark_as_replied", "mark_as_closed"]

    def subject_display(self, obj):
        """Display subject with color coding"""
        colors = {
            "sales": "#22c55e",  # Green
            "demo": "#3b82f6",  # Blue
            "support": "#f59e0b",  # Orange
            "partnership": "#8b5cf6",  # Purple
            "general": "#6b7280",  # Gray
            "other": "#6b7280",  # Gray
        }
        color = colors.get(obj.subject, "#6b7280")
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_subject_display(),
        )

    subject_display.short_description = "Subject"

    def status_badge(self, obj):
        """Display status with color badges"""
        colors = {
            "new": "#ef4444",  # Red
            "read": "#f59e0b",  # Orange
            "replied": "#22c55e",  # Green
            "closed": "#6b7280",  # Gray
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display().upper(),
        )

    status_badge.short_description = "Status"

    def mark_as_read(self, request, queryset):
        """Mark selected submissions as read"""
        updated = queryset.filter(status="new").update(status="read")
        self.message_user(request, f"{updated} submission(s) marked as read.")

    mark_as_read.short_description = "Mark as Read"

    def mark_as_replied(self, request, queryset):
        """Mark selected submissions as replied"""
        updated = queryset.exclude(status="replied").update(
            status="replied",
            replied_at=timezone.now(),
            replied_by=request.user.email or request.user.username,
        )
        self.message_user(request, f"{updated} submission(s) marked as replied.")

    mark_as_replied.short_description = "Mark as Replied"

    def mark_as_closed(self, request, queryset):
        """Mark selected submissions as closed"""
        updated = queryset.exclude(status="closed").update(status="closed")
        self.message_user(request, f"{updated} submission(s) closed.")

    mark_as_closed.short_description = "Mark as Closed"

    def save_model(self, request, obj, form, change):
        """Auto-set replied_by when status changes to replied"""
        if "status" in form.changed_data and obj.status == "replied":
            if not obj.replied_at:
                obj.replied_at = timezone.now()
            if not obj.replied_by:
                obj.replied_by = request.user.email or request.user.username
        super().save_model(request, obj, form, change)


# =============================================================================
# PREMIUM FEATURES ADMIN (Business/Enterprise)
# =============================================================================


@admin.register(TenantWebhook)
class TenantWebhookAdmin(admin.ModelAdmin):
    """Manage tenant webhook configurations"""

    list_display = [
        "tenant",
        "name",
        "url_display",
        "events_count",
        "is_active",
        "last_success_at",
        "success_rate",
    ]
    list_filter = ["is_active", "status", "tenant", "created_at"]
    search_fields = ["name", "url", "tenant__business_name"]
    readonly_fields = [
        "secret_key",
        "last_success_at",
        "last_failure_at",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]

    fieldsets = (
        (
            "Webhook Info",
            {"fields": ("tenant", "name", "url", "secret_key", "is_active", "status")},
        ),
        ("Events", {"fields": ("events",)}),
        (
            "Timestamps",
            {
                "fields": (
                    "last_success_at",
                    "last_failure_at",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def url_display(self, obj):
        if len(obj.url) > 50:
            return f"{obj.url[:50]}..."
        return obj.url

    url_display.short_description = "URL"

    def events_count(self, obj):
        return len(obj.events) if obj.events else 0

    events_count.short_description = "Events"

    def success_rate(self, obj):
        deliveries = obj.deliveries.all()
        total = deliveries.count()
        if total == 0:
            return "N/A"
        successful = deliveries.filter(success=True).count()
        rate = (successful / total) * 100
        color = "#22c55e" if rate >= 90 else "#f59e0b" if rate >= 70 else "#ef4444"
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color,
            rate,
        )

    success_rate.short_description = "Success Rate"


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    """Track webhook delivery attempts"""

    list_display = [
        "webhook",
        "event_type",
        "success_badge",
        "response_status_code",
        "attempts",
        "created_at",
    ]
    list_filter = ["status", "event_type", "webhook__tenant"]
    search_fields = ["webhook__name", "webhook__tenant__business_name", "event_type"]
    readonly_fields = [
        "webhook",
        "event_type",
        "payload",
        "response_status_code",
        "response_body",
        "status",
        "error_message",
        "attempts",
        "created_at",
    ]
    ordering = ["-created_at"]

    def success_badge(self, obj):
        if obj.status == "success":
            return format_html(
                '<span style="background: #22c55e; color: white; padding: 2px 8px; border-radius: 4px;">SUCCESS</span>'
            )
        elif obj.status == "failed":
            return format_html(
                '<span style="background: #ef4444; color: white; padding: 2px 8px; border-radius: 4px;">FAILED</span>'
            )
        return format_html(
            '<span style="background: #f59e0b; color: white; padding: 2px 8px; border-radius: 4px;">{}</span>',
            obj.status.upper(),
        )

    success_badge.short_description = "Status"


@admin.register(AutoSMSCampaign)
class AutoSMSCampaignAdmin(admin.ModelAdmin):
    """Manage auto SMS campaigns"""

    list_display = [
        "tenant",
        "name",
        "trigger_type",
        "is_active",
        "total_sent",
        "total_failed",
        "last_triggered_at",
    ]
    list_filter = ["is_active", "trigger_type", "tenant", "created_at"]
    search_fields = ["name", "tenant__business_name"]
    readonly_fields = [
        "total_sent",
        "total_failed",
        "last_triggered_at",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]

    fieldsets = (
        (
            "Campaign Info",
            {"fields": ("tenant", "name", "trigger_type", "is_active")},
        ),
        (
            "Message Template",
            {
                "fields": ("message_template",),
                "description": "Available placeholders: {name}, {phone}, {amount}, {voucher_code}, {expiry_date}, {bundle_name}",
            },
        ),
        (
            "Scheduling (for scheduled type)",
            {"fields": ("schedule_type", "schedule_time", "schedule_days")},
        ),
        (
            "Expiry Reminder (for expiry_reminder type)",
            {"fields": ("reminder_hours_before",)},
        ),
        (
            "Statistics",
            {"fields": ("total_sent", "total_failed", "last_triggered_at")},
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(AutoSMSLog)
class AutoSMSLogAdmin(admin.ModelAdmin):
    """Track auto SMS delivery logs"""

    list_display = [
        "campaign",
        "recipient_phone",
        "trigger_event",
        "success_badge",
        "triggered_at",
    ]
    list_filter = ["success", "trigger_event", "campaign__tenant", "triggered_at"]
    search_fields = [
        "recipient_phone",
        "campaign__name",
        "campaign__tenant__business_name",
    ]
    readonly_fields = [
        "campaign",
        "recipient_phone",
        "message_sent",
        "trigger_event",
        "success",
        "error_message",
        "triggered_at",
    ]
    ordering = ["-triggered_at"]

    def success_badge(self, obj):
        if obj.success:
            return format_html(
                '<span style="background: #22c55e; color: white; padding: 2px 8px; border-radius: 4px;">SENT</span>'
            )
        return format_html(
            '<span style="background: #ef4444; color: white; padding: 2px 8px; border-radius: 4px;">FAILED</span>'
        )

    success_badge.short_description = "Status"


@admin.register(TenantAnalyticsSnapshot)
class TenantAnalyticsSnapshotAdmin(admin.ModelAdmin):
    """View tenant analytics snapshots"""

    list_display = [
        "tenant",
        "date",
        "total_users",
        "active_users",
        "total_revenue_display",
        "vouchers_generated",
    ]
    list_filter = ["tenant", "date"]
    search_fields = ["tenant__business_name"]
    readonly_fields = [
        "tenant",
        "date",
        "total_users",
        "active_users",
        "new_users",
        "expired_users",
        "total_revenue",
        "payment_count",
        "vouchers_generated",
        "vouchers_redeemed",
        "bundle_breakdown",
        "payment_channel_breakdown",
        "created_at",
    ]
    ordering = ["-date", "tenant"]

    def total_revenue_display(self, obj):
        return f"TZS {obj.total_revenue:,.0f}"

    total_revenue_display.short_description = "Revenue"


# =============================================================================
# REMOTE USER ACCESS (VPN) ADMIN — Enterprise Plan
# =============================================================================


class RemoteUserInline(admin.TabularInline):
    """Inline for remote users within VPN config"""

    model = RemoteUser
    extra = 0
    fields = [
        "name",
        "plan",
        "assigned_ip",
        "status",
        "is_active",
        "expires_at",
        "config_downloaded",
        "is_configured_on_router",
        "last_handshake",
    ]
    readonly_fields = ["last_handshake", "config_downloaded", "is_configured_on_router"]


@admin.register(TenantVPNConfig)
class TenantVPNConfigAdmin(admin.ModelAdmin):
    """Manage per-tenant WireGuard VPN configurations"""

    list_display = [
        "tenant",
        "router",
        "interface_name",
        "listen_port",
        "address_pool",
        "is_active",
        "is_configured_on_router",
        "last_synced_at",
    ]
    list_filter = ["is_active", "is_configured_on_router"]
    search_fields = ["tenant__business_name", "router__name"]
    readonly_fields = [
        "id",
        "server_public_key",
        "last_synced_at",
        "last_sync_error",
        "created_at",
        "updated_at",
    ]
    inlines = [RemoteUserInline]

    fieldsets = (
        (
            "Tenant & Router",
            {
                "fields": ("id", "tenant", "router"),
            },
        ),
        (
            "WireGuard Interface",
            {
                "fields": (
                    "interface_name",
                    "listen_port",
                    "server_private_key",
                    "server_public_key",
                ),
            },
        ),
        (
            "Network Configuration",
            {
                "fields": (
                    "address_pool",
                    "server_address",
                    "dns_servers",
                    "mtu",
                    "persistent_keepalive",
                    "allowed_ips",
                ),
            },
        ),
        (
            "Router Integration",
            {
                "fields": (
                    "enable_nat",
                    "enable_firewall_rules",
                    "is_configured_on_router",
                    "last_synced_at",
                    "last_sync_error",
                ),
            },
        ),
        (
            "Status",
            {
                "fields": ("is_active", "created_at", "updated_at"),
            },
        ),
    )


@admin.register(RemoteUser)
class RemoteUserAdmin(admin.ModelAdmin):
    """Manage remote VPN users (WireGuard peers)"""

    list_display = [
        "name",
        "tenant",
        "plan_name",
        "assigned_ip",
        "status",
        "is_active",
        "is_configured_on_router",
        "expires_at",
        "last_handshake",
        "created_at",
    ]
    list_filter = [
        "status",
        "is_active",
        "is_configured_on_router",
        "config_downloaded",
        "plan",
        "tenant",
    ]
    search_fields = [
        "name",
        "email",
        "phone",
        "assigned_ip",
        "tenant__business_name",
    ]
    readonly_fields = [
        "id",
        "public_key",
        "is_configured_on_router",
        "config_downloaded",
        "last_handshake",
        "created_at",
        "updated_at",
    ]
    list_editable = ["status", "is_active"]
    date_hierarchy = "created_at"

    def plan_name(self, obj):
        return obj.plan.name if obj.plan else "—"

    plan_name.short_description = "Plan"


@admin.register(RemoteAccessLog)
class RemoteAccessLogAdmin(admin.ModelAdmin):
    """View remote access VPN event logs"""

    list_display = [
        "remote_user",
        "tenant",
        "event_type",
        "client_endpoint",
        "bytes_sent",
        "bytes_received",
        "timestamp",
    ]
    list_filter = ["event_type", "tenant"]
    search_fields = [
        "remote_user__name",
        "tenant__business_name",
        "client_endpoint",
    ]
    readonly_fields = [
        "id",
        "remote_user",
        "tenant",
        "event_type",
        "event_details",
        "client_endpoint",
        "bytes_sent",
        "bytes_received",
        "timestamp",
        "created_at",
    ]
    date_hierarchy = "timestamp"

    def has_add_permission(self, request):
        return False  # Logs are created programmatically

    def has_change_permission(self, request, obj=None):
        return False  # Logs are read-only


@admin.register(RemoteAccessPlan)
class RemoteAccessPlanAdmin(admin.ModelAdmin):
    """Manage remote access VPN plans that tenants sell to their users"""

    list_display = [
        "name",
        "tenant_name",
        "price_display",
        "billing_cycle",
        "speed_display",
        "data_display",
        "subscriber_count_display",
        "popular_badge",
        "is_active",
    ]
    list_filter = ["is_active", "billing_cycle", "tenant", "is_popular"]
    search_fields = ["name", "description", "tenant__business_name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["tenant", "display_order"]

    fieldsets = (
        (
            "Plan Info",
            {
                "fields": (
                    "id",
                    "tenant",
                    "name",
                    "description",
                    "is_active",
                ),
            },
        ),
        (
            "Pricing",
            {
                "fields": (
                    "price",
                    "currency",
                    "promo_price",
                    "promo_label",
                ),
            },
        ),
        (
            "Billing Cycle",
            {
                "fields": (
                    "billing_cycle",
                    "billing_days",
                ),
            },
        ),
        (
            "Bandwidth & Data",
            {
                "fields": (
                    "bandwidth_limit_down",
                    "bandwidth_limit_up",
                    "download_speed",
                    "upload_speed",
                    "data_limit_gb",
                ),
            },
        ),
        (
            "Access Scope",
            {
                "fields": (
                    "max_devices_per_user",
                    "allowed_ips",
                    "full_tunnel",
                ),
            },
        ),
        (
            "Display",
            {
                "fields": (
                    "features",
                    "display_order",
                    "is_popular",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def tenant_name(self, obj):
        return obj.tenant.business_name

    tenant_name.short_description = "Tenant"

    def price_display(self, obj):
        if obj.promo_price is not None:
            return format_html(
                '<span style="text-decoration: line-through; color: #999;">TZS {}</span> '
                '<span style="color: #10b981; font-weight: bold;">TZS {}</span>',
                f"{obj.price:,.0f}",
                f"{obj.promo_price:,.0f}",
            )
        return f"TZS {obj.price:,.0f}"

    price_display.short_description = "Price"

    def speed_display(self, obj):
        return obj.speed_display

    speed_display.short_description = "Speed"

    def data_display(self, obj):
        return obj.data_display

    data_display.short_description = "Data"

    def subscriber_count_display(self, obj):
        count = obj.subscriber_count
        if count > 0:
            return format_html('<span style="font-weight: bold;">{}</span>', count)
        return "0"

    subscriber_count_display.short_description = "Subscribers"

    def popular_badge(self, obj):
        if obj.is_popular:
            return format_html(
                '<span style="background: #f59e0b; color: white; padding: 2px 8px; border-radius: 4px;">⭐ POPULAR</span>'
            )
        return "—"

    popular_badge.short_description = "Popular"


@admin.register(RemoteAccessPayment)
class RemoteAccessPaymentAdmin(admin.ModelAdmin):
    """Track remote access VPN payments"""

    list_display = [
        "order_reference",
        "remote_user_name",
        "tenant_name",
        "plan_name",
        "amount_display",
        "billing_days",
        "status_badge",
        "payment_channel",
        "created_at",
        "completed_at",
    ]
    list_filter = ["status", "payment_channel", "tenant", "billing_days"]
    search_fields = [
        "order_reference",
        "payment_reference",
        "transaction_id",
        "phone_number",
        "remote_user__name",
        "tenant__business_name",
    ]
    readonly_fields = [
        "id",
        "order_reference",
        "payment_reference",
        "transaction_id",
        "created_at",
        "updated_at",
        "completed_at",
    ]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Payment Info",
            {
                "fields": (
                    "id",
                    "tenant",
                    "remote_user",
                    "plan",
                    "order_reference",
                ),
            },
        ),
        (
            "Amount & Duration",
            {
                "fields": (
                    "amount",
                    "currency",
                    "billing_days",
                ),
            },
        ),
        (
            "Payment Method",
            {
                "fields": (
                    "payment_channel",
                    "phone_number",
                    "payment_reference",
                    "transaction_id",
                ),
            },
        ),
        (
            "Status & Timestamps",
            {
                "fields": (
                    "status",
                    "created_at",
                    "updated_at",
                    "completed_at",
                ),
            },
        ),
    )

    actions = ["mark_as_completed", "mark_as_failed"]

    def remote_user_name(self, obj):
        return obj.remote_user.name

    remote_user_name.short_description = "Remote User"

    def tenant_name(self, obj):
        return obj.tenant.business_name

    tenant_name.short_description = "Tenant"

    def plan_name(self, obj):
        return obj.plan.name if obj.plan else "—"

    plan_name.short_description = "Plan"

    def amount_display(self, obj):
        return f"TZS {obj.amount:,.0f}"

    amount_display.short_description = "Amount"

    def status_badge(self, obj):
        colors = {
            "pending": "#f59e0b",
            "completed": "#10b981",
            "failed": "#ef4444",
            "expired": "#6b7280",
            "refunded": "#8b5cf6",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 4px;">{}</span>',
            color,
            obj.status.upper(),
        )

    status_badge.short_description = "Status"

    def mark_as_completed(self, request, queryset):
        """Mark selected payments as completed and extend user access"""
        for payment in queryset.filter(status="pending"):
            payment.mark_completed()
        self.message_user(
            request,
            f"Processed {queryset.filter(status='completed').count()} payment(s).",
        )

    mark_as_completed.short_description = "Mark as completed (extends access)"

    def mark_as_failed(self, request, queryset):
        """Mark selected payments as failed"""
        for payment in queryset.filter(status="pending"):
            payment.mark_failed()
        self.message_user(request, "Selected payments marked as failed.")

    mark_as_failed.short_description = "Mark as failed"


# =============================================================================
# PPP (Point-to-Point Protocol) ADMIN — Enterprise Plan
# =============================================================================


@admin.register(PPPProfile)
class PPPProfileAdmin(admin.ModelAdmin):
    """Manage PPP speed/service profiles"""

    list_display = [
        "name",
        "tenant",
        "router",
        "rate_limit",
        "service_type",
        "monthly_price_display",
        "synced_badge",
        "is_active",
    ]
    list_filter = ["tenant", "router", "service_type", "is_active", "synced_to_router"]
    search_fields = ["name", "tenant__business_name", "router__name"]
    readonly_fields = ["mikrotik_id", "synced_to_router", "created_at", "updated_at"]

    fieldsets = (
        (None, {"fields": ("tenant", "router", "name", "is_active")}),
        (
            "Bandwidth",
            {"fields": ("rate_limit",)},
        ),
        (
            "IP & Addressing",
            {
                "fields": (
                    "local_address",
                    "remote_address",
                    "address_pool",
                    "dns_server",
                )
            },
        ),
        (
            "Connection",
            {"fields": ("service_type", "session_timeout", "idle_timeout")},
        ),
        (
            "Billing",
            {"fields": ("monthly_price",)},
        ),
        (
            "MikroTik Sync",
            {
                "classes": ("collapse",),
                "fields": ("synced_to_router", "mikrotik_id"),
            },
        ),
        (
            "Timestamps",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    def monthly_price_display(self, obj):
        return f"TZS {obj.monthly_price:,.0f}"

    monthly_price_display.short_description = "Price"

    def synced_badge(self, obj):
        if obj.synced_to_router:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 8px; border-radius: 4px;">SYNCED</span>'
            )
        return format_html(
            '<span style="background: #f59e0b; color: white; padding: 2px 8px; border-radius: 4px;">PENDING</span>'
        )

    synced_badge.short_description = "Router Sync"


@admin.register(PPPPlan)
class PPPPlanAdmin(admin.ModelAdmin):
    """Manage PPPoE billing plans"""

    list_display = [
        "name",
        "tenant",
        "profile_name",
        "price_display",
        "billing_cycle",
        "billing_days",
        "data_display",
        "speed_display",
        "customer_count_display",
        "popular_badge",
        "is_active",
    ]
    list_filter = ["tenant", "billing_cycle", "is_active", "is_popular"]
    search_fields = ["name", "description", "tenant__business_name", "profile__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["tenant", "profile"]

    fieldsets = (
        (None, {"fields": ("tenant", "profile", "name", "description", "is_active")}),
        (
            "Pricing",
            {"fields": ("price", "currency", "promo_price", "promo_label")},
        ),
        (
            "Billing Cycle",
            {"fields": ("billing_cycle", "billing_days")},
        ),
        (
            "Speed & Data",
            {"fields": ("download_speed", "upload_speed", "data_limit_gb")},
        ),
        (
            "Display",
            {"fields": ("features", "display_order", "is_popular")},
        ),
        (
            "Timestamps",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    def profile_name(self, obj):
        return f"{obj.profile.name} ({obj.profile.rate_limit or 'unlimited'})"

    profile_name.short_description = "Profile"

    def price_display(self, obj):
        if obj.promo_price is not None:
            return format_html(
                '<span style="text-decoration: line-through; color: #999;">TZS {}</span> '
                '<span style="color: #10b981; font-weight: bold;">TZS {}</span>',
                f"{obj.price:,.0f}",
                f"{obj.promo_price:,.0f}",
            )
        return f"TZS {obj.price:,.0f}"

    price_display.short_description = "Price"

    def data_display(self, obj):
        return obj.data_display

    data_display.short_description = "Data"

    def speed_display(self, obj):
        return obj.speed_display

    speed_display.short_description = "Speed"

    def customer_count_display(self, obj):
        count = obj.customer_count
        if count > 0:
            return format_html('<span style="font-weight: bold;">{}</span>', count)
        return "0"

    customer_count_display.short_description = "Customers"

    def popular_badge(self, obj):
        if obj.is_popular:
            return format_html(
                '<span style="background: #f59e0b; color: white; padding: 2px 8px; border-radius: 4px;">⭐ POPULAR</span>'
            )
        return "—"

    popular_badge.short_description = "Popular"


@admin.register(PPPCustomer)
class PPPCustomerAdmin(admin.ModelAdmin):
    """Manage PPPoE customer accounts"""

    list_display = [
        "username",
        "full_name",
        "tenant",
        "router",
        "profile",
        "plan",
        "status_badge",
        "billing_type",
        "effective_price_display",
        "paid_until",
        "synced_badge",
    ]
    list_filter = [
        "tenant",
        "router",
        "profile",
        "plan",
        "status",
        "billing_type",
        "synced_to_router",
    ]
    search_fields = [
        "username",
        "full_name",
        "phone_number",
        "email",
        "tenant__business_name",
    ]
    readonly_fields = [
        "mikrotik_id",
        "synced_to_router",
        "last_payment_date",
        "last_payment_amount",
        "control_number",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (None, {"fields": ("tenant", "router", "profile", "plan", "status")}),
        (
            "PPP Credentials",
            {"fields": ("username", "password", "service")},
        ),
        (
            "Customer Info",
            {"fields": ("full_name", "phone_number", "email", "address")},
        ),
        (
            "IP & Access Control",
            {"fields": ("static_ip", "mac_address", "caller_id")},
        ),
        (
            "Billing",
            {
                "fields": (
                    "billing_type",
                    "monthly_price",
                    "paid_until",
                    "last_payment_date",
                    "last_payment_amount",
                    "control_number",
                ),
            },
        ),
        (
            "Notes",
            {"fields": ("comment",)},
        ),
        (
            "MikroTik Sync",
            {
                "classes": ("collapse",),
                "fields": ("synced_to_router", "mikrotik_id"),
            },
        ),
        (
            "Timestamps",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    def status_badge(self, obj):
        colors = {
            "active": "#10b981",
            "suspended": "#f59e0b",
            "disabled": "#6b7280",
            "expired": "#ef4444",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 4px;">{}</span>',
            color,
            obj.status.upper(),
        )

    status_badge.short_description = "Status"

    def effective_price_display(self, obj):
        return f"TZS {obj.effective_price:,.0f}"

    effective_price_display.short_description = "Price"

    def synced_badge(self, obj):
        if obj.synced_to_router:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 8px; border-radius: 4px;">SYNCED</span>'
            )
        return format_html(
            '<span style="background: #f59e0b; color: white; padding: 2px 8px; border-radius: 4px;">PENDING</span>'
        )

    synced_badge.short_description = "Router Sync"


@admin.register(PPPPayment)
class PPPPaymentAdmin(admin.ModelAdmin):
    """Manage PPPoE customer payments"""

    list_display = [
        "order_reference",
        "customer",
        "tenant",
        "amount_display",
        "billing_days",
        "status_badge",
        "payment_channel",
        "control_number",
        "created_at",
        "completed_at",
    ]
    list_filter = ["status", "payment_channel", "tenant", "billing_days"]
    search_fields = [
        "order_reference",
        "payment_reference",
        "control_number",
        "phone_number",
        "customer__username",
        "customer__full_name",
    ]
    readonly_fields = [
        "order_reference",
        "payment_reference",
        "control_number",
        "created_at",
        "completed_at",
    ]
    raw_id_fields = ["customer", "tenant"]

    def amount_display(self, obj):
        return f"TZS {obj.amount:,.0f}"

    amount_display.short_description = "Amount"

    def status_badge(self, obj):
        colors = {
            "pending": "#f59e0b",
            "completed": "#10b981",
            "failed": "#ef4444",
            "expired": "#6b7280",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 4px;">{}</span>',
            color,
            obj.status.upper(),
        )

    status_badge.short_description = "Status"


# Set admin site properties
admin.site.site_header = "Kitonga SaaS Platform - Super Admin"
admin.site.site_title = "Kitonga SaaS Admin"
admin.site.index_title = "Kitonga Multi-Tenant WiFi Billing Platform"
