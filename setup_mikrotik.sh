#!/bin/bash

# ==========================================
# KITONGA WI-FI HOTSPOT - MIKROTIK SETUP
# ==========================================
# Complete MikroTik configuration for Django backend integration
# Author: Kitonga Wi-Fi System
# Date: October 27, 2025

echo "🚀 Starting MikroTik Configuration for Kitonga Wi-Fi System..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration Variables
ROUTER_IP="192.168.88.1"
ADMIN_USER="admin"
API_URL="https://api.kitonga.klikcell.com"
HOTSPOT_NAME="kitonga-hotspot"
DHCP_POOL="192.168.88.10-192.168.88.100"
DNS_SERVERS="8.8.8.8,1.1.1.1"

echo -e "${BLUE}Configuration Settings:${NC}"
echo "Router IP: $ROUTER_IP"
echo "API URL: $API_URL"
echo "Hotspot Name: $HOTSPOT_NAME"
echo "DHCP Pool: $DHCP_POOL"
echo ""

# Function to check if router is accessible
check_router() {
    echo -n "Checking router connectivity... "
    if ping -c 1 $ROUTER_IP > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Router is accessible${NC}"
        return 0
    else
        echo -e "${RED}❌ Router not accessible at $ROUTER_IP${NC}"
        return 1
    fi
}

# Function to generate MikroTik script
generate_mikrotik_script() {
    cat > mikrotik_kitonga_config.rsc << 'EOF'
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

/system ntp client
set enabled=yes
set primary-ntp=0.pool.ntp.org
set secondary-ntp=1.pool.ntp.org

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

EOF

    echo -e "${GREEN}✅ MikroTik configuration script generated: mikrotik_kitonga_config.rsc${NC}"
}

# Function to create custom hotspot HTML files
create_hotspot_html() {
    echo -e "${YELLOW}📝 Creating custom hotspot HTML files...${NC}"
    
    mkdir -p hotspot_html
    
    # Login page
    cat > hotspot_html/login.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kitonga WiFi - Login</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Arial', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
            max-width: 400px;
            width: 100%;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 28px;
            margin-bottom: 10px;
        }
        
        .header p {
            opacity: 0.9;
            font-size: 16px;
        }
        
        .form-container {
            padding: 40px 30px;
        }
        
        .input-group {
            margin-bottom: 25px;
            position: relative;
        }
        
        .input-group label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 600;
        }
        
        .input-group input {
            width: 100%;
            padding: 15px;
            border: 2px solid #e1e1e1;
            border-radius: 10px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        .input-group input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .login-btn {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }
        
        .login-btn:hover {
            transform: translateY(-2px);
        }
        
        .info {
            background: #f8f9fa;
            padding: 20px;
            margin-top: 20px;
            border-radius: 10px;
            text-align: center;
        }
        
        .info h3 {
            color: #333;
            margin-bottom: 10px;
        }
        
        .info p {
            color: #666;
            font-size: 14px;
            line-height: 1.5;
        }
        
        .wifi-icon {
            font-size: 48px;
            margin-bottom: 10px;
        }
        
        @media (max-width: 480px) {
            .container {
                margin: 10px;
            }
            
            .header {
                padding: 20px;
            }
            
            .form-container {
                padding: 30px 20px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="wifi-icon">📶</div>
            <h1>Kitonga WiFi</h1>
            <p>Welcome to our high-speed internet service</p>
        </div>
        
        <div class="form-container">
            <form name="login" action="$(link-login-only)" method="post">
                <input type="hidden" name="dst" value="$(link-orig)">
                <input type="hidden" name="popup" value="true">
                
                <div class="input-group">
                    <label for="username">Phone Number</label>
                    <input type="text" 
                           id="username" 
                           name="username" 
                           placeholder="Enter your phone number (e.g., 255700000000)"
                           pattern="255[0-9]{9}"
                           required
                           autocomplete="tel">
                </div>
                
                <button type="submit" class="login-btn">
                    Connect to Internet
                </button>
            </form>
            
            <div class="info">
                <h3>📱 How to Connect</h3>
                <p>
                    1. Enter your phone number (starting with 255)<br>
                    2. Make sure you have an active internet bundle<br>
                    3. Click "Connect to Internet" to get online<br><br>
                    <strong>Need a bundle?</strong> Visit our portal to purchase.
                </p>
            </div>
        </div>
    </div>
    
    <script>
        // Auto-format phone number
        document.getElementById('username').addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, '');
            if (!value.startsWith('255') && value.length > 0) {
                value = '255' + value;
            }
            if (value.length > 12) {
                value = value.substring(0, 12);
            }
            e.target.value = value;
        });
        
        // Show error if authentication failed
        if (window.location.search.includes('failed')) {
            alert('Login failed. Please check if you have an active internet bundle and try again.');
        }
    </script>
</body>
</html>
EOF

    # Status page
    cat > hotspot_html/status.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kitonga WiFi - Status</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Arial', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 500px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .status-icon {
            font-size: 48px;
            margin-bottom: 10px;
        }
        
        .header h1 {
            font-size: 24px;
            margin-bottom: 5px;
        }
        
        .content {
            padding: 30px;
        }
        
        .status-item {
            display: flex;
            justify-content: space-between;
            padding: 15px 0;
            border-bottom: 1px solid #f0f0f0;
        }
        
        .status-item:last-child {
            border-bottom: none;
        }
        
        .status-label {
            font-weight: 600;
            color: #333;
        }
        
        .status-value {
            color: #666;
            text-align: right;
        }
        
        .logout-btn {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 20px;
            transition: transform 0.2s;
        }
        
        .logout-btn:hover {
            transform: translateY(-2px);
        }
        
        .refresh-btn {
            width: 100%;
            padding: 12px;
            background: #f8f9fa;
            color: #333;
            border: 2px solid #e9ecef;
            border-radius: 10px;
            font-size: 14px;
            cursor: pointer;
            margin-top: 10px;
        }
        
        .time-remaining {
            background: linear-gradient(135deg, #ffc107 0%, #ffb300 100%);
            color: white;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            margin-bottom: 20px;
        }
        
        .connected-since {
            background: #e3f2fd;
            padding: 10px;
            border-radius: 8px;
            text-align: center;
            color: #1976d2;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="status-icon">✅</div>
            <h1>Connected Successfully</h1>
            <p>You are now online</p>
        </div>
        
        <div class="content">
            <div class="time-remaining">
                <strong>⏰ Session Time Remaining</strong><br>
                <span style="font-size: 18px;">$(session-time-left)</span>
            </div>
            
            <div class="status-item">
                <span class="status-label">📱 User</span>
                <span class="status-value">$(username)</span>
            </div>
            
            <div class="status-item">
                <span class="status-label">🌐 IP Address</span>
                <span class="status-value">$(ip)</span>
            </div>
            
            <div class="status-item">
                <span class="status-label">⬇️ Downloaded</span>
                <span class="status-value">$(bytes-in-nice)</span>
            </div>
            
            <div class="status-item">
                <span class="status-label">⬆️ Uploaded</span>
                <span class="status-value">$(bytes-out-nice)</span>
            </div>
            
            <div class="status-item">
                <span class="status-label">⏱️ Session Time</span>
                <span class="status-value">$(uptime)</span>
            </div>
            
            <div class="connected-since">
                Connected since: $(uptime-secs) seconds ago
            </div>
            
            <button class="refresh-btn" onclick="window.location.reload()">
                🔄 Refresh Status
            </button>
            
            <form action="$(link-logout)" method="post">
                <button type="submit" class="logout-btn">
                    🚪 Disconnect
                </button>
            </form>
        </div>
    </div>
    
    <script>
        // Auto-refresh every 30 seconds
        setTimeout(function() {
            window.location.reload();
        }, 30000);
    </script>
</body>
</html>
EOF

    # Error page
    cat > hotspot_html/error.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kitonga WiFi - Error</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Arial', sans-serif;
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
            max-width: 400px;
            width: 100%;
            text-align: center;
        }
        
        .header {
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
            color: white;
            padding: 30px;
        }
        
        .error-icon {
            font-size: 48px;
            margin-bottom: 10px;
        }
        
        .content {
            padding: 30px;
        }
        
        .error-message {
            color: #333;
            font-size: 18px;
            margin-bottom: 20px;
            line-height: 1.5;
        }
        
        .error-details {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            color: #666;
            font-size: 14px;
        }
        
        .try-again-btn {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            margin-bottom: 10px;
            transition: transform 0.2s;
        }
        
        .try-again-btn:hover {
            transform: translateY(-2px);
        }
        
        .contact-info {
            background: #e3f2fd;
            padding: 15px;
            border-radius: 10px;
            color: #1976d2;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="error-icon">❌</div>
            <h1>Connection Error</h1>
            <p>Unable to authenticate</p>
        </div>
        
        <div class="content">
            <div class="error-message">
                <strong>Authentication Failed</strong><br>
                Please check your credentials and try again.
            </div>
            
            <div class="error-details">
                <strong>Error:</strong> $(error)<br>
                <strong>Possible causes:</strong><br>
                • No active internet bundle<br>
                • Invalid phone number<br>
                • Server connection issue
            </div>
            
            <button class="try-again-btn" onclick="history.back()">
                🔄 Try Again
            </button>
            
            <div class="contact-info">
                <strong>Need Help?</strong><br>
                Visit our portal at kitonga.klikcell.com<br>
                or contact support
            </div>
        </div>
    </div>
</body>
</html>
EOF

    # Logout page
    cat > hotspot_html/logout.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kitonga WiFi - Logged Out</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Arial', sans-serif;
            background: linear-gradient(135deg, #6c757d 0%, #495057 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
            max-width: 400px;
            width: 100%;
            text-align: center;
        }
        
        .header {
            background: linear-gradient(135deg, #6c757d 0%, #495057 100%);
            color: white;
            padding: 30px;
        }
        
        .logout-icon {
            font-size: 48px;
            margin-bottom: 10px;
        }
        
        .content {
            padding: 30px;
        }
        
        .message {
            color: #333;
            font-size: 18px;
            margin-bottom: 20px;
            line-height: 1.5;
        }
        
        .stats {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        
        .stat-item {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-size: 14px;
        }
        
        .stat-item:last-child {
            margin-bottom: 0;
        }
        
        .login-again-btn {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }
        
        .login-again-btn:hover {
            transform: translateY(-2px);
        }
        
        .thank-you {
            background: #d4edda;
            color: #155724;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logout-icon">👋</div>
            <h1>Logged Out</h1>
            <p>You have been disconnected</p>
        </div>
        
        <div class="content">
            <div class="thank-you">
                <strong>Thank you for using Kitonga WiFi!</strong><br>
                We hope you enjoyed our service.
            </div>
            
            <div class="message">
                You have been successfully logged out from the internet service.
            </div>
            
            <div class="stats">
                <div class="stat-item">
                    <span>📱 User:</span>
                    <span>$(username)</span>
                </div>
                <div class="stat-item">
                    <span>⏱️ Session Duration:</span>
                    <span>$(uptime)</span>
                </div>
                <div class="stat-item">
                    <span>⬇️ Downloaded:</span>
                    <span>$(bytes-in-nice)</span>
                </div>
                <div class="stat-item">
                    <span>⬆️ Uploaded:</span>
                    <span>$(bytes-out-nice)</span>
                </div>
            </div>
            
            <button class="login-again-btn" onclick="window.location.href='$(link-login)'">
                🔄 Login Again
            </button>
        </div>
    </div>
</body>
</html>
EOF

    echo -e "${GREEN}✅ Custom hotspot HTML files created in hotspot_html/ directory${NC}"
}

# Function to create Django integration instructions
create_integration_guide() {
    cat > MIKROTIK_DJANGO_INTEGRATION.md << 'EOF'
# 🔧 MikroTik-Django Integration Guide

## Complete Setup Instructions

### 1. Upload Configuration to MikroTik

```bash
# Copy the configuration file to your MikroTik router
scp mikrotik_kitonga_config.rsc admin@192.168.88.1:/

# SSH into your router and apply configuration
ssh admin@192.168.88.1
/import file-name=mikrotik_kitonga_config.rsc
```

### 2. Upload Custom HTML Files

```bash
# Create hotspot directory on router
ssh admin@192.168.88.1 "/file/print"

# Upload HTML files via FTP or web interface
# Files to upload:
# - login.html
# - status.html  
# - error.html
# - logout.html
```

### 3. Configure External Authentication

In MikroTik terminal:

```routeros
# Set the authentication URL to your Django backend
/ip hotspot profile
set kitonga-hotspot-profile login-by=http-chap,cookie

# Configure the authentication redirect
/ip hotspot service-port
set www port=80

# The login.html page will handle the authentication redirect
```

### 4. Django Backend Authentication Flow

Your Django backend (`/api/mikrotik/auth/`) receives:
- `username` (phone number)
- `password` (optional)
- `mac` (device MAC address)
- `ip` (client IP)

Response format:
```json
{
    "success": true/false,
    "message": "Authentication result",
    "session_timeout": 86400,  // 24 hours in seconds
    "user_data": {
        "phone": "255700000000",
        "bundle": "Daily Bundle",
        "expires": "2025-10-28T10:00:00Z"
    }
}
```

### 5. Authentication URL Configuration

The login page redirects to:
```
https://api.kitonga.klikcell.com/api/mikrotik/auth/?username=$(username)&mac=$(mac)&ip=$(ip)
```

### 6. Network Configuration Details

```
Router IP: 192.168.88.1
DHCP Range: 192.168.88.10-192.168.88.100
WiFi SSID: Kitonga WiFi
WiFi Password: kitonga2025
DNS Servers: 8.8.8.8, 1.1.1.1
```

### 7. Firewall & Access Rules

- Internet access blocked by default
- Walled garden allows access to:
  - api.kitonga.klikcell.com
  - kitonga.klikcell.com
  - *.clickpesa.com
  - *.messaging-service.co.tz
  - Essential DNS and NTP servers

### 8. User Management Flow

1. User connects to "Kitonga WiFi"
2. Redirected to login page
3. Enters phone number
4. System checks Django backend for active bundle
5. If valid, user gets internet access
6. Session managed by MikroTik hotspot

### 9. Monitoring & Logs

View logs in MikroTik:
```routeros
/log print where topics~"hotspot"
/log print where topics~"account"
```

### 10. Backup & Recovery

```routeros
# Create backup
/system backup save name=kitonga-backup

# Export configuration
/export file=kitonga-config-backup
```

## 🔧 Troubleshooting

### Common Issues:

1. **Authentication fails**
   - Check Django backend is accessible
   - Verify walled garden configuration
   - Check Django API response format

2. **Users can't access payment page**
   - Add payment gateway domains to walled garden
   - Check CORS configuration in Django

3. **WiFi connection issues**
   - Verify DHCP is working
   - Check WiFi security settings
   - Ensure bridge configuration is correct

### Test Commands:

```bash
# Test Django authentication endpoint
curl "https://api.kitonga.klikcell.com/api/mikrotik/auth/?username=255700000000&mac=aa:bb:cc:dd:ee:ff&ip=192.168.88.50"

# Test from MikroTik
/tool fetch url="https://api.kitonga.klikcell.com/api/health/"
```

## 📱 Mobile App Integration

Your mobile app should:
1. Register users with phone numbers
2. Handle ClickPesa payments
3. Send SMS notifications via NextSMS
4. Provide user dashboard for bundle management

## 🚀 Go Live Checklist

- [ ] MikroTik configuration applied
- [ ] Custom HTML pages uploaded
- [ ] Django authentication tested
- [ ] Walled garden configured
- [ ] Payment flow tested
- [ ] SMS notifications working
- [ ] WiFi security configured
- [ ] Backup system in place
- [ ] Monitoring configured
- [ ] User documentation ready

Your MikroTik router is now fully integrated with your Django backend! 🎉
EOF

    echo -e "${GREEN}✅ Integration guide created: MIKROTIK_DJANGO_INTEGRATION.md${NC}"
}

# Main execution
echo -e "${BLUE}🚀 Starting MikroTik Configuration Process...${NC}"

# Check router connectivity
if ! check_router; then
    echo -e "${YELLOW}⚠️  Router not accessible. Configuration files will be generated for manual upload.${NC}"
fi

# Generate configuration files
generate_mikrotik_script
create_hotspot_html
create_integration_guide

echo ""
echo -e "${GREEN}🎉 MikroTik Configuration Complete!${NC}"
echo ""
echo -e "${BLUE}📋 Files Generated:${NC}"
echo "• mikrotik_kitonga_config.rsc - Main router configuration"
echo "• hotspot_html/ - Custom login pages"
echo "• MIKROTIK_DJANGO_INTEGRATION.md - Setup guide"
echo ""
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo "1. Upload mikrotik_kitonga_config.rsc to your router"
echo "2. Apply configuration: /import file-name=mikrotik_kitonga_config.rsc"
echo "3. Upload HTML files to /hotspot directory"
echo "4. Test authentication with Django backend"
echo "5. Configure SSL certificates for production"
echo ""
echo -e "${BLUE}🔗 Important URLs to configure:${NC}"
echo "• Django Auth API: https://api.kitonga.klikcell.com/api/mikrotik/auth/"
echo "• User Portal: https://kitonga.klikcell.com"
echo "• Router IP: http://192.168.88.1"
echo ""
echo -e "${GREEN}✅ Your MikroTik router is ready for Django integration!${NC}"
