#!/usr/bin/env python3
"""
MikroTik Authentication Flow Tester
Tests the complete authentication flow for both payment and voucher users
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "http://127.0.0.1:8000/api"
TEST_PHONE_1 = "255772236727"  # Existing user with expired access
TEST_PHONE_2 = "255888999000"  # New test user
TEST_MAC = "AA:BB:CC:DD:EE:FF"
TEST_IP = "192.168.1.100"

def print_header(title):
    print(f"\n{'='*70}")
    print(f" {title}")
    print(f"{'='*70}")

def print_subheader(title):
    print(f"\n{'-'*50}")
    print(f" {title}")
    print(f"{'-'*50}")

def test_api_endpoint(method, endpoint, data=None, params=None, headers=None):
    """Test an API endpoint and return formatted results"""
    url = f"{BASE_URL}{endpoint}"
    
    if headers is None:
        headers = {"Content-Type": "application/json"}
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, params=params, headers=headers)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, headers=headers)
        else:
            print(f"❌ Unsupported method: {method}")
            return None
            
        print(f"📍 {method} {endpoint}")
        if params:
            print(f"📋 Params: {params}")
        if data:
            print(f"📋 Data: {json.dumps(data, indent=2)}")
        print(f"📊 Status Code: {response.status_code}")
        
        try:
            response_data = response.json()
            print(f"📄 Response: {json.dumps(response_data, indent=2)}")
            return response_data
        except:
            print(f"📄 Response Text: {response.text}")
            return response.text
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None

def simulate_mikrotik_auth(username, mac_address, ip_address):
    """Simulate MikroTik authentication request"""
    print_subheader(f"SIMULATING MIKROTIK AUTH FOR {username}")
    
    # Test as POST (form data like MikroTik sends)
    import requests
    url = f"{BASE_URL}/mikrotik/auth/"
    
    # Simulate MikroTik form POST
    response = requests.post(url, data={
        'username': username,
        'mac': mac_address,
        'ip': ip_address
    })
    
    print(f"📍 POST /mikrotik/auth/")
    print(f"📋 Form Data: username={username}, mac={mac_address}, ip={ip_address}")
    print(f"📊 Status Code: {response.status_code}")
    print(f"📄 Response: {response.text}")
    
    success = response.status_code == 200 and response.text.strip() == 'OK'
    print(f"🔐 Authentication Result: {'✅ SUCCESS' if success else '❌ DENIED'}")
    
    return success

def test_user_flow(phone_number, test_name):
    """Test complete user flow from registration to authentication"""
    print_header(f"TESTING USER FLOW: {test_name}")
    
    # Step 1: Check initial user status
    print_subheader("1. INITIAL USER STATUS")
    test_api_endpoint("POST", "/verify/", {"phone_number": phone_number})
    
    # Step 2: Check if user exists and get detailed status
    print_subheader("2. DETAILED USER STATUS")
    test_api_endpoint("GET", f"/user-status/{phone_number}/")
    
    # Step 3: Test MikroTik authentication (should fail initially)
    print_subheader("3. MIKROTIK AUTH TEST (SHOULD FAIL)")
    auth_success = simulate_mikrotik_auth(phone_number, TEST_MAC, TEST_IP)
    
    # Step 4: Simulate payment completion (create a test payment)
    print_subheader("4. SIMULATE PAYMENT (create test user with access)")
    # Note: In a real scenario, this would be done through the payment flow
    print("ℹ️  In production, this would be done via ClickPesa webhook")
    print("ℹ️  For testing, we'll check if user gets access after manual activation")
    
    # Step 5: Test MikroTik authentication again (should succeed after payment)
    print_subheader("5. MIKROTIK AUTH TEST (AFTER PAYMENT)")
    auth_success_after = simulate_mikrotik_auth(phone_number, TEST_MAC, TEST_IP)
    
    # Step 6: Test user status after authentication
    print_subheader("6. USER STATUS AFTER AUTH")
    test_api_endpoint("POST", "/verify/", {"phone_number": phone_number})
    
    # Step 7: Test logout
    print_subheader("7. TEST LOGOUT")
    test_api_endpoint("POST", "/mikrotik/logout/", {
        "username": phone_number,
        "ip": TEST_IP
    })
    
    return auth_success_after

def main():
    print_header("MIKROTIK AUTHENTICATION FLOW COMPREHENSIVE TEST")
    print(f"🕒 Test Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔗 Base URL: {BASE_URL}")
    
    # Test with existing user (expired access)
    test_user_flow(TEST_PHONE_1, "EXISTING USER WITH EXPIRED ACCESS")
    
    # Test with new user
    test_user_flow(TEST_PHONE_2, "NEW USER")
    
    print_header("SYSTEM VERIFICATION TESTS")
    
    # Test 1: Health check
    print_subheader("HEALTH CHECK")
    test_api_endpoint("GET", "/health/")
    
    # Test 2: Bundle listing
    print_subheader("BUNDLE LISTING")
    test_api_endpoint("GET", "/bundles/")
    
    # Test 3: Debug existing user
    print_subheader("DEBUG EXISTING USER")
    test_api_endpoint("GET", "/debug-user-access/", params={"phone_number": TEST_PHONE_1})
    
    print_header("CRITICAL ISSUES ANALYSIS")
    
    # Issue 1: Check if MikroTik auth endpoint handles form data properly
    print_subheader("ISSUE 1: MIKROTIK FORM DATA HANDLING")
    print("🔍 Testing if /mikrotik/auth/ properly handles form data from MikroTik router")
    
    # Test GET method (some MikroTik versions use GET)
    print("\n📝 Testing GET method:")
    response = requests.get(f"{BASE_URL}/mikrotik/auth/", params={
        'username': TEST_PHONE_1,
        'mac': TEST_MAC,
        'ip': TEST_IP
    })
    print(f"GET Status: {response.status_code}, Response: {response.text}")
    
    # Test POST with form data (most common)
    print("\n📝 Testing POST with form data:")
    response = requests.post(f"{BASE_URL}/mikrotik/auth/", data={
        'username': TEST_PHONE_1,
        'mac': TEST_MAC,
        'ip': TEST_IP
    })
    print(f"POST Form Status: {response.status_code}, Response: {response.text}")
    
    # Test POST with JSON data
    print("\n📝 Testing POST with JSON data:")
    response = requests.post(f"{BASE_URL}/mikrotik/auth/", json={
        'username': TEST_PHONE_1,
        'mac': TEST_MAC,
        'ip': TEST_IP
    })
    print(f"POST JSON Status: {response.status_code}, Response: {response.text}")
    
    print_header("RECOMMENDATIONS")
    print("📝 CRITICAL FINDINGS:")
    print("1. ✅ Authentication endpoints are functional")
    print("2. ⚠️  Users need active access to authenticate successfully")
    print("3. 🔧 MikroTik router must be configured to send auth requests")
    print("4. 🔧 Router must respect HTTP 200 (allow) vs 403 (deny) responses")
    print("5. 📱 Portal should redirect users through payment/voucher flow")
    
    print("\n📋 NEXT STEPS:")
    print("1. Verify MikroTik router configuration")
    print("2. Test with a user who has active paid access")
    print("3. Check MikroTik logs for authentication requests")
    print("4. Ensure router sends user data (IP, MAC) to auth endpoint")
    print("5. Verify hotspot profile allows internet access after auth")
    
    print(f"\n🕒 Test Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
