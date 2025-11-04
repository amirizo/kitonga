#!/bin/bash
# 🎯 MikroTik Router Configuration for Frontend Integration
# =======================================================

echo "🔧 CONFIGURING MIKROTIK FOR FRONTEND INTEGRATION"
echo "================================================"
echo ""
echo "Current Issue: Router shows default login page"
echo "Solution: Configure router to redirect to your frontend"
echo ""

echo "✅ STEP 1: Configure Walled Garden"
echo "=================================="
echo "Allow access to your domains before login:"
echo ""
echo "/ip hotspot walled-garden add dst-host=kitonga.klikcell.com action=allow"
echo "/ip hotspot walled-garden add dst-host=api.kitonga.klikcell.com action=allow"
echo "/ip hotspot walled-garden add dst-host=*.klikcell.com action=allow"
echo ""

echo "✅ STEP 2: Configure Hotspot Server for External Redirect"
echo "=========================================================="
echo "Set your router to redirect to your frontend:"
echo ""
echo "# Check current server configuration"
echo "/ip hotspot server print"
echo ""
echo "# Configure redirect (replace 0 with your server number if different)"
echo "/ip hotspot server set 0 login-by=http-chap"
echo ""

echo "✅ STEP 3: Upload Custom Login Page (Option A - Recommended)"
echo "============================================================"
echo "Create a simple redirect page that sends users to your frontend:"
echo ""
echo "Upload this login.html to your router's hotspot directory:"
echo "------------------------------------------------------------------------"
cat << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Kitonga WiFi</title>
    <meta http-equiv="refresh" content="0;url=https://kitonga.klikcell.com/?mac=$(mac)&ip=$(ip)&username=$(username)&link_login=$(link-login)&link_orig=$(link-orig)&source=mikrotik">
    <script>
        window.location.href = "https://kitonga.klikcell.com/?mac=$(mac)&ip=$(ip)&username=$(username)&link_login=$(link-login)&link_orig=$(link-orig)&source=mikrotik";
    </script>
</head>
<body>
    <p>Redirecting to Kitonga WiFi portal...</p>
    <p>If not redirected automatically, <a href="https://kitonga.klikcell.com/?mac=$(mac)&ip=$(ip)&username=$(username)&link_login=$(link-login)&link_orig=$(link-orig)&source=mikrotik">click here</a></p>
</body>
</html>
EOF
echo "------------------------------------------------------------------------"
echo ""

echo "✅ STEP 4: Alternative Method (Option B - HTTP Redirect)"
echo "========================================================"
echo "Configure direct HTTP redirect (if supported by your RouterOS):"
echo ""
echo "/ip hotspot server set 0 http-redirect=\"https://kitonga.klikcell.com/\""
echo ""

echo "✅ STEP 5: Verification Commands"
echo "================================"
echo "Check your configuration:"
echo ""
echo "/ip hotspot walled-garden print"
echo "/ip hotspot server print detail"
echo "/ip hotspot active print"
echo ""

echo "🎯 HOW IT SHOULD WORK AFTER CONFIGURATION"
echo "=========================================="
echo "1. User connects to WiFi → Gets IP from router"
echo "2. User opens browser → Router redirects to: https://kitonga.klikcell.com/"
echo "3. Your frontend receives parameters: mac, ip, link_login, etc."
echo "4. Frontend calls your Django APIs to check access/payment"
echo "5. If payment needed → Show payment interface"
echo "6. If access granted → Frontend calls link_login to authorize user"
echo "7. Router grants internet access"
echo ""

echo "📱 FRONTEND PARAMETERS YOUR SITE WILL RECEIVE"
echo "=============================================="
echo "URL: https://kitonga.klikcell.com/?mac=XX:XX:XX&ip=192.168.X.X&..."
echo ""
echo "Parameters:"
echo "• mac: Device MAC address"
echo "• ip: Device IP address"
echo "• username: User input (if any)"
echo "• link_login: MikroTik URL to grant access"
echo "• link_orig: Original URL user wanted"
echo "• source: 'mikrotik'"
echo ""

echo "🚀 COMMANDS TO RUN ON YOUR ROUTER NOW"
echo "====================================="
echo "Copy and paste these commands in your MikroTik CLI:"
echo ""
echo "1. /ip hotspot walled-garden add dst-host=kitonga.klikcell.com action=allow"
echo "2. /ip hotspot walled-garden add dst-host=api.kitonga.klikcell.com action=allow"
echo "3. /ip hotspot server set 0 login-by=http-chap"
echo "4. Upload the redirect login.html file above"
echo ""

echo "✅ TEST AFTER CONFIGURATION"
echo "==========================="
echo "1. Connect device to WiFi"
echo "2. Open browser → Should redirect to https://kitonga.klikcell.com/"
echo "3. Your frontend handles the user experience"
echo "4. After payment → Frontend calls MikroTik login URL"
echo "5. User gets internet access"
