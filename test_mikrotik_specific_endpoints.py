#!/usr/bin/env python
"""
Test script for specific MikroTik admin endpoints:
- admin/mikrotik/active-users/
- admin/mikrotik/profiles/
"""
import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from django.test import Client
from django.urls import reverse
import json

class TestMikroTikSpecificEndpoints:
    def __init__(self):
        self.client = Client()
        self.admin_token = "kitonga_admin_2025"
        self.headers = {'HTTP_X_ADMIN_ACCESS': self.admin_token}
        
    def test_mikrotik_active_users(self):
        """Test GET /admin/mikrotik/active-users/ - Get list of active users on MikroTik router"""
        print("\n" + "="*80)
        print("TEST: Get Active Users from MikroTik Router")
        print("="*80)
        
        url = reverse('mikrotik_active_users')
        print(f"URL: GET {url}")
        print(f"Headers: X-Admin-Access: {self.admin_token}")
        
        response = self.client.get(url, **self.headers)
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response Data:")
        print(json.dumps(response.json(), indent=2))
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert 'active_users' in data, "Response should contain 'active_users'"
        assert isinstance(data['active_users'], list), "'active_users' should be a list"
        
        print(f"\n✅ PASSED: Found {len(data['active_users'])} active users")
        return True
        
    def test_mikrotik_hotspot_profiles(self):
        """Test GET /admin/mikrotik/profiles/ - Get list of hotspot profiles from MikroTik router"""
        print("\n" + "="*80)
        print("TEST: Get Hotspot Profiles from MikroTik Router")
        print("="*80)
        
        url = reverse('mikrotik_hotspot_profiles')
        print(f"URL: GET {url}")
        print(f"Headers: X-Admin-Access: {self.admin_token}")
        
        response = self.client.get(url, **self.headers)
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response Data:")
        print(json.dumps(response.json(), indent=2))
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert 'profiles' in data, "Response should contain 'profiles'"
        assert isinstance(data['profiles'], list), "'profiles' should be a list"
        
        print(f"\n✅ PASSED: Found {len(data['profiles'])} hotspot profiles")
        return True
    
    def test_authentication_required(self):
        """Test that both endpoints require admin authentication"""
        print("\n" + "="*80)
        print("TEST: Authentication Required")
        print("="*80)
        
        endpoints = [
            ('mikrotik_active_users', 'admin/mikrotik/active-users/'),
            ('mikrotik_hotspot_profiles', 'admin/mikrotik/profiles/')
        ]
        
        for endpoint_name, endpoint_path in endpoints:
            print(f"\nTesting {endpoint_path} without authentication...")
            url = reverse(endpoint_name)
            response = self.client.get(url)
            
            print(f"Status Code: {response.status_code}")
            assert response.status_code == 403, f"Expected 403 Forbidden, got {response.status_code}"
            print(f"✅ Correctly returns 403 Forbidden without admin token")
        
        return True

def main():
    print("\n" + "="*80)
    print("MIKROTIK SPECIFIC ENDPOINTS TEST SUITE")
    print("Testing: admin/mikrotik/active-users/ and admin/mikrotik/profiles/")
    print("="*80)
    
    tester = TestMikroTikSpecificEndpoints()
    results = []
    
    # Run tests
    tests = [
        ("Authentication Required", tester.test_authentication_required),
        ("Get Active Users", tester.test_mikrotik_active_users),
        ("Get Hotspot Profiles", tester.test_mikrotik_hotspot_profiles),
    ]
    
    for test_name, test_func in tests:
        try:
            test_func()
            results.append((test_name, "PASSED", None))
        except AssertionError as e:
            results.append((test_name, "FAILED", str(e)))
            print(f"\n❌ FAILED: {e}")
        except Exception as e:
            results.append((test_name, "ERROR", str(e)))
            print(f"\n❌ ERROR: {e}")
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, status, _ in results if status == "PASSED")
    failed = sum(1 for _, status, _ in results if status == "FAILED")
    errors = sum(1 for _, status, _ in results if status == "ERROR")
    
    for test_name, status, error in results:
        icon = "✅" if status == "PASSED" else "❌"
        print(f"{icon} {test_name}: {status}")
        if error:
            print(f"   Error: {error}")
    
    print(f"\nTotal: {len(results)} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Errors: {errors}")
    print(f"Success Rate: {(passed/len(results)*100):.1f}%")
    
    if failed > 0 or errors > 0:
        sys.exit(1)
    
    print("\n🎉 All tests passed!")

if __name__ == '__main__':
    main()
