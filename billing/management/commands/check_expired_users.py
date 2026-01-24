"""
Management command to check and deactivate expired users
Run this periodically via cron job
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from billing.models import User


class Command(BaseCommand):
    help = 'Check and deactivate users with expired access'

    def handle(self, *args, **options):
        now = timezone.now()
        expired_users = User.objects.filter(
            is_active=True,
            paid_until__lt=now
        )
        
        count = expired_users.count()
        
        for user in expired_users:
            user.deactivate_access()
            self.stdout.write(
                self.style.WARNING(f'Deactivated user: {user.phone_number}')
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully deactivated {count} expired users')
        )
