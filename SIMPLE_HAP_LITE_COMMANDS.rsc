# =============================================================================
# SIMPLE STEP-BY-STEP COMMANDS FOR YOUR hAP lite
# Copy and paste these commands one by one in your MikroTik terminal
# =============================================================================

# STEP 1: Create WiFi Security Profile (this was missing the password)
/interface wireless security-profiles add name="kitonga-security" mode=dynamic-keys authentication-types=wpa2-psk unicast-ciphers=aes-ccm group-ciphers=aes-ccm wpa2-pre-shared-key="KITONGA2024@WiFi" comment="WPA2 Security for hAP lite WiFi"

# STEP 2: Apply security to WiFi
/interface wireless set wlan1 security-profile=kitonga-security ssid="KITONGA WiFi" disabled=no

# STEP 3: Create IP pool (if not exists)
/ip pool add name=hotspot-pool ranges=192.168.88.10-192.168.88.200 comment="Hotspot DHCP Pool"

# STEP 4: Create hotspot user profile with external authentication
/ip hotspot user profile add name="kitonga-external-auth" shared-users=10 idle-timeout=none keepalive-timeout=2m mac-cookie-timeout=1d address-pool=hotspot-pool transparent-proxy=yes login-by=http-post http-post-url="https://api.kitonga.klikcell.com/api/mikrotik/auth/" http-post-data="username=\$(username)&password=\$(password)&mac=\$(mac)&ip=\$(ip)" comment="Kitonga External Authentication Profile"

# STEP 5: Create hotspot profile
/ip hotspot profile add name="kitonga-profile" hotspot-address=192.168.88.1 dns-name="login.kitonga.local" html-directory=hotspot http-cookie-lifetime=1d http-proxy=0.0.0.0:0 login-by=http-post use-radius=no comment="Kitonga Hotspot Profile"

# STEP 6: Create the hotspot
/ip hotspot add name="kitonga-hotspot" interface=bridge-lan address-pool=hotspot-pool profile=kitonga-profile idle-timeout=5m keepalive-timeout=2m disabled=no comment="Kitonga Main Hotspot"

# STEP 7: Add walled garden entries
/ip hotspot walled-garden add dst-host=api.kitonga.klikcell.com comment="Django API Server - REQUIRED"
/ip hotspot walled-garden add dst-host=kitonga.klikcell.com comment="Frontend Portal"
/ip hotspot walled-garden add dst-host=*.kitonga.klikcell.com comment="All Kitonga subdomains"
/ip hotspot walled-garden add dst-host=8.8.8.8 comment="Google DNS Primary"
/ip hotspot walled-garden add dst-host=8.8.4.4 comment="Google DNS Secondary"
/ip hotspot walled-garden add dst-host=1.1.1.1 comment="Cloudflare DNS"

# STEP 8: Set default user profile to use external authentication
/ip hotspot user profile set default shared-users=1 idle-timeout=none keepalive-timeout=2m mac-cookie-timeout=1d address-pool=hotspot-pool transparent-proxy=yes login-by=http-post http-post-url="https://api.kitonga.klikcell.com/api/mikrotik/auth/" http-post-data="username=\$(username)&password=\$(password)&mac=\$(mac)&ip=\$(ip)"

# STEP 9: Create test user
/ip hotspot user add name=255684106419 profile=kitonga-external-auth password="" comment="Test user for Kitonga system"

# =============================================================================
# VERIFICATION COMMANDS
# =============================================================================

# Check if everything is created correctly:
/ip hotspot print
/ip hotspot profile print
/ip hotspot user profile print
/interface wireless print detail
/interface wireless security-profiles print

# Test internet and API connectivity:
/ping 8.8.8.8 count=3
/tool fetch url="https://api.kitonga.klikcell.com/api/health/" mode=https

# =============================================================================
# TESTING PROCEDURE
# =============================================================================

# 1. Connect a device to WiFi "KITONGA WiFi" using password "KITONGA2024@WiFi"
# 2. Open a web browser
# 3. Try to visit any website (like google.com)
# 4. You should be redirected to the login page
# 5. Enter phone number: 255684106419
# 6. Click login - should authenticate successfully
# 7. You should then have internet access

# =============================================================================
# IF SOMETHING FAILS
# =============================================================================

# Check hotspot status:
/ip hotspot active print

# Check logs for errors:
/log print where topics~"hotspot"

# Check if users can reach the API:
/tool fetch url="https://api.kitonga.klikcell.com/api/mikrotik/auth/" mode=https

# If authentication fails, check walled garden:
/ip hotspot walled-garden print

# Make sure NAT is working:
/ip firewall nat print
