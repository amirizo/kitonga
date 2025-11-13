# Automatic MikroTik Connection/Disconnection on Access Verification

## 🎯 Overview

The `verify_access` API endpoint now **automatically connects or disconnects users** from the MikroTik router based on their access status. This ensures that:

1. ✅ Users with valid access are **automatically connected** to the internet
2. ❌ Users without valid access are **automatically disconnected** from the internet
3. 🔄 Real-time enforcement of access control

---

## 🚀 How It Works

### When User Has Access (Automatic Connection)

When a user calls `verify_access` and has valid access:

```python
# User has valid access
has_access = True

# System automatically:
1. Checks if user has paid_until > now
2. Validates device limit not exceeded
3. Creates/updates hotspot user in MikroTik
4. Adds MAC address bypass in MikroTik
5. User gets instant internet access
```

**What happens:**
- Creates hotspot user: `username=phone_number, password=last_6_digits`
- Adds MAC bypass binding with comment: `Auto-connected on access verification (payment/voucher)`
- User is immediately connected to internet
- Logs: `✓ Automatically connected {phone} to internet via MikroTik`

### When User Has NO Access (Automatic Disconnection)

When a user calls `verify_access` and has NO valid access:

```python
# User has no valid access
has_access = False

# System automatically:
1. Checks why user doesn't have access (expired, no payment, etc.)
2. Removes MAC address bypass from MikroTik
3. Disables hotspot user in MikroTik
4. User is immediately disconnected from internet
```

**What happens:**
- Removes MAC bypass binding
- Disables hotspot user
- User loses internet connection immediately
- Logs: `✓ Automatically disconnected {phone} from MikroTik`

---

## 📡 API Endpoint

### POST `/api/verify-access/`

**Request:**
```json
{
  "phone_number": "+255772236727",
  "mac_address": "AA:BB:CC:DD:EE:FF",
  "ip_address": "192.168.88.100"
}
```

**Response (User with Access):**
```json
{
  "access_granted": true,
  "denial_reason": "",
  "user": {
    "id": 1,
    "phone_number": "+255772236727",
    "is_active": true,
    "paid_until": "2025-11-14T12:00:00Z"
  },
  "access_method": "payment",
  "mikrotik_connection": {
    "action": "connected",
    "success": true,
    "message": "Successfully connected to internet"
  },
  "debug_info": {
    "has_payments": true,
    "has_vouchers": false,
    "paid_until": "2025-11-14T12:00:00Z",
    "is_active": true,
    "device_count": 1,
    "max_devices": 1
  }
}
```

**Response (User without Access):**
```json
{
  "access_granted": false,
  "denial_reason": "Access expired 5 hours ago - payment or voucher required",
  "user": {
    "id": 1,
    "phone_number": "+255772236727",
    "is_active": false,
    "paid_until": "2025-11-13T07:00:00Z"
  },
  "access_method": "payment",
  "mikrotik_connection": {
    "action": "disconnected",
    "success": true,
    "message": "Disconnected from internet (no valid access)"
  },
  "debug_info": {
    "has_payments": true,
    "has_vouchers": false,
    "paid_until": "2025-11-13T07:00:00Z",
    "is_active": false,
    "device_count": 1,
    "max_devices": 1
  }
}
```

---

## 🔄 Complete User Flow

### Scenario 1: User Makes Payment

```
1. User makes payment via ClickPesa
   └─> Payment webhook received
       └─> User access granted (paid_until set)
           └─> Auto-connection triggered in webhook handler
               └─> User connected to internet ✅

2. User device calls verify_access API
   └─> has_access = True
       └─> Auto-connection triggered again (idempotent)
           └─> User stays connected ✅

3. Access expires (paid_until < now)
   └─> Cron job runs disconnect_expired_users
       └─> User disconnected by cron ❌

4. User device calls verify_access API
   └─> has_access = False
       └─> Auto-disconnection triggered
           └─> User stays disconnected ❌
```

### Scenario 2: User Redeems Voucher

```
1. User redeems voucher
   └─> User access granted (paid_until set)
       └─> Auto-connection triggered in redeem handler
           └─> User connected to internet ✅

2. User device calls verify_access API
   └─> has_access = True
       └─> Auto-connection triggered again (idempotent)
           └─> User stays connected ✅

3. Voucher expires
   └─> Same disconnection flow as payment
```

### Scenario 3: User Tries to Access Without Payment

```
1. New user (no payment, no voucher)
   └─> User not found in database
       └─> verify_access returns: "User not found"
           └─> No connection possible ❌

2. User makes payment
   └─> User account created
       └─> Access granted
           └─> Auto-connection triggered ✅
```

---

## 🎨 MikroTik Connection States

| State | Description | Action Taken |
|-------|-------------|--------------|
| `connected` | User successfully connected | Hotspot user created + MAC bypassed |
| `disconnected` | User successfully disconnected | MAC revoked + User disabled |
| `connect_failed` | Connection attempt failed | Error logged, user not connected |
| `disconnect_failed` | Disconnection attempt failed | Warning logged, retry later |
| `connect_error` | Connection threw exception | Error logged with traceback |
| `disconnect_error` | Disconnection threw exception | Error logged with traceback |
| `none` | No action taken | MAC address not provided |

---

## 📋 Logging

### Connection Logs

```
INFO: ✓ User +255772236727 has valid access - connecting to MikroTik (MAC: AA:BB:CC:DD:EE:FF, IP: 192.168.88.100)
INFO: ✓ Automatically connected +255772236727 to internet via MikroTik
```

### Disconnection Logs

```
INFO: ✗ User +255772236727 has no valid access - disconnecting from MikroTik (Reason: Access expired 5 hours ago)
INFO: ✓ Automatically disconnected +255772236727 from MikroTik
```

### Error Logs

```
ERROR: ✗ Failed to connect +255772236727 to MikroTik: mac:bypass_failed
ERROR: ✗ Error connecting +255772236727 to MikroTik: Connection timeout
WARNING: ⚠ Failed to disconnect +255772236727 from MikroTik: User not found
```

---

## 🔧 Implementation Details

### Functions Used

1. **`grant_user_access()`** - Creates hotspot user and MAC bypass
   - Located in: `billing/mikrotik.py`
   - Parameters: `username, mac_address, password, comment`
   - Returns: `{'success': bool, 'errors': []}`

2. **`revoke_user_access()`** - Removes MAC bypass and disables user
   - Located in: `billing/mikrotik.py`
   - Parameters: `mac_address, username`
   - Returns: `{'success': bool, 'errors': []}`

### Access Check Logic

```python
# Core access check
has_access = user.has_active_access()

# has_active_access() checks:
# 1. user.is_active == True
# 2. user.paid_until is not None
# 3. user.paid_until > timezone.now()
```

### Device Tracking

- Device MAC and IP are tracked in database
- Device limit enforced (default: 1 device per user)
- Device limit exceeded = access denied
- Last seen timestamp updated on each verification

---

## 🎯 Benefits

### 1. **Real-Time Enforcement**
- No delay between access expiration and disconnection
- Users are disconnected immediately when access expires

### 2. **Multiple Trigger Points**
- Payment webhook → Auto-connect
- Voucher redemption → Auto-connect
- Access verification → Auto-connect/disconnect
- Cron job → Auto-disconnect expired users

### 3. **Idempotent Operations**
- Multiple connection attempts don't cause errors
- System handles "already connected" gracefully
- System handles "already disconnected" gracefully

### 4. **Better User Experience**
- Instant connection after payment
- Instant connection after voucher
- Clear denial reasons when access denied
- MikroTik connection status in API response

### 5. **Admin Visibility**
- Full logging of all connection/disconnection events
- MikroTik action status in API response
- Debug info for troubleshooting

---

## 🧪 Testing

### Test Valid Access

```bash
curl -X POST http://localhost:8000/api/verify-access/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+255772236727",
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "ip_address": "192.168.88.100"
  }'
```

**Expected:** `access_granted: true`, `mikrotik_connection.action: "connected"`

### Test Invalid Access

```bash
curl -X POST http://localhost:8000/api/verify-access/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+255700000099",
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "ip_address": "192.168.88.100"
  }'
```

**Expected:** `access_granted: false`, `mikrotik_connection.action: "disconnected"`

---

## 🔍 Troubleshooting

### Issue: User shows access_granted=true but can't access internet

**Check:**
1. Verify MikroTik connection: `python manage.py test_mikrotik`
2. Check MikroTik logs: `mikrotik_connection.success` in API response
3. Verify MAC address is correct
4. Check MikroTik hotspot users: `/ip hotspot user print`
5. Check MikroTik IP bindings: `/ip hotspot ip-binding print`

### Issue: User disconnected but still has internet access

**Check:**
1. User might be using cached connection
2. Check paid_until in database: `python manage.py shell`
3. Force disconnect: `python manage.py disconnect_expired_users`
4. Check MikroTik active sessions: `/ip hotspot active print`

### Issue: Connection/disconnection fails

**Check:**
1. MikroTik API credentials in `.env`
2. MikroTik API enabled on router
3. Port 8728 accessible from Django server
4. Check logs for specific error messages

---

## 📊 Monitoring

### Key Metrics to Track

1. **Connection Success Rate**
   - Count: `mikrotik_action == "connected"`
   - Monitor: `mikrotik_success == true`

2. **Disconnection Success Rate**
   - Count: `mikrotik_action == "disconnected"`
   - Monitor: `mikrotik_success == true`

3. **Failed Operations**
   - Count: `mikrotik_action.endswith("_failed")`
   - Alert: When failure rate > 5%

4. **Error Rate**
   - Count: `mikrotik_action.endswith("_error")`
   - Alert: When error rate > 1%

### Log Queries

```bash
# Count successful connections today
grep "Automatically connected" logs/django.log | grep $(date +%Y-%m-%d) | wc -l

# Count successful disconnections today
grep "Automatically disconnected" logs/django.log | grep $(date +%Y-%m-%d) | wc -l

# Show connection failures
grep "Failed to connect" logs/django.log | tail -20

# Show disconnection failures
grep "Failed to disconnect" logs/django.log | tail -20
```

---

## ✅ Summary

The automatic connection/disconnection feature ensures that:

1. ✅ **Instant Access** - Users get internet immediately after payment/voucher
2. ✅ **Instant Revocation** - Users lose internet immediately when access expires
3. ✅ **Real-Time Enforcement** - Access control enforced at every verification
4. ✅ **Full Logging** - All operations logged for monitoring and debugging
5. ✅ **Error Handling** - Graceful handling of MikroTik API errors
6. ✅ **Idempotent** - Safe to call multiple times without side effects

Your system now provides seamless, automated access control! 🎉
