# 🚀 VPS MikroTik Integration - Quick Reference

## 📋 Setup Checklist

### ✅ Prerequisites
- [ ] VPS with root access
- [ ] MikroTik router (hAP lite or similar)
- [ ] Home internet with public IP
- [ ] Domain name (optional but recommended)

### ✅ Initial Setup
1. [ ] **Run automated setup:** `./setup_vps_mikrotik.sh`
2. [ ] **Configure WireGuard VPN** between VPS and router
3. [ ] **Test connectivity:** `python test_vps_integration.py`
4. [ ] **Deploy Django application**
5. [ ] **Configure MikroTik external auth**

## 🔧 Key Configuration Files

| File | Purpose | Location |
|------|---------|----------|
| `.env` | Environment variables | Project root |
| `wg0.conf` | WireGuard VPN config | `/etc/wireguard/` |
| `mikrotik_commands.rsc` | Router configuration | Project directory |

## 🌐 Network Configuration

### VPN Setup (Recommended)
```
VPS IP: 10.10.0.2/24
Router IP: 10.10.0.1/24
VPN Port: 13231/udp
```

### Important Ports
- **8728** - MikroTik API
- **13231** - WireGuard VPN
- **80/443** - HTTP/HTTPS
- **22** - SSH

## ⚙️ Environment Variables

### Critical Settings
```env
# Disable mock mode for VPS
MIKROTIK_MOCK_MODE=false

# Router connection (via VPN)
MIKROTIK_HOST=10.10.0.1
MIKROTIK_PORT=8728
MIKROTIK_USER=admin
MIKROTIK_PASSWORD=your_router_password

# Production settings
DEBUG=False
ALLOWED_HOSTS=your-domain.com,your-vps-ip
```

## 🧪 Testing Commands

### Quick Tests
```bash
# Test VPN connectivity
ping 10.10.0.1

# Test API port
nc -zv 10.10.0.1 8728

# Test Django integration
python test_vps_integration.py

# Test API endpoints
curl -X GET https://your-domain.com/api/admin/mikrotik/router-info/ \
  -H "X-Admin-Access: kitonga_admin_2025"
```

## 🔄 Service Management

### WireGuard VPN
```bash
# Start VPN
sudo systemctl start wg-quick@wg0

# Enable auto-start
sudo systemctl enable wg-quick@wg0

# Check status
sudo wg show
```

### Django Application
```bash
# Restart with systemd
sudo systemctl restart gunicorn

# Restart with Docker
docker-compose restart

# Check logs
journalctl -u gunicorn -f
```

## 🎯 Router Configuration (MikroTik)

### External Authentication Setup
```routeros
# Configure hotspot profile
/ip hotspot user profile
set [find default=yes] \
  login-by=cookie,http-chap \
  http-login-url="https://your-domain.com/api/mikrotik/auth/" \
  http-logout-url="https://your-domain.com/api/mikrotik/logout/"

# Enable API for VPS
/ip service
set api disabled=no
set api address=10.10.0.0/24
```

### Security Rules
```routeros
# Allow VPN traffic
/ip firewall filter
add action=accept chain=input dst-port=13231 protocol=udp comment="WireGuard VPS"
add action=accept chain=input src-address=10.10.0.0/24 comment="Allow VPS access"

# Secure API access
add action=drop chain=input protocol=tcp dst-port=8728 src-address=!10.10.0.0/24 comment="Block external API"
```

## 🆘 Troubleshooting

### Common Issues

#### 1. Connection Refused
**Problem:** `[Errno 111] Connection refused`
**Solutions:**
- Check VPN: `ping 10.10.0.1`
- Test API port: `nc -zv 10.10.0.1 8728`
- Restart WireGuard: `sudo systemctl restart wg-quick@wg0`

#### 2. Authentication Failed
**Problem:** Router API authentication errors
**Solutions:**
- Verify password in `.env`
- Check router user exists: `/user print`
- Test with WinBox using same credentials

#### 3. External Auth Not Working
**Problem:** Users not redirected properly
**Solutions:**
- Check hotspot profile URLs
- Verify DNS settings: `/ip dns print`
- Test URLs manually in browser

#### 4. Mock Mode Still Active
**Problem:** Getting "not accessible" messages
**Solutions:**
- Check `.env`: `MIKROTIK_MOCK_MODE=false`
- Restart application
- Run: `python test_vps_integration.py`

## 📞 Quick Support Commands

```bash
# Check environment
cat .env | grep MIKROTIK

# Test connectivity
python -c "
import socket
s = socket.socket()
s.settimeout(5)
try:
    s.connect(('10.10.0.1', 8728))
    print('✅ Router reachable')
except:
    print('❌ Router not reachable')
s.close()
"

# Check VPN status
sudo wg show wg0

# Check service status
sudo systemctl status wg-quick@wg0
sudo systemctl status gunicorn
```

## 🎉 Success Indicators

### ✅ Everything Working
- [ ] `test_vps_integration.py` passes all tests
- [ ] Can ping router: `ping 10.10.0.1`
- [ ] API endpoints return router data
- [ ] Admin dashboard shows active users
- [ ] Can disconnect users remotely
- [ ] External auth redirects users properly

### 🎯 Ready for Production
- [ ] SSL certificate installed
- [ ] DNS pointing to VPS
- [ ] Backups configured
- [ ] Monitoring enabled
- [ ] Router config backed up

## 📚 Documentation Links

- 📖 **Complete Guide:** VPS_MIKROTIK_SETUP_GUIDE.md
- 🔧 **Setup Script:** setup_vps_mikrotik.sh
- 🔄 **Migration:** transition_to_vps.sh
- 🧪 **Testing:** test_vps_integration.py

---

**🚀 With VPS, you have complete control of your Kitonga Wi-Fi system!**

No more mock mode limitations - enjoy full router management capabilities!
