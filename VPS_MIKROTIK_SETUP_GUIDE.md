# VPS MikroTik Integration Setup Guide

## 🎯 VPS Advantages

**Welcome to full control!** 🚀  
Since you've moved to VPS, you can now:

✅ **Full router control** - Connect directly to your MikroTik router  
✅ **Real-time management** - Monitor active users from your admin dashboard  
✅ **Remote operations** - Disconnect users, view statistics, manage profiles  
✅ **Secure VPN connectivity** - Establish encrypted tunnel to your home router  
✅ **No mock mode needed** - Use real router operations  

---

## 🔧 Step 1: Remove Mock Mode

First, let's disable the mock mode that was required for shared hosting:

```bash
# Edit your .env file on VPS
nano .env

# Remove or comment out this line:
# MIKROTIK_MOCK_MODE=true

# Or set it to false:
MIKROTIK_MOCK_MODE=false
```

---

## 🌐 Step 2: Network Connectivity Options

### Option A: WireGuard VPN (Recommended)

**Most secure and reliable method**

#### 2.1. Configure WireGuard on MikroTik Router

Connect to your MikroTik router (http://192.168.0.173 or WinBox):

```routeros
# Create WireGuard interface
/interface wireguard
add listen-port=13231 mtu=1420 name=wg-to-vps

# Generate WireGuard keys (note down the public key)
/interface wireguard peers
add allowed-address=10.10.0.2/32 interface=wg-to-vps public-key="<VPS_PUBLIC_KEY>"

# Add IP address to WireGuard interface
/ip address
add address=10.10.0.1/24 interface=wg-to-vps

# Configure firewall
/ip firewall filter
add action=accept chain=input dst-port=13231 protocol=udp comment="WireGuard VPS"
add action=accept chain=input src-address=10.10.0.0/24 comment="Allow VPS access"
```

#### 2.2. Configure WireGuard on VPS

```bash
# Install WireGuard on your VPS
sudo apt update
sudo apt install wireguard

# Generate keys
wg genkey | tee /etc/wireguard/privatekey | wg pubkey > /etc/wireguard/publickey

# Create config file
sudo nano /etc/wireguard/wg0.conf
```

**WireGuard Config (`/etc/wireguard/wg0.conf`):**
```ini
[Interface]
PrivateKey = <YOUR_VPS_PRIVATE_KEY>
Address = 10.10.0.2/24

[Peer]
PublicKey = <MIKROTIK_PUBLIC_KEY>
Endpoint = <YOUR_HOME_PUBLIC_IP>:13231
AllowedIPs = 10.10.0.0/24, 192.168.0.0/24
PersistentKeepalive = 25
```

#### 2.3. Start WireGuard

```bash
# Enable and start WireGuard
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0

# Check status
sudo wg show

# Test connectivity
ping 10.10.0.1
ping 192.168.0.173
```

### Option B: Port Forwarding (Less Secure)

If VPN is not available, you can use port forwarding:

#### 2.1. Configure Router Port Forwarding

In your MikroTik router:

```routeros
# Allow API access from VPS
/ip firewall filter
add action=accept chain=input protocol=tcp dst-port=8728 src-address=<VPS_PUBLIC_IP> comment="VPS API Access"

# Optional: NAT forwarding if behind another router
/ip firewall nat
add action=dst-nat chain=dstnat dst-port=8728 protocol=tcp to-addresses=192.168.0.173 to-ports=8728
```

#### 2.2. Update Environment Variables

```bash
# In your VPS .env file
MIKROTIK_HOST=<YOUR_HOME_PUBLIC_IP>  # Your public IP
MIKROTIK_PORT=8728
```

---

## ⚙️ Step 3: Update VPS Environment Configuration

Create or update your `.env` file on VPS:

```env
# Django Configuration
SECRET_KEY=your-production-secret-key
DEBUG=False
ALLOWED_HOSTS=api.kitonga.klikcell.com,kitonga.klikcell.com,66.29.143.116,localhost

# MikroTik Router Configuration
MIKROTIK_HOST=10.10.0.1  # Router VPN IP (or use 192.168.0.173 for direct connection)
MIKROTIK_PORT=8728
MIKROTIK_USER=admin
MIKROTIK_PASSWORD=Kijangwani2003
MIKROTIK_USE_SSL=False
MIKROTIK_DEFAULT_PROFILE=default
MIKROTIK_MOCK_MODE=false

# IMPORTANT: Remove mock mode entirely or set to false
# This enables full router control on VPS

# Payment & SMS (keep your existing values)
CLICKPESA_CLIENT_ID=your_client_id
CLICKPESA_API_KEY=your_api_key
NEXTSMS_USERNAME=your_username
NEXTSMS_PASSWORD=your_password

# Admin token for frontend
SIMPLE_ADMIN_TOKEN=kitonga_admin_2025

# VPS-specific settings
CORS_ALLOWED_ORIGINS=https://kitonga.klikcell.com,https://api.kitonga.klikcell.com
CSRF_TRUSTED_ORIGINS=https://kitonga.klikcell.com,https://api.kitonga.klikcell.com
```

---

## 🔗 Step 4: Test Router Connectivity

### 4.1. Test Basic Connectivity

```bash
# Test ping (if WireGuard is configured)
ping 192.168.0.173

# Test API port
nc -zv 192.168.0.173 8728

# Test HTTP (if enabled)
curl -I http://192.168.0.173/
```

### 4.2. Test Django Integration

```bash
# Navigate to your project directory
cd /path/to/your/project

# Run connectivity test
python manage.py shell -c "
from billing.mikrotik import test_mikrotik_connection
result = test_mikrotik_connection()
print('Success:', result['success'])
print('Message:', result['message'])
if 'router_info' in result:
    print('Router Info:', result['router_info'])
"
```

### 4.3. Test API Endpoints

```bash
# Test router connection endpoint
curl -X POST https://api.kitonga.klikcell.com/api/admin/mikrotik/test-connection/ \
  -H "X-Admin-Access: kitonga_admin_2025" \
  -H "Content-Type: application/json"

# Expected: {"success": true, "message": "Connection successful", ...}

# Test active users
curl -X GET https://api.kitonga.klikcell.com/api/admin/mikrotik/active-users/ \
  -H "X-Admin-Access: kitonga_admin_2025"

# Expected: {"success": true, "active_users": [...]}
```

---

## 🚀 Step 5: Deploy and Restart Application

### 5.1. Install Dependencies

```bash
# Install updated requirements
pip install -r requirements.txt

# Specifically ensure routeros-api is installed
pip install routeros-api==0.21.0
```

### 5.2. Restart Application

```bash
# If using systemd
sudo systemctl restart gunicorn
sudo systemctl restart nginx

# If using Docker
docker-compose restart

# If using supervisor
sudo supervisorctl restart kitonga

# If using PM2
pm2 restart all
```

### 5.3. Check Logs

```bash
# Check application logs
tail -f /var/log/your-app/error.log

# Check nginx logs
tail -f /var/log/nginx/error.log

# Check systemd logs
journalctl -u gunicorn -f
```

---

## 🧪 Step 6: Comprehensive Testing

### 6.1. Test Router Management Features

```bash
# Test 1: Router Info
curl -X GET https://api.kitonga.klikcell.com/api/admin/mikrotik/router-info/ \
  -H "X-Admin-Access: kitonga_admin_2025"

# Test 2: Active Users
curl -X GET https://api.kitonga.klikcell.com/api/admin/mikrotik/active-users/ \
  -H "X-Admin-Access: kitonga_admin_2025"

# Test 3: Hotspot Profiles
curl -X GET https://api.kitonga.klikcell.com/api/admin/mikrotik/profiles/ \
  -H "X-Admin-Access: kitonga_admin_2025"
```

### 6.2. Test User Authentication Flow

```bash
# Test user auth (simulates router request)
curl -X POST https://api.kitonga.klikcell.com/api/mikrotik/auth/ \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=255743852695&mac=AA:BB:CC:DD:EE:FF&ip=192.168.0.100"

# Expected: Success response with access granted
```

### 6.3. Test Payment Integration

```bash
# Test a complete payment flow
curl -X POST https://api.kitonga.klikcell.com/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}'

# Test bundle purchase (requires valid user token)
```

---

## 🎯 Step 7: Configure MikroTik Router for External Auth

### 7.1. Hotspot Configuration

In MikroTik WebFig or WinBox:

1. **Go to IP > Hotspot > Server Profiles**
2. **Edit your hotspot profile:**
   - Login By: cookie, http-chap
   - HTTP Login: `https://api.kitonga.klikcell.com/api/mikrotik/auth/`
   - HTTP Logout: `https://api.kitonga.klikcell.com/api/mikrotik/logout/`

### 7.2. Router Script Commands

```routeros
# Configure hotspot server profile
/ip hotspot user profile
set [find default=yes] login-by=cookie,http-chap

# Configure authentication URLs
/ip hotspot user profile
set [find default=yes] \
  http-login-url="https://api.kitonga.klikcell.com/api/mikrotik/auth/" \
  http-logout-url="https://api.kitonga.klikcell.com/api/mikrotik/logout/"

# Configure DNS (important for external auth)
/ip dns
set servers=8.8.8.8,1.1.1.1
set allow-remote-requests=yes
```

---

## 🔒 Step 8: Security Hardening

### 8.1. MikroTik Security

```routeros
# Secure API access
/ip service
set api disabled=no
set api-ssl disabled=yes
set api address=10.10.0.0/24  # Only allow VPS access

# Secure SSH
/ip service
set ssh port=2222
set ssh address=10.10.0.0/24

# Firewall rules
/ip firewall filter
add action=drop chain=input protocol=tcp dst-port=8728 src-address=!10.10.0.0/24 comment="Block external API access"
```

### 8.2. VPS Security

```bash
# Configure UFW firewall
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow 13231/udp  # WireGuard

# Secure API access (if needed)
sudo ufw allow from 192.168.0.0/24 to any port 8728
```

---

## 📊 Step 9: Monitoring and Logging

### 9.1. Set Up Log Monitoring

```bash
# Create log monitoring script
cat > /usr/local/bin/check-mikrotik.sh << 'EOF'
#!/bin/bash
# Check MikroTik connectivity

if ping -c 1 192.168.0.173 > /dev/null 2>&1; then
    echo "$(date): MikroTik router is reachable" >> /var/log/mikrotik-monitor.log
else
    echo "$(date): MikroTik router is unreachable!" >> /var/log/mikrotik-monitor.log
fi
EOF

chmod +x /usr/local/bin/check-mikrotik.sh

# Add to crontab
echo "*/5 * * * * /usr/local/bin/check-mikrotik.sh" | crontab -
```

### 9.2. Django Logging Configuration

Add to your `settings.py`:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'mikrotik_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/var/log/your-app/mikrotik.log',
        },
    },
    'loggers': {
        'billing.mikrotik': {
            'handlers': ['mikrotik_file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

---

## 🎉 Step 10: Verification Checklist

### ✅ Pre-Deployment Checklist

- [ ] VPN or port forwarding configured
- [ ] Router connectivity tested from VPS
- [ ] MIKROTIK_MOCK_MODE removed or set to false
- [ ] Environment variables updated
- [ ] Dependencies installed
- [ ] Application restarted

### ✅ Post-Deployment Testing

- [ ] Router connection API works
- [ ] Active users endpoint returns data
- [ ] User authentication flow works
- [ ] Router commands execute successfully
- [ ] Frontend admin dashboard shows router status

### ✅ End-to-End Testing

- [ ] User connects to WiFi
- [ ] External authentication redirects to payment
- [ ] Payment completes and grants access
- [ ] User browses internet successfully
- [ ] Admin can see active users
- [ ] Admin can disconnect users remotely

---

## 🆘 Troubleshooting

### Common Issues and Solutions

#### 1. Connection Refused Error

**Symptoms:** `[Errno 111] Connection refused`

**Solutions:**
- Check VPN connectivity: `ping 192.168.0.173`
- Verify API port: `nc -zv 192.168.0.173 8728`
- Check router API service: `/ip service print`
- Verify firewall rules allow VPS access

#### 2. Authentication Failed

**Symptoms:** RouterOS API authentication errors

**Solutions:**
- Verify username/password in `.env`
- Check router user permissions
- Test with WinBox using same credentials
- Ensure API user has necessary permissions

#### 3. External Auth Not Working

**Symptoms:** Users not redirected to payment page

**Solutions:**
- Check hotspot profile configuration
- Verify DNS settings on router
- Test URLs manually
- Check SSL certificate validity

#### 4. WireGuard Connection Issues

**Symptoms:** VPN tunnel not establishing

**Solutions:**
- Check firewall allows UDP 13231
- Verify public keys are correctly exchanged
- Check endpoint IP and port
- Restart WireGuard: `sudo systemctl restart wg-quick@wg0`

---

## 📈 Performance Optimization

### Router Performance

```routeros
# Optimize hotspot performance
/ip hotspot user profile
set [find default=yes] address-pool=dhcp_pool1 keepalive-timeout=2m

# Enable firewall connection tracking
/ip firewall connection
print
```

### Django Performance

```python
# Add to settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}

# Cache router data
from django.core.cache import cache

def get_cached_active_users():
    cache_key = 'mikrotik_active_users'
    users = cache.get(cache_key)
    if users is None:
        users = get_active_hotspot_users()
        cache.set(cache_key, users, 60)  # Cache for 1 minute
    return users
```

---

## 🔄 Backup and Recovery

### 1. MikroTik Backup

```routeros
# Create backup
/system backup save name=kitonga-backup

# Export configuration
/export file=kitonga-config

# Schedule automatic backups
/system scheduler
add interval=1d name=daily-backup on-event="/system backup save name=(\"backup-\" . [/system clock get date])" start-time=03:00:00
```

### 2. Database Backup

```bash
# Create backup script
cat > /usr/local/bin/backup-db.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
python manage.py dumpdata > /backups/kitonga_backup_$DATE.json
find /backups -name "kitonga_backup_*.json" -mtime +7 -delete
EOF

chmod +x /usr/local/bin/backup-db.sh
echo "0 2 * * * /usr/local/bin/backup-db.sh" | crontab -
```

---

## 🎯 Next Steps

1. **Monitor System Performance**
   - Set up monitoring alerts
   - Track user connection patterns
   - Monitor router resource usage

2. **Optimize User Experience**
   - Customize captive portal design
   - Implement user feedback system
   - Add bandwidth management

3. **Scale Infrastructure**
   - Consider load balancing for high traffic
   - Implement database replication
   - Add redundant internet connections

4. **Business Intelligence**
   - Implement usage analytics
   - Generate revenue reports
   - Track customer satisfaction metrics

---

## 📞 Support

If you encounter any issues:

1. Check logs: `/var/log/your-app/`
2. Test connectivity: `python manage.py shell`
3. Review this guide step by step
4. Check MikroTik forums for router-specific issues

**Your system is now ready for full production use with complete router control!** 🚀

---

## Summary

✅ **VPS gives you complete control**  
✅ **No more mock mode limitations**  
✅ **Real-time router management**  
✅ **Secure VPN connectivity**  
✅ **Full feature set available**  

Your customers will have the same great experience, but now you can:
- Monitor who's online in real-time
- Disconnect users remotely
- View detailed router statistics
- Manage hotspot profiles
- Troubleshoot issues remotely

Welcome to the full power of your Kitonga Wi-Fi system! 🎉
