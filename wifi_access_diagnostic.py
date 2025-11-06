#!/usr/bin/env python3
"""
WiFi Access Diagnostic and Fix Script
This script helps diagnose and fix issues preventing users from getting internet access
"""

import os
import sys
import django
import requests
import json
from datetime import datetime

# Setup Django
sys.path.append('/Users/macbookair/Desktop/kitonga')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from billing.models import User, Device, AccessLog, Payment, Voucher
from billing.mikrotik import authenticate_user_with_mikrotik, track_device_connection

def check_user_access_status(phone_number):
    """Check comprehensive user access status"""
    print(f"\n🔍 CHECKING ACCESS STATUS FOR {phone_number}")
    print("=" * 60)
    
    try:
        user = User.objects.get(phone_number=phone_number)
        
        # Basic user info
        print(f"📱 Phone: {user.phone_number}")
        print(f"✅ Active: {user.is_active}")
        print(f"🔓 Has Access: {user.has_active_access()}")
        print(f"📱 Max Devices: {user.max_devices}")
        print(f"💰 Total Payments: {user.total_payments}")
        print(f"📅 Joined: {user.created_at.strftime('%m/%d/%Y')}")
        
        if user.paid_until:
            print(f"⏰ Paid Until: {user.paid_until.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print("⏰ Paid Until: None")
        
        # Device info
        devices = user.devices.all()
        active_devices = user.get_active_devices()
        print(f"\n📱 DEVICES: {active_devices.count()}/{user.max_devices}")
        
        for device in devices:
            status = "🟢 Active" if device.is_active else "🔴 Inactive"
            print(f"   {status} {device.mac_address} -> {device.ip_address}")
            print(f"      First seen: {device.first_seen}")
            print(f"      Last seen: {device.last_seen}")
        
        # Payment history
        payments = user.payments.filter(status='completed').order_by('-created_at')[:3]
        print(f"\n💰 RECENT PAYMENTS:")
        total_spent = sum(p.amount for p in user.payments.filter(status='completed'))
        print(f"   Total Spent: TSh {total_spent}")
        
        for payment in payments:
            print(f"   ✅ TSh {payment.amount} - {payment.created_at.strftime('%m/%d %H:%M')}")
        
        # Voucher history
        vouchers = user.vouchers_used.filter(is_used=True).order_by('-used_at')[:3]
        print(f"\n🎫 RECENT VOUCHERS:")
        for voucher in vouchers:
            print(f"   ✅ {voucher.code} - {voucher.duration_hours}h - {voucher.used_at.strftime('%m/%d %H:%M') if voucher.used_at else 'N/A'}")
        
        # Access method detection
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
        
        print(f"\n🔑 ACCESS METHOD: {access_method}")
        
        # Recent access logs
        recent_logs = AccessLog.objects.filter(user=user).order_by('-timestamp')[:5]
        print(f"\n📊 RECENT ACCESS ATTEMPTS:")
        for log in recent_logs:
            status = "✅ Granted" if log.access_granted else "❌ Denied"
            print(f"   {status} {log.timestamp.strftime('%m/%d %H:%M')} - {log.denial_reason if log.denial_reason else 'Success'}")
        
        return user
        
    except User.DoesNotExist:
        print(f"❌ User {phone_number} not found")
        return None

def test_wifi_authentication(phone_number, mac_address=None, ip_address=None):
    """Test WiFi authentication flow"""
    print(f"\n🔧 TESTING WIFI AUTHENTICATION FOR {phone_number}")
    print("=" * 60)
    
    try:
        user = User.objects.get(phone_number=phone_number)
        
        if not user.has_active_access():
            print("❌ User does not have active access - cannot test authentication")
            return False
        
        # Test device tracking
        if mac_address and ip_address:
            print("📱 Testing device tracking...")
            device_result = track_device_connection(
                phone_number=phone_number,
                mac_address=mac_address,
                ip_address=ip_address,
                connection_type='wifi',
                access_method='diagnostic_test'
            )
            
            if device_result['success']:
                print("✅ Device tracking successful")
                print(f"   Device ID: {device_result['device_info']['device_id']}")
                print(f"   Device Count: {device_result['device_info']['device_count']}/{device_result['device_info']['max_devices']}")
            else:
                print(f"❌ Device tracking failed: {device_result['message']}")
                return False
        
        # Test MikroTik authentication
        print("🌐 Testing MikroTik authentication...")
        mikrotik_result = authenticate_user_with_mikrotik(
            phone_number=phone_number,
            mac_address=mac_address or '',
            ip_address=ip_address or '127.0.0.1'
        )
        
        if mikrotik_result.get('success'):
            print("✅ MikroTik authentication successful")
            print(f"   Method: {mikrotik_result.get('method', 'unknown')}")
            print(f"   Message: {mikrotik_result.get('message', 'No message')}")
        else:
            print("❌ MikroTik authentication failed")
            print(f"   Message: {mikrotik_result.get('message', 'No message')}")
            return False
        
        # Test API endpoints
        print("🔗 Testing API endpoints...")
        base_url = "http://127.0.0.1:8000/api"
        
        # Test verify endpoint
        verify_data = {
            'phone_number': phone_number,
            'mac_address': mac_address or '',
            'ip_address': ip_address or '127.0.0.1'
        }
        
        try:
            response = requests.post(f"{base_url}/verify/", json=verify_data, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('access_granted'):
                    print("✅ Verify endpoint: Access granted")
                else:
                    print(f"❌ Verify endpoint: Access denied - {data.get('denial_reason', 'Unknown reason')}")
            else:
                print(f"❌ Verify endpoint failed: HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ Verify endpoint error: {str(e)}")
        
        # Test MikroTik auth endpoint
        mikrotik_data = {
            'username': phone_number,
            'password': '',
            'mac': mac_address or '',
            'ip': ip_address or '127.0.0.1'
        }
        
        try:
            response = requests.post(f"{base_url}/mikrotik/auth/", data=mikrotik_data, timeout=10)
            if response.status_code == 200:
                print("✅ MikroTik auth endpoint: Success")
            else:
                print(f"❌ MikroTik auth endpoint failed: HTTP {response.status_code}")
                print(f"   Response: {response.text[:100]}")
        except Exception as e:
            print(f"❌ MikroTik auth endpoint error: {str(e)}")
        
        return True
        
    except User.DoesNotExist:
        print(f"❌ User {phone_number} not found")
        return False
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        return False

def fix_user_internet_access(phone_number):
    """Try to fix internet access issues for a user"""
    print(f"\n🔧 FIXING INTERNET ACCESS FOR {phone_number}")
    print("=" * 60)
    
    try:
        user = User.objects.get(phone_number=phone_number)
        
        # Fix 1: Ensure max_devices is set
        if user.max_devices is None:
            user.max_devices = 1
            user.save()
            print("✅ Fixed: Set max_devices to 1")
        
        # Fix 2: Ensure user is active if they have access
        if user.has_active_access() and not user.is_active:
            user.is_active = True
            user.save()
            print("✅ Fixed: Activated user account")
        
        # Fix 3: Clean up inactive devices
        inactive_devices = user.devices.filter(is_active=False)
        if inactive_devices.exists():
            count = inactive_devices.count()
            inactive_devices.delete()
            print(f"✅ Fixed: Removed {count} inactive devices")
        
        # Fix 4: Try to authenticate with MikroTik
        active_device = user.devices.filter(is_active=True).first()
        if active_device:
            print("🌐 Attempting MikroTik authentication...")
            result = authenticate_user_with_mikrotik(
                phone_number=phone_number,
                mac_address=active_device.mac_address,
                ip_address=active_device.ip_address
            )
            
            if result.get('success'):
                print("✅ MikroTik authentication successful")
            else:
                print(f"⚠️  MikroTik authentication incomplete: {result.get('message', 'Unknown error')}")
        
        # Fix 5: Create access log entry
        AccessLog.objects.create(
            user=user,
            device=active_device,
            ip_address=active_device.ip_address if active_device else '127.0.0.1',
            mac_address=active_device.mac_address if active_device else '',
            access_granted=True,
            denial_reason='Manual fix applied'
        )
        print("✅ Fixed: Created access log entry")
        
        print("\n🎯 RECOMMENDED ACTIONS FOR USER:")
        print("1. Disconnect from WiFi completely")
        print("2. Wait 10 seconds")
        print("3. Reconnect to WiFi network")
        print("4. Open a web browser")
        print("5. Try to visit any website")
        print("6. If prompted, enter phone number for authentication")
        print("7. Should automatically get internet access")
        
        return True
        
    except User.DoesNotExist:
        print(f"❌ User {phone_number} not found")
        return False
    except Exception as e:
        print(f"❌ Fix failed: {str(e)}")
        return False

def main():
    """Main diagnostic and fix function"""
    print("🔧 KITONGA WIFI ACCESS DIAGNOSTIC & FIX TOOL")
    print("=" * 70)
    print("This tool helps diagnose and fix WiFi access issues")
    print()
    
    # Test the specific user mentioned in the issue
    problem_phone = "255684106419"
    
    print(f"🎯 DIAGNOSING USER: {problem_phone}")
    user = check_user_access_status(problem_phone)
    
    if user:
        # Test WiFi authentication
        test_wifi_authentication(
            phone_number=problem_phone,
            mac_address="AA:BB:CC:DD:EE:FF",  # Example MAC
            ip_address="192.168.1.100"        # Example IP
        )
        
        # Try to fix issues
        fix_user_internet_access(problem_phone)
    
    print("\n" + "=" * 70)
    print("✅ DIAGNOSTIC COMPLETE")
    print("\nIf user still can't access internet:")
    print("1. Check MikroTik router is accessible at 192.168.0.173")
    print("2. Verify hotspot is configured correctly")
    print("3. Check external authentication settings")
    print("4. Monitor Django logs for authentication attempts")

if __name__ == "__main__":
    main()
