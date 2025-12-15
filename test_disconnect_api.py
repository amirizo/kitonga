#!/usr/bin/env python
"""
Test script for the new disconnect user APIs

Usage:
    python test_disconnect_api.py

Make sure the Django server is running first:
    python manage.py runserver
"""

import requests
import json
import sys

# Configuration - update these values
BASE_URL = "http://localhost:8000/api"  # Change to your API URL
ADMIN_TOKEN = "kitonga_admin_2025"  # Your SIMPLE_ADMIN_TOKEN from settings

# Headers for admin authentication
headers = {
    "Content-Type": "application/json",
    "X-Admin-Access": ADMIN_TOKEN
}


def print_response(name, response):
    """Pretty print API response"""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    print(f"Status Code: {response.status_code}")
    try:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
    except:
        print(f"Response Text: {response.text[:500]}")
    print()


def test_health_check():
    """Test health check endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/health/", timeout=5)
        print_response("Health Check", response)
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to the API server.")
        print("   Make sure the Django server is running:")
        print("   python manage.py runserver")
        return False


def test_list_users():
    """List all users to find expired ones"""
    response = requests.get(f"{BASE_URL}/admin/users/", headers=headers)
    print_response("List Users", response)
    
    if response.status_code == 200:
        data = response.json()
        users = data.get('users', [])
        
        print("\n📊 User Summary:")
        print("-" * 40)
        
        expired_users = []
        active_users = []
        
        for user in users:
            status = "🟢" if user.get('has_active_access') else "🔴"
            print(f"{status} ID: {user['id']} | Phone: {user['phone_number']} | Access: {user.get('access_status', 'Unknown')}")
            
            if not user.get('has_active_access'):
                expired_users.append(user)
            else:
                active_users.append(user)
        
        print(f"\n✅ Active users: {len(active_users)}")
        print(f"❌ Expired/No access users: {len(expired_users)}")
        
        return expired_users
    return []


def test_disconnect_user(user_id):
    """Test disconnecting a specific user"""
    print(f"\n🔌 Disconnecting user ID: {user_id}")
    
    response = requests.post(
        f"{BASE_URL}/admin/users/{user_id}/disconnect/",
        headers=headers
    )
    print_response(f"Disconnect User {user_id}", response)
    
    return response.status_code == 200


def test_cleanup_expired_users():
    """Test the bulk cleanup of expired users"""
    print("\n🧹 Running bulk cleanup of expired users...")
    
    response = requests.post(
        f"{BASE_URL}/admin/cleanup-expired/",
        headers=headers
    )
    print_response("Cleanup Expired Users", response)
    
    return response.status_code == 200


def test_system_status():
    """Get system status"""
    response = requests.get(f"{BASE_URL}/admin/status/", headers=headers)
    print_response("System Status", response)
    return response.status_code == 200


def main():
    print("=" * 60)
    print("🧪 KITONGA API - DISCONNECT USER TESTS")
    print("=" * 60)
    
    # Test 1: Health check
    print("\n📡 Testing API connectivity...")
    if not test_health_check():
        sys.exit(1)
    
    # Test 2: System status
    print("\n📊 Getting system status...")
    test_system_status()
    
    # Test 3: List users and find expired ones
    print("\n👥 Listing all users...")
    expired_users = test_list_users()
    
    # Test 4: Cleanup all expired users
    print("\n🧹 Testing bulk cleanup endpoint...")
    test_cleanup_expired_users()
    
    # Test 5: Disconnect a specific expired user (if any found)
    if expired_users:
        print(f"\n🔌 Testing individual disconnect on first expired user...")
        first_expired = expired_users[0]
        test_disconnect_user(first_expired['id'])
    else:
        print("\n✅ No expired users found to disconnect individually.")
    
    # Final status check
    print("\n📊 Final system status...")
    test_system_status()
    
    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
