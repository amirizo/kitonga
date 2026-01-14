# Tenant Portal - Next Available VPN IP API

## Overview

The **Portal Router Next VPN IP API** automatically suggests the next available WireGuard VPN IP address and provides complete configuration commands for tenants to set up their MikroTik routers. This eliminates manual IP allocation and reduces configuration errors.

---

## 🔗 API Endpoint

**URL:** `GET /api/portal/router/next-vpn-ip/`

**Authentication:** Tenant API Key (required)

**Purpose:** Get the next available WireGuard VPN IP and auto-generated MikroTik configuration

---

## 📋 Request

### Headers

```http
Authorization: Bearer YOUR_TENANT_API_KEY
Content-Type: application/json
```

### No Request Body Required

This is a GET request - no body needed!

### Example Request

```bash
curl -X GET "https://api.kitonga.klikcell.com/api/portal/router/next-vpn-ip/" \
  -H "Authorization: Bearer YOUR_TENANT_API_KEY"
```

---

## ✅ Success Response (200 OK)

```json
{
  "success": true,
  "next_available_ip": "10.100.0.30",
  "vpn_network": "10.100.0.0/24",
  "vps_vpn_ip": "10.100.0.1",
  "used_ips": [
    "10.100.0.10",
    "10.100.0.20"
  ],
  "total_available": 250,
  "wireguard_config": {
    "router_vpn_ip": "10.100.0.30",
    "vps_public_ip": "66.29.143.116",
    "vps_vpn_ip": "10.100.0.1",
    "wireguard_port": 51820,
    "server_public_key": "0ItNRIAXdf090Z3RpIVsmrA1JjRJrZveYweNZXXo3mQ=",
    "vpn_network": "10.100.0.0/24"
  },
  "mikrotik_commands": "# ============================================\n# WireGuard VPN Configuration for ABC Hotel\n# Router VPN IP: 10.100.0.30\n# ============================================\n\n# Step 1: Create WireGuard interface\n/interface wireguard add name=wg-kitonga listen-port=51820\n\n# Step 2: Add VPS as peer\n/interface wireguard peers add \\\n    interface=wg-kitonga \\\n    public-key=\"0ItNRIAXdf090Z3RpIVsmrA1JjRJrZveYweNZXXo3mQ=\" \\\n    endpoint-address=66.29.143.116 \\\n    endpoint-port=51820 \\\n    allowed-address=10.100.0.0/24 \\\n    persistent-keepalive=25\n\n# Step 3: Assign VPN IP address to your router\n/ip address add address=10.100.0.30/24 interface=wg-kitonga\n\n# Step 4: Allow Kitonga API access from VPN\n/ip firewall filter add \\\n    chain=input \\\n    src-address=10.100.0.0/24 \\\n    protocol=tcp \\\n    dst-port=8728 \\\n    action=accept \\\n    comment=\"Kitonga API Access\"\n\n# Step 5: Verify connection\n/ping 10.100.0.1 count=5\n\n# ============================================\n# After running these commands:\n# 1. Contact Kitonga support to add your router to VPS\n# 2. Provide them with your router's WireGuard public key\n# 3. Get the public key with: /interface wireguard print\n# ============================================",
  "setup_instructions": [
    "1. Copy the MikroTik commands above",
    "2. Connect to your MikroTik router via Winbox or SSH",
    "3. Paste and run all commands",
    "4. Get your router's WireGuard public key: /interface wireguard print",
    "5. Contact Kitonga support to add your public key to the VPS",
    "6. Once approved, add router in Kitonga portal using IP: 10.100.0.30"
  ],
  "important_notes": [
    "⚠️  Use 10.100.0.30 as the 'Host' when adding router in Kitonga portal",
    "⚠️  Your router must have internet access to reach VPS",
    "⚠️  Keep your WireGuard private key secure",
    "⚠️  Port 51820/UDP must be open on your router's firewall"
  ]
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether the operation succeeded |
| `next_available_ip` | string | Next free VPN IP to use for your router |
| `vpn_network` | string | WireGuard VPN network range |
| `vps_vpn_ip` | string | VPS server's VPN IP address |
| `used_ips` | array | List of IPs already allocated to other routers |
| `total_available` | integer | Number of remaining available IPs |
| `wireguard_config` | object | Complete WireGuard configuration details |
| `mikrotik_commands` | string | Ready-to-paste MikroTik commands |
| `setup_instructions` | array | Step-by-step setup guide |
| `important_notes` | array | Critical warnings and reminders |

---

## ❌ Error Responses

### No Available IPs (507)

```json
{
  "success": false,
  "error": "No available IP addresses in VPN range 10.100.0.0/24",
  "message": "All IPs are allocated. Please contact support."
}
```

**Cause:** All 253 usable IPs in the /24 network are allocated

### Internal Error (500)

```json
{
  "success": false,
  "error": "Error: [error details]"
}
```

**Cause:** Unexpected server error

---

## 💡 Use Cases

### 1. Router Setup Wizard - Step 1

Display next available IP before user configures router:

```javascript
async function startRouterSetup(apiKey) {
  // Step 1: Get next available VPN IP
  const response = await fetch('/api/portal/router/next-vpn-ip/', {
    headers: {
      'Authorization': `Bearer ${apiKey}`
    }
  });
  
  const data = await response.json();
  
  if (data.success) {
    // Display to user
    document.getElementById('vpn-ip').textContent = data.next_available_ip;
    document.getElementById('mikrotik-commands').textContent = data.mikrotik_commands;
    
    // Auto-fill the IP when they save router
    document.getElementById('router-host').value = data.next_available_ip;
    
    return data;
  } else {
    alert(data.message);
  }
}
```

### 2. React Component - Router Wizard

```jsx
import React, { useState, useEffect } from 'react';

function RouterSetupWizard({ apiKey }) {
  const [vpnConfig, setVpnConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    fetchNextVpnIp();
  }, []);
  
  const fetchNextVpnIp = async () => {
    try {
      const response = await fetch('/api/portal/router/next-vpn-ip/', {
        headers: {
          'Authorization': `Bearer ${apiKey}`
        }
      });
      
      const data = await response.json();
      
      if (data.success) {
        setVpnConfig(data);
      }
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const copyCommands = () => {
    navigator.clipboard.writeText(vpnConfig.mikrotik_commands);
    alert('MikroTik commands copied to clipboard!');
  };
  
  if (loading) return <div>Loading...</div>;
  
  if (!vpnConfig) return <div>Error loading VPN configuration</div>;
  
  return (
    <div className="router-wizard">
      <h2>Step 1: Configure WireGuard VPN</h2>
      
      <div className="vpn-info">
        <h3>Your Router's VPN IP: {vpnConfig.next_available_ip}</h3>
        <p>This IP will be used to connect your MikroTik router to Kitonga VPS</p>
      </div>
      
      <div className="stats">
        <p>Used IPs: {vpnConfig.used_ips.length}</p>
        <p>Available IPs: {vpnConfig.total_available}</p>
      </div>
      
      <div className="commands">
        <h4>MikroTik Commands</h4>
        <pre>{vpnConfig.mikrotik_commands}</pre>
        <button onClick={copyCommands}>
          📋 Copy Commands
        </button>
      </div>
      
      <div className="instructions">
        <h4>Setup Instructions</h4>
        <ol>
          {vpnConfig.setup_instructions.map((instruction, index) => (
            <li key={index}>{instruction}</li>
          ))}
        </ol>
      </div>
      
      <div className="warnings">
        <h4>Important Notes</h4>
        {vpnConfig.important_notes.map((note, index) => (
          <div key={index} className="warning-item">
            {note}
          </div>
        ))}
      </div>
      
      <button onClick={() => proceedToStep2(vpnConfig.next_available_ip)}>
        Next: Test Connection
      </button>
    </div>
  );
}
```

### 3. Auto-Fill Host Field

Automatically populate the router host field with VPN IP:

```javascript
async function prepareRouterForm(apiKey) {
  const vpnData = await fetch('/api/portal/router/next-vpn-ip/', {
    headers: { 'Authorization': `Bearer ${apiKey}` }
  }).then(res => res.json());
  
  if (vpnData.success) {
    // Auto-fill form
    document.getElementById('router-host').value = vpnData.next_available_ip;
    document.getElementById('router-host').readOnly = true; // Make it read-only
    
    // Add helper text
    document.getElementById('host-helper').textContent = 
      `Using WireGuard VPN IP. ${vpnData.total_available} IPs available.`;
  }
}
```

### 4. Show IP Availability Dashboard

Display VPN IP allocation status:

```javascript
async function showVpnStatus(apiKey) {
  const data = await fetch('/api/portal/router/next-vpn-ip/', {
    headers: { 'Authorization': `Bearer ${apiKey}` }
  }).then(res => res.json());
  
  if (data.success) {
    const totalIps = 253; // /24 network has 253 usable IPs (minus network, broadcast, VPS)
    const usedCount = data.used_ips.length;
    const availableCount = data.total_available;
    const usagePercent = ((usedCount / totalIps) * 100).toFixed(1);
    
    return {
      nextIp: data.next_available_ip,
      used: usedCount,
      available: availableCount,
      usagePercent: usagePercent,
      usedIps: data.used_ips
    };
  }
}
```

### 5. Validation Helper

Validate user-entered IP against available IPs:

```javascript
async function validateRouterIp(userIp, apiKey) {
  const data = await fetch('/api/portal/router/next-vpn-ip/', {
    headers: { 'Authorization': `Bearer ${apiKey}` }
  }).then(res => res.json());
  
  if (!data.success) return { valid: false, reason: 'Failed to check IP' };
  
  // Check if IP is in used list
  if (data.used_ips.includes(userIp)) {
    return {
      valid: false,
      reason: `IP ${userIp} is already used by another router`,
      suggestion: data.next_available_ip
    };
  }
  
  // Check if IP is in VPN range
  const [a, b, c, d] = userIp.split('.').map(Number);
  if (a !== 10 || b !== 100 || c !== 0) {
    return {
      valid: false,
      reason: 'IP must be in 10.100.0.0/24 range',
      suggestion: data.next_available_ip
    };
  }
  
  // Check if IP is reserved
  if (d === 0 || d === 1 || d === 255) {
    return {
      valid: false,
      reason: 'IP is reserved',
      suggestion: data.next_available_ip
    };
  }
  
  return { valid: true };
}
```

---

## 🔄 Complete Router Setup Flow

### Recommended Workflow

```javascript
class RouterSetupFlow {
  constructor(apiKey) {
    this.apiKey = apiKey;
    this.vpnConfig = null;
    this.routerId = null;
  }
  
  // Step 1: Get VPN IP and commands
  async step1_GetVpnConfig() {
    const response = await fetch('/api/portal/router/next-vpn-ip/', {
      headers: { 'Authorization': `Bearer ${this.apiKey}` }
    });
    
    this.vpnConfig = await response.json();
    
    if (this.vpnConfig.success) {
      console.log('✅ Next VPN IP:', this.vpnConfig.next_available_ip);
      console.log('📋 Copy these commands to MikroTik:');
      console.log(this.vpnConfig.mikrotik_commands);
      return this.vpnConfig;
    }
    
    throw new Error(this.vpnConfig.message);
  }
  
  // Step 2: Test connection
  async step2_TestConnection() {
    const response = await fetch('/api/portal/router/test/', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        host: this.vpnConfig.next_available_ip,
        port: 8728,
        username: 'admin',
        password: 'your-mikrotik-password'
      })
    });
    
    const data = await response.json();
    
    if (data.success && data.connection_successful) {
      console.log('✅ Connection successful!');
      return data;
    }
    
    throw new Error('Connection failed: ' + data.message);
  }
  
  // Step 3: Save router
  async step3_SaveRouter(name, password) {
    const response = await fetch('/api/portal/router/save/', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        name: name,
        host: this.vpnConfig.next_available_ip,
        port: 8728,
        username: 'admin',
        password: password
      })
    });
    
    const data = await response.json();
    
    if (data.success) {
      this.routerId = data.router.id;
      console.log('✅ Router saved! ID:', this.routerId);
      return data;
    }
    
    throw new Error('Failed to save: ' + data.message);
  }
  
  // Complete flow
  async setupRouter(routerName, mikrotikPassword) {
    try {
      console.log('🚀 Starting router setup...');
      
      // Step 1
      await this.step1_GetVpnConfig();
      console.log('👉 Please configure WireGuard on your MikroTik now');
      console.log('👉 Then press Enter to continue');
      await this.waitForUser();
      
      // Step 2
      await this.step2_TestConnection();
      
      // Step 3
      await this.step3_SaveRouter(routerName, mikrotikPassword);
      
      console.log('✅ Router setup complete!');
      console.log(`🎉 Your router is now connected at ${this.vpnConfig.next_available_ip}`);
      
      return {
        success: true,
        routerId: this.routerId,
        vpnIp: this.vpnConfig.next_available_ip
      };
    } catch (error) {
      console.error('❌ Setup failed:', error.message);
      return {
        success: false,
        error: error.message
      };
    }
  }
  
  waitForUser() {
    return new Promise(resolve => {
      // In browser: use confirm dialog
      // In Node: use readline
      if (confirm('Have you configured WireGuard on your MikroTik?')) {
        resolve();
      }
    });
  }
}

// Usage
const setup = new RouterSetupFlow('YOUR_API_KEY');
await setup.setupRouter('Hotel Main Router', 'mikrotik-password');
```

---

## 📊 IP Allocation Logic

### Reserved IPs

| IP | Purpose | Status |
|----|---------|--------|
| 10.100.0.0 | Network address | Reserved |
| 10.100.0.1 | VPS server | Reserved |
| 10.100.0.255 | Broadcast | Reserved |

### Usable Range

- **Start:** 10.100.0.2
- **End:** 10.100.0.254
- **Total Usable:** 253 IPs (excluding 0, 1, 255)

### Allocation Strategy

1. Scan all existing routers in database
2. Extract IPs from `Router.host` field
3. Filter only IPs in 10.100.0.0/24 range
4. Find first available IP starting from 10.100.0.2
5. Skip reserved IPs (0, 1, 255)

---

## 🎯 Benefits

✅ **Automatic IP Assignment** - No manual IP tracking needed  
✅ **Prevents Conflicts** - Checks all existing routers  
✅ **Ready-to-Use Commands** - Copy-paste MikroTik configuration  
✅ **Complete Documentation** - Step-by-step instructions included  
✅ **Error Prevention** - Validates IP range and availability  
✅ **Scalable** - Supports up to 253 routers per VPS

---

## 🔐 Security Notes

1. **VPN IP Visibility:** Only shows IPs allocated to any tenant (doesn't reveal which tenant)
2. **WireGuard Keys:** Private keys never exposed via API
3. **API Key Required:** Must authenticate to get IP
4. **Rate Limiting:** Consider implementing for this endpoint

---

## 🚀 Best Practices

### For Tenants

1. **Call this API first** before configuring MikroTik
2. **Save the VPN IP** - you'll need it when adding router
3. **Follow the instructions** in the exact order
4. **Test connection** before saving router
5. **Keep WireGuard private key** secure

### For Frontend Developers

1. **Auto-fill host field** with returned IP
2. **Show command box** with copy button
3. **Display instructions** clearly
4. **Add validation** for manual IP entry
5. **Show IP availability** stats

### For Platform Admins

1. **Monitor IP usage** - alert when >90% used
2. **Plan for expansion** if running low on IPs
3. **Verify WireGuard configs** on VPS match database
4. **Regular audits** of allocated vs actually connected routers

---

## 🎉 Summary

The Portal Router Next VPN IP API makes router setup **effortless**:

✅ **Automatic IP allocation** - No guesswork  
✅ **Ready-to-use commands** - Just copy & paste  
✅ **Complete instructions** - Step-by-step guide  
✅ **Conflict prevention** - Checks all existing IPs  
✅ **Perfect for tenants** - Self-service router setup

**Perfect workflow:**
1. Call API → Get VPN IP + commands
2. Configure MikroTik with provided commands
3. Test connection using the VPN IP
4. Save router with auto-filled IP

**Ready to deploy!** 🚀
