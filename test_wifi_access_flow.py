#!/usr/bin/env python3
"""
Comprehensive WiFi Access API Test Script
Tests the complete user journey from payment to MikroTik authentication

Usage:
    python test_wifi_access_flow.py [API_BASE_URL]
    
Examples:
    python test_wifi_access_flow.py http://localhost:8000/api
    python test_wifi_access_flow.py https://api.yum-express.com/api
"""

import sys
import json
import requests
import time
from datetime import datetime


class WiFiAccessTester:
    def __init__(self, base_url="http://localhost:8000/api"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.test_phone = "255772236727"
        self.test_mac = "aa:bb:cc:dd:ee:ff"
        self.test_ip = "192.168.1.100"
        self.order_reference = None
        
    def log(self, message, status="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {status}: {message}")
        
    def make_request(self, method, endpoint, data=None, headers=None):
        """Make HTTP request with error handling"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        if headers is None:
            headers = {"Content-Type": "application/json"}
            
        try:
            if method == "GET":
                response = self.session.get(url, headers=headers, timeout=30)
            elif method == "POST":
                if headers.get("Content-Type") == "application/json":
                    response = self.session.post(url, json=data, headers=headers, timeout=30)
                else:
                    response = self.session.post(url, data=data, headers=headers, timeout=30)
            else:
                response = self.session.request(method, url, json=data, headers=headers, timeout=30)
                
            return response
            
        except requests.exceptions.RequestException as e:
            self.log(f"Request failed: {e}", "ERROR")
            return None
            
    def test_health_check(self):
        """Test if the API is accessible"""
        self.log("Testing API health check...")
        
        response = self.make_request("GET", "/health/")
        if not response:
            return False
            
        if response.status_code == 200:
            self.log("✅ API is accessible", "SUCCESS")
            return True
        else:
            self.log(f"❌ API health check failed: {response.status_code}", "ERROR")
            self.log(f"Response: {response.text[:200]}")
            return False
            
    def test_list_bundles(self):
        """Test bundle listing"""
        self.log("Testing bundle listing...")
        
        response = self.make_request("GET", "/bundles/")
        if not response:
            return False
            
        if response.status_code == 200:
            try:
                data = response.json()
                bundles = data.get('bundles', [])
                self.log(f"✅ Found {len(bundles)} bundles", "SUCCESS")
                for bundle in bundles[:3]:  # Show first 3
                    self.log(f"   - {bundle['name']}: {bundle['price']} TSH for {bundle['duration_hours']}h")
                return True
            except json.JSONDecodeError:
                self.log("❌ Invalid JSON response", "ERROR")
                return False
        else:
            self.log(f"❌ Bundle listing failed: {response.status_code}", "ERROR")
            return False
            
    def test_user_status_before_payment(self):
        """Check user status before payment"""
        self.log(f"Checking user status for {self.test_phone}...")
        
        response = self.make_request("GET", f"/user-status/{self.test_phone}/")
        if not response:
            return False
            
        if response.status_code == 200:
            user_data = response.json()
            self.log(f"✅ User exists - Active: {user_data.get('has_active_access', False)}")
            return True
        elif response.status_code == 404:
            self.log("✅ User not found (will be created during payment)")
            return True
        else:
            self.log(f"❌ User status check failed: {response.status_code}", "ERROR")
            return False
            
    def test_initiate_payment(self):
        """Test payment initiation"""
        self.log("Testing payment initiation...")
        
        payment_data = {
            "phone_number": self.test_phone,
            "bundle_id": 1,  # Daily bundle
            "ip_address": self.test_ip,
            "mac_address": self.test_mac
        }
        
        response = self.make_request("POST", "/initiate-payment/", payment_data)
        if not response:
            return False
            
        if response.status_code == 200:
            try:
                data = response.json()
                if data.get('success'):
                    self.order_reference = data.get('order_reference')
                    self.log(f"✅ Payment initiated - Order: {self.order_reference}", "SUCCESS")
                    self.log(f"   Amount: {data.get('amount')} TSH")
                    return True
                else:
                    self.log(f"❌ Payment initiation failed: {data.get('message')}", "ERROR")
                    return False
            except json.JSONDecodeError:
                self.log("❌ Invalid JSON response", "ERROR")
                return False
        else:
            self.log(f"❌ Payment initiation failed: {response.status_code}", "ERROR")
            return False
            
    def test_webhook_simulation(self):
        """Simulate successful payment webhook"""
        if not self.order_reference:
            self.log("❌ No order reference available", "ERROR")
            return False
            
        self.log("Simulating successful payment webhook...")
        
        webhook_data = {
            "event": "PAYMENT RECEIVED",
            "data": {
                "orderReference": self.order_reference,
                "paymentId": "TEST123456789",
                "status": "COMPLETED",
                "channel": "TIGO-PESA",
                "collectedAmount": "1000.00"
            }
        }
        
        response = self.make_request("POST", "/clickpesa-webhook/", webhook_data)
        if not response:
            return False
            
        if response.status_code == 200:
            try:
                data = response.json()
                if data.get('success'):
                    self.log("✅ Payment webhook processed successfully", "SUCCESS")
                    return True
                else:
                    self.log(f"❌ Webhook processing failed: {data.get('message')}", "ERROR")
                    return False
            except json.JSONDecodeError:
                self.log("❌ Invalid JSON response", "ERROR")
                return False
        else:
            self.log(f"❌ Webhook processing failed: {response.status_code}", "ERROR")
            return False
            
    def test_verify_access(self):
        """Test access verification after payment"""
        self.log("Testing access verification...")
        
        verify_data = {
            "phone_number": self.test_phone,
            "ip_address": self.test_ip,
            "mac_address": self.test_mac
        }
        
        response = self.make_request("POST", "/verify/", verify_data)
        if not response:
            return False
            
        if response.status_code == 200:
            try:
                data = response.json()
                access_granted = data.get('access_granted', False)
                if access_granted:
                    self.log("✅ Access verification successful", "SUCCESS")
                    user_data = data.get('user', {})
                    remaining = user_data.get('time_remaining', {})
                    if remaining:
                        self.log(f"   Time remaining: {remaining.get('hours', 0)}h {remaining.get('minutes', 0)}m")
                    
                    # Check MikroTik connection status
                    mikrotik_status = data.get('mikrotik_connection', {})
                    if mikrotik_status.get('success'):
                        self.log("✅ MikroTik connection successful", "SUCCESS")
                    else:
                        self.log(f"⚠️ MikroTik connection failed: {mikrotik_status.get('message', 'Unknown error')}", "WARNING")
                    
                    return True
                else:
                    denial_reason = data.get('denial_reason', 'Unknown')
                    self.log(f"❌ Access denied: {denial_reason}", "ERROR")
                    return False
            except json.JSONDecodeError:
                self.log("❌ Invalid JSON response", "ERROR")
                return False
        else:
            self.log(f"❌ Access verification failed: {response.status_code}", "ERROR")
            return False
            
    def test_mikrotik_auth(self):
        """Test MikroTik authentication endpoint"""
        self.log("Testing MikroTik authentication...")
        
        auth_data = {
            "username": self.test_phone,
            "password": "",
            "mac": self.test_mac,
            "ip": self.test_ip
        }
        
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = self.make_request("POST", "/mikrotik/auth/", auth_data, headers)
        if not response:
            return False
            
        if response.status_code == 200:
            response_text = response.text.strip()
            if response_text == "OK":
                self.log("✅ MikroTik authentication successful", "SUCCESS")
                return True
            else:
                self.log(f"❌ MikroTik authentication failed: {response_text}", "ERROR")
                return False
        else:
            self.log(f"❌ MikroTik authentication failed: {response.status_code}", "ERROR")
            return False
            
    def test_user_devices(self):
        """Test device listing"""
        self.log("Testing device listing...")
        
        response = self.make_request("GET", f"/devices/{self.test_phone}/")
        if not response:
            return False
            
        if response.status_code == 200:
            try:
                data = response.json()
                if data.get('success'):
                    devices = data.get('devices', [])
                    self.log(f"✅ Found {len(devices)} devices", "SUCCESS")
                    for device in devices:
                        status = "Active" if device.get('is_active') else "Inactive"
                        self.log(f"   - {device.get('mac_address')}: {status}")
                    return True
                else:
                    self.log(f"❌ Device listing failed: {data.get('message')}", "ERROR")
                    return False
            except json.JSONDecodeError:
                self.log("❌ Invalid JSON response", "ERROR")
                return False
        else:
            self.log(f"❌ Device listing failed: {response.status_code}", "ERROR")
            return False
            
    def run_complete_test(self):
        """Run the complete WiFi access test flow"""
        self.log("=" * 60)
        self.log("STARTING WIFI ACCESS API TEST")
        self.log("=" * 60)
        
        test_results = []
        
        # Test 1: Health check
        test_results.append(("API Health Check", self.test_health_check()))
        
        # Test 2: List bundles
        test_results.append(("Bundle Listing", self.test_list_bundles()))
        
        # Test 3: Check user status before payment
        test_results.append(("User Status (Before)", self.test_user_status_before_payment()))
        
        # Test 4: Initiate payment
        test_results.append(("Payment Initiation", self.test_initiate_payment()))
        
        # Wait a bit before webhook
        time.sleep(1)
        
        # Test 5: Simulate payment webhook
        test_results.append(("Payment Webhook", self.test_webhook_simulation()))
        
        # Wait a bit before verification
        time.sleep(1)
        
        # Test 6: Verify access
        test_results.append(("Access Verification", self.test_verify_access()))
        
        # Test 7: MikroTik authentication
        test_results.append(("MikroTik Authentication", self.test_mikrotik_auth()))
        
        # Test 8: Device listing
        test_results.append(("Device Listing", self.test_user_devices()))
        
        # Summary
        self.log("=" * 60)
        self.log("TEST RESULTS SUMMARY")
        self.log("=" * 60)
        
        passed = 0
        failed = 0
        
        for test_name, result in test_results:
            status = "✅ PASS" if result else "❌ FAIL"
            self.log(f"{status} | {test_name}")
            if result:
                passed += 1
            else:
                failed += 1
                
        self.log("=" * 60)
        self.log(f"TOTAL: {passed} passed, {failed} failed")
        
        if failed == 0:
            self.log("🎉 ALL TESTS PASSED! WiFi Access API is fully functional!", "SUCCESS")
        else:
            self.log(f"⚠️ {failed} tests failed. Check the logs above for details.", "WARNING")
            
        return failed == 0


def main():
    # Get API base URL from command line or use default
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:8000/api"
        
    print(f"Testing WiFi Access API at: {base_url}")
    print()
    
    tester = WiFiAccessTester(base_url)
    success = tester.run_complete_test()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
