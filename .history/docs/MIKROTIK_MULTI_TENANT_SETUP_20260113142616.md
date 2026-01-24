# MikroTik Multi-Tenant Hotspot Setup Guide

This guide explains how to configure MikroTik routers to work with Kitonga's multi-tenant WiFi billing system.

## Prerequisites

1. Router registered in Kitonga admin panel (you'll get a `router_id`)
2. MikroTik RouterOS 6.x or 7.x
3. Hotspot configured and working

## Step 1: Get Your Router ID

1. Login to Kitonga Admin Portal
2. Go to **Routers** section
3. Find your router and note the **Router ID** (e.g., `5`)

## Step 2: Upload Hotspot HTML Files

Upload the following files to your MikroTik router's `/hotspot` directory:

```
/hotspot/
├── login.html      # Main login page
├── logout.html     # Logout confirmation page
├── status.html     # Connection status page
├── error.html      # Error page
├── alogin.html     # Auto-login page (optional)
└── rlogin.html     # Redirect login (optional)
```

### Using Winbox:
1. Open Winbox and connect to your router
2. Go to **Files**
3. Navigate to `/hotspot` folder
4. Drag and drop the HTML files

### Using SCP (command line):
```bash
scp hotspot_html/*.html admin@192.168.88.1:/hotspot/
```

## Step 3: Configure Hotspot to Pass Router ID

The critical step is configuring MikroTik to pass the `router-id` parameter to the captive portal.

### Option A: Using Login Page Variables (Recommended)

Edit your hotspot server profile to include the router ID in the login URL:

```routeros
# Set your router ID (get this from Kitonga admin panel)
:local routerId "5"

# Configure hotspot login URL with router-id
/ip hotspot profile set [find name=hsprof1] \
    login-by=http-chap \
    html-directory=hotspot \
    http-cookie-lifetime=1d \
    login-page="login.html?router-id=$routerId"
```

### Option B: Modify HTML to Include Router ID

If you can't modify the profile, hardcode the router ID in login.html:

```javascript
// At the top of the script section in login.html
var ROUTER_ID = '5';  // <-- Replace with your actual router ID
```

### Option C: Use Router Identity

You can use the router's identity name and map it in your backend:

```routeros
# Set router identity
/system identity set name="hotel-abc-lobby"

# The $(identity) variable will be passed to login page
```

Then in login.html, the router identity is available as `$(identity)`.

## Step 4: Configure Walled Garden

Allow access to Kitonga API and portal before authentication:

```routeros
/ip hotspot walled-garden
add dst-host=api.kitonga.klikcell.com action=allow comment="Kitonga API"
add dst-host=kitonga.klikcell.com action=allow comment="Kitonga Portal"
add dst-host=*.clickpesa.com action=allow comment="ClickPesa Payment Gateway"
```

For IP-based walled garden (more reliable):

```routeros
/ip hotspot walled-garden ip
add dst-address=0.0.0.0/0 dst-port=443 protocol=tcp action=allow comment="HTTPS"
add dst-address=0.0.0.0/0 dst-port=80 protocol=tcp action=allow comment="HTTP"
```

## Step 5: Complete Hotspot Profile Configuration

```routeros
/ip hotspot profile
set [find name=hsprof1] \
    hotspot-address=192.168.88.1 \
    dns-name=wifi.local \
    html-directory=hotspot \
    login-by=http-chap \
    http-cookie-lifetime=3d \
    split-user-domain=no \
    use-radius=no
```

## Step 6: Hotspot Server Configuration

```routeros
/ip hotspot
set [find] \
    address-pool=dhcp_pool1 \
    profile=hsprof1 \
    idle-timeout=5m \
    keepalive-timeout=2m
```

## MikroTik Variables Reference

These variables are automatically passed by MikroTik to your login page:

| Variable | Description | Example |
|----------|-------------|---------|
| `$(mac)` | Client MAC address | `AA:BB:CC:DD:EE:FF` |
| `$(ip)` | Client IP address | `192.168.88.100` |
| `$(username)` | Username (if known) | `255712345678` |
| `$(link-login)` | Login form action URL | `http://192.168.88.1/login` |
| `$(link-orig)` | Original destination URL | `http://google.com` |
| `$(error)` | Error message | `invalid username or password` |
| `$(chap-id)` | CHAP ID for authentication | `\371` |
| `$(chap-challenge)` | CHAP challenge | `\357\241...` |
| `$(identity)` | Router identity name | `hotel-abc-lobby` |

## Complete Flow Diagram

```
User connects to WiFi
        │
        ▼
┌───────────────────────┐
│ MikroTik Hotspot      │
│ Intercepts traffic    │
│ Redirects to login    │
│ Adds: mac, ip,        │
│ router-id, link-login │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ login.html            │
│ Extracts params       │
│ Shows login form      │
└───────────┬───────────┘
            │
            ▼ User enters phone
┌───────────────────────┐
│ POST /api/verify/     │
│ {phone, mac, ip,      │
│  router_id: 5}        │
└───────────┬───────────┘
            │
    ┌───────┴───────┐
    │               │
    ▼ Has Access    ▼ No Access
┌──────────┐   ┌──────────────┐
│Submit to │   │Redirect to   │
│MikroTik  │   │portal with   │
│login     │   │router_id     │
└──────────┘   └──────────────┘
    │               │
    ▼               ▼
Connected!     Buy Bundle
               (tenant-specific)
```

## Troubleshooting

### Router ID Not Being Passed

1. Check browser console for errors
2. Enable `DEBUG_MODE = true` in login.html
3. Verify URL contains `router-id` parameter

### Can't Access Payment Portal

1. Check walled garden configuration
2. Test: `ping api.kitonga.klikcell.com` from router
3. Verify DNS resolution works

### User Authenticated But No Internet

1. Check if user exists in MikroTik hotspot users
2. Verify IP binding was created
3. Check firewall rules

### Wrong Tenant Bundles Showing

1. Verify `router_id` is correct in login.html
2. Check router is assigned to correct tenant in admin
3. Test API: `GET /api/bundles/?router_id=5`

## Testing the Setup

1. Connect a device to the WiFi
2. Open browser - should redirect to login.html
3. Check URL has `router-id` parameter
4. Enter phone number and click "Register"
5. Portal should show tenant-specific bundles
6. Complete payment
7. Device should get internet access

## Security Considerations

1. **HTTPS**: Always use HTTPS for API calls
2. **Walled Garden**: Only whitelist necessary domains
3. **Router Credentials**: Store securely, never in HTML
4. **Rate Limiting**: Consider limiting login attempts
