# MikroTik Integration API Testing Guide

## Overview
The MikroTik integration endpoints handle captive portal authentication, allowing the router to verify user access before granting internet connectivity.

## Captive Portal Flow Explanation

### How Users Connect to WiFi and Get Directed to Captive Portal

1. **User Connects to WiFi**
   - User selects "kitonga-hotspot" WiFi network
   - Connects without password (open network)
   - Tries to browse internet

2. **Router Intercepts Traffic**
   - MikroTik router intercepts all HTTP/HTTPS requests
   - Redirects user to captive portal page
   - Portal URL: `http://192.168.0.173/login` or custom portal

3. **Captive Portal Authentication**
   - Portal calls Django API: `/api/mikrotik/auth/`
   - Django checks if user has valid access
   - Returns Accept/Reject to router

4. **Access Granted or Payment Required**
   - **If paid**: User gets internet access
   - **If unpaid**: User redirected to payment portal

## API Endpoints Testing

### 1. `/api/mikrotik/auth/` - Authentication Endpoint

**Purpose**: Called by MikroTik router to authenticate users
**Method**: POST
**Called by**: MikroTik router during captive portal login

**Request Parameters:**
```json
{
  "username": "0772236727",     // Phone number
  "password": "0772236727",     // Usually same as username
  "mac_address": "AA:BB:CC:DD:EE:99",
  "ip_address": "10.5.50.200",
  "user_agent": "Mozilla/5.0..."
}
```

**Expected Responses:**

**✅ PAID USER (Access Granted):**
```json
{
  "Auth-Status": "Accept",
  "success": true,
  "message": "Authentication successful",
  "user_info": {
    "phone_number": "0772236727",
    "has_active_access": true,
    "paid_until": "2025-10-29T18:00:00Z",
    "remaining_time": "23:45:30"
  }
}
```

**❌ UNPAID USER (Access Denied):**
```json
{
  "Auth-Status": "Reject",
  "success": false,
  "message": "No active subscription",
  "redirect_url": "https://portal.kitonga.com/payment",
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

### 2. `/api/mikrotik/logout/` - Logout Endpoint

**Purpose**: Handle user logout from hotspot
**Method**: POST

**Request:**
```json
{
  "username": "0772236727",
  "ip_address": "10.5.50.200",
  "mac_address": "AA:BB:CC:DD:EE:99"
}
```

**Response:**
```json
{
  "success": true,
  "message": "User logged out successfully",
  "username": "0772236727"
}
```

### 3. `/api/mikrotik/status/` - Status Check

**Purpose**: Check router and system status
**Method**: GET

**Response:**
```json
{
  "success": true,
  "router_status": "connected",
  "active_users": 15,
  "system_status": "healthy",
  "timestamp": "2025-10-28T18:00:00Z"
}
```

### 4. `/api/mikrotik/user-status/` - User Status Check

**Purpose**: Check specific user's connection status
**Method**: GET/POST

**Request:**
```json
{
  "username": "0772236727"
}
```

**Response:**
```json
{
  "success": true,
  "user": {
    "username": "0772236727",
    "is_online": true,
    "ip_address": "10.5.50.200",
    "mac_address": "AA:BB:CC:DD:EE:99",
    "session_time": "01:15:30",
    "bytes_in": 10485760,
    "bytes_out": 5242880,
    "has_active_access": true,
    "paid_until": "2025-10-29T18:00:00Z"
  }
}
```

## Testing Both Payment and Voucher Methods

### Payment Method Testing

**Step 1: Verify Access (New User)**
```bash
curl -X POST http://api.kitonga.com/api/verify/ \\
  -H "Content-Type: application/json" \\
  -d '{
    "phone_number": "0772236727",
    "mac_address": "AA:BB:CC:DD:EE:99",
    "ip_address": "10.5.50.200"
  }'
```

**Expected**: Access denied, user needs to pay

**Step 2: Initiate Payment**
```bash
curl -X POST http://api.kitonga.com/api/initiate-payment/ \\
  -H "Content-Type: application/json" \\
  -d '{
    "phone_number": "0772236727",
    "bundle_id": 1
  }'
```

**Step 3: Simulate Payment Completion**
```bash
curl -X POST http://api.kitonga.com/api/clickpesa-webhook/ \\
  -H "Content-Type: application/json" \\
  -d '{
    "event": "PAYMENT_RECEIVED",
    "data": {
      "orderReference": "KITONGA12345678",
      "status": "COMPLETED",
      "collectedAmount": "1000"
    }
  }'
```

**Step 4: Verify Access Again**
```bash
curl -X POST http://api.kitonga.com/api/verify/ \\
  -H "Content-Type: application/json" \\
  -d '{
    "phone_number": "0772236727",
    "mac_address": "AA:BB:CC:DD:EE:99",
    "ip_address": "10.5.50.200"
  }'
```

**Expected**: Access granted

### Voucher Method Testing

**Step 1: Generate Voucher (Admin)**
```bash
curl -X POST http://api.kitonga.com/api/vouchers/generate/ \\
  -H "Authorization: Token admin_token" \\
  -H "X-Admin-Access: kitonga_admin_2025" \\
  -H "Content-Type: application/json" \\
  -d '{
    "bundle_id": 1,
    "quantity": 1,
    "prefix": "TEST"
  }'
```

**Step 2: Redeem Voucher**
```bash
curl -X POST http://api.kitonga.com/api/vouchers/redeem/ \\
  -H "Content-Type: application/json" \\
  -d '{
    "phone_number": "0772236728",
    "voucher_code": "TEST-ABCD-1234"
  }'
```

**Step 3: Verify Access with Voucher**
```bash
curl -X POST http://api.kitonga.com/api/verify/ \\
  -H "Content-Type: application/json" \\
  -d '{
    "phone_number": "0772236728",
    "mac_address": "BB:CC:DD:EE:FF:01",
    "ip_address": "10.5.50.201"
  }'
```

**Expected**: Access granted

### User Status Testing

**Check Payment User Status:**
```bash
curl -X GET http://api.kitonga.com/api/user-status/0772236727/
```

**Check Voucher User Status:**
```bash
curl -X GET http://api.kitonga.com/api/user-status/0772236728/
```

## MikroTik Router Configuration

### Required Router Settings

1. **Hotspot Setup**
   ```
   /ip hotspot
   add name=kitonga-hotspot interface=bridge
   ```

2. **External Authentication**
   ```
   /ip hotspot user profile
   set default use-radius=yes
   
   /radius
   add service=hotspot address=192.168.0.100 secret=radius_secret
   ```

3. **Captive Portal**
   ```
   /ip hotspot walled-garden
   add dst-host=api.kitonga.com
   add dst-host=portal.kitonga.com
   ```

## Production Deployment Checklist

### API Server Configuration
- [ ] Django server running on production
- [ ] HTTPS enabled with SSL certificates
- [ ] CORS configured for router IP
- [ ] Database properly configured
- [ ] ClickPesa webhook configured

### Router Configuration
- [ ] Hotspot network configured
- [ ] External authentication pointing to API
- [ ] Captive portal page configured
- [ ] Walled garden rules for API access

### Network Configuration
- [ ] Router can reach API server
- [ ] DNS resolution working
- [ ] Firewall rules configured
- [ ] Network isolation between hotspot and admin

## Troubleshooting

### Common Issues

1. **User can't access captive portal**
   - Check walled garden rules
   - Verify DNS resolution
   - Check router connectivity to API

2. **Authentication always fails**
   - Check API server connectivity
   - Verify authentication endpoint
   - Check database connectivity

3. **Payment doesn't grant access**
   - Check webhook processing
   - Verify payment completion
   - Check user activation logic

### Debug Commands

**Check router connectivity:**
```bash
curl -X POST http://api.kitonga.com/api/admin/mikrotik/test-connection/
```

**Check user in database:**
```bash
curl -X GET http://api.kitonga.com/api/user-status/0772236727/
```

**Check active users on router:**
```bash
curl -X GET http://api.kitonga.com/api/admin/mikrotik/active-users/
```

## Summary

The MikroTik integration endpoints provide a complete captive portal solution that:

1. ✅ Authenticates users based on payment status
2. ✅ Supports both payment and voucher methods
3. ✅ Handles user session management
4. ✅ Provides admin monitoring capabilities
5. ✅ Integrates with ClickPesa payment system

The system is ready for production deployment with a physical MikroTik router configured for hotspot authentication.
