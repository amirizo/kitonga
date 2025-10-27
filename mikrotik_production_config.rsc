# =============================================================================
# KITONGA WI-FI BILLING SYSTEM - PRODUCTION MIKROTIK CONFIGURATION
# Domain: https://api.kitonga.klikcell.com
# =============================================================================

# 1. BASIC NETWORK CONFIGURATION
# Configure your internet interface (replace ether1 with your WAN interface)
/interface ethernet
set [ find default-name=ether1 ] name=ether1-wan comment="Internet Connection"

# Configure LAN bridge
/interface bridge
add name=bridge-lan comment="LAN Bridge"

# Add LAN interfaces to bridge (replace ether2,ether3,ether4,ether5 with your LAN ports)
/interface bridge port
add bridge=bridge-lan interface=ether2
add bridge=bridge-lan interface=ether3
add bridge=bridge-lan interface=ether4
add bridge=bridge-lan interface=ether5

# 2. IP CONFIGURATION
# Configure WAN (DHCP from ISP)
/ip dhcp-client
add disabled=no interface=ether1-wan comment="ISP DHCP"

# Configure LAN IP
/ip address
add address=192.168.88.1/24 interface=bridge-lan network=192.168.88.0 comment="LAN Network"

# 3. DHCP SERVER CONFIGURATION
/ip pool
add name=dhcp_pool1 ranges=192.168.88.10-192.168.88.200 comment="DHCP Pool for Clients"

/ip dhcp-server network
add address=192.168.88.0/24 gateway=192.168.88.1 dns-server=8.8.8.8,8.8.4.4 comment="DHCP Network"

/ip dhcp-server
add name=dhcp1 interface=bridge-lan lease-time=1h pool=dhcp_pool1 disabled=no comment="DHCP Server"

# 4. FIREWALL CONFIGURATION
# NAT Rules
/ip firewall nat
add chain=srcnat out-interface=ether1-wan action=masquerade comment="Internet NAT"

# Firewall Filter Rules
/ip firewall filter
add chain=input action=accept connection-state=established,related comment="Accept established/related"
add chain=input action=accept src-address=192.168.88.0/24 comment="Accept LAN"
add chain=input action=accept protocol=icmp comment="Accept ICMP"
add chain=input action=accept dst-port=22,80,443,8728,8291 protocol=tcp comment="Accept SSH,HTTP,HTTPS,API,Winbox"
add chain=input action=drop comment="Drop all other input"

add chain=forward action=accept connection-state=established,related comment="Accept established/related"
add chain=forward action=accept src-address=192.168.88.0/24 comment="Accept LAN to WAN"
add chain=forward action=drop comment="Drop all other forward"

# 5. HOTSPOT CONFIGURATION
# Create hotspot user profile with external authentication
/ip hotspot user profile
add name="kitonga-auth" shared-users=1 idle-timeout=none keepalive-timeout=2m \
    mac-cookie-timeout=1d address-pool=dhcp_pool1 transparent-proxy=yes \
    login-by=http-post \
    http-post-url="https://api.kitonga.klikcell.com/api/mikrotik/auth/" \
    http-post-data="username=\$(username)&password=\$(password)&mac=\$(mac)&ip=\$(ip)" \
    comment="Kitonga External Authentication Profile"

# Configure default hotspot profile
/ip hotspot profile
set [ find default=yes ] name=hsprof1 hotspot-address=192.168.88.1 \
    dns-name=kitonga.klikcell.com html-directory=kitonga \
    http-cookie-lifetime=1d http-proxy=0.0.0.0:0 login-by=http-post \
    use-radius=no comment="Kitonga Hotspot Profile"

# Create hotspot
/ip hotspot
add name=kitonga-hotspot interface=bridge-lan address-pool=dhcp_pool1 \
    profile=hsprof1 disabled=no idle-timeout=5m keepalive-timeout=2m \
    comment="Kitonga Wi-Fi Hotspot"

# Set user profile for hotspot
/ip hotspot user profile
set hsprof1 name="kitonga-auth" shared-users=1 \
    address-pool=dhcp_pool1 transparent-proxy=yes \
    login-by=http-post \
    http-post-url="https://api.kitonga.klikcell.com/api/mikrotik/auth/" \
    http-post-data="username=\$(username)&password=\$(password)&mac=\$(mac)&ip=\$(ip)"

# 6. WALLED GARDEN CONFIGURATION
# Allow access to essential services before authentication
/ip hotspot walled-garden
add dst-host=api.kitonga.klikcell.com comment="Django API Server"
add dst-host=kitonga.klikcell.com comment="Frontend Portal"
add dst-host=messaging-service.co.tz comment="SMS Service"
add dst-host=api.clickpesa.com comment="Payment Gateway"
add dst-host=*.google.com comment="Google Services"
add dst-host=*.googleapis.com comment="Google APIs"
add dst-host=fonts.googleapis.com comment="Google Fonts"
add dst-host=*.gstatic.com comment="Google Static"
add dst-host=cdnjs.cloudflare.com comment="CDN Libraries"

# Allow DNS
/ip hotspot walled-garden
add dst-port=53 protocol=udp comment="DNS UDP"
add dst-port=53 protocol=tcp comment="DNS TCP"

# 7. DNS CONFIGURATION
/ip dns
set servers=8.8.8.8,8.8.4.4 allow-remote-requests=yes

# 8. TIME CONFIGURATION
/system ntp client
set enabled=yes server-dns-names=pool.ntp.org

# Set timezone (adjust for Tanzania)
/system clock
set time-zone-name=Africa/Dar_es_Salaam

# 9. HOTSPOT SERVER PROFILE SETTINGS
/ip hotspot profile
set [ find name=hsprof1 ] html-directory=kitonga dns-name=kitonga.klikcell.com \
    hotspot-address=192.168.88.1 http-proxy=0.0.0.0:0 login-by=http-post \
    use-radius=no

# 10. LOGGING CONFIGURATION
/system logging
add topics=hotspot action=memory prefix="HOTSPOT"
add topics=firewall action=memory prefix="FIREWALL"

# 11. BANDWIDTH MANAGEMENT (Optional)
# Create simple queue for bandwidth control
/queue simple
add name=total-bandwidth target=192.168.88.0/24 max-limit=50M/50M \
    comment="Total Bandwidth Limit"

# 12. SECURITY ENHANCEMENTS
# Change default admin password
/user set admin password="YourSecurePassword123!"

# Create backup user
/user add name=backup group=full password="BackupPassword123!" \
    comment="Backup Admin User"

# Disable unnecessary services
/ip service
set telnet disabled=yes
set ftp disabled=yes
set www disabled=no
set ssh disabled=no
set api disabled=no
set winbox disabled=no
set api-ssl disabled=yes

# 13. BACKUP CONFIGURATION
# Create automatic backup
/system backup save name=kitonga-config

# 14. MONITORING SETUP
/tool netwatch
add host=8.8.8.8 interval=30s comment="Internet Connectivity Check"
add host=api.kitonga.klikcell.com interval=1m comment="API Server Check"

# =============================================================================
# CUSTOM HOTSPOT HTML FILES
# Upload these files to Files > hotspot folder in Winbox
# =============================================================================

# Files needed in /hotspot/ folder:
# - login.html (custom login page)
# - alogin.html (admin login page)  
# - status.html (status page)
# - logout.html (logout page)
# - error.html (error page)

# =============================================================================
# VERIFICATION COMMANDS
# =============================================================================

# Check hotspot status
# /ip hotspot print

# Check active users
# /ip hotspot active print

# Check hotspot profile
# /ip hotspot user profile print

# Monitor logs
# /log print where topics~"hotspot"

# Test authentication
# Try connecting with phone number: 255708374149

# =============================================================================
# TROUBLESHOOTING
# =============================================================================

# 1. Check if hotspot is running:
#    /ip hotspot print
#    Should show "kitonga-hotspot" as enabled

# 2. Check walled garden:
#    /ip hotspot walled-garden print
#    Should show api.kitonga.klikcell.com

# 3. Check external auth URL:
#    /ip hotspot user profile print
#    Should show correct https://api.kitonga.klikcell.com URL

# 4. Monitor authentication attempts:
#    /log print where topics~"hotspot"

# 5. Test connectivity to API:
#    /tool fetch url="https://api.kitonga.klikcell.com/api/health/"

# =============================================================================
# FINAL CHECKLIST
# =============================================================================
# [ ] Internet connection working
# [ ] LAN network configured (192.168.88.0/24)
# [ ] DHCP server working
# [ ] Hotspot created and enabled
# [ ] External authentication URL configured
# [ ] Walled garden entries added
# [ ] Custom HTML files uploaded
# [ ] Admin password changed
# [ ] Backup created
# [ ] Test user authentication working
