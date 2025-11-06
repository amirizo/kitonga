# ==========================================
# INTERNET ACCESS FIX - MikroTik Configuration
# ==========================================
# Apply these commands in your MikroTik router terminal

# STEP 1: Fix Firewall Filter Rules (CRITICAL)
# ============================================

# Remove existing forward rules that might be blocking traffic
/ip firewall filter
remove [find chain="forward"]

# Add correct firewall rules in this EXACT order:

# 1. Accept established and related connections (MUST BE FIRST)
add chain=forward action=accept connection-state=established,related comment="accept established,related"

# 2. Allow hotspot users to access internet (CRITICAL FOR YOUR ISSUE)
add chain=forward action=accept src-address=192.168.88.0/24 comment="allow hotspot users to internet"

# 3. Accept ICMP for ping tests
add chain=forward action=accept protocol=icmp comment="accept icmp"

# 4. Drop invalid connections
add chain=forward action=drop connection-state=invalid comment="drop invalid"

# 5. Drop all other traffic (MUST BE LAST)
add chain=forward action=drop comment="drop all else"

# STEP 2: Fix NAT Configuration (CRITICAL)
# ========================================

# Check your WAN interface first:
/interface print
# Look for your internet-connected interface (usually ether1 or ether1-wan)

# Remove existing NAT rules and add correct one:
/ip firewall nat
remove [find chain="srcnat"]

# Add NAT rule - REPLACE "ether1" with your actual WAN interface name
add chain=srcnat action=masquerade out-interface=ether1 comment="Internet NAT for hotspot"

# If your WAN interface has a different name, use it instead:
# Examples:
# add chain=srcnat action=masquerade out-interface=ether1-wan comment="Internet NAT"
# add chain=srcnat action=masquerade out-interface=pppoe-out1 comment="Internet NAT"

# STEP 3: Verify Hotspot Configuration
# ===================================

# Ensure hotspot is properly configured
/ip hotspot
set [find] address-pool=dhcp_pool1 profile=hsprof1 disabled=no

# Check hotspot profile
/ip hotspot profile
set [find name="hsprof1"] dns-name="kitonga.wifi" hotspot-address=192.168.88.1

# STEP 4: Verify DNS and Routing
# ==============================

# Set DNS servers
/ip dns
set servers=8.8.8.8,1.1.1.1 allow-remote-requests=yes

# Check if default route exists
/ip route print
# If no default route, and you're using DHCP from ISP:
/ip dhcp-client
add interface=ether1 disabled=no

# STEP 5: Test Configuration
# =========================

# Test internet from router
/ping 8.8.8.8 count=3

# Check active users
/ip hotspot active print

# Check logs
/log print where topics~"hotspot"

# ==========================================
# SIMPLIFIED VERSION (if above is too complex)
# ==========================================

# If you want to start fresh with minimal rules:

# Clear all firewall rules
/ip firewall filter remove [find]
/ip firewall nat remove [find]

# Add minimal working rules
/ip firewall filter
add chain=input action=accept
add chain=forward action=accept

# Add NAT
/ip firewall nat
add chain=srcnat action=masquerade out-interface=ether1

# ==========================================
# VERIFICATION COMMANDS
# ==========================================

# After applying the fix, run these to verify:
/ip firewall filter print
/ip firewall nat print
/ip hotspot active print
/ping 8.8.8.8
/ip route print
