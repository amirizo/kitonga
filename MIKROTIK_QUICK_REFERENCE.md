# MikroTik Setup Quick Reference Card

## QUICK ACCESS INFO
- **Your Network**: 192.168.0.0/24 (Gateway: 192.168.0.1)
- **MikroTik Management IP**: 192.168.88.1
- **MikroTik WAN IP**: 192.168.0.x (auto-assigned)
- **Default Login**: admin / (no password)
- **New Admin Password**: Kijangwani2003.  
- **WiFi Network**: Kitonga WiFi
- **WiFi Password**: kitonga2025
- **WiFi Client IP Range**: 192.168.88.10-100
- **MikroTik MAC**: F4:1E:57:58:E9:9E

## ESSENTIAL COMMANDS

### First Time Access
```bash
# Physical setup (for your 192.168.0.x network)
1. Connect power cable to MikroTik
2. Connect ethernet from your router (192.168.0.1) to MikroTik port 1 (WAN)
3. Connect your computer to MikroTik port 2-5

# Access router (will create new network segment)
http://192.168.88.1
# Username: admin  
# Password: (empty)

# Network topology after setup:
# Your Router (192.168.0.1) → MikroTik WAN (192.168.0.x) → MikroTik LAN (192.168.88.1) → WiFi Clients
```

### Configuration Upload
```routeros
# SSH into router
ssh admin@192.168.88.1

# Upload and import config
/import file-name=mikrotik_kitonga_config.rsc

# Reboot
/system reboot
```

### HTML Files Upload (via Winbox)
```
1. Open Winbox → Connect to 192.168.88.1
2. Files menu → Navigate to 'hotspot' folder
3. Drag and drop:
   - login.html
   - status.html
   - error.html
   - logout.html
```

### Quick Status Check
```routeros
# System health
/system resource print

# WiFi status
/interface wireless print

# Hotspot users
/ip hotspot active print

# Internet test
/ping 8.8.8.8 count=3
```

### Common Troubleshooting
```routeros
# Reset WiFi interface
/interface wireless disable wlan1
/interface wireless enable wlan1

# Restart hotspot
/ip hotspot remove [find]
/import file-name=mikrotik_kitonga_config.rsc

# View logs
/log print where topics~"hotspot"
```

## EMERGENCY RESET
1. Hold reset button 10 seconds while powered
2. Wait 3 minutes for full boot
3. Access 192.168.88.1 with admin/(no password)
4. Re-upload mikrotik_kitonga_config.rsc

## TESTING CHECKLIST
- [ ] Router accessible at 192.168.88.1
- [ ] WiFi "Kitonga WiFi" visible
- [ ] Can connect with password "kitonga2025"
- [ ] Browser redirects to login page
- [ ] Login page accepts phone numbers
- [ ] Status page shows session info
- [ ] Django API responds to auth requests
- [ ] Internet access after authentication

## SUPPORT CONTACTS
- Django API: Check server logs
- Router Config: Check MIKROTIK_DJANGO_INTEGRATION.md
- Emergency: Factory reset and reconfigure
