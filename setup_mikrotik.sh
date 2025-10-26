#!/bin/bash

# Kitonga Wi-Fi Billing System - Mikrotik Integration Setup Script
# This script helps set up and test the Mikrotik integration

echo "======================================"
echo "Kitonga Wi-Fi Billing System"
echo "Mikrotik Integration Setup"
echo "======================================"

# Check if Django is running
echo "1. Checking Django server status..."
if curl -s http://localhost:8000/api/health/ > /dev/null; then
    echo "✓ Django server is running"
else
    echo "✗ Django server is not running"
    echo "Please start Django with: python manage.py runserver"
    exit 1
fi

# Check if Mikrotik router is reachable
echo ""
echo "2. Checking Mikrotik router connectivity..."
ROUTER_IP=${MIKROTIK_ROUTER_IP:-192.168.88.1}
if ping -c 1 -W 2 $ROUTER_IP > /dev/null 2>&1; then
    echo "✓ Mikrotik router ($ROUTER_IP) is reachable"
else
    echo "✗ Mikrotik router ($ROUTER_IP) is not reachable"
    echo "Please check your network connection and router IP"
fi

# Check hotspot login page
echo ""
echo "3. Checking Mikrotik hotspot login page..."
if curl -s http://$ROUTER_IP/login | grep -i "username" > /dev/null; then
    echo "✓ Hotspot login page is accessible"
else
    echo "⚠ Hotspot login page may not be configured"
fi

# Test Django management command
echo ""
echo "4. Running Django Mikrotik test command..."
cd /Users/macbookair/Desktop/kitonga
python manage.py test_mikrotik --router-ip=$ROUTER_IP

echo ""
echo "======================================"
echo "Setup Instructions:"
echo "======================================"

echo ""
echo "1. Configure your Mikrotik router with these commands:"
echo ""
echo "# Basic hotspot setup"
echo "/ip hotspot user profile"
echo "add name=\"kitonga-profile\" shared-users=1 idle-timeout=none keepalive-timeout=2m \\"
echo "    mac-cookie-timeout=3d address-pool=dhcp_pool1 transparent-proxy=yes"
echo ""
echo "# Enable external HTTP authentication"
echo "/ip hotspot user profile"
echo "set hsprof1 name=\"default\" shared-users=1 \\"
echo "    address-pool=dhcp_pool1 transparent-proxy=yes \\"
echo "    login-by=http-post \\"
echo "    http-post-url=\"http://$(hostname -I | awk '{print $1}'):8000/api/mikrotik/auth/\" \\"
echo "    http-post-data=\"username=\\\$(username)&password=\\\$(password)&mac=\\\$(mac)&ip=\\\$(ip)\""
echo ""
echo "# Add Django server to walled garden"
echo "/ip hotspot walled-garden"
echo "add dst-host=$(hostname -I | awk '{print $1}') comment=\"Django server access\""
echo ""

echo "2. Environment Variables:"
echo "Add these to your .env file:"
echo ""
echo "MIKROTIK_ROUTER_IP=$ROUTER_IP"
echo "MIKROTIK_ADMIN_USER=admin"
echo "MIKROTIK_ADMIN_PASS=your_admin_password"
echo "MIKROTIK_API_PORT=8728"
echo "MIKROTIK_HOTSPOT_NAME=hotspot1"
echo ""

echo "3. Test Authentication:"
echo "Create a test user in Django admin, then try connecting to the hotspot"
echo ""

echo "4. API Endpoints:"
echo "- Authentication: http://$(hostname -I | awk '{print $1}'):8000/api/mikrotik/auth/"
echo "- Logout: http://$(hostname -I | awk '{print $1}'):8000/api/mikrotik/logout/"
echo "- Status Check: http://$(hostname -I | awk '{print $1}'):8000/api/mikrotik/status/"
echo ""

echo "======================================"
echo "Troubleshooting:"
echo "======================================"
echo "- Check Django logs: tail -f logs/django.log"
echo "- Check Mikrotik logs: /log print where topics~\"hotspot\""
echo "- Test API directly: curl -X POST http://localhost:8000/api/mikrotik/auth/ -d \"username=255708374149\""
echo ""

echo "Setup complete! Check the documentation in docs/ROUTER_SETUP.md for detailed instructions."
