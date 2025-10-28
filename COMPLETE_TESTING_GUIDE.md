# Kitonga WiFi Billing System - Complete Testing Guide

## Overview
This guide provides step-by-step testing procedures for the complete user journey in the Kitonga WiFi billing system, from router connection to payment and internet access.

## Test Environment Setup

### Prerequisites
- **MikroTik Router**: Configured with hotspot
- **Django Server**: Running on http://127.0.0.1:8000 or https://api.kitonga.klikcell.com
- **Test Phone Numbers**: Use Tanzania format (255XXXXXXXXX)
- **ClickPesa Account**: For payment testing (sandbox mode)

### Router Configuration
```
Router IP: 192.168.0.173
Hotspot Network: kitonga-hotspot  
Login Page: Custom redirect to billing system
API Port: 8728
```

## Complete User Flow Testing

### Step 1: User Connects to WiFi
**Scenario**: New user connects to "kitonga-hotspot" WiFi network

**Expected Behavior**:
1. User connects to WiFi
2. Router redirects to captive portal
3. User is redirected to billing system

**Test Commands**:
```bash
# Simulate user connecting (run on router or test device)
# User will be redirected to: https://api.kitonga.klikcell.com/api/verify/
```

### Step 2: Access Verification
**API Endpoint**: `GET /api/verify/`

**Test Cases**:

#### 2.1 New User (No Access)
```bash
curl -X POST http://127.0.0.1:8000/api/verify/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "255712345999",
    "mac_address": "AA:BB:CC:DD:EE:FF"
  }'
```

**Expected Response**:
```json
{
  "success": false,
  "has_access": false,
  "message": "No active internet package found",
  "user_created": true,
  "bundles": [
    {
      "id": 1,
      "name": "Daily Access",
      "price": "1000.00",
      "duration_hours": 24
    }
  ]
}
```

#### 2.2 Existing User with Active Access
```bash
curl -X POST http://127.0.0.1:8000/api/verify/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "255712345678",
    "mac_address": "AA:BB:CC:DD:EE:FF"
  }'
```

### Step 3: View Available Bundles
**API Endpoint**: `GET /api/bundles/`

```bash
curl -X GET http://127.0.0.1:8000/api/bundles/
```

**Expected Response**:
```json
{
  "success": true,
  "bundles": [
    {
      "id": 1,
      "name": "Daily Access",
      "description": "24 hours internet access",
      "price": "1000.00",
      "duration_hours": 24,
      "is_active": true
    },
    {
      "id": 2,
      "name": "Weekly Access", 
      "description": "7 days internet access",
      "price": "5000.00",
      "duration_hours": 168,
      "is_active": true
    }
  ]
}
```

### Step 4: Initiate Payment
**API Endpoint**: `POST /api/initiate-payment/`

#### 4.1 Valid Payment Request
```bash
curl -X POST http://127.0.0.1:8000/api/initiate-payment/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "255712345999",
    "bundle_id": 1,
    "amount": 1000
  }'
```

**Expected Response**:
```json
{
  "success": true,
  "message": "Payment initiated successfully",
  "payment_details": {
    "order_reference": "KITONGA1ABC12345",
    "amount": "1000.00",
    "bundle_name": "Daily Access",
    "payment_url": "https://api.clickpesa.com/checkout/...",
    "expires_in": 900
  }
}
```

#### 4.2 Invalid Bundle ID
```bash
curl -X POST http://127.0.0.1:8000/api/initiate-payment/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "255712345999",
    "bundle_id": 999,
    "amount": 1000
  }'
```

### Step 5: Check Payment Status
**API Endpoint**: `GET /api/payment-status/{order_reference}/`

```bash
curl -X GET http://127.0.0.1:8000/api/payment-status/KITONGA1ABC12345/
```

**Expected Responses**:

**Pending Payment**:
```json
{
  "success": true,
  "payment_status": "pending",
  "message": "Payment is still being processed",
  "order_reference": "KITONGA1ABC12345"
}
```

**Completed Payment**:
```json
{
  "success": true,
  "payment_status": "completed",
  "message": "Payment completed successfully",
  "access_granted": true,
  "expires_at": "2025-10-29T12:00:00Z"
}
```

### Step 6: Simulate ClickPesa Webhook
**API Endpoint**: `POST /api/clickpesa-webhook/`

```bash
curl -X POST http://127.0.0.1:8000/api/clickpesa-webhook/ \
  -H "Content-Type: application/json" \
  -d '{
    "order_reference": "KITONGA1ABC12345",
    "transaction_reference": "CLPLCPCA6KYH4",
    "amount": 1000,
    "status": "PAYMENT RECEIVED",
    "phone_number": "255712345999",
    "channel": "TIGO-PESA"
  }'
```

### Step 7: Verify Access After Payment
```bash
curl -X POST http://127.0.0.1:8000/api/verify/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "255712345999",
    "mac_address": "AA:BB:CC:DD:EE:FF"
  }'
```

**Expected Response** (Access Granted):
```json
{
  "success": true,
  "has_access": true,
  "message": "Internet access granted",
  "expires_at": "2025-10-29T12:00:00Z",
  "time_remaining": "23:45:30"
}
```

### Step 8: Check User Status
**API Endpoint**: `GET /api/user-status/{phone_number}/`

```bash
curl -X GET http://127.0.0.1:8000/api/user-status/255712345999/
```

**Expected Response**:
```json
{
  "success": true,
  "user": {
    "phone_number": "255712345999",
    "is_active": true,
    "has_active_access": true,
    "paid_until": "2025-10-29T12:00:00Z",
    "time_remaining": "23:45:30",
    "device_count": 1,
    "max_devices": 1
  }
}
```

### Step 9: Device Management
**API Endpoint**: `GET /api/devices/{phone_number}/`

```bash
curl -X GET http://127.0.0.1:8000/api/devices/255712345999/
```

**Expected Response**:
```json
{
  "success": true,
  "devices": [
    {
      "id": 1,
      "mac_address": "AA:BB:CC:DD:EE:FF",
      "device_name": "Unknown Device",
      "first_connected": "2025-10-28T12:00:00Z",
      "last_active": "2025-10-28T12:00:00Z",
      "is_active": true
    }
  ],
  "device_count": 1,
  "max_devices": 1,
  "can_add_device": false
}
```

## MikroTik Integration Testing

### Test Router Connection
```bash
curl -X POST http://127.0.0.1:8000/api/admin/mikrotik/test-connection/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "X-Admin-Access: kitonga_admin_2025" \
  -H "Content-Type: application/json" \
  -d '{
    "router_ip": "192.168.0.173",
    "username": "admin", 
    "password": "router_password"
  }'
```

### Check Active Users on Router
```bash
curl -X GET http://127.0.0.1:8000/api/admin/mikrotik/active-users/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "X-Admin-Access: kitonga_admin_2025"
```

### Force User Logout
```bash
curl -X POST http://127.0.0.1:8000/api/force-logout/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "255712345999",
    "reason": "Testing logout"
  }'
```

## Error Testing Scenarios

### 1. Device Limit Exceeded
```bash
# Try to connect second device for same user
curl -X POST http://127.0.0.1:8000/api/verify/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "255712345999",
    "mac_address": "BB:CC:DD:EE:FF:AA"
  }'
```

**Expected Response**:
```json
{
  "success": false,
  "has_access": false,
  "message": "Device limit reached (1 devices max)",
  "device_limit_exceeded": true
}
```

### 2. Expired Access
```bash
# Test with user whose access has expired
curl -X POST http://127.0.0.1:8000/api/verify/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "255712345678",
    "mac_address": "CC:DD:EE:FF:AA:BB"
  }'
```

### 3. Invalid Payment Amount
```bash
curl -X POST http://127.0.0.1:8000/api/initiate-payment/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "255712345999",
    "bundle_id": 1,
    "amount": 500
  }'
```

**Expected Response**:
```json
{
  "success": false,
  "message": "Amount mismatch. Expected 1000.00 for Daily Access"
}
```

## Performance Testing

### Load Testing with Multiple Users
```bash
# Test concurrent payment requests
for i in {1..10}; do
  curl -X POST http://127.0.0.1:8000/api/initiate-payment/ \
    -H "Content-Type: application/json" \
    -d "{
      \"phone_number\": \"25571234500$i\",
      \"bundle_id\": 1,
      \"amount\": 1000
    }" &
done
wait
```

## Frontend Integration Testing

### JavaScript Test Script
```javascript
const API_BASE = 'http://127.0.0.1:8000/api/';

// Test complete user flow
async function testUserFlow() {
  const phoneNumber = '255712345999';
  const macAddress = 'AA:BB:CC:DD:EE:FF';
  
  try {
    // 1. Check access
    const accessCheck = await fetch(`${API_BASE}verify/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone_number: phoneNumber,
        mac_address: macAddress
      })
    });
    
    console.log('Access Check:', await accessCheck.json());
    
    // 2. Get bundles
    const bundles = await fetch(`${API_BASE}bundles/`);
    console.log('Bundles:', await bundles.json());
    
    // 3. Initiate payment
    const payment = await fetch(`${API_BASE}initiate-payment/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone_number: phoneNumber,
        bundle_id: 1,
        amount: 1000
      })
    });
    
    console.log('Payment:', await payment.json());
    
  } catch (error) {
    console.error('Test failed:', error);
  }
}

// Run the test
testUserFlow();
```

## Expected User Journey

### New User Flow:
1. **Connect to WiFi** → Redirect to captive portal
2. **Access Check** → "No access found, please purchase a bundle"
3. **View Bundles** → Display available packages
4. **Select Bundle** → Choose and proceed to payment
5. **Make Payment** → ClickPesa integration
6. **Payment Completion** → Webhook processes payment
7. **Access Granted** → User gets internet access
8. **Monitor Usage** → Track time and device limits

### Returning User Flow:
1. **Connect to WiFi** → Automatic access check
2. **If Access Valid** → Immediate internet access
3. **If Access Expired** → Show renewal options
4. **Device Management** → Handle multiple device scenarios

## Monitoring and Logs

### Check System Health
```bash
curl -X GET http://127.0.0.1:8000/api/health/
```

### View Dashboard Stats
```bash
curl -X GET http://127.0.0.1:8000/api/dashboard-stats/ \
  -H "Authorization: Token YOUR_TOKEN"
```

### Admin User Management
```bash
curl -X GET http://127.0.0.1:8000/api/admin/users/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "X-Admin-Access: kitonga_admin_2025"
```

## Troubleshooting

### Common Issues:
1. **Payment Not Processing**: Check ClickPesa webhook configuration
2. **Router Not Connecting**: Verify MikroTik API settings
3. **Device Limit Issues**: Check max_devices configuration
4. **Access Not Granted**: Verify payment completion and user status

### Debug Commands:
```bash
# Check user in database
python manage.py shell -c "from billing.models import User; print(User.objects.get(phone_number='255712345999'))"

# Check payments
python manage.py shell -c "from billing.models import Payment; print(Payment.objects.filter(phone_number='255712345999'))"

# Check devices
python manage.py shell -c "from billing.models import Device; print(Device.objects.filter(user__phone_number='255712345999'))"
```

---

This comprehensive testing guide covers the complete WiFi billing system flow from connection to payment and access management. Use these tests to validate the entire user journey and system functionality.
