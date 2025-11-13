"""
Django management command to disconnect expired users
Run with: python manage.py disconnect_expired_users
"""
from django.core.management.base import BaseCommand
from billing.tasks import disconnect_expired_users, cleanup_inactive_devices


class Command(BaseCommand):
    help = 'Disconnect users whose Wi-Fi access has expired'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup-devices',
            action='store_true',
            help='Also cleanup inactive devices',
        )

    def handle(self, *args, **options):
        self.stdout.write('Checking for expired users...')
        
        result = disconnect_expired_users()
        
        if result['success']:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Disconnected {result["disconnected"]} expired users'
                )
            )
            if result['failed'] > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠ Failed to disconnect {result["failed"]} users'
                    )
                )
        else:
            self.stdout.write(
                self.style.ERROR(f'✗ Error: {result.get("error", "Unknown error")}')
            )
        
        if options['cleanup_devices']:
            self.stdout.write('\nCleaning up inactive devices...')
            device_result = cleanup_inactive_devices()
            
            if device_result['success']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Deactivated {device_result["deactivated"]} inactive devices'
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'✗ Error: {device_result.get("error", "Unknown error")}')
                )
        
        self.stdout.write('\nDone!')
