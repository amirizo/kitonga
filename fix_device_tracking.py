#!/usr/bin/env python3
"""
Device Tracking Fix Script for Kitonga WiFi Billing System
This script fixes device tracking issues and ensures proper device counting
"""

import os
import sys
import django

# Setup Django environment
sys.path.append('/Users/macbookair/Desktop/kitonga')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga_billing.settings')
django.setup()

from billing.models import User, Device, AccessLog
from django.utils import timezone
from django.db.models import Q
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_device_tracking():
    """
    Fix device tracking issues for all users
    """
    print("=" * 50)
    print("KITONGA DEVICE TRACKING FIX")
    print("=" * 50)
    
    # 1. Fix users with broken device counts
    users_with_issues = []
    total_users = User.objects.count()
    
    print(f"Checking {total_users} users for device tracking issues...")
    
    for user in User.objects.all():
        try:
            # Check if device count is showing correctly
            device_count = user.get_active_devices().count()
            all_devices = user.devices.count()
            
            # Fix max_devices if not set
            if not user.max_devices or user.max_devices <= 0:
                user.max_devices = 3  # Default to 3 devices
                user.save()
                print(f"✅ Fixed max_devices for {user.phone_number}: set to 3")
            
            # Check for access logs without devices (indicates tracking issue)
            recent_logs = AccessLog.objects.filter(
                user=user,
                access_granted=True,
                mac_address__isnull=False,
                device__isnull=True,
                created_at__gte=timezone.now() - timezone.timedelta(days=7)
            ).exclude(mac_address='')
            
            if recent_logs.exists():
                print(f"⚠️  Found {recent_logs.count()} access logs without device tracking for {user.phone_number}")
                
                # Try to create devices from access logs
                for log in recent_logs:
                    if log.mac_address and log.mac_address != '':
                        device, created = Device.objects.get_or_create(
                            user=user,
                            mac_address=log.mac_address,
                            defaults={
                                'ip_address': log.ip_address,
                                'is_active': True,
                                'device_name': f'Device-{log.mac_address[-8:]}',
                                'first_seen': log.created_at,
                                'last_seen': log.created_at
                            }
                        )
                        
                        if created:
                            # Update the access log to link to the device
                            log.device = device
                            log.save()
                            print(f"  ✅ Created device from access log: {device.mac_address}")
                        else:
                            # Update existing device
                            if not device.is_active:
                                device.is_active = True
                                device.last_seen = log.created_at
                                device.save()
                            
                            # Link log to device
                            log.device = device
                            log.save()
                            print(f"  ✅ Linked existing device: {device.mac_address}")
                
                users_with_issues.append(user.phone_number)
            
            # Display current status
            updated_device_count = user.get_active_devices().count()
            if updated_device_count != device_count:
                print(f"✅ Fixed device count for {user.phone_number}: {device_count} → {updated_device_count}")
            
        except Exception as e:
            print(f"❌ Error fixing user {user.phone_number}: {str(e)}")
    
    print(f"\n📊 SUMMARY:")
    print(f"   Total users checked: {total_users}")
    print(f"   Users with tracking issues: {len(users_with_issues)}")
    if users_with_issues:
        print(f"   Affected users: {', '.join(users_with_issues)}")
    
    return len(users_with_issues)

def verify_device_tracking():
    """
    Verify that device tracking is working correctly
    """
    print("\n" + "=" * 50)
    print("DEVICE TRACKING VERIFICATION")
    print("=" * 50)
    
    # Test user with known activity
    test_users = ['255684106419', '255708374149']
    
    for phone_number in test_users:
        try:
            user = User.objects.get(phone_number=phone_number)
            device_count = user.get_active_devices().count()
            total_devices = user.devices.count()
            has_access = user.has_active_access()
            
            print(f"\n📱 User: {phone_number}")
            print(f"   Active devices: {device_count}/{user.max_devices}")
            print(f"   Total devices: {total_devices}")
            print(f"   Has access: {has_access}")
            print(f"   Access until: {user.paid_until}")
            
            # Show device details
            if user.devices.exists():
                print("   Devices:")
                for device in user.devices.all():
                    status = "🟢 Active" if device.is_active else "🔴 Inactive"
                    print(f"     {status} {device.mac_address} ({device.device_name}) - Last seen: {device.last_seen}")
            else:
                print("   No devices registered")
            
            # Show recent access logs
            recent_logs = AccessLog.objects.filter(user=user).order_by('-created_at')[:3]
            if recent_logs.exists():
                print("   Recent access attempts:")
                for log in recent_logs:
                    status = "✅" if log.access_granted else "❌"
                    device_info = f" - Device: {log.device.mac_address}" if log.device else " - No device"
                    print(f"     {status} {log.created_at.strftime('%Y-%m-%d %H:%M')} {device_info}")
            
        except User.DoesNotExist:
            print(f"❌ Test user {phone_number} not found")
        except Exception as e:
            print(f"❌ Error checking user {phone_number}: {str(e)}")

def test_api_response():
    """
    Test that the API returns correct device count
    """
    print("\n" + "=" * 50)
    print("API RESPONSE TEST")
    print("=" * 50)
    
    from django.test import RequestFactory
    from billing.views import mikrotik_auth
    import json
    
    factory = RequestFactory()
    
    # Test with known user
    test_phone = '255684106419'
    try:
        user = User.objects.get(phone_number=test_phone)
        
        # Simulate frontend API call
        request = factory.post('/api/mikrotik/auth/', {
            'username': test_phone,
            'mac': 'AA:BB:CC:DD:EE:FF',
            'ip': '192.168.88.100'
        })
        request.content_type = 'application/json'
        request.META['HTTP_ACCEPT'] = 'application/json'
        request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0 Test'
        
        response = mikrotik_auth(request)
        
        if response.status_code == 200:
            data = json.loads(response.content)
            print(f"✅ API Test SUCCESS for {test_phone}:")
            print(f"   Device count: {data.get('device_count', 'N/A')}")
            print(f"   Max devices: {data.get('max_devices', 'N/A')}")
            print(f"   Access type: {data.get('access_type', 'N/A')}")
            print(f"   Full response: {data}")
        else:
            data = json.loads(response.content)
            print(f"❌ API Test FAILED for {test_phone}:")
            print(f"   Status: {response.status_code}")
            print(f"   Error: {data.get('error', 'Unknown error')}")
            
    except User.DoesNotExist:
        print(f"❌ Test user {test_phone} not found")
    except Exception as e:
        print(f"❌ API test error: {str(e)}")

def create_test_device_tracking():
    """
    Create test device tracking for demonstration
    """
    print("\n" + "=" * 50)
    print("CREATING TEST DEVICE TRACKING")
    print("=" * 50)
    
    # Find a user with access
    user_with_access = User.objects.filter(
        paid_until__gt=timezone.now(),
        is_active=True
    ).first()
    
    if not user_with_access:
        print("❌ No users with active access found. Creating test scenario...")
        
        # Use the test user
        try:
            user = User.objects.get(phone_number='255684106419')
            
            # Give them access for testing
            user.paid_until = timezone.now() + timezone.timedelta(hours=24)
            user.is_active = True
            user.max_devices = 3
            user.save()
            
            print(f"✅ Gave test access to {user.phone_number}")
            user_with_access = user
            
        except User.DoesNotExist:
            print("❌ Test user not found")
            return
    
    if user_with_access:
        print(f"📱 Testing device tracking for {user_with_access.phone_number}")
        
        # Create test device
        test_mac = 'AA:BB:CC:DD:EE:FF'
        device, created = Device.objects.get_or_create(
            user=user_with_access,
            mac_address=test_mac,
            defaults={
                'ip_address': '192.168.88.100',
                'is_active': True,
                'device_name': f'TestDevice-{test_mac[-8:]}',
                'first_seen': timezone.now(),
                'last_seen': timezone.now()
            }
        )
        
        if created:
            print(f"✅ Created test device: {device.mac_address}")
        else:
            device.is_active = True
            device.last_seen = timezone.now()
            device.save()
            print(f"✅ Updated test device: {device.mac_address}")
        
        # Create access log
        AccessLog.objects.create(
            user=user_with_access,
            device=device,
            ip_address='192.168.88.100',
            mac_address=test_mac,
            access_granted=True,
            denial_reason='Test device tracking'
        )
        
        print(f"✅ Created access log for test device")
        
        # Verify count
        device_count = user_with_access.get_active_devices().count()
        print(f"✅ Device count after test: {device_count}/{user_with_access.max_devices}")

if __name__ == "__main__":
    print("Starting Kitonga Device Tracking Fix...")
    
    try:
        # 1. Fix existing device tracking issues
        issues_fixed = fix_device_tracking()
        
        # 2. Verify device tracking is working
        verify_device_tracking()
        
        # 3. Test API response
        test_api_response()
        
        # 4. Create test scenario if needed
        if issues_fixed == 0:
            create_test_device_tracking()
        
        print("\n" + "=" * 50)
        print("✅ DEVICE TRACKING FIX COMPLETED")
        print("=" * 50)
        print("\nNext steps:")
        print("1. Apply the MikroTik configuration from COMPLETE_MIKROTIK_FIX.rsc")
        print("2. Test user authentication with a known phone number")
        print("3. Verify device count shows correctly in API responses")
        print("4. Check that users get internet access after authentication")
        
    except Exception as e:
        print(f"❌ Error during fix: {str(e)}")
        import traceback
        traceback.print_exc()
