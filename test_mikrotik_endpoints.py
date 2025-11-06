#!/usr/bin/env python3
"""
Test MikroTik authentication endpoints directly
Bypasses Django's SSL redirect for development testing
"""

import os
import django
import json
from django.test import RequestFactory
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from billing.views import mikrotik_auth, mikrotik_logout

def test_mikrotik_auth():
    """Test MikroTik authentication endpoint directly"""
    print("🔧 TESTING MIKROTIK AUTHENTICATION ENDPOINT")
    print("=" * 60)
    
    factory = RequestFactory()
    
    # Test data
    test_data = {
        'username': '255684106419',
        'mac': 'AA:BB:CC:DD:EE:FF',
        'ip': '192.168.1.100'
    }
    
    print(f"Test data: {test_data}")
    
    # Test 1: JSON request (frontend call)
    print("\n1. Testing JSON request (frontend call):")
    request = factory.post('/api/mikrotik/auth/', 
                          data=json.dumps(test_data),
                          content_type='application/json')
    request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0 (Testing Frontend)'
    
    try:
        response = mikrotik_auth(request)
        print(f"   Status Code: {response.status_code}")
        print(f"   Content-Type: {response.get('Content-Type', 'Not set')}")
        if hasattr(response, 'content'):
            try:
                content = json.loads(response.content.decode('utf-8'))
                print(f"   Response: {json.dumps(content, indent=2)}")
            except:
                print(f"   Response: {response.content.decode('utf-8')}")
    except Exception as e:
        print(f"   Error: {str(e)}")
    
    # Test 2: Form data request (MikroTik router call)
    print("\n2. Testing form data request (MikroTik router call):")
    request = factory.post('/api/mikrotik/auth/', data=test_data)
    request.META['HTTP_USER_AGENT'] = 'MikroTik/6.40'
    
    try:
        response = mikrotik_auth(request)
        print(f"   Status Code: {response.status_code}")
        print(f"   Content-Type: {response.get('Content-Type', 'Not set')}")
        if hasattr(response, 'content'):
            print(f"   Response: {response.content.decode('utf-8')}")
    except Exception as e:
        print(f"   Error: {str(e)}")

def test_mikrotik_logout():
    """Test MikroTik logout endpoint directly"""
    print("\n🔧 TESTING MIKROTIK LOGOUT ENDPOINT")
    print("=" * 60)
    
    factory = RequestFactory()
    
    # Test data
    test_data = {
        'username': '255684106419',
        'ip': '192.168.1.100'
    }
    
    print(f"Test data: {test_data}")
    
    # Test JSON request (frontend call)
    print("\n1. Testing JSON logout request:")
    request = factory.post('/api/mikrotik/logout/', 
                          data=json.dumps(test_data),
                          content_type='application/json')
    request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0 (Testing Frontend)'
    
    try:
        response = mikrotik_logout(request)
        print(f"   Status Code: {response.status_code}")
        print(f"   Content-Type: {response.get('Content-Type', 'Not set')}")
        if hasattr(response, 'content'):
            try:
                content = json.loads(response.content.decode('utf-8'))
                print(f"   Response: {json.dumps(content, indent=2)}")
            except:
                print(f"   Response: {response.content.decode('utf-8')}")
    except Exception as e:
        print(f"   Error: {str(e)}")

def main():
    """Main test function"""
    print("🚀 MIKROTIK ENDPOINT TESTING")
    print("=" * 70)
    print("Testing MikroTik authentication and logout endpoints directly")
    print("This bypasses Django's SSL redirect for development testing")
    print()
    
    test_mikrotik_auth()
    test_mikrotik_logout()
    
    print("\n" + "=" * 70)
    print("✅ TESTING COMPLETE")
    print()
    print("If you see successful responses above, the endpoints are working.")
    print("The SSL redirect is preventing browser/curl access in development.")
    print("For production, this SSL redirect is important for security.")

if __name__ == '__main__':
    main()
