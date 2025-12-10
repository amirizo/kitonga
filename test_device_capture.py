#!/usr/bin/env python3
"""
Test script to demonstrate device capture during WiFi verification
"""
import os
import sys
import django
import json

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from django.test.client import RequestFactory
from billing.views import verify_access
from billing.models import User, Device, Voucher
from billing.utils import get_or_create_user

def test_device_capture_on_verify():
    print("=== TESTING DEVICE CAPTURE DURING VERIFY ACCESS ===\n")
    
    # Create a test user with voucher access
    test_phone = "+255777888999"
    test_mac_new = "aa:bb:cc:dd:ee:11"  # New device MAC
    test_ip = "192.168.1.150"
    
    print(f"Test scenario: New device connecting to WiFi")
    print(f"Phone: {test_phone}")
    print(f"MAC: {test_mac_new}")
    print(f"IP: {test_ip}\n")
    
    # First, create user with voucher access
    try:
        user, created = get_or_create_user(test_phone, max_devices=1)
        if created:
            print(f"✓ Created new user: {user.phone_number}")
        else:
            print(f"✓ Found existing user: {user.phone_number}")
            
        # Give user access (simulate voucher redemption)
        from django.utils import timezone
        from datetime import timedelta
        user.paid_until = timezone.now() + timedelta(hours=24)
        user.is_active = True
        user.save()
        print(f"✓ User has active access until: {user.paid_until}")
        
    except Exception as e:
        print(f"ERROR setting up user: {e}")
        return
    
    # Check devices BEFORE verify call
    devices_before = Device.objects.filter(user=user).count()
    devices_with_mac_before = Device.objects.filter(mac_address=test_mac_new).count()
    
    print(f"\n📱 BEFORE verify access:")
    print(f"   User's total devices: {devices_before}")
    print(f"   Devices with MAC {test_mac_new}: {devices_with_mac_before}")
    
    # Create verify access request (simulating user connecting to WiFi)
    factory = RequestFactory()
    
    post_data = {
        'phone_number': test_phone,
        'mac_address': test_mac_new,
        'ip_address': test_ip
    }
    
    print(f"\n🔍 CALLING /api/verify/ with:")
    print(f"   {json.dumps(post_data, indent=2)}")
    
    request = factory.post(
        '/api/verify/',
        data=json.dumps(post_data),
        content_type='application/json',
        HTTP_X_FORWARDED_FOR=test_ip,
        HTTP_X_REAL_IP=test_ip,
        HTTP_USER_AGENT='WiFi-Device/1.0'
    )
    
    try:
        # Call the verify_access API
        response = verify_access(request)
        
        print(f"\n📡 API RESPONSE:")
        print(f"   Status: {response.status_code}")
        
        # Pretty print the response
        response_data = response.data
        print(f"   Access Granted: {response_data.get('access_granted')}")
        print(f"   User ID: {response_data.get('user', {}).get('id')}")
        print(f"   Device Registered: {response_data.get('device', {}).get('registered', False)}")
        print(f"   Device Name: {response_data.get('device', {}).get('device_name', 'None')}")
        print(f"   Device Active: {response_data.get('device', {}).get('is_active', False)}")
        
    except Exception as e:
        print(f"ERROR during verify access: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Check devices AFTER verify call
    devices_after = Device.objects.filter(user=user).count()
    devices_with_mac_after = Device.objects.filter(mac_address=test_mac_new).count()
    
    print(f"\n📱 AFTER verify access:")
    print(f"   User's total devices: {devices_after}")
    print(f"   Devices with MAC {test_mac_new}: {devices_with_mac_after}")
    
    # Show the actual device that was created
    try:
        new_device = Device.objects.get(mac_address=test_mac_new, user=user)
        print(f"\n🆕 NEW DEVICE CREATED:")
        print(f"   ID: {new_device.id}")
        print(f"   MAC: {new_device.mac_address}")
        print(f"   IP: {new_device.ip_address}")
        print(f"   Name: {new_device.device_name}")
        print(f"   Active: {new_device.is_active}")
        print(f"   Created: {new_device.first_seen}")
        print(f"   User: {new_device.user.phone_number}")
        
        print(f"\n✅ SUCCESS: Device was captured and saved to database!")
        
    except Device.DoesNotExist:
        print(f"\n❌ FAILED: No device was created with MAC {test_mac_new}")
    
    # Full response output for reference
    print(f"\n📄 FULL API RESPONSE:")
    print(json.dumps(response.data, indent=2, default=str))

def test_existing_user_new_device():
    print(f"\n\n=== TESTING EXISTING USER WITH NEW DEVICE ===\n")
    
    # Use existing user but with a different MAC
    test_phone = "+255777888999" 
    test_mac_second = "ff:ee:dd:cc:bb:22"  # Second device
    test_ip = "192.168.1.151"
    
    print(f"Test scenario: Existing user connecting new device")
    print(f"Phone: {test_phone}")
    print(f"MAC: {test_mac_second}")
    print(f"IP: {test_ip}\n")
    
    factory = RequestFactory()
    
    post_data = {
        'phone_number': test_phone,
        'mac_address': test_mac_second,
        'ip_address': test_ip
    }
    
    print(f"🔍 CALLING /api/verify/ with second device:")
    print(f"   {json.dumps(post_data, indent=2)}")
    
    request = factory.post(
        '/api/verify/',
        data=json.dumps(post_data),
        content_type='application/json',
        HTTP_X_FORWARDED_FOR=test_ip,
        HTTP_X_REAL_IP=test_ip,
        HTTP_USER_AGENT='Second-Device/1.0'
    )
    
    try:
        response = verify_access(request)
        
        print(f"\n📡 SECOND DEVICE RESPONSE:")
        print(f"   Status: {response.status_code}")
        print(f"   Access Granted: {response.data.get('access_granted')}")
        print(f"   Denial Reason: {response.data.get('denial_reason', 'None')}")
        print(f"   Device Registered: {response.data.get('device', {}).get('registered', False)}")
        
        # Check if device limit was enforced (should be since max_devices = 1)
        debug_info = response.data.get('debug_info', {})
        print(f"   Device Count: {debug_info.get('device_count', 0)}")
        print(f"   Max Devices: {debug_info.get('max_devices', 0)}")
        
        if not response.data.get('access_granted'):
            print(f"   ✅ CORRECT: Device limit enforced!")
        else:
            print(f"   ❓ UNEXPECTED: Second device was allowed")
            
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_device_capture_on_verify()
    test_existing_user_new_device()
    print(f"\n=== DEVICE CAPTURE TESTING COMPLETE ===")
