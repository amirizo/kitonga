#!/bin/bash
# 🎯 CORRECT MikroTik Commands for RouterOS 6.49.19
# =================================================

echo "🎉 SUCCESS! Found the correct command structure!"
echo "==============================================="
echo ""
echo "Your RouterOS 6.49.19 uses:"
echo "• /ip hotspot profile (not user-profile)"
echo "• /ip hotspot user"
echo ""

echo "✅ STEP 1: Check Current Profiles"
echo "================================="
echo "You're already in /ip hotspot menu, so run:"
echo ""
echo "profile print"
echo ""
echo "This will show you available profiles (likely 'default')"
echo ""

echo "✅ STEP 2: Configure External Authentication"
echo "============================================"
echo "Still in /ip hotspot menu, run these commands:"
echo ""
echo "# Configure the default profile for cookie authentication"
echo "profile set default login-by=cookie"
echo ""
echo "# Set authentication URL"
echo 'profile set default http-cookie-auth-url="https://api.kitonga.klikcell.com/api/mikrotik/auth/"'
echo ""
echo "# Set logout URL"
echo 'profile set default http-cookie-logout-url="https://api.kitonga.klikcell.com/api/mikrotik/logout/"'
echo ""

echo "✅ STEP 3: Verify Configuration"
echo "==============================="
echo "Check if the settings were applied:"
echo ""
echo "profile print detail"
echo ""

echo "✅ STEP 4: Exit and Test"
echo "========================"
echo "Exit hotspot menu:"
echo "/"
echo ""
echo "Then test your configuration!"
echo ""

echo "📋 COMPLETE COMMAND SEQUENCE"
echo "============================"
echo "Since you're already in /ip hotspot menu:"
echo ""
echo "1. profile print"
echo "2. profile set default login-by=cookie"
echo '3. profile set default http-cookie-auth-url="https://api.kitonga.klikcell.com/api/mikrotik/auth/"'
echo '4. profile set default http-cookie-logout-url="https://api.kitonga.klikcell.com/api/mikrotik/logout/"'
echo "5. profile print detail"
echo "6. /"
echo ""

echo "🎯 EXPECTED OUTPUT"
echo "=================="
echo "After 'profile print detail' you should see:"
echo ""
echo "login-by: cookie"
echo "http-cookie-auth-url: https://api.kitonga.klikcell.com/api/mikrotik/auth/"
echo "http-cookie-logout-url: https://api.kitonga.klikcell.com/api/mikrotik/logout/"
echo ""

echo "🚀 READY TO TEST!"
echo "=================="
echo "Once configured:"
echo "1. Connect a device to your WiFi hotspot"
echo "2. Browser should redirect to captive portal"
echo "3. Enter phone number as username"
echo "4. Check Django admin for access logs"
echo ""

echo "💡 You're almost there! Your router supports external authentication!"
