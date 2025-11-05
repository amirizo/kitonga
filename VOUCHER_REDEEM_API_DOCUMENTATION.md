# Kitonga WiFi Billing System - Voucher Redemption API Documentation

## API Endpoint: `POST /api/vouchers/redeem/`

This endpoint allows users to redeem voucher codes to get WiFi access. It creates user accounts automatically and handles device registration.

### Request Structure

**Method:** `POST`
**URL:** `http://your-domain.com/api/vouchers/redeem/`
**Content-Type:** `application/json`

#### Request Body (JSON):
```json
{
  "voucher_code": "ABCD-EFGH-1234",
  "phone_number": "255772236727",
  "ip_address": "192.168.0.100",
  "mac_address": "AA:BB:CC:DD:EE:FF"
}
```

#### Required Fields:
- `voucher_code` (string): The voucher code to redeem (format: XXXX-XXXX-XXXX)
- `phone_number` (string): User's phone number

#### Optional Fields:
- `ip_address` (string): User's IP address (auto-detected if not provided)
- `mac_address` (string): Device MAC address for immediate registration

---

## Response Examples

### 1. ✅ SUCCESS - Voucher Redeemed Successfully

```json
{
  "success": true,
  "message": "Voucher redeemed successfully. Access granted for 24 hours.",
  "user": {
    "id": 1,
    "phone_number": "255772236727",
    "created_at": "2025-11-05T14:30:00Z",
    "is_active": true,
    "paid_until": "2025-11-06T14:30:00Z",
    "max_devices": 1,
    "has_active_access": true,
    "time_remaining": {
      "hours": 24,
      "minutes": 0,
      "seconds": 0
    }
  },
  "voucher_info": {
    "code": "ABCD-EFGH-1234",
    "duration_hours": 24,
    "redeemed_at": "2025-11-05T14:30:00Z",
    "batch_id": "BATCH-001"
  },
  "access_info": {
    "has_active_access": true,
    "paid_until": "2025-11-06T14:30:00Z",
    "access_method": "voucher",
    "can_connect_to_wifi": true,
    "instructions": "Connect to WiFi network. Your device will automatically get internet access."
  },
  "device_info": {
    "device_registered": true,
    "device_id": 5,
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "device_count": 1,
    "max_devices": 1
  },
  "mikrotik_integration": {
    "mikrotik_auth_attempted": true,
    "mikrotik_auth_success": true,
    "ready_for_internet": true
  },
  "sms_notification_sent": true,
  "next_steps": [
    "1. Connect your device to the WiFi network",
    "2. Open your browser - you should automatically get internet access",
    "3. If prompted, enter your phone number to authenticate",
    "4. Your access is valid until 2025-11-06 14:30"
  ]
}
```

### 2. ✅ SUCCESS - Without MAC Address (Device Registration Later)

```json
{
  "success": true,
  "message": "Voucher redeemed successfully. Access granted for 24 hours.",
  "user": {
    "id": 2,
    "phone_number": "255987654321",
    "created_at": "2025-11-05T14:30:00Z",
    "is_active": true,
    "paid_until": "2025-11-06T14:30:00Z",
    "max_devices": 1,
    "has_active_access": true,
    "time_remaining": {
      "hours": 24,
      "minutes": 0,
      "seconds": 0
    }
  },
  "voucher_info": {
    "code": "WXYZ-9876-5432",
    "duration_hours": 24,
    "redeemed_at": "2025-11-05T14:30:00Z",
    "batch_id": "BATCH-002"
  },
  "access_info": {
    "has_active_access": true,
    "paid_until": "2025-11-06T14:30:00Z",
    "access_method": "voucher",
    "can_connect_to_wifi": true,
    "instructions": "Connect to WiFi network. Your device will automatically get internet access."
  },
  "device_info": {
    "device_registered": false,
    "message": "No device registered. User can connect with any device within device limit.",
    "max_devices": 1
  },
  "mikrotik_integration": {
    "mikrotik_auth_attempted": false,
    "ready_for_internet": true,
    "note": "Device will be registered when user connects to WiFi"
  },
  "sms_notification_sent": true,
  "next_steps": [
    "1. Connect your device to the WiFi network",
    "2. Open your browser - you should automatically get internet access",
    "3. If prompted, enter your phone number to authenticate",
    "4. Your access is valid until 2025-11-06 14:30"
  ]
}
```

### 3. ❌ ERROR - Voucher Already Used

```json
{
  "success": false,
  "message": "Voucher has already been used",
  "voucher_info": {
    "code": "ABCD-EFGH-1234",
    "used_at": "2025-11-04T10:15:00Z",
    "used_by": "255123456789"
  }
}
```

### 4. ❌ ERROR - Invalid Voucher Code

```json
{
  "success": false,
  "message": "Invalid voucher code"
}
```

### 5. ❌ ERROR - Device Limit Exceeded

```json
{
  "success": true,
  "message": "Voucher redeemed successfully. Access granted for 24 hours.",
  "user": {
    "id": 3,
    "phone_number": "255444555666",
    "created_at": "2025-11-05T14:30:00Z",
    "is_active": true,
    "paid_until": "2025-11-06T14:30:00Z",
    "max_devices": 1,
    "has_active_access": true,
    "time_remaining": {
      "hours": 24,
      "minutes": 0,
      "seconds": 0
    }
  },
  "voucher_info": {
    "code": "TEST-1234-5678",
    "duration_hours": 24,
    "redeemed_at": "2025-11-05T14:30:00Z",
    "batch_id": "BATCH-003"
  },
  "access_info": {
    "has_active_access": true,
    "paid_until": "2025-11-06T14:30:00Z",
    "access_method": "voucher",
    "can_connect_to_wifi": true,
    "instructions": "Connect to WiFi network. Your device will automatically get internet access."
  },
  "device_info": {
    "device_registered": false,
    "device_limit_exceeded": true,
    "device_count": 2,
    "max_devices": 1,
    "warning": "Device limit exceeded. Please remove an existing device first."
  },
  "mikrotik_integration": {
    "mikrotik_auth_attempted": true,
    "mikrotik_auth_success": false,
    "ready_for_internet": true
  },
  "sms_notification_sent": true,
  "next_steps": [
    "1. Connect your device to the WiFi network",
    "2. Open your browser - you should automatically get internet access",
    "3. If prompted, enter your phone number to authenticate",
    "4. Your access is valid until 2025-11-06 14:30"
  ]
}
```

---

## Frontend Implementation Examples

### JavaScript/Fetch Example:

```javascript
async function redeemVoucher(phoneNumber, voucherCode, macAddress, ipAddress) {
    const apiUrl = 'http://your-domain.com/api/vouchers/redeem/';
    
    const requestData = {
        phone_number: phoneNumber,
        voucher_code: voucherCode,
        mac_address: macAddress,  // Optional
        ip_address: ipAddress     // Optional
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
        
        if (response.ok && result.success) {
            console.log('✅ Voucher redeemed successfully!');
            console.log('Access granted until:', result.access_info.paid_until);
            console.log('Device registered:', result.device_info.device_registered);
            console.log('Ready for internet:', result.mikrotik_integration.ready_for_internet);
            
            return {
                success: true,
                user: result.user,
                accessInfo: result.access_info,
                deviceInfo: result.device_info,
                nextSteps: result.next_steps
            };
        } else {
            // Handle various error cases
            let errorMessage = result.message;
            let errorType = 'general';
            
            if (response.status === 404) {
                errorType = 'invalid_voucher';
                errorMessage = 'Invalid voucher code. Please check and try again.';
            } else if (response.status === 400 && result.message.includes('already been used')) {
                errorType = 'voucher_used';
                errorMessage = 'This voucher has already been used.';
            }
            
            console.log('❌ Voucher redemption failed:', errorMessage);
            return {
                success: false,
                error: errorMessage,
                errorType: errorType,
                voucherInfo: result.voucher_info
            };
        }
    } catch (error) {
        console.error('❌ API request failed:', error);
        return {
            success: false,
            error: 'Connection failed. Please check your internet and try again.',
            errorType: 'connection_error'
        };
    }
}

// Usage example:
redeemVoucher('255772236727', 'ABCD-EFGH-1234', 'AA:BB:CC:DD:EE:FF', '192.168.0.100')
    .then(result => {
        if (result.success) {
            // Voucher redeemed successfully
            showSuccessMessage('Voucher redeemed! You now have internet access.');
            displayAccessInfo(result.accessInfo);
            if (result.deviceInfo.device_registered) {
                showMessage('Your device has been registered for automatic access.');
            }
            showNextSteps(result.nextSteps);
        } else {
            // Handle different error types
            switch (result.errorType) {
                case 'invalid_voucher':
                    showErrorMessage('Invalid voucher code. Please check your voucher and try again.');
                    break;
                case 'voucher_used':
                    showErrorMessage('This voucher has already been used by another user.');
                    break;
                case 'connection_error':
                    showErrorMessage('Connection failed. Please check your internet and try again.');
                    break;
                default:
                    showErrorMessage(result.error);
            }
        }
    });
```

### React Hook Example:

```javascript
import { useState } from 'react';

function useVoucherRedemption() {
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    
    const redeemVoucher = async (phoneNumber, voucherCode, macAddress, ipAddress) => {
        setLoading(true);
        setError(null);
        setResult(null);
        
        try {
            const response = await fetch('/api/vouchers/redeem/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    phone_number: phoneNumber,
                    voucher_code: voucherCode,
                    mac_address: macAddress,
                    ip_address: ipAddress
                })
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                setResult(data);
            } else {
                setError({
                    message: data.message,
                    type: response.status === 404 ? 'invalid_voucher' : 
                          data.message.includes('already been used') ? 'voucher_used' : 'general',
                    voucherInfo: data.voucher_info
                });
            }
        } catch (err) {
            setError({
                message: 'Connection failed. Please try again.',
                type: 'connection_error'
            });
        } finally {
            setLoading(false);
        }
    };
    
    return {
        redeemVoucher,
        loading,
        result,
        error,
        clearResult: () => setResult(null),
        clearError: () => setError(null)
    };
}

// Usage in React component:
function VoucherRedemptionForm() {
    const { redeemVoucher, loading, result, error } = useVoucherRedemption();
    const [phoneNumber, setPhoneNumber] = useState('');
    const [voucherCode, setVoucherCode] = useState('');
    
    const handleSubmit = async (e) => {
        e.preventDefault();
        await redeemVoucher(phoneNumber, voucherCode);
    };
    
    if (result) {
        return (
            <div className="success-container">
                <h2>✅ Voucher Redeemed Successfully!</h2>
                <p>Access granted until: {new Date(result.access_info.paid_until).toLocaleString()}</p>
                {result.device_info.device_registered && (
                    <p>✅ Your device has been registered</p>
                )}
                <div className="next-steps">
                    <h3>Next Steps:</h3>
                    <ol>
                        {result.next_steps.map((step, index) => (
                            <li key={index}>{step}</li>
                        ))}
                    </ol>
                </div>
            </div>
        );
    }
    
    return (
        <form onSubmit={handleSubmit}>
            <h2>Redeem Voucher</h2>
            
            {error && (
                <div className="error-message">
                    {error.message}
                    {error.type === 'voucher_used' && error.voucherInfo && (
                        <p>Used by: {error.voucherInfo.used_by} on {new Date(error.voucherInfo.used_at).toLocaleString()}</p>
                    )}
                </div>
            )}
            
            <div>
                <label>Phone Number:</label>
                <input
                    type="tel"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    placeholder="255772236727"
                    required
                />
            </div>
            
            <div>
                <label>Voucher Code:</label>
                <input
                    type="text"
                    value={voucherCode}
                    onChange={(e) => setVoucherCode(e.target.value)}
                    placeholder="ABCD-EFGH-1234"
                    required
                />
            </div>
            
            <button type="submit" disabled={loading}>
                {loading ? 'Redeeming...' : 'Redeem Voucher'}
            </button>
        </form>
    );
}
```

### cURL Examples for Testing:

```bash
# Test with valid voucher and device info
curl -X POST http://127.0.0.1:8000/api/vouchers/redeem/ \
  -H "Content-Type: application/json" \
  -d '{
    "voucher_code": "ABCD-EFGH-1234",
    "phone_number": "255772236727",
    "ip_address": "192.168.0.100",
    "mac_address": "AA:BB:CC:DD:EE:FF"
  }'

# Test with voucher only (no device info)
curl -X POST http://127.0.0.1:8000/api/vouchers/redeem/ \
  -H "Content-Type: application/json" \
  -d '{
    "voucher_code": "WXYZ-9876-5432",
    "phone_number": "255987654321"
  }'

# Test with invalid voucher code
curl -X POST http://127.0.0.1:8000/api/vouchers/redeem/ \
  -H "Content-Type: application/json" \
  -d '{
    "voucher_code": "INVALID-CODE",
    "phone_number": "255123456789"
  }'

# Test with already used voucher
curl -X POST http://127.0.0.1:8000/api/vouchers/redeem/ \
  -H "Content-Type: application/json" \
  -d '{
    "voucher_code": "USED-VOUC-1234",
    "phone_number": "255111222333"
  }'
```

---

## Response Field Descriptions

### Main Response Fields:
- `success` (boolean): Whether voucher redemption was successful
- `message` (string): Human-readable success/error message
- `user` (object): User information (created or existing)
- `voucher_info` (object): Details about the redeemed voucher
- `access_info` (object): WiFi access information
- `device_info` (object): Device registration information
- `mikrotik_integration` (object): MikroTik router integration status
- `sms_notification_sent` (boolean): Whether SMS confirmation was sent
- `next_steps` (array): Step-by-step instructions for user

### User Object Fields:
- `id` (integer): User's database ID
- `phone_number` (string): User's phone number
- `created_at` (datetime): When user account was created
- `is_active` (boolean): Whether user account is active
- `paid_until` (datetime): When access expires
- `max_devices` (integer): Maximum devices allowed
- `has_active_access` (boolean): Whether user currently has access
- `time_remaining` (object): Hours, minutes, seconds remaining

### Voucher Info Fields:
- `code` (string): The voucher code that was redeemed
- `duration_hours` (integer): How many hours of access granted
- `redeemed_at` (datetime): When voucher was redeemed
- `batch_id` (string): Batch identifier for voucher

### Access Info Fields:
- `has_active_access` (boolean): Whether user has active WiFi access
- `paid_until` (datetime): When access expires
- `access_method` (string): Always "voucher" for this API
- `can_connect_to_wifi` (boolean): Whether user can connect to WiFi
- `instructions` (string): Basic connection instructions

### Device Info Fields:
- `device_registered` (boolean): Whether device was registered
- `device_id` (integer): Device database ID (if registered)
- `mac_address` (string): Device MAC address
- `device_count` (integer): Current device count
- `max_devices` (integer): Maximum devices allowed
- `device_limit_exceeded` (boolean): Whether device limit was exceeded
- `existing_device_updated` (boolean): Whether existing device was updated
- `warning` (string): Warning message if device limit exceeded

### MikroTik Integration Fields:
- `mikrotik_auth_attempted` (boolean): Whether MikroTik authentication was attempted
- `mikrotik_auth_success` (boolean): Whether MikroTik authentication succeeded
- `ready_for_internet` (boolean): Whether user is ready for internet access
- `mikrotik_error` (string): MikroTik error message (if failed)
- `note` (string): Additional information

---

## Status Codes

- `200 OK`: Voucher redeemed successfully
- `400 Bad Request`: Voucher already used or validation errors
- `404 Not Found`: Invalid voucher code
- `500 Internal Server Error`: Server error during redemption

---

## Best Practices

1. **Always check `success` field** - don't rely on HTTP status code alone
2. **Handle different error types** - invalid codes vs already used vouchers
3. **Display next steps** - guide users through connecting to WiFi
4. **Show access expiry** - let users know when access expires
5. **Handle device registration** - inform users about device limits
6. **Provide MAC address when possible** - for immediate device registration
7. **Cache user info briefly** - avoid repeated API calls

## Integration Notes

- **User Account Creation**: API automatically creates user accounts if they don't exist
- **Device Registration**: MAC address enables immediate device registration and MikroTik authentication
- **SMS Notifications**: System sends confirmation SMS to user's phone
- **Access Logging**: All redemptions are logged for monitoring and troubleshooting
- **MikroTik Integration**: Immediate router authentication if MAC address provided

This API endpoint enables complete voucher-based WiFi access with automatic user and device management! 🎟️
