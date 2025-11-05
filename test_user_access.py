#!/usr/bin/env python3
"""
Test script to verify user access logic for both payment and voucher users
Run this after fixing the access logic to ensure it works correctly
"""

import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django
sys.path.append('/Users/macbookair/Desktop/kitonga')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from django.utils import timezone
from billing.models import User, Voucher, Payment, Bundle
import requests

def test_user_access_api():
    """Test the user access APIs"""
    base_url = "http://127.0.0.1:8000"
    
    print("🧪 TESTING USER ACCESS LOGIC")
    print("=" * 50)
    
    # Test phone numbers
    payment_user = "255123456789"
    voucher_user = "255987654321"
    new_user = "255111222333"
    
    print(f"\n1. Testing Payment User: {payment_user}")
    print("-" * 30)
    
    # Test payment user status
    response = requests.get(f"{base_url}/api/mikrotik/user-status/?username={payment_user}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Payment User Status:")
        print(f"   - Has Access: {data['user']['has_active_access']}")
        print(f"   - Paid Until: {data['user']['paid_until']}")
        print(f"   - Access Method: {data['access_details']['access_method']}")
        print(f"   - Time Remaining: {data['access_details']['time_remaining']}")
    else:
        print(f"❌ Payment User not found or error: {response.status_code}")
    
    print(f"\n2. Testing Voucher User: {voucher_user}")
    print("-" * 30)
    
    # Test voucher user status
    response = requests.get(f"{base_url}/api/mikrotik/user-status/?username={voucher_user}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Voucher User Status:")
        print(f"   - Has Access: {data['user']['has_active_access']}")
        print(f"   - Paid Until: {data['user']['paid_until']}")
        print(f"   - Access Method: {data['access_details']['access_method']}")
        print(f"   - Time Remaining: {data['access_details']['time_remaining']}")
    else:
        print(f"❌ Voucher User not found or error: {response.status_code}")
    
    print(f"\n3. Testing New User: {new_user}")
    print("-" * 30)
    
    # Test new user status
    response = requests.get(f"{base_url}/api/mikrotik/user-status/?username={new_user}")
    if response.status_code == 404:
        print("✅ New User correctly not found")
    else:
        print(f"❌ Unexpected response for new user: {response.status_code}")
    
    print(f"\n4. Testing MikroTik Auth for Users")
    print("-" * 30)
    
    # Test MikroTik authentication for payment user
    auth_data = {
        'username': payment_user,
        'password': '',
        'mac': '00:11:22:33:44:55',
        'ip': '192.168.0.100'
    }
    
    response = requests.post(f"{base_url}/api/mikrotik/auth/", data=auth_data)
    print(f"Payment User Auth: {response.status_code} - {response.text}")
    
    # Test MikroTik authentication for voucher user
    auth_data['username'] = voucher_user
    auth_data['mac'] = '00:11:22:33:44:66'
    auth_data['ip'] = '192.168.0.101'
    
    response = requests.post(f"{base_url}/api/mikrotik/auth/", data=auth_data)
    print(f"Voucher User Auth: {response.status_code} - {response.text}")
    
    # Test MikroTik authentication for new user
    auth_data['username'] = new_user
    auth_data['mac'] = '00:11:22:33:44:77'
    auth_data['ip'] = '192.168.0.102'
    
    response = requests.post(f"{base_url}/api/mikrotik/auth/", data=auth_data)
    print(f"New User Auth: {response.status_code} - {response.text}")

def create_test_users():
    """Create test users with different access methods"""
    print("\n🔧 CREATING TEST USERS")
    print("=" * 30)
    
    # Create payment user
    payment_user, created = User.objects.get_or_create(
        phone_number="255123456789",
        defaults={
            'is_active': True,
            'paid_until': timezone.now() + timedelta(hours=24),
            'total_payments': 1
        }
    )
    if created:
        print("✅ Created payment test user")
    else:
        # Update existing user
        payment_user.is_active = True
        payment_user.paid_until = timezone.now() + timedelta(hours=24)
        payment_user.save()
        print("✅ Updated payment test user")
    
    # Create voucher user
    voucher_user, created = User.objects.get_or_create(
        phone_number="255987654321"
    )
    
    # Create and redeem a voucher for this user
    voucher = Voucher.objects.create(
        code="TEST-VOUC-HER1",
        duration_hours=24,
        created_by="test_script"
    )
    
    success, message = voucher.redeem(voucher_user)
    if success:
        print("✅ Created voucher test user and redeemed voucher")
    else:
        print(f"❌ Failed to redeem voucher: {message}")
    
    print(f"\nTest Users Created:")
    print(f"Payment User: {payment_user.phone_number} - Access: {payment_user.has_active_access()}")
    print(f"Voucher User: {voucher_user.phone_number} - Access: {voucher_user.has_active_access()}")

if __name__ == "__main__":
    try:
        # First create test users
        create_test_users()
        
        # Then test the APIs
        test_user_access_api()
        
        print(f"\n✅ TEST COMPLETED")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
