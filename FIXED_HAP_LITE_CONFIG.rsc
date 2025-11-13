# =============================================================================
# CORRECTED MIKROTIK hAP lite (RB941-2nD) CONFIGURATION
# Based on your terminal output and syntax errors encountered
# This fixes all the command syntax issues you experienced
# =============================================================================

# Step 1: First, let's check what we have and clean up
/ip hotspot remove [find]
/ip hotspot profile remove [find where name!="default"]
/ip hotspot user profile remove [find where name!="default"]

# Step 2: Create IP pool for hotspot (this might already exist)
/ip pool
add name=hotspot-pool ranges=192.168.88.10-192.168.88.200 comment="Hotspot DHCP Pool"

# Step 3: Create WiFi security profile FIRST (this was missing the password)
/interface wireless security-profiles
add name="kitonga-security" \
    mode=dynamic-keys \
    authentication-types=wpa2-psk \
    unicast-ciphers=aes-ccm \
    group-ciphers=aes-ccm \
    wpa2-pre-shared-key="KITONGA2024@WiFi" \
    comment="WPA2 Security for hAP lite WiFi"

# Step 4: Apply security profile to WiFi (this failed before because profile didn't exist)
/interface wireless
set [ find default-name=wlan1 ] \
    mode=ap-bridge \
    ssid="KITONGA WiFi" \
    wireless-protocol=802.11 \
    band=2ghz-b/g/n \
    channel-width=20mhz \
    frequency=2442 \
    country=tanzania \
    installation=indoor \
    security-profile=kitonga-security \
    disabled=no \
    comment="hAP lite 2.4GHz WiFi"

# Step 5: Create hotspot user profile with CORRECT syntax
/ip hotspot user profile
add name="kitonga-external-auth" \
    shared-users=10 \
    idle-timeout=none \
    keepalive-timeout=2m \
    mac-cookie-timeout=1d \
    address-pool=hotspot-pool \
    transparent-proxy=yes \
    login-by=http-post \
    http-post-url="https://api.kitonga.klikcell.com/api/mikrotik/auth/" \
    http-post-data="username=\$(username)&password=\$(password)&mac=\$(mac)&ip=\$(ip)" \
    comment="Kitonga External Authentication Profile"

# Step 6: Create hotspot profile with CORRECT syntax
/ip hotspot profile
add name="kitonga-profile" \
    hotspot-address=192.168.88.1 \
    dns-name="login.kitonga.local" \
    html-directory=hotspot \
    http-cookie-lifetime=1d \
    http-proxy=0.0.0.0:0 \
    login-by=http-post \
    use-radius=no \
    comment="Kitonga Hotspot Profile"

# Step 7: Create the hotspot with CORRECT syntax
/ip hotspot
add name="kitonga-hotspot" \
    interface=bridge-lan \
    address-pool=hotspot-pool \
    profile=kitonga-profile \
    idle-timeout=5m \
    keepalive-timeout=2m \
    disabled=no \
    comment="Kitonga Main Hotspot"

# Step 8: Configure walled garden with correct syntax (no protocol/port mixing)
/ip hotspot walled-garden
add dst-host=api.kitonga.klikcell.com comment="Django API Server - REQUIRED"
add dst-host=kitonga.klikcell.com comment="Frontend Portal"
add dst-host=*.kitonga.klikcell.com comment="All Kitonga subdomains"
add dst-host=messaging-service.co.tz comment="SMS Service"
add dst-host=api.clickpesa.com comment="Payment Gateway"
add dst-host=*.clickpesa.com comment="Payment Gateway CDN"
add dst-host=login.kitonga.local comment="Local login page"
add dst-host=8.8.8.8 comment="Google DNS Primary"
add dst-host=8.8.4.4 comment="Google DNS Secondary"
add dst-host=1.1.1.1 comment="Cloudflare DNS"

# Step 9: Set default user profile to use external authentication
/ip hotspot user profile
set default shared-users=1 \
    idle-timeout=none \
    keepalive-timeout=2m \
    mac-cookie-timeout=1d \
    address-pool=hotspot-pool \
    transparent-proxy=yes \
    login-by=http-post \
    http-post-url="https://api.kitonga.klikcell.com/api/mikrotik/auth/" \
    http-post-data="username=\$(username)&password=\$(password)&mac=\$(mac)&ip=\$(ip)"

# Step 10: Create test user (now that profile exists)
/ip hotspot user
add name=255684106419 \
    profile=kitonga-external-auth \
    password="" \
    comment="Test user for Kitonga system"

# Step 11: Optimize wireless settings (remove unsupported tx-power-mode)
/interface wireless
set wlan1 tx-power=17 \
    wmm-support=enabled \
    guard-interval=long \
    ht-basic-mcs="mcs-0,mcs-1,mcs-2,mcs-3,mcs-4,mcs-5,mcs-6,mcs-7" \
    ht-supported-mcs="mcs-0,mcs-1,mcs-2,mcs-3,mcs-4,mcs-5,mcs-6,mcs-7,mcs-8,mcs-9,mcs-10,mcs-11,mcs-12,mcs-13,mcs-14,mcs-15"

# Step 12: Set scan list for optimal channel selection
/interface wireless
set wlan1 frequency=2442 scan-list=2412,2437,2462

# Step 13: Monitor tools (using IP instead of hostname for netwatch)
/tool netwatch
add host=8.8.8.8 interval=30s comment="Internet connectivity check"
add host=1.1.1.1 interval=1m comment="Cloudflare DNS check"

# =============================================================================
# VERIFICATION COMMANDS - Run these after applying the config
# =============================================================================

# 1. Check WiFi security profile
# /interface wireless security-profiles print

# 2. Check WiFi interface
# /interface wireless print detail

# 3. Check hotspot user profiles
# /ip hotspot user profile print detail

# 4. Check hotspot profile
# /ip hotspot profile print detail

# 5. Check hotspot
# /ip hotspot print

# 6. Check walled garden
# /ip hotspot walled-garden print

# 7. Test with a device:
#    - Connect to "KITONGA WiFi" with password "KITONGA2024@WiFi"
#    - Open browser, should redirect to login page
#    - Enter phone number 255684106419
#    - Should authenticate successfully

# =============================================================================
# TROUBLESHOOTING QUICK FIXES
# =============================================================================

# If hotspot still doesn't work, try these commands:

# Reset hotspot completely and recreate:
# /ip hotspot remove [find]
# /ip hotspot setup hotspot-interface=bridge-lan

# Then manually configure the authentication:
# /ip hotspot user profile set default http-post-url="https://api.kitonga.klikcell.com/api/mikrotik/auth/"
# /ip hotspot user profile set default http-post-data="username=\$(username)&password=\$(password)&mac=\$(mac)&ip=\$(ip)"
# /ip hotspot user profile set default login-by=http-post

# If users can't access internet after login:
# /ip firewall nat print
# Should show masquerade rule for ether1

# If authentication fails:
# /log print where topics~"hotspot"
# Check for error messages

# =============================================================================
# STEP-BY-STEP MANUAL SETUP (if script fails)
# =============================================================================

# 1. Create security profile:
# /interface wireless security-profiles add name=kitonga-security mode=dynamic-keys authentication-types=wpa2-psk wpa2-pre-shared-key="KITONGA2024@WiFi"

# 2. Apply to WiFi:
# /interface wireless set wlan1 security-profile=kitonga-security ssid="KITONGA WiFi"

# 3. Create user profile:
# /ip hotspot user profile add name=kitonga-auth login-by=http-post http-post-url="https://api.kitonga.klikcell.com/api/mikrotik/auth/" http-post-data="username=\$(username)&password=\$(password)&mac=\$(mac)&ip=\$(ip)"

# 4. Create hotspot profile:
# /ip hotspot profile add name=kitonga-profile hotspot-address=192.168.88.1 login-by=http-post

# 5. Create hotspot:
# /ip hotspot add interface=bridge-lan address-pool=hotspot-pool profile=kitonga-profile name=kitonga-hotspot

# 6. Add walled garden:
# /ip hotspot walled-garden add dst-host=api.kitonga.klikcell.com

# 7. Set default profile:
# /ip hotspot user profile set default login-by=http-post http-post-url="https://api.kitonga.klikcell.com/api/mikrotik/auth/" http-post-data="username=\$(username)&password=\$(password)&mac=\$(mac)&ip=\$(ip)"
