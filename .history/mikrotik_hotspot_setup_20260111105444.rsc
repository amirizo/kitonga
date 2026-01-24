# ============================================
# KITONGA WIFI HOTSPOT CONFIGURATION
# ============================================
# Run this script on your MikroTik router via:
# 1. Winbox: System → Scripts → New → Paste this → Run
# 2. Or SSH: /import mikrotik_hotspot_setup.rsc
#
# IMPORTANT: Update these variables first!
# ============================================

# === CONFIGURATION - CHANGE THESE! ===
:local routerId "16"
:local backendIP "127.0.0.1"
:local backendPort "8000"
:local hotspotInterface "wlan1"
:local hotspotServerName "kitonga-hotspot"
:local hotspotProfile "default"

# For production, use your VPS IP:
# :local backendIP "66.29.143.116"
# :local backendPort "8000"

# For local testing via WireGuard VPN:
# The backend is on your laptop, so we need the VPN peer address
# Example: :local backendIP "10.0.0.2"

:log info "=== Starting Kitonga Hotspot Configuration ==="

# ============================================
# 1. WALLED GARDEN - Allow API access BEFORE login
# ============================================
:log info "Configuring Walled Garden..."

# Remove old Kitonga walled garden entries
/ip hotspot walled-garden ip remove [find where comment~"kitonga" or comment~"Kitonga"]

# Add backend API to walled garden (allow HTTP/HTTPS before login)
/ip hotspot walled-garden ip add dst-address=$backendIP dst-port=$backendPort action=accept comment="Kitonga Backend API"
/ip hotspot walled-garden ip add dst-address=$backendIP dst-port=443 action=accept comment="Kitonga Backend HTTPS"

# Allow DNS resolution
/ip hotspot walled-garden ip add dst-port=53 protocol=udp action=accept comment="Kitonga DNS UDP"
/ip hotspot walled-garden ip add dst-port=53 protocol=tcp action=accept comment="Kitonga DNS TCP"

# Add domain-based walled garden entries
/ip hotspot walled-garden remove [find where dst-host~"kitonga" or dst-host~"klikcell"]
/ip hotspot walled-garden add dst-host="*.kitonga.klikcell.com" action=allow comment="Kitonga Domain"
/ip hotspot walled-garden add dst-host="api.kitonga.klikcell.com" action=allow comment="Kitonga API"
/ip hotspot walled-garden add dst-host="kitonga.klikcell.com" action=allow comment="Kitonga Portal"

:log info "Walled Garden configured"

# ============================================
# 2. HOTSPOT SERVER PROFILE
# ============================================
:log info "Configuring Hotspot Profile..."

# Update default profile for Kitonga
/ip hotspot profile set [find name=$hotspotProfile] \
    html-directory=hotspot \
    login-by=http-chap,http-pap,mac-cookie \
    http-cookie-lifetime=1d \
    split-user-domain=no \
    use-radius=no

:log info "Hotspot Profile configured"

# ============================================
# 3. HOTSPOT SERVER
# ============================================
:log info "Configuring Hotspot Server..."

# Check if hotspot server exists
:if ([:len [/ip hotspot find name=$hotspotServerName]] = 0) do={
    :log warning "Hotspot server '$hotspotServerName' not found. Please create it in Winbox."
} else={
    # Enable the hotspot server
    /ip hotspot enable [find name=$hotspotServerName]
    
    # Configure hotspot server
    /ip hotspot set [find name=$hotspotServerName] \
        disabled=no \
        profile=$hotspotProfile \
        idle-timeout=5m \
        keepalive-timeout=2m
    
    :log info "Hotspot Server '$hotspotServerName' enabled"
}

# ============================================
# 4. HOTSPOT USER PROFILE (for internet access)
# ============================================
:log info "Configuring User Profile..."

# Create or update kitonga user profile
:if ([:len [/ip hotspot user profile find name="kitonga"]] = 0) do={
    /ip hotspot user profile add name="kitonga" \
        rate-limit="" \
        session-timeout=1d \
        idle-timeout=30m \
        keepalive-timeout=2m \
        shared-users=3 \
        mac-cookie-timeout=1d
    :log info "Created 'kitonga' user profile"
} else={
    /ip hotspot user profile set [find name="kitonga"] \
        rate-limit="" \
        session-timeout=1d \
        idle-timeout=30m \
        shared-users=3
    :log info "Updated 'kitonga' user profile"
}

# ============================================
# 5. FIREWALL - Allow API traffic
# ============================================
:log info "Configuring Firewall..."

# Remove old Kitonga firewall rules
/ip firewall filter remove [find comment~"Kitonga"]

# Add firewall rules to allow API access from hotspot network
/ip firewall filter add chain=forward \
    dst-address=$backendIP dst-port=$backendPort protocol=tcp \
    action=accept comment="Kitonga - Allow API access" place-before=0

:log info "Firewall configured"

# ============================================
# 6. NAT - Ensure hotspot clients can reach API
# ============================================
:log info "Configuring NAT..."

# Masquerade for hotspot clients (if not already exists)
:if ([:len [/ip firewall nat find comment~"Kitonga Hotspot NAT"]] = 0) do={
    /ip firewall nat add chain=srcnat \
        src-address=10.5.50.0/24 \
        action=masquerade \
        comment="Kitonga Hotspot NAT"
    :log info "Added Hotspot NAT rule"
}

# ============================================
# VERIFICATION
# ============================================
:log info "=== Configuration Complete ==="
:log info "Verifying configuration..."

# List walled garden entries
:put "=== Walled Garden Entries ==="
/ip hotspot walled-garden ip print where comment~"Kitonga"
/ip hotspot walled-garden print where comment~"Kitonga"

# List hotspot servers
:put "\n=== Hotspot Servers ==="
/ip hotspot print

# List user profiles
:put "\n=== User Profiles ==="
/ip hotspot user profile print

:log info "=== Kitonga Configuration Complete ==="
:put "\n=== NEXT STEPS ==="
:put "1. Upload login.html to MikroTik: Files → hotspot folder"
:put "2. Test by connecting to WiFi and opening any website"
:put "3. You should see the Kitonga login page"
:put "4. Check logs: /log print where topics~\"hotspot\""
