#!/usr/bin/env python3
"""
Direct API Test for Device Tracking
"""
import os
import sys
import django

# Setup Django
sys.path.append('/Users/macbookair/Desktop/kitonga')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'billing.settings')
django.setup()

from billing.views import mikrotik_auth
from django.test import RequestFactory
from django.http import HttpRequest
import json

def test_mikrotik_auth_direct():
    """Test mikrotik_auth function directly with proper parameters"""
    
    print("=" * 50)
    print("DIRECT MIKROTIK AUTH API TEST")
    print("=" * 50)
    
    # Test 1: Form data (like MikroTik router would send)
    print("\n1. Testing with form data (MikroTik style):")
    
    factory = RequestFactory()
    request = factory.post('/api/mikrotik/auth/', {
        'username': '255684106419',
        'password': '',
        'mac': 'AA:BB:CC:DD:EE:FF',
        'ip': '192.168.88.100'
    })
    
    response = mikrotik_auth(request)
    print(f"   Status: {response.status_code}")
    if hasattr(response, 'content'):
        try:
            if response['Content-Type'] == 'application/json':
                data = json.loads(response.content)
                print(f"   Response: {data}")
            else:
                print(f"   Response: {response.content.decode()}")
        except:
            print(f"   Response: {response.content}")
    
    # Test 2: JSON data (frontend API call)
    print("\n2. Testing with JSON data (Frontend API style):")
    
    json_data = {
        'username': '255684106419',
        'mac': 'AA:BB:CC:DD:EE:FF',
        'ip': '192.168.88.100'
    }
    
    request = factory.post('/api/mikrotik/auth/', 
                          data=json.dumps(json_data),
                          content_type='application/json')
    request.META['HTTP_ACCEPT'] = 'application/json'
    request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0 Test Browser'
    
    response = mikrotik_auth(request)
    print(f"   Status: {response.status_code}")
    try:
        data = json.loads(response.content)
        print(f"   Response: {data}")
        print(f"   Device count: {data.get('device_count', 'N/A')}")
        print(f"   Max devices: {data.get('max_devices', 'N/A')}")
        print(f"   Success: {data.get('success', 'N/A')}")
    except Exception as e:
        print(f"   Error parsing response: {e}")
        print(f"   Raw response: {response.content}")

def test_user_device_count():
    """Test user device count directly"""
    
    print("\n" + "=" * 50)
    print("DIRECT USER DEVICE COUNT TEST")
    print("=" * 50)
    
    from billing.models import User, Device
    
    try:
        user = User.objects.get(phone_number='255684106419')
        print(f"\nUser: {user.phone_number}")
        print(f"Max devices: {user.max_devices}")
        print(f"Has active access: {user.has_active_access()}")
        print(f"Access until: {user.paid_until}")
        
        # Device counts
        active_devices = user.get_active_devices()
        all_devices = user.devices.all()
        
        print(f"\nDevice Counts:")
        print(f"Active devices: {active_devices.count()}")
        print(f"Total devices: {all_devices.count()}")
        
        print(f"\nDevice Details:")
        for device in all_devices:
            status = "🟢 Active" if device.is_active else "🔴 Inactive"
            print(f"  {status} {device.mac_address} - {device.device_name}")
            print(f"    IP: {device.ip_address}")
            print(f"    First seen: {device.first_seen}")
            print(f"    Last seen: {device.last_seen}")
        
        return active_devices.count()
        
    except User.DoesNotExist:
        print("❌ Test user not found")
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 0

def test_authentication_flow():
    """Test the complete authentication flow"""
    
    print("\n" + "=" * 50)
    print("COMPLETE AUTHENTICATION FLOW TEST")
    print("=" * 50)
    
    from billing.models import User, Device, AccessLog
    from billing.mikrotik import track_device_connection
    
    phone_number = '255684106419'
    mac_address = 'BB:CC:DD:EE:FF:00'
    ip_address = '192.168.88.101'
    
    print(f"\nTesting authentication flow for {phone_number}")
    print(f"MAC: {mac_address}, IP: {ip_address}")
    
    try:
        # 1. Track device connection
        print("\n1. Testing device tracking...")
        result = track_device_connection(
            phone_number=phone_number,
            mac_address=mac_address,
            ip_address=ip_address,
            connection_type='wifi',
            access_method='test'
        )
        
        print(f"   Device tracking result: {result}")
        
        # 2. Test authentication
        print("\n2. Testing authentication...")
        factory = RequestFactory()
        request = factory.post('/api/mikrotik/auth/', {
            'username': phone_number,
            'mac': mac_address,
            'ip': ip_address
        })
        request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0 Test Browser'
        request.META['HTTP_ACCEPT'] = 'application/json'
        
        response = mikrotik_auth(request)
        print(f"   Auth status: {response.status_code}")
        
        if response.status_code == 200:
            data = json.loads(response.content)
            print(f"   ✅ Authentication successful!")
            print(f"   Device count: {data.get('device_count', 'N/A')}")
            print(f"   Max devices: {data.get('max_devices', 'N/A')}")
            print(f"   Access type: {data.get('access_type', 'N/A')}")
        else:
            try:
                data = json.loads(response.content)
                print(f"   ❌ Authentication failed: {data.get('error', 'Unknown error')}")
            except:
                print(f"   ❌ Authentication failed: {response.content}")
        
        # 3. Check final device count
        print("\n3. Final device count check...")
        final_count = test_user_device_count()
        print(f"   Final active device count: {final_count}")
        
    except Exception as e:
        print(f"❌ Error in authentication flow: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Starting direct API tests...")
    
    # Test device count first
    device_count = test_user_device_count()
    
    # Test API directly
    test_mikrotik_auth_direct()
    
    # Test complete flow
    test_authentication_flow()
    
    print("\n" + "=" * 50)
    print("✅ DIRECT API TESTS COMPLETED")
    print("=" * 50)
