# Router Setup Guide

## OpenWRT with Nodogsplash

### Installation

1. **Install OpenWRT** on your router (if not already installed)

2. **Install Nodogsplash**:
\`\`\`bash
opkg update
opkg install nodogsplash
\`\`\`

### Configuration

Edit `/etc/nodogsplash/nodogsplash.conf`:

\`\`\`conf
# Gateway Interface
GatewayInterface br-lan

# Gateway Address
GatewayAddress 192.168.1.1

# Gateway Port
GatewayPort 2050

# Max Clients
MaxClients 250

# Client Idle Timeout (minutes)
ClientIdleTimeout 120

# Client Force Timeout (minutes)
ClientForceTimeout 1440

# Splash Page
SplashPage http://your-portal-url:3000

# Auth API
AuthAPI http://your-backend-url:8000/api/verify/

# Firewall Rules
FirewallRuleSet authenticated-users {
    FirewallRule allow all
}

FirewallRuleSet preauthenticated-users {
    FirewallRule allow tcp port 53
    FirewallRule allow udp port 53
    FirewallRule allow tcp port 80
    FirewallRule allow tcp port 443
}
\`\`\`

### Start Service

\`\`\`bash
/etc/init.d/nodogsplash enable
/etc/init.d/nodogsplash start
\`\`\`

## Alternative: CoovaChilli

### Installation

\`\`\`bash
opkg update
opkg install coova-chilli
\`\`\`

### Configuration

Edit `/etc/chilli/config`:

\`\`\`conf
HS_LANIF=br-lan
HS_NETWORK=192.168.182.0
HS_NETMASK=255.255.255.0
HS_UAMLISTEN=192.168.182.1
HS_UAMPORT=3990
HS_UAMUIPORT=4990
HS_UAMSERVER=http://your-portal-url:3000
HS_RADIUS=localhost
HS_RADIUS2=localhost
HS_RADSECRET=testing123
\`\`\`

## Raspberry Pi Hotspot

### Setup

1. **Install Required Packages**:
\`\`\`bash
sudo apt update
sudo apt install hostapd dnsmasq iptables-persistent
\`\`\`

2. **Configure hostapd** (`/etc/hostapd/hostapd.conf`):
\`\`\`conf
interface=wlan0
driver=nl80211
ssid=Kitonga-WiFi
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=YourPassword
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
\`\`\`

3. **Configure dnsmasq** (`/etc/dnsmasq.conf`):
\`\`\`conf
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
\`\`\`

4. **Setup IP Forwarding**:
\`\`\`bash
sudo sh -c "echo 1 > /proc/sys/net/ipv4/ip_forward"
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
sudo iptables-save | sudo tee /etc/iptables/rules.v4
\`\`\`

5. **Start Services**:
\`\`\`bash
sudo systemctl unmask hostapd
sudo systemctl enable hostapd
sudo systemctl start hostapd
sudo systemctl start dnsmasq
\`\`\`

## Testing

### Test Captive Portal Redirect

1. Connect to Wi-Fi
2. Open browser
3. Should redirect to payment portal

### Test Access Control

\`\`\`bash
# Test API endpoint
curl -X POST http://your-backend:8000/api/verify/ \
  -H "Content-Type: application/json" \
  -d '{"phone_number":"254712345678"}'
\`\`\`

## Troubleshooting

### Check Nodogsplash Status
\`\`\`bash
/etc/init.d/nodogsplash status
ndsctl status
\`\`\`

### View Logs
\`\`\`bash
logread | grep nodogsplash
\`\`\`

### Reset Nodogsplash
\`\`\`bash
/etc/init.d/nodogsplash restart
\`\`\`
