#!/usr/bin/env python3
"""
API Test Script - Simulate real voucher redemption with MAC address
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
from billing.views import redeem_voucher, verify_access
from billing.models import User, Device, Voucher
import uuid

def simulate_voucher_redemption():
    print("=== SIMULATING VOUCHER REDEMPTION API CALL ===\n")
    
    # Create a test voucher if none exists
    unused_vouchers = Voucher.objects.filter(is_used=False)
    if not unused_vouchers.exists():
        from billing.models import User as DummyUser
        admin_user = User.objects.first()
        if admin_user:
            test_voucher = Voucher.objects.create(
                duration_hours=24,
                created_by_phone=admin_user.phone_number,
                notes="Test voucher for debugging"
            )
            print(f"Created test voucher: {test_voucher.code}")
        else:
            print("ERROR: No users found to create test voucher")
            return
    else:
        test_voucher = unused_vouchers.first()
        print(f"Using existing voucher: {test_voucher.code}")
    
    # Test data
    test_phone = "+255787654321"
    test_mac = "11:22:33:44:55:66"
    test_ip = "192.168.1.200"
    
    print(f"Test phone: {test_phone}")
    print(f"Test MAC: {test_mac}")
    print(f"Test IP: {test_ip}")
    
    # Create request factory
    factory = RequestFactory()
    
    # Simulate voucher redemption request
    post_data = {
        'voucher_code': test_voucher.code,
        'phone_number': test_phone,
        'mac_address': test_mac,
        'ip_address': test_ip
    }
    
    print(f"\nRequest data: {json.dumps(post_data, indent=2)}")
    
    # Create POST request
    request = factory.post(
        '/api/vouchers/redeem/',
        data=json.dumps(post_data),
        content_type='application/json',
        HTTP_X_FORWARDED_FOR=test_ip,
        HTTP_X_REAL_IP=test_ip,
        HTTP_USER_AGENT='Test-Browser/1.0'
    )
    
    print(f"\n1. BEFORE redemption:")
    users_before = User.objects.filter(phone_number=test_phone.replace('+', '')).count()
    devices_before = Device.objects.filter(mac_address=test_mac).count()
    print(f"   Users with phone {test_phone}: {users_before}")
    print(f"   Devices with MAC {test_mac}: {devices_before}")
    
    try:
        # Call the actual API endpoint
        response = redeem_voucher(request)
        
        print(f"\n2. API Response:")
        print(f"   Status: {response.status_code}")
        print(f"   Data: {json.dumps(response.data, indent=2, default=str)}")
        
    except Exception as e:
        print(f"\n2. API ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    print(f"\n3. AFTER redemption:")
    users_after = User.objects.filter(phone_number=test_phone.replace('+', '')).count()
    devices_after = Device.objects.filter(mac_address=test_mac).count()
    print(f"   Users with phone {test_phone}: {users_after}")
    print(f"   Devices with MAC {test_mac}: {devices_after}")
    
    # Check the specific user and device
    try:
        from billing.utils import find_user_by_phone
        user = find_user_by_phone(test_phone)
        if user:
            print(f"\n4. User details:")
            print(f"   Phone: {user.phone_number}")
            print(f"   Active: {user.is_active}")
            print(f"   Paid until: {user.paid_until}")
            print(f"   Max devices: {user.max_devices}")
            print(f"   Active devices: {user.get_active_devices().count()}")
            
            # Check devices
            user_devices = user.devices.all()
            print(f"\n5. User devices:")
            for device in user_devices:
                print(f"   - MAC: {device.mac_address}")
                print(f"     IP: {device.ip_address}")
                print(f"     Name: {device.device_name}")
                print(f"     Active: {device.is_active}")
                print(f"     Created: {device.first_seen}")
        else:
            print(f"\n4. ERROR: User not found after redemption")
            
    except Exception as e:
        print(f"\n4. ERROR checking user: {str(e)}")

def simulate_verify_access():
    print(f"\n=== SIMULATING VERIFY ACCESS API CALL ===\n")
    
    # Use the same test data
    test_phone = "+255787654321"
    test_mac = "11:22:33:44:55:66"
    test_ip = "192.168.1.200"
    
    factory = RequestFactory()
    
    post_data = {
        'phone_number': test_phone,
        'mac_address': test_mac,
        'ip_address': test_ip
    }
    
    print(f"Verify request data: {json.dumps(post_data, indent=2)}")
    
    request = factory.post(
        '/api/verify/',
        data=json.dumps(post_data),
        content_type='application/json',
        HTTP_X_FORWARDED_FOR=test_ip,
        HTTP_X_REAL_IP=test_ip,
        HTTP_USER_AGENT='Test-Browser/1.0'
    )
    
    try:
        response = verify_access(request)
        print(f"\nVerify Response:")
        print(f"   Status: {response.status_code}")
        print(f"   Data: {json.dumps(response.data, indent=2, default=str)}")
    except Exception as e:
        print(f"\nVerify ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    simulate_voucher_redemption()
    simulate_verify_access()
    print(f"\n=== TEST COMPLETE ===")
