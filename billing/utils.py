"""
Utility functions for billing system
"""
from django.utils import timezone
from django.db import models
from datetime import timedelta
from .models import User, Payment
import logging

logger = logging.getLogger(__name__)


def format_phone_number(phone_number):
    """
    Format phone number to standard Tanzania format (255XXXXXXXXX)
    """
    # Remove spaces and special characters
    phone = phone_number.replace(' ', '').replace('-', '').replace('+', '')
    
    # Handle different formats
    if phone.startswith('0'):
        phone = '255' + phone[1:]  # Convert 0712345678 to 255712345678
    elif phone.startswith('255'):  # Already correct Tanzania format
        pass
    elif phone.startswith('254'):  # Convert Kenya to Tanzania (if mistakenly entered)
        phone = '255' + phone[3:]
    else:
        phone = '255' + phone  # Add Tanzania prefix for local numbers
    
    return phone


def get_user_statistics(user):
    """
    Get statistics for a user
    """
    # Calculate actual total spent from payments
    total_spent = Payment.objects.filter(
        user=user,
        status='completed'
    ).aggregate(total=models.Sum('amount'))['total'] or 0
    
    successful_payments = Payment.objects.filter(
        user=user,
        status='completed'
    ).count()
    
    failed_payments = Payment.objects.filter(
        user=user,
        status='failed'
    ).count()
    
    last_payment = Payment.objects.filter(
        user=user,
        status='completed'
    ).order_by('-completed_at').first()
    
    return {
        'total_spent': float(total_spent),
        'successful_payments': successful_payments,
        'failed_payments': failed_payments,
        'last_payment_date': last_payment.completed_at if last_payment else None,
        'member_since': user.created_at
    }


def check_and_deactivate_expired_users():
    """
    Check and deactivate users with expired access
    Can be called from a scheduled task
    """
    now = timezone.now()
    expired_users = User.objects.filter(
        is_active=True,
        paid_until__lt=now
    )
    
    count = 0
    for user in expired_users:
        user.deactivate_access()
        count += 1
        logger.info(f'Deactivated expired user: {user.phone_number}')
    
    return count


def get_active_users_count():
    """
    Get count of currently active users
    """
    now = timezone.now()
    return User.objects.filter(
        is_active=True,
        paid_until__gt=now
    ).count()


def get_revenue_statistics(days=30):
    """
    Get revenue statistics for the specified period
    """
    from_date = timezone.now() - timedelta(days=days)
    
    completed_payments = Payment.objects.filter(
        status='completed',
        completed_at__gte=from_date
    )
    
    # Calculate actual total revenue from payment amounts
    total_revenue = completed_payments.aggregate(
        total=models.Sum('amount')
    )['total'] or 0
    
    total_transactions = completed_payments.count()
    unique_users = completed_payments.values('user').distinct().count()
    
    return {
        'period_days': days,
        'total_revenue': float(total_revenue),
        'total_transactions': total_transactions,
        'unique_users': unique_users,
        'average_per_user': float(total_revenue) / unique_users if unique_users > 0 else 0
    }
