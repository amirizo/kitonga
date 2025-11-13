#!/usr/bin/env python3
"""
Test script for User Management API endpoints
Tests the shorter frontend-compatible endpoints:
- GET /api/users/ (list all users)
- GET /api/users/<user_id>/ (get user detail)
"""

import os
import sys
import django
import requests
from datetime import datetime

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from billing.models import User, Bundle

# Configuration
BASE_URL = "http://127.0.0.1:8000/api"
ADMIN_TOKEN = "kitonga_admin_2025"

def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")

def test_list_users():
    """Test GET /api/users/ endpoint"""
    print_section("TEST 1: List All Users")
    
    url = f"{BASE_URL}/users/"
    headers = {
        "X-Admin-Access": ADMIN_TOKEN,
        "Content-Type": "application/json"
    }
    
    print(f"Endpoint: GET {url}")
    print(f"Headers: {headers}\n")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}\n")
        
        if response.status_code == 200:
            data = response.json()
            
            # Handle both list and dict response formats
            if isinstance(data, dict):
                # Response is wrapped in a dict (e.g., {'success': True, 'users': [...]})
                if 'users' in data:
                    users_list = data['users']
                elif 'data' in data:
                    users_list = data['data']
                else:
                    # Assume the dict itself is the user data
                    users_list = [data]
            else:
                # Response is a list
                users_list = data
            
            print(f"✅ SUCCESS - Retrieved {len(users_list)} users\n")
            
            if users_list:
                print("Sample User Data (first user):")
                first_user = users_list[0]
                for key, value in first_user.items():
                    print(f"  {key}: {value}")
                
                print(f"\nAll Users Summary:")
                for user in users_list:
                    print(f"  - ID: {user.get('id')}, Phone: {user.get('phone_number')}, "
                          f"Status: {user.get('status')}, Devices: {user.get('device_count')}")
            else:
                print("No users found in database")
            
            return True
        else:
            print(f"❌ FAILED - {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def test_get_user_detail():
    """Test GET /api/users/<user_id>/ endpoint"""
    print_section("TEST 2: Get User Detail")
    
    # First, get a user ID from the database
    users = User.objects.all()
    if not users.exists():
        print("⚠️  No users in database. Creating a test user...")
        
        # Create a test user
        bundle = Bundle.objects.first()
        if not bundle:
            print("❌ No bundles available to create test user")
            return False
        
        test_user = User.objects.create(
            phone_number="+255700000999",
            bundle=bundle,
            status='active'
        )
        user_id = test_user.id
        print(f"✅ Created test user with ID: {user_id}\n")
    else:
        user_id = users.first().id
        print(f"Using existing user with ID: {user_id}\n")
    
    url = f"{BASE_URL}/users/{user_id}/"
    headers = {
        "X-Admin-Access": ADMIN_TOKEN,
        "Content-Type": "application/json"
    }
    
    print(f"Endpoint: GET {url}")
    print(f"Headers: {headers}\n")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}\n")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS - Retrieved user details\n")
            
            print("User Details:")
            for key, value in data.items():
                print(f"  {key}: {value}")
            
            return True
        else:
            print(f"❌ FAILED - {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def test_get_nonexistent_user():
    """Test GET /api/users/<user_id>/ with non-existent user ID"""
    print_section("TEST 3: Get Non-Existent User (Error Handling)")
    
    user_id = 99999  # Non-existent ID
    url = f"{BASE_URL}/users/{user_id}/"
    headers = {
        "X-Admin-Access": ADMIN_TOKEN,
        "Content-Type": "application/json"
    }
    
    print(f"Endpoint: GET {url}")
    print(f"Headers: {headers}\n")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}\n")
        
        if response.status_code == 404:
            print(f"✅ SUCCESS - Properly returns 404 for non-existent user")
            return True
        else:
            print(f"⚠️  Expected 404, got {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def test_unauthorized_access():
    """Test endpoints without admin token"""
    print_section("TEST 4: Unauthorized Access (No Admin Token)")
    
    url = f"{BASE_URL}/users/"
    
    print(f"Endpoint: GET {url}")
    print("Headers: (no admin token)\n")
    
    try:
        response = requests.get(url, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}\n")
        
        if response.status_code == 403:
            print(f"✅ SUCCESS - Properly blocks unauthorized access")
            return True
        else:
            print(f"⚠️  Expected 403, got {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("  USER MANAGEMENT API ENDPOINT TESTS")
    print("  Testing: /api/users/ and /api/users/<user_id>/")
    print("=" * 80)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Base URL: {BASE_URL}")
    print(f"Admin Token: {ADMIN_TOKEN}")
    
    # Check if Django server is running
    try:
        response = requests.get(f"{BASE_URL}/health/", timeout=5)
        if response.status_code != 200:
            print("\n❌ Django server is not responding. Please start the server with:")
            print("   python manage.py runserver")
            return
    except requests.exceptions.RequestException:
        print("\n❌ Cannot connect to Django server. Please start the server with:")
        print("   python manage.py runserver")
        return
    
    # Run all tests
    results = []
    
    results.append(("List Users", test_list_users()))
    results.append(("Get User Detail", test_get_user_detail()))
    results.append(("Get Non-Existent User", test_get_nonexistent_user()))
    results.append(("Unauthorized Access", test_unauthorized_access()))
    
    # Print summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print(f"Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if passed == total:
        print("\n🎉 All tests passed successfully!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the results above.")

if __name__ == "__main__":
    main()
