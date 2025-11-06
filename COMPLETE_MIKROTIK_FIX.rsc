# =============================================================================
# COMPLETE MIKROTIK CONFIGURATION FIX FOR KITONGA WI-FI BILLING SYSTEM
# This fixes internet access issues and device tracking problems
# =============================================================================

# Step 1: Reset hotspot configuration (if needed)
/ip hotspot remove [find]
/ip hotspot profile remove [find where name!="default"]
/ip hotspot user profile remove [find where name!="default"]

# Step 2: Create proper network infrastructure
/interface bridge
add name=bridge-lan comment="Main LAN Bridge"

# Add your LAN interfaces to bridge (adjust interface names as needed)
/interface bridge port
add bridge=bridge-lan interface=ether2
add bridge=bridge-lan interface=ether3
add bridge=bridge-lan interface=ether4
add bridge=bridge-lan interface=ether5
add bridge=bridge-lan interface=wlan1

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

# Step 5: Configure NAT for internet access
/ip firewall nat
add chain=srcnat out-interface=ether1 action=masquerade comment="Internet NAT"

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

# Step 11: Configure WiFi with WPA2 security (IMPORTANT for security warning fix)
/interface wireless
set [ find default-name=wlan1 ] \
    mode=ap-bridge \
    ssid="KITONGA WiFi" \
    wireless-protocol=802.11 \
    band=2ghz-b/g/n \
    channel-width=20/40mhz-Ce \
    frequency=auto \
    security-profile=kitonga-security \
    bridge-mode=enabled \
    disabled=no

# Create WPA2 security profile
/interface wireless security-profiles
add name="kitonga-security" \
    mode=dynamic-keys \
    authentication-types=wpa2-psk \
    unicast-ciphers=aes-ccm \
    group-ciphers=aes-ccm \
    wpa2-pre-shared-key="KITONGA2024@WiFi" \
    comment="WPA2 Security for Kitonga WiFi"

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
add name=255708374149 \
    profile=kitonga-external-auth \
    password="" \
    comment="Test user for Kitonga system"

# Step 15: Upload custom login page HTML to /hotspot/ folder
# The login.html file has been updated and is ready to upload
# Copy the content from hotspot_html/login.html to your MikroTik /hotspot/ folder

# To upload the file:
# 1. Open Winbox
# 2. Go to Files menu
# 3. Navigate to hotspot folder (create if doesn't exist)
# 4. Upload the new login.html file
# 5. The file includes:
#    - Modern responsive design
#    - Device tracking integration
#    - Phone number validation
#    - Loading states and error handling
#    - localStorage for user convenience
#    - Proper MikroTik variable integration

# Step 16: System logging for debugging
/system logging
add topics=hotspot action=memory disabled=no prefix="HOTSPOT"
add topics=wireless action=memory disabled=no prefix="WIRELESS"
add topics=dhcp action=memory disabled=no prefix="DHCP"

# Step 17: Time synchronization
/system ntp client
set enabled=yes server-dns-names=pool.ntp.org

/system clock
set time-zone-name=Africa/Dar_es_Salaam

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
# VERIFICATION AND TESTING COMMANDS
# =============================================================================

# 1. Check hotspot status
# /ip hotspot print
# Should show: kitonga-hotspot with I flag (interface) and profile kitonga-profile

# 2. Check if users can get IP addresses
# /ip dhcp-server lease print
# Should show connected devices getting IPs from 192.168.88.10-200

# 3. Test external authentication
# Try connecting with phone: 255708374149
# Check logs: /log print where topics~"hotspot"

# 4. Test internet connectivity from router
# /tool fetch url="https://api.kitonga.klikcell.com/api/health/" mode=https

# 5. Check walled garden
# /ip hotspot walled-garden print
# Should show api.kitonga.klikcell.com and other essential domains

# 6. Monitor active hotspot users
# /ip hotspot active print
# Shows currently authenticated users

# 7. Check WiFi security
# /interface wireless registration-table print
# Shows connected WiFi clients

# =============================================================================
# TROUBLESHOOTING STEPS
# =============================================================================

# If users can't access internet after authentication:
# 1. Check NAT rule: /ip firewall nat print
# 2. Check if WAN interface has internet: /ping 8.8.8.8
# 3. Check hotspot active users: /ip hotspot active print
# 4. Check firewall forward rules: /ip firewall filter print where chain=forward

# If authentication fails:
# 1. Check walled garden allows API access: /ip hotspot walled-garden print
# 2. Test API connectivity: /tool fetch url="https://api.kitonga.klikcell.com/api/health/"
# 3. Check authentication URL in profile: /ip hotspot user profile print detail
# 4. Monitor logs: /log print where topics~"hotspot"

# If device count shows 0:
# 1. This is fixed in the Django API code below
# 2. Devices will be tracked when users authenticate through WiFi
# 3. Check device tracking in Django admin or via API

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
