"""
Management command to fix duplicate phone numbers by normalizing and merging users
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from billing.models import User, Payment, Device, AccessLog, Voucher
from billing.utils import normalize_phone_number, validate_tanzania_phone_number
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fix duplicate phone numbers by normalizing them and merging user accounts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making any changes',
        )
        parser.add_argument(
            '--phone',
            type=str,
            help='Fix specific phone number (in any format)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        specific_phone = options['phone']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        duplicates_found = 0
        users_merged = 0
        users_fixed = 0
        
        if specific_phone:
            # Fix specific phone number
            try:
                normalized = normalize_phone_number(specific_phone)
                self.stdout.write(f'Processing phone number: {specific_phone} -> {normalized}')
                
                users = User.objects.filter(
                    phone_number__in=[
                        specific_phone,
                        specific_phone.replace('+', ''),
                        '0' + specific_phone.replace('+255', ''),
                        '255' + specific_phone.replace('+255', '').replace('0', '', 1) if specific_phone.startswith('0') else None
                    ]
                ).exclude(phone_number=normalized)
                
                result = self._fix_phone_duplicates(normalized, users, dry_run)
                if result:
                    users_merged += result
                    
            except ValueError as e:
                self.stdout.write(self.style.ERROR(f'Invalid phone number {specific_phone}: {e}'))
                
        else:
            # Find all users and group by normalized phone number
            all_users = User.objects.all().order_by('created_at')
            phone_groups = {}
            
            for user in all_users:
                try:
                    # Try to normalize the current phone number
                    normalized = normalize_phone_number(user.phone_number)
                    
                    # Validate it's a Tanzania number
                    is_valid, network, normalized = validate_tanzania_phone_number(normalized)
                    
                    if is_valid:
                        if normalized not in phone_groups:
                            phone_groups[normalized] = []
                        phone_groups[normalized].append(user)
                    else:
                        self.stdout.write(
                            self.style.WARNING(f'Invalid Tanzania number: {user.phone_number} (User ID: {user.id})')
                        )
                        
                except ValueError as e:
                    self.stdout.write(
                        self.style.ERROR(f'Could not normalize {user.phone_number} (User ID: {user.id}): {e}')
                    )
            
            # Process each group
            for normalized_phone, user_list in phone_groups.items():
                if len(user_list) > 1:
                    duplicates_found += 1
                    self.stdout.write(f'\\nFound {len(user_list)} users with phone {normalized_phone}:')
                    
                    for user in user_list:
                        self.stdout.write(f'  - ID: {user.id}, Phone: {user.phone_number}, Created: {user.created_at}')
                    
                    # Keep the oldest user, merge others into it
                    primary_user = user_list[0]  # Already ordered by created_at
                    duplicate_users = user_list[1:]
                    
                    result = self._merge_users(primary_user, duplicate_users, normalized_phone, dry_run)
                    if result:
                        users_merged += result
                
                elif user_list[0].phone_number != normalized_phone:
                    # Single user but phone number needs normalization
                    user = user_list[0]
                    self.stdout.write(f'\\nNormalizing phone number for user {user.id}: {user.phone_number} -> {normalized_phone}')
                    
                    if not dry_run:
                        user.phone_number = normalized_phone
                        user.save()
                        
                    users_fixed += 1
        
        # Summary
        self.stdout.write('\\n' + '='*50)
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN SUMMARY (no changes made):'))
        else:
            self.stdout.write(self.style.SUCCESS('SUMMARY:'))
            
        self.stdout.write(f'Phone number groups with duplicates: {duplicates_found}')
        self.stdout.write(f'Users merged: {users_merged}')
        self.stdout.write(f'Phone numbers normalized: {users_fixed}')

    def _fix_phone_duplicates(self, normalized_phone, duplicate_users, dry_run):
        """Fix duplicates for a specific phone number"""
        if not duplicate_users:
            return 0
            
        try:
            # Try to get the primary user with normalized phone
            primary_user = User.objects.get(phone_number=normalized_phone)
            self.stdout.write(f'  Primary user: ID {primary_user.id}')
        except User.DoesNotExist:
            # No user with normalized phone exists, use the oldest duplicate
            primary_user = duplicate_users.order_by('created_at').first()
            duplicate_users = duplicate_users.exclude(id=primary_user.id)
            
            self.stdout.write(f'  Setting primary user: ID {primary_user.id} -> {normalized_phone}')
            if not dry_run:
                primary_user.phone_number = normalized_phone
                primary_user.save()
        
        return self._merge_users(primary_user, duplicate_users, normalized_phone, dry_run)

    def _merge_users(self, primary_user, duplicate_users, normalized_phone, dry_run):
        """Merge duplicate users into primary user"""
        merged_count = 0
        
        for duplicate_user in duplicate_users:
            self.stdout.write(f'  Merging user {duplicate_user.id} into {primary_user.id}')
            
            if not dry_run:
                with transaction.atomic():
                    # Update primary user's paid_until to the latest
                    if duplicate_user.paid_until:
                        if not primary_user.paid_until or duplicate_user.paid_until > primary_user.paid_until:
                            primary_user.paid_until = duplicate_user.paid_until
                    
                    # Merge other fields
                    primary_user.is_active = primary_user.is_active or duplicate_user.is_active
                    primary_user.total_payments += duplicate_user.total_payments
                    primary_user.max_devices = max(primary_user.max_devices or 1, duplicate_user.max_devices or 1)
                    
                    # Ensure normalized phone number
                    primary_user.phone_number = normalized_phone
                    primary_user.save()
                    
                    # Move payments
                    Payment.objects.filter(user=duplicate_user).update(user=primary_user)
                    
                    # Move devices (handle unique constraint)
                    for device in Device.objects.filter(user=duplicate_user):
                        existing_device = Device.objects.filter(
                            user=primary_user, 
                            mac_address=device.mac_address
                        ).first()
                        
                        if existing_device:
                            # Merge device info
                            if device.last_seen > existing_device.last_seen:
                                existing_device.ip_address = device.ip_address
                                existing_device.device_name = device.device_name or existing_device.device_name
                                existing_device.last_seen = device.last_seen
                                existing_device.is_active = device.is_active or existing_device.is_active
                                existing_device.save()
                            device.delete()
                        else:
                            device.user = primary_user
                            device.save()
                    
                    # Move access logs
                    AccessLog.objects.filter(user=duplicate_user).update(user=primary_user)
                    
                    # Move voucher usage
                    Voucher.objects.filter(used_by=duplicate_user).update(used_by=primary_user)
                    
                    # Delete the duplicate user
                    duplicate_user.delete()
                    
                    merged_count += 1
        
        return merged_count
