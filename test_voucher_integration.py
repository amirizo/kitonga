#!/usr/bin/env python3
"""
Voucher Integration Test Script
Tests the complete voucher redemption flow including device access and MikroTik integration
"""

import requests
import json
import time
from datetime import datetime

class VoucherIntegrationTester:
    def __init__(self, base_url="http://127.0.0.1:8000"):
        self.base_url = base_url
        self.admin_token = "kitonga_admin_2025"  # Update this with your admin token
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
        
    def test_request(self, method, endpoint, data=None, headers=None, description=""):
        """Make a test request and return status and response"""
        url = f"{self.base_url}/api/{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, params=data, headers=headers)
            elif method == "POST":
                response = requests.post(url, json=data, headers=headers)
            elif method == "PUT":
                response = requests.put(url, json=data, headers=headers)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers)
            else:
                return None, {"error": f"Unsupported method: {method}"}
            
            try:
                response_data = response.json()
            except:
                response_data = {"raw_response": response.text}
                
            self.log(f"{description}: {method} {endpoint} -> {response.status_code}")
            
            return response.status_code, response_data
            
        except Exception as e:
            self.log(f"Request failed: {str(e)}", "ERROR")
            return None, {"error": str(e)}
    
    def generate_test_voucher(self):
        """Generate a test voucher for testing"""
        self.log("=" * 60)
        self.log("STEP 1: GENERATING TEST VOUCHER")
        self.log("=" * 60)
        
        headers = {
            "Authorization": f"Token {self.admin_token}",
            "X-Admin-Access": "kitonga_admin_2025"
        }
        
        data = {
            "quantity": 1,
            "duration_hours": 24,
            "batch_id": "TEST-INTEGRATION",
            "notes": "Integration test voucher",
            "admin_phone_number": "255123456789",
            "language": "en"
        }
        
        status, response = self.test_request(
            "POST", "vouchers/generate/", 
            data=data, headers=headers,
            description="Generate test voucher"
        )
        
        if status == 201 and response.get('success'):
            voucher_code = response['vouchers'][0]['code']
            self.log(f"✅ Successfully generated voucher: {voucher_code}", "SUCCESS")
            return voucher_code
        else:
            self.log(f"❌ Failed to generate voucher: {response.get('message', 'Unknown error')}", "ERROR")
            return None
    
    def test_voucher_redemption(self, voucher_code, phone_number):
        """Test voucher redemption with device information"""
        self.log("=" * 60)
        self.log("STEP 2: TESTING VOUCHER REDEMPTION")
        self.log("=" * 60)
        
        data = {
            "voucher_code": voucher_code,
            "phone_number": phone_number,
            "ip_address": "192.168.1.100",
            "mac_address": "AA:BB:CC:DD:EE:FF"
        }
        
        status, response = self.test_request(
            "POST", "vouchers/redeem/",
            data=data,
            description="Redeem voucher with device info"
        )
        
        if status == 200 and response.get('success'):
            self.log("✅ Voucher redemption successful", "SUCCESS")
            self.log(f"   User Access: {response['access_info']['has_active_access']}")
            self.log(f"   Paid Until: {response['access_info']['paid_until']}")
            self.log(f"   Device Registered: {response['device_info'].get('device_registered', False)}")
            self.log(f"   MikroTik Auth: {response['mikrotik_integration'].get('mikrotik_auth_success', 'N/A')}")
            return True
        else:
            self.log(f"❌ Voucher redemption failed: {response.get('message', 'Unknown error')}", "ERROR")
            return False
    
    def test_access_verification(self, phone_number):
        """Test access verification endpoint"""
        self.log("=" * 60)
        self.log("STEP 3: TESTING ACCESS VERIFICATION")
        self.log("=" * 60)
        
        data = {
            "phone_number": phone_number,
            "ip_address": "192.168.1.100",
            "mac_address": "AA:BB:CC:DD:EE:FF"
        }
        
        status, response = self.test_request(
            "POST", "verify/",
            data=data,
            description="Verify access"
        )
        
        if status == 200:
            access_granted = response.get('access_granted', False)
            access_method = response.get('access_method', 'unknown')
            
            if access_granted:
                self.log("✅ Access verification successful", "SUCCESS")
                self.log(f"   Access Method: {access_method}")
                self.log(f"   Device Count: {response['debug_info']['device_count']}")
                return True
            else:
                self.log(f"❌ Access denied: {response.get('denial_reason', 'Unknown')}", "ERROR")
                return False
        else:
            self.log(f"❌ Access verification failed: {response.get('message', 'Unknown error')}", "ERROR")
            return False
    
    def test_mikrotik_authentication(self, phone_number):
        """Test MikroTik authentication endpoint"""
        self.log("=" * 60)
        self.log("STEP 4: TESTING MIKROTIK AUTHENTICATION")
        self.log("=" * 60)
        
        # Test with form data (as MikroTik would send)
        url = f"{self.base_url}/api/mikrotik/auth/"
        data = {
            "username": phone_number,
            "password": "",
            "mac": "AA:BB:CC:DD:EE:FF",
            "ip": "192.168.1.100"
        }
        
        try:
            response = requests.post(url, data=data)  # Form data, not JSON
            self.log(f"MikroTik Auth: POST /api/mikrotik/auth/ -> {response.status_code}")
            
            if response.status_code == 200:
                self.log("✅ MikroTik authentication successful", "SUCCESS")
                self.log(f"   Response: {response.text[:100]}...")
                return True
            else:
                self.log(f"❌ MikroTik authentication failed: {response.status_code}", "ERROR")
                self.log(f"   Response: {response.text[:100]}...")
                return False
                
        except Exception as e:
            self.log(f"❌ MikroTik authentication error: {str(e)}", "ERROR")
            return False
    
    def test_user_status(self, phone_number):
        """Test user status endpoint"""
        self.log("=" * 60)
        self.log("STEP 5: TESTING USER STATUS")
        self.log("=" * 60)
        
        status, response = self.test_request(
            "GET", f"user-status/{phone_number}/",
            description="Get user status"
        )
        
        if status == 200:
            self.log("✅ User status retrieved successfully", "SUCCESS")
            self.log(f"   Phone: {response.get('phone_number')}")
            self.log(f"   Active: {response.get('is_active')}")
            self.log(f"   Access: {response.get('has_active_access')}")
            return True
        else:
            self.log(f"❌ User status failed: {response.get('message', 'Unknown error')}", "ERROR")
            return False
    
    def test_voucher_specific_debug(self, phone_number):
        """Test the voucher-specific debug endpoint"""
        self.log("=" * 60)
        self.log("STEP 6: TESTING VOUCHER DEBUG ENDPOINT")
        self.log("=" * 60)
        
        data = {
            "phone_number": phone_number,
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "ip_address": "192.168.1.100"
        }
        
        status, response = self.test_request(
            "POST", "vouchers/test-access/",
            data=data,
            description="Test voucher access debug"
        )
        
        if status == 200 and response.get('success'):
            voucher_info = response['voucher_access_test']
            self.log("✅ Voucher debug test successful", "SUCCESS")
            self.log(f"   Total Vouchers: {voucher_info['voucher_info']['total_vouchers_redeemed']}")
            self.log(f"   Has Access: {voucher_info['access_status']['has_active_access']}")
            self.log(f"   Time Remaining: {voucher_info['access_status']['time_remaining_hours']} hours")
            return True
        else:
            self.log(f"❌ Voucher debug test failed: {response.get('message', 'Unknown error')}", "ERROR")
            return False
    
    def run_complete_test(self):
        """Run the complete integration test"""
        self.log("🧪 STARTING VOUCHER INTEGRATION TEST")
        self.log("=" * 80)
        
        test_phone = "255999888777"  # Test phone number
        results = []
        
        # Step 1: Generate test voucher
        voucher_code = self.generate_test_voucher()
        if not voucher_code:
            self.log("❌ Cannot continue without voucher", "ERROR")
            return False
        
        results.append(("Generate Voucher", True))
        
        # Step 2: Redeem voucher
        redemption_success = self.test_voucher_redemption(voucher_code, test_phone)
        results.append(("Redeem Voucher", redemption_success))
        
        if redemption_success:
            # Step 3: Test access verification
            access_success = self.test_access_verification(test_phone)
            results.append(("Access Verification", access_success))
            
            # Step 4: Test MikroTik authentication
            mikrotik_success = self.test_mikrotik_authentication(test_phone)
            results.append(("MikroTik Auth", mikrotik_success))
            
            # Step 5: Test user status
            status_success = self.test_user_status(test_phone)
            results.append(("User Status", status_success))
            
            # Step 6: Test voucher debug
            debug_success = self.test_voucher_specific_debug(test_phone)
            results.append(("Voucher Debug", debug_success))
        
        # Print summary
        self.log("=" * 80)
        self.log("🎯 TEST RESULTS SUMMARY")
        self.log("=" * 80)
        
        total_tests = len(results)
        passed_tests = sum(1 for _, success in results if success)
        
        for test_name, success in results:
            status = "✅ PASS" if success else "❌ FAIL"
            self.log(f"{test_name:25} : {status}")
        
        self.log("=" * 80)
        self.log(f"OVERALL RESULT: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            self.log("🎉 ALL TESTS PASSED! Voucher integration is working correctly.", "SUCCESS")
            return True
        else:
            self.log("⚠️  Some tests failed. Check the logs above for details.", "WARNING")
            return False

if __name__ == "__main__":
    print("🧪 Voucher Integration Test Script")
    print("=" * 50)
    print("This script tests the complete voucher redemption flow:")
    print("1. Generate a test voucher")
    print("2. Redeem the voucher")
    print("3. Test access verification")
    print("4. Test MikroTik authentication")
    print("5. Test user status")
    print("6. Test voucher debug endpoint")
    print("")
    
    base_url = input("Enter API base URL (default: http://127.0.0.1:8000): ").strip()
    if not base_url:
        base_url = "http://127.0.0.1:8000"
    
    tester = VoucherIntegrationTester(base_url)
    success = tester.run_complete_test()
    
    if success:
        print("\n✅ Integration test completed successfully!")
        exit(0)
    else:
        print("\n❌ Integration test failed!")
        exit(1)
