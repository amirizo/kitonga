#!/usr/bin/env python3
"""
Kitonga WiFi Billing System - Python Test Script
This script tests the complete user workflow with better error handling
"""

import requests
import json
import time
import sys
from datetime import datetime

class KitongaAPITester:
    def __init__(self, base_url="http://127.0.0.1:8000/api", admin_token=None):
        self.base_url = base_url.rstrip('/')
        self.admin_token = admin_token
        self.test_phone = "255712345999"
        self.test_mac = "AA:BB:CC:DD:EE:FF"
        self.session = requests.Session()
        
    def log(self, message, status="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {status}: {message}")
        
    def pretty_print(self, data):
        print(json.dumps(data, indent=2))
        
    def make_request(self, method, endpoint, data=None, headers=None):
        """Make API request with error handling"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, headers=headers)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
                
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            self.log(f"Request failed: {e}", "ERROR")
            return None
        except json.JSONDecodeError:
            self.log(f"Invalid JSON response", "ERROR")
            return None
            
    def test_system_health(self):
        """Test 1: System Health Check"""
        self.log("Testing system health...")
        result = self.make_request('GET', '/health/')
        if result:
            self.pretty_print(result)
            return result.get('status') == 'healthy'
        return False
        
    def test_bundles(self):
        """Test 2: Get Available Bundles"""
        self.log("Getting available bundles...")
        result = self.make_request('GET', '/bundles/')
        if result:
            self.pretty_print(result)
            return len(result.get('bundles', [])) > 0
        return False
        
    def test_access_verification(self, phone=None, mac=None):
        """Test 3: Access Verification"""
        phone = phone or self.test_phone
        mac = mac or self.test_mac
        
        self.log(f"Testing access verification for {phone}...")
        data = {
            "phone_number": phone,
            "mac_address": mac
        }
        
        result = self.make_request('POST', '/verify/', data)
        if result:
            self.pretty_print(result)
            return True
        return False
        
    def test_payment_initiation(self):
        """Test 4: Initiate Payment"""
        self.log("Initiating payment...")
        data = {
            "phone_number": self.test_phone,
            "bundle_id": 1,
            "amount": 1000
        }
        
        result = self.make_request('POST', '/initiate-payment/', data)
        if result:
            self.pretty_print(result)
            order_ref = result.get('payment_details', {}).get('order_reference')
            return order_ref
        return None
        
    def test_payment_status(self, order_ref):
        """Test 5: Check Payment Status"""
        self.log(f"Checking payment status for {order_ref}...")
        result = self.make_request('GET', f'/payment-status/{order_ref}/')
        if result:
            self.pretty_print(result)
            return result.get('payment_status')
        return None
        
    def test_payment_webhook(self, order_ref):
        """Test 6: Simulate Payment Webhook"""
        self.log("Simulating payment webhook...")
        data = {
            "order_reference": order_ref,
            "transaction_reference": "CLPLCPCA6KYH4",
            "amount": 1000,
            "status": "PAYMENT RECEIVED",
            "phone_number": self.test_phone,
            "channel": "TIGO-PESA"
        }
        
        result = self.make_request('POST', '/clickpesa-webhook/', data)
        if result:
            self.pretty_print(result)
            return result.get('success', False)
        return False
        
    def test_user_status(self):
        """Test 7: Check User Status"""
        self.log(f"Checking user status for {self.test_phone}...")
        result = self.make_request('GET', f'/user-status/{self.test_phone}/')
        if result:
            self.pretty_print(result)
            return result.get('success', False)
        return False
        
    def test_device_management(self):
        """Test 8: Device Management"""
        self.log(f"Checking devices for {self.test_phone}...")
        result = self.make_request('GET', f'/devices/{self.test_phone}/')
        if result:
            self.pretty_print(result)
            return result.get('success', False)
        return False
        
    def test_device_limit(self):
        """Test 9: Device Limit (Second Device)"""
        self.log("Testing device limit with second device...")
        return self.test_access_verification(
            phone=self.test_phone,
            mac="BB:CC:DD:EE:FF:AA"
        )
        
    def test_invalid_payment(self):
        """Test 10: Invalid Payment Amount"""
        self.log("Testing invalid payment amount...")
        data = {
            "phone_number": self.test_phone,
            "bundle_id": 1,
            "amount": 500  # Wrong amount
        }
        
        result = self.make_request('POST', '/initiate-payment/', data)
        if result:
            self.pretty_print(result)
            return not result.get('success', True)  # Should fail
        return False
        
    def test_admin_dashboard(self):
        """Test 11: Admin Dashboard Stats"""
        if not self.admin_token:
            self.log("Skipping admin tests - no token provided", "WARN")
            return False
            
        self.log("Testing admin dashboard...")
        headers = {
            "Authorization": f"Token {self.admin_token}"
        }
        
        result = self.make_request('GET', '/dashboard-stats/', headers=headers)
        if result:
            self.pretty_print(result)
            return result.get('success', False)
        return False
        
    def test_admin_users(self):
        """Test 12: Admin User List"""
        if not self.admin_token:
            return False
            
        self.log("Testing admin user list...")
        headers = {
            "Authorization": f"Token {self.admin_token}",
            "X-Admin-Access": "kitonga_admin_2025"
        }
        
        result = self.make_request('GET', '/admin/users/', headers=headers)
        if result:
            self.pretty_print(result)
            return result.get('success', False)
        return False
        
    def run_complete_test(self):
        """Run all tests in sequence"""
        print("=" * 60)
        print("KITONGA WIFI BILLING SYSTEM - PYTHON TEST SUITE")
        print("=" * 60)
        print()
        
        tests_passed = 0
        total_tests = 0
        
        # Test sequence
        test_results = []
        
        # 1. System Health
        total_tests += 1
        if self.test_system_health():
            tests_passed += 1
            test_results.append("✅ System Health")
        else:
            test_results.append("❌ System Health")
        print()
        
        # 2. Bundles
        total_tests += 1
        if self.test_bundles():
            tests_passed += 1
            test_results.append("✅ Bundles")
        else:
            test_results.append("❌ Bundles")
        print()
        
        # 3. Access Verification (New User)
        total_tests += 1
        if self.test_access_verification():
            tests_passed += 1
            test_results.append("✅ Access Verification")
        else:
            test_results.append("❌ Access Verification")
        print()
        
        # 4. Payment Initiation
        total_tests += 1
        order_ref = self.test_payment_initiation()
        if order_ref:
            tests_passed += 1
            test_results.append("✅ Payment Initiation")
        else:
            test_results.append("❌ Payment Initiation")
        print()
        
        # Continue with payment flow if we have order ref
        if order_ref:
            # 5. Payment Status
            total_tests += 1
            if self.test_payment_status(order_ref):
                tests_passed += 1
                test_results.append("✅ Payment Status")
            else:
                test_results.append("❌ Payment Status")
            print()
            
            # 6. Payment Webhook
            total_tests += 1
            if self.test_payment_webhook(order_ref):
                tests_passed += 1
                test_results.append("✅ Payment Webhook")
            else:
                test_results.append("❌ Payment Webhook")
            print()
            
            # Wait a moment for webhook processing
            time.sleep(1)
            
            # 7. Access Verification After Payment
            total_tests += 1
            self.log("Re-checking access after payment...")
            if self.test_access_verification():
                tests_passed += 1
                test_results.append("✅ Access After Payment")
            else:
                test_results.append("❌ Access After Payment")
            print()
        
        # 8. User Status
        total_tests += 1
        if self.test_user_status():
            tests_passed += 1
            test_results.append("✅ User Status")
        else:
            test_results.append("❌ User Status")
        print()
        
        # 9. Device Management
        total_tests += 1
        if self.test_device_management():
            tests_passed += 1
            test_results.append("✅ Device Management")
        else:
            test_results.append("❌ Device Management")
        print()
        
        # 10. Device Limit Test
        total_tests += 1
        if self.test_device_limit():
            tests_passed += 1
            test_results.append("✅ Device Limit Test")
        else:
            test_results.append("❌ Device Limit Test")
        print()
        
        # 11. Invalid Payment Test
        total_tests += 1
        if self.test_invalid_payment():
            tests_passed += 1
            test_results.append("✅ Invalid Payment Test")
        else:
            test_results.append("❌ Invalid Payment Test")
        print()
        
        # Admin tests (if token provided)
        if self.admin_token:
            total_tests += 1
            if self.test_admin_dashboard():
                tests_passed += 1
                test_results.append("✅ Admin Dashboard")
            else:
                test_results.append("❌ Admin Dashboard")
            print()
            
            total_tests += 1
            if self.test_admin_users():
                tests_passed += 1
                test_results.append("✅ Admin Users")
            else:
                test_results.append("❌ Admin Users")
            print()
        
        # Results Summary
        print("=" * 60)
        print("TEST RESULTS SUMMARY")
        print("=" * 60)
        
        for result in test_results:
            print(result)
        
        print()
        print(f"TOTAL: {tests_passed}/{total_tests} tests passed")
        print(f"SUCCESS RATE: {(tests_passed/total_tests)*100:.1f}%")
        
        if tests_passed == total_tests:
            print("🎉 ALL TESTS PASSED! System is working correctly.")
        elif tests_passed >= total_tests * 0.8:
            print("⚠️  Most tests passed. Check failed tests above.")
        else:
            print("❌ Multiple test failures. System needs attention.")
        
        print("=" * 60)


def main():
    """Main function"""
    # Configuration
    api_base = "http://127.0.0.1:8000/api"
    admin_token = None  # Set this to your admin token for full testing
    
    # Check if admin token provided as argument
    if len(sys.argv) > 1:
        admin_token = sys.argv[1]
        print(f"Using admin token: {admin_token[:10]}...")
    
    # Create tester and run
    tester = KitongaAPITester(api_base, admin_token)
    tester.run_complete_test()


if __name__ == "__main__":
    main()
