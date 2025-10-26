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
HS_UAMSERVER=https://kitonga.klikcell.com/
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
curl -X POST https://api.kitonga.klikcell.com/api/verify/ \
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
### Reset Nodogsplash
```bash
/etc/init.d/nodogsplash restart
```

## Mikrotik Router Integration

### Prerequisites
- Mikrotik router with RouterOS
- Access to Winbox or Web interface
- Your Kitonga backend running and accessible

### Step 1: Basic Hotspot Setup

1. **Access Mikrotik Interface**:
   - Use Winbox or web interface (192.168.88.1)
   - Login with admin credentials

2. **Create Hotspot via Quick Setup**:
   ```
   IP → Hotspot → Hotspot Setup
   ```
   - Select hotspot interface (usually bridge)
   - Set local address: `192.168.88.1/24`
   - Set DHCP pool: `192.168.88.100-192.168.88.200`
   - Select certificate: none
   - SMTP server: `0.0.0.0`
   - DNS servers: `8.8.8.8,8.8.4.4`
   - DNS name: `kitonga.local`
   - Username: `admin`
   - Password: `admin`

### Step 2: Configure External Authentication

1. **Create API Script for User Authentication**:
   ```routeros
   /system script add name=kitonga-auth source={
       :local phone "$"phone-number"
       :local mac "$"mac-address"
       :local ip "$"ip-address"
       
       :local url "http://YOUR_BACKEND_IP:8000/api/verify/"
       :local data "{"phone_number":"$phone","ip_address":"$ip","mac_address":"$mac"}"
       
       :local result [/tool fetch url=$url http-method=post http-data=$data http-header-field="Content-Type: application/json" as-value output=user]
       
       :if ($result->"status" = "finished") do={
           :local response $result->"data"
           :if ($response ~ "access_granted.*true") do={
               /ip hotspot active add user=$phone address=$ip mac-address=$mac
               :return "success"
           } else={
               :return "failed"
           }
       }
       :return "error"
   }
   ```

### Step 3: Customize Login Page

1. **Upload Custom Login Page**:
   - Go to `Files` in Winbox
   - Navigate to `hotspot` folder
   - Replace `login.html` with custom page:

   ```html
   <!DOCTYPE html>
   <html>
   <head>
       <title>Kitonga Wi-Fi</title>
       <meta charset="utf-8">
       <meta name="viewport" content="width=device-width, initial-scale=1.0">
       <script>
           // Redirect to your portal with Mikrotik parameters
           var params = new URLSearchParams(window.location.search);
           var redirectUrl = "http://YOUR_PORTAL_IP:3000?" + 
                           "link-login=" + encodeURIComponent("$(link-login)") +
                           "&link-orig=" + encodeURIComponent("$(link-orig)") +
                           "&mac=" + encodeURIComponent("$(mac)") +
                           "&ip=" + encodeURIComponent("$(ip)") +
                           "&username=" + encodeURIComponent("$(username)");
           
           window.location.href = redirectUrl;
       </script>
   </head>
   <body>
       <p>Redirecting to Kitonga Portal...</p>
   </body>
   </html>
   ```

### Step 4: Backend Integration Script

Create a script to handle Mikrotik login from your backend:

```python
# Add to your Django views.py
import requests
from urllib.parse import quote

def mikrotik_login_user(phone_number, mac_address, ip_address, mikrotik_ip="192.168.88.1"):
    """
    Authenticate user with Mikrotik hotspot
    """
    try:
        # Mikrotik login URL
        login_url = f"http://{mikrotik_ip}/login"
        
        # Prepare login data
        login_data = {
            'username': phone_number,
            'password': '',  # Can be empty for voucher-based auth
            'dst': '',
            'popup': 'true'
        }
        
        # Send login request to Mikrotik
        response = requests.post(login_url, data=login_data, timeout=10)
        
        if response.status_code == 200 and 'You are logged in' in response.text:
            logger.info(f'User {phone_number} logged into Mikrotik successfully')
            return True
        else:
            logger.error(f'Mikrotik login failed for {phone_number}')
            return False
            
    except Exception as e:
        logger.error(f'Error logging user into Mikrotik: {str(e)}')
        return False
```

### Step 5: Update Your Verify Access View

Update your `verify_access` view to integrate with Mikrotik:

```python
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_access(request):
    """
    Verify access and login user to Mikrotik
    """
    serializer = VerifyAccessSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    phone_number = serializer.validated_data['phone_number']
    ip_address = serializer.validated_data.get('ip_address', request.META.get('REMOTE_ADDR'))
    mac_address = serializer.validated_data.get('mac_address', '')
    
    try:
        user = User.objects.get(phone_number=phone_number)
        has_access = user.has_active_access()
        
        if has_access:
            # Login user to Mikrotik
            mikrotik_success = mikrotik_login_user(phone_number, mac_address, ip_address)
            
            if mikrotik_success:
                # Log successful access
                AccessLog.objects.create(
                    user=user,
                    ip_address=ip_address,
                    mac_address=mac_address,
                    access_granted=True
                )
                
                return Response({
                    'access_granted': True,
                    'mikrotik_login': True,
                    'user': UserSerializer(user).data
                })
            else:
                return Response({
                    'access_granted': True,
                    'mikrotik_login': False,
                    'message': 'Access granted but Mikrotik login failed',
                    'user': UserSerializer(user).data
                })
        else:
            return Response({
                'access_granted': False,
                'message': 'Access expired or not found'
            })
            
    except User.DoesNotExist:
        return Response({
            'access_granted': False,
            'message': 'User not found. Please register and pay to access Wi-Fi.'
        }, status=status.HTTP_404_NOT_FOUND)
```

### Step 6: Mikrotik API Integration (Advanced)

For more control, use Mikrotik's API:

```python
import socket
import hashlib

class MikrotikAPI:
    def __init__(self, host, username, password, port=8728):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.socket = None;
        
    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        
    def login(self):
        # Mikrotik API login implementation
        # This is a simplified version - use a proper Mikrotik API library
        pass;
        
    def add_hotspot_user(self, username, mac_address, ip_address):
        # Add active hotspot user
        command = f"/ip/hotspot/active/add"
        params = {
            "user": username,
            "address": ip_address,
            "mac-address": mac_address
        }
        # Send API command
        pass;
```

### Step 7: Frontend Integration

Update your frontend to handle Mikrotik parameters:

```javascript
// In your React/Next.js portal
const handlePaymentSuccess = async (paymentData) => {
    try {
        // Verify payment with backend
        const response = await fetch('/api/verify/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                phone_number: paymentData.phone_number,
                ip_address: getUrlParameter('ip'),
                mac_address: getUrlParameter('mac')
            })
        });
        
        const result = await response.json();
        
        if (result.access_granted && result.mikrotik_login) {
            // Success - user is now connected
            showSuccessMessage('Connected successfully!');
            
            // Optionally redirect to original URL
            const originalUrl = getUrlParameter('link-orig');
            if (originalUrl) {
                window.location.href = decodeURIComponent(originalUrl);
            }
        } else {
            showErrorMessage('Payment successful but connection failed');
        }
    } catch (error) {
        showErrorMessage('Connection error');
    }
};

function getUrlParameter(name) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(name);
}
```

### Step 8: Testing the Integration

1. **Test Hotspot Redirect**:
   ```bash
   # Connect device to Mikrotik Wi-Fi
   # Open browser - should redirect to your portal
   ```

2. **Test API Integration**:
   ```bash
   curl -X POST http://your-backend:8000/api/verify/ 
     -H "Content-Type: application/json" 
     -d '{
       "phone_number": "255712345678",
       "ip_address": "192.168.88.101",
       "mac_address": "AA:BB:CC:DD:EE:FF"
     }'
   ```

3. **Monitor Mikrotik Logs**:
   ```routeros
   /log print where topics~"hotspot"
   ```

### Troubleshooting

1. **Check Hotspot Active Users**:
   ```routeros
   /ip hotspot active print
   ```

2. **View Hotspot Logs**:
   ```routeros
   /log print where topics~"hotspot"
   ```

3. **Test API Connectivity**:
   ```routeros
   /tool fetch url="http://your-backend:8000/api/health/" check-certificate=no
   ```

4. **Debug Login Issues**:
   - Check if user appears in active list
   - Verify IP and MAC address matching
   - Test direct Mikrotik login form

### Security Considerations

1. **Use HTTPS**: Configure SSL certificates for production
2. **API Authentication**: Secure your backend API endpoints
3. **MAC Address Validation**: Validate MAC addresses to prevent spoofing
4. **Rate Limiting**: Implement rate limiting on authentication endpoints
5. **Firewall Rules**: Configure proper firewall rules for hotspot users

This integration allows your Kitonga backend to control Mikrotik hotspot access, enabling seamless user authentication and internet access control.
\`\`\`
