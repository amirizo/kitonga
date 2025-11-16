# 🚀 Kitonga Wi-Fi Router Integration - Quick Setup

## Your VPS Configuration
- **VPS IP:** 66.29.143.116
- **Hostname:** server1.yum-express.com
- **Frontend:** https://kitonga.klikcell.com/
- **Backend API:** https://api.kitonga.klikcell.com/
- **OS:** Ubuntu 24.04
- **Resources:** 12GB RAM, 240GB Disk

## 🎯 Quick Setup (Since Your App is Already Deployed)

### Step 1: Update Environment Configuration

SSH to your VPS and edit your `.env` file:

```bash
# SSH to your VPS
ssh root@66.29.143.116

# Navigate to your project directory
cd /path/to/your/kitonga/project

# Edit .env file
nano .env
```

**Update these lines in your .env:**
```env
# Disable mock mode for full router control
MIKROTIK_MOCK_MODE=false

# Router connection (start with direct IP, then switch to VPN)
MIKROTIK_HOST=192.168.0.173
MIKROTIK_PORT=8728
MIKROTIK_USER=admin
MIKROTIK_PASSWORD=Kijangwani2003

# Your domains
ALLOWED_HOSTS=api.kitonga.klikcell.com,kitonga.klikcell.com,66.29.143.116,localhost
CORS_ALLOWED_ORIGINS=https://kitonga.klikcell.com,https://api.kitonga.klikcell.com
CSRF_TRUSTED_ORIGINS=https://kitonga.klikcell.com,https://api.kitonga.klikcell.com

# Ensure production mode
DEBUG=False
```

### Step 2: Install Router API Library

```bash
# Install/upgrade the router API library
pip install --upgrade routeros-api==0.21.0
```

### Step 3: Configure MikroTik Router

Connect to your MikroTik router at http://192.168.0.173 and run these commands:

```routeros
# Enable API for VPS access (IMPORTANT!)
/ip service
set api disabled=no

# Allow your VPS to access the router
/ip firewall filter
add action=accept chain=input protocol=tcp dst-port=8728 src-address=66.29.143.116 comment="VPS API Access"

# Configure external authentication
/ip hotspot user profile
set [find default=yes] login-by=cookie,http-chap

/ip hotspot user profile
set [find default=yes] \
  http-login-url="https://api.kitonga.klikcell.com/api/mikrotik/auth/" \
  http-logout-url="https://api.kitonga.klikcell.com/api/mikrotik/logout/"

# Configure DNS
/ip dns
set servers=8.8.8.8,1.1.1.1
set allow-remote-requests=yes
```

### Step 4: Test Connection

```bash
# Test basic connectivity
nc -zv 192.168.0.173 8728

# Test Django integration
python manage.py shell -c "
from billing.mikrotik import test_mikrotik_connection
result = test_mikrotik_connection()
print('Success:', result['success'])
print('Message:', result['message'])
"
```

### Step 5: Test API Endpoints

```bash
# Test router info endpoint
curl -X GET https://api.kitonga.klikcell.com/api/admin/mikrotik/router-info/ \
  -H "X-Admin-Access: kitonga_admin_2025"

# Should return router information instead of mock mode error
```

### Step 6: Restart Your Application

```bash
# Restart your Django application (adjust command based on your setup)
sudo systemctl restart gunicorn
# OR
sudo supervisorctl restart kitonga
# OR
pm2 restart all
```

## 🧪 Verify Everything Works

### Test 1: Check Mock Mode is Disabled
```bash
curl -X GET https://api.kitonga.klikcell.com/api/admin/mikrotik/router-info/ \
  -H "X-Admin-Access: kitonga_admin_2025"
```
**Expected:** Real router data, not "not accessible" message

### Test 2: Check Active Users
```bash
curl -X GET https://api.kitonga.klikcell.com/api/admin/mikrotik/active-users/ \
  -H "X-Admin-Access: kitonga_admin_2025"
```
**Expected:** List of active users (may be empty)

### Test 3: Test User Authentication
```bash
curl -X POST https://api.kitonga.klikcell.com/api/mikrotik/auth/ \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=255743852695&mac=AA:BB:CC:DD:EE:FF&ip=192.168.0.100"
```
**Expected:** Authentication response

## 🔒 Security Enhancement (Optional but Recommended)

For better security, set up WireGuard VPN:

### 1. Install WireGuard on VPS
```bash
sudo apt update
sudo apt install wireguard
```

### 2. Generate Keys
```bash
wg genkey | sudo tee /etc/wireguard/privatekey | wg pubkey | sudo tee /etc/wireguard/publickey
```

### 3. Configure Router for VPN
```routeros
# Create WireGuard interface
/interface wireguard
add listen-port=13231 mtu=1420 name=wg-to-vps

# Add VPS peer (replace with your VPS public key)
/interface wireguard peers
add allowed-address=10.10.0.2/32 interface=wg-to-vps public-key="YOUR_VPS_PUBLIC_KEY"

# Add VPN IP
/ip address
add address=10.10.0.1/24 interface=wg-to-vps

# Allow VPN traffic
/ip firewall filter
add action=accept chain=input dst-port=13231 protocol=udp comment="WireGuard VPS"
add action=accept chain=input src-address=10.10.0.0/24 comment="Allow VPS access"

# Restrict API to VPN only
/ip service
set api address=10.10.0.0/24
```

### 4. Update .env for VPN
```env
MIKROTIK_HOST=10.10.0.1  # VPN IP instead of direct IP
```

## 🎉 What You Get

✅ **Real-time monitoring** - See active users in admin dashboard  
✅ **Remote user management** - Disconnect users from anywhere  
✅ **Full router control** - All API features available  
✅ **Better security** - VPN-encrypted router access  
✅ **Professional operation** - Complete system control  

## 🆘 Troubleshooting

### Issue: Still getting "not accessible" errors
**Solution:**
1. Check `.env` has `MIKROTIK_MOCK_MODE=false`
2. Restart application
3. Verify router firewall allows VPS IP

### Issue: Connection refused
**Solution:**
1. Check router API is enabled: `/ip service print`
2. Verify firewall rules allow VPS access
3. Test with: `nc -zv 192.168.0.173 8728`

### Issue: Authentication failed
**Solution:**
1. Verify username/password in `.env`
2. Check router user exists and has API permissions
3. Test with WinBox using same credentials

## 📞 Quick Support Commands

```bash
# Check environment
grep MIKROTIK .env

# Test router connectivity
nc -zv 192.168.0.173 8728

# Check Django router settings
python manage.py shell -c "from django.conf import settings; print('Host:', settings.MIKROTIK_HOST); print('Mock Mode:', getattr(settings, 'MIKROTIK_MOCK_MODE', 'Not set'))"

# View application logs
tail -f /var/log/your-app/error.log
```

---

**🚀 Your system is now ready for full router control!**

No more mock mode - you can monitor and manage your router remotely from your admin dashboard at https://kitonga.klikcell.com/ 🎉
