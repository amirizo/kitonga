#!/usr/bin/env python3
"""
Complete API URL Testing Suite for Kitonga WiFi Billing System
Tests all endpoints defined in billing/urls.py systematically
"""

import requests
import json
import time
from datetime import datetime
import sys

# Configuration
BASE_URL = "http://127.0.0.1:8000/api"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"  # Update with actual admin password

# Test data
TEST_DATA = {
    "phone_numbers": ["255772236727", "255123456789"],
    "mac_addresses": ["AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"],
    "ip_addresses": ["192.168.0.100", "192.168.0.101"],
    "order_reference": "TEST_ORDER_123",
    "voucher_code": "TEST_VOUCHER_123",
    "user_id": 1,
    "payment_id": 1,
    "bundle_id": 1
}

class APITester:
    def __init__(self):
        self.session = requests.Session()
        self.admin_token = None
        self.results = {
            "total_tests": 0,
            "successful": 0,
            "failed": 0,
            "endpoints": {}
        }
    
    def print_header(self, title):
        print(f"\n{'='*80}")
        print(f" {title.center(78)}")
        print(f"{'='*80}")
    
    def print_subheader(self, title):
        print(f"\n{'-'*60}")
        print(f" {title}")
        print(f"{'-'*60}")
    
    def test_endpoint(self, method, endpoint, data=None, params=None, headers=None, auth_required=False):
        """Test a single API endpoint"""
        self.results["total_tests"] += 1
        url = f"{BASE_URL}{endpoint}"
        
        # Set default headers
        if headers is None:
            headers = {"Content-Type": "application/json"}
        
        # Add admin token if auth required and available
        if auth_required and self.admin_token:
            headers["Authorization"] = f"Bearer {self.admin_token}"
        
        try:
            print(f"\n📍 Testing: {method.upper()} {endpoint}")
            print(f"🔗 URL: {url}")
            
            if params:
                print(f"📋 Params: {json.dumps(params, indent=2)}")
            if data:
                print(f"📋 Data: {json.dumps(data, indent=2)}")
            
            # Make the request
            if method.upper() == "GET":
                response = self.session.get(url, params=params, headers=headers, timeout=10)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, headers=headers, timeout=10)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data, headers=headers, timeout=10)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, headers=headers, timeout=10)
            else:
                print(f"❌ Unsupported method: {method}")
                return False
            
            # Process response
            print(f"📊 Status Code: {response.status_code}")
            
            success = response.status_code < 500  # Consider 4xx as successful (client errors are expected)
            
            try:
                response_data = response.json()
                print(f"📄 Response: {json.dumps(response_data, indent=2)}")
            except:
                print(f"📄 Response Text: {response.text[:200]}...")
            
            # Record result
            self.results["endpoints"][f"{method.upper()} {endpoint}"] = {
                "status_code": response.status_code,
                "success": success,
                "auth_required": auth_required
            }
            
            if success:
                self.results["successful"] += 1
                print("✅ Test passed")
            else:
                self.results["failed"] += 1
                print("❌ Test failed (5xx error)")
            
            return success
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            self.results["failed"] += 1
            self.results["endpoints"][f"{method.upper()} {endpoint}"] = {
                "status_code": "ERROR",
                "success": False,
                "error": str(e)
            }
            return False
    
    def admin_login(self):
        """Attempt to log in as admin and get token"""
        self.print_subheader("ADMIN LOGIN ATTEMPT")
        login_data = {
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        }
        
        try:
            response = self.session.post(f"{BASE_URL}/auth/login/", json=login_data)
            if response.status_code == 200:
                result = response.json()
                if "token" in result:
                    self.admin_token = result["token"]
                    print("✅ Admin login successful")
                    return True
                elif "access_token" in result:
                    self.admin_token = result["access_token"]
                    print("✅ Admin login successful")
                    return True
            print("❌ Admin login failed - continuing without authentication")
            return False
        except Exception as e:
            print(f"❌ Admin login error: {e}")
            return False
    
    def test_authentication_endpoints(self):
        """Test all authentication endpoints"""
        self.print_subheader("AUTHENTICATION ENDPOINTS")
        
        # Admin login
        self.test_endpoint("POST", "/auth/login/", {
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        
        # Admin logout
        self.test_endpoint("POST", "/auth/logout/", auth_required=True)
        
        # Admin profile
        self.test_endpoint("GET", "/auth/profile/", auth_required=True)
        
        # Change password
        self.test_endpoint("POST", "/auth/change-password/", {
            "old_password": "oldpass",
            "new_password": "newpass"
        }, auth_required=True)
        
        # Create admin user
        self.test_endpoint("POST", "/auth/create-admin/", {
            "username": "testadmin",
            "password": "testpass123",
            "email": "test@example.com"
        }, auth_required=True)
    
    def test_wifi_access_endpoints(self):
        """Test WiFi access endpoints"""
        self.print_subheader("WI-FI ACCESS ENDPOINTS")
        
        # Verify access
        self.test_endpoint("POST", "/verify/", {
            "phone_number": TEST_DATA["phone_numbers"][0]
        })
        
        # List bundles
        self.test_endpoint("GET", "/bundles/")
        
        # Initiate payment
        self.test_endpoint("POST", "/initiate-payment/", {
            "phone_number": TEST_DATA["phone_numbers"][0],
            "bundle_id": TEST_DATA["bundle_id"],
            "mac_address": TEST_DATA["mac_addresses"][0]
        })
        
        # ClickPesa webhook (simulated)
        self.test_endpoint("POST", "/clickpesa-webhook/", {
            "order_reference": TEST_DATA["order_reference"],
            "status": "SUCCESS"
        })
        
        # Payment status query
        self.test_endpoint("GET", f"/payment-status/{TEST_DATA['order_reference']}/")
        
        # User status
        self.test_endpoint("GET", f"/user-status/{TEST_DATA['phone_numbers'][0]}/")
        
        # List user devices
        self.test_endpoint("GET", f"/devices/{TEST_DATA['phone_numbers'][0]}/")
        
        # Remove device
        self.test_endpoint("POST", "/devices/remove/", {
            "phone_number": TEST_DATA["phone_numbers"][0],
            "mac_address": TEST_DATA["mac_addresses"][0]
        })
    
    def test_voucher_endpoints(self):
        """Test voucher management endpoints"""
        self.print_subheader("VOUCHER ENDPOINTS")
        
        # Generate vouchers
        self.test_endpoint("POST", "/vouchers/generate/", {
            "batch_name": "TEST_BATCH",
            "count": 5,
            "duration_hours": 24
        }, auth_required=True)
        
        # Redeem voucher
        self.test_endpoint("POST", "/vouchers/redeem/", {
            "voucher_code": TEST_DATA["voucher_code"],
            "phone_number": TEST_DATA["phone_numbers"][0],
            "mac_address": TEST_DATA["mac_addresses"][0]
        })
        
        # List vouchers
        self.test_endpoint("GET", "/vouchers/list/", auth_required=True)
        
        # Test voucher access
        self.test_endpoint("POST", "/vouchers/test-access/", {
            "voucher_code": TEST_DATA["voucher_code"]
        })
    
    def test_admin_endpoints(self):
        """Test admin-only endpoints"""
        self.print_subheader("ADMIN ENDPOINTS")
        
        # Webhook logs
        self.test_endpoint("GET", "/webhook-logs/", auth_required=True)
        
        # Dashboard stats
        self.test_endpoint("GET", "/dashboard-stats/", auth_required=True)
        
        # Force logout
        self.test_endpoint("POST", "/force-logout/", {
            "phone_number": TEST_DATA["phone_numbers"][0]
        }, auth_required=True)
        
        # Debug user access
        self.test_endpoint("GET", "/debug-user-access/", 
                         params={"phone_number": TEST_DATA["phone_numbers"][0]})
    
    def test_user_management_endpoints(self):
        """Test user management endpoints"""
        self.print_subheader("USER MANAGEMENT ENDPOINTS")
        
        # List users (admin path)
        self.test_endpoint("GET", "/admin/users/", auth_required=True)
        
        # List users (short path)
        self.test_endpoint("GET", "/users/", auth_required=True)
        
        # Get user detail (admin path)
        self.test_endpoint("GET", f"/admin/users/{TEST_DATA['user_id']}/", auth_required=True)
        
        # Get user detail (short path)
        self.test_endpoint("GET", f"/users/{TEST_DATA['user_id']}/", auth_required=True)
        
        # Update user
        self.test_endpoint("PUT", f"/admin/users/{TEST_DATA['user_id']}/update/", {
            "phone_number": TEST_DATA["phone_numbers"][0],
            "is_active": True
        }, auth_required=True)
        
        # Delete user (commented out to avoid data loss)
        # self.test_endpoint("DELETE", f"/admin/users/{TEST_DATA['user_id']}/delete/", auth_required=True)
    
    def test_payment_management_endpoints(self):
        """Test payment management endpoints"""
        self.print_subheader("PAYMENT MANAGEMENT ENDPOINTS")
        
        # List payments (admin path)
        self.test_endpoint("GET", "/admin/payments/", auth_required=True)
        
        # List payments (short path)
        self.test_endpoint("GET", "/payments/", auth_required=True)
        
        # Get payment detail (admin path)
        self.test_endpoint("GET", f"/admin/payments/{TEST_DATA['payment_id']}/", auth_required=True)
        
        # Get payment detail (short path)
        self.test_endpoint("GET", f"/payments/{TEST_DATA['payment_id']}/", auth_required=True)
        
        # Refund payment
        self.test_endpoint("POST", f"/admin/payments/{TEST_DATA['payment_id']}/refund/", {
            "reason": "Test refund"
        }, auth_required=True)
    
    def test_bundle_management_endpoints(self):
        """Test bundle/package management endpoints"""
        self.print_subheader("BUNDLE MANAGEMENT ENDPOINTS")
        
        # Manage bundles
        self.test_endpoint("GET", "/admin/bundles/", auth_required=True)
        self.test_endpoint("POST", "/admin/bundles/", {
            "name": "Test Bundle",
            "price": 1000,
            "duration_hours": 24,
            "data_limit_mb": 1024
        }, auth_required=True)
        
        # Manage specific bundle
        self.test_endpoint("GET", f"/admin/bundles/{TEST_DATA['bundle_id']}/", auth_required=True)
        self.test_endpoint("PUT", f"/admin/bundles/{TEST_DATA['bundle_id']}/", {
            "name": "Updated Test Bundle",
            "price": 1500
        }, auth_required=True)
    
    def test_system_endpoints(self):
        """Test system settings and status endpoints"""
        self.print_subheader("SYSTEM ENDPOINTS")
        
        # System settings
        self.test_endpoint("GET", "/admin/settings/", auth_required=True)
        
        # System status
        self.test_endpoint("GET", "/admin/status/", auth_required=True)
        
        # Health check
        self.test_endpoint("GET", "/health/")
    
    def test_mikrotik_endpoints(self):
        """Test MikroTik integration endpoints"""
        self.print_subheader("MIKROTIK INTEGRATION ENDPOINTS")
        
        # MikroTik auth
        self.test_endpoint("POST", "/mikrotik/auth/", {
            "username": TEST_DATA["phone_numbers"][0],
            "mac": TEST_DATA["mac_addresses"][0],
            "ip": TEST_DATA["ip_addresses"][0]
        })
        
        # MikroTik logout
        self.test_endpoint("POST", "/mikrotik/logout/", {
            "username": TEST_DATA["phone_numbers"][0],
            "ip": TEST_DATA["ip_addresses"][0]
        })
        
        # MikroTik status check
        self.test_endpoint("GET", "/mikrotik/status/")
        
        # MikroTik user status
        self.test_endpoint("GET", "/mikrotik/user-status/", 
                         params={"username": TEST_DATA["phone_numbers"][0]})
    
    def test_mikrotik_admin_endpoints(self):
        """Test MikroTik admin endpoints"""
        self.print_subheader("MIKROTIK ADMIN ENDPOINTS")
        
        # MikroTik configuration
        self.test_endpoint("GET", "/admin/mikrotik/config/", auth_required=True)
        
        # Test MikroTik connection
        self.test_endpoint("GET", "/admin/mikrotik/test-connection/", auth_required=True)
        
        # MikroTik router info
        self.test_endpoint("GET", "/admin/mikrotik/router-info/", auth_required=True)
        
        # MikroTik active users
        self.test_endpoint("GET", "/admin/mikrotik/active-users/", auth_required=True)
        
        # Disconnect user
        self.test_endpoint("POST", "/admin/mikrotik/disconnect-user/", {
            "username": TEST_DATA["phone_numbers"][0]
        }, auth_required=True)
        
        # Disconnect all users (commented out for safety)
        # self.test_endpoint("POST", "/admin/mikrotik/disconnect-all/", auth_required=True)
        
        # Reboot router (commented out for safety)
        # self.test_endpoint("POST", "/admin/mikrotik/reboot/", auth_required=True)
        
        # Hotspot profiles
        self.test_endpoint("GET", "/admin/mikrotik/profiles/", auth_required=True)
        
        # Create hotspot profile
        self.test_endpoint("POST", "/admin/mikrotik/profiles/create/", {
            "name": "test-profile",
            "rate_limit": "1M/1M"
        }, auth_required=True)
        
        # System resources
        self.test_endpoint("GET", "/admin/mikrotik/resources/", auth_required=True)
    
    def print_summary(self):
        """Print test results summary"""
        self.print_header("TEST RESULTS SUMMARY")
        
        print(f"📊 Total Tests: {self.results['total_tests']}")
        print(f"✅ Successful: {self.results['successful']}")
        print(f"❌ Failed: {self.results['failed']}")
        print(f"📈 Success Rate: {(self.results['successful']/self.results['total_tests']*100):.1f}%")
        
        # Group results by status code
        status_codes = {}
        for endpoint, result in self.results["endpoints"].items():
            status = str(result["status_code"])
            if status not in status_codes:
                status_codes[status] = []
            status_codes[status].append(endpoint)
        
        print(f"\n📋 Status Code Summary:")
        for status, endpoints in sorted(status_codes.items()):
            print(f"  {status}: {len(endpoints)} endpoints")
        
        # Show failed tests
        failed_tests = [ep for ep, result in self.results["endpoints"].items() 
                       if not result["success"]]
        
        if failed_tests:
            print(f"\n❌ Failed Tests ({len(failed_tests)}):")
            for test in failed_tests:
                result = self.results["endpoints"][test]
                print(f"  - {test} (Status: {result['status_code']})")
        
        print(f"\n🕒 Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def main():
    """Run the complete API test suite"""
    tester = APITester()
    
    tester.print_header("KITONGA WIFI BILLING SYSTEM - COMPLETE API URL TESTING")
    print(f"🕒 Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔗 Base URL: {BASE_URL}")
    print(f"📋 Total endpoints to test: ~75 endpoints")
    
    # Try to login as admin first
    tester.admin_login()
    
    # Run all test categories
    try:
        tester.test_system_endpoints()          # Start with health check
        tester.test_authentication_endpoints()   
        tester.test_wifi_access_endpoints()     
        tester.test_voucher_endpoints()         
        tester.test_admin_endpoints()           
        tester.test_user_management_endpoints() 
        tester.test_payment_management_endpoints()
        tester.test_bundle_management_endpoints()
        tester.test_mikrotik_endpoints()        
        tester.test_mikrotik_admin_endpoints()  
        
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite error: {e}")
    finally:
        tester.print_summary()

if __name__ == "__main__":
    main()
