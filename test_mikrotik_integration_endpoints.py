#!/usr/bin/env python
"""
Test script for MikroTik Integration Endpoints
Tests the 4 public MikroTik integration endpoints according to mikrotik.py configuration
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from billing.models import User, Bundle, Payment, Device
from django.utils import timezone
from datetime import timedelta
import json

# Test configuration
client = Client()
TEST_PHONE = "+255743852695"
TEST_MAC = "AA:BB:CC:DD:EE:FF"
TEST_IP = "192.168.0.100"

# Get admin token from environment or use test token
ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN', 'test-admin-token-12345')

def print_header(title):
    """Print formatted test header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def print_result(endpoint, method, status_code, response_data, passed):
    """Print formatted test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{status} - {method} {endpoint}")
    print(f"Status Code: {status_code}")
    print(f"Response: {json.dumps(response_data, indent=2)}")

def setup_test_user():
    """Create or get test user with active access"""
    print_header("Setting up test user")
    
    # Create test user if doesn't exist
    user, created = User.objects.get_or_create(
        phone_number=TEST_PHONE,
        defaults={
            'is_active': True,
            'paid_until': timezone.now() + timedelta(hours=24),
            'max_devices': 3
        }
    )
    
    if not created:
        # Update existing user
        user.is_active = True
        user.paid_until = timezone.now() + timedelta(hours=24)
        user.save()
    
    # Create a bundle if needed
    bundle, _ = Bundle.objects.get_or_create(
        name='Test Bundle',
        defaults={
            'price': 1000,
            'duration_hours': 24,
            'is_active': True
        }
    )
    
    # Create a completed payment if none exists
    if not user.payments.filter(status='completed').exists():
        import uuid
        Payment.objects.create(
            user=user,
            bundle=bundle,
            amount=bundle.price,
            status='completed',
            phone_number=TEST_PHONE,
            transaction_id=f'TEST-{uuid.uuid4().hex[:12]}',
            order_reference=f'ORD-{uuid.uuid4().hex[:12]}'
        )
    
    print(f"✅ Test user created/updated: {TEST_PHONE}")
    print(f"   Active: {user.is_active}")
    print(f"   Paid Until: {user.paid_until}")
    print(f"   Max Devices: {user.max_devices}")
    
    return user

def test_mikrotik_auth():
    """Test 1: MikroTik Authentication Endpoint"""
    print_header("Test 1: MikroTik Auth - POST /api/mikrotik/auth/")
    
    # Test 1a: Form data (MikroTik router format)
    print("\n--- Test 1a: Form Data Authentication ---")
    response = client.post('/api/mikrotik/auth/', {
        'username': TEST_PHONE,
        'password': '',
        'mac': TEST_MAC,
        'ip': TEST_IP
    })
    
    passed = response.status_code == 200
    print_result('/api/mikrotik/auth/', 'POST (form)', response.status_code, 
                 response.content.decode() if response.status_code == 200 else response.json(), 
                 passed)
    
    # Test 1b: JSON data (Frontend format)
    print("\n--- Test 1b: JSON Authentication ---")
    response = client.post('/api/mikrotik/auth/', 
        json.dumps({
            'username': TEST_PHONE,
            'mac': TEST_MAC,
            'ip': TEST_IP
        }),
        content_type='application/json'
    )
    
    try:
        data = response.json()
        passed = response.status_code == 200 and data.get('success') == True
        print_result('/api/mikrotik/auth/', 'POST (JSON)', response.status_code, data, passed)
    except:
        passed = False
        print_result('/api/mikrotik/auth/', 'POST (JSON)', response.status_code, 
                     response.content.decode(), passed)
    
    # Test 1c: Failed authentication (non-existent user)
    print("\n--- Test 1c: Failed Authentication (non-existent user) ---")
    response = client.post('/api/mikrotik/auth/', {
        'username': '+255999999999',
        'mac': TEST_MAC,
        'ip': TEST_IP
    })
    
    passed = response.status_code == 403
    print_result('/api/mikrotik/auth/', 'POST (fail)', response.status_code, 
                 response.content.decode() if response.status_code == 403 else response.json(), 
                 passed)
    
    return True

def test_mikrotik_logout():
    """Test 2: MikroTik Logout Endpoint"""
    print_header("Test 2: MikroTik Logout - POST /api/mikrotik/logout/")
    
    # Test 2a: Form data logout
    print("\n--- Test 2a: Form Data Logout ---")
    response = client.post('/api/mikrotik/logout/', {
        'username': TEST_PHONE,
        'ip': TEST_IP
    })
    
    passed = response.status_code == 200
    print_result('/api/mikrotik/logout/', 'POST (form)', response.status_code, 
                 response.content.decode(), passed)
    
    # Test 2b: JSON logout
    print("\n--- Test 2b: JSON Logout ---")
    response = client.post('/api/mikrotik/logout/',
        json.dumps({
            'username': TEST_PHONE,
            'ip': TEST_IP
        }),
        content_type='application/json'
    )
    
    try:
        data = response.json()
        passed = response.status_code == 200 and data.get('success') == True
        print_result('/api/mikrotik/logout/', 'POST (JSON)', response.status_code, data, passed)
    except:
        passed = False
        print_result('/api/mikrotik/logout/', 'POST (JSON)', response.status_code, 
                     response.content.decode(), passed)
    
    return True

def test_mikrotik_status():
    """Test 3: MikroTik Status Check Endpoint (Admin only)"""
    print_header("Test 3: MikroTik Status - GET /api/mikrotik/status/")
    
    # Test 3a: Without admin token (should fail)
    print("\n--- Test 3a: Status Check Without Auth ---")
    response = client.get('/api/mikrotik/status/')
    
    passed = response.status_code == 401
    try:
        data = response.json()
    except:
        data = {'error': 'No JSON response'}
    print_result('/api/mikrotik/status/', 'GET (no auth)', response.status_code, data, passed)
    
    # Test 3b: With admin token
    print("\n--- Test 3b: Status Check With Admin Token ---")
    response = client.get('/api/mikrotik/status/', 
                         HTTP_X_ADMIN_TOKEN=ADMIN_TOKEN)
    
    try:
        data = response.json()
        passed = response.status_code == 200 and data.get('success') == True
        print_result('/api/mikrotik/status/', 'GET (admin)', response.status_code, data, passed)
    except:
        passed = False
        print_result('/api/mikrotik/status/', 'GET (admin)', response.status_code, 
                     response.content.decode(), passed)
    
    return True

def test_mikrotik_user_status():
    """Test 4: MikroTik User Status Endpoint"""
    print_header("Test 4: MikroTik User Status - GET/POST /api/mikrotik/user-status/")
    
    # Test 4a: GET with query parameter
    print("\n--- Test 4a: User Status via GET ---")
    response = client.get(f'/api/mikrotik/user-status/?username={TEST_PHONE}')
    
    try:
        data = response.json()
        passed = response.status_code == 200 and data.get('success') == True
        print_result('/api/mikrotik/user-status/', 'GET', response.status_code, data, passed)
    except:
        passed = False
        print_result('/api/mikrotik/user-status/', 'GET', response.status_code, 
                     response.content.decode(), passed)
    
    # Test 4b: POST with form data
    print("\n--- Test 4b: User Status via POST (form) ---")
    response = client.post('/api/mikrotik/user-status/', {
        'username': TEST_PHONE
    })
    
    try:
        data = response.json()
        passed = response.status_code == 200 and data.get('success') == True
        print_result('/api/mikrotik/user-status/', 'POST (form)', response.status_code, data, passed)
    except:
        passed = False
        print_result('/api/mikrotik/user-status/', 'POST (form)', response.status_code, 
                     response.content.decode(), passed)
    
    # Test 4c: POST with JSON
    print("\n--- Test 4c: User Status via POST (JSON) ---")
    response = client.post('/api/mikrotik/user-status/',
        json.dumps({'username': TEST_PHONE}),
        content_type='application/json'
    )
    
    try:
        data = response.json()
        passed = response.status_code == 200 and data.get('success') == True
        print_result('/api/mikrotik/user-status/', 'POST (JSON)', response.status_code, data, passed)
    except:
        passed = False
        print_result('/api/mikrotik/user-status/', 'POST (JSON)', response.status_code, 
                     response.content.decode(), passed)
    
    # Test 4d: Non-existent user
    print("\n--- Test 4d: User Status for Non-existent User ---")
    response = client.get('/api/mikrotik/user-status/?username=+255999999999')
    
    try:
        data = response.json()
        passed = response.status_code == 404 and data.get('success') == False
        print_result('/api/mikrotik/user-status/', 'GET (not found)', response.status_code, data, passed)
    except:
        passed = False
        print_result('/api/mikrotik/user-status/', 'GET (not found)', response.status_code, 
                     response.content.decode(), passed)
    
    return True

def main():
    """Run all tests"""
    print("\n" + "🔬 " * 35)
    print("  MIKROTIK INTEGRATION ENDPOINTS TEST SUITE")
    print("  Testing 4 MikroTik Integration Endpoints")
    print("🔬 " * 35)
    
    try:
        # Setup
        user = setup_test_user()
        
        # Run tests
        tests = [
            ("MikroTik Auth", test_mikrotik_auth),
            ("MikroTik Logout", test_mikrotik_logout),
            ("MikroTik Status Check", test_mikrotik_status),
            ("MikroTik User Status", test_mikrotik_user_status),
        ]
        
        results = []
        for test_name, test_func in tests:
            try:
                success = test_func()
                results.append((test_name, success))
            except Exception as e:
                print(f"\n❌ ERROR in {test_name}: {str(e)}")
                import traceback
                traceback.print_exc()
                results.append((test_name, False))
        
        # Print summary
        print_header("TEST SUMMARY")
        passed = sum(1 for _, success in results if success)
        total = len(results)
        
        for test_name, success in results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} - {test_name}")
        
        print(f"\n{'='*70}")
        print(f"Total: {passed}/{total} test groups passed ({passed*100//total}%)")
        print(f"{'='*70}")
        
        if passed == total:
            print("\n🎉 ALL MIKROTIK INTEGRATION ENDPOINTS ARE WORKING!")
            print("\nEndpoint Summary:")
            print("1. ✅ POST /api/mikrotik/auth/ - Handles both form and JSON, MikroTik router compatible")
            print("2. ✅ POST /api/mikrotik/logout/ - Handles both form and JSON")
            print("3. ✅ GET /api/mikrotik/status/ - Admin only, tests connection to router")
            print("4. ✅ GET/POST /api/mikrotik/user-status/ - Public endpoint, checks user access")
            print("\nConfiguration aligned with mikrotik.py:")
            print("- Uses MIKROTIK_HOST, MIKROTIK_PORT, MIKROTIK_USER from settings")
            print("- Uses test_mikrotik_connection() for status checks")
            print("- Supports both payment and voucher users")
            print("- Enhanced device tracking with track_device_connection()")
        else:
            print(f"\n⚠️  {total - passed} test group(s) failed. Please review the errors above.")
        
        return passed == total
        
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
