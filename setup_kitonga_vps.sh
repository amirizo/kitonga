#!/bin/bash
# Kitonga Wi-Fi VPS Router Integration Setup
# Customized for server1.yum-express.com (66.29.143.116)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Your VPS Configuration
VPS_IP="66.29.143.116"
VPS_HOSTNAME="server1.yum-express.com"
FRONTEND_DOMAIN="kitonga.klikcell.com"
BACKEND_DOMAIN="api.kitonga.klikcell.com"
MIKROTIK_IP="192.168.0.173"
MIKROTIK_USER="admin"
MIKROTIK_PASS="Kijangwani2003"

echo -e "${BLUE}🚀 Kitonga Wi-Fi VPS Router Integration Setup${NC}"
echo "=============================================="
echo "VPS IP: ${VPS_IP}"
echo "Hostname: ${VPS_HOSTNAME}"
echo "Frontend: https://${FRONTEND_DOMAIN}"
echo "Backend API: https://${BACKEND_DOMAIN}"
echo "Router IP: ${MIKROTIK_IP}"
echo

print_status() {
    echo -e "${GREEN}[✅]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[⚠️]${NC} $1"
}

print_error() {
    echo -e "${RED}[❌]${NC} $1"
}

# Step 1: Check if we're on the correct VPS
print_status "Verifying VPS configuration..."
CURRENT_IP=$(curl -s ifconfig.me || echo "unknown")
if [ "$CURRENT_IP" = "$VPS_IP" ]; then
    print_status "✅ Running on correct VPS (${VPS_IP})"
else
    print_warning "⚠️  Expected IP: ${VPS_IP}, Current IP: ${CURRENT_IP}"
    read -p "Continue anyway? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Step 2: Update system packages
print_status "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Step 3: Install required packages
print_status "Installing required packages..."
sudo apt install -y \
    wireguard \
    netcat-openbsd \
    curl \
    wget \
    htop \
    python3-pip \
    ufw

# Step 4: Setup WireGuard for router connection
print_status "Setting up WireGuard VPN..."

# Generate WireGuard keys if they don't exist
if [ ! -f /etc/wireguard/privatekey ]; then
    sudo mkdir -p /etc/wireguard
    wg genkey | sudo tee /etc/wireguard/privatekey | wg pubkey | sudo tee /etc/wireguard/publickey
    sudo chmod 600 /etc/wireguard/privatekey
    print_status "WireGuard keys generated"
fi

VPS_PUBLIC_KEY=$(sudo cat /etc/wireguard/publickey)
VPS_PRIVATE_KEY=$(sudo cat /etc/wireguard/privatekey)

# Create WireGuard configuration
print_status "Creating WireGuard configuration..."
sudo tee /etc/wireguard/wg0.conf > /dev/null << EOF
[Interface]
PrivateKey = ${VPS_PRIVATE_KEY}
Address = 10.10.0.2/24
ListenPort = 13231

[Peer]
# PublicKey = ROUTER_PUBLIC_KEY_GOES_HERE
# Endpoint = YOUR_HOME_PUBLIC_IP:13231
AllowedIPs = 10.10.0.0/24, 192.168.0.0/24
PersistentKeepalive = 25
EOF

# Step 5: Configure firewall
print_status "Configuring UFW firewall..."
sudo ufw --force enable
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow 13231/udp  # WireGuard

# Step 6: Find Django project directory
print_status "Locating Django project..."

# Common locations for Django projects
POSSIBLE_DIRS=(
    "/opt/kitonga"
    "/var/www/kitonga"
    "/home/$(whoami)/kitonga"
    "/root/kitonga"
    "$(pwd)"
)

PROJECT_DIR=""
for dir in "${POSSIBLE_DIRS[@]}"; do
    if [ -f "$dir/manage.py" ]; then
        PROJECT_DIR="$dir"
        break
    fi
done

if [ -z "$PROJECT_DIR" ]; then
    echo "Django project not found in common locations."
    read -p "Enter the full path to your Django project: " PROJECT_DIR
    if [ ! -f "$PROJECT_DIR/manage.py" ]; then
        print_error "manage.py not found in $PROJECT_DIR"
        exit 1
    fi
fi

print_status "Found Django project at: $PROJECT_DIR"

# Step 7: Update environment configuration
print_status "Updating environment configuration..."

cd "$PROJECT_DIR"

# Backup existing .env
if [ -f ".env" ]; then
    cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    print_status "Backed up existing .env file"
fi

# Update .env for VPS configuration
print_status "Configuring environment variables..."

# Remove or disable mock mode
if grep -q "MIKROTIK_MOCK_MODE=true" .env 2>/dev/null; then
    sed -i 's/MIKROTIK_MOCK_MODE=true/MIKROTIK_MOCK_MODE=false/' .env
    print_status "Disabled MIKROTIK_MOCK_MODE"
fi

# Function to update or add environment variable
update_env_var() {
    local key=$1
    local value=$2
    
    if grep -q "^${key}=" .env 2>/dev/null; then
        sed -i "s/^${key}=.*/${key}=${value}/" .env
    else
        echo "${key}=${value}" >> .env
    fi
}

# Update critical settings
update_env_var "MIKROTIK_HOST" "10.10.0.1"
update_env_var "MIKROTIK_PORT" "8728"
update_env_var "MIKROTIK_USER" "$MIKROTIK_USER"
update_env_var "MIKROTIK_PASSWORD" "$MIKROTIK_PASS"
update_env_var "MIKROTIK_MOCK_MODE" "false"
update_env_var "DEBUG" "False"
update_env_var "ALLOWED_HOSTS" "${BACKEND_DOMAIN},${FRONTEND_DOMAIN},${VPS_IP},localhost"
update_env_var "CORS_ALLOWED_ORIGINS" "https://${FRONTEND_DOMAIN},https://${BACKEND_DOMAIN}"
update_env_var "CSRF_TRUSTED_ORIGINS" "https://${FRONTEND_DOMAIN},https://${BACKEND_DOMAIN}"

print_status "Environment configuration updated"

# Step 8: Install Python dependencies
print_status "Installing/updating Python dependencies..."

# Check if virtual environment exists
if [ -d "venv" ]; then
    source venv/bin/activate
    print_status "Activated virtual environment"
elif [ -d ".venv" ]; then
    source .venv/bin/activate
    print_status "Activated virtual environment"
else
    print_warning "Virtual environment not found - using system Python"
fi

# Install/upgrade routeros-api
pip install --upgrade routeros-api==0.21.0
pip install --upgrade python-decouple

print_status "Python dependencies updated"

# Step 9: Create connectivity test script
print_status "Creating connectivity test script..."

cat > test_router_connection.py << 'EOF'
#!/usr/bin/env python3
"""
Test router connectivity for Kitonga Wi-Fi VPS integration
"""

import socket
import sys
import os
from datetime import datetime

# Test configuration
VPN_ROUTER_IP = "10.10.0.1"
DIRECT_ROUTER_IP = "192.168.0.173"
API_PORT = 8728

def test_connection(host, port, name):
    """Test TCP connection to host:port"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✅ {name}: CONNECTED")
            return True
        else:
            print(f"❌ {name}: FAILED")
            return False
    except Exception as e:
        print(f"❌ {name}: ERROR - {e}")
        return False

def main():
    print("🧪 Kitonga Wi-Fi Router Connectivity Test")
    print("=" * 50)
    print(f"Test Time: {datetime.now()}")
    print()
    
    tests = [
        (VPN_ROUTER_IP, API_PORT, "VPN Router Connection (10.10.0.1:8728)"),
        (DIRECT_ROUTER_IP, API_PORT, "Direct Router Connection (192.168.0.173:8728)"),
        (VPN_ROUTER_IP, 22, "VPN Router SSH (10.10.0.1:22)"),
        (DIRECT_ROUTER_IP, 22, "Direct Router SSH (192.168.0.173:22)"),
    ]
    
    results = []
    for host, port, name in tests:
        success = test_connection(host, port, name)
        results.append(success)
    
    print()
    print("=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    
    if results[0]:  # VPN connection works
        print("\n🎉 VPN connection successful! Use MIKROTIK_HOST=10.10.0.1")
    elif results[1]:  # Direct connection works
        print("\n⚠️  Direct connection only. Use MIKROTIK_HOST=192.168.0.173")
        print("Consider setting up VPN for security")
    else:
        print("\n❌ No router connectivity. Check:")
        print("   • Router is powered on")
        print("   • Network connectivity")
        print("   • VPN configuration")
        print("   • Firewall settings")
    
    return passed > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
EOF

chmod +x test_router_connection.py

# Step 10: Create MikroTik configuration commands
print_status "Creating MikroTik configuration commands..."

cat > mikrotik_setup_commands.rsc << EOF
# Kitonga Wi-Fi MikroTik Configuration for VPS Integration
# Run these commands on your MikroTik router

# 1. Create WireGuard interface for VPS connection
/interface wireguard
add listen-port=13231 mtu=1420 name=wg-to-vps

# 2. Add VPS as WireGuard peer (REPLACE PUBLIC KEY!)
/interface wireguard peers
add allowed-address=10.10.0.2/32 interface=wg-to-vps public-key="${VPS_PUBLIC_KEY}"

# 3. Configure IP address for VPN
/ip address
add address=10.10.0.1/24 interface=wg-to-vps

# 4. Configure firewall rules for VPS access
/ip firewall filter
add action=accept chain=input dst-port=13231 protocol=udp comment="WireGuard VPS"
add action=accept chain=input src-address=10.10.0.0/24 comment="Allow VPS access"
add action=accept chain=input protocol=tcp dst-port=8728 src-address=10.10.0.0/24 comment="API access from VPS"

# 5. Configure API service for VPS access
/ip service
set api disabled=no
set api address=10.10.0.0/24

# 6. Configure DNS (important for external auth)
/ip dns
set servers=8.8.8.8,1.1.1.1
set allow-remote-requests=yes

# 7. Configure external authentication URLs
/ip hotspot user profile
set [find default=yes] \\
  login-by=cookie,http-chap \\
  http-login-url="https://${BACKEND_DOMAIN}/api/mikrotik/auth/" \\
  http-logout-url="https://${BACKEND_DOMAIN}/api/mikrotik/logout/"

# 8. Security: Block external API access
/ip firewall filter
add action=drop chain=input protocol=tcp dst-port=8728 src-address=!10.10.0.0/24 comment="Block external API"

# Print configuration for verification
/interface wireguard print
/interface wireguard peers print  
/ip address print where interface=wg-to-vps
/ip firewall filter print where comment~"VPS"
EOF

print_status "MikroTik configuration commands created"

# Step 11: Test current connectivity
print_status "Testing current router connectivity..."
python3 test_router_connection.py

# Step 12: Final summary
echo
echo -e "${GREEN}🎉 VPS Router Integration Setup Complete!${NC}"
echo "=============================================="
echo
echo -e "${YELLOW}📋 NEXT STEPS:${NC}"
echo
echo "1. 🔧 Configure MikroTik Router:"
echo "   • Copy commands from: mikrotik_setup_commands.rsc"
echo "   • Connect to your router: http://192.168.0.173"
echo "   • Paste commands in terminal or use WinBox"
echo
echo "2. 🌐 Start WireGuard VPN:"
echo "   • Configure router endpoint in /etc/wireguard/wg0.conf"
echo "   • Add your home public IP"
echo "   • Start: sudo systemctl start wg-quick@wg0"
echo "   • Enable: sudo systemctl enable wg-quick@wg0"
echo
echo "3. 🧪 Test Everything:"
echo "   • Run: python3 test_router_connection.py"
echo "   • Test API: curl -X GET https://${BACKEND_DOMAIN}/api/admin/mikrotik/router-info/ -H \"X-Admin-Access: kitonga_admin_2025\""
echo
echo "4. 🔄 Restart Application:"
echo "   • Restart your Django application"
echo "   • Check logs for any errors"
echo
echo -e "${BLUE}📖 Key Information:${NC}"
echo "VPS Public Key: ${VPS_PUBLIC_KEY}"
echo "VPS IP: ${VPS_IP}"
echo "Backend: https://${BACKEND_DOMAIN}"
echo "Frontend: https://${FRONTEND_DOMAIN}"
echo
echo -e "${GREEN}✅ Your VPS is ready for router integration!${NC}"

# Display WireGuard config that needs completion
echo
echo -e "${YELLOW}⚠️  IMPORTANT: Complete WireGuard Configuration${NC}"
echo "Edit /etc/wireguard/wg0.conf and add:"
echo "   • Your MikroTik router's public key"
echo "   • Your home's public IP address"
echo
echo "Current WireGuard config:"
sudo cat /etc/wireguard/wg0.conf
