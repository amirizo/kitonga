#!/usr/bin/env python3
"""
Test script to verify the payment flow and MikroTik integration
"""

import requests
import json
import sys

BASE_URL = "https://kitonga.klikcell.com"
# For local testing: BASE_URL = "http://localhost:8000"

def test_payment_flow():
    """Test the complete payment flow with device registration"""
    
    # Test data
    phone_number = "255123456789"  # Test phone number
    mac_address = "AA:BB:CC:DD:EE:FF"  # Test MAC address
    ip_address = "192.168.1.100"  # Test IP address
    
    print("🧪 Testing Kitonga Payment Flow with MikroTik Integration")
    print("=" * 60)
    
    # Step 1: Check if user exists
    print(f"1. Checking user status for {phone_number}...")
    response = requests.get(f"{BASE_URL}/user-status/{phone_number}/")
    if response.status_code == 200:
        user_data = response.json()
        print(f"   ✅ User exists: {user_data.get('is_active', False)}")
        print(f"   📅 Access until: {user_data.get('paid_until', 'None')}")
    else:
        print(f"   ❌ User not found (this is expected for new users)")
    
    # Step 2: Initiate payment with device info
    print(f"\n2. Initiating payment with device registration...")
    payment_data = {
        "phone_number": phone_number,
        "bundle_id": 1,  # Assuming bundle ID 1 exists
        "mac_address": mac_address,
        "ip_address": ip_address
    }
    
    try:
        response = requests.post(f"{BASE_URL}/initiate-payment/", json=payment_data)
        if response.status_code == 200:
            payment_result = response.json()
            print(f"   ✅ Payment initiated: {payment_result.get('order_reference')}")
            order_reference = payment_result.get('order_reference')
        else:
            print(f"   ❌ Payment initiation failed: {response.text}")
            return
    except Exception as e:
        print(f"   ❌ Error initiating payment: {e}")
        return
    
    # Step 3: Simulate successful payment webhook (for testing)
    print(f"\n3. Testing manual device authentication...")
    auth_data = {
        "phone_number": phone_number,
        "mac_address": mac_address,
        "ip_address": ip_address
    }
    
    try:
        response = requests.post(f"{BASE_URL}/trigger-auth/", json=auth_data)
        if response.status_code == 200:
            auth_result = response.json()
            print(f"   ✅ Authentication trigger: {auth_result.get('success')}")
            print(f"   📡 MikroTik result: {auth_result.get('mikrotik_result', {}).get('success')}")
            print(f"   📋 Instructions: {len(auth_result.get('instructions', []))} steps provided")
        else:
            auth_result = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
            print(f"   ❌ Authentication failed: {auth_result.get('message', response.text)}")
    except Exception as e:
        print(f"   ❌ Error triggering authentication: {e}")
    
    # Step 4: Test MikroTik auth endpoint
    print(f"\n4. Testing MikroTik authentication endpoint...")
    mikrotik_data = {
        "username": phone_number,
        "mac": mac_address,
        "ip": ip_address
    }
    
    try:
        response = requests.post(f"{BASE_URL}/mikrotik-auth/", data=mikrotik_data)
        if response.status_code == 200:
            print(f"   ✅ MikroTik auth successful")
        elif response.status_code == 403:
            print(f"   ❌ MikroTik auth denied: {response.text}")
        else:
            print(f"   ⚠️  MikroTik auth unexpected response: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error testing MikroTik auth: {e}")
    
    print(f"\n" + "=" * 60)
    print("🏁 Test completed!")
    print("\n📋 Next steps for real usage:")
    print("1. User connects to WiFi and visits login page")
    print("2. Login page redirects to portal with device info")
    print("3. User makes payment on portal")
    print("4. Payment webhook triggers MikroTik authentication")
    print("5. User gets automatic internet access")
    print("\n💡 If users still can't access internet after payment:")
    print("- They should disconnect and reconnect to WiFi")
    print("- Or call the /trigger-auth/ endpoint manually")

if __name__ == "__main__":
    test_payment_flow()
