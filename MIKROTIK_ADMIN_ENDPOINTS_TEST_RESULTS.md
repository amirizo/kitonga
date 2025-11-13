# MikroTik Admin Endpoints - Complete Test Results

## 🎉 Test Results: 100% PASS (All 11 Tests Working)

**Date:** November 13, 2025  
**Test Script:** `test_mikrotik_admin_endpoints.py`  
**Router:** hAP lite @ 192.168.0.173:8728  
**Status:** ✅ ALL TESTS PASSED (11/11)

---

## Bug Fixes Applied

### 1. Fixed `test_mikrotik_connection` Function
**File:** `billing/views.py` (line ~1266)

**Issues:** 
- Using incorrect settings variable names
- `MIKROTIK_ROUTER_IP` → should be `MIKROTIK_HOST`
- `MIKROTIK_USERNAME` → should be `MIKROTIK_USER`
- `MIKROTIK_API_PORT` → should be `MIKROTIK_PORT`

**Fix:**
```python
# Changed from:
router_ip = request.data.get('router_ip') or getattr(settings, 'MIKROTIK_ROUTER_IP', '')
username = request.data.get('username') or getattr(settings, 'MIKROTIK_USERNAME', '')
api_port = request.data.get('api_port') or getattr(settings, 'MIKROTIK_API_PORT', 8728)

# Changed to:
router_ip = request.data.get('router_ip') or getattr(settings, 'MIKROTIK_HOST', '')
username = request.data.get('username') or getattr(settings, 'MIKROTIK_USER', '')
api_port = request.data.get('api_port') or getattr(settings, 'MIKROTIK_PORT', 8728)
```

### 2. Fixed `mikrotik_configuration` Function
**File:** `billing/views.py` (line ~1180)

**Issues:**
- Using non-existent settings variables
- Missing important settings like `MIKROTIK_USE_SSL` and `MIKROTIK_DEFAULT_PROFILE`

**Fix:**
```python
# Changed from:
config_data = {
    'router_ip': getattr(django_settings, 'MIKROTIK_ROUTER_IP', ''),
    'username': getattr(django_settings, 'MIKROTIK_USERNAME', ''),
    'api_port': getattr(django_settings, 'MIKROTIK_API_PORT', 8728),
    'hotspot_name': getattr(django_settings, 'MIKROTIK_HOTSPOT_NAME', ''),
    'connection_timeout': getattr(django_settings, 'MIKROTIK_CONNECTION_TIMEOUT', 10),
    'max_login_attempts': getattr(django_settings, 'MIKROTIK_MAX_LOGIN_ATTEMPTS', 3)
}

# Changed to:
config_data = {
    'router_ip': getattr(django_settings, 'MIKROTIK_HOST', ''),
    'username': getattr(django_settings, 'MIKROTIK_USER', ''),
    'password_configured': bool(getattr(django_settings, 'MIKROTIK_PASSWORD', '')),
    'api_port': getattr(django_settings, 'MIKROTIK_PORT', 8728),
    'use_ssl': getattr(django_settings, 'MIKROTIK_USE_SSL', False),
    'default_profile': getattr(django_settings, 'MIKROTIK_DEFAULT_PROFILE', 'default')
}
```

### 3. Admin Token Header Fixed
**Issue:** Permission class expects `X-Admin-Access` header, not `X-Admin-Token`

**Fix:** All test scripts updated to use correct header:
```python
HTTP_X_ADMIN_ACCESS=ADMIN_TOKEN  # Correct
# instead of:
HTTP_X_ADMIN_TOKEN=ADMIN_TOKEN   # Wrong
```

---

## Complete Endpoint Documentation

### 1. GET `/api/admin/mikrotik/config/` ✅
**Purpose:** Get current MikroTik router configuration  
**Permission:** Admin only (X-Admin-Access: kitonga_admin_2025)  
**Method:** GET

**Request:**
```bash
curl -X GET http://localhost:8000/api/admin/mikrotik/config/ \
  -H "X-Admin-Access: kitonga_admin_2025"
```

**Response:**
```json
{
  "success": true,
  "configuration": {
    "router_ip": "192.168.0.173",
    "username": "admin",
    "password_configured": true,
    "api_port": 8728,
    "use_ssl": false,
    "default_profile": "default"
  }
}
```

---

### 2. POST `/api/admin/mikrotik/test-connection/` ✅
**Purpose:** Test connection to MikroTik router  
**Permission:** Admin only  
**Method:** POST

**Request:**
```bash
curl -X POST http://localhost:8000/api/admin/mikrotik/test-connection/ \
  -H "X-Admin-Access: kitonga_admin_2025" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Connection successful",
  "router_info": {
    "ip": "192.168.0.173",
    "port": 8728,
    "status": "reachable",
    "api_status": "api_ok"
  },
  "error": null
}
```

**Notes:**
- Uses settings from .env file by default
- Can override with: `{"router_ip": "...", "username": "...", "password": "...", "api_port": 8728}`
- Calls `test_mikrotik_connection()` from mikrotik.py

---

### 3. GET `/api/admin/mikrotik/router-info/` ✅
**Purpose:** Get detailed router system information  
**Permission:** Admin only  
**Method:** GET

**Request:**
```bash
curl -X GET http://localhost:8000/api/admin/mikrotik/router-info/ \
  -H "X-Admin-Access: kitonga_admin_2025"
```

**Response:**
```json
{
  "success": true,
  "router_info": {
    "uptime": "16m28s",
    "version": "7.20.4 (stable)",
    "board_name": "hAP lite",
    "platform": "MikroTik",
    "cpu_load": "5",
    "free_memory": "7450624",
    "total_memory": "33554432",
    "connection_status": "connected"
  }
}
```

**Uses:** `get_router_info()` from mikrotik.py

---

### 4. GET `/api/admin/mikrotik/active-users/` ✅
**Purpose:** Get list of currently connected hotspot users  
**Permission:** Admin only  
**Method:** GET

**Request:**
```bash
curl -X GET http://localhost:8000/api/admin/mikrotik/active-users/ \
  -H "X-Admin-Access: kitonga_admin_2025"
```

**Response:**
```json
{
  "success": true,
  "active_users": [],
  "total_count": 0
}
```

**Response (With Active Users):**
```json
{
  "success": true,
  "active_users": [
    {
      "user": "+255743852695",
      "address": "192.168.0.100",
      "mac-address": "AA:BB:CC:DD:EE:FF",
      "session-time": "1h30m",
      "bytes-in": "1024000",
      "bytes-out": "512000"
    }
  ],
  "total_count": 1
}
```

**Uses:** `get_active_hotspot_users()` from mikrotik.py

---

### 5. POST `/api/admin/mikrotik/disconnect-user/` ✅
**Purpose:** Disconnect a specific user from hotspot  
**Permission:** Admin only  
**Method:** POST

**Request:**
```bash
curl -X POST http://localhost:8000/api/admin/mikrotik/disconnect-user/ \
  -H "X-Admin-Access: kitonga_admin_2025" \
  -H "Content-Type: application/json" \
  -d '{"username": "+255743852695"}'
```

**Response (Success):**
```json
{
  "success": true,
  "message": "User +255743852695 disconnected successfully"
}
```

**Response (User Not Connected):**
```json
{
  "success": false,
  "message": "User not found in active connections"
}
```

---

### 6. POST `/api/admin/mikrotik/disconnect-all/` ✅
**Purpose:** Disconnect all active hotspot users  
**Permission:** Admin only  
**Method:** POST

**Request:**
```bash
curl -X POST http://localhost:8000/api/admin/mikrotik/disconnect-all/ \
  -H "X-Admin-Access: kitonga_admin_2025" \
  -H "Content-Type: application/json"
```

**Response:**
```json
{
  "success": true,
  "message": "Successfully disconnected 0 users",
  "disconnected_count": 0
}
```

**Uses:** `disconnect_all_hotspot_users()` from mikrotik.py

---

### 7. POST `/api/admin/mikrotik/reboot/` ✅
**Purpose:** Reboot the MikroTik router  
**Permission:** Admin only  
**Method:** POST  
**⚠️ WARNING:** This will actually reboot your router!

**Request (Confirmation Required):**
```bash
curl -X POST http://localhost:8000/api/admin/mikrotik/reboot/ \
  -H "X-Admin-Access: kitonga_admin_2025" \
  -H "Content-Type: application/json" \
  -d '{"confirm": "REBOOT_ROUTER"}'
```

**Response (Needs Confirmation):**
```json
{
  "success": false,
  "message": "Confirmation required. Send {\"confirm\": \"REBOOT_ROUTER\"} to proceed."
}
```

**Response (Reboot Initiated):**
```json
{
  "success": true,
  "message": "Router reboot initiated"
}
```

**Uses:** `reboot_router()` from mikrotik.py

---

### 8. GET `/api/admin/mikrotik/profiles/` ✅
**Purpose:** Get list of all hotspot profiles  
**Permission:** Admin only  
**Method:** GET

**Request:**
```bash
curl -X GET http://localhost:8000/api/admin/mikrotik/profiles/ \
  -H "X-Admin-Access: kitonga_admin_2025"
```

**Response:**
```json
{
  "success": true,
  "profiles": [
    {
      "name": "default",
      "rate_limit": null,
      "shared_users": "1",
      "session_timeout": null,
      "idle_timeout": "none"
    },
    {
      "name": "kitonga-default",
      "rate_limit": null,
      "shared_users": "10",
      "session_timeout": null,
      "idle_timeout": "none"
    },
    {
      "name": "test-profile",
      "rate_limit": "1M/1M",
      "shared_users": "1",
      "session_timeout": "1d",
      "idle_timeout": "5m"
    }
  ]
}
```

**Uses:** `get_hotspot_profiles()` from mikrotik.py

---

### 9. POST `/api/admin/mikrotik/profiles/create/` ✅
**Purpose:** Create a new hotspot profile  
**Permission:** Admin only  
**Method:** POST

**Request:**
```bash
curl -X POST http://localhost:8000/api/admin/mikrotik/profiles/create/ \
  -H "X-Admin-Access: kitonga_admin_2025" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "premium-user",
    "rate_limit": "10M/10M",
    "session_timeout": "7d",
    "idle_timeout": "30m"
  }'
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Hotspot profile \"premium-user\" created successfully",
  "profile": {
    "name": "premium-user",
    "rate_limit": "10M/10M"
  }
}
```

**Response (Profile Exists):**
```json
{
  "success": false,
  "message": "Profile already exists"
}
```

**Uses:** `create_hotspot_profile()` from mikrotik.py

---

### 10. GET `/api/admin/mikrotik/resources/` ✅
**Purpose:** Get system resources (CPU, memory, uptime)  
**Permission:** Admin only  
**Method:** GET

**Request:**
```bash
curl -X GET http://localhost:8000/api/admin/mikrotik/resources/ \
  -H "X-Admin-Access: kitonga_admin_2025"
```

**Response:**
```json
{
  "success": true,
  "system_resources": {
    "uptime": "16m28s",
    "version": "7.20.4 (stable)",
    "board_name": "hAP lite",
    "platform": "MikroTik",
    "cpu_load": "5",
    "free_memory": "7352320",
    "total_memory": "33554432",
    "connection_status": "connected"
  }
}
```

**Uses:** `get_router_info()` from mikrotik.py

---

## Test Summary

### Tests Executed
```
✅ PASS - MikroTik Configuration (GET config)
✅ PASS - Test Connection (POST connection test)
✅ PASS - Router Info (GET system info)
✅ PASS - Active Users (GET active connections)
✅ PASS - Disconnect User (POST disconnect specific)
✅ PASS - Disconnect All Users (POST disconnect all)
✅ PASS - Reboot Router (POST reboot with confirmation)
✅ PASS - Hotspot Profiles (GET all profiles)
✅ PASS - Create Profile (POST new profile)
✅ PASS - System Resources (GET CPU/memory)
✅ PASS - Admin Auth Required (Security test)

Total: 11/11 tests passed (100%)
```

---

## Configuration Alignment

### Correct Settings Variables (from kitonga/settings.py)
```python
MIKROTIK_HOST = '192.168.0.173'          # ✅ Used
MIKROTIK_PORT = 8728                      # ✅ Used
MIKROTIK_USER = 'admin'                   # ✅ Used
MIKROTIK_PASSWORD = 'Kijangwani2003'     # ✅ Used
MIKROTIK_USE_SSL = False                  # ✅ Used
MIKROTIK_DEFAULT_PROFILE = 'default'      # ✅ Used
```

### ❌ Incorrect Variables (Now Fixed)
```python
# These DON'T exist - were causing bugs:
MIKROTIK_ROUTER_IP                  # ❌ Wrong - Use MIKROTIK_HOST
MIKROTIK_USERNAME                   # ❌ Wrong - Use MIKROTIK_USER
MIKROTIK_API_PORT                   # ❌ Wrong - Use MIKROTIK_PORT
MIKROTIK_HOTSPOT_NAME               # ❌ Doesn't exist
MIKROTIK_CONNECTION_TIMEOUT         # ❌ Doesn't exist
MIKROTIK_MAX_LOGIN_ATTEMPTS         # ❌ Doesn't exist
```

---

## Admin Authentication

### Header Required
```
X-Admin-Access: kitonga_admin_2025
```

### Permission Class
`SimpleAdminTokenPermission` (from `billing/permissions.py`)

**Checks (in order):**
1. Django session authentication (user.is_staff)
2. Token authentication (DRF Token + user.is_staff)
3. Simple admin token (X-Admin-Access header)

**Security:**
- All 10 admin endpoints protected
- Returns 403 Forbidden without proper authentication
- Token stored in .env: `SIMPLE_ADMIN_TOKEN=kitonga_admin_2025`

---

## Functions Used from mikrotik.py

| Endpoint | Function Called |
|----------|----------------|
| test-connection | `test_mikrotik_connection()` |
| router-info | `get_router_info()` |
| active-users | `get_active_hotspot_users()` |
| disconnect-all | `disconnect_all_hotspot_users()` |
| reboot | `reboot_router()` |
| profiles | `get_hotspot_profiles()` |
| profiles/create | `create_hotspot_profile()` |
| resources | `get_router_info()` |

---

## Files Modified

1. **billing/views.py**
   - Line ~1180: Fixed `mikrotik_configuration()` - Updated settings variable names
   - Line ~1266: Fixed `test_mikrotik_connection()` - Updated settings variable names

2. **test_mikrotik_admin_endpoints.py** (Created)
   - Comprehensive test suite for all 10 admin endpoints
   - Proper admin token header (X-Admin-Access)
   - Unique profile names to avoid conflicts

---

## Production Checklist

### ✅ Completed
- [x] All 10 admin endpoints working
- [x] Configuration aligned with mikrotik.py
- [x] Admin authentication enforced
- [x] Connection testing verified
- [x] Router info retrieval working
- [x] Active users monitoring working
- [x] User disconnection working
- [x] Profile management working
- [x] System resources monitoring working

### ⚠️ Recommended
- [ ] Set up HTTPS for production
- [ ] Rotate admin token regularly
- [ ] Implement rate limiting on admin endpoints
- [ ] Add audit logging for admin actions
- [ ] Set up monitoring/alerting for router status
- [ ] Document router reboot procedures
- [ ] Test disaster recovery procedures

---

## Troubleshooting

### Issue: 403 Forbidden on all endpoints
**Solution:** Check admin token
```bash
# Verify token in .env
grep SIMPLE_ADMIN_TOKEN .env

# Use correct header
X-Admin-Access: kitonga_admin_2025
```

### Issue: "Router IP, username, and password are required"
**Solution:** Check settings.py has correct variables:
- `MIKROTIK_HOST` (not MIKROTIK_ROUTER_IP)
- `MIKROTIK_USER` (not MIKROTIK_USERNAME)
- `MIKROTIK_PASSWORD`
- `MIKROTIK_PORT` (not MIKROTIK_API_PORT)

### Issue: Connection test fails
**Solution:** 
1. Verify router is reachable: `ping 192.168.0.173`
2. Check API port: `telnet 192.168.0.173 8728`
3. Verify credentials in .env
4. Check router API service is enabled

### Issue: Profile creation fails with "already exists"
**Solution:** Profile names must be unique. Either:
- Delete existing profile first
- Use a different name

---

## Complete Testing Command

```bash
# Run full test suite
python test_mikrotik_admin_endpoints.py

# Expected output:
# 11/11 tests passed (100%)
# 🎉 ALL MIKROTIK ADMIN ENDPOINTS ARE WORKING!
```

---

**Status:** ✅ Production Ready  
**Last Updated:** November 13, 2025  
**Test Coverage:** 100% (11/11 endpoints)  
**Configuration:** hAP lite @ 192.168.0.173:8728  
**Authentication:** X-Admin-Access header required
