# 🔧 MikroTik-Django Integration Guide

## Complete Setup Instructions for Fresh MikroTik Router

### STEP 0: Initial MikroTik Setup (Fresh Router)

#### A. Physical Connection (After Reset)
```bash
# CRITICAL: After reset, follow this exact order:

# 1. Power OFF the MikroTik router
# 2. Connect internet cable from your main router to MikroTik Port 1 (WAN)
# 3. Connect ethernet cable from your computer to MikroTik Port 2-5 (LAN)
# 4. Power ON the MikroTik router
# 5. Wait 2-3 minutes for full boot up

# Your network will be:
# Internet → Your Router (192.168.0.1) → MikroTik Port 1 → MikroTik (192.168.88.1) → Your Computer
```

#### B. Access Router (After Reset - Fresh Start)
```bash
# AFTER RESET - DEFAULT SETTINGS:
# Default IP: 192.168.88.1
# Username: admin
# Password: (empty/no password)

# Access via web browser
open http://192.168.88.1

# OR access via WebFig
open http://192.168.88.1/webfig/

# OR access via Winbox (recommended)
# Download from: https://mikrotik.com/download
# Connect to: 192.168.88.1 or scan for MAC: F4:1E:57:58:E9:9E

# AFTER CONFIGURATION: MikroTik will get IP from your main router
# - WAN IP: Will be assigned by your main router (192.168.0.x)
# - LAN IP: 192.168.88.1 (for WiFi clients)
# - WiFi Clients: 192.168.88.10-100
```

#### C. Initial Security Setup
```routeros
# 1. Set admin password (CRITICAL!)
/user set admin password=Kijangwani2003.

# 2. Set router identity
/system identity set name=Kitonga-WiFi-Router

# 3. Update RouterOS (recommended)
/system package update check-for-updates
/system package update download
# Wait for download, then:
/system reboot
```

#### D. Basic Internet Setup
Based on your current network (192.168.0.x), your MikroTik will create a separate hotspot network:

```routeros
# Your current network topology:
# Internet → Your Router (192.168.0.1) → Your Computer (192.168.0.173)
# We'll add: → MikroTik (192.168.0.x) → WiFi Clients (192.168.88.x)

# Configure WAN interface (ether1) to get IP from your existing router
/ip dhcp-client add interface=ether1 disabled=no

# This will make MikroTik get an IP like 192.168.0.x from your main router
# The MikroTik will then provide 192.168.88.x IPs to WiFi clients

# After configuration, check what IP MikroTik got:
/ip dhcp-client print

# Test internet connectivity
/ping 8.8.8.8 count=3
```

**Network Topology After Setup:**
```
Internet
    ↓
Your Main Router (192.168.0.1)
    ↓
Your Computer (192.168.0.173) + MikroTik WAN (192.168.0.x)
    ↓
MikroTik LAN/WiFi (192.168.88.1)
    ↓
WiFi Clients (192.168.88.10-100)
```

### STEP 1: Upload Complete Configuration

#### A. Prepare Configuration File
```bash
# Copy the configuration file to your MikroTik router
scp mikrotik_kitonga_config.rsc admin@192.168.0.173:/

# Alternative: Upload via Winbox
# 1. Open Winbox
# 2. Connect to 192.168.0.173
# 3. Go to Files
# 4. Drag and drop mikrotik_kitonga_config.rsc

# Alternative: Upload via WebFig (YOU CAN USE THIS!)
# 1. Go to http://192.168.0.173/webfig/#Files
# 2. Click "Choose File" and select mikrotik_kitonga_config.rsc
# 3. Click "Upload"
```

# SSH into your router and apply configuration
ssh admin@192.168.0.173
/import file-name=mikrotik_kitonga_config.rsc
```

#### B. Apply Configuration
```routeros
# SSH into router
ssh admin@192.168.0.173

# Import the configuration
/import file-name=mikrotik_kitonga_config.rsc

# OR via WebFig Terminal (EASIEST FOR YOU):
# 1. Go to http://192.168.0.173/webfig/#Terminal
# 2. Type: /import file-name=mikrotik_kitonga_config.rsc
# 3. Press Enter

# OR via Winbox Terminal:
# 1. Open Terminal in Winbox (connect to 192.168.0.173)
# 2. Type: /import file-name=mikrotik_kitonga_config.rsc
# 3. Press Enter

# Reboot router to apply all settings
/system reboot

# Wait 2-3 minutes for reboot
```

#### C. Verify Basic Configuration
```routeros
# After reboot, check key settings:

# 1. Check WiFi interface
/interface wireless print

# 2. Check hotspot
/ip hotspot print

# 3. Check bridge
/interface bridge print

# 4. Check IP addresses
/ip address print

# 5. Test internet connectivity
/ping 8.8.8.8 count=3
```

### STEP 2: Upload Custom HTML Files

#### A. Create Hotspot Directory
```routeros
# Connect via SSH or Winbox Terminal
# The hotspot directory should already exist, but verify:
/file print where name~"hotspot"

# If not exists, create it:
# (Usually not needed as it's created automatically)
```

#### B. Upload HTML Files
```bash
# Method 1: Via WebFig (EASIEST FOR YOU!)
# 1. Go to http://192.168.0.173/webfig/#Files
# 2. Navigate to 'hotspot' folder (double-click to enter)
# 3. For each HTML file:
#    - Click "Choose File"
#    - Select the file (login.html, status.html, error.html, logout.html)
#    - Click "Upload"

# Method 2: Via Winbox
# 1. Open Winbox and connect to 192.168.0.173
# 2. Go to Files menu
# 3. Navigate to 'hotspot' folder (double-click to enter)
# 4. Drag and drop these files:
#    - login.html
#    - status.html  
#    - error.html
#    - logout.html

# Method 3: Via FTP
ftp 192.168.0.173
# Username: admin
# Password: Kijangwani2003.
cd hotspot
put hotspot_html/login.html login.html
put hotspot_html/status.html status.html
put hotspot_html/error.html error.html
put hotspot_html/logout.html logout.html
quit

# Method 4: Via SCP
scp hotspot_html/*.html admin@192.168.0.173:/hotspot/
```

#### C. Verify HTML Files
```routeros
# Check uploaded files
/file print where name~"hotspot"

# You should see:
# hotspot/login.html
# hotspot/status.html
# hotspot/error.html
# hotspot/logout.html
```

### STEP 3: Configure External Authentication

#### A. Set Authentication URL
```routeros
# Configure hotspot profile for external authentication
/ip hotspot profile
set kitonga-hotspot-profile \
    html-directory=hotspot \
    login-by=http-chap,cookie \
    use-radius=no

# Verify the configuration
/ip hotspot profile print detail
```

#### B. Configure Service Ports
```routeros
# Ensure HTTP service is enabled for hotspot
/ip hotspot service-port
set www port=80 disabled=no

# Check services
/ip hotspot service-port print
```

#### C. Set Up External Authentication Script
```routeros
# Create a script for external authentication (Advanced)
# This is handled by the login.html page redirecting to Django API

# Verify hotspot is running
/ip hotspot print
/ip hotspot active print
```

### STEP 4: Test WiFi and Hotspot

#### A. Test WiFi Connection
```bash
# 1. On your phone/laptop, search for WiFi networks
# 2. Connect to "Kitonga WiFi"
# 3. Password: kitonga2025
# 4. You should get IP in range 192.168.88.10-192.168.88.100
```

#### B. Test Hotspot Login
```bash
# 1. After connecting to WiFi, open browser
# 2. Try to visit any website (e.g., google.com)
# 3. Should redirect to login page
# 4. Login page should show phone number input
# 5. Enter test phone number: 255700000000
```

#### C. Test Django Authentication
```bash
# Test the authentication endpoint manually
curl -X POST "https://api.kitonga.klikcell.com/api/mikrotik/auth/" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=255700000000&mac=aa:bb:cc:dd:ee:ff&ip=192.168.88.50"

# Should return HTTP 200 if user has bundle, 403 if not
```

### STEP 5: Configure External Authentication URL

#### A. Update Login Page (if needed)
The login.html page should redirect to:
```html
<!-- This is already configured in the provided login.html -->
<form name="login" action="$(link-login-only)" method="post">
```

#### B. Configure Authentication Handler
```routeros
# The authentication is handled by MikroTik calling your Django API
# When user submits login form, MikroTik will:
# 1. Get username from form
# 2. Call Django API: /api/mikrotik/auth/
# 3. Grant/deny access based on API response

# No additional configuration needed if using provided files
```

### STEP 6: Advanced Configuration

#### A. Bandwidth Management
```routeros
# Set bandwidth limits (optional)
/queue simple
add max-limit=10M/2M name=hotspot-users target=192.168.88.0/24

# Create per-user bandwidth profiles
/ip hotspot user profile
set kitonga-profile rate-limit=5M/1M
```

#### B. Custom Walled Garden
```routeros
# Add additional sites to walled garden if needed
/ip hotspot walled-garden
add dst-host=yourdomain.com comment="Additional site"

# View current walled garden
/ip hotspot walled-garden print
```

#### C. Advanced Logging
```routeros
# Enable detailed logging
/system logging
add topics=hotspot,!debug action=memory
add topics=wireless,!debug action=memory

# View logs
/log print where topics~"hotspot"
```

### STEP 7: Testing Complete Integration

#### A. Complete User Journey Test
```bash
# 1. Connect new device to "Kitonga WiFi"
# 2. Open browser → Should redirect to login page
# 3. Enter phone number with active bundle
# 4. Should get internet access
# 5. Check status page shows session info
# 6. Test logout functionality
```

#### B. Admin Testing
```bash
# 1. Create test user in Django admin
# 2. Give user active bundle
# 3. Test authentication with that user
# 4. Monitor logs in both Django and MikroTik
```

#### C. Payment Flow Testing
```bash
# 1. Create user without bundle
# 2. Try to authenticate → Should fail
# 3. User should be able to access payment page (walled garden)
# 4. After payment, authentication should work
```

### STEP 8: Production Readiness

#### A. Security Hardening
```routeros
# Change default passwords
/user set admin password=STRONG_PASSWORD_HERE

# Disable unnecessary services
/ip service disable telnet,ftp,www-ssl

# Enable only needed services
/ip service enable ssh,winbox,api,www

# Set up firewall rules (already configured in main config)
/ip firewall filter print
```

#### B. Backup Configuration
```routeros
# Create backup
/system backup save name=kitonga-production-backup

# Export configuration
/export file=kitonga-production-config

# Download backups
/file print where name~"backup"
```

#### C. Monitoring Setup
```routeros
# Enable SNMP for monitoring (optional)
/snmp set enabled=yes contact=admin@kitonga.klikcell.com

# Set up automatic backups
/system script add name=daily-backup source={
    /system backup save name=("backup-" . [/system clock get date])
}
/system scheduler add name=backup interval=1d on-event=daily-backup
```

## TROUBLESHOOTING GUIDE

### Common Issues and Solutions

#### 1. Can't Connect to Router (192.168.88.1)
**Problem**: Can't access router web interface or SSH
**Solutions**:
```bash
# Check network connection
ping 192.168.88.1

# Try default credentials:
# Username: admin
# Password: (empty) or "admin"

# If still can't connect, reset router:
# Hold reset button for 10 seconds while powered on
```

#### 2. WiFi Network Not Visible
**Problem**: "Kitonga WiFi" network not showing up
**Solutions**:
```routeros
# Check wireless interface status
/interface wireless print
/interface wireless monitor [find default-name~"wlan"]

# Enable wireless if disabled
/interface wireless enable wlan1

# Check security profile
/interface wireless security-profiles print
```

#### 3. Connected to WiFi but No Internet
**Problem**: Connected to WiFi but hotspot page not showing
**Solutions**:
```routeros
# Check hotspot status
/ip hotspot print
/ip hotspot active print

# Check bridge configuration
/interface bridge print
/interface bridge port print

# Test hotspot on router itself
/ip hotspot user add name=test profile=kitonga-profile
```

#### 4. Hotspot Login Page Not Showing
**Problem**: Browser doesn't redirect to login page
**Solutions**:
```routeros
# Check hotspot files
/file print where name~"hotspot"

# Verify hotspot profile
/ip hotspot profile print detail

# Check DNS configuration
/ip dns print

# Clear browser cache and try different device
```

#### 5. Django Authentication Not Working
**Problem**: Login page shows but authentication fails
**Solutions**:
```bash
# Test Django API endpoint
curl -v "https://api.kitonga.klikcell.com/api/mikrotik/auth/"

# Check Django logs
docker logs kitonga_web

# Verify CORS settings in Django
# Check that CORS_ALLOWED_ORIGINS includes router IP

# Test with direct API call
curl -X POST "https://api.kitonga.klikcell.com/api/mikrotik/auth/" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=255700000000&mac=aa:bb:cc:dd:ee:ff&ip=192.168.88.50"
```

#### 6. Users Can't Access Internet After Login
**Problem**: Authentication successful but still no internet
**Solutions**:
```routeros
# Check hotspot active users
/ip hotspot active print

# Check if user is in correct profile
/ip hotspot user print where name=PHONE_NUMBER

# Verify internet connectivity on router
/ping 8.8.8.8

# Check firewall rules
/ip firewall filter print where action=drop
```

#### 7. Slow Internet Speed
**Problem**: Internet speed slower than expected
**Solutions**:
```routeros
# Check bandwidth settings
/queue simple print
/ip hotspot user profile print

# Monitor CPU usage
/system resource print

# Check wireless signal strength
/interface wireless monitor wlan1
```

### Diagnostic Commands

#### Router Health Check
```routeros
# System status
/system resource print
/system clock print
/system routerboard print

# Network interfaces
/interface print stats
/ip address print
/ip route print

# Wireless status
/interface wireless print detail
/interface wireless monitor wlan1 once

# Hotspot status
/ip hotspot print detail
/ip hotspot active print detail
/ip hotspot host print
```

#### Log Analysis
```routeros
# View hotspot logs
/log print where topics~"hotspot"

# View system logs
/log print where topics~"system"

# View wireless logs
/log print where topics~"wireless"

# Clear logs
/log print where topics~"debug"
```

#### Performance Monitoring
```routeros
# CPU and memory usage
/system resource monitor duration=10

# Interface statistics
/interface monitor-traffic bridge1 duration=10

# Wireless monitoring
/interface wireless monitor wlan1 duration=10
```

### Emergency Recovery

#### Factory Reset Recovery
If you need to completely start over:

```bash
# 1. Physical reset
# Hold reset button for 10+ seconds while router is powered on

# 2. Wait for router to fully boot (2-3 minutes)

# 3. Connect via ethernet cable to port 2-5

# 4. Access router at 192.168.88.1

# 5. Follow STEP 1 (Complete Initial Setup) again
```

#### Configuration Backup Recovery
If you have backup files:

```routeros
# Upload backup file via Winbox Files menu
# Then restore:
/system backup load name=kitonga-production-backup

# OR restore from exported config:
/import file-name=kitonga-production-config.rsc
```

## MAINTENANCE SCHEDULE

### Daily Tasks
- Monitor active hotspot users: `/ip hotspot active print`
- Check system resources: `/system resource print`
- Review logs for errors: `/log print where topics~"error"`

### Weekly Tasks
- Create configuration backup: `/system backup save name=weekly-backup`
- Update user profiles if needed
- Check bandwidth usage statistics
- Review Django authentication logs

### Monthly Tasks
- Update router firmware if available
- Review and rotate backup files
- Analyze user behavior and optimize settings
- Security audit and password changes

### Emergency Contacts
- Django API Issues: Check Django server logs
- Router Issues: MikroTik support documentation
- Network Issues: Check internet provider status
- Payment Issues: ClickPesa support

## ADDITIONAL RESOURCES

### Useful Commands Reference
```routeros
# Quick status check
/system resource print; /ip hotspot active print; /interface wireless print

# User management
/ip hotspot user add name=PHONE profile=kitonga-profile
/ip hotspot user remove [find name=PHONE]
/ip hotspot user print where profile=kitonga-profile

# Bandwidth monitoring
/tool bandwidth-test address=8.8.8.8 protocol=tcp
/queue simple print stats

# Network troubleshooting
/ping 8.8.8.8 count=5
/tool traceroute address=8.8.8.8
/ip route print where active
```

### Configuration Files Summary
- `mikrotik_kitonga_config.rsc`: Complete router configuration
- `hotspot_html/login.html`: Custom login page
- `hotspot_html/status.html`: User session status page  
- `hotspot_html/error.html`: Error handling page
- `hotspot_html/logout.html`: Logout confirmation page
- `setup_mikrotik.sh`: Automated setup script

This completes your MikroTik router setup and Django integration. Your WiFi billing system is now production-ready!

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
