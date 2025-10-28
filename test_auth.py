#!/usr/bin/env python3
"""
Kitonga Wi-Fi Authentication Troubleshooting Script
Tests all authentication methods and provides debugging information
"""

import os
import sys
import django
import requests
import json
from pathlib import Path

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from django.conf import settings
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

# Configuration
API_BASE_URL = 'http://127.0.0.1:8000'  # Change to your server URL
ADMIN_USERNAME = 'admin'  # Updated to match actual admin user
ADMIN_PASSWORD = 'admin123'  # Change to your admin password

def test_health_check():
    """Test basic API connectivity"""
    print("🔍 Testing API Health Check...")
    try:
        response = requests.get(f"{API_BASE_URL}/api/health/")
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ API is healthy: {data.get('status')}")
            return True
        else:
            print(f"  ❌ Health check failed: {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"  ❌ Connection failed: {e}")
        return False

def test_admin_login():
    """Test admin login and get tokens"""
    print("\n🔐 Testing Admin Login...")
    try:
        response = requests.post(f"{API_BASE_URL}/api/auth/login/", 
                               json={
                                   'username': ADMIN_USERNAME,
                                   'password': ADMIN_PASSWORD
                               })
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"  ✅ Login successful")
                print(f"  📄 User: {data['user']['username']} (Staff: {data['user']['is_staff']})")
                print(f"  🎫 Django Token: {data['token'][:20]}...")
                print(f"  🔑 Admin Token: {data['admin_access_token']}")
                return data['token'], data['admin_access_token']
            else:
                print(f"  ❌ Login failed: {data.get('message')}")
        else:
            print(f"  ❌ Login request failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"  📄 Error details: {error_data}")
            except:
                print(f"  📄 Response: {response.text}")
    except requests.RequestException as e:
        print(f"  ❌ Request failed: {e}")
    
    return None, None

def test_token_authentication(django_token):
    """Test API calls with Django token"""
    print(f"\n🎫 Testing Django Token Authentication...")
    if not django_token:
        print("  ⚠️  No Django token available")
        return False
    
    headers = {'Authorization': f'Token {django_token}'}
    
    # Test endpoints that require authentication
    endpoints = [
        '/api/auth/profile/',
        '/api/dashboard-stats/',
        '/api/mikrotik/status/',
        '/api/vouchers/list/'
    ]
    
    success_count = 0
    for endpoint in endpoints:
        try:
            response = requests.get(f"{API_BASE_URL}{endpoint}", headers=headers)
            if response.status_code == 200:
                print(f"  ✅ {endpoint}: Success")
                success_count += 1
            elif response.status_code == 403:
                print(f"  ❌ {endpoint}: Permission denied (403)")
            elif response.status_code == 401:
                print(f"  ❌ {endpoint}: Unauthorized (401)")
            else:
                print(f"  ⚠️  {endpoint}: HTTP {response.status_code}")
        except requests.RequestException as e:
            print(f"  ❌ {endpoint}: Request failed - {e}")
    
    print(f"  📊 Token auth success rate: {success_count}/{len(endpoints)}")
    return success_count == len(endpoints)

def test_admin_token_authentication(admin_token):
    """Test API calls with static admin token"""
    print(f"\n🔑 Testing Static Admin Token Authentication...")
    if not admin_token:
        print("  ⚠️  No admin token available")
        return False
    
    headers = {'X-Admin-Access': admin_token}
    
    # Test endpoints that require authentication
    endpoints = [
        '/api/dashboard-stats/',
        '/api/mikrotik/status/',
        '/api/vouchers/list/'
    ]
    
    success_count = 0
    for endpoint in endpoints:
        try:
            response = requests.get(f"{API_BASE_URL}{endpoint}", headers=headers)
            if response.status_code == 200:
                print(f"  ✅ {endpoint}: Success")
                success_count += 1
            elif response.status_code == 403:
                print(f"  ❌ {endpoint}: Permission denied (403)")
            elif response.status_code == 401:
                print(f"  ❌ {endpoint}: Unauthorized (401)")
            else:
                print(f"  ⚠️  {endpoint}: HTTP {response.status_code}")
        except requests.RequestException as e:
            print(f"  ❌ {endpoint}: Request failed - {e}")
    
    print(f"  📊 Admin token auth success rate: {success_count}/{len(endpoints)}")
    return success_count == len(endpoints)

def test_no_authentication():
    """Test API calls without authentication (should fail)"""
    print(f"\n🚫 Testing No Authentication (should fail)...")
    
    # Test endpoints that require authentication
    endpoints = [
        '/api/auth/profile/',
        '/api/dashboard-stats/',
        '/api/mikrotik/status/'
    ]
    
    failed_count = 0
    for endpoint in endpoints:
        try:
            response = requests.get(f"{API_BASE_URL}{endpoint}")
            if response.status_code in [401, 403]:
                print(f"  ✅ {endpoint}: Correctly denied (HTTP {response.status_code})")
                failed_count += 1
            else:
                print(f"  ❌ {endpoint}: Unexpectedly allowed (HTTP {response.status_code})")
        except requests.RequestException as e:
            print(f"  ❌ {endpoint}: Request failed - {e}")
    
    print(f"  📊 Properly protected endpoints: {failed_count}/{len(endpoints)}")
    return failed_count == len(endpoints)

def check_database_users():
    """Check users and tokens in database"""
    print(f"\n💾 Checking Database Users and Tokens...")
    
    try:
        users = User.objects.filter(is_staff=True)
        print(f"  👥 Admin users in database: {users.count()}")
        
        for user in users:
            print(f"    - {user.username} (Staff: {user.is_staff}, Active: {user.is_active})")
            try:
                token = Token.objects.get(user=user)
                print(f"      🎫 Token: {token.key[:20]}...")
            except Token.DoesNotExist:
                print(f"      ⚠️  No token found")
    except Exception as e:
        print(f"  ❌ Database check failed: {e}")

def show_configuration():
    """Show current configuration"""
    print(f"\n⚙️  Current Configuration:")
    print(f"  🌐 API URL: {API_BASE_URL}")
    print(f"  👤 Admin Username: {ADMIN_USERNAME}")
    print(f"  🔑 Simple Admin Token: {getattr(settings, 'SIMPLE_ADMIN_TOKEN', 'Not set')}")
    print(f"  🛡️  Debug Mode: {settings.DEBUG}")
    print(f"  🏠 Allowed Hosts: {settings.ALLOWED_HOSTS}")

def generate_frontend_code(django_token, admin_token):
    """Generate frontend code examples"""
    print(f"\n💻 Frontend Integration Code:")
    print(f"```javascript")
    print(f"// Method 1: Using Django Token (recommended)")
    print(f"const headers = {{")
    if django_token:
        print(f"    'Authorization': 'Token {django_token}',")
    print(f"    'Content-Type': 'application/json'")
    print(f"}};")
    print(f"")
    print(f"// Method 2: Using Static Admin Token")
    print(f"const headers = {{")
    if admin_token:
        print(f"    'X-Admin-Access': '{admin_token}',")
    print(f"    'Content-Type': 'application/json'")
    print(f"}};")
    print(f"")
    print(f"// Example API call")
    print(f"fetch('{API_BASE_URL}/dashboard-stats/', {{ headers }})") 
    print(f"    .then(response => response.json())")
    print(f"    .then(data => console.log(data));")
    print(f"```")

def main():
    """Run all authentication tests"""
    print("🔐 Kitonga Wi-Fi Authentication Troubleshooting")
    print("=" * 50)
    
    show_configuration()
    check_database_users()
    
    # Test basic connectivity
    if not test_health_check():
        print("\n❌ Cannot connect to API. Please ensure the server is running.")
        return
    
    # Test login and get tokens
    django_token, admin_token = test_admin_login()
    
    # Test different authentication methods
    test_no_authentication()
    
    if django_token:
        test_token_authentication(django_token)
    
    if admin_token:
        test_admin_token_authentication(admin_token)
    
    # Generate frontend code
    generate_frontend_code(django_token, admin_token)
    
    print(f"\n" + "=" * 50)
    print(f"✨ Authentication test completed!")
    
    if django_token or admin_token:
        print(f"🎉 Authentication is working correctly!")
        print(f"💡 Use the generated frontend code above for your application.")
    else:
        print(f"⚠️  Authentication issues detected. Check:")
        print(f"   1. Admin user exists and has correct password")
        print(f"   2. User has is_staff=True permission")
        print(f"   3. Server is running correctly")

if __name__ == "__main__":
    main()
