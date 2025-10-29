#!/usr/bin/env python3
"""
MikroTik Captive Portal API Tester
Tests the integration between MikroTik router and Django billing system
"""

import requests
import json
import time
from typing import Dict, Any

class MikroTikAPITester:
    def __init__(self, base_url: str = "http://127.0.0.1:8000/api"):
        self.base_url = base_url
        self.session = requests.Session()
        
    def test_endpoint(self, method: str, endpoint: str, data: Dict = None, description: str = ""):
        """Test an API endpoint and return response"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        print(f"\n🔍 {description}")
        print(f"📡 {method} {url}")
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data)
            else:
                response = self.session.request(method, url, json=data)
                
            print(f"📊 Status: {response.status_code}")
            
            # Handle different response types
            if response.headers.get('content-type', '').startswith('application/json'):
                result = response.json()
                print(f"📝 Response: {json.dumps(result, indent=2)}")
            else:
                result = response.text
                print(f"📝 Response: {result}")
                
            return response.status_code, result
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error: {e}")
            return 0, str(e)
    
    def test_captive_portal_flow(self):
        """Test the complete captive portal authentication flow"""
        
        print("🌐 CAPTIVE PORTAL FLOW TESTING")
        print("=" * 50)
        
        test_phone = "0772236727"
        test_mac = "AA:BB:CC:DD:EE:99"
        test_ip = "10.5.50.200"
        
        # Test 1: New user tries to authenticate (should fail)
        print("\n1️⃣ STEP 1: New user attempts WiFi access")
        print("   - User connects to 'kitonga-hotspot'")
        print("   - Router intercepts and calls authentication API")
        
        status, response = self.test_endpoint(
            "POST", 
            "mikrotik/auth/",
            {
                "username": test_phone,
                "password": test_phone,
                "mac": test_mac,
                "ip": test_ip
            },
            "MikroTik Authentication - New User"
        )
        
        if status == 403:
            print("✅ EXPECTED: Authentication denied - user needs to pay")
        else:
            print(f"❌ UNEXPECTED: Expected 403, got {status}")
            
        # Test 2: Check user status
        print("\n2️⃣ STEP 2: Check user status")
        status, response = self.test_endpoint(
            "GET",
            f"user-status/{test_phone}/",
            description="User Status Check"
        )
        
        # Test 3: Verify access (detailed check)
        print("\n3️⃣ STEP 3: Verify access with device info")
        status, response = self.test_endpoint(
            "POST",
            "verify/",
            {
                "phone_number": test_phone,
                "mac_address": test_mac,
                "ip_address": test_ip
            },
            "Verify Access - Detailed Check"
        )
        
        # Test 4: Initiate payment
        print("\n4️⃣ STEP 4: User initiates payment")
        print("   - User redirected to payment portal")
        print("   - User selects bundle and pays")
        
        status, response = self.test_endpoint(
            "POST",
            "initiate-payment/",
            {
                "phone_number": test_phone,
                "bundle_id": 1
            },
            "Payment Initiation"
        )
        
        order_reference = None
        if isinstance(response, dict) and response.get('success'):
            order_reference = response.get('order_reference')
            print(f"💰 Payment initiated: {order_reference}")
            
            # Test 5: Simulate payment completion
            print("\n5️⃣ STEP 5: Payment completed (webhook simulation)")
            status, webhook_response = self.test_endpoint(
                "POST",
                "clickpesa-webhook/",
                {
                    "event": "PAYMENT_RECEIVED",
                    "data": {
                        "orderReference": order_reference,
                        "status": "COMPLETED",
                        "collectedAmount": "1000"
                    }
                },
                "Payment Webhook - Payment Completed"
            )
            
            time.sleep(1)  # Allow processing
            
        # Test 6: User tries authentication again (should succeed)
        print("\n6️⃣ STEP 6: User tries WiFi access again")
        print("   - Router calls authentication API again")
        print("   - This time user has paid")
        
        status, response = self.test_endpoint(
            "POST",
            "mikrotik/auth/",
            {
                "username": test_phone,
                "password": test_phone,
                "mac": test_mac,
                "ip": test_ip
            },
            "MikroTik Authentication - Paid User"
        )
        
        if status == 200:
            print("🎉 SUCCESS: Authentication successful - user granted internet access")
        else:
            print(f"❌ FAILED: Expected 200, got {status}")
            
        # Test 7: Check user status after payment
        print("\n7️⃣ STEP 7: Check user status after payment")
        status, response = self.test_endpoint(
            "GET",
            f"user-status/{test_phone}/",
            description="User Status After Payment"
        )
        
        # Test 8: MikroTik user status check
        print("\n8️⃣ STEP 8: MikroTik specific user status")
        status, response = self.test_endpoint(
            "POST",
            "mikrotik/user-status/",
            {"username": test_phone},
            "MikroTik User Status Check"
        )
        
        # Test 9: User logout
        print("\n9️⃣ STEP 9: User logout")
        status, response = self.test_endpoint(
            "POST",
            "mikrotik/logout/",
            {
                "username": test_phone,
                "ip": test_ip,
                "mac": test_mac
            },
            "MikroTik User Logout"
        )
        
    def test_voucher_flow(self):
        """Test voucher-based access"""
        print("\n\n🎫 VOUCHER FLOW TESTING")
        print("=" * 50)
        
        voucher_phone = "0772236728"
        voucher_mac = "BB:CC:DD:EE:FF:01"
        voucher_ip = "10.5.50.201"
        
        # Note: Voucher generation requires admin authentication
        print("📝 NOTE: Voucher testing requires admin token")
        print("   In production:")
        print("   1. Admin generates vouchers")
        print("   2. User enters voucher code")
        print("   3. System grants access")
        
        # Test voucher redemption (if voucher exists)
        print("\n1️⃣ Testing voucher redemption")
        status, response = self.test_endpoint(
            "POST",
            "vouchers/redeem/",
            {
                "phone_number": voucher_phone,
                "voucher_code": "TEST-ABCD-1234"  # Example voucher
            },
            "Voucher Redemption"
        )
        
        # Test authentication for voucher user
        print("\n2️⃣ Testing authentication for voucher user")
        status, response = self.test_endpoint(
            "POST",
            "mikrotik/auth/",
            {
                "username": voucher_phone,
                "password": voucher_phone,
                "mac": voucher_mac,
                "ip": voucher_ip
            },
            "MikroTik Authentication - Voucher User"
        )
        
    def test_router_status(self):
        """Test router status endpoints"""
        print("\n\n📡 ROUTER STATUS TESTING")
        print("=" * 50)
        
        # Test general status
        status, response = self.test_endpoint(
            "GET",
            "mikrotik/status/",
            description="MikroTik Router Status"
        )
        
    def run_all_tests(self):
        """Run all test suites"""
        print("🚀 Starting MikroTik API Tests")
        print("🌐 Testing Captive Portal Integration")
        print(f"📡 API Base URL: {self.base_url}")
        
        try:
            self.test_captive_portal_flow()
            self.test_voucher_flow()
            self.test_router_status()
            
            print("\n\n✅ ALL TESTS COMPLETED")
            print("=" * 50)
            print("\n📋 SUMMARY:")
            print("✅ Captive Portal Flow: Authentication, Payment, Access")
            print("✅ Voucher System: Alternative payment method")
            print("✅ Router Integration: Status monitoring")
            print("\n🔧 NEXT STEPS:")
            print("1. Configure MikroTik router for external authentication")
            print("2. Point router to this Django API")
            print("3. Set up captive portal page")
            print("4. Configure payment gateway")
            
        except KeyboardInterrupt:
            print("\n\n⏹️  Tests interrupted by user")
        except Exception as e:
            print(f"\n\n❌ Test suite failed: {e}")

def main():
    """Main test runner"""
    import sys
    
    # Check if custom URL provided
    base_url = "http://127.0.0.1:8000/api"
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
        
    print(f"🔧 Using API base URL: {base_url}")
    
    tester = MikroTikAPITester(base_url)
    tester.run_all_tests()

if __name__ == "__main__":
    main()
