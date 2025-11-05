# Kitonga WiFi Billing System - Verify Access API Documentation

## API Endpoint: `POST /api/verify/`

This endpoint verifies if a user has valid WiFi access. It works for both payment and voucher users.

### Request Structure

**Method:** `POST`
**URL:** `http://your-domain.com/api/verify/`
**Content-Type:** `application/json`

#### Request Body (JSON):
```json
{
  "phone_number": "255772236727",
  "ip_address": "192.168.0.100",
  "mac_address": "AA:BB:CC:DD:EE:FF"
}
```

#### Required Fields:
- `phone_number` (string): User's phone number
- `ip_address` (string, optional): User's IP address 
- `mac_address` (string, optional): Device MAC address

---

## Response Examples

### 1. ✅ SUCCESS - User Has Active Access

```json
{
  "access_granted": true,
  "denial_reason": "",
  "user": {
    "id": 1,
    "phone_number": "255772236727",
    "created_at": "2025-11-01T10:00:00Z",
    "is_active": true,
    "paid_until": "2025-11-06T14:30:00Z",
    "max_devices": 1,
    "has_active_access": true,
    "time_remaining": {
      "hours": 18,
      "minutes": 45,
      "seconds": 30
    }
  },
  "access_method": "payment",
  "debug_info": {
    "has_payments": true,
    "has_vouchers": false,
    "paid_until": "2025-11-06T14:30:00Z",
    "is_active": true,
    "device_count": 1,
    "max_devices": 1
  }
}
```

### 2. ✅ SUCCESS - Voucher User Has Active Access

```json
{
  "access_granted": true,
  "denial_reason": "",
  "user": {
    "id": 2,
    "phone_number": "255987654321",
    "created_at": "2025-11-02T09:00:00Z",
    "is_active": true,
    "paid_until": "2025-11-06T12:00:00Z",
    "max_devices": 1,
    "has_active_access": true,
    "time_remaining": {
      "hours": 16,
      "minutes": 15,
      "seconds": 45
    }
  },
  "access_method": "voucher",
  "debug_info": {
    "has_payments": false,
    "has_vouchers": true,
    "paid_until": "2025-11-06T12:00:00Z",
    "is_active": true,
    "device_count": 1,
    "max_devices": 1
  }
}
```

### 3. ❌ ACCESS DENIED - Expired Access

```json
{
  "access_granted": false,
  "denial_reason": "Access expired 5 hours ago - payment or voucher required",
  "user": {
    "id": 3,
    "phone_number": "255123456789",
    "created_at": "2025-11-01T08:00:00Z",
    "is_active": false,
    "paid_until": "2025-11-04T18:00:00Z",
    "max_devices": 1,
    "has_active_access": false,
    "time_remaining": {
      "hours": 0,
      "minutes": 0,
      "seconds": 0
    }
  },
  "access_method": "payment",
  "debug_info": {
    "has_payments": true,
    "has_vouchers": false,
    "paid_until": "2025-11-04T18:00:00Z",
    "is_active": false,
    "device_count": 0,
    "max_devices": 1
  }
}
```

### 4. ❌ ACCESS DENIED - Device Limit Exceeded

```json
{
  "access_granted": false,
  "denial_reason": "Device limit reached (1 devices max)",
  "user": {
    "id": 4,
    "phone_number": "255444555666",
    "created_at": "2025-11-01T12:00:00Z",
    "is_active": true,
    "paid_until": "2025-11-07T12:00:00Z",
    "max_devices": 1,
    "has_active_access": true,
    "time_remaining": {
      "hours": 25,
      "minutes": 30,
      "seconds": 15
    }
  },
  "access_method": "payment_and_voucher",
  "debug_info": {
    "has_payments": true,
    "has_vouchers": true,
    "paid_until": "2025-11-07T12:00:00Z",
    "is_active": true,
    "device_count": 2,
    "max_devices": 1
  }
}
```

### 5. ❌ USER NOT FOUND

```json
{
  "access_granted": false,
  "message": "User not found. Please register and pay to access Wi-Fi.",
  "suggestion": "Make a payment or redeem a voucher to create account and get access"
}
```

---

## Frontend Implementation Examples

### JavaScript/Fetch Example:

```javascript
async function verifyUserAccess(phoneNumber, macAddress, ipAddress) {
    const apiUrl = 'http://your-domain.com/api/verify/';
    
    const requestData = {
        phone_number: phoneNumber,
        mac_address: macAddress,
        ip_address: ipAddress
    };
    
    try {
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            if (result.access_granted) {
                console.log('✅ Access granted!');
                console.log('Access method:', result.access_method);
                console.log('Time remaining:', result.user.time_remaining);
                return {
                    success: true,
                    hasAccess: true,
                    user: result.user,
                    accessMethod: result.access_method
                };
            } else {
                console.log('❌ Access denied:', result.denial_reason);
                return {
                    success: true,
                    hasAccess: false,
                    reason: result.denial_reason,
                    user: result.user
                };
            }
        } else if (response.status === 404) {
            console.log('❌ User not found');
            return {
                success: true,
                hasAccess: false,
                reason: result.message,
                userNotFound: true
            };
        } else {
            throw new Error(`HTTP ${response.status}: ${result.message || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('❌ API request failed:', error);
        return {
            success: false,
            error: error.message
        };
    }
}

// Usage example:
verifyUserAccess('255772236727', 'AA:BB:CC:DD:EE:FF', '192.168.0.100')
    .then(result => {
        if (result.success && result.hasAccess) {
            // User has access - allow internet
            showSuccessMessage('Internet access granted!');
            displayUserInfo(result.user);
        } else if (result.success && !result.hasAccess) {
            // User denied - show reason
            showErrorMessage(result.reason);
            if (result.userNotFound) {
                redirectToPayment();
            }
        } else {
            // API error
            showErrorMessage('Connection failed. Please try again.');
        }
    });
```

### React Hook Example:

```javascript
import { useState, useEffect } from 'react';

function useUserAccess(phoneNumber, macAddress, ipAddress) {
    const [accessData, setAccessData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    
    const checkAccess = async () => {
        if (!phoneNumber) return;
        
        setLoading(true);
        setError(null);
        
        try {
            const result = await verifyUserAccess(phoneNumber, macAddress, ipAddress);
            setAccessData(result);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };
    
    useEffect(() => {
        checkAccess();
    }, [phoneNumber, macAddress, ipAddress]);
    
    return {
        accessData,
        loading,
        error,
        refetch: checkAccess
    };
}

// Usage in React component:
function WiFiAccessChecker() {
    const { accessData, loading, error } = useUserAccess(
        '255772236727',
        'AA:BB:CC:DD:EE:FF',
        '192.168.0.100'
    );
    
    if (loading) return <div>Checking access...</div>;
    if (error) return <div>Error: {error}</div>;
    if (!accessData) return <div>No data</div>;
    
    return (
        <div>
            {accessData.hasAccess ? (
                <div className="access-granted">
                    <h2>✅ Internet Access Granted</h2>
                    <p>Method: {accessData.accessMethod}</p>
                    <p>Time remaining: {accessData.user.time_remaining.hours}h {accessData.user.time_remaining.minutes}m</p>
                </div>
            ) : (
                <div className="access-denied">
                    <h2>❌ Access Denied</h2>
                    <p>{accessData.reason}</p>
                    {accessData.userNotFound && (
                        <button onClick={() => window.location.href = '/payment'}>
                            Make Payment
                        </button>
                    )}
                </div>
            )}
        </div>
    );
}
```

### cURL Example for Testing:

```bash
# Test with existing user
curl -X POST http://127.0.0.1:8000/api/verify/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "255772236727",
    "ip_address": "192.168.0.100",
    "mac_address": "AA:BB:CC:DD:EE:FF"
  }'

# Test with non-existent user
curl -X POST http://127.0.0.1:8000/api/verify/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "255999888777",
    "ip_address": "192.168.0.101",
    "mac_address": "BB:CC:DD:EE:FF:AA"
  }'
```

---

## Response Field Descriptions

### Main Response Fields:
- `access_granted` (boolean): Whether user has valid access
- `denial_reason` (string): Reason for denial if access_granted is false
- `user` (object): User information (if user exists)
- `access_method` (string): How user gained access (payment/voucher/payment_and_voucher/manual)
- `debug_info` (object): Technical details for debugging

### User Object Fields:
- `id` (integer): User's database ID
- `phone_number` (string): User's phone number
- `created_at` (datetime): When user account was created
- `is_active` (boolean): Whether user account is active
- `paid_until` (datetime): When access expires
- `max_devices` (integer): Maximum devices allowed
- `has_active_access` (boolean): Whether user currently has access
- `time_remaining` (object): Hours, minutes, seconds remaining

### Access Method Values:
- `"payment"`: User gained access through payment
- `"voucher"`: User gained access through voucher redemption
- `"payment_and_voucher"`: User has both payment and voucher history
- `"manual"`: Access manually granted by admin
- `"unknown"`: Could not determine access method

---

## Status Codes

- `200 OK`: Request successful (check `access_granted` field)
- `400 Bad Request`: Invalid request data
- `404 Not Found`: User not found
- `500 Internal Server Error`: Server error

---

## Best Practices

1. **Always check `access_granted` field** - don't rely on HTTP status code alone
2. **Handle both existing and non-existent users** - 404 means user needs to pay/redeem voucher
3. **Display meaningful error messages** - use `denial_reason` for user feedback
4. **Cache results briefly** - avoid excessive API calls
5. **Include MAC address** - for device tracking and limits
6. **Monitor time remaining** - warn users before expiry

This API endpoint is the core of your WiFi access control system and works seamlessly for both payment and voucher users! 🚀
