"""
Tests for Kitonga billing system
"""
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from .models import User, Payment, AccessLog
from .utils import format_phone_number, get_user_statistics


class UserModelTest(TestCase):
    """Test User model functionality"""
    
    def setUp(self):
        self.user = User.objects.create(phone_number='255712345678')
    
    def test_user_creation(self):
        """Test user is created correctly"""
        self.assertEqual(self.user.phone_number, '255712345678')
        self.assertFalse(self.user.is_active)
        self.assertIsNone(self.user.paid_until)
    
    def test_has_active_access_no_payment(self):
        """Test user without payment has no access"""
        self.assertFalse(self.user.has_active_access())
    
    def test_extend_access(self):
        """Test extending user access"""
        self.user.extend_access(hours=24)
        self.assertTrue(self.user.is_active)
        self.assertTrue(self.user.has_active_access())
        self.assertEqual(self.user.total_payments, 1)
    
    def test_expired_access(self):
        """Test expired access detection"""
        # Set paid_until to past
        self.user.paid_until = timezone.now() - timedelta(hours=1)
        self.user.is_active = True
        self.user.save()
        
        self.assertFalse(self.user.has_active_access())
    
    def test_deactivate_access(self):
        """Test deactivating user access"""
        self.user.is_active = True
        self.user.save()
        
        self.user.deactivate_access()
        self.assertFalse(self.user.is_active)


class PaymentModelTest(TestCase):
    """Test Payment model functionality"""
    
    def setUp(self):
        self.user = User.objects.create(phone_number='255712345678')
        self.payment = Payment.objects.create(
            user=self.user,
            amount=1000,
            phone_number='255712345678',
            transaction_id='test-123',
            status='pending'
        )
    
    def test_payment_creation(self):
        """Test payment is created correctly"""
        self.assertEqual(self.payment.status, 'pending')
        self.assertEqual(self.payment.amount, 1000)
    
    def test_mark_completed(self):
        """Test marking payment as completed"""
        self.payment.mark_completed('MPESA123')
        
        self.assertEqual(self.payment.status, 'completed')
        self.assertEqual(self.payment.mpesa_receipt_number, 'MPESA123')
        self.assertIsNotNone(self.payment.completed_at)
        
        # Check user access was extended
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertTrue(self.user.has_active_access())
    
    def test_mark_failed(self):
        """Test marking payment as failed"""
        self.payment.mark_failed()
        self.assertEqual(self.payment.status, 'failed')


class UtilsTest(TestCase):
    """Test utility functions"""
    
    def test_format_phone_number(self):
        """Test phone number formatting"""
        self.assertEqual(format_phone_number('0712345678'), '255712345678')
        self.assertEqual(format_phone_number('255712345678'), '255712345678')
        self.assertEqual(format_phone_number('712345678'), '255712345678')
        self.assertEqual(format_phone_number('0712 345 678'), '255712345678')
