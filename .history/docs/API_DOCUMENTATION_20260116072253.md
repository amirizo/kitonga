# Kitonga API Documentation

## Base URL
\`\`\`
http://localhost:8000/api/
\`\`\`

## Endpoints

### 1. Verify Access
Check if a user has valid Wi-Fi access.

**Endpoint:** `POST /api/verify/`

**Request Body:**
\`\`\`json
{
  "phone_number": "254712345678",
  "ip_address": "192.168.1.100",
  "mac_address": "00:11:22:33:44:55"
}
\`\`\`

**Response (Access Granted):**
\`\`\`json
{
  "access_granted": true,
  "user": {
    "id": 1,
    "phone_number": "254712345678",
    "paid_until": "2025-01-12T14:30:00Z",
    "is_active": true,
    "has_active_access": true,
    "time_remaining": {
      "hours": 18,
      "minutes": 45
    },
    "total_payments": 5,
    "created_at": "2025-01-01T10:00:00Z"
  }
}
\`\`\`

**Response (Access Denied):**
\`\`\`json
{
  "access_granted": false,
  "message": "User not found. Please register and pay to access Wi-Fi."
}
\`\`\`

---

### 2. Initiate Payment
Start mobile money USSD-PUSH payment process (M-Pesa, Tigo Pesa, Airtel Money, Halopesa).

**Endpoint:** `POST /api/initiate-payment/`

**Request Body:**
\`\`\`json
{
  "phone_number": "255712345678",
  "bundle_id": 1,
  "router_id": 5,
  "mac_address": "AA:BB:CC:DD:EE:FF",
  "ip_address": "192.168.88.100"
}
\`\`\`

| Parameter | Required | Description |
|-----------|----------|-------------|
| phone_number | Yes | User's phone number (will be normalized to +255 format) |
| bundle_id | No | Bundle ID to purchase. If not provided, uses default daily bundle |
| router_id | **Recommended** | Router ID where user is connected. **Critical for multi-tenant SaaS** - ensures hotspot user is created on correct router |
| mac_address | No | User's device MAC address (for IP binding bypass) |
| ip_address | No | User's current IP address |

**Response (Success):**
\`\`\`json
{
  "success": true,
  "message": "Payment initiated. Please check your phone for USSD prompt.",
  "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
  "order_reference": "KITONGA12ABC123",
  "amount": 1000,
  "bundle": {
    "id": 1,
    "name": "Daily Bundle",
    "price": 1000,
    "duration_hours": 24
  },
  "channel": "vodacom"
}
\`\`\`

**Response (Error):**
\`\`\`json
{
  "success": false,
  "message": "Failed to initiate payment"
}
\`\`\`

**Important:** When calling from captive portal frontend, always include `router_id` from URL parameters. This ensures the user gets connected to the correct router after payment.

---

### 3. M-Pesa Callback
Receives payment confirmation from Safaricom (internal use).

**Endpoint:** `POST /api/mpesa-callback/`

**Note:** This endpoint is called by M-Pesa servers, not by clients.

---

### 4. Get User Status
Retrieve user information and access status.

**Endpoint:** `GET /api/user-status/<phone_number>/`

**Example:** `GET /api/user-status/254712345678/`

**Response:**
\`\`\`json
{
  "id": 1,
  "phone_number": "254712345678",
  "paid_until": "2025-01-12T14:30:00Z",
  "is_active": true,
  "has_active_access": true,
  "time_remaining": {
    "hours": 18,
    "minutes": 45
  },
  "total_payments": 5,
  "created_at": "2025-01-01T10:00:00Z"
}
\`\`\`

---

### 5. Query Payment Status
Check the current status of a payment transaction.

**Endpoint:** `GET /api/payment-status/<order_reference>/`

**Example:** `GET /api/payment-status/KITONGA123ABC12345/`

**Response (Success):**
\`\`\`json
{
  "success": true,
  "payment": {
    "id": 1,
    "amount": "1000.00",
    "phone_number": "255712345678",
    "status": "completed",
    "order_reference": "KITONGA123ABC12345",
    "created_at": "2025-01-12T10:30:00Z",
    "completed_at": "2025-01-12T10:31:00Z"
  },
  "clickpesa_status": {
    "id": "cp_transaction_123",
    "orderReference": "KITONGA123ABC12345", 
    "status": "COMPLETED",
    "amount": "1000",
    "currency": "TZS",
    "channel": "M-PESA"
  }
}
\`\`\`

**Response (Payment Not Found):**
\`\`\`json
{
  "success": false,
  "message": "Payment not found"
}
\`\`\`

---

## Error Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 400 | Bad Request (invalid data) |
| 404 | Not Found (user doesn't exist) |
| 500 | Internal Server Error |

---

## Phone Number Format

Phone numbers should be in one of these formats:
- `254712345678` (preferred)
- `0712345678` (will be converted)
- `712345678` (will be converted)

The API automatically formats phone numbers to the standard format.

---

## Access Control Flow

1. **User connects to Wi-Fi** → Captive portal appears
2. **User enters phone number** → System checks access status
3. **If no access** → Initiate payment via M-Pesa STK Push
4. **User enters M-Pesa PIN** → Payment processed
5. **Payment confirmed** → Access granted for 24 hours
6. **After 24 hours** → Access automatically expires

---

## Testing

Use the following test credentials in sandbox mode:

**Test Phone Number:** `254708374149`
**Test M-Pesa PIN:** `1234`

---

## API Testing Guide

This section provides detailed instructions for testing all API endpoints using various tools and methods.

### Prerequisites

1. **API Base URL**: `http://localhost:8000/api/` (development) or your production URL
2. **Test Phone Number**: Use `255712345678` for testing
3. **Admin Authentication**: Required for some endpoints (create admin user first)

### Testing Tools

You can test the APIs using:
- **cURL** (command line)
- **Postman** (GUI)
- **HTTPie** (command line)
- **Python requests** (scripts)
- **Browser** (for GET endpoints)

---

### 1. Test Verify Access

**Purpose**: Check if a user has valid Wi-Fi access

**cURL Example**:
```bash
curl -X POST http://localhost:8000/api/verify/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "255712345678",
    "ip_address": "192.168.1.100",
    "mac_address": "00:11:22:33:44:55"
  }'
```

**Expected Response** (New User):
```json
{
  "access_granted": false,
  "message": "User not found. Please register and pay to access Wi-Fi."
}
```

**Python Test Script**:
```python
import requests

response = requests.post('http://localhost:8000/api/verify/', json={
    "phone_number": "255712345678",
    "ip_address": "192.168.1.100",
    "mac_address": "00:11:22:33:44:55"
})
print(response.status_code, response.json())
```

---

### 2. Test Initiate Payment

**Purpose**: Start a payment process for Wi-Fi access

**cURL Example**:
```bash
curl -X POST http://localhost:8000/api/initiate-payment/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "255712345678",
    "bundle_id": 1
  }'
```

**Expected Response** (Success):
```json
{
  "success": true,
  "message": "Payment request sent to your phone",
  "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
  "order_reference": "KITONGA1A1B2C3D4",
  "amount": 1000.0,
  "bundle": {
    "id": 1,
    "name": "Daily Access",
    "price": "1000.00",
    "duration_hours": 24
  }
}
```

**Test Cases**:
1. Valid phone number with bundle
2. Valid phone number without bundle (uses default)
3. Invalid bundle ID
4. Invalid phone number format

---

### 3. Test Payment Status Query

**Purpose**: Check the status of a payment

**cURL Example**:
```bash
curl -X GET http://localhost:8000/api/payment-status/KITONGA1A1B2C3D4/
```

**Expected Response**:
```json
{
  "success": true,
  "payment": {
    "id": 1,
    "amount": "1000.00",
    "phone_number": "255712345678",
    "status": "pending",
    "order_reference": "KITONGA1A1B2C3D4",
    "created_at": "2025-01-12T10:30:00Z"
  },
  "clickpesa_status": {
    "status": "PENDING",
    "amount": "1000",
    "currency": "TZS"
  }
}
```

---

### 4. Test User Status

**Purpose**: Get user information and access status

**cURL Example**:
```bash
curl -X GET http://localhost:8000/api/user-status/255712345678/
```

**Expected Response** (Active User):
```json
{
  "id": 1,
  "phone_number": "255712345678",
  "paid_until": "2025-01-13T10:30:00Z",
  "is_active": true,
  "has_active_access": true,
  "time_remaining": {
    "hours": 18,
    "minutes": 45
  },
  "total_payments": 1,
  "created_at": "2025-01-12T10:30:00Z"
}
```

---

### 5. Test List Bundles

**Purpose**: Get available package options

**cURL Example**:
```bash
curl -X GET http://localhost:8000/api/bundles/
```

**Expected Response**:
```json
{
  "success": true,
  "bundles": [
    {
      "id": 1,
      "name": "Daily Access",
      "description": "24-hour Wi-Fi access",
      "price": "1000.00",
      "duration_hours": 24,
      "is_active": true
    },
    {
      "id": 2,
      "name": "Weekly Access",
      "description": "7-day Wi-Fi access",
      "price": "5000.00",
      "duration_hours": 168,
      "is_active": true
    }
  ]
}
```

---

### 6. Test Voucher Redemption

**Purpose**: Redeem a voucher code for access

**cURL Example**:
```bash
curl -X POST http://localhost:8000/api/vouchers/redeem/ \
  -H "Content-Type: application/json" \
  -d '{
    "voucher_code": "A1B2-C3D4-E5F6",
    "phone_number": "255712345678"
  }'
```

**Expected Response** (Success):
```json
{
  "success": true,
  "message": "Voucher redeemed successfully. Access granted for 24 hours.",
  "user": {
    "phone_number": "255712345678",
    "paid_until": "2025-01-13T10:30:00Z",
    "is_active": true
  }
}
```

---

### 7. Test Device Management

#### List User Devices

**cURL Example**:
```bash
curl -X GET http://localhost:8000/api/devices/255712345678/
```

#### Remove Device

**cURL Example**:
```bash
curl -X POST http://localhost:8000/api/devices/remove/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "255712345678",
    "device_id": 1
  }'
```

---

### 8. Test Admin Endpoints

**Note**: These require admin authentication. First create an admin user:

```bash
python manage.py createsuperuser
```

#### Generate Vouchers

**cURL Example** (with authentication):
```bash
curl -X POST http://localhost:8000/api/vouchers/generate/ \
  -H "Content-Type: application/json" \
  -u "admin:password" \
  -d '{
    "quantity": 10,
    "duration_hours": 24,
    "batch_id": "TEST-BATCH-001",
    "notes": "Test vouchers"
  }'
```

#### List Vouchers

**cURL Example**:
```bash
curl -X GET http://localhost:8000/api/vouchers/list/ \
  -u "admin:password"
```

---

### 9. Test Health Check

**Purpose**: Verify API is running

**cURL Example**:
```bash
curl -X GET http://localhost:8000/api/health/
```

**Expected Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-01-12T10:30:00Z",
  "service": "Kitonga Wi-Fi Billing System"
}
```

---

### Complete Test Script

Here's a Python script to test all endpoints:

```python
import requests
import time

BASE_URL = "http://localhost:8000/api"
TEST_PHONE = "255712345678"

def test_all_apis():
    print("🧪 Testing Kitonga APIs...")
    
    # 1. Test Health Check
    print("\n1. Testing Health Check...")
    response = requests.get(f"{BASE_URL}/health/")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # 2. Test Bundles
    print("\n2. Testing List Bundles...")
    response = requests.get(f"{BASE_URL}/bundles/")
    print(f"Status: {response.status_code}")
    bundles = response.json()
    print(f"Found {len(bundles.get('bundles', []))} bundles")
    
    # 3. Test Verify Access (should fail - new user)
    print("\n3. Testing Verify Access...")
    response = requests.post(f"{BASE_URL}/verify/", json={
        "phone_number": TEST_PHONE,
        "ip_address": "192.168.1.100",
        "mac_address": "00:11:22:33:44:55"
    })
    print(f"Status: {response.status_code}")
    print(f"Access Granted: {response.json().get('access_granted', False)}")
    
    # 4. Test User Status (should fail - new user)
    print("\n4. Testing User Status...")
    response = requests.get(f"{BASE_URL}/user-status/{TEST_PHONE}/")
    print(f"Status: {response.status_code}")
    
    # 5. Test Payment Initiation
    print("\n5. Testing Payment Initiation...")
    bundle_id = bundles['bundles'][0]['id'] if bundles.get('bundles') else None
    response = requests.post(f"{BASE_URL}/initiate-payment/", json={
        "phone_number": TEST_PHONE,
        "bundle_id": bundle_id
    })
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        payment_data = response.json()
        order_reference = payment_data.get('order_reference')
        print(f"Order Reference: {order_reference}")
        
        # 6. Test Payment Status
        print("\n6. Testing Payment Status...")
        time.sleep(2)  # Wait a bit
        response = requests.get(f"{BASE_URL}/payment-status/{order_reference}/")
        print(f"Status: {response.status_code}")
        print(f"Payment Status: {response.json().get('payment', {}).get('status')}")
    
    # 7. Test Voucher Redemption (will fail - invalid code)
    print("\n7. Testing Voucher Redemption...")
    response = requests.post(f"{BASE_URL}/vouchers/redeem/", json={
        "voucher_code": "TEST-TEST-TEST",
        "phone_number": TEST_PHONE
    })
    print(f"Status: {response.status_code}")
    print(f"Message: {response.json().get('message')}")
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    test_all_apis()
```

---

### Testing Checklist

#### Pre-Testing Setup
- [ ] Django server is running (`python manage.py runserver`)
- [ ] Database is migrated (`python manage.py migrate`)
- [ ] Admin user created (`python manage.py createsuperuser`)
- [ ] Bundles are created in admin panel
- [ ] Environment variables are set (ClickPesa, NEXTSMS)

#### Basic API Tests
- [ ] Health check returns 200
- [ ] Bundles list returns active bundles
- [ ] Verify access handles new user (404)
- [ ] User status handles new user (404)
- [ ] Payment initiation creates payment record
- [ ] Payment status query works

#### Payment Flow Tests
- [ ] Initiate payment with valid phone number
- [ ] Payment record created in database
- [ ] Order reference is alphanumeric only
- [ ] ClickPesa integration (if credentials available)
- [ ] Payment status polling works

#### Voucher Tests
- [ ] Generate vouchers (admin only)
- [ ] List vouchers (admin only)
- [ ] Redeem valid voucher
- [ ] Reject invalid voucher
- [ ] Reject already used voucher

#### Device Management Tests
- [ ] List user devices
- [ ] Add device via verify access
- [ ] Remove device
- [ ] Device limit enforcement

#### Error Handling Tests
- [ ] Invalid phone number formats
- [ ] Missing required fields
- [ ] Non-existent resources (404)
- [ ] Unauthorized access (401/403)
- [ ] Malformed JSON requests

#### Load Testing (Optional)
```bash
# Using Apache Bench
ab -n 100 -c 10 http://localhost:8000/api/health/

# Using curl with multiple requests
for i in {1..10}; do
  curl -X GET http://localhost:8000/api/bundles/ &
done
wait
```

---

## Rate Limiting

Currently no rate limiting is implemented. Consider adding rate limiting in production to prevent abuse.

---

## Security Notes

1. Always use HTTPS in production
2. Validate all phone numbers
3. Log all access attempts
4. Monitor for suspicious activity
5. Implement rate limiting
6. Secure M-Pesa credentials
