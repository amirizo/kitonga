#!/usr/bin/env python3
"""
Debug script to test device registration and MAC address capture
"""
import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from billing.models import User, Device, Voucher
from billing.utils import get_or_create_user, normalize_phone_number
import json

def debug_device_registration():
    print("=== KITONGA DEVICE REGISTRATION DEBUG ===\n")
    
    # Test phone number
    test_phone = "+255712345678"  # Use a test number
    test_mac = "aa:bb:cc:dd:ee:ff"
    
    print(f"1. Testing phone number normalization:")
    try:
        normalized = normalize_phone_number(test_phone)
        print(f"   Original: {test_phone}")
        print(f"   Normalized: {normalized}")
    except Exception as e:
        print(f"   ERROR: {e}")
        return
    
    print(f"\n2. Testing user creation:")
    try:
        user, created = get_or_create_user(test_phone, max_devices=1)
        print(f"   User: {user.phone_number}")
        print(f"   Created: {created}")
        print(f"   Max devices: {user.max_devices}")
        print(f"   Active devices: {user.get_active_devices().count()}")
    except Exception as e:
        print(f"   ERROR: {e}")
        return
    
    print(f"\n3. Testing device creation:")
    try:
        device, device_created = Device.objects.get_or_create(
            user=user,
            mac_address=test_mac,
            defaults={
                'ip_address': '192.168.1.100',
                'is_active': True,
                'device_name': 'Test Device'
            }
        )
        print(f"   Device: {device.mac_address}")
        print(f"   Created: {device_created}")
        print(f"   Active: {device.is_active}")
        print(f"   IP: {device.ip_address}")
        print(f"   Name: {device.device_name}")
    except Exception as e:
        print(f"   ERROR: {e}")
        return
    
    print(f"\n4. Database verification:")
    all_users = User.objects.all()
    all_devices = Device.objects.all()
    
    print(f"   Total users in database: {all_users.count()}")
    print(f"   Total devices in database: {all_devices.count()}")
    
    print(f"\n5. Recent users:")
    for user in all_users.order_by('-created_at')[:5]:
        device_count = user.get_active_devices().count()
        print(f"   - {user.phone_number}: {device_count} devices, Active: {user.is_active}")
    
    print(f"\n6. Recent devices:")
    for device in all_devices.order_by('-first_seen')[:5]:
        print(f"   - {device.mac_address}: {device.user.phone_number if device.user else 'No user'}, Active: {device.is_active}")
    
    print(f"\n7. Testing voucher scenario:")
    # Check if there are any vouchers
    unused_vouchers = Voucher.objects.filter(is_used=False)
    if unused_vouchers.exists():
        test_voucher = unused_vouchers.first()
        print(f"   Test voucher code: {test_voucher.code}")
        print(f"   Duration: {test_voucher.duration_hours} hours")
    else:
        print(f"   No unused vouchers found for testing")
    
    print(f"\n=== DEBUG COMPLETE ===")

if __name__ == "__main__":
    debug_device_registration()
