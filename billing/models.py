"""
Database models for Kitonga Wi-Fi Billing System
"""
from django.db import models
from django.utils import timezone
from django.conf import settings
from datetime import timedelta


class Bundle(models.Model):
    """
    Bundle packages for different access durations
    """
    name = models.CharField(max_length=50, unique=True)
    duration_hours = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    display_order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['display_order', 'duration_hours']
    
    def __str__(self):
        return f"{self.name} - {self.duration_hours}hrs - TSh {self.price}"
    
    @property
    def duration_days(self):
        """Get duration in days"""
        return self.duration_hours // 24


class User(models.Model):
    """
    User model - identified by phone number
    """
    phone_number = models.CharField(max_length=15, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    total_payments = models.IntegerField(default=0)
    expiry_notification_sent = models.BooleanField(default=False)
    max_devices = models.IntegerField(default=1)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.phone_number} - Active: {self.is_active}"
    
    def save(self, *args, **kwargs):
        """Override save to ensure max_devices defaults to 1"""
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
    
    def extend_access(self, hours=24, source='payment'):
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
        if source == 'payment':
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


class Device(models.Model):
    """
    Device model to track user devices
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    mac_address = models.CharField(max_length=17, db_index=True)
    ip_address = models.GenericIPAddressField()
    device_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-last_seen']
        unique_together = ['user', 'mac_address']
    
    def __str__(self):
        return f"{self.user.phone_number} - {self.mac_address} - {'Active' if self.is_active else 'Inactive'}"


class Payment(models.Model):
    """
    Payment transaction model
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    bundle = models.ForeignKey(Bundle, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=15)
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    transaction_id = models.CharField(max_length=100, unique=True)
    order_reference = models.CharField(max_length=100, unique=True, null=True, blank=True)
    payment_channel = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.phone_number} - TSh {self.amount} - {self.status}"
    
    def mark_completed(self, payment_reference=None, channel=None):
        """Mark payment as completed and extend user access"""
        self.status = 'completed'
        self.payment_reference = payment_reference
        self.payment_channel = channel
        self.completed_at = timezone.now()
        self.save()
        
        # Extend user access based on bundle duration, specify source as payment
        if self.bundle:
            self.user.extend_access(hours=self.bundle.duration_hours, source='payment')
        else:
            # Default to 24 hours if no bundle specified
            self.user.extend_access(hours=24, source='payment')
    
    def mark_failed(self):
        """Mark payment as failed"""
        self.status = 'failed'
        self.save()


class AccessLog(models.Model):
    """
    Log of user access attempts and sessions
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='access_logs')
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True, related_name='access_logs')
    ip_address = models.GenericIPAddressField()
    mac_address = models.CharField(max_length=17, blank=True)
    access_granted = models.BooleanField(default=False)
    denial_reason = models.CharField(max_length=100, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user.phone_number} - {self.ip_address} - {'Granted' if self.access_granted else 'Denied'}"


class Voucher(models.Model):
    """
    Voucher code model for offline access
    Allows users to redeem codes for Wi-Fi access without online payment
    """
    DURATION_CHOICES = [
        (24, '24 Hours (1 Day)'),
        (168, '168 Hours (7 Days)'),
        (720, '720 Hours (30 Days)'),
    ]
    
    code = models.CharField(max_length=16, unique=True, db_index=True)
    duration_hours = models.IntegerField(choices=DURATION_CHOICES, default=24)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=100, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='vouchers_used')
    batch_id = models.CharField(max_length=50, blank=True, db_index=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.code} - {self.duration_hours}hrs - {'Used' if self.is_used else 'Available'}"
    
    def redeem(self, user):
        """Redeem voucher for a user and extend their access"""
        if self.is_used:
            return False, "Voucher has already been used"
        
        self.is_used = True
        self.used_at = timezone.now()
        self.used_by = user
        self.save()
        
        # Extend user access, specify source as voucher
        user.extend_access(hours=self.duration_hours, source='voucher')
        
        return True, f"Voucher redeemed successfully. Access granted for {self.duration_hours} hours."
    
    @staticmethod
    def generate_code():
        """Generate a unique voucher code"""
        import random
        import string
        
        while True:
            # Generate format: XXXX-XXXX-XXXX
            code = '-'.join([
                ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                for _ in range(3)
            ])
            
            # Check if code already exists
            if not Voucher.objects.filter(code=code).exists():
                return code


class SMSLog(models.Model):
    """
    Log of SMS notifications sent
    """
    SMS_TYPE_CHOICES = [
        ('payment', 'Payment Confirmation'),
        ('expiry_warning', 'Expiry Warning'),
        ('expired', 'Access Expired'),
        ('voucher', 'Voucher Redemption'),
        ('other', 'Other'),
    ]
    
    phone_number = models.CharField(max_length=15, db_index=True)
    message = models.TextField()
    sms_type = models.CharField(max_length=20, choices=SMS_TYPE_CHOICES, default='other')
    success = models.BooleanField(default=False)
    response_data = models.JSONField(null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-sent_at']
    
    def __str__(self):
        return f"{self.phone_number} - {self.sms_type} - {'Sent' if self.success else 'Failed'}"


class PaymentWebhook(models.Model):
    """
    Log of payment webhooks received from ClickPesa
    Tracks all webhook events for debugging and audit purposes
    """
    WEBHOOK_EVENT_CHOICES = [
        ('PAYMENT RECEIVED', 'Payment Received'),
        ('PAYMENT FAILED', 'Payment Failed'),
        ('PAYMENT PENDING', 'Payment Pending'),
        ('PAYMENT CANCELLED', 'Payment Cancelled'),
        ('OTHER', 'Other'),
    ]
    
    PROCESSING_STATUS_CHOICES = [
        ('received', 'Received'),
        ('processed', 'Processed Successfully'),
        ('failed', 'Processing Failed'),
        ('ignored', 'Ignored'),
    ]
    
    # Webhook metadata
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_status = models.CharField(max_length=20, choices=PROCESSING_STATUS_CHOICES, default='received')
    processing_error = models.TextField(blank=True)
    
    # ClickPesa webhook data
    event_type = models.CharField(max_length=50, choices=WEBHOOK_EVENT_CHOICES, default='OTHER')
    order_reference = models.CharField(max_length=100, db_index=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    payment_status = models.CharField(max_length=50, blank=True, null=True)
    channel = models.CharField(max_length=50, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Raw webhook payload for debugging
    raw_payload = models.JSONField()
    
    # Related payment record (if found)
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name='webhook_logs')
    
    # Request metadata
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['order_reference', '-received_at']),
            models.Index(fields=['event_type', '-received_at']),
            models.Index(fields=['processing_status', '-received_at']),
        ]
    
    def __str__(self):
        return f"{self.order_reference} - {self.event_type} - {self.processing_status}"
    
    def mark_processed(self, payment=None):
        """Mark webhook as successfully processed"""
        self.processing_status = 'processed'
        self.processed_at = timezone.now()
        if payment:
            self.payment = payment
        self.save()
    
    def mark_failed(self, error_message):
        """Mark webhook processing as failed"""
        self.processing_status = 'failed'
        self.processed_at = timezone.now()
        self.processing_error = error_message
        self.save()
    
    def mark_ignored(self, reason):
        """Mark webhook as ignored (e.g., duplicate, invalid)"""
        self.processing_status = 'ignored'
        self.processed_at = timezone.now()
        self.processing_error = reason
        self.save()
    
    @property
    def is_duplicate(self):
        """Check if this webhook is a duplicate"""
        return PaymentWebhook.objects.filter(
            order_reference=self.order_reference,
            event_type=self.event_type,
            processing_status='processed',
            received_at__lt=self.received_at
        ).exists()
