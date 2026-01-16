# Payment Flow Fixes - WiFi Connection After Payment

## Problem Statement

Users were experiencing issues where:

1. **Payment completed but WiFi not connected** - Users would pay via mobile money but not get internet access
2. **No hotspot user created** - The MikroTik router didn't know about the user
3. **Router unknown** - System didn't know which router the user was connected to
4. **Tenant isolation broken** - Multi-tenant SaaS couldn't properly isolate users

## Root Causes Identified

### 1. Missing Router ID from Captive Portal

The MikroTik captive portal login page wasn't passing the `router_id` parameter to the backend API when users initiated payments. Without this, the system couldn't determine which router to create hotspot users on.

### 2. Payment Initiated Without Router Context

The `initiate_payment()` endpoint was receiving payment requests without knowing which router the user was connected to. This meant:

- No tenant context
- No way to know where to create the hotspot user
- Payment was recorded but disconnected from router

### 3. Webhook Couldn't Target Specific Router

When ClickPesa sent payment confirmation, the webhook had no way to know which router to authorize the user on. It would fall back to authorizing on ALL tenant routers (inefficient) or fail silently.

### 4. MAC Address Not Always Captured

The user's device MAC address wasn't being reliably passed from captive portal to backend, making IP binding creation impossible.

## Fixes Implemented

### Fix 1: Enhanced `initiate_payment()` in `views.py`

**Location:** `billing/views.py` - `initiate_payment()` function

**Change:** Now properly looks up and saves the Router object to the Payment record.

```python
# Get router if provided (CRITICAL for multi-tenant SaaS)
router_id = request.data.get("router_id")
payment_router = None
if router_id:
    try:
        from .models import Router
        payment_router = Router.objects.get(id=router_id, is_active=True)
        logger.info(f"Payment initiated with router_id={router_id}, router={payment_router.name}, tenant={payment_router.tenant.slug if payment_router.tenant else 'N/A'}")
    except Router.DoesNotExist:
        logger.warning(f"Router ID {router_id} not found or inactive")
```

And later saves it:

```python
payment = Payment.objects.create(
    user=user,
    amount=bundle.price,
    bundle=bundle,
    phone_number=user.phone_number,
    status="pending",
    metadata=payment_metadata,
    tenant=user.tenant,
    router=payment_router,  # CRITICAL: Save router for webhook to use
)
```

### Fix 2: Updated ClickPesa Webhook in `views.py`

**Location:** `billing/views.py` - `clickpesa_webhook()` function

**Change:** Now checks for `payment.router` first and authorizes on that specific router.

```python
# CRITICAL: Use the router saved during payment initiation
# This ensures we authorize on the EXACT router the user is connected to
payment_router = getattr(payment, 'router', None)

if payment_router:
    # Authorize ONLY on the specific router where payment was initiated
    logger.info(f"✓ Using payment.router ({payment_router.name}) for access grant")
    access_result = authorize_user_on_specific_router(
        user=user,
        router_id=payment_router.id,
        mac_address=mac_address,
        ip_address=ip_address,
        access_type="payment",
    )
elif user.tenant:
    # Fallback: authorize on ALL tenant routers
    access_result = force_immediate_internet_access_on_tenant_routers(...)
```

### Fix 3: Enhanced Captive Portal `login.html`

**Location:** `hotspot_html/login.html`

**Changes:**

1. **Improved `getRouterId()` function:**

```javascript
function getRouterId() {
  const params = getParams()
  // Support multiple parameter names that MikroTik might use
  return params['router_id'] || params['router-id'] || params['routerid'] || params['rid'] || params['r'] || null
}
```

2. **Added `getTenantSlug()` function:**

```javascript
function getTenantSlug() {
  const params = getParams()
  return params['tenant'] || params['tenant_slug'] || null
}
```

3. **Enhanced `buildPortalUrl()` to include router_id:**

```javascript
function buildPortalUrl(basePath) {
  let url = MAIN_PORTAL_URL + basePath + '?ip=' + encodeURIComponent(ip) + '&mac=' + encodeURIComponent(mac)

  if (routerId) {
    url += '&router_id=' + encodeURIComponent(routerId)
  }
  if (tenant) {
    url += '&tenant=' + encodeURIComponent(tenant)
  }
  return url
}
```

4. **Enhanced `verifyUserAccess()` to pass router_id:**

```javascript
const requestBody = {
  phone_number: phone,
  mac_address: mac,
  ip_address: ip
}

if (routerId) {
  requestBody.router_id = parseInt(routerId, 10)
  console.log('📡 Router ID:', routerId, '- Using for tenant isolation')
}
```

## MikroTik Configuration Required

For the fixes to work, each tenant must configure their MikroTik router's hotspot profile to pass the `router_id` parameter in the login URL.

### Setting Up Login URL with Router ID

1. **In MikroTik Terminal:**

```
/ip hotspot profile set [find name="hsprof1"] login-url="https://api.kitonga.klikcell.com/hotspot/login.html?router_id=YOUR_ROUTER_ID"
```

2. **Via WinBox:**

   - Go to IP → Hotspot → Server Profiles
   - Edit your profile (e.g., `hsprof1`)
   - Set **Login URL** to: `https://api.kitonga.klikcell.com/hotspot/login.html?router_id=YOUR_ROUTER_ID`

3. **Important MikroTik Variables:**
   MikroTik automatically appends these variables to the login URL:

   - `$(mac)` - User's MAC address
   - `$(ip)` - User's IP address
   - `$(username)` - Username (if any)

   So the full URL becomes:

   ```
   https://api.kitonga.klikcell.com/hotspot/login.html?router_id=5&mac=AA:BB:CC:DD:EE:FF&ip=192.168.88.100
   ```

### Finding Your Router ID

The router ID is found in the Kitonga admin panel:

1. Login to admin portal at `https://kitonga.klikcell.com/admin/`
2. Go to **Billing → Routers**
3. Your router ID is shown in the first column of the list

### Example Complete Setup

For a router with ID `5`:

```
# Set login URL with router_id
/ip hotspot profile set [find name="hsprof1"] login-url="https://api.kitonga.klikcell.com/hotspot/login.html?router_id=5"

# Ensure HTML directory is properly set (optional, for custom pages)
/ip hotspot profile set [find name="hsprof1"] html-directory=hotspot

# Set login-by to HTTP CHAP for security
/ip hotspot profile set [find name="hsprof1"] login-by=http-chap
```

## Testing the Fix

### 1. Verify Router ID is Passed

On the captive portal page, open browser developer console (F12) and check:

```javascript
console.log(getRouterId()) // Should show your router ID
```

### 2. Test Payment Flow

1. Connect to WiFi hotspot
2. Open captive portal
3. Enter phone number and select bundle
4. Initiate payment
5. Check server logs for: `Payment initiated with router_id=X, router=RouterName`

### 3. Verify After Payment

After successful payment, check logs for:

```
✓ Using payment.router (RouterName) for access grant
✓ Hotspot user created on RouterName for +255XXXXXXXXX
✓ IP binding created on RouterName for XX:XX:XX:XX:XX:XX
```

## System Architecture

### Frontend Portal

- **URL:** `https://kitonga.klikcell.com/portal/`
- **Purpose:** User-facing portal for bundle selection, payment, and account management
- **Features:** Welcome screen, bundle listing, payment initiation, status checking

### Backend API

- **URL:** `https://api.kitonga.klikcell.com/api/`
- **Purpose:** REST API for all backend operations

### Captive Portal Login Page

- **URL:** Served by MikroTik, hosted at `https://api.kitonga.klikcell.com/hotspot/login.html`
- **Purpose:** Initial login page shown when user connects to WiFi

## Complete Payment Flow

```
[User connects to WiFi hotspot]
    ↓
[MikroTik shows Captive Portal]
    → login.html?router_id=X&mac=XX:XX:XX:XX:XX:XX&ip=192.168.x.x
    ↓
[User enters phone number on login.html]
    ↓
[User clicks "Register/Buy Bundle"]
    ↓
[Opens Frontend Portal]
    → https://kitonga.klikcell.com/portal?ip=...&mac=...&router_id=X
    ↓
[User selects bundle and initiates payment]
    ↓
[Frontend calls Backend API]
    POST https://api.kitonga.klikcell.com/api/initiate-payment/
    {phone_number, bundle_id, router_id, mac_address}
    → Creates Payment with router FK
    ↓
[ClickPesa sends USSD push to user's phone]
    ↓
[User confirms payment on phone]
    ↓
[ClickPesa sends webhook to Backend]
    POST https://api.kitonga.klikcell.com/api/clickpesa/webhook/
    → Finds Payment with router
    → Calls authorize_user_on_specific_router(router_id=payment.router.id)
    → Creates hotspot user on that specific router
    → Creates IP binding for MAC address
    ↓
[User gets internet access immediately]
```

## Troubleshooting

### User paid but no internet access

1. **Check Payment record:**

```sql
SELECT id, status, router_id FROM billing_payment WHERE phone_number='...' ORDER BY created_at DESC LIMIT 1;
```

2. **If router_id is NULL:** The captive portal isn't passing router_id. Check MikroTik login-url configuration.

3. **Check server logs:** Look for authorization messages after webhook.

### Hotspot user not created

1. **Verify router credentials:** Check Router.host, Router.username, Router.api_password
2. **Test router connection:** Use the router test endpoint
3. **Check router API status:** MikroTik API must be enabled (port 8728)

### Tenant mismatch error

If you see "tenant_mismatch" error:

- User belongs to one tenant but connected to another tenant's router
- This is a security feature - each tenant's users can only use their own routers

## Files Modified

1. `billing/views.py`

   - `initiate_payment()` - Now saves router to payment
   - `clickpesa_webhook()` - Now uses payment.router for authorization

2. `hotspot_html/login.html`
   - `getRouterId()` - Enhanced to check multiple parameter names
   - `getTenantSlug()` - New function for tenant identification
   - `buildPortalUrl()` - Now includes router_id and tenant parameters
   - `verifyUserAccess()` - Now passes router_id to /verify/ endpoint

## Related Functions

- `authorize_user_on_specific_router()` - Creates hotspot user on specific router
- `force_immediate_internet_access_on_tenant_routers()` - Fallback for all tenant routers
- `create_hotspot_user_on_router()` - Low-level RouterOS API call
- `allow_mac_on_router()` - Creates IP binding for MAC address bypass
