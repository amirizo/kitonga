# WireGuard VPN Router Setup Guide

This guide explains how to connect tenant MikroTik routers to the Kitonga VPS using WireGuard VPN.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        KITONGA VPS                               │
│                    66.29.143.116                                 │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │   Django     │    │  WireGuard   │    │   MySQL      │       │
│  │   API        │◄──►│   VPN        │    │   Database   │       │
│  │   :8000      │    │   :51820     │    │   :3306      │       │
│  └──────────────┘    └──────┬───────┘    └──────────────┘       │
│                             │                                    │
│                      VPN: 10.100.0.1                             │
└─────────────────────────────┼────────────────────────────────────┘
                              │
                    WireGuard VPN Tunnel
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  Tenant A     │   │  Tenant B     │   │  Tenant C     │
│  MikroTik     │   │  MikroTik     │   │  MikroTik     │
│  10.100.0.10  │   │  10.100.0.20  │   │  10.100.0.30  │
│  (Hotel ABC)  │   │  (Cafe XYZ)   │   │  (Guest House)│
└───────────────┘   └───────────────┘   └───────────────┘
```

## VPS WireGuard Server Info

| Setting               | Value                                          |
| --------------------- | ---------------------------------------------- |
| **VPS Public IP**     | 66.29.143.116                                  |
| **WireGuard Port**    | 51820/UDP                                      |
| **Server Public Key** | `0ItNRIAXdf090Z3RpIVsmrA1JjRJrZveYweNZXXo3mQ=` |
| **VPN Network**       | 10.100.0.0/24                                  |
| **VPS VPN IP**        | 10.100.0.1                                     |

## Adding a New Tenant Router

### Step 1: Generate Router Configuration on VPS

SSH to the VPS and run:

```bash
ssh root@66.29.143.116
add-tenant-router <tenant_name> <last_ip_octet>
```

Example:

```bash
add-tenant-router hotel_paradise 10
# This assigns IP 10.100.0.10 to the router
```

Kitonga WiFi 2

This will output MikroTik commands and save config to `/etc/wireguard/tenants/<tenant_name>.conf`

### Step 2: Configure MikroTik Router

Connect to the MikroTik router via Winbox or SSH and run the commands provided:

```routeros
# Create WireGuard interface
/interface wireguard add name=wg-kitonga listen-port=51820 private-key="<ROUTER_PRIVATE_KEY>"

# Add VPS as peer
/interface wireguard peers add \
    interface=wg-kitonga \
    public-key="0ItNRIAXdf090Z3RpIVsmrA1JjRJrZveYweNZXXo3mQ=" \
    endpoint-address=66.29.143.116 \
    endpoint-port=51820 \
    allowed-address=10.100.0.0/24 \
    persistent-keepalive=25

# Assign VPN IP address
/ip address add address=10.100.0.X/24 interface=wg-kitonga

# Allow API access from VPN
/ip firewall filter add chain=input src-address=10.100.0.0/24 protocol=tcp dst-port=8728 action=accept comment="Kitonga API Access"
```

### Step 3: Verify Connection

On the VPS:

```bash
# Check WireGuard status
wg show

# Ping the router
ping 10.100.0.10
```

On the MikroTik:

```routeros
/ping 10.100.0.1
```

### Step 4: Register Router in Django Admin

1. Go to https://api.kitonga.klikcell.com/admin/
2. Navigate to **Billing → Routers**
3. Add new router:
   - **Name**: Hotel Paradise Router
   - **Tenant**: Select the tenant
   - **Host**: `10.100.0.10` (WireGuard IP)
   - **Port**: `8728`
   - **Username**: MikroTik API user
   - **Password**: MikroTik API password
   - **Hotspot Name**: `hotspot1`

## IP Address Allocation

| Tenant       | Router Name    | WireGuard IP |
| ------------ | -------------- | ------------ |
| VPS Server   | -              | 10.100.0.1   |
| Kitonga WiFi | Kitonga WiFi   | 10.100.0.10  |
| Kitonga WiFi | Kitonga Remote | 10.100.0.40  |
| Tenant 2     | -              | 10.100.0.20  |
| DULA-WIFI    | DULLA WIFI     | 10.100.0.30  |
| ...          | ...            | ...          |

## MikroTik API User Setup

On each MikroTik router, create an API user:

```routeros
# Create API group with necessary permissions
/user group add name=api-group policy=api,read,write,policy,test

# Create API user
/user add name=kitonga-api password=SecurePassword123 group=api-group

# Enable API service (if not enabled)
/ip service enable api

# Optional: Restrict API to VPN only
/ip service set api address=10.100.0.0/24
```

## Troubleshooting

### Router Not Connecting

1. **Check firewall**: Ensure UDP port 51820 is open on both ends
2. **Check keys**: Verify public/private key pairs match
3. **Check endpoint**: Ensure router can reach 66.29.143.116:51820

```routeros
# On MikroTik - check WireGuard status
/interface wireguard print
/interface wireguard peers print

# Check for handshake
/interface wireguard peers print detail
```

### API Connection Failed

1. **Check API service**:

```routeros
/ip service print where name=api
```

2. **Check firewall allows API**:

```routeros
/ip firewall filter print where dst-port=8728
```

3. **Test from VPS**:

```bash
nc -zv 10.100.0.10 8728
```

### VPN Latency Issues

Add these settings to MikroTik for better performance:

```routeros
/interface wireguard set wg-kitonga mtu=1420
```

## SSL/TLS with Certbot (Let's Encrypt)

### Domain Configuration

| Domain                     | Purpose           |
| -------------------------- | ----------------- |
| `api.kitonga.klikcell.com` | Main API endpoint |
| `kitonga.klikcell.com`     | Admin dashboard   |

### Install Certbot (if not installed)

```bash
apt update
apt install certbot python3-certbot-nginx -y
```

### Generate SSL Certificate

```bash
# For Nginx
certbot --nginx -d api.kitonga.klikcell.com -d kitonga.klikcell.com

# Or standalone (if Nginx not running)
certbot certonly --standalone -d api.kitonga.klikcell.com -d kitonga.klikcell.com
```

### Auto-Renewal Setup

```bash
# Test renewal
certbot renew --dry-run

# Cron job (usually auto-added)
echo "0 0,12 * * * root certbot renew --quiet" >> /etc/crontab
```

### Nginx SSL Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name api.kitonga.klikcell.com;

    ssl_certificate /etc/letsencrypt/live/api.kitonga.klikcell.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.kitonga.klikcell.com/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name api.kitonga.klikcell.com kitonga.klikcell.com;
    return 301 https://$server_name$request_uri;
}
```

### Check Certificate Status

```bash
# View certificate details
certbot certificates

# Check expiry date
openssl x509 -enddate -noout -in /etc/letsencrypt/live/api.kitonga.klikcell.com/fullchain.pem
```

## Walled Garden Configuration

The Walled Garden allows unauthenticated hotspot users to access specific domains (like payment gateways and the login API) before they log in.

### Required Walled Garden Entries

These domains must be accessible for Kitonga to work properly:

| Domain                     | Purpose                                |
| -------------------------- | -------------------------------------- |
| `api.kitonga.klikcell.com` | Kitonga API (login, payments, bundles) |
| `kitonga.klikcell.com`     | Admin dashboard                        |
| `*.clickpesa.com`          | ClickPesa payment gateway              |
| `*.tigopesa.com`           | Tigo Pesa payments                     |
| `*.mpesa.com`              | M-Pesa payments                        |
| `*.vodacom.co.tz`          | Vodacom M-Pesa                         |
| `*.airtel.com`             | Airtel Money                           |
| `*.halopesa.com`           | Halo Pesa payments                     |

### MikroTik Walled Garden Setup

Run these commands on each MikroTik router:

```routeros
# Add Kitonga API domain
/ip hotspot walled-garden add dst-host="api.kitonga.klikcell.com" action=allow comment="Kitonga API"
/ip hotspot walled-garden add dst-host="kitonga.klikcell.com" action=allow comment="Kitonga Dashboard"

# Add ClickPesa payment gateway
/ip hotspot walled-garden add dst-host="*.clickpesa.com" action=allow comment="ClickPesa Gateway"
/ip hotspot walled-garden add dst-host="clickpesa.com" action=allow comment="ClickPesa"

# Add Mobile Money payment gateways
/ip hotspot walled-garden add dst-host="*.tigopesa.com" action=allow comment="Tigo Pesa"
/ip hotspot walled-garden add dst-host="*.vodacom.co.tz" action=allow comment="Vodacom M-Pesa"
/ip hotspot walled-garden add dst-host="*.mpesa.com" action=allow comment="M-Pesa"
/ip hotspot walled-garden add dst-host="*.airtel.com" action=allow comment="Airtel Money"
/ip hotspot walled-garden add dst-host="*.halopesa.com" action=allow comment="Halo Pesa"

# Add IP-based walled garden for VPS (backup)
/ip hotspot walled-garden ip add dst-address=66.29.143.116 action=accept comment="Kitonga VPS IP"
```

### Verify Walled Garden Configuration

```routeros
# View all walled garden entries
/ip hotspot walled-garden print

# View IP-based walled garden entries
/ip hotspot walled-garden ip print

# Test if domain is in walled garden (from router terminal)
/ip hotspot walled-garden print where dst-host~"kitonga"
```

### Troubleshooting Walled Garden

If users can't access the login page or payment gateway:

1. **Check entries exist**:

```routeros
/ip hotspot walled-garden print
```

2. **Check DNS resolution**:

```routeros
/ip dns print
:put [:resolve "api.kitonga.klikcell.com"]
```

3. **Add by IP if DNS fails**:

```routeros
# Get the IP and add it
/ip hotspot walled-garden ip add dst-address=66.29.143.116 action=accept
```

4. **Check hotspot profile has walled garden enabled**:

```routeros
/ip hotspot profile print
```

### Complete Walled Garden Script

Copy and paste this complete script to set up all walled garden entries at once:

```routeros
# Remove old entries (optional - be careful!)
# /ip hotspot walled-garden remove [find]

# Kitonga domains
/ip hotspot walled-garden add dst-host="api.kitonga.klikcell.com" action=allow comment="Kitonga API"
/ip hotspot walled-garden add dst-host="kitonga.klikcell.com" action=allow comment="Kitonga Dashboard"
/ip hotspot walled-garden add dst-host="*.klikcell.com" action=allow comment="Klikcell All"

# Payment gateways
/ip hotspot walled-garden add dst-host="*.clickpesa.com" action=allow comment="ClickPesa"
/ip hotspot walled-garden add dst-host="clickpesa.com" action=allow comment="ClickPesa Root"
/ip hotspot walled-garden add dst-host="*.tigopesa.com" action=allow comment="Tigo Pesa"
/ip hotspot walled-garden add dst-host="*.vodacom.co.tz" action=allow comment="M-Pesa Vodacom"
/ip hotspot walled-garden add dst-host="*.mpesa.com" action=allow comment="M-Pesa"
/ip hotspot walled-garden add dst-host="*.airtel.com" action=allow comment="Airtel Money"
/ip hotspot walled-garden add dst-host="*.halopesa.com" action=allow comment="Halo Pesa"

# VPS IP (backup)
/ip hotspot walled-garden ip add dst-address=66.29.143.116 action=accept comment="Kitonga VPS"

# Verify
/ip hotspot walled-garden print
```

## Security Best Practices

1. **Use unique API passwords** for each router
2. **Restrict API to VPN network** (`/ip service set api address=10.100.0.0/24`)
3. **Enable API-SSL** for encrypted API connections
4. **Regular key rotation** - regenerate WireGuard keys annually
5. **Monitor connections** - check for unauthorized peers
6. **Keep SSL certificates valid** - ensure auto-renewal is working

## Quick Reference Commands

### VPS Commands

```bash
# Show all connected routers
wg show

# Add new tenant router
add-tenant-router <name> <ip_octet>

# View tenant config
cat /etc/wireguard/tenants/<name>.conf

# Restart WireGuard
systemctl restart wg-quick@wg0

# View WireGuard logs
journalctl -u wg-quick@wg0 -f
```

### MikroTik Commands

```routeros
# Check WireGuard status
/interface wireguard print
/interface wireguard peers print

# Ping VPS
/ping 10.100.0.1

# Check handshake time
/interface wireguard peers print detail where interface=wg-kitonga
```
