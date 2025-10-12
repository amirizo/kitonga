"""
Django admin configuration for Kitonga Wi-Fi with Jazzmin
"""
from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from django.http import HttpResponse
from django.utils.html import format_html
from django.utils import timezone
import csv
from .models import User, Payment, AccessLog, Voucher, Bundle, Device, SMSLog, PaymentWebhook
from .views import dashboard_stats

class KitongaAdminSite(admin.AdminSite):
    """Custom admin site with dashboard link"""
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_view(self.dashboard_view), name='billing_statistics'),
        ]
        return custom_urls + urls
    
    def dashboard_view(self, request):
        """Redirect to dashboard stats view"""
        return dashboard_stats(request)

# Use default admin site for Jazzmin
# admin_site = KitongaAdminSite()

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'is_active', 'access_status', 'paid_until', 'total_payments', 'device_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['phone_number']
    readonly_fields = ['created_at', 'total_payments']
    ordering = ['-created_at']
    
    def access_status(self, obj):
        """Display access status with color coding"""
        if obj.is_active and obj.paid_until and obj.paid_until > timezone.now():
            return format_html('<span style="color: green;">✓ Active</span>')
        else:
            return format_html('<span style="color: red;">✗ Inactive</span>')
    access_status.short_description = 'Access Status'
    
    def device_count(self, obj):
        """Count of active devices"""
        return obj.devices.filter(is_active=True).count()
    device_count.short_description = 'Active Devices'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('devices')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'amount_formatted', 'status_badge', 'payment_reference', 'payment_channel', 'bundle_name', 'created_at']
    list_filter = ['status', 'payment_channel', 'created_at', 'bundle']
    search_fields = ['phone_number', 'payment_reference', 'transaction_id', 'order_reference']
    readonly_fields = ['created_at', 'completed_at']
    ordering = ['-created_at']
    
    def amount_formatted(self, obj):
        """Format amount with currency"""
        return f"TSh {obj.amount:,}"
    amount_formatted.short_description = 'Amount'
    
    def status_badge(self, obj):
        """Display status with color badges"""
        if obj.status == 'COMPLETED':
            return format_html('<span style="background: green; color: white; padding: 2px 8px; border-radius: 4px;">COMPLETED</span>')
        elif obj.status == 'PENDING':
            return format_html('<span style="background: orange; color: white; padding: 2px 8px; border-radius: 4px;">PENDING</span>')
        elif obj.status == 'FAILED':
            return format_html('<span style="background: red; color: white; padding: 2px 8px; border-radius: 4px;">FAILED</span>')
        else:
            return obj.status
    status_badge.short_description = 'Status'
    
    def bundle_name(self, obj):
        """Display bundle name"""
        return obj.bundle.name if obj.bundle else '-'
    bundle_name.short_description = 'Bundle'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'bundle')


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['user_phone', 'device_name', 'mac_address', 'ip_address', 'is_active', 'first_seen', 'last_seen']
    list_filter = ['is_active', 'first_seen']
    search_fields = ['user__phone_number', 'mac_address', 'ip_address', 'device_name']
    readonly_fields = ['first_seen', 'last_seen']
    ordering = ['-last_seen']
    
    def user_phone(self, obj):
        """Display user phone number"""
        return obj.user.phone_number
    user_phone.short_description = 'User Phone'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user')


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ['user_phone', 'ip_address', 'mac_address', 'access_granted_badge', 'denial_reason', 'timestamp']
    list_filter = ['access_granted', 'timestamp', 'denial_reason']
    search_fields = ['user__phone_number', 'ip_address', 'mac_address']
    readonly_fields = ['timestamp']
    ordering = ['-timestamp']
    
    def user_phone(self, obj):
        """Display user phone number"""
        return obj.user.phone_number if obj.user else '-'
    user_phone.short_description = 'User Phone'
    
    def access_granted_badge(self, obj):
        """Display access status with badges"""
        if obj.access_granted:
            return format_html('<span style="background: green; color: white; padding: 2px 8px; border-radius: 4px;">GRANTED</span>')
        else:
            return format_html('<span style="background: red; color: white; padding: 2px 8px; border-radius: 4px;">DENIED</span>')
    access_granted_badge.short_description = 'Access'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user')


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'sms_type', 'success_badge', 'sent_at']
    list_filter = ['sms_type', 'success', 'sent_at']
    search_fields = ['phone_number', 'message']
    readonly_fields = ['sent_at']
    ordering = ['-sent_at']
    
    def success_badge(self, obj):
        """Display success status with badges"""
        if obj.success:
            return format_html('<span style="background: green; color: white; padding: 2px 8px; border-radius: 4px;">SUCCESS</span>')
        else:
            return format_html('<span style="background: red; color: white; padding: 2px 8px; border-radius: 4px;">FAILED</span>')
    success_badge.short_description = 'Status'


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ['code', 'duration_days', 'status_badge', 'batch_id', 'created_at', 'used_at', 'used_by_phone']
    list_filter = ['is_used', 'duration_hours', 'created_at', 'batch_id']
    search_fields = ['code', 'batch_id', 'used_by__phone_number']
    readonly_fields = ['code', 'created_at', 'used_at', 'is_used']
    ordering = ['-created_at']
    
    actions = ['export_vouchers_csv', 'mark_as_used', 'mark_as_unused']
    
    def duration_days(self, obj):
        """Display duration in days"""
        days = obj.duration_hours // 24
        return f"{days} days ({obj.duration_hours}h)"
    duration_days.short_description = 'Duration'
    
    def status_badge(self, obj):
        """Display voucher status with badges"""
        if obj.is_used:
            return format_html('<span style="background: red; color: white; padding: 2px 8px; border-radius: 4px;">USED</span>')
        else:
            return format_html('<span style="background: green; color: white; padding: 2px 8px; border-radius: 4px;">AVAILABLE</span>')
    status_badge.short_description = 'Status'
    
    def used_by_phone(self, obj):
        """Display phone number of user who redeemed voucher"""
        return obj.used_by.phone_number if obj.used_by else '-'
    used_by_phone.short_description = 'Used By'
    
    def export_vouchers_csv(self, request, queryset):
        """Export selected vouchers to CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="vouchers.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Code', 'Duration (Hours)', 'Status', 'Batch ID', 'Created At', 'Used At', 'Used By'])
        
        for voucher in queryset:
            writer.writerow([
                voucher.code,
                voucher.duration_hours,
                'Used' if voucher.is_used else 'Available',
                voucher.batch_id,
                voucher.created_at.strftime('%Y-%m-%d %H:%M'),
                voucher.used_at.strftime('%Y-%m-%d %H:%M') if voucher.used_at else '-',
                voucher.used_by.phone_number if voucher.used_by else '-'
            ])
        
        return response
    export_vouchers_csv.short_description = 'Export selected vouchers to CSV'
    
    def mark_as_used(self, request, queryset):
        """Mark selected vouchers as used (for testing)"""
        updated = queryset.update(is_used=True)
        self.message_user(request, f'{updated} vouchers marked as used.')
    mark_as_used.short_description = 'Mark as used'
    
    def mark_as_unused(self, request, queryset):
        """Mark selected vouchers as unused (for testing)"""
        updated = queryset.filter(is_used=True).update(is_used=False, used_at=None, used_by=None)
        self.message_user(request, f'{updated} vouchers marked as unused.')
    mark_as_unused.short_description = 'Mark as unused'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('used_by')


@admin.register(PaymentWebhook)
class PaymentWebhookAdmin(admin.ModelAdmin):
    list_display = ['order_reference', 'event_type', 'processing_status_badge', 'payment_status', 'amount_formatted', 'received_at', 'processed_at']
    list_filter = ['event_type', 'processing_status', 'payment_status', 'received_at']
    search_fields = ['order_reference', 'transaction_id', 'source_ip']
    readonly_fields = ['received_at', 'processed_at', 'raw_payload', 'source_ip', 'user_agent']
    ordering = ['-received_at']
    
    fieldsets = (
        ('Webhook Information', {
            'fields': ('event_type', 'processing_status', 'processing_error', 'received_at', 'processed_at')
        }),
        ('Payment Data', {
            'fields': ('order_reference', 'transaction_id', 'payment_status', 'channel', 'amount', 'payment')
        }),
        ('Request Metadata', {
            'fields': ('source_ip', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Raw Data', {
            'fields': ('raw_payload',),
            'classes': ('collapse',)
        }),
    )
    
    def processing_status_badge(self, obj):
        """Display processing status with color badges"""
        colors = {
            'received': 'blue',
            'processed': 'green',
            'failed': 'red',
            'ignored': 'gray'
        }
        color = colors.get(obj.processing_status, 'gray')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 4px; text-transform: uppercase;">{}</span>',
            color, obj.processing_status
        )
    processing_status_badge.short_description = 'Processing Status'
    
    def amount_formatted(self, obj):
        """Format amount with currency"""
        if obj.amount:
            return f"TSh {obj.amount:,}"
        return '-'
    amount_formatted.short_description = 'Amount'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('payment')


@admin.register(Bundle)
class BundleAdmin(admin.ModelAdmin):
    list_display = ['name', 'duration_days_formatted', 'price_formatted', 'price', 'is_active_badge', 'is_active', 'display_order', 'payment_count']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    list_editable = ['price', 'is_active', 'display_order']
    ordering = ['display_order']
    
    def duration_days_formatted(self, obj):
        """Display duration in days"""
        days = obj.duration_hours // 24
        return f"{days} days"
    duration_days_formatted.short_description = 'Duration'
    
    def price_formatted(self, obj):
        """Format price with currency"""
        return f"TSh {obj.price:,}"
    price_formatted.short_description = 'Price'
    
    def is_active_badge(self, obj):
        """Display active status with badges"""
        if obj.is_active:
            return format_html('<span style="background: green; color: white; padding: 2px 8px; border-radius: 4px;">ACTIVE</span>')
        else:
            return format_html('<span style="background: gray; color: white; padding: 2px 8px; border-radius: 4px;">INACTIVE</span>')
    is_active_badge.short_description = 'Status'
    
    def payment_count(self, obj):
        """Count of payments for this bundle"""
        return obj.payments.filter(status='COMPLETED').count()
    payment_count.short_description = 'Sales Count'

# Set admin site properties
admin.site.site_header = "Kitonga Wi-Fi Administration"
admin.site.site_title = "Kitonga Admin"
admin.site.index_title = "Welcome to Kitonga Wi-Fi Management"
