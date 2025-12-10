# Kitonga WiFi API Complete Documentation

## Overview

The Kitonga WiFi Billing System provides a comprehensive API for managing WiFi access with automatic MikroTik integration. This system handles phone number normalization, payment processing, voucher redemption, and automatic internet connection/disconnection.

**Base URL:** `https://api.kitonga.klikcell.com/api`

## Phone Number Normalization System

The system automatically prevents duplicate users by normalizing all phone number formats:

- **Supported Formats:** `+255772236727`, `255772236727`, `0772236727`
- **Normalized Output:** `255772236727`
- **Duplicate Prevention:** Users with the same number in different formats are treated as one user

## Core Connection Flow

1. User connects to WiFi hotspot
2. System captures device info (MAC, IP)
3. User provides phone number for verification
4. System checks access status (payment/voucher)
5. **If valid:** MikroTik grants internet access
6. **If invalid:** User must pay or redeem voucher
7. **After payment/voucher:** Automatic internet connection

## API Endpoints

### 1. Verify Access (Core Endpoint)

**URL:** `POST /verify/`  
**Authentication:** None required  
**Description:** Checks user access and automatically connects/disconnects from MikroTik

#### Request Body
```json
{
  "phone_number": "string (any format: +255, 255, or 0 prefix)",
  "mac_address": "string (optional, for device tracking)",
  "ip_address": "string (optional, auto-detected if not provided)"
}
```

#### Response Examples

**Valid Access User:**
```json
{
  "access_granted": true,
  "denial_reason": "",
  "user": {
    "id": 123,
    "phone_number": "255772236727",
    "is_active": true,
    "paid_until": "2025-12-10T15:30:00Z",
    "max_devices": 1,
    "created_at": "2025-12-09T10:00:00Z"
  },
  "access_method": "payment",
  "device": {
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "registered": true,
    "is_active": true,
    "device_name": "iPhone-John"
  },
  "mikrotik_connection": {
    "action": "connected",
    "success": true,
    "message": "Successfully connected to internet"
  },
  "debug_info": {
    "has_payments": true,
    "has_vouchers": false,
    "paid_until": "2025-12-10T15:30:00Z",
    "is_active": true,
    "device_count": 1,
    "max_devices": 1
  }
}
```

**Expired Access User:**
```json
{
  "access_granted": false,
  "denial_reason": "Access expired 2 hours ago",
  "user": {
    "id": 124,
    "phone_number": "255787654321",
    "is_active": false,
    "paid_until": "2025-12-09T08:00:00Z",
    "max_devices": 1
  },
  "access_method": "voucher",
  "device": {
    "mac_address": "BB:CC:DD:EE:FF:11",
    "registered": true,
    "is_active": false,
    "device_name": null
  },
  "mikrotik_connection": {
    "action": "disconnected",
    "success": true,
    "message": "Disconnected from internet (no valid access)"
  }
}
```

**New User (No Access):**
```json
{
  "access_granted": false,
  "message": "User not found. Please register and pay to access Wi-Fi.",
  "suggestion": "Make a payment or redeem a voucher to create account and get access",
  "normalized_phone": "255798765432"
}
```

### 2. Initiate Payment

**URL:** `POST /initiate-payment/`  
**Authentication:** None required  
**Description:** Start ClickPesa USSD payment with automatic device registration

#### Request Body
```json
{
  "phone_number": "string (any format)",
  "bundle_id": "integer (optional, defaults to daily bundle)",
  "mac_address": "string (optional, for device tracking)",
  "ip_address": "string (optional, auto-detected)"
}
```

#### Response Examples

**Success:**
```json
{
  "success": true,
  "message": "Payment initiated successfully. Please complete USSD payment on your phone.",
  "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
  "order_reference": "KITONGA123ABC12345",
  "amount": 1000.0,
  "bundle": {
    "id": 1,
    "name": "Daily Access",
    "price": "1000.00",
    "duration_hours": 24,
    "description": "24 hours unlimited internet access"
  },
  "channel": "USSD_PUSH"
}
```

### 3. Redeem Voucher

**URL:** `POST /vouchers/redeem/`  
**Authentication:** None required  
**Description:** Redeem voucher code with automatic internet access

#### Request Body
```json
{
  "voucher_code": "string",
  "phone_number": "string (any format)",
  "mac_address": "string (optional, for immediate connection)",
  "ip_address": "string (optional, auto-detected)"
}
```

#### Response Examples

**Success:**
```json
{
  "success": true,
  "message": "Voucher redeemed successfully! You now have 24 hours of internet access.",
  "voucher": {
    "code": "H7SQ-V5XB-HOK2",
    "duration_hours": 24,
    "redeemed_at": "2025-12-09T14:30:00Z"
  },
  "user": {
    "phone_number": "255772236727",
    "access_until": "2025-12-10T14:30:00Z",
    "is_active": true
  },
  "device": {
    "mac_address": "CC:DD:EE:FF:11:22",
    "registered": true,
    "connected": true
  },
  "mikrotik_connection": {
    "action": "connected",
    "success": true,
    "message": "Automatically connected to internet"
  }
}
```

### 4. User Status

**URL:** `GET /user-status/{normalized_phone}/`  
**Authentication:** None required

#### Response Examples

**Active User:**
```json
{
  "has_active_access": true,
  "phone_number": "255772236727",
  "access_until": "2025-12-10T15:30:00Z",
  "time_remaining": {
    "hours": 23,
    "minutes": 45,
    "seconds": 30
  },
  "access_method": "payment",
  "devices": [
    {
      "mac_address": "AA:BB:CC:DD:EE:FF",
      "device_name": "iPhone-John",
      "is_active": true,
      "last_seen": "2025-12-09T14:25:00Z"
    }
  ]
}
```

### 5. Available Bundles

**URL:** `GET /bundles/`  
**Authentication:** None required

#### Response Example
```json
[
  {
    "id": 1,
    "name": "Hourly Access",
    "price": "500.00",
    "duration_hours": 1,
    "description": "1 hour unlimited internet access",
    "is_active": true
  },
  {
    "id": 2,
    "name": "Daily Access",
    "price": "1000.00",
    "duration_hours": 24,
    "description": "24 hours unlimited internet access",
    "is_active": true
  }
]
```

### 6. MikroTik Authentication

**URL:** `POST /mikrotik/auth/`  
**Description:** Used by MikroTik router for hotspot authentication

#### Request Body
```json
{
  "username": "string (normalized phone number)",
  "password": "string (last 6 digits of phone)"
}
```

#### Response Examples
- **Authorized:** `"OK"`
- **Denied:** `{"auth-state": 1, "error": "User not found or access expired"}`

## Automatic Systems

### Phone Normalization
- Converts all formats to `255XXXXXXXXX`
- Prevents duplicate users
- Works with `+255`, `255`, and `0` prefixes

### MikroTik Integration
- **Connection triggers:** Successful payment, voucher redemption, valid access verification
- **Disconnection triggers:** Access expiration, invalid access verification
- **Functions:** `grant_user_access()`, `revoke_user_access()`

### Device Tracking
- Automatic MAC address registration
- Device limit enforcement (1 per user by default)
- Device naming and identification

## Complete Flows

### Payment Flow
1. **User submits phone:** `/initiate-payment/` → Payment initiated, USSD sent
2. **User completes USSD:** External (ClickPesa) → Payment processed
3. **ClickPesa webhook:** `/clickpesa-webhook/` → Payment completed, access granted
4. **User verification:** `/verify/` → User connected to internet via MikroTik

### Voucher Flow
1. **Admin generates:** `/generate-vouchers/` → Voucher codes created and sent via SMS
2. **User redeems:** `/vouchers/redeem/` → Voucher validated, access granted, user connected
3. **Automatic connection:** Internal MikroTik integration → Immediate internet access

## Frontend Integration

### JavaScript Examples

#### Verify Access
```javascript
async function verifyAccess(phoneNumber, macAddress, ipAddress) {
  const response = await fetch('/api/verify/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      phone_number: phoneNumber, // Any format: +255, 255, or 0
      mac_address: macAddress,   // Optional but recommended
      ip_address: ipAddress      // Optional, auto-detected
    })
  });
  
  const data = await response.json();
  
  if (data.access_granted) {
    // User has access and is automatically connected
    showSuccessMessage('Connected to internet!');
    if (data.mikrotik_connection.success) {
      showConnectionStatus('Internet access granted');
    }
  } else {
    // Show payment or voucher options
    showAccessDeniedMessage(data.denial_reason);
    showPaymentOptions();
  }
  
  return data;
}
```

#### Initiate Payment
```javascript
async function initiatePayment(phoneNumber, bundleId, macAddress, ipAddress) {
  const response = await fetch('/api/initiate-payment/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      phone_number: phoneNumber,
      bundle_id: bundleId,
      mac_address: macAddress,
      ip_address: ipAddress
    })
  });
  
  const data = await response.json();
  
  if (data.success) {
    // Show USSD instructions
    showPaymentInstructions(data.message, data.order_reference);
    
    // Start polling for payment completion
    pollPaymentStatus(data.order_reference, phoneNumber, macAddress, ipAddress);
  } else {
    showErrorMessage(data.message);
  }
  
  return data;
}
```

#### Redeem Voucher
```javascript
async function redeemVoucher(voucherCode, phoneNumber, macAddress, ipAddress) {
  const response = await fetch('/api/vouchers/redeem/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      voucher_code: voucherCode,
      phone_number: phoneNumber,
      mac_address: macAddress,
      ip_address: ipAddress
    })
  });
  
  const data = await response.json();
  
  if (data.success) {
    showSuccessMessage(data.message);
    
    // Check if automatically connected
    if (data.mikrotik_connection && data.mikrotik_connection.success) {
      showConnectionStatus('Connected to internet!');
    } else {
      // Manually verify access
      verifyAccess(phoneNumber, macAddress, ipAddress);
    }
  } else {
    showErrorMessage(data.message);
  }
  
  return data;
}
```

#### Poll Payment Status
```javascript
function pollPaymentStatus(orderReference, phoneNumber, macAddress, ipAddress) {
  const pollInterval = setInterval(async () => {
    try {
      // Check access status for immediate response
      const accessData = await verifyAccess(phoneNumber, macAddress, ipAddress);
      
      if (accessData.access_granted) {
        clearInterval(pollInterval);
        showSuccessMessage('Payment completed! You are now connected to internet.');
      }
      
      // Stop polling after 5 minutes
      setTimeout(() => clearInterval(pollInterval), 300000);
    } catch (error) {
      console.error('Polling error:', error);
    }
  }, 10000); // Poll every 10 seconds
}
```

### Captive Portal Integration

1. **Capture device info:** MAC address and IP from user device
2. **Show phone input:** Accept any format (+255, 255, 0 prefix)
3. **Call verify_access:** If `access_granted=true`, show success. If false, show payment/voucher options
4. **For payment:** Call `initiate_payment`, user completes USSD on phone
5. **For voucher:** Call `redeem_voucher` with voucher code
6. **Poll verification:** Check `verify_access` every 5-10 seconds until `access_granted=true`

## Error Handling

### Common Errors

- **Invalid Phone (400):** "Invalid phone number: Must be a valid Tanzanian mobile number"
- **User Not Found (404):** "User not found. Please register and pay to access Wi-Fi."
- **Access Expired (200):** `access_granted: false`, `denial_reason: "Access expired X hours ago"`
- **Device Limit (200):** `denial_reason: "Device limit exceeded (1/1 devices active)"`

## Admin Endpoints

**Authentication:** `Authorization: Token <admin_token>`

- **Generate Vouchers:** `/generate-vouchers/`
- **List Users:** `/users/`
- **List Payments:** `/payments/`
- **MikroTik Management:** `/mikrotik/`
- **System Status:** `/system/status/`

## Testing

### Test Numbers
- **Payment Test:** `255000000000` (won't charge real money)
- **Existing User:** `255772236727`
- **Voucher Test:** Use generated test vouchers

### Test Vouchers
- **Generate:** Use admin panel to create test vouchers
- **Format:** `XXXX-XXXX-XXXX`
- **Example:** `H7SQ-V5XB-HOK2`

## Key Features

✅ **Phone Number Normalization** - Prevents duplicate users  
✅ **Automatic MikroTik Integration** - Seamless internet connection/disconnection  
✅ **Device Tracking** - MAC address management and limits  
✅ **Payment Integration** - ClickPesa USSD payments  
✅ **Voucher System** - Code-based access redemption  
✅ **Real-time Status** - Live access verification  
✅ **Comprehensive Logging** - Full audit trail  
✅ **Error Handling** - Detailed error messages and recovery
