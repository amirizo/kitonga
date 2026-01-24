"""
Management command to run subscription-related tasks
Should be run daily via cron:
    0 6 * * * cd /path/to/kitonga && python manage.py subscription_tasks
"""
from django.core.management.base import BaseCommand
from billing.subscription import (
    check_expiring_subscriptions,
    suspend_expired_subscriptions,
    expire_trials
)


class Command(BaseCommand):
    help = 'Run subscription management tasks (expiry checks, reminders, suspensions)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--reminders-only',
            action='store_true',
            help='Only send expiry reminders, do not suspend accounts'
        )
        parser.add_argument(
            '--suspend-only',
            action='store_true',
            help='Only suspend expired accounts'
        )
        parser.add_argument(
            '--trials-only',
            action='store_true',
            help='Only handle trial expirations'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Running subscription tasks...'))
        
        if options.get('reminders_only'):
            count = check_expiring_subscriptions()
            self.stdout.write(self.style.SUCCESS(f'Sent {count} expiry reminders'))
            return
        
        if options.get('suspend_only'):
            count = suspend_expired_subscriptions()
            self.stdout.write(self.style.SUCCESS(f'Suspended {count} expired subscriptions'))
            return
        
        if options.get('trials_only'):
            count = expire_trials()
            self.stdout.write(self.style.SUCCESS(f'Expired {count} trials'))
            return
        
        # Run all tasks
        self.stdout.write('1. Checking expiring subscriptions...')
        reminders = check_expiring_subscriptions()
        self.stdout.write(f'   Sent {reminders} expiry reminders')
        
        self.stdout.write('2. Suspending expired subscriptions...')
        suspended = suspend_expired_subscriptions()
        self.stdout.write(f'   Suspended {suspended} accounts')
        
        self.stdout.write('3. Handling trial expirations...')
        trials = expire_trials()
        self.stdout.write(f'   Expired {trials} trials')
        
        self.stdout.write(self.style.SUCCESS(
            f'\nSubscription tasks completed!\n'
            f'- Reminders sent: {reminders}\n'
            f'- Subscriptions suspended: {suspended}\n'
            f'- Trials expired: {trials}'
        ))
