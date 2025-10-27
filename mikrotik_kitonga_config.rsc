# ==========================================
# KITONGA WI-FI HOTSPOT CONFIGURATION
# ==========================================
# Complete MikroTik RouterOS configuration
# Generated: October 27, 2025

# Set router identity
/system identity
set name="Kitonga-WiFi-Router"

# Configure system clock and NTP
/system clock
set time-zone-name=Africa/Dar_es_Salaam

# Configure NTP client (commented out due to syntax issues)
# /system ntp client
# set enabled=yes

# ==========================================
# INTERFACE CONFIGURATION
# ==========================================

# Configure bridge for LAN
/interface bridge
add name=bridge-local protocol-mode=rstp

# Add interfaces to bridge
/interface bridge port
add bridge=bridge-local interface=ether2
add bridge=bridge-local interface=ether3
add bridge=bridge-local interface=ether4
add bridge=bridge-local interface=ether5
add bridge=bridge-local interface=wlan1

# Configure WiFi interface
/interface wireless
set [ find default-name=wlan1 ] band=2ghz-b/g/n channel-width=20/40mhz-XX \
    country=tanzania disabled=no distance=indoors frequency=auto mode=ap-bridge \
    ssid="Kitonga WiFi" wireless-protocol=802.11 wps-mode=disabled

# Enable WiFi security (WPA2)
/interface wireless security-profiles
set [ find default=yes ] authentication-types=wpa2-psk eap-methods="" \
    group-ciphers=tkip,aes-ccm mode=dynamic-keys supplicant-identity=MikroTik \
    unicast-ciphers=tkip,aes-ccm wpa-pre-shared-key="kitonga2025" \
    wpa2-pre-shared-key="kitonga2025"

# ==========================================
# IP CONFIGURATION
# ==========================================

# Configure IP address on bridge
/ip address
add address=192.168.88.1/24 interface=bridge-local network=192.168.88.0

# Configure DHCP server
/ip pool
add name=dhcp-pool ranges=192.168.88.10-192.168.88.100

/ip dhcp-server
add address-pool=dhcp-pool disabled=no interface=bridge-local lease-time=1h name=dhcp-server

/ip dhcp-server network
add address=192.168.88.0/24 dns-server=192.168.88.1 gateway=192.168.88.1

# Configure DNS
/ip dns
set allow-remote-requests=yes servers=8.8.8.8,1.1.1.1

# ==========================================
# FIREWALL CONFIGURATION
# ==========================================

# Basic firewall rules
/ip firewall filter
add action=accept chain=input comment="allow established,related" connection-state=established,related
add action=accept chain=input comment="allow ICMP" protocol=icmp
add action=accept chain=input comment="allow SSH" dst-port=22 protocol=tcp
add action=accept chain=input comment="allow HTTP" dst-port=80 protocol=tcp
add action=accept chain=input comment="allow HTTPS" dst-port=443 protocol=tcp
add action=accept chain=input comment="allow DNS" dst-port=53 protocol=udp
add action=accept chain=input comment="allow DHCP" dst-port=67 protocol=udp
add action=accept chain=input comment="allow Winbox" dst-port=8291 protocol=tcp
add action=accept chain=input comment="allow API" dst-port=8728 protocol=tcp
add action=accept chain=input comment="allow from LAN" in-interface=bridge-local
add action=drop chain=input comment="drop all else"

# NAT configuration
/ip firewall nat
add action=masquerade chain=srcnat out-interface=ether1 comment="masquerade LAN"

# ==========================================
# HOTSPOT CONFIGURATION
# ==========================================

# Create hotspot user profile
/ip hotspot user profile
add name="kitonga-profile" \
    idle-timeout=none \
    keepalive-timeout=2m \
    mac-cookie-timeout=3d \
    session-timeout=24h \
    shared-users=1 \
    status-autorefresh=1m \
    transparent-proxy=yes

# Create hotspot server profile
/ip hotspot profile
add dns-name="kitonga.wifi" \
    hotspot-address=192.168.88.1 \
    html-directory=hotspot \
    http-cookie-lifetime=3d \
    http-proxy=0.0.0.0:0 \
    login-by=cookie,http-chap,http-pap \
    name="kitonga-hotspot-profile" \
    rate-limit="" \
    smtp-server=0.0.0.0 \
    split-user-domain=no \
    use-radius=no

# Create hotspot server
/ip hotspot
add address-pool=dhcp-pool \
    disabled=no \
    interface=bridge-local \
    name="kitonga-hotspot" \
    profile=kitonga-hotspot-profile

# Configure external authentication
/ip hotspot service-port
set ftp disabled=yes
set www disabled=no

# ==========================================
# WALLED GARDEN CONFIGURATION
# ==========================================
# Allow access to authentication server and essential services

/ip hotspot walled-garden
add comment="Django API Server" dst-host=api.kitonga.klikcell.com
add comment="Django Frontend" dst-host=kitonga.klikcell.com
add comment="ClickPesa Payment" dst-host=*.clickpesa.com
add comment="ClickPesa Payment API" dst-host=api.clickpesa.com
add comment="NextSMS Service" dst-host=*.messaging-service.co.tz
add comment="Google DNS" dst-host=8.8.8.8
add comment="Cloudflare DNS" dst-host=1.1.1.1
add comment="NTP Servers" dst-host=*.pool.ntp.org
add comment="SSL Certificates" dst-host=*.letsencrypt.org
add comment="WhatsApp Business" dst-host=*.whatsapp.com
add comment="WhatsApp Web" dst-host=web.whatsapp.com

# Allow specific IP ranges for essential services
/ip hotspot walled-garden ip
add action=accept dst-address=8.8.8.8/32 comment="Google DNS"
add action=accept dst-address=1.1.1.1/32 comment="Cloudflare DNS"
add action=accept dst-address=192.168.88.1/32 comment="Router Access"

# ==========================================
# EXTERNAL AUTHENTICATION SETUP
# ==========================================

# Set authentication URL to Django backend
/ip hotspot service-port
set www port=80

# Note: The login.html file will contain the redirect to Django API
# URL format: https://api.kitonga.klikcell.com/api/mikrotik/auth/

# ==========================================
# USER MANAGEMENT
# ==========================================

# Create default admin user (will be replaced by Django authentication)
/ip hotspot user
add name=admin password=admin profile=kitonga-profile disabled=yes comment="Default admin - disabled for security"

# ==========================================
# LOGGING CONFIGURATION
# ==========================================

# Configure system logging
/system logging
add action=memory disabled=no prefix="" topics=hotspot
add action=memory disabled=no prefix="" topics=wireless
add action=memory disabled=no prefix="" topics=dhcp
add action=memory disabled=no prefix="" topics=account
add action=memory disabled=no prefix="" topics=info

# ==========================================
# BANDWIDTH MANAGEMENT (Optional)
# ==========================================

# Create bandwidth profiles
/queue type
add kind=pcq name=pcq-download pcq-classifier=dst-address
add kind=pcq name=pcq-upload pcq-classifier=src-address

# Create bandwidth limitation queues (adjust as needed)
/queue simple
add max-limit=10M/2M name=hotspot-users target=192.168.88.0/24 queue=pcq-upload/pcq-download

# ==========================================
# SECURITY CONFIGURATION
# ==========================================

# Disable unnecessary services
/ip service
set telnet disabled=yes
set ftp disabled=yes
set www-ssl disabled=no certificate=https-cert
set api disabled=no
set winbox disabled=no
set ssh disabled=no

# Set secure passwords (change these!)
/user
set admin password="kitonga_admin_2025" comment="Main admin user"

# Configure SNMP (optional)
/snmp
set contact="admin@kitonga.klikcell.com" enabled=no location="Kitonga WiFi System"

# ==========================================
# BACKUP CONFIGURATION
# ==========================================

# Create automatic backup script
/system script
add name=daily-backup owner=admin policy=ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon source={
    /system backup save name=("backup-" . [/system clock get date])
    :log info "Daily backup created"
}

# Schedule daily backup
/system scheduler
add interval=1d name=daily-backup on-event=daily-backup policy=ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon start-time=02:00:00

# ==========================================
# MONITORING SETUP
# ==========================================

# Enable graphing for monitoring
/tool graphing interface
add allow-address=192.168.88.0/24 interface=bridge-local

/tool graphing resource
add allow-address=192.168.88.0/24

# ==========================================
# FINAL CONFIGURATION
# ==========================================

# Set router clock
/system clock
set time-zone-name=Africa/Dar_es_Salaam

# Reboot message
:log info "Kitonga WiFi Hotspot configuration completed successfully!"
:put "Configuration applied successfully. Please upload custom hotspot pages."
:put "Don't forget to:"
:put "1. Upload custom HTML files to /hotspot directory"
:put "2. Configure external authentication URL in hotspot profile"
:put "3. Test authentication with Django backend"
:put "4. Change default passwords!"

