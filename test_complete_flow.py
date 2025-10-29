#!/usr/bin/env python3
"""
Complete User Flow Testing: Payment + Voucher + Logout Fix
Tests the full WiFi billing system including the logout bug fix
"""

import requests
import json
import time
from datetime import datetime

class KitongaAPITester:
    def __init__(self, base_url="https://api.kitonga.klikcell.com/api"):
        self.base_url = base_url
        self.session = requests.Session()
        self.admin_token = None
        
    def log(self, message, status="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        status_icon = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️"}.get(status, "📝")
        print(f"[{timestamp}] {status_icon} {message}")
        
    def test_request(self, method, endpoint, data=None, headers=None, description=""):
        """Make API request and handle response"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        self.log(f"Testing: {description}")
        self.log(f"Request: {method} {endpoint}")
        
        try:
            kwargs = {"timeout": 10}
            if headers:
                kwargs["headers"] = headers
            if data:
                kwargs["json"] = data
                
            response = self.session.request(method, url, **kwargs)
            
            self.log(f"Status: {response.status_code}")
            
            # Try to parse JSON response
            try:
                result = response.json()
                self.log(f"Response: {json.dumps(result, indent=2)}")
            except:
                result = response.text
                self.log(f"Response: {result[:500]}")
                
            return response.status_code, result
            
        except requests.exceptions.RequestException as e:
            self.log(f"Request failed: {e}", "ERROR")
            return 0, str(e)
    
    def test_payment_user_flow(self):
        """Test complete payment user flow"""
        self.log("=" * 60)
        self.log("TESTING PAYMENT USER FLOW", "INFO")
        self.log("=" * 60)
        
        payment_phone = "0772236727"
        payment_mac = "AA:BB:CC:DD:EE:99"
        payment_ip = "10.5.50.200"
        
        # Step 1: Check initial access (should be denied)
        self.log("Step 1: Check initial access for new user")
        status, response = self.test_request(
            "POST", "verify/",
            {
                "phone_number": payment_phone,
                "mac_address": payment_mac,
                "ip_address": payment_ip
            },
            description="Verify access - new user"
        )
        
        # Step 2: Initiate payment
        self.log("Step 2: Initiate payment")
        status, response = self.test_request(
            "POST", "initiate-payment/",
            {
                "phone_number": payment_phone,
                "bundle_id": 1
            },
            description="Initiate payment"
        )
        
        order_reference = None
        if isinstance(response, dict) and response.get('success'):
            order_reference = response.get('order_reference')
            self.log(f"Payment initiated: {order_reference}", "SUCCESS")
            
            # Step 3: Simulate payment completion
            self.log("Step 3: Simulate payment completion")
            webhook_data = {
                "event": "PAYMENT_RECEIVED",
                "data": {
                    "orderReference": order_reference,
                    "status": "COMPLETED",
                    "collectedAmount": "1000"
                }
            }
            
            status, response = self.test_request(
                "POST", "clickpesa-webhook/",
                webhook_data,
                description="Payment webhook"
            )
            
            time.sleep(2)  # Allow processing
            
        # Step 4: Test MikroTik authentication
        self.log("Step 4: Test MikroTik authentication after payment")
        status, response = self.test_request(
            "POST", "mikrotik/auth/",
            {
                "username": payment_phone,
                "password": payment_phone,
                "mac": payment_mac,
                "ip": payment_ip
            },
            description="MikroTik auth - paid user"
        )
        
        if status == 200:
            self.log("Authentication successful - user granted access", "SUCCESS")
        else:
            self.log(f"Authentication failed - Status: {status}", "ERROR")
            
        # Step 5: Check user status
        self.log("Step 5: Check user status after payment")
        status, response = self.test_request(
            "GET", f"user-status/{payment_phone}/",
            description="User status check"
        )
        
        # Step 6: Test MikroTik logout (THIS IS WHERE THE BUG IS)
        self.log("Step 6: Test MikroTik logout - FIXING 400 ERROR")
        
        # Test with different parameter combinations to find the issue
        logout_attempts = [
            {"username": payment_phone},
            {"username": payment_phone, "ip": payment_ip},
            {"username": payment_phone, "ip_address": payment_ip},
            {"username": payment_phone, "mac": payment_mac, "ip": payment_ip},
            {"phone_number": payment_phone, "ip_address": payment_ip}
        ]
        
        for i, logout_data in enumerate(logout_attempts, 1):
            self.log(f"Logout attempt {i}: {logout_data}")
            status, response = self.test_request(
                "POST", "mikrotik/logout/",
                logout_data,
                description=f"MikroTik logout attempt {i}"
            )
            
            if status == 200:
                self.log(f"Logout successful with parameters: {logout_data}", "SUCCESS")
                break
            else:
                self.log(f"Logout failed: Status {status}", "WARNING")
        
        return payment_phone
    
    def test_voucher_user_flow(self):
        """Test complete voucher user flow"""
        self.log("=" * 60)
        self.log("TESTING VOUCHER USER FLOW", "INFO") 
        self.log("=" * 60)
        
        voucher_phone = "0772236728"
        voucher_mac = "BB:CC:DD:EE:FF:01"
        voucher_ip = "10.5.50.201"
        
        # Step 1: Check initial access (should be denied)
        self.log("Step 1: Check initial access for voucher user")
        status, response = self.test_request(
            "POST", "verify/",
            {
                "phone_number": voucher_phone,
                "mac_address": voucher_mac,
                "ip_address": voucher_ip
            },
            description="Verify access - voucher user (before redemption)"
        )
        
        # Step 2: Try to redeem a voucher (might fail if no vouchers exist)
        self.log("Step 2: Try voucher redemption")
        status, response = self.test_request(
            "POST", "vouchers/redeem/",
            {
                "phone_number": voucher_phone,
                "voucher_code": "TEST-ABCD-1234"
            },
            description="Voucher redemption"
        )
        
        if status == 200:
            self.log("Voucher redeemed successfully", "SUCCESS")
            
            # Step 3: Test authentication after voucher
            self.log("Step 3: Test authentication after voucher redemption")
            status, response = self.test_request(
                "POST", "mikrotik/auth/",
                {
                    "username": voucher_phone,
                    "password": voucher_phone,
                    "mac": voucher_mac,
                    "ip": voucher_ip
                },
                description="MikroTik auth - voucher user"
            )
            
            if status == 200:
                self.log("Voucher user authentication successful", "SUCCESS")
            else:
                self.log(f"Voucher user authentication failed: {status}", "ERROR")
                
            # Step 4: Test logout for voucher user
            self.log("Step 4: Test logout for voucher user")
            status, response = self.test_request(
                "POST", "mikrotik/logout/",
                {"username": voucher_phone, "ip": voucher_ip},
                description="MikroTik logout - voucher user"
            )
            
        else:
            self.log("Voucher redemption failed - no valid vouchers available", "WARNING")
            
        return voucher_phone
    
    def test_logout_parameter_formats(self):
        """Test different logout parameter formats to fix the 400 error"""
        self.log("=" * 60)
        self.log("TESTING LOGOUT PARAMETER FORMATS", "INFO")
        self.log("=" * 60)
        
        test_phone = "0772236727"
        test_ip = "10.5.50.200"
        test_mac = "AA:BB:CC:DD:EE:99"
        
        # Different parameter formats that frontend might be sending
        logout_formats = [
            # Format 1: Basic username only
            {"username": test_phone},
            
            # Format 2: Username + IP
            {"username": test_phone, "ip": test_ip},
            
            # Format 3: Username + IP as ip_address
            {"username": test_phone, "ip_address": test_ip},
            
            # Format 4: All parameters
            {"username": test_phone, "ip": test_ip, "mac": test_mac},
            
            # Format 5: Phone number instead of username
            {"phone_number": test_phone, "ip_address": test_ip},
            
            # Format 6: What frontend might be sending
            {"phoneNumber": test_phone, "ipAddress": test_ip},
            
            # Format 7: Empty (should return 400)
            {},
            
            # Format 8: Null username
            {"username": None, "ip": test_ip}
        ]
        
        for i, logout_data in enumerate(logout_formats, 1):
            self.log(f"Testing logout format {i}: {logout_data}")
            status, response = self.test_request(
                "POST", "mikrotik/logout/",
                logout_data,
                description=f"Logout format test {i}"
            )
            
            if status == 200:
                self.log(f"✅ Format {i} works: {logout_data}", "SUCCESS")
            elif status == 400:
                self.log(f"❌ Format {i} returns 400: {logout_data}", "ERROR")
            else:
                self.log(f"⚠️ Format {i} returns {status}: {logout_data}", "WARNING")
    
    def test_all_mikrotik_endpoints(self):
        """Test all MikroTik integration endpoints"""
        self.log("=" * 60)
        self.log("TESTING ALL MIKROTIK ENDPOINTS", "INFO")
        self.log("=" * 60)
        
        test_phone = "0772236727"
        test_mac = "AA:BB:CC:DD:EE:99"
        test_ip = "10.5.50.200"
        
        # Test auth endpoint
        self.log("Testing mikrotik/auth/")
        status, response = self.test_request(
            "POST", "mikrotik/auth/",
            {
                "username": test_phone,
                "password": test_phone,
                "mac": test_mac,
                "ip": test_ip
            },
            description="MikroTik authentication"
        )
        
        # Test status endpoint
        self.log("Testing mikrotik/status/")
        status, response = self.test_request(
            "GET", "mikrotik/status/",
            description="MikroTik status check"
        )
        
        # Test user-status endpoint
        self.log("Testing mikrotik/user-status/")
        status, response = self.test_request(
            "POST", "mikrotik/user-status/",
            {"username": test_phone},
            description="MikroTik user status"
        )
        
        # Test logout endpoint (the problematic one)
        self.log("Testing mikrotik/logout/")
        status, response = self.test_request(
            "POST", "mikrotik/logout/",
            {"username": test_phone, "ip": test_ip},
            description="MikroTik logout"
        )
        
    def run_complete_tests(self):
        """Run all tests"""
        self.log("🚀 STARTING COMPLETE API TESTING", "INFO")
        self.log(f"🌐 Base URL: {self.base_url}")
        
        try:
            # Test logout parameter formats first to identify the issue
            self.test_logout_parameter_formats()
            
            # Test complete payment flow
            payment_user = self.test_payment_user_flow()
            
            # Test complete voucher flow  
            voucher_user = self.test_voucher_user_flow()
            
            # Test all MikroTik endpoints
            self.test_all_mikrotik_endpoints()
            
            self.log("=" * 60)
            self.log("🎉 ALL TESTS COMPLETED", "SUCCESS")
            self.log("=" * 60)
            
            self.log("📋 SUMMARY:")
            self.log("✅ Payment user flow tested")
            self.log("✅ Voucher user flow tested") 
            self.log("✅ MikroTik logout bug investigation completed")
            self.log("✅ All endpoint parameter formats tested")
            
        except KeyboardInterrupt:
            self.log("⏹️ Tests interrupted by user", "WARNING")
        except Exception as e:
            self.log(f"❌ Test suite failed: {e}", "ERROR")

def main():
    """Main test runner"""
    import sys
    
    # Use production API by default
    base_url = "https://api.kitonga.klikcell.com/api"
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
        
    print(f"🔧 Testing API: {base_url}")
    print(f"📱 Phone numbers: 0772236727 (payment), 0772236728 (voucher)")
    print(f"🎯 Focus: Fixing logout 400 error and testing complete flows")
    print()
    
    tester = KitongaAPITester(base_url)
    tester.run_complete_tests()

if __name__ == "__main__":
    main()
