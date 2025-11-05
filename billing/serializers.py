"""
Serializers for API requests and responses
"""
from rest_framework import serializers
from .models import User, Payment, AccessLog, Voucher, Bundle, Device


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
                  'max_devices', 'active_devices', 'device_limit_reached', 'created_at']
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
        # Remove spaces and special characters
        value = value.replace(' ', '').replace('-', '').replace('+', '')
        
        # Validate format
        if not value.isdigit():
            raise serializers.ValidationError('Phone number must contain only digits')
        
        # Validate length (Tanzanian numbers)
        if len(value) < 9 or len(value) > 12:
            raise serializers.ValidationError('Invalid phone number length')
        
        return value
    
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
        # Remove spaces and special characters
        value = value.replace(' ', '').replace('-', '').replace('+', '')
        
        # Validate format
        if not value.isdigit():
            raise serializers.ValidationError('Phone number must contain only digits')
        
        # Validate length (Tanzanian numbers)
        if len(value) < 9 or len(value) > 12:
            raise serializers.ValidationError('Invalid phone number length')
        
        return value


class RedeemVoucherSerializer(serializers.Serializer):
    voucher_code = serializers.CharField(max_length=16)
    phone_number = serializers.CharField(max_length=15)
    # Optional device information for immediate access setup
    ip_address = serializers.IPAddressField(required=False)
    mac_address = serializers.CharField(max_length=17, required=False)
    
    def validate_voucher_code(self, value):
        # Remove spaces and convert to uppercase
        value = value.replace(' ', '').replace('-', '').upper()
        
        # Add dashes back in correct format
        if len(value) == 12:
            value = f"{value[:4]}-{value[4:8]}-{value[8:]}"
        
        return value
    
    def validate_phone_number(self, value):
        # Remove spaces and special characters
        value = value.replace(' ', '').replace('-', '').replace('+', '')
        
        # Validate format
        if not value.isdigit():
            raise serializers.ValidationError('Phone number must contain only digits')
        
        return value
    
    def validate_mac_address(self, value):
        if value:
            # Basic MAC address format validation
            import re
            if not re.match(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', value):
                raise serializers.ValidationError('Invalid MAC address format')
        return value
