# 🔗 COMPLETE MIKROTIK-DJANGO INTEGRATION COMMANDS

## 🎯 GOAL: Connect MikroTik to Your Django WiFi Billing System

Your Django system is already configured with:
- ✅ ClickPesa payment gateway
- ✅ NextSMS notifications  
- ✅ User management and bundles
- ✅ MikroTik authentication API (`/api/mikrotik/auth/`)

Now we need to configure MikroTik to work with it.

## 🚀 STEP-BY-STEP INTEGRATION COMMANDS

### PHASE 1: Basic Network Setup

```routeros
# 1. Configure internet connection (CRITICAL FIRST STEP)
/ip dhcp-client add interface=ether1 disabled=no

# 2. Wait 30 seconds, then check if you got IP from main router
/ip dhcp-client print

# 3. Set IP address for WiFi clients
/ip address add address=192.168.88.1/24 interface=bridge-local

# 4. Configure DNS servers
/ip dns set allow-remote-requests=yes servers=8.8.8.8,1.1.1.1

# 5. Enable internet sharing (NAT)
/ip firewall nat add chain=srcnat out-interface=ether1 action=masquerade

# 6. Test internet connectivity
/ping 8.8.8.8 count=3
```

### PHASE 2: WiFi Configuration

```routeros
# 1. Configure WiFi as Access Point
/interface wireless set wlan1 disabled=no mode=ap-bridge ssid="Kitonga WiFi" band=2ghz-b/g/n

# 2. Set WiFi password
/interface wireless security-profiles set default authentication-types=wpa2-psk wpa2-pre-shared-key="kitonga2025"

# 3. Add WiFi to bridge
/interface bridge port add bridge=bridge-local interface=wlan1

# 4. Verify WiFi is running
/interface wireless print
```

### PHASE 3: DHCP Server for WiFi Clients

```routeros
# 1. Create DHCP pool for WiFi clients
/ip pool add name=dhcp-pool ranges=192.168.88.10-192.168.88.100

# 2. Create DHCP server
/ip dhcp-server add address-pool=dhcp-pool interface=bridge-local name=dhcp-server

# 3. Configure DHCP network settings
/ip dhcp-server network add address=192.168.88.0/24 gateway=192.168.88.1 dns-server=8.8.8.8
```

### PHASE 4: Hotspot Setup (Critical for Django Integration)

```routeros
# 1. Create hotspot user profile
/ip hotspot user profile add name=kitonga-profile idle-timeout=none keepalive-timeout=2m session-timeout=24h

# 2. Create hotspot server profile
/ip hotspot profile add name=kitonga-hotspot-profile html-directory=hotspot login-by=cookie,http-chap use-radius=no

# 3. Create hotspot server
/ip hotspot add interface=bridge-local address-pool=dhcp-pool profile=kitonga-hotspot-profile name=kitonga-hotspot

# 4. Verify hotspot is created
/ip hotspot print
```

### PHASE 5: Django Integration - Walled Garden

```routeros
# Allow access to your Django API and payment systems
/ip hotspot walled-garden add dst-host=api.kitonga.klikcell.com comment="Django API Server"
/ip hotspot walled-garden add dst-host=kitonga.klikcell.com comment="Django Frontend"
/ip hotspot walled-garden add dst-host=*.clickpesa.com comment="ClickPesa Payment"
/ip hotspot walled-garden add dst-host=*.messaging-service.co.tz comment="NextSMS Service"
/ip hotspot walled-garden add dst-host=8.8.8.8 comment="Google DNS"
/ip hotspot walled-garden add dst-host=1.1.1.1 comment="Cloudflare DNS"

# Verify walled garden
/ip hotspot walled-garden print
```

### PHASE 6: Test Complete Integration

```routeros
# 1. Check all components are working
/system resource print
/interface wireless print
/ip hotspot print
/ip hotspot active print

# 2. Test internet from router
/ping api.kitonga.klikcell.com count=3

# 3. Check DHCP client (should show your main router IP)
/ip dhcp-client print
```

## 📱 **TESTING YOUR INTEGRATION**

### Test 1: Basic WiFi Connection
1. **Look for "Kitonga WiFi"** on your phone
2. **Connect** with password: `kitonga2025`
3. **Should get IP**: 192.168.88.x
4. **Open browser** → Should redirect to hotspot login page

### Test 2: Django Authentication Flow
1. **After WiFi connection**, open any website
2. **Should redirect** to MikroTik login page
3. **Login page** will authenticate via your Django API
4. **Successful login** grants internet access
5. **User session** managed by MikroTik

### Test 3: Payment Integration
1. **User without bundle** → Login fails
2. **Redirected to payment page** (walled garden allows access)
3. **After ClickPesa payment** → Django updates user bundle
4. **User can then authenticate** and get internet

## 🔗 **HOW THE INTEGRATION WORKS**

```
User Device → WiFi "Kitonga WiFi" → MikroTik Hotspot Login
     ↓
MikroTik calls: https://api.kitonga.klikcell.com/api/mikrotik/auth/
     ↓
Django checks: User bundle status
     ↓
Response: Allow/Deny internet access
     ↓
MikroTik grants/denies internet based on Django response
```

## 🎯 **DJANGO API INTEGRATION POINTS**

Your Django system already has:

1. **Authentication Endpoint**: `/api/mikrotik/auth/`
   - Receives: username, MAC, IP
   - Returns: Allow/Deny + session timeout

2. **User Management**: Django admin for managing users and bundles

3. **Payment Processing**: ClickPesa integration for bundle purchases

4. **Notifications**: NextSMS for user notifications

5. **Bundle Management**: Track usage and expiry

## ✅ **EXPECTED RESULTS**

After running these commands:
- ✅ "Kitonga WiFi" network visible and working
- ✅ Users redirected to login page when connecting
- ✅ Authentication handled by your Django system
- ✅ Payment flow works through walled garden
- ✅ User sessions managed automatically
- ✅ Complete WiFi billing system operational

## 🆘 **TROUBLESHOOTING**

If any step fails, let me know and I'll help fix it immediately. The key is getting each phase working before moving to the next.

**Ready to start with Phase 1?** Copy and paste the Phase 1 commands into your MikroTik terminal! 🚀
