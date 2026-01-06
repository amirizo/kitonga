# Tenant Portal API Documentation

## Overview

The Tenant Portal provides a comprehensive self-service dashboard for WiFi hotspot operators (tenants) to manage their business. This documentation covers all Phase 3 features.

## Authentication

All portal endpoints require tenant authentication via API key:

```
Header: X-API-Key: your_tenant_api_key
```

Alternatively, authenticated staff members can use token authentication:
```
Header: Authorization: Token your_auth_token
```

---

## Dashboard & Analytics

### Get Dashboard Summary

Get comprehensive dashboard data including stats, trends, and insights.

**Endpoint:** `GET /api/portal/dashboard/`

**Response:**
```json
{
  "success": true,
  "tenant": {
    "id": "uuid",
    "slug": "my-hotel",
    "business_name": "My Hotel WiFi",
    "subscription_status": "active",
    "subscription_plan": "Business",
    "subscription_ends_at": "2026-02-01T00:00:00Z"
  },
  "dashboard": {
    "overview": {
      "total_users": 1250,
      "active_users": 45,
      "total_devices": 2100,
      "active_devices": 52,
      "total_routers": 3,
      "online_routers": 3,
      "total_payments": 5420,
      "total_revenue": 5420000,
      "total_vouchers_generated": 500,
      "total_vouchers_used": 380
    },
    "today": {
      "payments_count": 25,
      "revenue": 25000,
      "average_payment": 1000,
      "new_users": 8,
      "vouchers_redeemed": 5
    },
    "this_week": {...},
    "this_month": {...},
    "active_users": {
      "total_active": 45,
      "expiring_soon": 5,
      "expiring_today": 12,
      "expiring_this_week": 28
    },
    "revenue_trend": [
      {"date": "2026-01-01", "revenue": 50000, "transactions": 50},
      ...
    ],
    "top_bundles": [
      {"bundle_id": 1, "name": "Daily", "price": 1000, "sales_count": 200, "total_revenue": 200000}
    ],
    "device_breakdown": {
      "phone": 150,
      "laptop": 45,
      "tablet": 20,
      "unknown": 10
    },
    "router_status": [
      {"id": 1, "name": "Main Router", "host": "192.168.1.1", "status": "online", "location": "Lobby"}
    ]
  }
}
```

### Get Real-time Stats

Lightweight endpoint for live dashboard updates (polling).

**Endpoint:** `GET /api/portal/realtime/`

**Response:**
```json
{
  "success": true,
  "data": {
    "timestamp": "2026-01-06T10:30:00Z",
    "active_users": 45,
    "recent_activity_5min": 12,
    "recent_payments": [
      {"id": 123, "amount": 1000, "phone": "****5678", "bundle": "Daily", "time": "2026-01-06T10:28:00Z"}
    ]
  }
}
```

### Get Period Comparison

Compare current period with previous (week over week, month over month).

**Endpoint:** `GET /api/portal/comparison/`

**Response:**
```json
{
  "success": true,
  "week_over_week": {
    "current_period": {
      "start": "2025-12-30",
      "end": "2026-01-06",
      "revenue": 175000,
      "transactions": 175,
      "new_users": 50,
      "vouchers_used": 25
    },
    "previous_period": {...},
    "changes": {
      "revenue_change": 12.5,
      "transactions_change": 10.0,
      "new_users_change": 25.0,
      "vouchers_change": -5.0
    }
  },
  "month_over_month": {...}
}
```

---

## Analytics Endpoints

### Revenue Analytics

**Endpoint:** `GET /api/portal/analytics/revenue/`

**Query Parameters:**
- `start_date` (optional): ISO datetime
- `end_date` (optional): ISO datetime  
- `group_by` (optional): `hour`, `day`, `week`, `month` (default: `day`)

**Response:**
```json
{
  "success": true,
  "report": {
    "period": {
      "start": "2025-12-07T00:00:00Z",
      "end": "2026-01-06T23:59:59Z",
      "group_by": "day"
    },
    "summary": {
      "total_revenue": 750000,
      "total_transactions": 750,
      "average_transaction": 1000
    },
    "trend": [
      {"period": "2025-12-07", "revenue": 25000, "transactions": 25, "average": 1000}
    ],
    "by_channel": [
      {"channel": "mpesa", "transactions": 500, "revenue": 500000}
    ],
    "by_bundle": [
      {"bundle": "Daily", "sales": 400, "revenue": 400000}
    ]
  }
}
```

### User Analytics

**Endpoint:** `GET /api/portal/analytics/users/`

### Voucher Analytics

**Endpoint:** `GET /api/portal/analytics/vouchers/`

### Export Data

Export data as CSV file.

**Endpoint:** `POST /api/portal/export/`

**Request Body:**
```json
{
  "export_type": "payments",  // payments, users, vouchers
  "start_date": "2025-12-01T00:00:00Z",
  "end_date": "2026-01-06T23:59:59Z",
  "format": "csv"
}
```

**Response:** CSV file download

---

## Router Configuration Wizard

### Step 1: Test Connection

Test connection to a MikroTik router before saving.

**Endpoint:** `POST /api/portal/router/test/`

**Request Body:**
```json
{
  "host": "192.168.1.1",
  "port": 8728,
  "username": "admin",
  "password": "yourpassword",
  "use_ssl": false
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Connection successful!",
  "step": "connected",
  "router_info": {
    "identity": "MikroTik",
    "model": "RB750Gr3",
    "version": "7.10",
    "uptime": "5d 12:30:00",
    "cpu_load": "15%"
  },
  "hotspot_status": {
    "configured": true,
    "servers": [{"name": "server1", "interface": "bridge", "disabled": false}],
    "profiles": ["default", "kitonga"],
    "user_count": 150,
    "active_count": 12
  },
  "recommendations": []
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "Cannot reach 192.168.1.1:8728",
  "step": "connectivity",
  "troubleshooting": [
    "Ensure the router IP is correct",
    "Check that API service is enabled",
    "Verify port 8728 is not blocked"
  ]
}
```

### Step 2: Save Configuration

Save router configuration to database.

**Endpoint:** `POST /api/portal/router/save/`

**Request Body:**
```json
{
  "name": "Main Router",
  "host": "192.168.1.1",
  "port": 8728,
  "username": "admin",
  "password": "yourpassword",
  "use_ssl": false,
  "location_id": 1,
  "hotspot_interface": "bridge",
  "hotspot_profile": "default",
  "description": "Main lobby router"
}
```

### Step 3: Auto-Configure Hotspot (Optional)

Automatically configure hotspot on the router.

**Endpoint:** `POST /api/portal/router/auto-configure/`

**Request Body:**
```json
{
  "router_id": 1,
  "interface": "bridge",
  "server_name": "kitonga-hotspot",
  "profile_name": "kitonga-profile"
}
```

### Generate Hotspot HTML

Generate custom branded hotspot login pages.

**Endpoint:** `GET /api/portal/router/{router_id}/html/`

**Response:**
```json
{
  "success": true,
  "message": "HTML files generated",
  "files": ["login.html", "status.html", "logout.html", "error.html"],
  "instructions": [
    "Connect to router via FTP or Winbox",
    "Navigate to /flash/hotspot/",
    "Upload the generated HTML files"
  ],
  "html_content": {
    "login.html": "<!DOCTYPE html>...",
    "status.html": "<!DOCTYPE html>..."
  }
}
```

### Router Health Check

Check connectivity of all routers.

**Endpoint:** `GET /api/portal/router/health/`

---

## White-Label Customization

### Get Current Branding

**Endpoint:** `GET /api/portal/branding/`

**Response:**
```json
{
  "success": true,
  "branding": {
    "business_name": "My Hotel WiFi",
    "logo_url": "/media/tenant_logos/my-hotel_logo.png",
    "primary_color": "#3B82F6",
    "secondary_color": "#1E40AF",
    "custom_domain": "wifi.myhotel.com",
    "slug": "my-hotel",
    "portal_url": "https://my-hotel.kitonga.klikcell.com"
  }
}
```

### Update Branding Colors

**Endpoint:** `PUT /api/portal/branding/update/`

**Request Body:**
```json
{
  "primary_color": "#10B981",
  "secondary_color": "#059669",
  "business_name": "Green Hotel WiFi"
}
```

### Upload Logo

**Endpoint:** `POST /api/portal/branding/logo/`

**Request:** Multipart form with `logo` file field

### Remove Logo

**Endpoint:** `DELETE /api/portal/branding/logo/remove/`

### Custom Domain Management

**Get Domain Status:**
`GET /api/portal/branding/domain/`

**Set Custom Domain:**
`POST /api/portal/branding/domain/`
```json
{
  "domain": "wifi.myhotel.com"
}
```

**Remove Custom Domain:**
`DELETE /api/portal/branding/domain/`

### Get Theme CSS

**Endpoint:** `GET /api/portal/branding/theme/`

Query parameter `?format=css` to download as CSS file.

### Get Captive Portal Pages

**Endpoint:** `GET /api/portal/branding/captive-portal/`

Returns all branded HTML pages for hotspot login.

---

## Settings Management

### Get/Update Settings

**Endpoint:** `GET/PUT /api/portal/settings/`

### API Keys

**Get API Keys:** `GET /api/portal/api-keys/`

**Regenerate:** `POST /api/portal/api-keys/regenerate/`

---

## Staff Management

### List/Invite Staff

**Endpoint:** `GET/POST /api/portal/staff/`

**Invite Request:**
```json
{
  "email": "staff@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "role": "manager",
  "can_manage_routers": true,
  "can_manage_users": true,
  "can_manage_payments": true,
  "can_manage_vouchers": true,
  "can_view_reports": true,
  "can_manage_staff": false,
  "can_manage_settings": false
}
```

### Staff Detail

**Endpoint:** `GET/PUT/DELETE /api/portal/staff/{staff_id}/`

---

## Location Management

### List/Create Locations

**Endpoint:** `GET/POST /api/portal/locations/`

### Location Detail

**Endpoint:** `GET/PUT/DELETE /api/portal/locations/{location_id}/`

---

## Bundle Management

### List/Create Bundles

**Endpoint:** `GET/POST /api/portal/bundles/`

**Create Request:**
```json
{
  "name": "Weekly Special",
  "duration_hours": 168,
  "price": 5000,
  "description": "7 days of unlimited WiFi",
  "is_active": true,
  "display_order": 2
}
```

### Bundle Detail

**Endpoint:** `GET/PUT/DELETE /api/portal/bundles/{bundle_id}/`

---

## Error Responses

All endpoints return consistent error responses:

```json
{
  "success": false,
  "message": "Error description",
  "errors": {
    "field_name": ["Error message"]
  }
}
```

## Rate Limiting

API endpoints are rate limited to:
- 100 requests per minute for authenticated requests
- 20 requests per minute for unauthenticated requests

## Subscription Limits

Features are limited based on subscription plan:

| Feature | Starter | Business | Enterprise |
|---------|---------|----------|------------|
| Custom Branding | ❌ | ✅ | ✅ |
| Custom Domain | ❌ | ❌ | ✅ |
| Max Routers | 1 | 5 | Unlimited |
| Max Locations | 1 | 3 | Unlimited |
| Max Staff | 2 | 5 | Unlimited |
| Analytics | Basic | Full | Full + Export |
