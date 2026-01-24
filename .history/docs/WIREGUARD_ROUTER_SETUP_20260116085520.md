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

| Tenant     | Router Name | WireGuard IP |
| ---------- | ----------- | ------------ |
| VPS Server | -           | 10.100.0.1   |
| Tenant 1   | -           | 10.100.0.10  |
| Tenant 2   | -           | 10.100.0.20  |
| Tenant 3   | -           | 10.100.0.30  |
| ...        | ...         | ...          |

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

## Security Best Practices

1. **Use unique API passwords** for each router
2. **Restrict API to VPN network** (`/ip service set api address=10.100.0.0/24`)
3. **Enable API-SSL** for encrypted API connections
4. **Regular key rotation** - regenerate WireGuard keys annually
5. **Monitor connections** - check for unauthorized peers

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
