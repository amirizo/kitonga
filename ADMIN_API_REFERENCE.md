# Kitonga WiFi Billing - Admin API Reference

## Overview
This document provides comprehensive reference for all admin management APIs in the Kitonga WiFi Billing System. These APIs provide complete administrative control over users, payments, bundles, system settings, and MikroTik router management.

## Base URL
```
Production: https://api.kitonga.klikcell.com/api/
Development: http://127.0.0.1:8000/api/
```

## Authentication
All admin endpoints require dual authentication:

1. **Authorization Token**: Standard Django REST framework token
2. **Admin Access Token**: Special admin header

### Authentication Headers
```javascript
{
  "Authorization": "Token YOUR_AUTH_TOKEN",
  "X-Admin-Access": "kitonga_admin_2025"
}
```

### Login to Get Tokens
```bash
curl -X POST https://api.kitonga.klikcell.com/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}'
```

Response:
```json
{
  "success": true,
  "message": "Login successful",
  "user": {
    "id": 2,
    "username": "admin",
    "email": "admin@kitonga.com",
    "is_staff": true,
    "is_superuser": true
  },
  "token": "00fa02d094b7def5f0aa6ddc98d452cde566edc9",
  "admin_access_token": "kitonga_admin_secure_token_2025"
}
```

## Core Admin APIs

### 1. User Management

#### List All Users
```bash
GET /api/admin/users/
GET /api/users/  # Short alias
```

**Parameters:**
- `page` (int): Page number (default: 1)
- `page_size` (int): Items per page (default: 20)
- `phone_number` (string): Filter by phone number
- `is_active` (boolean): Filter by active status

**Example:**
```bash
curl -X GET "https://api.kitonga.klikcell.com/api/admin/users/?page=1&page_size=10" \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "X-Admin-Access: kitonga_admin_2025"
```

**Response:**
```json
{
  "success": true,
  "users": [
    {
      "id": 7,
      "phone_number": "255712345678",
      "is_active": true,
      "created_at": "2025-10-12T10:59:36.358945+00:00",
      "paid_until": "2025-10-13T10:59:36.363277+00:00",
      "has_active_access": false,
      "max_devices": 3,
      "total_payments": 1,
      "device_count": 0,
      "payment_count": 1,
      "last_payment": {
        "amount": "1000.00",
        "bundle_name": "Daily Access",
        "completed_at": "2025-10-12T10:59:36.362381+00:00"
      }
    }
  ],
  "pagination": {
    "total": 5,
    "page": 1,
    "page_size": 20,
    "total_pages": 1
  }
}
```

#### Get User Details
```bash
GET /api/admin/users/{user_id}/
GET /api/users/{user_id}/  # Short alias
```

#### Update User
```bash
PUT /api/admin/users/{user_id}/update/
```

#### Delete User
```bash
DELETE /api/admin/users/{user_id}/delete/
```

### 2. Payment Management

#### List All Payments
```bash
GET /api/admin/payments/
GET /api/payments/  # Short alias
```

**Parameters:**
- `status` (string): Filter by payment status (pending, completed, failed)
- `phone_number` (string): Filter by phone number
- `date_from` (ISO date): Filter from date
- `date_to` (ISO date): Filter to date
- `bundle_id` (int): Filter by bundle ID

**Example:**
```bash
curl -X GET "https://api.kitonga.klikcell.com/api/admin/payments/?status=completed" \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "X-Admin-Access: kitonga_admin_2025"
```

**Response:**
```json
{
  "success": true,
  "payments": [
    {
      "id": 18,
      "phone_number": "255772236727",
      "amount": "1000.00",
      "status": "completed",
      "order_reference": "KITONGA5CECF8933",
      "bundle_name": "Daily Access",
      "bundle_id": 1,
      "created_at": "2025-10-12T13:10:30.210845+00:00",
      "completed_at": "2025-10-12T13:10:45.123456+00:00",
      "user_id": 5,
      "payment_reference": "CLPLCPCA6KYH4",
      "transaction_id": "fea7bce6-22ce-44bb-9d9d-bb4fe998b3cf",
      "payment_channel": "TIGO-PESA"
    }
  ],
  "pagination": {
    "total": 14,
    "page": 1,
    "page_size": 20,
    "total_pages": 1
  },
  "summary": {
    "total_amount": "5000",
    "pending_amount": "1000",
    "completed_count": 5,
    "pending_count": 1,
    "failed_count": 8
  }
}
```

#### Get Payment Details
```bash
GET /api/admin/payments/{payment_id}/
```

#### Refund Payment
```bash
POST /api/admin/payments/{payment_id}/refund/
```

### 3. Bundle Management

#### List All Bundles
```bash
GET /api/admin/bundles/
```

**Response:**
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
      "is_active": true,
      "display_order": 1,
      "total_purchases": 5,
      "revenue": "5000"
    }
  ]
}
```

#### Create/Update Bundle
```bash
POST /api/admin/bundles/
PUT /api/admin/bundles/{bundle_id}/
```

#### Delete Bundle
```bash
DELETE /api/admin/bundles/{bundle_id}/
```

### 4. System Administration

#### System Settings
```bash
GET /api/admin/settings/
```

**Response:**
```json
{
  "success": true,
  "settings": {
    "mikrotik": {
      "router_ip": "192.168.0.173",
      "username": "",
      "hotspot_name": "kitonga-hotspot",
      "api_port": 8728,
      "connection_status": "Unknown"
    },
    "clickpesa": {
      "api_key_configured": true,
      "webhook_url": "https://api.kitonga.klikcell.com/api/clickpesa-webhook/",
      "environment": "sandbox"
    },
    "nextsms": {
      "api_key_configured": false,
      "sender_id": "Klikcell"
    },
    "system": {
      "debug_mode": true,
      "allowed_hosts": ["localhost", "127.0.0.1", "api.kitonga.klikcell.com"],
      "time_zone": "Africa/Dar_es_Salaam",
      "language_code": "en-us"
    }
  }
}
```

#### System Status
```bash
GET /api/admin/status/
```

**Response:**
```json
{
  "success": true,
  "status": {
    "database_status": "OK",
    "mikrotik_status": "OK",
    "uptime": "Unknown",
    "memory_usage": "Unknown",
    "disk_usage": "Unknown",
    "active_users": 0,
    "payments_today": 0,
    "revenue_today": 0,
    "payments_week": 0,
    "revenue_week": 0,
    "total_users": 5,
    "active_bundles": 3,
    "pending_payments": 1
  },
  "timestamp": "2025-10-28T11:29:31.750960+00:00"
}
```

## MikroTik Router Management

### Test Router Connection
```bash
POST /api/admin/mikrotik/test-connection/
```

**Request Body:**
```json
{
  "router_ip": "192.168.0.173",
  "username": "admin",
  "password": "router_password"
}
```

### Router Configuration
```bash
GET /api/admin/mikrotik/config/
POST /api/admin/mikrotik/config/
```

### Router Information
```bash
GET /api/admin/mikrotik/router-info/
```

### Active Users on Router
```bash
GET /api/admin/mikrotik/active-users/
```

### Disconnect User
```bash
POST /api/admin/mikrotik/disconnect-user/
```

### Disconnect All Users
```bash
POST /api/admin/mikrotik/disconnect-all/
```

### Reboot Router
```bash
POST /api/admin/mikrotik/reboot/
```

### Hotspot Profiles
```bash
GET /api/admin/mikrotik/profiles/
POST /api/admin/mikrotik/profiles/create/
```

### System Resources
```bash
GET /api/admin/mikrotik/resources/
```

## Dashboard Analytics

### Dashboard Statistics
```bash
GET /api/dashboard-stats/
```

**Response:**
```json
{
  "active_users": 0,
  "revenue_30d": {
    "period_days": 30,
    "total_revenue": 3000.0,
    "total_transactions": 3,
    "unique_users": 3,
    "average_per_user": 1000.0
  },
  "revenue_7d": {
    "period_days": 7,
    "total_revenue": 0.0,
    "total_transactions": 0,
    "unique_users": 0,
    "average_per_user": 0
  },
  "recent_payments": [...],
  "recent_users": [...],
  "payment_stats": [...],
  "voucher_stats": {...},
  "device_stats": {...}
}
```

## Error Handling

All endpoints return consistent error responses:

```json
{
  "success": false,
  "message": "Error description",
  "error_code": "OPTIONAL_ERROR_CODE"
}
```

Common HTTP status codes:
- `200`: Success
- `400`: Bad Request
- `401`: Unauthorized
- `403`: Forbidden (insufficient permissions)
- `404`: Not Found
- `500`: Internal Server Error

## Frontend Integration Examples

### JavaScript/React Example
```javascript
const API_BASE = 'https://api.kitonga.klikcell.com/api/';
const authToken = 'your_auth_token';
const adminToken = 'kitonga_admin_2025';

const headers = {
  'Authorization': `Token ${authToken}`,
  'X-Admin-Access': adminToken,
  'Content-Type': 'application/json'
};

// Fetch users
const fetchUsers = async () => {
  const response = await fetch(`${API_BASE}admin/users/`, { headers });
  const data = await response.json();
  return data;
};

// Fetch payments with filters
const fetchPayments = async (filters = {}) => {
  const params = new URLSearchParams(filters);
  const response = await fetch(`${API_BASE}admin/payments/?${params}`, { headers });
  const data = await response.json();
  return data;
};

// Update user
const updateUser = async (userId, userData) => {
  const response = await fetch(`${API_BASE}admin/users/${userId}/update/`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(userData)
  });
  return await response.json();
};
```

### Python Example
```python
import requests

API_BASE = 'https://api.kitonga.klikcell.com/api/'
headers = {
    'Authorization': 'Token your_auth_token',
    'X-Admin-Access': 'kitonga_admin_2025',
    'Content-Type': 'application/json'
}

# Fetch users
response = requests.get(f'{API_BASE}admin/users/', headers=headers)
users_data = response.json()

# Fetch payments
params = {'status': 'completed', 'page_size': 50}
response = requests.get(f'{API_BASE}admin/payments/', headers=headers, params=params)
payments_data = response.json()
```

## Complete Endpoint List

### Authentication
- `POST /api/auth/login/` - Admin login
- `GET /api/auth/profile/` - Get admin profile
- `POST /api/auth/logout/` - Admin logout
- `POST /api/auth/change-password/` - Change password

### User Management (21 endpoints total)
- `GET /api/admin/users/` - List all users ✅
- `GET /api/users/` - List users (short alias) ✅
- `GET /api/admin/users/{id}/` - Get user details
- `PUT /api/admin/users/{id}/update/` - Update user
- `DELETE /api/admin/users/{id}/delete/` - Delete user

### Payment Management
- `GET /api/admin/payments/` - List all payments ✅
- `GET /api/payments/` - List payments (short alias) ✅
- `GET /api/admin/payments/{id}/` - Get payment details
- `POST /api/admin/payments/{id}/refund/` - Refund payment

### Bundle Management
- `GET /api/admin/bundles/` - List all bundles ✅
- `POST /api/admin/bundles/` - Create bundle
- `GET /api/admin/bundles/{id}/` - Get bundle details
- `PUT /api/admin/bundles/{id}/` - Update bundle
- `DELETE /api/admin/bundles/{id}/` - Delete bundle

### System Administration
- `GET /api/admin/settings/` - System settings ✅
- `GET /api/admin/status/` - System status ✅

### MikroTik Management (10+ endpoints)
- `POST /api/admin/mikrotik/test-connection/` - Test connection ✅
- `GET /api/admin/mikrotik/config/` - Get configuration
- `POST /api/admin/mikrotik/config/` - Update configuration
- `GET /api/admin/mikrotik/router-info/` - Router information
- `GET /api/admin/mikrotik/active-users/` - Active users
- `POST /api/admin/mikrotik/disconnect-user/` - Disconnect user
- `POST /api/admin/mikrotik/disconnect-all/` - Disconnect all
- `POST /api/admin/mikrotik/reboot/` - Reboot router
- `GET /api/admin/mikrotik/profiles/` - Hotspot profiles
- `POST /api/admin/mikrotik/profiles/create/` - Create profile
- `GET /api/admin/mikrotik/resources/` - System resources

### Analytics & Monitoring
- `GET /api/dashboard-stats/` - Dashboard statistics ✅
- `GET /api/health/` - Health check ✅

## Security Notes

1. **Always use HTTPS** in production
2. **Store tokens securely** - never expose in client-side code
3. **Implement token refresh** mechanism
4. **Rate limiting** is enforced on all endpoints
5. **Admin access** is logged and monitored

## Testing Status
✅ All core admin endpoints tested and working
✅ Authentication system validated
✅ Error handling implemented
✅ Response formats standardized
✅ Frontend integration ready

---

*Last updated: October 28, 2025*
*API Version: 1.0*
