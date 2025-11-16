#!/bin/bash
# VPS MikroTik Integration Setup Script
# Automated setup for Kitonga Wi-Fi system on VPS

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration variables
PROJECT_NAME="kitonga"
MIKROTIK_IP="192.168.0.173"
MIKROTIK_USER="admin"
MIKROTIK_PASS="Kijangwani2003"
VPN_NETWORK="10.10.0.0/24"
VPS_VPN_IP="10.10.0.2"
ROUTER_VPN_IP="10.10.0.1"

echo -e "${BLUE}🚀 VPS MikroTik Integration Setup${NC}"
echo "========================================"

# Function to print status
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_warning "Running as root. Consider running as non-root user for security."
fi

# Step 1: System Update
print_status "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Step 2: Install required packages
print_status "Installing required packages..."
sudo apt install -y \
    python3-pip \
    python3-venv \
    git \
    nginx \
    ufw \
    wireguard \
    netcat-openbsd \
    curl \
    wget \
    htop

# Step 3: Configure firewall
print_status "Configuring firewall..."
sudo ufw --force enable
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow 13231/udp  # WireGuard

print_status "Firewall configured successfully"

# Step 4: Setup WireGuard
print_status "Setting up WireGuard VPN..."

# Generate WireGuard keys
if [ ! -f /etc/wireguard/privatekey ]; then
    sudo mkdir -p /etc/wireguard
    wg genkey | sudo tee /etc/wireguard/privatekey | wg pubkey | sudo tee /etc/wireguard/publickey
    sudo chmod 600 /etc/wireguard/privatekey
    print_status "WireGuard keys generated"
fi

# Get public key for display
VPS_PUBLIC_KEY=$(sudo cat /etc/wireguard/publickey)

# Create WireGuard config template
if [ ! -f /etc/wireguard/wg0.conf ]; then
    print_status "Creating WireGuard configuration..."
    sudo tee /etc/wireguard/wg0.conf > /dev/null << EOF
[Interface]
PrivateKey = $(sudo cat /etc/wireguard/privatekey)
Address = ${VPS_VPN_IP}/24
ListenPort = 13231

[Peer]
# PublicKey = ROUTER_PUBLIC_KEY_HERE
# Endpoint = YOUR_HOME_PUBLIC_IP:13231
AllowedIPs = ${VPN_NETWORK}, 192.168.0.0/24
PersistentKeepalive = 25
EOF
    
    print_warning "WireGuard config created. You need to:"
    echo "1. Get your MikroTik router's WireGuard public key"
    echo "2. Replace ROUTER_PUBLIC_KEY_HERE with the actual key"
    echo "3. Replace YOUR_HOME_PUBLIC_IP with your home's public IP"
    echo "4. Edit /etc/wireguard/wg0.conf manually"
fi

# Step 5: Test basic connectivity
print_status "Testing system connectivity..."

# Test internet connectivity
if curl -s --connect-timeout 5 google.com > /dev/null; then
    print_status "Internet connectivity: OK"
else
    print_error "Internet connectivity: FAILED"
    exit 1
fi

# Step 6: Create project directory structure
PROJECT_DIR="/opt/${PROJECT_NAME}"
print_status "Setting up project directory: ${PROJECT_DIR}"

if [ ! -d "$PROJECT_DIR" ]; then
    sudo mkdir -p "$PROJECT_DIR"
    sudo chown $USER:$USER "$PROJECT_DIR"
fi

cd "$PROJECT_DIR"

# Step 7: Setup Python virtual environment
if [ ! -d "venv" ]; then
    print_status "Creating Python virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    print_status "Virtual environment created"
else
    print_status "Virtual environment already exists"
    source venv/bin/activate
fi

# Step 8: Install Python dependencies for MikroTik
print_status "Installing Python dependencies..."
pip install routeros-api==0.21.0
pip install django
pip install python-decouple
pip install requests

# Step 9: Create environment configuration template
ENV_FILE="${PROJECT_DIR}/.env.template"
print_status "Creating environment configuration template..."

cat > "$ENV_FILE" << EOF
# Django Configuration
SECRET_KEY=your-production-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-domain.com,$(curl -s ifconfig.me)

# Database Configuration
DATABASE_URL=sqlite:///db.sqlite3

# MikroTik Router Configuration
MIKROTIK_HOST=${ROUTER_VPN_IP}
MIKROTIK_PORT=8728
MIKROTIK_USER=${MIKROTIK_USER}
MIKROTIK_PASSWORD=${MIKROTIK_PASS}
MIKROTIK_USE_SSL=False
MIKROTIK_DEFAULT_PROFILE=default
MIKROTIK_MOCK_MODE=false

# Payment & SMS Configuration (Update with your values)
CLICKPESA_CLIENT_ID=your_clickpesa_client_id
CLICKPESA_API_KEY=your_clickpesa_api_key
NEXTSMS_USERNAME=your_nextsms_username
NEXTSMS_PASSWORD=your_nextsms_password

# Admin Configuration
SIMPLE_ADMIN_TOKEN=kitonga_admin_2025

# Security
CSRF_TRUSTED_ORIGINS=https://your-domain.com
CORS_ALLOWED_ORIGINS=https://your-domain.com
EOF

print_status "Environment template created at: $ENV_FILE"

# Step 10: Create connectivity test script
TEST_SCRIPT="${PROJECT_DIR}/test_connectivity.py"
cat > "$TEST_SCRIPT" << 'EOF'
#!/usr/bin/env python3
"""
Test script for VPS-MikroTik connectivity
"""

import socket
import sys
import os
from datetime import datetime

# Configuration
MIKROTIK_IP = "10.10.0.1"  # VPN IP
MIKROTIK_API_PORT = 8728
MIKROTIK_HTTP_PORT = 80

def test_connectivity():
    print("🧪 VPS-MikroTik Connectivity Test")
    print("=" * 50)
    print(f"Test Time: {datetime.now()}")
    print(f"Target Router: {MIKROTIK_IP}")
    print()
    
    results = {}
    
    # Test 1: Ping equivalent (socket connection test)
    print("1. Testing basic network connectivity...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((MIKROTIK_IP, 22))  # SSH port
        sock.close()
        
        if result == 0:
            print("   ✅ Network connectivity: OK")
            results['network'] = True
        else:
            print("   ❌ Network connectivity: FAILED")
            results['network'] = False
    except Exception as e:
        print(f"   ❌ Network test error: {e}")
        results['network'] = False
    
    # Test 2: API Port
    print("\n2. Testing MikroTik API port...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((MIKROTIK_IP, MIKROTIK_API_PORT))
        sock.close()
        
        if result == 0:
            print(f"   ✅ API port {MIKROTIK_API_PORT}: ACCESSIBLE")
            results['api'] = True
        else:
            print(f"   ❌ API port {MIKROTIK_API_PORT}: NOT ACCESSIBLE")
            results['api'] = False
    except Exception as e:
        print(f"   ❌ API port test error: {e}")
        results['api'] = False
    
    # Test 3: HTTP Port (if enabled)
    print("\n3. Testing MikroTik HTTP port...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((MIKROTIK_IP, MIKROTIK_HTTP_PORT))
        sock.close()
        
        if result == 0:
            print(f"   ✅ HTTP port {MIKROTIK_HTTP_PORT}: ACCESSIBLE")
            results['http'] = True
        else:
            print(f"   ⚠️  HTTP port {MIKROTIK_HTTP_PORT}: NOT ACCESSIBLE (may be disabled)")
            results['http'] = False
    except Exception as e:
        print(f"   ❌ HTTP port test error: {e}")
        results['http'] = False
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 CONNECTIVITY SUMMARY")
    print("=" * 50)
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    for test, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test.upper()} connectivity")
    
    print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
    
    if results.get('network') and results.get('api'):
        print("\n🎉 SUCCESS: Your VPS can communicate with MikroTik router!")
        print("You can proceed with Django application deployment.")
    else:
        print("\n⚠️  ISSUES DETECTED:")
        if not results.get('network'):
            print("   - Network connectivity failed. Check VPN configuration.")
        if not results.get('api'):
            print("   - API port not accessible. Check router API service and firewall.")
        print("\nRefer to VPS_MIKROTIK_SETUP_GUIDE.md for troubleshooting.")

if __name__ == "__main__":
    test_connectivity()
EOF

chmod +x "$TEST_SCRIPT"
print_status "Connectivity test script created: $TEST_SCRIPT"

# Step 11: Create MikroTik configuration commands
MIKROTIK_COMMANDS="${PROJECT_DIR}/mikrotik_commands.rsc"
cat > "$MIKROTIK_COMMANDS" << EOF
# MikroTik Router Configuration for VPS Integration
# Copy and paste these commands into your MikroTik terminal

# 1. Create WireGuard interface
/interface wireguard
add listen-port=13231 mtu=1420 name=wg-to-vps

# 2. Add WireGuard peer (replace with your VPS public key)
/interface wireguard peers
add allowed-address=${VPS_VPN_IP}/32 interface=wg-to-vps public-key="${VPS_PUBLIC_KEY}"

# 3. Configure IP address for VPN
/ip address
add address=${ROUTER_VPN_IP}/24 interface=wg-to-vps

# 4. Configure firewall rules
/ip firewall filter
add action=accept chain=input dst-port=13231 protocol=udp comment="WireGuard VPS"
add action=accept chain=input src-address=${VPN_NETWORK} comment="Allow VPS access"
add action=accept chain=input protocol=tcp dst-port=8728 src-address=${VPN_NETWORK} comment="API access from VPS"

# 5. Configure API service
/ip service
set api disabled=no
set api address=${VPN_NETWORK}

# 6. Configure DNS (important for external auth)
/ip dns
set servers=8.8.8.8,1.1.1.1
set allow-remote-requests=yes

# 7. Configure hotspot external authentication (replace with your domain)
/ip hotspot user profile
set [find default=yes] \\
  login-by=cookie,http-chap \\
  http-login-url="https://your-domain.com/api/mikrotik/auth/" \\
  http-logout-url="https://your-domain.com/api/mikrotik/logout/"

# Print configuration for verification
/interface wireguard print
/interface wireguard peers print
/ip address print where interface=wg-to-vps
/ip firewall filter print where comment~"VPS"
EOF

print_status "MikroTik configuration commands created: $MIKROTIK_COMMANDS"

# Step 12: Create systemd service for connectivity monitoring
MONITOR_SERVICE="/etc/systemd/system/mikrotik-monitor.service"
print_status "Creating connectivity monitoring service..."

sudo tee "$MONITOR_SERVICE" > /dev/null << EOF
[Unit]
Description=MikroTik Connectivity Monitor
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=/bin/bash -c 'while true; do python3 test_connectivity.py >> /var/log/mikrotik-monitor.log 2>&1; sleep 300; done'
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
print_status "Monitoring service created (not started yet)"

# Step 13: Create log rotation configuration
print_status "Setting up log rotation..."
sudo mkdir -p /var/log
sudo tee /etc/logrotate.d/mikrotik > /dev/null << EOF
/var/log/mikrotik-monitor.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
    create 644 $USER $USER
}
EOF

# Step 14: Summary and next steps
echo
echo -e "${GREEN}🎉 VPS MikroTik Integration Setup Complete!${NC}"
echo "============================================"
echo
echo -e "${YELLOW}📋 NEXT STEPS:${NC}"
echo
echo "1. 📝 Configure MikroTik Router:"
echo "   - Copy commands from: $MIKROTIK_COMMANDS"
echo "   - Paste them into your MikroTik terminal"
echo "   - Update the WireGuard peer public key"
echo
echo "2. 🔧 Configure WireGuard:"
echo "   - Edit: /etc/wireguard/wg0.conf"
echo "   - Add your router's public key and home IP"
echo "   - Start: sudo systemctl start wg-quick@wg0"
echo "   - Enable: sudo systemctl enable wg-quick@wg0"
echo
echo "3. 🧪 Test Connectivity:"
echo "   - Run: python3 $TEST_SCRIPT"
echo "   - Should show successful connections"
echo
echo "4. 🚀 Deploy Your Application:"
echo "   - Copy your Django project to: $PROJECT_DIR"
echo "   - Update .env from template: $ENV_FILE"
echo "   - Install dependencies: pip install -r requirements.txt"
echo "   - Run migrations: python manage.py migrate"
echo
echo "5. 🔒 Security Hardening:"
echo "   - Change default passwords"
echo "   - Configure SSL certificates"
echo "   - Review firewall rules"
echo
echo -e "${BLUE}📖 Documentation:${NC}"
echo "   - Full guide: VPS_MIKROTIK_SETUP_GUIDE.md"
echo "   - Router config: $MIKROTIK_COMMANDS"
echo "   - Environment template: $ENV_FILE"
echo "   - Connectivity test: $TEST_SCRIPT"
echo
echo -e "${GREEN}✅ Your VPS is ready for MikroTik integration!${NC}"

# Display important information
echo
echo -e "${YELLOW}🔑 IMPORTANT INFORMATION:${NC}"
echo "VPS Public Key: $VPS_PUBLIC_KEY"
echo "VPS IP (for router config): $(curl -s ifconfig.me)"
echo "VPN Network: $VPN_NETWORK"
echo "Router VPN IP: $ROUTER_VPN_IP"
echo "VPS VPN IP: $VPS_VPN_IP"
