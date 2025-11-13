# =============================================================================
# MIKROTIK hAP lite (RB941-2nD) CONFIGURATION FOR KITONGA WI-FI BILLING SYSTEM
# Router Model: RB941-2nD (hAP lite)
# Firmware: 7.20.4
# Serial: HH60A7JKJ8G
# This configuration is specifically optimized for hAP lite hardware
# =============================================================================

# Step 1: Reset hotspot configuration (if needed)
/ip hotspot remove [find]
/ip hotspot profile remove [find where name!="default"]
/ip hotspot user profile remove [find where name!="default"]

# Step 2: Create proper network infrastructure for hAP lite
# hAP lite has: ether1 (WAN), ether2-4 (LAN), wlan1 (2.4GHz WiFi)
/interface bridge
add name=bridge-lan comment="hAP lite LAN Bridge"

# Add LAN interfaces to bridge (hAP lite specific - ether2-4 + wlan1)
/interface bridge port
add bridge=bridge-lan interface=ether2 comment="LAN Port 1"
add bridge=bridge-lan interface=ether3 comment="LAN Port 2" 
add bridge=bridge-lan interface=ether4 comment="LAN Port 3"
add bridge=bridge-lan interface=wlan1 comment="WiFi Interface"

# Step 3: Configure IP addresses
/ip address
add address=192.168.88.1/24 interface=bridge-lan network=192.168.88.0 comment="LAN Gateway"

# Step 4: Configure DHCP
/ip pool
add name=hotspot-pool ranges=192.168.88.10-192.168.88.200 comment="Hotspot DHCP Pool"

/ip dhcp-server network
add address=192.168.88.0/24 gateway=192.168.88.1 dns-server=8.8.8.8,8.8.4.4 comment="Hotspot Network"

/ip dhcp-server
add name=hotspot-dhcp interface=bridge-lan lease-time=1h pool=hotspot-pool disabled=no comment="Hotspot DHCP Server"

# Step 5: Configure NAT for internet access (hAP lite - ether1 is WAN)
/ip firewall nat
add chain=srcnat out-interface=ether1 action=masquerade comment="Internet NAT via ether1"

# Step 6: Create hotspot user profile with correct external authentication
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

# Step 7: Create hotspot profile
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

# Step 8: Create the hotspot
/ip hotspot
add name="kitonga-hotspot" \
    interface=bridge-lan \
    address-pool=hotspot-pool \
    profile=kitonga-profile \
    idle-timeout=5m \
    keepalive-timeout=2m \
    disabled=no \
    comment="Kitonga Main Hotspot"

# Step 9: Configure walled garden (essential for authentication)
/ip hotspot walled-garden
add dst-host=api.kitonga.klikcell.com comment="Django API Server - REQUIRED"
add dst-host=kitonga.klikcell.com comment="Frontend Portal"
add dst-host=*.kitonga.klikcell.com comment="All Kitonga subdomains"
add dst-host=messaging-service.co.tz comment="SMS Service"
add dst-host=api.clickpesa.com comment="Payment Gateway"
add dst-host=*.clickpesa.com comment="Payment Gateway CDN"
add dst-host=login.kitonga.local comment="Local login page"

# Allow DNS servers
add dst-host=8.8.8.8 comment="Google DNS Primary"
add dst-host=8.8.4.4 comment="Google DNS Secondary"
add dst-host=1.1.1.1 comment="Cloudflare DNS"

# Allow essential services
add dst-port=53 protocol=udp comment="DNS UDP"
add dst-port=53 protocol=tcp comment="DNS TCP"
add dst-port=123 protocol=udp comment="NTP"

# Step 10: Configure firewall rules for hotspot
/ip firewall filter
add chain=input action=accept connection-state=established,related comment="Accept established/related"
add chain=input action=accept src-address=192.168.88.0/24 comment="Accept LAN"
add chain=input action=accept protocol=icmp comment="Accept ICMP"
add chain=input action=accept dst-port=22,80,443,8728,8291 protocol=tcp comment="Accept management"
add chain=input action=accept dst-port=53 protocol=udp comment="Accept DNS UDP"
add chain=input action=accept dst-port=53 protocol=tcp comment="Accept DNS TCP"
add chain=input action=drop comment="Drop other input"

add chain=forward action=accept connection-state=established,related comment="Accept established/related"
add chain=forward action=accept src-address=192.168.88.0/24 out-interface=ether1 comment="Allow authenticated users to internet"
add chain=forward action=drop comment="Drop other forward"

# Step 11: Configure WiFi with WPA2 security (hAP lite - 2.4GHz only)
# hAP lite has only 2.4GHz WiFi (wlan1), no 5GHz capability
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

# Create WPA2 security profile optimized for hAP lite
/interface wireless security-profiles
add name="kitonga-security" \
    mode=dynamic-keys \
    authentication-types=wpa2-psk \
    unicast-ciphers=aes-ccm \
    group-ciphers=aes-ccm \
    wpa2-pre-shared-key="Server_room" \
    comment="WPA2 Security for hAP lite WiFi"

# Step 12: DNS configuration
/ip dns
set servers=8.8.8.8,8.8.4.4 allow-remote-requests=yes

# Step 13: Configure default user profile for hotspot users
/ip hotspot user profile
set default shared-users=1 \
    idle-timeout=none \
    keepalive-timeout=2m \
    mac-cookie-timeout=1d \
    address-pool=hotspot-pool \
    transparent-proxy=yes \
    login-by=http-post

# Step 14: Create a test user (optional - for testing)
/ip hotspot user
add name=255684106419 \
    profile=kitonga-external-auth \
    password="" \
    comment="Test user for Kitonga system"

# Step 15: hAP lite specific optimizations
# Optimize for lower-end hardware (hAP lite has limited CPU/RAM)
/system resource
# Monitor CPU usage - hAP lite should stay under 80%

/interface wireless
# Optimize wireless for hAP lite performance
set wlan1 tx-power=17 tx-power-mode=card-rates \
    wmm-support=enabled \
    guard-interval=long \
    ht-basic-mcs="mcs-0,mcs-1,mcs-2,mcs-3,mcs-4,mcs-5,mcs-6,mcs-7" \
    ht-supported-mcs="mcs-0,mcs-1,mcs-2,mcs-3,mcs-4,mcs-5,mcs-6,mcs-7,mcs-8,mcs-9,mcs-10,mcs-11,mcs-12,mcs-13,mcs-14,mcs-15"

# Set optimal channel for Tanzania (less congested)
/interface wireless
set wlan1 frequency=2442 scan-list=2412,2437,2462

# Step 16: Upload custom login page HTML to /hotspot/ folder
# The modern login.html file has been created and is ready to upload
# Copy the content from hotspot_html/login.html to your MikroTik /hotspot/ folder

# To upload the file to hAP lite:
# 1. Open Winbox and connect to your hAP lite
# 2. Go to Files menu
# 3. Navigate to hotspot folder (create if doesn't exist)  
# 4. Upload the new login.html file from hotspot_html/login.html
# 5. The file includes:
#    - Modern responsive design optimized for mobile devices
#    - Phone number validation (255xxxxxxxxx format)
#    - Device tracking integration with your Django API
#    - Loading states and proper error handling
#    - localStorage for user convenience
#    - Proper MikroTik variable integration ($(username), $(error), etc.)
#    - Touch-friendly interface for smartphones/tablets

# Step 17: System logging optimized for hAP lite
/system logging
add topics=hotspot action=memory disabled=no prefix="HOTSPOT"
add topics=wireless action=memory disabled=no prefix="WIRELESS"  
add topics=dhcp action=memory disabled=no prefix="DHCP"
# Limit log memory usage on hAP lite (limited RAM)
set 0 memory-lines=100
set 1 memory-lines=100  
set 2 memory-lines=100

# Step 18: Performance optimization for hAP lite
# Reduce CPU load and optimize for lower-end hardware
/system watchdog
set watchdog-timer=yes auto-reboot=yes

# Optimize TCP settings for hAP lite
/ip settings
set tcp-syncookies=yes allow-fast-path=yes

# Limit connection tracking for performance
/ip firewall connection tracking
set enabled=yes tcp-timeout-established=1d udp-timeout=30s

# Step 19: Time synchronization
/system ntp client
set enabled=yes server-dns-names=pool.ntp.org

/system clock
set time-zone-name=Africa/Dar_es_Salaam

# Step 20: hAP lite specific monitoring
# Monitor key metrics for troubleshooting
/tool netwatch
add host=8.8.8.8 interval=30s comment="Internet connectivity check"
add host=api.kitonga.klikcell.com interval=1m comment="API server connectivity"

# =============================================================================
# CUSTOM LOGIN PAGE HTML - Save to /hotspot/login.html via Files menu
# =============================================================================

# HTML Content for login.html:
#<!DOCTYPE html>
#<html>
#<head>
#    <title>KITONGA WiFi - Login</title>
#    <meta charset="utf-8">
#    <meta name="viewport" content="width=device-width, initial-scale=1">
#    <style>
#        body { font-family: Arial, sans-serif; background: #f0f0f0; margin: 0; padding: 20px; }
#        .container { max-width: 400px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
#        .logo { text-align: center; color: #2196F3; font-size: 24px; font-weight: bold; margin-bottom: 20px; }
#        .form-group { margin-bottom: 15px; }
#        label { display: block; margin-bottom: 5px; font-weight: bold; }
#        input[type="text"] { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 16px; }
#        .btn { width: 100%; padding: 12px; background: #2196F3; color: white; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; }
#        .btn:hover { background: #1976D2; }
#        .info { background: #e3f2fd; padding: 15px; border-radius: 5px; margin-bottom: 20px; text-align: center; }
#        .footer { text-align: center; margin-top: 20px; font-size: 12px; color: #666; }
#    </style>
#</head>
#<body>
#    <div class="container">
#        <div class="logo">KITONGA WiFi</div>
#        <div class="info">
#            Enter your phone number to access internet<br>
#            <small>Make sure you have an active payment or voucher</small>
#        </div>
#        
#        $(if error)
#        <div style="background: #ffebee; color: #c62828; padding: 10px; border-radius: 5px; margin-bottom: 15px;">
#            Error: $(error)
#        </div>
#        $(endif)
#        
#        <form name="login" action="$(link-login-only)" method="post">
#            <input type="hidden" name="dst" value="$(dst)" />
#            <input type="hidden" name="popup" value="true" />
#            
#            <div class="form-group">
#                <label>Phone Number:</label>
#                <input type="text" name="username" placeholder="255xxxxxxxxx" value="$(username)" required />
#            </div>
#            
#            <button type="submit" class="btn">Connect to Internet</button>
#        </form>
#        
#        <div class="footer">
#            Need access? Visit <a href="https://kitonga.klikcell.com">kitonga.klikcell.com</a><br>
#            Or call support: +255 123 456 789
#        </div>
#    </div>
#</body>
#</html>

# =============================================================================
# hAP lite SPECIFIC VERIFICATION AND TESTING COMMANDS
# =============================================================================

# 1. Check hAP lite interface status
# /interface print
# Should show: ether1 (WAN), ether2-4 (LAN), wlan1 (WiFi), bridge-lan

# 2. Check WiFi is working on hAP lite (2.4GHz only)
# /interface wireless print detail
# Should show wlan1 enabled with security-profile=kitonga-security

# 3. Verify hotspot on hAP lite
# /ip hotspot print
# Should show: kitonga-hotspot active on bridge-lan

# 4. Check DHCP on hAP lite
# /ip dhcp-server lease print
# Should show connected devices getting IPs from 192.168.88.10-200

# 5. Test internet connectivity from hAP lite
# /ping 8.8.8.8 count=5
# Should get responses confirming internet access

# 6. Test API connectivity from hAP lite
# /tool fetch url="https://api.kitonga.klikcell.com/api/health/" mode=https
# Should return HTTP 200 OK

# 7. Monitor hAP lite resource usage
# /system resource print
# Monitor CPU usage (should stay under 80%)
# Check free memory (hAP lite has limited RAM)

# 8. Check WiFi clients on hAP lite
# /interface wireless registration-table print
# Shows devices connected to WiFi

# 9. Monitor hotspot active users
# /ip hotspot active print
# Shows currently authenticated users

# 10. Check hAP lite specific logs
# /log print where topics~"hotspot"
# /log print where topics~"wireless"

# =============================================================================
# hAP lite SPECIFIC TROUBLESHOOTING GUIDE
# =============================================================================

# If users can't access internet after authentication:
# 1. Check NAT rule: /ip firewall nat print
#    Should show masquerade rule for ether1 (WAN interface)
# 2. Check internet on hAP lite: /ping 8.8.8.8
# 3. Check hotspot active users: /ip hotspot active print
# 4. Verify firewall forward rules: /ip firewall filter print where chain=forward
# 5. Check hAP lite CPU usage: /system resource print (should be <80%)

# If WiFi connection fails on hAP lite:
# 1. Check WiFi interface: /interface wireless print
#    Should show wlan1 enabled with SSID "KITONGA WiFi"
# 2. Check security profile: /interface wireless security-profiles print
#    Should show kitonga-security with WPA2-PSK
# 3. Check WiFi channel: /interface wireless scan wlan1
#    Try different channels if interference detected
# 4. Check WiFi registration: /interface wireless registration-table print

# If authentication fails:
# 1. Check walled garden: /ip hotspot walled-garden print
#    Must include api.kitonga.klikcell.com
# 2. Test API from hAP lite: /tool fetch url="https://api.kitonga.klikcell.com/api/health/"
# 3. Check external auth URL: /ip hotspot user profile print detail
# 4. Monitor logs: /log print where topics~"hotspot"

# If device count shows 0:
# 1. This is fixed in Django API - devices tracked properly
# 2. Check API response: should show device_count > 0
# 3. Verify device tracking in Django admin

# hAP lite Performance Issues:
# 1. Monitor CPU: /system resource print (keep under 80%)
# 2. Check memory: /system resource print (hAP lite has 32MB RAM)
# 3. Limit concurrent users if needed
# 4. Reduce log verbosity if high CPU usage
# 5. Check for interference: /interface wireless scan wlan1

# hAP lite Firmware Notes:
# - Current: 7.20.4 (latest stable)
# - Supports RouterOS v7 features
# - 2.4GHz WiFi only (no 5GHz)
# - 4x 10/100 Ethernet ports
# - QCA9531 SoC with limited resources

# =============================================================================
# BACKUP AND RECOVERY
# =============================================================================

# Create backup after configuration
/system backup save name="kitonga-working-config"

# Export configuration
/export file="kitonga-complete-config"

# =============================================================================
# FINAL STEPS
# =============================================================================
# 1. Upload custom login.html to /hotspot/ folder via Files menu in Winbox
# 2. Test with a known working phone number
# 3. Verify internet access after authentication
# 4. Monitor logs for any issues
# 5. Update Django settings with correct MikroTik IP if needed
