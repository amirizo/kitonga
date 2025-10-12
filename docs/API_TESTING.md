# Kitonga API Testing Guide

Complete testing documentation for all Kitonga Wi-Fi Billing System APIs.

## Quick Start

### 1. Setup Test Environment
```bash
# Start Django server
python manage.py runserver

# Create test admin user
python manage.py createsuperuser

# Create test bundles (optional - can use admin panel)
python manage.py shell
>>> from billing.models import Bundle
>>> Bundle.objects.create(name="Daily Access", price=1000, duration_hours=24, is_active=True)
>>> Bundle.objects.create(name="Weekly Access", price=5000, duration_hours=168, is_active=True)
>>> Bundle.objects.create(name="Monthly Access", price=15000, duration_hours=720, is_active=True)
```

### 2. Test Variables
```bash
export API_URL="http://localhost:8000/api"
export TEST_PHONE="255712345678"
export ADMIN_USER="admin"
export ADMIN_PASS="your_admin_password"
```

## API Testing Scripts

### Complete Python Test Suite

Save as `test_apis.py`:

```python
#!/usr/bin/env python3
"""
Comprehensive API test suite for Kitonga Wi-Fi Billing System
"""
import requests
import json
import time
import sys
from datetime import datetime

class KitongaAPITester:
    def __init__(self, base_url="http://localhost:8000/api", test_phone="255712345678"):
        self.base_url = base_url
        self.test_phone = test_phone
        self.test_results = []
        self.order_reference = None
        
    def log_test(self, test_name, success, message, response_code=None):
        """Log test results"""
        result = {
            'test': test_name,
            'success': success,
            'message': message,
            'response_code': response_code,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        if response_code:
            print(f"    Response Code: {response_code}")
    
    def test_health_check(self):
        """Test health check endpoint"""
        try:
            response = requests.get(f"{self.base_url}/health/")
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'healthy':
                    self.log_test("Health Check", True, "API is healthy", response.status_code)
                    return True
                else:
                    self.log_test("Health Check", False, "Unhealthy response", response.status_code)
            else:
                self.log_test("Health Check", False, "Non-200 response", response.status_code)
        except Exception as e:
            self.log_test("Health Check", False, f"Exception: {str(e)}")
        return False
    
    def test_list_bundles(self):
        """Test list bundles endpoint"""
        try:
            response = requests.get(f"{self.base_url}/bundles/")
            if response.status_code == 200:
                data = response.json()
                bundles = data.get('bundles', [])
                self.bundles = bundles  # Store for later use
                self.log_test("List Bundles", True, f"Found {len(bundles)} bundles", response.status_code)
                return True
            else:
                self.log_test("List Bundles", False, "Non-200 response", response.status_code)
        except Exception as e:
            self.log_test("List Bundles", False, f"Exception: {str(e)}")
        return False
    
    def test_verify_access_new_user(self):
        """Test verify access for new user (should fail)"""
        try:
            payload = {
                "phone_number": self.test_phone,
                "ip_address": "192.168.1.100",
                "mac_address": "00:11:22:33:44:55"
            }
            response = requests.post(f"{self.base_url}/verify/", json=payload)
            
            if response.status_code == 404:
                data = response.json()
                if not data.get('access_granted', True):
                    self.log_test("Verify Access (New User)", True, "Correctly denied access", response.status_code)
                    return True
            
            self.log_test("Verify Access (New User)", False, "Unexpected response", response.status_code)
        except Exception as e:
            self.log_test("Verify Access (New User)", False, f"Exception: {str(e)}")
        return False
    
    def test_user_status_new_user(self):
        """Test user status for new user (should fail)"""
        try:
            response = requests.get(f"{self.base_url}/user-status/{self.test_phone}/")
            
            if response.status_code == 404:
                self.log_test("User Status (New User)", True, "User not found (expected)", response.status_code)
                return True
            else:
                self.log_test("User Status (New User)", False, "User should not exist yet", response.status_code)
        except Exception as e:
            self.log_test("User Status (New User)", False, f"Exception: {str(e)}")
        return False
    
    def test_initiate_payment(self):
        """Test payment initiation"""
        try:
            bundle_id = self.bundles[0]['id'] if hasattr(self, 'bundles') and self.bundles else None
            payload = {
                "phone_number": self.test_phone,
                "bundle_id": bundle_id
            }
            response = requests.post(f"{self.base_url}/initiate-payment/", json=payload)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    self.order_reference = data.get('order_reference')
                    self.log_test("Initiate Payment", True, f"Payment initiated: {self.order_reference}", response.status_code)
                    return True
                else:
                    self.log_test("Initiate Payment", False, data.get('message', 'Unknown error'), response.status_code)
            else:
                self.log_test("Initiate Payment", False, "Non-200 response", response.status_code)
        except Exception as e:
            self.log_test("Initiate Payment", False, f"Exception: {str(e)}")
        return False
    
    def test_payment_status(self):
        """Test payment status query"""
        if not self.order_reference:
            self.log_test("Payment Status", False, "No order reference available")
            return False
        
        try:
            response = requests.get(f"{self.base_url}/payment-status/{self.order_reference}/")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    payment_status = data.get('payment', {}).get('status', 'unknown')
                    self.log_test("Payment Status", True, f"Status: {payment_status}", response.status_code)
                    return True
                else:
                    self.log_test("Payment Status", False, data.get('message', 'Unknown error'), response.status_code)
            else:
                self.log_test("Payment Status", False, "Non-200 response", response.status_code)
        except Exception as e:
            self.log_test("Payment Status", False, f"Exception: {str(e)}")
        return False
    
    def test_user_status_after_payment(self):
        """Test user status after payment initiation"""
        try:
            response = requests.get(f"{self.base_url}/user-status/{self.test_phone}/")
            
            if response.status_code == 200:
                data = response.json()
                phone = data.get('phone_number')
                if phone == self.test_phone:
                    self.log_test("User Status (After Payment)", True, "User created successfully", response.status_code)
                    return True
                else:
                    self.log_test("User Status (After Payment)", False, "Wrong user data", response.status_code)
            else:
                self.log_test("User Status (After Payment)", False, "User not found", response.status_code)
        except Exception as e:
            self.log_test("User Status (After Payment)", False, f"Exception: {str(e)}")
        return False
    
    def test_list_user_devices(self):
        """Test list user devices"""
        try:
            response = requests.get(f"{self.base_url}/devices/{self.test_phone}/")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    device_count = len(data.get('devices', []))
                    self.log_test("List User Devices", True, f"Found {device_count} devices", response.status_code)
                    return True
                else:
                    self.log_test("List User Devices", False, "Unsuccessful response", response.status_code)
            else:
                self.log_test("List User Devices", False, "Non-200 response", response.status_code)
        except Exception as e:
            self.log_test("List User Devices", False, f"Exception: {str(e)}")
        return False
    
    def test_voucher_redemption_invalid(self):
        """Test voucher redemption with invalid code"""
        try:
            payload = {
                "voucher_code": "INVALID-CODE-TEST",
                "phone_number": self.test_phone
            }
            response = requests.post(f"{self.base_url}/vouchers/redeem/", json=payload)
            
            if response.status_code == 404:
                self.log_test("Voucher Redemption (Invalid)", True, "Invalid voucher correctly rejected", response.status_code)
                return True
            else:
                self.log_test("Voucher Redemption (Invalid)", False, "Should reject invalid voucher", response.status_code)
        except Exception as e:
            self.log_test("Voucher Redemption (Invalid)", False, f"Exception: {str(e)}")
        return False
    
    def test_admin_endpoints(self, admin_user="admin", admin_pass="admin"):
        """Test admin-only endpoints"""
        auth = (admin_user, admin_pass)
        
        # Test generate vouchers
        try:
            payload = {
                "quantity": 5,
                "duration_hours": 24,
                "batch_id": "TEST-BATCH-001",
                "notes": "Test vouchers from API test"
            }
            response = requests.post(f"{self.base_url}/vouchers/generate/", json=payload, auth=auth)
            
            if response.status_code == 201:
                data = response.json()
                if data.get('success'):
                    self.test_vouchers = data.get('vouchers', [])
                    self.log_test("Generate Vouchers", True, f"Generated {len(self.test_vouchers)} vouchers", response.status_code)
                else:
                    self.log_test("Generate Vouchers", False, "Unsuccessful response", response.status_code)
            elif response.status_code == 401:
                self.log_test("Generate Vouchers", False, "Authentication failed - check admin credentials", response.status_code)
            else:
                self.log_test("Generate Vouchers", False, "Unexpected response", response.status_code)
        except Exception as e:
            self.log_test("Generate Vouchers", False, f"Exception: {str(e)}")
        
        # Test list vouchers
        try:
            response = requests.get(f"{self.base_url}/vouchers/list/", auth=auth)
            
            if response.status_code == 200:
                data = response.json()
                voucher_count = data.get('count', 0)
                self.log_test("List Vouchers", True, f"Found {voucher_count} vouchers", response.status_code)
            elif response.status_code == 401:
                self.log_test("List Vouchers", False, "Authentication failed", response.status_code)
            else:
                self.log_test("List Vouchers", False, "Unexpected response", response.status_code)
        except Exception as e:
            self.log_test("List Vouchers", False, f"Exception: {str(e)}")
    
    def test_voucher_redemption_valid(self):
        """Test voucher redemption with valid code"""
        if not hasattr(self, 'test_vouchers') or not self.test_vouchers:
            self.log_test("Voucher Redemption (Valid)", False, "No test vouchers available")
            return False
        
        try:
            voucher_code = self.test_vouchers[0]['code']
            payload = {
                "voucher_code": voucher_code,
                "phone_number": self.test_phone
            }
            response = requests.post(f"{self.base_url}/vouchers/redeem/", json=payload)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    self.log_test("Voucher Redemption (Valid)", True, "Voucher redeemed successfully", response.status_code)
                    return True
                else:
                    self.log_test("Voucher Redemption (Valid)", False, data.get('message', 'Unknown error'), response.status_code)
            else:
                self.log_test("Voucher Redemption (Valid)", False, "Non-200 response", response.status_code)
        except Exception as e:
            self.log_test("Voucher Redemption (Valid)", False, f"Exception: {str(e)}")
        return False
    
    def test_verify_access_active_user(self):
        """Test verify access for user with active access"""
        try:
            payload = {
                "phone_number": self.test_phone,
                "ip_address": "192.168.1.100",
                "mac_address": "00:11:22:33:44:55"
            }
            response = requests.post(f"{self.base_url}/verify/", json=payload)
            
            if response.status_code == 200:
                data = response.json()
                access_granted = data.get('access_granted', False)
                if access_granted:
                    self.log_test("Verify Access (Active User)", True, "Access granted for active user", response.status_code)
                    return True
                else:
                    denial_reason = data.get('denial_reason', 'Unknown')
                    self.log_test("Verify Access (Active User)", False, f"Access denied: {denial_reason}", response.status_code)
            else:
                self.log_test("Verify Access (Active User)", False, "Non-200 response", response.status_code)
        except Exception as e:
            self.log_test("Verify Access (Active User)", False, f"Exception: {str(e)}")
        return False
    
    def run_all_tests(self, admin_user=None, admin_pass=None):
        """Run all tests in sequence"""
        print("🚀 Starting Kitonga API Test Suite...")
        print(f"📍 Base URL: {self.base_url}")
        print(f"📱 Test Phone: {self.test_phone}")
        print("-" * 60)
        
        # Basic API tests
        self.test_health_check()
        self.test_list_bundles()
        
        # User flow tests
        self.test_verify_access_new_user()
        self.test_user_status_new_user()
        self.test_initiate_payment()
        time.sleep(1)  # Brief pause
        self.test_payment_status()
        self.test_user_status_after_payment()
        self.test_list_user_devices()
        
        # Voucher tests
        self.test_voucher_redemption_invalid()
        
        # Admin tests (if credentials provided)
        if admin_user and admin_pass:
            print("\n🔐 Testing Admin Endpoints...")
            self.test_admin_endpoints(admin_user, admin_pass)
            self.test_voucher_redemption_valid()
            self.test_verify_access_active_user()
        else:
            print("\n⚠️  Skipping admin tests (no credentials provided)")
        
        # Summary
        print("\n" + "="*60)
        print("📊 TEST RESULTS SUMMARY")
        print("="*60)
        
        passed = sum(1 for result in self.test_results if result['success'])
        total = len(self.test_results)
        failed = total - passed
        
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"📈 Success Rate: {(passed/total)*100:.1f}%")
        
        if failed > 0:
            print("\n🔍 Failed Tests:")
            for result in self.test_results:
                if not result['success']:
                    print(f"   • {result['test']}: {result['message']}")
        
        return passed == total

def main():
    """Main test runner"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Kitonga API Test Suite')
    parser.add_argument('--url', default='http://localhost:8000/api', help='API base URL')
    parser.add_argument('--phone', default='255712345678', help='Test phone number')
    parser.add_argument('--admin-user', help='Admin username for admin tests')
    parser.add_argument('--admin-pass', help='Admin password for admin tests')
    
    args = parser.parse_args()
    
    tester = KitongaAPITester(args.url, args.phone)
    success = tester.run_all_tests(args.admin_user, args.admin_pass)
    
    # Export results
    with open('test_results.json', 'w') as f:
        json.dump(tester.test_results, f, indent=2)
    print(f"\n💾 Test results saved to test_results.json")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
```

### Bash Test Scripts

Save as `test_apis.sh`:

```bash
#!/bin/bash

# Kitonga API Testing Script
# Usage: ./test_apis.sh [BASE_URL]

BASE_URL=${1:-"http://localhost:8000/api"}
TEST_PHONE="255712345678"
RESULTS_FILE="test_results.txt"

echo "🧪 Kitonga API Test Suite"
echo "📍 Base URL: $BASE_URL"
echo "📱 Test Phone: $TEST_PHONE"
echo "----------------------------------------"

# Initialize results file
echo "Kitonga API Test Results - $(date)" > $RESULTS_FILE
echo "========================================" >> $RESULTS_FILE

# Test function
test_endpoint() {
    local name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    local expected_code="$5"
    
    echo -n "Testing $name... "
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "%{http_code}" -o response.tmp "$BASE_URL$endpoint")
    else
        response=$(curl -s -w "%{http_code}" -o response.tmp -X "$method" \
                   -H "Content-Type: application/json" \
                   -d "$data" "$BASE_URL$endpoint")
    fi
    
    http_code="${response: -3}"
    
    if [ "$http_code" = "$expected_code" ]; then
        echo "✅ PASS ($http_code)"
        echo "PASS - $name ($http_code)" >> $RESULTS_FILE
    else
        echo "❌ FAIL (Expected: $expected_code, Got: $http_code)"
        echo "FAIL - $name (Expected: $expected_code, Got: $http_code)" >> $RESULTS_FILE
        cat response.tmp >> $RESULTS_FILE
        echo "" >> $RESULTS_FILE
    fi
    
    rm -f response.tmp
}

# Run tests
echo "🏃 Running API Tests..."
echo ""

# Basic tests
test_endpoint "Health Check" "GET" "/health/" "" "200"
test_endpoint "List Bundles" "GET" "/bundles/" "" "200"

# User flow tests
test_endpoint "Verify Access (New User)" "POST" "/verify/" \
    '{"phone_number":"'$TEST_PHONE'","ip_address":"192.168.1.100","mac_address":"00:11:22:33:44:55"}' "404"

test_endpoint "User Status (New User)" "GET" "/user-status/$TEST_PHONE/" "" "404"

test_endpoint "Initiate Payment" "POST" "/initiate-payment/" \
    '{"phone_number":"'$TEST_PHONE'","bundle_id":1}' "200"

# Extract order reference for next test (simplified - in real scenario you'd parse JSON)
ORDER_REF="KITONGA1TESTREF"  # Placeholder
test_endpoint "Payment Status" "GET" "/payment-status/$ORDER_REF/" "" "200"

test_endpoint "User Status (After Payment)" "GET" "/user-status/$TEST_PHONE/" "" "200"

test_endpoint "List User Devices" "GET" "/devices/$TEST_PHONE/" "" "200"

test_endpoint "Invalid Voucher Redemption" "POST" "/vouchers/redeem/" \
    '{"voucher_code":"INVALID-CODE","phone_number":"'$TEST_PHONE'"}' "404"

echo ""
echo "📊 Test Results Summary:"
echo "----------------------------------------"
grep -c "PASS" $RESULTS_FILE | xargs echo "✅ Passed:"
grep -c "FAIL" $RESULTS_FILE | xargs echo "❌ Failed:"
echo ""
echo "📄 Detailed results saved to: $RESULTS_FILE"
```

## Postman Collection

### Import this JSON into Postman:

```json
{
  "info": {
    "name": "Kitonga Wi-Fi API",
    "description": "Complete API collection for Kitonga Wi-Fi Billing System",
    "version": "1.0.0"
  },
  "variable": [
    {
      "key": "base_url",
      "value": "http://localhost:8000/api"
    },
    {
      "key": "test_phone",
      "value": "255712345678"
    }
  ],
  "item": [
    {
      "name": "Health Check",
      "request": {
        "method": "GET",
        "header": [],
        "url": "{{base_url}}/health/"
      }
    },
    {
      "name": "List Bundles",
      "request": {
        "method": "GET",
        "header": [],
        "url": "{{base_url}}/bundles/"
      }
    },
    {
      "name": "Verify Access",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"phone_number\": \"{{test_phone}}\",\n  \"ip_address\": \"192.168.1.100\",\n  \"mac_address\": \"00:11:22:33:44:55\"\n}"
        },
        "url": "{{base_url}}/verify/"
      }
    },
    {
      "name": "Initiate Payment",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"phone_number\": \"{{test_phone}}\",\n  \"bundle_id\": 1\n}"
        },
        "url": "{{base_url}}/initiate-payment/"
      }
    },
    {
      "name": "Query Payment Status",
      "request": {
        "method": "GET",
        "header": [],
        "url": "{{base_url}}/payment-status/KITONGA1TESTREF/"
      }
    },
    {
      "name": "User Status",
      "request": {
        "method": "GET",
        "header": [],
        "url": "{{base_url}}/user-status/{{test_phone}}/"
      }
    },
    {
      "name": "List User Devices",
      "request": {
        "method": "GET",
        "header": [],
        "url": "{{base_url}}/devices/{{test_phone}}/"
      }
    },
    {
      "name": "Remove Device",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"phone_number\": \"{{test_phone}}\",\n  \"device_id\": 1\n}"
        },
        "url": "{{base_url}}/devices/remove/"
      }
    },
    {
      "name": "Redeem Voucher",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"voucher_code\": \"A1B2-C3D4-E5F6\",\n  \"phone_number\": \"{{test_phone}}\"\n}"
        },
        "url": "{{base_url}}/vouchers/redeem/"
      }
    },
    {
      "name": "Generate Vouchers (Admin)",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "auth": {
          "type": "basic",
          "basic": [
            {
              "key": "username",
              "value": "admin"
            },
            {
              "key": "password",
              "value": "admin"
            }
          ]
        },
        "body": {
          "mode": "raw",
          "raw": "{\n  \"quantity\": 10,\n  \"duration_hours\": 24,\n  \"batch_id\": \"TEST-BATCH-001\",\n  \"notes\": \"Test vouchers\"\n}"
        },
        "url": "{{base_url}}/vouchers/generate/"
      }
    },
    {
      "name": "List Vouchers (Admin)",
      "request": {
        "method": "GET",
        "header": [],
        "auth": {
          "type": "basic",
          "basic": [
            {
              "key": "username",
              "value": "admin"
            },
            {
              "key": "password",
              "value": "admin"
            }
          ]
        },
        "url": "{{base_url}}/vouchers/list/"
      }
    }
  ]
}
```

## Load Testing

### Using Apache Bench (ab)
```bash
# Install apache2-utils if not available
sudo apt-get install apache2-utils  # Ubuntu/Debian
brew install httpie                  # macOS

# Test health endpoint
ab -n 1000 -c 10 http://localhost:8000/api/health/

# Test bundles endpoint
ab -n 500 -c 5 http://localhost:8000/api/bundles/
```

### Using Python with concurrent requests
```python
import requests
import concurrent.futures
import time

def test_endpoint(url):
    start_time = time.time()
    try:
        response = requests.get(url, timeout=10)
        end_time = time.time()
        return {
            'success': response.status_code == 200,
            'time': end_time - start_time,
            'status_code': response.status_code
        }
    except Exception as e:
        return {
            'success': False,
            'time': time.time() - start_time,
            'error': str(e)
        }

def load_test(url, concurrent_requests=10, total_requests=100):
    print(f"Load testing {url}")
    print(f"Concurrent requests: {concurrent_requests}")
    print(f"Total requests: {total_requests}")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
        futures = [executor.submit(test_endpoint, url) for _ in range(total_requests)]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    
    successful = sum(1 for r in results if r['success'])
    avg_time = sum(r['time'] for r in results) / len(results)
    
    print(f"Success rate: {successful}/{total_requests} ({(successful/total_requests)*100:.1f}%)")
    print(f"Average response time: {avg_time:.3f}s")

# Run load tests
load_test("http://localhost:8000/api/health/")
load_test("http://localhost:8000/api/bundles/")
```

## Usage Instructions

1. **Run Python test suite**:
   ```bash
   python test_apis.py --admin-user admin --admin-pass your_password
   ```

2. **Run bash tests**:
   ```bash
   chmod +x test_apis.sh
   ./test_apis.sh http://localhost:8000/api
   ```

3. **Import Postman collection**:
   - Copy the JSON above
   - Open Postman → Import → Raw Text → Paste and Import

4. **Load testing**:
   - Use the Apache Bench commands for simple load testing
   - Run the Python concurrent testing script for detailed metrics

This comprehensive testing suite covers all API endpoints and provides multiple ways to verify your Kitonga Wi-Fi system is working correctly.
