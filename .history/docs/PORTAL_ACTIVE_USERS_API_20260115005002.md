# Tenant Portal - Active Users API

## Overview

The **Portal Router Active Users API** allows tenants to view all users currently connected to their MikroTik routers in real-time. This is essential for monitoring WiFi usage, troubleshooting connection issues, and understanding which customers are actively using the service.

---

## 🔗 API Endpoint

**URL:** `GET /api/portal/router/<router_id>/active-users/`

**Authentication:** Tenant API Key (required)

**Access:** Tenant Portal only - tenants can only see users on their own routers

---

## 📋 Request

### Headers

```http
Authorization: Bearer YOUR_TENANT_API_KEY
Content-Type: application/json
```

### URL Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `router_id` | integer | Yes | The ID of the router to query |

### Example Request

```bash
curl -X GET "https://api.kitonga.klikcell.com/api/portal/router/1/active-users/" \
  -H "Authorization: Bearer YOUR_TENANT_API_KEY"
```

---

## ✅ Success Response (200 OK)

```json
{
  "success": true,
  "router": {
    "id": 1,
    "name": "Main Office Router",
    "host": "10.50.0.2",
    "status": "online"
  },
  "active_users": [
    {
      "session_id": "*1234",
      "username": "+255712345678",
      "mac_address": "AA:BB:CC:DD:EE:FF",
      "ip_address": "10.5.50.100",
      "uptime": "1h30m15s",
      "bytes_in": "52428800",
      "bytes_out": "104857600",
      "idle_time": "5s",
      "login_time": "macauth",
      "database_info": {
        "user_id": 42,
        "is_active": true,
        "has_active_access": true,
        "access_expires_at": "2026-01-16T10:30:00Z",
        "time_remaining": "23:45:30"
      }
    },
    {
      "session_id": "*5678",
      "username": "+255787654321",
      "mac_address": "BB:CC:DD:EE:FF:00",
      "ip_address": "10.5.50.101",
      "uptime": "45m22s",
      "bytes_in": "10485760",
      "bytes_out": "31457280",
      "idle_time": "2s",
      "login_time": "macauth",
      "database_info": {
        "user_id": 89,
        "is_active": true,
        "has_active_access": true,
        "access_expires_at": "2026-01-15T15:00:00Z",
        "time_remaining": "2:15:45"
      }
    }
  ],
  "total_count": 2,
  "timestamp": "2026-01-15T12:44:15.123456Z"
}
```

### Response Fields

#### Router Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Router database ID |
| `name` | string | Router name |
| `host` | string | Router IP address |
| `status` | string | Router status (online/offline) |

#### Active Users Array

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | MikroTik session ID (used for disconnection) |
| `username` | string | User's phone number |
| `mac_address` | string | Device MAC address |
| `ip_address` | string | Assigned IP address |
| `uptime` | string | How long user has been connected |
| `bytes_in` | string | Bytes downloaded (received) |
| `bytes_out` | string | Bytes uploaded (sent) |
| `idle_time` | string | Time since last activity |
| `login_time` | string | Login method (usually "macauth") |
| `database_info` | object | User information from database |

#### Database Info Object

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | integer/null | User's database ID (null if not found) |
| `is_active` | boolean | Whether user account is active |
| `has_active_access` | boolean | Whether user has valid paid access |
| `access_expires_at` | string/null | ISO timestamp when access expires |
| `time_remaining` | string/null | Human-readable time until expiry |
| `note` | string | Note if user not found in database |

---

## ❌ Error Responses

### Router Not Found (404)

```json
{
  "success": false,
  "error": "Router not found or access denied"
}
```

**Cause:** Router ID doesn't exist or doesn't belong to your tenant

### Router Connection Failed (503)

```json
{
  "success": false,
  "error": "Cannot connect to router Main Office Router. Please check router configuration."
}
```

**Cause:** Cannot establish connection to MikroTik router (wrong credentials, router offline, network issues)

### Internal Error (500)

```json
{
  "success": false,
  "error": "Error retrieving active users from MikroTik: [error details]"
}
```

**Cause:** Unexpected error querying MikroTik router

---

## 💡 Use Cases

### 1. Real-Time Monitoring Dashboard

Display active users count and bandwidth usage on your dashboard:

```javascript
async function updateActivUsersDisplay(routerId) {
  const response = await fetch(`/api/portal/router/${routerId}/active-users/`, {
    headers: {
      'Authorization': `Bearer ${apiKey}`
    }
  });
  
  const data = await response.json();
  
  if (data.success) {
    document.getElementById('active-count').textContent = data.total_count;
    
    // Calculate total bandwidth
    const totalDownload = data.active_users.reduce((sum, user) => 
      sum + parseInt(user.bytes_in), 0
    );
    const totalUpload = data.active_users.reduce((sum, user) => 
      sum + parseInt(user.bytes_out), 0
    );
    
    displayBandwidth(totalDownload, totalUpload);
  }
}
```

### 2. User Connection Troubleshooting

Check if a specific user is connected:

```javascript
async function checkUserConnection(routerId, phoneNumber) {
  const response = await fetch(`/api/portal/router/${routerId}/active-users/`, {
    headers: {
      'Authorization': `Bearer ${apiKey}`
    }
  });
  
  const data = await response.json();
  
  if (data.success) {
    const userSession = data.active_users.find(u => u.username === phoneNumber);
    
    if (userSession) {
      console.log('User is connected:', {
        ip: userSession.ip_address,
        uptime: userSession.uptime,
        expiresAt: userSession.database_info?.access_expires_at
      });
    } else {
      console.log('User is NOT connected to this router');
    }
  }
}
```

### 3. Identify Expired Users Still Connected

Find users who should have been disconnected:

```javascript
function findExpiredUsersStillConnected(activeUsersData) {
  const expiredUsers = activeUsersData.active_users.filter(user => {
    const dbInfo = user.database_info;
    return dbInfo && !dbInfo.has_active_access;
  });
  
  if (expiredUsers.length > 0) {
    console.warn('Found expired users still connected:', expiredUsers);
    // Alert admin or trigger manual disconnection
  }
}
```

### 4. Bandwidth Usage Report

Generate bandwidth usage for all active users:

```javascript
function generateBandwidthReport(activeUsersData) {
  return activeUsersData.active_users.map(user => ({
    username: user.username,
    downloadMB: (parseInt(user.bytes_in) / 1024 / 1024).toFixed(2),
    uploadMB: (parseInt(user.bytes_out) / 1024 / 1024).toFixed(2),
    totalMB: ((parseInt(user.bytes_in) + parseInt(user.bytes_out)) / 1024 / 1024).toFixed(2),
    uptime: user.uptime,
    timeRemaining: user.database_info?.time_remaining || 'N/A'
  }));
}
```

---

## 🔄 Auto-Refresh Pattern

For live monitoring, implement auto-refresh with proper error handling:

```javascript
class ActiveUsersMonitor {
  constructor(routerId, apiKey, refreshInterval = 10000) {
    this.routerId = routerId;
    this.apiKey = apiKey;
    this.refreshInterval = refreshInterval;
    this.intervalId = null;
  }
  
  async fetchActiveUsers() {
    try {
      const response = await fetch(
        `/api/portal/router/${this.routerId}/active-users/`,
        {
          headers: {
            'Authorization': `Bearer ${this.apiKey}`
          }
        }
      );
      
      const data = await response.json();
      
      if (data.success) {
        this.onUpdate(data);
      } else {
        this.onError(data.error);
      }
    } catch (error) {
      this.onError(error.message);
    }
  }
  
  start() {
    this.fetchActiveUsers(); // Initial fetch
    this.intervalId = setInterval(() => {
      this.fetchActiveUsers();
    }, this.refreshInterval);
  }
  
  stop() {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }
  
  onUpdate(data) {
    // Override this method to handle updates
    console.log(`${data.total_count} users online`);
  }
  
  onError(error) {
    // Override this method to handle errors
    console.error('Error fetching active users:', error);
  }
}

// Usage
const monitor = new ActiveUsersMonitor(1, 'YOUR_API_KEY', 10000);
monitor.onUpdate = (data) => {
  updateDashboard(data);
};
monitor.start();
```

---

## 🎯 Key Differences: Portal API vs Admin API

| Feature | Portal API (`/api/portal/router/.../active-users/`) | Admin API (`/api/admin/routers/.../active-users/`) |
|---------|-----------------------------------------------------|---------------------------------------------------|
| **Access** | Tenant API Key only | Platform Admin authentication |
| **Scope** | Only tenant's own routers | All routers across all tenants |
| **Use Case** | Tenant self-service monitoring | Platform-wide administration |
| **Response** | Includes router status | Includes tenant information |

---

## 📊 Example Frontend Implementation

### React Component

```jsx
import React, { useState, useEffect } from 'react';

function ActiveUsersTable({ routerId, apiKey }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const response = await fetch(
          `/api/portal/router/${routerId}/active-users/`,
          {
            headers: {
              'Authorization': `Bearer ${apiKey}`
            }
          }
        );
        
        const data = await response.json();
        
        if (data.success) {
          setUsers(data.active_users);
          setError(null);
        } else {
          setError(data.error);
        }
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    
    fetchUsers();
    const interval = setInterval(fetchUsers, 10000); // Refresh every 10s
    
    return () => clearInterval(interval);
  }, [routerId, apiKey]);
  
  if (loading) return <div>Loading active users...</div>;
  if (error) return <div>Error: {error}</div>;
  
  return (
    <div>
      <h2>Active Users ({users.length})</h2>
      <table>
        <thead>
          <tr>
            <th>Phone Number</th>
            <th>IP Address</th>
            <th>Uptime</th>
            <th>Download</th>
            <th>Upload</th>
            <th>Expires In</th>
          </tr>
        </thead>
        <tbody>
          {users.map(user => (
            <tr key={user.session_id}>
              <td>{user.username}</td>
              <td>{user.ip_address}</td>
              <td>{user.uptime}</td>
              <td>{(parseInt(user.bytes_in) / 1024 / 1024).toFixed(2)} MB</td>
              <td>{(parseInt(user.bytes_out) / 1024 / 1024).toFixed(2)} MB</td>
              <td>{user.database_info?.time_remaining || 'N/A'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

---

## 🔐 Security Notes

1. **Tenant Isolation:** API automatically ensures tenants can only see users on their own routers
2. **API Key Required:** Must include valid tenant API key in Authorization header
3. **Rate Limiting:** Consider implementing rate limiting for auto-refresh to avoid overloading MikroTik
4. **Sensitive Data:** MAC addresses and IP addresses are included - handle with care per privacy policies

---

## 🚀 Best Practices

1. **Refresh Interval:** Use 10-30 second intervals for live monitoring (don't refresh too frequently)
2. **Error Handling:** Always handle connection errors gracefully (router might be offline)
3. **Data Formatting:** Convert bytes to MB/GB for better user experience
4. **Time Display:** Format `time_remaining` into human-readable format
5. **Caching:** Consider caching results for 5-10 seconds on frontend to reduce API calls

---

## 📝 Related APIs

- **Disconnect User:** `POST /api/portal/users/<user_id>/disconnect/`
- **User Details:** `GET /api/portal/users/<user_id>/`
- **Router Monitoring:** `GET /api/portal/router/<router_id>/monitoring/`
- **Router Health:** `GET /api/portal/router/health/`

---

## 🎉 Summary

The Portal Router Active Users API provides real-time visibility into who's connected to your WiFi network. Perfect for:

✅ **Live Dashboard** - Show current user count and bandwidth usage  
✅ **Troubleshooting** - Check if specific users are connected  
✅ **Monitoring** - Identify expired users still online  
✅ **Reports** - Generate bandwidth usage reports  
✅ **Alerts** - Detect unusual activity or connection issues

**Ready to use!** Just deploy to your VPS and tenants can start monitoring their routers! 🚀
