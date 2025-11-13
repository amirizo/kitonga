# Production MikroTik Connection Setup Guide

## Problem
Your production server at `https://api.kitonga.klikcell.com` cannot connect to your MikroTik router because:
- **Error:** `[Errno 111] Connection refused`
- **Cause:** Production server trying to connect to `192.168.0.173:8728` (private IP)
- **Local works:** Local dev server can reach the router on the same network

## Understanding the Issue

```
[Your Local Network]                    [Internet]                [Production Server]
192.168.0.0/24                                                    api.kitonga.klikcell.com
├── Your Computer (Dev)                                           
│   └── Can reach router ✅                                       ❌ Cannot reach router
├── MikroTik Router                                               (Private IP not routable)
    └── 192.168.0.173:8728
```

## Solution Options

### Option 1: VPN Tunnel (Most Secure) ⭐ RECOMMENDED

#### Step 1: Set up WireGuard VPN on MikroTik
```bash
# On MikroTik RouterOS 7.x
/interface wireguard add name=wg-server listen-port=13231
/interface wireguard peers add interface=wg-server public-key="<production-server-public-key>" allowed-address=10.0.0.2/32

# Assign IP to WireGuard interface
/ip address add address=10.0.0.1/24 interface=wg-server
```

#### Step 2: Install WireGuard on Production Server
```bash
# On production server
sudo apt update
sudo apt install wireguard

# Generate keys
wg genkey | tee privatekey | wg pubkey > publickey

# Configure WireGuard
sudo nano /etc/wireguard/wg0.conf
```

**wg0.conf:**
```ini
[Interface]
PrivateKey = <production-server-private-key>
Address = 10.0.0.2/24

[Peer]
PublicKey = <mikrotik-public-key>
Endpoint = <your-home-public-ip>:13231
AllowedIPs = 10.0.0.0/24, 192.168.0.0/24
PersistentKeepalive = 25
```

#### Step 3: Update Production Environment Variables
```bash
# In production .env
MIKROTIK_HOST=192.168.0.173  # Can now reach via VPN
MIKROTIK_PORT=8728
MIKROTIK_USER=admin
MIKROTIK_PASSWORD=Kijangwani2003
MIKROTIK_USE_SSL=false
```

---

### Option 2: Public IP + Port Forwarding (Less Secure) ⚠️

#### Step 1: Get Your Public IP
```bash
curl ifconfig.me
# Example output: 203.0.113.45
```

#### Step 2: Configure MikroTik Port Forwarding
```bash
# On MikroTik
/ip firewall nat add chain=dstnat dst-port=8728 protocol=tcp action=dst-nat to-addresses=192.168.0.173 to-ports=8728

# Add firewall rule to allow API access
/ip firewall filter add chain=input protocol=tcp dst-port=8728 action=accept comment="MikroTik API"
```

#### Step 3: Update Production Environment
```bash
# In production .env
MIKROTIK_HOST=203.0.113.45  # Your public IP
MIKROTIK_PORT=8728
MIKROTIK_USER=admin
MIKROTIK_PASSWORD=Kijangwani2003
MIKROTIK_USE_SSL=false
```

⚠️ **Security Warning:** This exposes your router API to the internet. Use strong passwords and consider:
- Changing default API port
- Enabling SSL/TLS
- IP whitelisting production server

---

### Option 3: Local Proxy Service (Most Complex)

#### Step 1: Create Local MikroTik Proxy Service
Run a small API service on your local network that:
1. Connects to MikroTik locally
2. Exposes REST API over HTTPS
3. Tunnels to production via ngrok or similar

#### Step 2: Use ngrok or CloudFlare Tunnel
```bash
# Install ngrok
ngrok http 8080

# Or CloudFlare Tunnel
cloudflared tunnel --url http://localhost:8080
```

#### Step 3: Update Production to Use Proxy
Instead of connecting directly to MikroTik, production calls your proxy API.

---

### Option 4: Mock/Disable in Production (Development Only) 🚫

**NOT for production use**, but for testing:

```python
# In billing/mikrotik.py at the top
import os

# Add check for production environment
MIKROTIK_MOCK_MODE = os.getenv('MIKROTIK_MOCK_MODE', 'false').lower() == 'true'

def get_mikrotik_api():
    if MIKROTIK_MOCK_MODE:
        raise ImportError('MikroTik mock mode - router not available in this environment')
    # ... rest of existing code
```

Then in production `.env`:
```bash
MIKROTIK_MOCK_MODE=true
```

This will return graceful errors instead of connection refused.

---

## Recommended Implementation Steps

### For Production Deployment:

1. **Short Term (Quick Fix):**
   - Use Option 4 (Mock Mode) to make errors graceful
   - Display "Router features unavailable" in frontend
   - Log warnings instead of errors

2. **Medium Term (Proper Solution):**
   - Set up VPN (Option 1) for secure access
   - Update production environment variables
   - Test connection from production

3. **Long Term (Best Practice):**
   - Consider moving router to same network as production server
   - Or use cloud-managed networking (VPC, etc.)
   - Implement proper monitoring

### Quick Fix Code Changes

Add this to `billing/mikrotik.py`:

```python
# At the top after imports
import os

PRODUCTION_ENV = os.getenv('ENVIRONMENT', 'development').lower() == 'production'
MIKROTIK_MOCK_MODE = os.getenv('MIKROTIK_MOCK_MODE', 'false').lower() == 'true'

def get_mikrotik_api():
    """
    Return an authenticated RouterOS API connection using env-driven settings.
    """
    if MIKROTIK_MOCK_MODE:
        raise ImportError('MikroTik is not accessible in this environment')
    
    if routeros_api is None:
        raise ImportError('routeros-api is not installed. Add it to requirements.txt')

    # ... rest of existing code
```

Update your production `.env`:
```bash
ENVIRONMENT=production
MIKROTIK_MOCK_MODE=true  # Set to false once VPN is configured
```

---

## Testing Connection

### Test from Production Server:

```bash
# SSH into production server
ssh user@api.kitonga.klikcell.com

# Test router connectivity
nc -zv 192.168.0.173 8728
# If connection refused: Router not reachable
# If connection successful: Connection OK

# Test with Python
python3 << 'EOF'
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
result = s.connect_ex(('192.168.0.173', 8728))
print(f"Connection result: {result}")  # 0 = success, other = failed
print(f"Status: {'Connected' if result == 0 else 'Connection refused'}")
s.close()
EOF
```

### Test API Endpoint:

```bash
# From anywhere
curl -X GET https://api.kitonga.klikcell.com/api/admin/mikrotik/test-connection/ \
  -H "X-Admin-Access: kitonga_admin_2025" \
  -H "Content-Type: application/json"
```

---

## Security Best Practices

1. **Use Strong Passwords:**
   ```bash
   # Change default MikroTik password
   /user set admin password=<strong-random-password>
   ```

2. **Enable API SSL:**
   ```bash
   /ip service set api-ssl disabled=no port=8729
   ```

3. **IP Whitelisting:**
   ```bash
   # Only allow production server IP
   /ip firewall filter add chain=input src-address=<production-ip> \
     protocol=tcp dst-port=8728 action=accept
   
   /ip firewall filter add chain=input protocol=tcp dst-port=8728 \
     action=drop comment="Block unauthorized API access"
   ```

4. **Use Certificate Authentication:**
   - Generate SSL certificates
   - Configure mutual TLS authentication

---

## Troubleshooting

### Connection Refused
- **Check:** Is router reachable from production server?
- **Fix:** Set up VPN or port forwarding

### Timeout
- **Check:** Firewall blocking connection?
- **Fix:** Add firewall rules to allow traffic

### Authentication Failed
- **Check:** Correct credentials in production `.env`?
- **Fix:** Update environment variables

### SSL Certificate Errors
- **Check:** SSL enabled but certificate invalid?
- **Fix:** Disable SSL or install proper certificate

---

## Contact & Support

If you need help setting up VPN or port forwarding:
1. Check your internet service provider's documentation
2. Review MikroTik's official VPN setup guide
3. Consider hiring a network administrator for secure setup

**Important:** Never expose your router API directly to the internet without proper security measures!
