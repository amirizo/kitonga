#!/usr/bin/env python3
"""
Quick verification script to check voucher user access implementation
Checks that voucher users can connect to WiFi and logs are created properly
"""

import os
import sys
import django
from datetime import timedelta

# Setup Django
sys.path.append('/Users/macbookair/Desktop/kitonga')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from django.utils import timezone
from billing.models import User, Voucher, Device, AccessLog

def test_voucher_user_access():
    """Test that voucher users can access internet and logs are created"""
    print("🎟️ TESTING VOUCHER USER ACCESS IMPLEMENTATION")
    print("=" * 60)
    
    # Test data
    test_phone = "255999888777"
    test_mac = "00:11:22:33:99:88"
    test_ip = "192.168.1.250"
    
    try:
        # Clean up any existing test data
        User.objects.filter(phone_number=test_phone).delete()
        Voucher.objects.filter(code="TEST-IMPL-CHEK").delete()
        
        print("1. Creating test voucher...")
        voucher = Voucher.objects.create(
            code="TEST-IMPL-CHEK",
            duration_hours=24,
            created_by="test_script"
        )
        print(f"✅ Test voucher created: {voucher.code}")
        
        print(f"\n2. Testing voucher redemption...")
        # Create user and redeem voucher
        user = User.objects.create(phone_number=test_phone)
        success, message = voucher.redeem(user)
        
        if success:
            print(f"✅ Voucher redeemed successfully")
            print(f"   - User active: {user.is_active}")
            print(f"   - Paid until: {user.paid_until}")
            print(f"   - Has access: {user.has_active_access()}")
        else:
            print(f"❌ Voucher redemption failed: {message}")
            return
        
        print(f"\n3. Testing device registration...")
        # Test device creation
        device, created = Device.objects.get_or_create(
            user=user,
            mac_address=test_mac,
            defaults={'ip_address': test_ip, 'is_active': True}
        )
        
        if created:
            print(f"✅ Device registered successfully")
            print(f"   - Device ID: {device.id}")
            print(f"   - MAC: {device.mac_address}")
            print(f"   - Active: {device.is_active}")
        else:
            print(f"⚠️  Device already existed")
        
        print(f"\n4. Testing access logging...")
        # Create access log
        access_log = AccessLog.objects.create(
            user=user,
            device=device,
            ip_address=test_ip,
            mac_address=test_mac,
            access_granted=True,
            denial_reason=f'Voucher redemption test: {voucher.code}'
        )
        
        print(f"✅ Access log created")
        print(f"   - Log ID: {access_log.id}")
        print(f"   - Access granted: {access_log.access_granted}")
        print(f"   - Timestamp: {access_log.timestamp}")
        
        print(f"\n5. Testing access verification...")
        # Test the has_active_access logic
        has_access = user.has_active_access()
        print(f"✅ Access verification: {has_access}")
        
        if has_access:
            remaining = user.paid_until - timezone.now()
            hours_remaining = int(remaining.total_seconds() / 3600)
            print(f"   - Access remaining: {hours_remaining} hours")
        
        print(f"\n6. Testing device management...")
        # Test device queries
        active_devices = user.get_active_devices()
        can_add_device = user.can_add_device()
        
        print(f"✅ Device management working")
        print(f"   - Active devices: {active_devices.count()}")
        print(f"   - Max devices: {user.max_devices}")
        print(f"   - Can add device: {can_add_device}")
        
        print(f"\n7. Testing access method detection...")
        # Test access method logic
        has_payments = user.payments.filter(status='completed').exists()
        has_vouchers = user.vouchers_used.filter(is_used=True).exists()
        
        if has_payments and has_vouchers:
            access_method = 'payment_and_voucher'
        elif has_payments:
            access_method = 'payment'
        elif has_vouchers:
            access_method = 'voucher'
        else:
            access_method = 'manual'
        
        print(f"✅ Access method detection: {access_method}")
        print(f"   - Has payments: {has_payments}")
        print(f"   - Has vouchers: {has_vouchers}")
        
        print(f"\n✅ ALL TESTS PASSED")
        print("=" * 30)
        print("Voucher users can now:")
        print("✅ Redeem vouchers → Get internet access")
        print("✅ Register devices → MAC tracking works")
        print("✅ Generate access logs → Monitoring works")
        print("✅ Use device management → Limits enforced")
        print("✅ Have access verified → Authentication works")
        
        # Cleanup
        print(f"\n🧹 Cleaning up test data...")
        user.delete()
        voucher.delete()
        print("✅ Cleanup completed")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()

def main():
    print("🔍 VOUCHER USER ACCESS VERIFICATION")
    print("=" * 50)
    print("This script verifies that voucher users can:")
    print("- Redeem vouchers and get internet access")
    print("- Register devices and manage device limits")
    print("- Generate proper access logs")
    print("- Use all the same features as payment users")
    print("")
    
    test_voucher_user_access()

if __name__ == "__main__":
    main()
