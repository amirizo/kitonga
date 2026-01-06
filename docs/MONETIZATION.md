# Kitonga SaaS Monetization Guide

## ✅ Phase 2: Monetization - COMPLETED

This document describes the monetization features of the Kitonga SaaS platform.

## Revenue Streams

### 1. Subscription Payments (Primary Revenue)

Tenants pay monthly/yearly subscription fees via ClickPesa (Mobile Money):

| Plan | Monthly | Yearly | Savings |
|------|---------|--------|---------|
| **Starter** | TZS 30,000 | TZS 300,000 | 17% |
| **Business** | TZS 60,000 | TZS 600,000 | 17% |
| **Enterprise** | TZS 120,000 | TZS 1,200,000 | 17% |

### 2. Revenue Sharing (Secondary Revenue)

Platform takes a percentage of WiFi payments made by end-users:

| Plan | Revenue Share |
|------|---------------|
| **Starter** | 5% |
| **Business** | 3% |
| **Enterprise** | 2% |

**Example:** If a Starter tenant earns TZS 1,000,000/month from WiFi payments:
- Platform share: TZS 50,000
- Tenant keeps: TZS 950,000

---

## Subscription API Endpoints

### Public Endpoints

#### List Subscription Plans
```http
GET /api/saas/plans/
```

Response:
```json
{
  "success": true,
  "plans": [
    {
      "id": 1,
      "name": "starter",
      "display_name": "Starter",
      "monthly_price": 30000.00,
      "yearly_price": 300000.00,
      "currency": "TZS",
      "max_routers": 1,
      "max_vouchers_per_month": 100,
      "features": {
        "custom_branding": false,
        "api_access": false,
        "priority_support": false
      }
    }
  ],
  "currency": "TZS",
  "payment_methods": ["M-Pesa", "Tigo Pesa", "Airtel Money", "Bank Transfer"]
}
```

#### Register New Tenant
```http
POST /api/saas/register/
Content-Type: application/json

{
  "business_name": "Hotel WiFi",
  "business_email": "info@hotel.com",
  "business_phone": "+255712345678",
  "admin_email": "admin@hotel.com",
  "admin_password": "securepassword123",
  "plan_id": 1
}
```

Response:
```json
{
  "success": true,
  "message": "Registration successful! Your 14-day trial has started.",
  "tenant": {
    "id": "uuid-here",
    "slug": "hotel-wifi",
    "api_key": "abc123...",
    "trial_ends_at": "2026-01-20T00:00:00Z"
  }
}
```

---

### Tenant Endpoints (Requires X-API-Key)

#### Tenant Dashboard
```http
GET /api/saas/dashboard/
X-API-Key: <tenant_api_key>
```

Response:
```json
{
  "success": true,
  "tenant": { ... },
  "subscription": {
    "is_valid": true,
    "days_remaining": 25,
    "plan": {
      "name": "business",
      "display_name": "Business"
    }
  },
  "usage": {
    "routers": { "used": 2, "limit": 3, "percentage": 66.7 },
    "vouchers_this_month": { "used": 150, "limit": "Unlimited" }
  },
  "revenue_this_month": {
    "total_revenue": 500000.00,
    "platform_share": 15000.00,
    "tenant_share": 485000.00
  }
}
```

#### Get Usage Details
```http
GET /api/saas/usage/
X-API-Key: <tenant_api_key>
```

#### Create Subscription Payment
```http
POST /api/saas/subscribe/
X-API-Key: <tenant_api_key>
Content-Type: application/json

{
  "plan_id": 2,
  "billing_cycle": "monthly"
}
```

Response:
```json
{
  "success": true,
  "payment_id": 123,
  "transaction_id": "SUB-hotel-wifi-A1B2C3D4",
  "amount": 60000.00,
  "currency": "TZS",
  "checkout_url": "https://clickpesa.com/checkout/...",
  "period_start": "2026-02-01T00:00:00Z",
  "period_end": "2026-03-01T00:00:00Z"
}
```

#### View Subscription History
```http
GET /api/saas/subscription-history/
X-API-Key: <tenant_api_key>
```

#### View Revenue Report
```http
GET /api/saas/revenue/?year=2026&month=1
X-API-Key: <tenant_api_key>
```

---

### Platform Admin Endpoints (Super Admin Only)

#### Platform Dashboard
```http
GET /api/platform/dashboard/
Authorization: Token <admin_token>
```

Response:
```json
{
  "success": true,
  "tenants": {
    "total": 45,
    "active": 32,
    "trial": 8,
    "expiring_soon": 5
  },
  "revenue_this_month": {
    "subscription_payments": 1500000.00,
    "wifi_payments_total": 5000000.00,
    "platform_revenue_share": 175000.00,
    "total_platform_revenue": 1675000.00
  }
}
```

#### List All Tenants
```http
GET /api/platform/tenants/?status=active&page=1
Authorization: Token <admin_token>
```

#### Manage Specific Tenant
```http
GET /api/platform/tenants/<tenant_id>/
PUT /api/platform/tenants/<tenant_id>/
Authorization: Token <admin_token>
```

#### Platform Revenue Report
```http
GET /api/platform/revenue/?year=2026&month=1
Authorization: Token <admin_token>
```

---

## Usage Limits & Enforcement

The system automatically enforces usage limits based on subscription plan:

### Limit Checks

Before creating resources, the system checks:

| Resource | Check Method | Error Message |
|----------|--------------|---------------|
| Routers | `can_add_router()` | "Router limit reached (X). Upgrade your plan." |
| WiFi Users | `can_add_wifi_user()` | "WiFi user limit reached. Upgrade your plan." |
| Vouchers | `can_create_voucher()` | "Monthly voucher limit reached (X)." |
| Locations | `can_add_location()` | "Location limit reached." |
| Staff | `can_add_staff()` | "Staff account limit reached." |

### Subscription Validity

Resources are only usable if subscription is valid:
- Active subscription with `subscription_ends_at > now`
- OR Trial with `trial_ends_at > now`

---

## Automated Tasks (Cron Jobs)

### Daily Subscription Tasks

Run daily at 6 AM:

```bash
# crontab entry
0 6 * * * cd /path/to/kitonga && python manage.py subscription_tasks
```

### Tasks Performed:

1. **Expiry Reminders** - Send SMS 7 days before subscription expires
2. **Suspend Expired** - Set `subscription_status='suspended'` for expired subscriptions
3. **Expire Trials** - Handle trial period expirations

### Manual Execution:

```bash
# Run all tasks
python manage.py subscription_tasks

# Only send reminders
python manage.py subscription_tasks --reminders-only

# Only suspend expired
python manage.py subscription_tasks --suspend-only

# Only handle trials
python manage.py subscription_tasks --trials-only
```

---

## Payment Flow

### Subscription Payment Flow

```
1. Tenant visits /api/saas/plans/ → See available plans
2. Tenant calls POST /api/saas/subscribe/ with plan_id
3. System creates TenantSubscriptionPayment (pending)
4. System calls ClickPesa API → Returns checkout URL
5. Tenant completes payment on ClickPesa
6. ClickPesa calls POST /api/saas/webhook/
7. System activates subscription
8. SMS confirmation sent to tenant
```

### ClickPesa Webhook Payload

```json
{
  "payment_status": "PAYMENT RECEIVED",
  "external_reference": "SUB-hotel-wifi-A1B2C3D4",
  "order_reference": "CP123456789",
  "channel": "MPESA",
  "amount": 60000
}
```

---

## SMS Notifications

### Subscription SMS Templates

**Welcome SMS (Registration):**
```
Welcome to Kitonga!
Your business: {business_name}
Trial ends: {date}
Login: https://app.kitonga.com
API Key: {api_key_preview}...
```

**Payment Confirmation:**
```
Kitonga Subscription Confirmed!
Plan: {plan_name}
Amount: TZS {amount}
Valid until: {end_date}
Thank you for choosing Kitonga!
```

**Expiry Reminder (7 days):**
```
Kitonga Subscription Reminder
Your {plan_name} plan expires in {days} days.
Renew now to avoid service interruption.
Amount: TZS {price}/month
```

**Subscription Expired:**
```
Kitonga Subscription Expired
Your subscription has expired. WiFi services are now limited.
Please renew to restore full access.
Contact: support@kitonga.com
```

---

## Integration with Existing System

### Modified Models

All existing models now support tenant filtering:

```python
# Example: Get WiFi users for a tenant
users = User.objects.filter(tenant=request.tenant)

# Get payments for a tenant
payments = Payment.objects.filter(tenant=request.tenant)

# Get vouchers for a tenant
vouchers = Voucher.objects.filter(tenant=request.tenant)
```

### Middleware Integration

The `TenantMiddleware` automatically:
1. Resolves tenant from X-API-Key header
2. Sets `request.tenant` for all views
3. Validates subscription before allowing access

---

## Revenue Calculation Example

### Monthly Revenue Report for Tenant

```python
from billing.subscription import RevenueCalculator

calc = RevenueCalculator(tenant)
report = calc.get_monthly_revenue_report(year=2026, month=1)

# Result:
{
  'tenant': 'Hotel WiFi',
  'period': '2026-01',
  'total_payments': 150,
  'total_revenue': 500000.00,
  'revenue_share_percentage': 3.0,
  'platform_share': 15000.00,
  'tenant_share': 485000.00,
  'currency': 'TZS'
}
```

### Platform Revenue Report

```python
# Aggregate across all tenants
GET /api/platform/revenue/?year=2026&month=1

{
  'subscription_revenue': {
    'total': 1500000.00,
    'count': 35
  },
  'revenue_share': {
    'total_platform_share': 175000.00,
    'by_tenant': [
      {'tenant': 'Big Hotel', 'platform_share': 50000.00},
      {'tenant': 'Cafe Net', 'platform_share': 25000.00}
    ]
  },
  'total_platform_revenue': 1675000.00
}
```

---

## Files Created/Modified

### New Files

| File | Description |
|------|-------------|
| `billing/subscription.py` | Subscription management, usage metering, revenue calculation |
| `billing/management/commands/subscription_tasks.py` | Daily cron job for subscription management |

### Modified Files

| File | Changes |
|------|---------|
| `billing/serializers.py` | Added SaaS serializers (plans, tenants, payments, routers) |
| `billing/views.py` | Added 15+ new subscription/platform API endpoints |
| `billing/urls.py` | Added subscription and platform URL routes |

---

## Testing the Monetization System

### 1. Create Subscription Plans

```bash
python manage.py setup_saas
```

### 2. Register a Test Tenant

```bash
curl -X POST http://localhost:8000/api/saas/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "business_name": "Test Hotel",
    "business_email": "test@hotel.com",
    "business_phone": "+255712345678",
    "admin_email": "admin@test.com",
    "admin_password": "testpass123"
  }'
```

### 3. Check Dashboard

```bash
curl http://localhost:8000/api/saas/dashboard/ \
  -H "X-API-Key: <returned_api_key>"
```

### 4. Create Subscription Payment

```bash
curl -X POST http://localhost:8000/api/saas/subscribe/ \
  -H "X-API-Key: <api_key>" \
  -H "Content-Type: application/json" \
  -d '{"plan_id": 2, "billing_cycle": "monthly"}'
```

---

## Summary

Phase 2 Monetization is now complete with:

- ✅ **Subscription Payment Flow** via ClickPesa
- ✅ **Usage Metering** with limit enforcement
- ✅ **Revenue Sharing** calculation (platform percentage)
- ✅ **Automated Subscription Management** (reminders, suspensions)
- ✅ **Platform Admin Dashboard** for super admin
- ✅ **Tenant Dashboard** with usage and revenue stats
- ✅ **SMS Notifications** for subscription events
