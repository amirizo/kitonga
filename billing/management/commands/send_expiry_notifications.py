"""
Management command to send expiry notifications
Run this as a cron job every hour
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from billing.models import User, SMSLog
from billing.nextsms import NextSMSAPI
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send SMS notifications to users whose access is about to expire'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=2,
            help='Send notification X hours before expiry (default: 2)'
        )

    def handle(self, *args, **options):
        hours_before = options['hours']
        now = timezone.now()
        warning_time = now + timedelta(hours=hours_before)
        
        # Find users whose access expires within the warning period
        users_to_notify = User.objects.filter(
            is_active=True,
            paid_until__lte=warning_time,
            paid_until__gt=now,
            expiry_notification_sent=False
        )
        
        self.stdout.write(f'Found {users_to_notify.count()} users to notify')
        
        nextsms = NextSMSAPI()
        sent_count = 0
        failed_count = 0
        
        for user in users_to_notify:
            # Calculate hours remaining
            time_remaining = user.paid_until - now
            hours_remaining = int(time_remaining.total_seconds() // 3600)
            
            # Send SMS
            result = nextsms.send_expiry_warning(user.phone_number, hours_remaining)
            
            # Log SMS
            SMSLog.objects.create(
                phone_number=user.phone_number,
                message=f'Expiry warning: {hours_remaining} hours remaining',
                sms_type='expiry_warning',
                success=result['success'],
                response_data=result.get('data')
            )
            
            if result['success']:
                # Mark notification as sent
                user.expiry_notification_sent = True
                user.save()
                sent_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Sent to {user.phone_number}'))
            else:
                failed_count += 1
                self.stdout.write(self.style.ERROR(f'✗ Failed to send to {user.phone_number}'))
        
        self.stdout.write(self.style.SUCCESS(
            f'\nCompleted: {sent_count} sent, {failed_count} failed'
        ))
