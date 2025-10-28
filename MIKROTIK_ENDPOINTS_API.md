# 🌐 MikroTik Integration Endpoints - API Documentation

## 📋 Overview

The MikroTik integration endpoints provide seamless communication between your Django backend and MikroTik RouterOS hotspot system. These endpoints handle user authentication, logout, status monitoring, and user management for the Wi-Fi billing system.

**Base URL**: `http://your-domain.com/api/`  
**Authentication**: Admin endpoints require `X-Admin-Access` token

---

## 🔐 1. MikroTik Authentication

### **Endpoint**: `POST/GET /mikrotik/auth/`

**Purpose**: External authentication endpoint called by MikroTik router for hotspot user validation.

**Method**: `POST` or `GET`  
**Permission**: `AllowAny` (Called by MikroTik router)  
**Content-Type**: `application/x-www-form-urlencoded` or `application/json`

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `username` | string | ✅ | User's phone number (used as username) |
| `password` | string | ❌ | User password (optional) |
| `mac` | string | ❌ | Device MAC address |
| `ip` | string | ❌ | User's IP address |

### Frontend Integration

```javascript
// ✅ MikroTik Authentication (Usually called by router, not frontend)
async function mikrotikAuth(username, password, macAddress, ipAddress) {
    const response = await fetch('/api/mikrotik/auth/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            username: username,
            password: password || '',
            mac: macAddress || '',
            ip: ipAddress || ''
        })
    });
    
    if (response.ok) {
        console.log('✅ Authentication successful');
        return true;
    } else {
        const error = await response.text();
        console.log('❌ Authentication failed:', error);
        return false;
    }
}

// Example usage (for testing)
mikrotikAuth('+255700123456', '', 'AA:BB:CC:DD:EE:FF', '192.168.88.10');
```

### Response Codes

| Status | Response | Description |
|--------|----------|-------------|
| `200` | `"OK"` | Authentication successful |
| `403` | `"No username provided"` | Missing username |
| `403` | `"Payment required"` | User has no active subscription |
| `403` | `"Device limit exceeded"` | User reached max device limit |
| `403` | `"User not found"` | User doesn't exist |
| `500` | `"Authentication error"` | Server error |

### Business Logic

1. ✅ Validates user exists by phone number
2. ✅ Checks if user has active paid subscription
3. ✅ Manages device registration and limits
4. ✅ Logs access attempts
5. ✅ Returns appropriate HTTP status for MikroTik

---

## 🚪 2. MikroTik Logout

### **Endpoint**: `POST/GET /mikrotik/logout/`

**Purpose**: Handles user logout from MikroTik hotspot system.

**Method**: `POST` or `GET`  
**Permission**: `AllowAny` (Called by MikroTik router)

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `username` | string | ✅ | User's phone number |
| `ip` | string | ❌ | User's IP address |

### Frontend Integration

```javascript
// ✅ MikroTik Logout
async function mikrotikLogout(username, ipAddress) {
    const response = await fetch('/api/mikrotik/logout/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            username: username,
            ip: ipAddress || ''
        })
    });
    
    if (response.ok) {
        console.log('✅ Logout successful');
        return { success: true };
    } else {
        console.log('❌ Logout failed');
        return { success: false };
    }
}

// Example usage
mikrotikLogout('+255700123456', '192.168.88.10')
    .then(result => {
        if (result.success) {
            alert('Successfully logged out from Wi-Fi');
        }
    });
```

### Response

| Status | Response | Description |
|--------|----------|-------------|
| `200` | `"OK"` | Logout successful |
| `400` | `"No username provided"` | Missing username |
| `500` | `"Logout error"` | Server error |

---

## 📊 3. MikroTik Status Check

### **Endpoint**: `GET /mikrotik/status/`

**Purpose**: Admin endpoint to check router status and connectivity.

**Method**: `GET`  
**Permission**: Admin only (`X-Admin-Access` token required)

### Headers Required

```javascript
{
    'X-Admin-Access': 'kitonga_admin_secure_token_2025'
}
```

### Frontend Integration

```javascript
// ✅ Get MikroTik Router Status (Admin only)
async function getMikrotikStatus() {
    const response = await fetch('/api/mikrotik/status/', {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            'X-Admin-Access': 'kitonga_admin_secure_token_2025'
        }
    });
    
    if (response.ok) {
        const data = await response.json();
        console.log('📊 Router Status:', data);
        return data;
    } else {
        throw new Error('Failed to get router status');
    }
}

// Example usage with UI update
getMikrotikStatus()
    .then(status => {
        // Update dashboard
        document.getElementById('routerStatus').innerHTML = `
            <div class="router-status ${status.connection_status === 'connected' ? 'online' : 'offline'}">
                <h3>🌐 Router Status</h3>
                <p>Status: <span class="status-${status.connection_status}">${status.connection_status}</span></p>
                <p>Router IP: ${status.router_ip}</p>
                <p>Hotspot Name: ${status.hotspot_name}</p>
                <p>Active Users: ${status.active_users}</p>
                <p>API Port: ${status.api_port}</p>
                <p>Last Check: ${new Date(status.timestamp).toLocaleString()}</p>
            </div>
        `;
    })
    .catch(error => {
        console.error('❌ Router status check failed:', error);
        document.getElementById('routerStatus').innerHTML = `
            <div class="router-status offline">
                <h3>🌐 Router Status</h3>
                <p class="error">❌ Unable to connect to router</p>
                <p>Error: ${error.message}</p>
            </div>
        `;
    });
```

### Success Response (200)

```json
{
    "success": true,
    "router_ip": "192.168.0.173",
    "hotspot_name": "kitonga-hotspot",
    "connection_status": "connected",
    "active_users": 5,
    "api_port": 8728,
    "admin_user": "admin",
    "timestamp": "2025-10-28T10:30:00.000Z"
}
```

### Error Response (500)

```json
{
    "success": false,
    "message": "Failed to check router status: Connection timeout",
    "router_ip": "192.168.0.173",
    "error": "Connection timeout"
}
```

---

## 👤 4. MikroTik User Status

### **Endpoint**: `GET /mikrotik/user-status/`

**Purpose**: Check individual user's authentication status and activity.

**Method**: `GET`  
**Permission**: Admin only (`X-Admin-Access` token required)

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `username` | string | ✅ | User's phone number |

### Frontend Integration

```javascript
// ✅ Get Individual User Status
async function getUserMikrotikStatus(username) {
    const response = await fetch(`/api/mikrotik/user-status/?username=${encodeURIComponent(username)}`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            'X-Admin-Access': 'kitonga_admin_secure_token_2025'
        }
    });
    
    if (response.ok) {
        const data = await response.json();
        console.log('👤 User Status:', data);
        return data;
    } else {
        const error = await response.json();
        throw new Error(error.message);
    }
}

// Example usage with user search
async function searchUserStatus() {
    const phoneNumber = document.getElementById('phoneSearch').value;
    
    if (!phoneNumber) {
        alert('Please enter a phone number');
        return;
    }
    
    try {
        const userStatus = await getUserMikrotikStatus(phoneNumber);
        
        // Display user information
        document.getElementById('userInfo').innerHTML = `
            <div class="user-status-card">
                <h3>👤 User: ${userStatus.user.phone_number}</h3>
                <div class="status-grid">
                    <div>
                        <strong>Active:</strong> 
                        <span class="${userStatus.user.is_active ? 'status-active' : 'status-inactive'}">
                            ${userStatus.user.is_active ? '✅ Yes' : '❌ No'}
                        </span>
                    </div>
                    <div>
                        <strong>Has Access:</strong> 
                        <span class="${userStatus.user.has_active_access ? 'status-active' : 'status-inactive'}">
                            ${userStatus.user.has_active_access ? '✅ Yes' : '❌ No'}
                        </span>
                    </div>
                    <div>
                        <strong>Paid Until:</strong> 
                        ${userStatus.user.paid_until ? new Date(userStatus.user.paid_until).toLocaleDateString() : 'No payment'}
                    </div>
                    <div>
                        <strong>Devices:</strong> 
                        ${userStatus.user.device_count}/${userStatus.user.max_devices}
                    </div>
                </div>
                
                <h4>📝 Recent Activity</h4>
                <div class="activity-log">
                    ${userStatus.recent_activity.map(activity => `
                        <div class="activity-item">
                            <span class="timestamp">${new Date(activity.timestamp).toLocaleString()}</span>
                            <span class="action ${activity.authenticated ? 'login' : 'logout'}">
                                ${activity.authenticated ? '🔐 Login' : '🚪 Logout'}
                            </span>
                            <span class="ip">${activity.ip_address || 'N/A'}</span>
                            <span class="notes">${activity.notes}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
        
    } catch (error) {
        console.error('❌ User status check failed:', error);
        document.getElementById('userInfo').innerHTML = `
            <div class="error-message">
                <h3>❌ Error</h3>
                <p>${error.message}</p>
            </div>
        `;
    }
}

// HTML for user search
const userSearchHTML = `
    <div class="user-search-section">
        <h3>🔍 Search User Status</h3>
        <div class="search-form">
            <input type="tel" id="phoneSearch" placeholder="+255700123456" />
            <button onclick="searchUserStatus()" class="btn-primary">Search</button>
        </div>
        <div id="userInfo"></div>
    </div>
`;
```

### Success Response (200)

```json
{
    "success": true,
    "user": {
        "phone_number": "+255700123456",
        "paid_until": "2025-11-28T10:30:00.000Z",
        "is_active": true,
        "has_active_access": true,
        "device_count": 2,
        "max_devices": 3
    },
    "recent_activity": [
        {
            "timestamp": "2025-10-28T10:25:00.000Z",
            "authenticated": true,
            "ip_address": "192.168.88.10",
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "notes": "Mikrotik authentication successful"
        },
        {
            "timestamp": "2025-10-28T09:15:00.000Z",
            "authenticated": false,
            "ip_address": "192.168.88.10",
            "mac_address": null,
            "notes": "Mikrotik logout"
        }
    ]
}
```

### Error Response (404)

```json
{
    "success": false,
    "message": "User not found"
}
```

---

## 🎯 Complete Dashboard Integration

### Full Dashboard Example

```javascript
// ✅ Complete MikroTik Management Dashboard
class MikrotikDashboard {
    constructor() {
        this.baseURL = 'http://127.0.0.1:8000/api';
        this.adminToken = 'kitonga_admin_secure_token_2025';
        this.init();
    }
    
    async init() {
        await this.loadRouterStatus();
        this.setupUserSearch();
        this.startStatusPolling();
    }
    
    async loadRouterStatus() {
        try {
            const status = await this.apiCall('/mikrotik/status/');
            this.displayRouterStatus(status);
        } catch (error) {
            this.displayRouterError(error);
        }
    }
    
    async apiCall(endpoint, options = {}) {
        const response = await fetch(`${this.baseURL}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                'X-Admin-Access': this.adminToken,
                ...options.headers
            },
            ...options
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || response.statusText);
        }
        
        return await response.json();
    }
    
    displayRouterStatus(status) {
        const statusContainer = document.getElementById('routerStatus');
        const isOnline = status.connection_status === 'connected';
        
        statusContainer.innerHTML = `
            <div class="router-card ${isOnline ? 'online' : 'offline'}">
                <div class="card-header">
                    <h3>🌐 MikroTik Router Status</h3>
                    <span class="status-indicator ${isOnline ? 'green' : 'red'}">
                        ${isOnline ? '🟢 Online' : '🔴 Offline'}
                    </span>
                </div>
                <div class="card-body">
                    <div class="info-grid">
                        <div class="info-item">
                            <label>Router IP:</label>
                            <value>${status.router_ip}</value>
                        </div>
                        <div class="info-item">
                            <label>Hotspot Name:</label>
                            <value>${status.hotspot_name}</value>
                        </div>
                        <div class="info-item">
                            <label>Active Users:</label>
                            <value>${status.active_users}</value>
                        </div>
                        <div class="info-item">
                            <label>API Port:</label>
                            <value>${status.api_port}</value>
                        </div>
                        <div class="info-item">
                            <label>Admin User:</label>
                            <value>${status.admin_user}</value>
                        </div>
                        <div class="info-item">
                            <label>Last Check:</label>
                            <value>${new Date(status.timestamp).toLocaleString()}</value>
                        </div>
                    </div>
                </div>
                <div class="card-actions">
                    <button onclick="dashboard.refreshStatus()" class="btn-refresh">
                        🔄 Refresh Status
                    </button>
                </div>
            </div>
        `;
    }
    
    displayRouterError(error) {
        const statusContainer = document.getElementById('routerStatus');
        statusContainer.innerHTML = `
            <div class="router-card offline error">
                <div class="card-header">
                    <h3>🌐 MikroTik Router Status</h3>
                    <span class="status-indicator red">🔴 Error</span>
                </div>
                <div class="card-body">
                    <div class="error-message">
                        <p>❌ Unable to connect to router</p>
                        <p class="error-details">${error.message}</p>
                    </div>
                </div>
                <div class="card-actions">
                    <button onclick="dashboard.refreshStatus()" class="btn-refresh">
                        🔄 Retry Connection
                    </button>
                </div>
            </div>
        `;
    }
    
    setupUserSearch() {
        const searchContainer = document.getElementById('userSearch');
        searchContainer.innerHTML = `
            <div class="user-search-card">
                <div class="card-header">
                    <h3>🔍 User Status Lookup</h3>
                </div>
                <div class="card-body">
                    <div class="search-form">
                        <input type="tel" 
                               id="phoneNumberInput" 
                               placeholder="+255700123456" 
                               onkeypress="if(event.key==='Enter') dashboard.searchUser()"
                        />
                        <button onclick="dashboard.searchUser()" class="btn-search">
                            🔍 Search
                        </button>
                    </div>
                    <div id="userSearchResults"></div>
                </div>
            </div>
        `;
    }
    
    async searchUser() {
        const phoneNumber = document.getElementById('phoneNumberInput').value;
        const resultsContainer = document.getElementById('userSearchResults');
        
        if (!phoneNumber) {
            resultsContainer.innerHTML = '<p class="error">Please enter a phone number</p>';
            return;
        }
        
        resultsContainer.innerHTML = '<p class="loading">🔍 Searching...</p>';
        
        try {
            const userStatus = await this.apiCall(`/mikrotik/user-status/?username=${encodeURIComponent(phoneNumber)}`);
            this.displayUserStatus(userStatus);
        } catch (error) {
            resultsContainer.innerHTML = `
                <div class="error-result">
                    <h4>❌ Search Failed</h4>
                    <p>${error.message}</p>
                </div>
            `;
        }
    }
    
    displayUserStatus(userStatus) {
        const resultsContainer = document.getElementById('userSearchResults');
        const user = userStatus.user;
        
        resultsContainer.innerHTML = `
            <div class="user-result-card">
                <div class="user-header">
                    <h4>👤 ${user.phone_number}</h4>
                    <div class="status-badges">
                        <span class="badge ${user.is_active ? 'active' : 'inactive'}">
                            ${user.is_active ? '✅ Active' : '❌ Inactive'}
                        </span>
                        <span class="badge ${user.has_active_access ? 'access' : 'no-access'}">
                            ${user.has_active_access ? '🔓 Has Access' : '🔒 No Access'}
                        </span>
                    </div>
                </div>
                
                <div class="user-details">
                    <div class="detail-item">
                        <label>Paid Until:</label>
                        <value>${user.paid_until ? new Date(user.paid_until).toLocaleDateString() : 'No payment'}</value>
                    </div>
                    <div class="detail-item">
                        <label>Devices:</label>
                        <value>${user.device_count}/${user.max_devices}</value>
                    </div>
                </div>
                
                <div class="activity-section">
                    <h5>📝 Recent Activity (Last 5)</h5>
                    <div class="activity-list">
                        ${userStatus.recent_activity.map(activity => `
                            <div class="activity-item">
                                <div class="activity-time">
                                    ${new Date(activity.timestamp).toLocaleString()}
                                </div>
                                <div class="activity-action ${activity.authenticated ? 'login' : 'logout'}">
                                    ${activity.authenticated ? '🔐 Login' : '🚪 Logout'}
                                </div>
                                <div class="activity-details">
                                    <small>IP: ${activity.ip_address || 'N/A'}</small>
                                    <small>${activity.notes}</small>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
    }
    
    async refreshStatus() {
        await this.loadRouterStatus();
    }
    
    startStatusPolling() {
        // Refresh router status every 30 seconds
        setInterval(() => {
            this.refreshStatus();
        }, 30000);
    }
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new MikrotikDashboard();
});
```

### Required HTML Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MikroTik Management Dashboard</title>
    <style>
        .router-card, .user-search-card, .user-result-card {
            border: 1px solid #ddd;
            border-radius: 8px;
            margin: 16px 0;
            background: white;
        }
        
        .router-card.online { border-color: #4caf50; }
        .router-card.offline { border-color: #f44336; }
        
        .card-header {
            padding: 16px;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .status-indicator.green { color: #4caf50; }
        .status-indicator.red { color: #f44336; }
        
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
            padding: 16px;
        }
        
        .info-item {
            display: flex;
            justify-content: space-between;
        }
        
        .info-item label {
            font-weight: bold;
            color: #666;
        }
        
        .search-form {
            display: flex;
            gap: 8px;
            margin-bottom: 16px;
        }
        
        .search-form input {
            flex: 1;
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        
        .btn-search, .btn-refresh {
            background: #2196f3;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
        }
        
        .badge {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }
        
        .badge.active { background: #e8f5e8; color: #2e7d32; }
        .badge.inactive { background: #ffebee; color: #c62828; }
        .badge.access { background: #e3f2fd; color: #1565c0; }
        .badge.no-access { background: #fff3e0; color: #ef6c00; }
        
        .activity-item {
            border-bottom: 1px solid #eee;
            padding: 8px 0;
        }
        
        .activity-item:last-child {
            border-bottom: none;
        }
        
        .loading { color: #666; font-style: italic; }
        .error { color: #f44336; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌐 MikroTik Management Dashboard</h1>
        
        <div id="routerStatus">
            <p class="loading">Loading router status...</p>
        </div>
        
        <div id="userSearch">
            <p class="loading">Loading user search...</p>
        </div>
    </div>
    
    <script src="mikrotik-dashboard.js"></script>
</body>
</html>
```

---

## 🔧 Testing Commands

Use these curl commands to test the endpoints:

```bash
# Test router status (Admin required)
curl -X GET "http://127.0.0.1:8000/api/mikrotik/status/" \
  -H "X-Admin-Access: kitonga_admin_secure_token_2025"

# Test user status (Admin required)
curl -X GET "http://127.0.0.1:8000/api/mikrotik/user-status/?username=%2B255700123456" \
  -H "X-Admin-Access: kitonga_admin_secure_token_2025"

# Test authentication (Usually called by MikroTik)
curl -X POST "http://127.0.0.1:8000/api/mikrotik/auth/" \
  -H "Content-Type: application/json" \
  -d '{"username":"+255700123456","mac":"AA:BB:CC:DD:EE:FF","ip":"192.168.88.10"}'

# Test logout (Usually called by MikroTik)
curl -X POST "http://127.0.0.1:8000/api/mikrotik/logout/" \
  -H "Content-Type: application/json" \
  -d '{"username":"+255700123456","ip":"192.168.88.10"}'
```

---

## 📝 Summary

The MikroTik integration endpoints provide:

- ✅ **Router Authentication**: Validates users accessing Wi-Fi hotspot
- ✅ **User Logout**: Handles clean disconnection from hotspot
- ✅ **Router Status**: Admin monitoring of router connectivity and stats
- ✅ **User Status**: Individual user access and activity monitoring

All endpoints include proper error handling, logging, and security measures for a production Wi-Fi billing system.
