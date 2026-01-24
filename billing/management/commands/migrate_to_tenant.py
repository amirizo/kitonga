"""
Management command to migrate existing data to multi-tenant structure
"""
from django.core.management.base import BaseCommand
from django.db import transaction, connection
from billing.models import (
    Tenant, User, Bundle, Payment, Device, 
    AccessLog, Voucher, SMSLog, PaymentWebhook
)


class Command(BaseCommand):
    help = 'Migrate existing data to multi-tenant structure by assigning a default tenant'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-slug',
            type=str,
            default='default',
            help='Slug of the tenant to assign existing data to',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without making changes',
        )
    
    def handle(self, *args, **options):
        tenant_slug = options['tenant_slug']
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        try:
            tenant = Tenant.objects.get(slug=tenant_slug)
        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f'Tenant with slug "{tenant_slug}" not found.\n'
                f'Run: python manage.py setup_saas --create-tenant first'
            ))
            return
        
        self.stdout.write(f'Migrating data to tenant: {tenant.business_name} ({tenant.slug})')
        
        with transaction.atomic():
            # Migrate Bundles
            bundles = Bundle.objects.filter(tenant__isnull=True)
            bundle_count = bundles.count()
            if not dry_run:
                bundles.update(tenant=tenant)
            self.stdout.write(f'  Bundles: {bundle_count}')
            
            # Migrate WiFi Users
            users = User.objects.filter(tenant__isnull=True)
            user_count = users.count()
            if not dry_run:
                users.update(tenant=tenant)
            self.stdout.write(f'  WiFi Users: {user_count}')
            
            # Migrate Devices - handle duplicate MAC addresses
            devices = Device.objects.filter(tenant__isnull=True)
            device_count = devices.count()
            if not dry_run:
                # Update one by one to handle duplicates gracefully
                for device in devices:
                    # Check if this MAC already exists for this tenant
                    existing = Device.objects.filter(tenant=tenant, mac_address=device.mac_address).exists()
                    if not existing:
                        device.tenant = tenant
                        device.save(update_fields=['tenant'])
                    else:
                        # Delete duplicate device
                        device.delete()
            self.stdout.write(f'  Devices: {device_count}')
            
            # Migrate Payments
            payments = Payment.objects.filter(tenant__isnull=True)
            payment_count = payments.count()
            if not dry_run:
                payments.update(tenant=tenant)
            self.stdout.write(f'  Payments: {payment_count}')
            
            # Migrate Vouchers
            vouchers = Voucher.objects.filter(tenant__isnull=True)
            voucher_count = vouchers.count()
            if not dry_run:
                vouchers.update(tenant=tenant)
            self.stdout.write(f'  Vouchers: {voucher_count}')
            
            # Migrate Access Logs
            access_logs = AccessLog.objects.filter(tenant__isnull=True)
            access_log_count = access_logs.count()
            if not dry_run:
                access_logs.update(tenant=tenant)
            self.stdout.write(f'  Access Logs: {access_log_count}')
            
            # Migrate SMS Logs
            sms_logs = SMSLog.objects.filter(tenant__isnull=True)
            sms_log_count = sms_logs.count()
            if not dry_run:
                sms_logs.update(tenant=tenant)
            self.stdout.write(f'  SMS Logs: {sms_log_count}')
            
            # Migrate Payment Webhooks
            webhooks = PaymentWebhook.objects.filter(tenant__isnull=True)
            webhook_count = webhooks.count()
            if not dry_run:
                webhooks.update(tenant=tenant)
            self.stdout.write(f'  Payment Webhooks: {webhook_count}')
            
            if dry_run:
                self.stdout.write(self.style.WARNING('\nDRY RUN - No changes made. Remove --dry-run to apply.'))
                # Rollback in dry-run mode
                transaction.set_rollback(True)
            else:
                total = (bundle_count + user_count + device_count + payment_count + 
                        voucher_count + access_log_count + sms_log_count + webhook_count)
                self.stdout.write(self.style.SUCCESS(f'\n✓ Migrated {total} records to tenant "{tenant.slug}"'))
