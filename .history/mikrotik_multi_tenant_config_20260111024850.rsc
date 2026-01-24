# ==========================================
# KITONGA MULTI-TENANT HOTSPOT CONFIGURATION
# ==========================================
# MikroTik RouterOS configuration for multi-tenant SaaS
# This script must include the ROUTER_ID for proper tenant isolation
#
# IMPORTANT: 
# 1. Set ROUTER_ID to the ID from your Kitonga dashboard
# 2. Set API_URL to your VPS endpoint
# 3. Upload the login.html to your router's hotspot folder
#
# Generated: January 2026

# ==========================================
# CONFIGURATION VARIABLES - CHANGE THESE!
# ==========================================
# Get your Router ID from Kitonga Dashboard > Routers > Your Router
:local ROUTER_ID "16"
:local API_URL "https://api.kitonga.klikcell.com"
:local HOTSPOT_NAME "kitonga-hotspot"
:local ROUTER_IDENTITY "Kitonga-WiFi-Router"

# ==========================================
# SET ROUTER IDENTITY
# ==========================================
/system identity set name=$ROUTER_IDENTITY

# ==========================================
# HOTSPOT SERVER PROFILE
# ==========================================
# This profile MUST use custom login pages that pass router-id

/ip hotspot profile
add name="kitonga-profile" \
    dns-name="wifi.kitonga.local" \
    hotspot-address=192.168.88.1 \
    html-directory=hotspot \
    http-cookie-lifetime=3d \
    http-proxy=0.0.0.0:0 \
    login-by=http-chap,http-pap \
    rate-limit="" \
    smtp-server=0.0.0.0 \
    split-user-domain=no \
    use-radius=no

# ==========================================
# HOTSPOT SERVER
# ==========================================
/ip hotspot
add name=$HOTSPOT_NAME \
    interface=bridgeLocal \
    address-pool=dhcp-pool \
    profile=kitonga-profile \
    disabled=no

# ==========================================
# USER PROFILE (DEFAULT)
# ==========================================
/ip hotspot user profile
add name="default" \
    idle-timeout=5m \
    keepalive-timeout=2m \
    mac-cookie-timeout=3d \
    session-timeout=24h \
    shared-users=1 \
    status-autorefresh=1m

# ==========================================
# WALLED GARDEN - Allow API Access
# ==========================================
# Users MUST be able to reach the API before authentication

/ip hotspot walled-garden
add comment="Kitonga API" dst-host=api.kitonga.klikcell.com
add comment="Kitonga Portal" dst-host=kitonga.klikcell.com
add comment="ClickPesa Payment" dst-host=*.clickpesa.com
add comment="NextSMS" dst-host=*.messaging-service.co.tz
add comment="Google DNS" dst-host=dns.google
add comment="Cloudflare DNS" dst-host=cloudflare-dns.com

/ip hotspot walled-garden ip
add action=accept dst-address=8.8.8.8/32 comment="Google DNS"
add action=accept dst-address=1.1.1.1/32 comment="Cloudflare DNS"
add action=accept dst-address=192.168.88.1/32 comment="Router"

# ==========================================
# ENABLE API ACCESS (FOR VPS CONNECTION)
# ==========================================
/ip service
set api address="" disabled=no port=8728
set api-ssl address="" disabled=yes port=8729

# API Firewall - allow from WireGuard VPN
/ip firewall filter
add action=accept chain=input comment="API from WireGuard" \
    dst-port=8728 protocol=tcp src-address=10.10.10.0/24 \
    place-before=0

# ==========================================
# LOGGING
# ==========================================
/system logging
add topics=hotspot action=memory prefix="HS"
add topics=account action=memory prefix="ACC"

:log info "Kitonga Multi-Tenant Configuration Applied - Router ID: $ROUTER_ID"
