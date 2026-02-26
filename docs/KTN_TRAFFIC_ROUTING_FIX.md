# KTN Traffic Routing Fix - Route Through MikroTik

> **STATUS: IMPLEMENTED AND VERIFIED** (Live on VPS + MikroTik)

## The Problem (FIXED)

Previously, KTN user traffic took a shortcut and bypassed MikroTik:

```
BEFORE (WRONG):
  User Phone -> VPS wg0 -> MASQUERADE on eth0 -> Internet directly
                         X MikroTik BYPASSED - no traffic control
```

## The Solution (LIVE)

All KTN client traffic now routes through MikroTik:

```
AFTER (CORRECT):
  User Phone (10.200.0.x)
       |
  Encrypted Tunnel (UDP 51820)
       |
  VPS wg0 (10.100.0.1)
       |
  Policy-Based Routing (table ktn)
       |
  Forward to MikroTik via site-to-site tunnel (wg0 -> wg0)
       |
  MikroTik (10.100.0.40)
       |  <-- Bandwidth control, QoS, user tracking, tenant policies
       |
  NAT Masquerade on WAN (ether1)
       |
  Internet
```

## What Was Changed

### 1. VPS - Policy-Based Routing (PBR)

**File:** `/etc/iproute2/rt_tables`
```
100 ktn
```

**Applied rules:**
```bash
# Traffic FROM KTN clients uses custom routing table
ip rule add from 10.200.0.0/24 table ktn priority 100

# KTN table routes everything to MikroTik
ip route replace default via 10.100.0.40 dev wg0 table 100
```

This means:
- Normal VPS traffic -> default route -> eth0 -> internet (unchanged)
- Traffic FROM KTN clients (10.200.0.x) -> ktn table -> MikroTik -> internet

### 2. VPS - WireGuard Config (`/etc/wireguard/wg0.conf`)

```ini
[Interface]
Address = 10.100.0.1/24
ListenPort = 51820
PrivateKey = <key>

PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -A FORWARD -i wg0 -o wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE; ip route replace default via 10.100.0.40 dev wg0 table 100 2>/dev/null || true; ip rule add from 10.200.0.0/24 table 100 priority 100 2>/dev/null || true

PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -D FORWARD -i wg0 -o wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE; ip rule del from 10.200.0.0/24 table 100 2>/dev/null || true; ip route del default via 10.100.0.40 dev wg0 table 100 2>/dev/null || true

# MikroTik peer - AllowedIPs includes client subnet for return traffic
[Peer]
PublicKey = uvxzOAmz/kdzrDJckj+Wk9C4O0K0O2QPp3XRso+ZLnw=
AllowedIPs = 10.100.0.40/32, 10.200.0.0/24
Endpoint = <mikrotik-endpoint>
PersistentKeepalive = 25
```

### 3. VPS - UFW Forwarding Rule

```bash
ufw route allow in on wg0 out on wg0
```

This allows wg0->wg0 forwarding through UFW (client traffic arriving on wg0 forwarded out wg0 to MikroTik).

### 4. MikroTik - VPS Peer AllowedIPs

Updated the VPS WireGuard peer on MikroTik to include `10.200.0.0/24`:

```routeros
/interface wireguard peers set [find public-key="0ItNRIAXdf090Z3RpIVsmrA1JjRJrZveYweNZXXo3mQ="] allowed-address=10.100.0.1/32,10.200.0.0/24
```

This tells MikroTik's WireGuard to send return traffic for KTN clients back through the tunnel to VPS.

### 5. MikroTik - Already Had (Pre-existing)

These were already configured on MikroTik:
- Route: `10.200.0.0/24 via wg-kitonga`
- Firewall: `forward src=10.200.0.0/24 action=accept`
- Firewall: `forward dst=10.200.0.0/24 action=accept`
- NAT: `srcnat src=10.200.0.0/24 action=masquerade`

## Summary of All Changes

| Where | What | Why |
|-------|------|-----|
| VPS `/etc/iproute2/rt_tables` | Added `100 ktn` | Custom routing table for KTN |
| VPS `ip rule` | `from 10.200.0.0/24 table ktn prio 100` | PBR: client traffic uses ktn table |
| VPS `ip route table 100` | `default via 10.100.0.40 dev wg0` | KTN traffic goes to MikroTik |
| VPS `wg0.conf` PostUp | PBR rules + wg0->wg0 forward | Persist across restarts |
| VPS UFW | `route allow in on wg0 out on wg0` | Allow wg0->wg0 forwarding |
| VPS WG peer | MikroTik AllowedIPs += `10.200.0.0/24` | Accept return traffic |
| MikroTik WG peer | VPS AllowedIPs = `10.100.0.1/32,10.200.0.0/24` | Route return traffic to VPS |

## Traffic Flow (Working)

```
1. User phone sends:     src=10.200.0.2  dst=8.8.8.8
2. Encrypted -> VPS wg0
3. VPS PBR matches:      from 10.200.0.0/24 -> table ktn
4. Table ktn:            default via 10.100.0.40 dev wg0
5. VPS forwards:         wg0 -> wg0 (to MikroTik)
6. MikroTik receives:    src=10.200.0.2  dst=8.8.8.8 on wg-kitonga
7. MikroTik masquerades: src=<WAN IP>    dst=8.8.8.8
8. Internet replies:     src=8.8.8.8     dst=<WAN IP>
9. MikroTik un-NATs:     src=8.8.8.8     dst=10.200.0.2
10. MikroTik routes:     10.200.0.0/24 via wg-kitonga -> VPS
11. VPS receives:        on wg0, forwards to user's peer on wg0
12. User gets internet!
```

## Verification Commands

```bash
# On VPS - Check PBR
ip rule list | grep ktn
ip route show table 100

# On VPS - Check route lookup for client traffic
ip route get 8.8.8.8 from 10.200.0.2 iif wg0
# Should show: via 10.100.0.40 dev wg0 table ktn

# On VPS - Check UFW forwarding counters
iptables -L ufw-user-forward -n -v
# wg0->wg0 rule should show increasing packet count

# On VPS - Check WireGuard
wg show wg0
# MikroTik peer should have active handshake + AllowedIPs includes 10.200.0.0/24
```

## Benefits

- MikroTik sees every KTN user connection
- Tenant can control bandwidth per KTN plan
- Usage tracking works (bytes in/out per user)
- Portal `/portal/vpn/users/` shows real live status
- MikroTik firewall/QoS rules apply to KTN users
- Same billing infrastructure for hotspot AND KTN users
