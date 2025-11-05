#!/usr/bin/env python3
"""
Test script to verify the verify_access API works for both payment and voucher users
Run this after making the fixes to ensure everything works correctly
"""

import requests
import json

# API base URL
BASE_URL = "http://127.0.0.1:8000/api"

def test_verify_access():
    """Test the verify_access endpoint for different user types"""
    print("🧪 TESTING VERIFY ACCESS API FIXES")
    print("=" * 50)
    
    # Test cases
    test_cases = [
        {
            "name": "Payment User (Active)",
            "phone_number": "255123456789",
            "mac_address": "00:11:22:33:44:55",
            "ip_address": "192.168.1.100",
            "expected_access": True
        },
        {
            "name": "Voucher User (Active)", 
            "phone_number": "255987654321",
            "mac_address": "00:11:22:33:44:66",
            "ip_address": "192.168.1.101",
            "expected_access": True
        },
        {
            "name": "Non-existent User",
            "phone_number": "255999888777",
            "mac_address": "00:11:22:33:44:77",
            "ip_address": "192.168.1.102",
            "expected_access": False
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. Testing {test_case['name']}")
        print("-" * 30)
        
        # Prepare request payload
        payload = {
            "phone_number": test_case["phone_number"],
            "ip_address": test_case["ip_address"],
            "mac_address": test_case["mac_address"]
        }
        
        try:
            # Make request to verify_access endpoint
            response = requests.post(f"{BASE_URL}/verify/", json=payload, timeout=10)
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code in [200, 404]:
                data = response.json()
                print(f"Response: {json.dumps(data, indent=2)}")
                
                # Check if response matches expected result
                if response.status_code == 200:
                    access_granted = data.get('access_granted', False)
                    access_method = data.get('access_method', 'unknown')
                    denial_reason = data.get('denial_reason', '')
                    
                    if access_granted == test_case['expected_access']:
                        print(f"✅ PASS: Access granted = {access_granted} (expected: {test_case['expected_access']})")
                        if access_granted:
                            print(f"   Access Method: {access_method}")
                        else:
                            print(f"   Denial Reason: {denial_reason}")
                    else:
                        print(f"❌ FAIL: Access granted = {access_granted} (expected: {test_case['expected_access']})")
                elif response.status_code == 404:
                    if not test_case['expected_access']:
                        print("✅ PASS: User not found (as expected)")
                    else:
                        print("❌ FAIL: User should exist but was not found")
            else:
                print(f"❌ FAIL: Unexpected status code {response.status_code}")
                print(f"Response: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ ERROR: Request failed - {str(e)}")
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")

def test_mikrotik_auth():
    """Test the MikroTik authentication endpoint"""
    print(f"\n🔐 TESTING MIKROTIK AUTH API")
    print("=" * 30)
    
    # Test cases for MikroTik auth
    auth_tests = [
        {
            "name": "Payment User Auth",
            "username": "255123456789",
            "mac": "00:11:22:33:44:55",
            "ip": "192.168.1.100",
            "expected_status": 200
        },
        {
            "name": "Voucher User Auth",
            "username": "255987654321", 
            "mac": "00:11:22:33:44:66",
            "ip": "192.168.1.101",
            "expected_status": 200
        },
        {
            "name": "Non-existent User Auth",
            "username": "255999888777",
            "mac": "00:11:22:33:44:77", 
            "ip": "192.168.1.102",
            "expected_status": 403
        }
    ]
    
    for i, test in enumerate(auth_tests, 1):
        print(f"\n{i}. {test['name']}")
        print("-" * 20)
        
        # Prepare form data (MikroTik typically sends form data)
        form_data = {
            'username': test['username'],
            'password': '',
            'mac': test['mac'],
            'ip': test['ip']
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/mikrotik/auth/",
                data=form_data,
                timeout=10
            )
            
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text[:100]}...")
            
            if response.status_code == test['expected_status']:
                print(f"✅ PASS: Got expected status {test['expected_status']}")
            else:
                print(f"❌ FAIL: Expected {test['expected_status']}, got {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ ERROR: Request failed - {str(e)}")

def main():
    print("🚀 TESTING KITONGA VERIFY ACCESS FIXES")
    print("=" * 60)
    print("This script tests the verify_access API to ensure it works")
    print("correctly for both payment and voucher users.")
    print("")
    
    try:
        # Test verify access endpoint
        test_verify_access()
        
        # Test MikroTik auth endpoint
        test_mikrotik_auth()
        
        print(f"\n✅ TESTING COMPLETED")
        print("Check the results above to verify all tests passed.")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
