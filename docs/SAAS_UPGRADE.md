# Kitonga SaaS Platform - Multi-Tenant Upgrade

## ✅ COMPLETED - Phase 1: Multi-Tenant Foundation
## ✅ COMPLETED - Phase 2: Monetization

This document describes the upgrade of Kitonga from a single-tenant WiFi billing system to a **multi-tenant SaaS platform** that can be sold to hotspot operators.

## Summary of Changes

### 1. New SaaS Models (`billing/models.py`)

| Model | Description |
|-------|-------------|
| `SubscriptionPlan` | SaaS subscription tiers (Starter, Business, Enterprise) |
| `Tenant` | Represents a hotspot business/customer |
| `TenantStaff` | Staff members with role-based permissions per tenant |
| `Location` | Physical locations for multi-site businesses |
| `Router` | MikroTik router configurations per tenant |
| `TenantSubscriptionPayment` | Track subscription payments from tenants |

### 2. Modified Existing Models

All existing models now include a `tenant` foreign key:

| Model | Changes |
|-------|---------|
| `Bundle` | Added `tenant`, `currency` fields |
| `WifiUser` (was `User`) | Added `tenant`, `name`, `email`, `total_amount_paid`, `primary_router` |
| `Device` | Added `tenant`, `router`, `device_type` |
| `Payment` | Added `tenant`, `router`, refunded status |
| `AccessLog` | Added `tenant`, `router` |
| `Voucher` | Added `tenant`, `bundle`, `used_on_router`, more duration options |
| `SMSLog` | Added `tenant` |
| `PaymentWebhook` | Added `tenant` |

### 3. Tenant Middleware (`billing/middleware.py`)

New middleware for tenant resolution:
- `TenantMiddleware` - Resolves tenant from subdomain, API key, or query param
- `get_current_tenant()` / `set_current_tenant()` - Thread-local tenant access

### 4. Admin Interface (`billing/admin.py`)

Enhanced Django admin with:
- SaaS management section (Plans, Tenants, Staff, Routers)
- Tenant filtering on all existing models
- Improved status badges and displays

### 5. Management Commands

| Command | Description |
|---------|-------------|
| `python manage.py setup_saas` | Create subscription plans |
| `python manage.py setup_saas --create-tenant` | Also create default tenant |
| `python manage.py migrate_to_tenant --tenant-slug=default` | Migrate existing data |

## Subscription Plans

| Plan | Price/Month | Routers | Vouchers/Month | Features |
|------|-------------|---------|----------------|----------|
| **Starter** | TZS 30,000 | 1 | 100 | Basic analytics, SMS |
| **Business** | TZS 60,000 | 3 | Unlimited | + Custom branding, Priority support |
| **Enterprise** | TZS 120,000 | Unlimited | Unlimited | + White-label, API access, Custom domain |

**Payment via ClickPesa** (Mobile Money: M-Pesa, Tigo Pesa, Airtel Money)

## Migration Steps

### Step 1: Install new dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Create database migrations
```bash
python manage.py makemigrations billing
python manage.py migrate
```

### Step 3: Set up SaaS plans and default tenant
```bash
python manage.py setup_saas --create-tenant
```

### Step 4: Migrate existing data to default tenant
```bash
# Preview what will be migrated
python manage.py migrate_to_tenant --dry-run

# Actually migrate
python manage.py migrate_to_tenant
```

## Tenant Resolution

Tenants are identified by (in order of priority):

1. **API Key** - Header: `X-API-Key: <tenant_api_key>`
2. **Query Parameter** - `?tenant=<slug>` (for testing)
3. **Subdomain** - `hotel.kitonga.com` → tenant slug "hotel"
4. **Custom Domain** - `wifi.hotel.com` → tenant with matching custom_domain

## API Changes

All API endpoints now support tenant context:

```bash
# Using API key (recommended for production)
curl -H "X-API-Key: abc123..." https://api.kitonga.com/api/bundles/

# Using query parameter (for testing)
curl https://api.kitonga.com/api/bundles/?tenant=hotel

# Using subdomain
curl https://hotel.kitonga.com/api/bundles/
```

## Next Steps

### Phase 3: Tenant Portal
- [ ] Tenant self-service dashboard
- [ ] Router configuration wizard
- [ ] Analytics and reporting
- [ ] White-label customization UI

### Phase 4: Advanced Features
- [ ] Tenant mobile app / PWA
- [ ] Multi-language support
- [ ] Email notifications
- [ ] Webhook notifications for tenants

## Database Schema

```
┌─────────────────────────────────────────────────────────┐
│                  SubscriptionPlan                        │
│  (starter, business, enterprise)                        │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                      Tenant                              │
│  (hotspot business - your customer)                     │
├─────────────────────────────────────────────────────────┤
│ - slug (subdomain)                                      │
│ - business_name, email, phone                           │
│ - subscription_plan, status                             │
│ - branding (logo, colors)                               │
│ - payment gateway credentials                           │
│ - API key/secret                                        │
└─────────┬───────────────┬───────────────┬──────────────┘
          │               │               │
          ▼               ▼               ▼
    ┌──────────┐   ┌───────────┐   ┌───────────┐
    │  Router  │   │  Bundle   │   │ TenantStaff│
    └────┬─────┘   └─────┬─────┘   └───────────┘
         │               │
         ▼               ▼
    ┌──────────┐   ┌───────────┐
    │ WifiUser │◄──┤  Payment  │
    └────┬─────┘   └───────────┘
         │
         ▼
    ┌──────────┐
    │  Device  │
    └──────────┘
```
