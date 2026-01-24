from django.core.management.base import BaseCommand
from billing.models import User, Device, AccessLog
from django.utils import timezone
from django.test import RequestFactory
import json
import logging

class Command(BaseCommand):
    help = 'Fix device tracking issues and verify device counting'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--verify-only',
            action='store_true',
            help='Only verify device tracking, do not fix',
        )
        parser.add_argument(
            '--test-user',
            type=str,
            help='Test specific user phone number',
        )
    
    def handle(self, *args, **options):
        self.stdout.write("=" * 50)
        self.stdout.write("KITONGA DEVICE TRACKING FIX")
        self.stdout.write("=" * 50)
        
        if not options['verify_only']:
            self.fix_device_tracking()
        
        self.verify_device_tracking()
        
        if options['test_user']:
            self.test_specific_user(options['test_user'])
        else:
            self.test_api_response()
        
        self.stdout.write(
            self.style.SUCCESS("\n✅ DEVICE TRACKING FIX COMPLETED")
        )
    
    def fix_device_tracking(self):
        """Fix device tracking issues for all users"""
        self.stdout.write("\n🔧 Fixing device tracking issues...")
        
        users_fixed = 0
        total_users = User.objects.count()
        
        for user in User.objects.all():
            try:
                fixed = False
                
                # Fix max_devices if not set
                if not user.max_devices or user.max_devices <= 0:
                    user.max_devices = 3
                    user.save()
                    fixed = True
                    self.stdout.write(f"  ✅ Fixed max_devices for {user.phone_number}")
                
                # Find access logs without device tracking
                recent_logs = AccessLog.objects.filter(
                    user=user,
                    access_granted=True,
                    mac_address__isnull=False,
                    device__isnull=True,
                    timestamp__gte=timezone.now() - timezone.timedelta(days=7)
                ).exclude(mac_address='')
                
                if recent_logs.exists():
                    self.stdout.write(f"  🔍 Found {recent_logs.count()} untracked access logs for {user.phone_number}")
                    
                    for log in recent_logs:
                        if log.mac_address:
                            device, created = Device.objects.get_or_create(
                                user=user,
                                mac_address=log.mac_address,
                                defaults={
                                    'ip_address': log.ip_address,
                                    'is_active': True,
                                    'device_name': f'Device-{log.mac_address[-8:]}',
                                    'first_seen': log.timestamp,
                                    'last_seen': log.timestamp
                                }
                            )
                            
                            log.device = device
                            log.save()
                            
                            if created:
                                self.stdout.write(f"    ✅ Created device: {device.mac_address}")
                            else:
                                self.stdout.write(f"    ✅ Linked device: {device.mac_address}")
                            
                            fixed = True
                
                if fixed:
                    users_fixed += 1
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Error fixing user {user.phone_number}: {str(e)}")
                )
        
        self.stdout.write(f"\n📊 Fixed device tracking for {users_fixed}/{total_users} users")
    
    def verify_device_tracking(self):
        """Verify device tracking is working"""
        self.stdout.write("\n🔍 Verifying device tracking...")
        
        # Check users with known activity
        test_users = ['255684106419', '255708374149']
        
        for phone_number in test_users:
            try:
                user = User.objects.get(phone_number=phone_number)
                device_count = user.get_active_devices().count()
                total_devices = user.devices.count()
                has_access = user.has_active_access()
                
                self.stdout.write(f"\n📱 User: {phone_number}")
                self.stdout.write(f"   Active devices: {device_count}/{user.max_devices}")
                self.stdout.write(f"   Total devices: {total_devices}")
                self.stdout.write(f"   Has access: {'✅ Yes' if has_access else '❌ No'}")
                
                if user.devices.exists():
                    for device in user.devices.all():
                        status = "🟢" if device.is_active else "🔴"
                        self.stdout.write(f"     {status} {device.mac_address} - {device.device_name}")
                
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f"⚠️  Test user {phone_number} not found")
                )
    
    def test_specific_user(self, phone_number):
        """Test device tracking for specific user"""
        self.stdout.write(f"\n🧪 Testing user: {phone_number}")
        
        try:
            user = User.objects.get(phone_number=phone_number)
            
            # Give them access for testing if they don't have it
            if not user.has_active_access():
                user.paid_until = timezone.now() + timezone.timedelta(hours=24)
                user.is_active = True
                user.save()
                self.stdout.write("  ✅ Granted test access")
            
            # Test device creation
            test_mac = 'AA:BB:CC:DD:EE:99'
            device, created = Device.objects.get_or_create(
                user=user,
                mac_address=test_mac,
                defaults={
                    'ip_address': '192.168.88.99',
                    'is_active': True,
                    'device_name': f'TestDevice-{test_mac[-8:]}',
                    'first_seen': timezone.now(),
                    'last_seen': timezone.now()
                }
            )
            
            if created:
                self.stdout.write(f"  ✅ Created test device: {device.mac_address}")
            else:
                device.is_active = True
                device.last_seen = timezone.now()
                device.save()
                self.stdout.write(f"  ✅ Updated test device: {device.mac_address}")
            
            # Test API response
            self.test_user_api_response(phone_number, test_mac)
            
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"❌ User {phone_number} not found")
            )
    
    def test_api_response(self):
        """Test API response for device count"""
        self.stdout.write("\n🌐 Testing API response...")
        
        test_phone = '255684106419'
        self.test_user_api_response(test_phone, 'AA:BB:CC:DD:EE:FF')
    
    def test_user_api_response(self, phone_number, mac_address):
        """Test API response for specific user"""
        try:
            user = User.objects.get(phone_number=phone_number)
            
            from billing.views import mikrotik_auth
            
            factory = RequestFactory()
            # Fix: Send data in request body as form data (not JSON)
            request = factory.post('/api/mikrotik/auth/', {
                'username': phone_number,
                'mac': mac_address,
                'ip': '192.168.88.100'
            })
            # Set content type to simulate frontend call
            request.content_type = 'application/json'
            request.META['HTTP_ACCEPT'] = 'application/json'
            request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0 Test'
            
            response = mikrotik_auth(request)
            
            if response.status_code == 200:
                data = json.loads(response.content)
                self.stdout.write(f"  ✅ API Success for {phone_number}:")
                self.stdout.write(f"     Device count: {data.get('device_count', 'N/A')}")
                self.stdout.write(f"     Max devices: {data.get('max_devices', 'N/A')}")
                self.stdout.write(f"     Access type: {data.get('access_type', 'N/A')}")
                self.stdout.write(f"     Success: {data.get('success', 'N/A')}")
            else:
                data = json.loads(response.content)
                self.stdout.write(
                    self.style.ERROR(f"  ❌ API Failed for {phone_number}: {data.get('error', 'Unknown')}")
                )
                
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"❌ Test user {phone_number} not found")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ API test error: {str(e)}")
            )
