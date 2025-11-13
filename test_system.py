#!/usr/bin/env python
"""
System Test Script for Kitonga Wi-Fi Billing System
Tests automatic connection and disconnection features
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from billing.models import User, Bundle, Payment, Voucher, Device
from billing.tasks import disconnect_expired_users, cleanup_inactive_devices
from billing.mikrotik import grant_user_access, revoke_user_access, test_mikrotik_connection


def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_mikrotik_connectivity():
    """Test MikroTik router connection"""
    print_section("Testing MikroTik Connectivity")
    
    try:
        result = test_mikrotik_connection()
        if result['success']:
            print("✅ MikroTik connection: SUCCESS")
            print(f"   Router info: {result.get('router_info', {})}")
        else:
            print("❌ MikroTik connection: FAILED")
            print(f"   Error: {result.get('error', 'Unknown error')}")
        return result['success']
    except Exception as e:
        print(f"❌ MikroTik connection test error: {str(e)}")
        return False


def test_user_creation():
    """Test user creation and access management"""
    print_section("Testing User Creation and Access")
    
    try:
        # Create or get test user
        test_phone = "+255772236727"
        user, created = User.objects.get_or_create(
            phone_number=test_phone,
            defaults={'max_devices': 1}
        )
        
        if created:
            print(f"✅ Created test user: {test_phone}")
        else:
            print(f"ℹ️  Using existing user: {test_phone}")
        
        # Check access before payment
        has_access = user.has_active_access()
        print(f"   Access before payment: {'YES' if has_access else 'NO'}")
        
        return True, user
    except Exception as e:
        print(f"❌ User creation error: {str(e)}")
        return False, None


def test_payment_flow(user):
    """Test payment and automatic connection"""
    print_section("Testing Payment Flow and Auto-Connection")
    
    try:
        # Get or create a bundle
        bundle, created = Bundle.objects.get_or_create(
            name="Test 24h Bundle",
            defaults={
                'duration_hours': 24,
                'price': 1000,
                'description': 'Test bundle for 24 hours',
                'is_active': True
            }
        )
        
        print(f"   Using bundle: {bundle.name} - TZS {bundle.price}")
        
        # Create a payment with unique transaction ID
        import uuid
        unique_transaction_id = f'TEST-{uuid.uuid4().hex[:12].upper()}'
        payment = Payment.objects.create(
            user=user,
            bundle=bundle,
            amount=bundle.price,
            phone_number=user.phone_number,
            order_reference=f'TEST-{timezone.now().timestamp()}',
            transaction_id=unique_transaction_id,
            status='pending'
        )
        
        print(f"✅ Created test payment: {payment.order_reference}")
        
        # Mark payment as completed (simulating webhook)
        payment.mark_completed(payment_reference='TEST-REF-123', channel='TIGOPESA')
        
        print(f"✅ Payment marked as completed")
        
        # Check if user now has access
        user.refresh_from_db()
        has_access = user.has_active_access()
        
        if has_access:
            print(f"✅ User has access after payment")
            print(f"   Paid until: {user.paid_until}")
        else:
            print(f"❌ User does NOT have access after payment")
        
        return has_access
        
    except Exception as e:
        print(f"❌ Payment flow error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_voucher_flow():
    """Test voucher redemption and automatic connection"""
    print_section("Testing Voucher Flow and Auto-Connection")
    
    try:
        # Create test voucher
        voucher = Voucher.objects.create(
            code=Voucher.generate_code(),
            duration_hours=24,
            batch_id='TEST-BATCH',
            created_by='test-script'
        )
        
        print(f"✅ Created test voucher: {voucher.code}")
        
        # Create test user for voucher
        test_phone = "+255684106419"
        user, created = User.objects.get_or_create(
            phone_number=test_phone,
            defaults={'max_devices': 1}
        )
        
        print(f"   Using user: {test_phone}")
        
        # Redeem voucher
        success, message = voucher.redeem(user)
        
        if success:
            print(f"✅ Voucher redeemed successfully")
            print(f"   Message: {message}")
            
            # Check if user has access
            user.refresh_from_db()
            has_access = user.has_active_access()
            
            if has_access:
                print(f"✅ User has access after voucher redemption")
                print(f"   Paid until: {user.paid_until}")
            else:
                print(f"❌ User does NOT have access after voucher redemption")
            
            return has_access
        else:
            print(f"❌ Voucher redemption failed: {message}")
            return False
            
    except Exception as e:
        print(f"❌ Voucher flow error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_mikrotik_grant_access():
    """Test MikroTik access granting"""
    print_section("Testing MikroTik Access Grant")
    
    try:
        test_phone = "+255700000003255772236727"
        test_mac = "AA:BB:CC:DD:EE:FF"
        
        result = grant_user_access(
            username=test_phone,
            mac_address=test_mac,
            password=test_phone,
            comment='Test access grant'
        )
        
        if result.get('success'):
            print(f"✅ Access granted successfully")
            print(f"   User created: {result.get('user_created', False)}")
            print(f"   MAC bypassed: {result.get('mac_bypassed', False)}")
        else:
            print(f"❌ Access grant failed")
            print(f"   Errors: {result.get('errors', [])}")
        
        return result.get('success', False)
        
    except Exception as e:
        print(f"❌ MikroTik grant access error: {str(e)}")
        return False


def test_mikrotik_revoke_access():
    """Test MikroTik access revocation"""
    print_section("Testing MikroTik Access Revocation")
    
    try:
        test_phone = "+255700000003"
        test_mac = "AA:BB:CC:DD:EE:FF"
        
        result = revoke_user_access(
            mac_address=test_mac,
            username=test_phone
        )
        
        if result.get('success'):
            print(f"✅ Access revoked successfully")
            print(f"   MAC revoked: {result.get('mac_revoked', False)}")
            print(f"   User disabled: {result.get('user_revoked', False)}")
        else:
            print(f"❌ Access revocation failed")
            print(f"   Errors: {result.get('errors', [])}")
        
        return result.get('success', False)
        
    except Exception as e:
        print(f"❌ MikroTik revoke access error: {str(e)}")
        return False


def test_expiration_flow():
    """Test automatic disconnection of expired users"""
    print_section("Testing Expiration and Auto-Disconnection")
    
    try:
        # Create expired user
        expired_phone = "+255700000099"
        expired_user, created = User.objects.get_or_create(
            phone_number=expired_phone,
            defaults={
                'max_devices': 1,
                'is_active': True,
                'paid_until': timezone.now() - timedelta(hours=1)  # Expired 1 hour ago
            }
        )
        
        if not created:
            expired_user.is_active = True
            expired_user.paid_until = timezone.now() - timedelta(hours=1)
            expired_user.save()
        
        print(f"✅ Created expired user: {expired_phone}")
        print(f"   Paid until: {expired_user.paid_until}")
        print(f"   Is active: {expired_user.is_active}")
        
        # Run disconnect task
        result = disconnect_expired_users()
        
        if result['success']:
            print(f"✅ Disconnect task completed")
            print(f"   Users disconnected: {result['disconnected']}")
            print(f"   Failed: {result['failed']}")
            
            # Check if user was deactivated
            expired_user.refresh_from_db()
            if not expired_user.is_active:
                print(f"✅ Expired user was deactivated")
            else:
                print(f"⚠️  Expired user is still active")
        else:
            print(f"❌ Disconnect task failed: {result.get('error', 'Unknown error')}")
        
        return result['success']
        
    except Exception as e:
        print(f"❌ Expiration flow error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_device_cleanup():
    """Test inactive device cleanup"""
    print_section("Testing Device Cleanup")
    
    try:
        result = cleanup_inactive_devices()
        
        if result['success']:
            print(f"✅ Device cleanup completed")
            print(f"   Devices deactivated: {result['deactivated']}")
        else:
            print(f"❌ Device cleanup failed: {result.get('error', 'Unknown error')}")
        
        return result['success']
        
    except Exception as e:
        print(f"❌ Device cleanup error: {str(e)}")
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("  KITONGA WI-FI BILLING SYSTEM - COMPREHENSIVE TEST")
    print("=" * 60)
    
    results = {}
    
    # Test 1: MikroTik Connectivity
    results['mikrotik'] = test_mikrotik_connectivity()
    
    # Test 2: User Creation
    user_created, test_user = test_user_creation()
    results['user_creation'] = user_created
    
    # Test 3: Payment Flow (only if user was created)
    if user_created and test_user:
        results['payment_flow'] = test_payment_flow(test_user)
    else:
        results['payment_flow'] = False
        print("⚠️  Skipping payment flow test (user creation failed)")
    
    # Test 4: Voucher Flow
    results['voucher_flow'] = test_voucher_flow()
    
    # Test 5: MikroTik Grant Access (only if connected)
    if results['mikrotik']:
        results['grant_access'] = test_mikrotik_grant_access()
        results['revoke_access'] = test_mikrotik_revoke_access()
    else:
        results['grant_access'] = False
        results['revoke_access'] = False
        print("⚠️  Skipping MikroTik access tests (router not connected)")
    
    # Test 6: Expiration Flow
    results['expiration'] = test_expiration_flow()
    
    # Test 7: Device Cleanup
    results['device_cleanup'] = test_device_cleanup()
    
    # Print Summary
    print_section("TEST SUMMARY")
    
    total = len(results)
    passed = sum(1 for r in results.values() if r)
    failed = total - passed
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} - {test_name.replace('_', ' ').title()}")
    
    print("\n" + "-" * 60)
    print(f"Total Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(passed/total*100):.1f}%")
    print("=" * 60 + "\n")
    
    # Exit with appropriate code
    sys.exit(0 if failed == 0 else 1)


if __name__ == '__main__':
    main()
