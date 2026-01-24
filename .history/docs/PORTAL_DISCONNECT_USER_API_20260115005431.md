# Tenant Portal - Disconnect User from Router API

## Overview

The **Portal Router Disconnect User API** allows tenants to forcefully disconnect a specific user from their MikroTik router. This is useful for troubleshooting, enforcing policies, or manually removing users from the network.

---

## 🔗 API Endpoint

**URL:** `POST /api/portal/router/<router_id>/disconnect-user/`

**Authentication:** Tenant API Key (required)

**Access:** Tenant Portal only - tenants can only disconnect users from their own routers

---

## 📋 Request

### Headers

```http
Authorization: Bearer YOUR_TENANT_API_KEY
Content-Type: application/json
```

### URL Parameters

| Parameter   | Type    | Required | Description                                  |
| ----------- | ------- | -------- | -------------------------------------------- |
| `router_id` | integer | Yes      | The ID of the router to disconnect user from |

### Request Body

```json
{
  "username": "+255712345678",
  "mac_address": "AA:BB:CC:DD:EE:FF"
}
```

| Field         | Type   | Required | Description                                                      |
| ------------- | ------ | -------- | ---------------------------------------------------------------- |
| `username`    | string | Yes      | User's phone number                                              |
| `mac_address` | string | No       | Specific device MAC address (optional - targets specific device) |

### Example Request

```bash
curl -X POST "https://api.kitonga.klikcell.com/api/portal/router/1/disconnect-user/" \
  -H "Authorization: Bearer YOUR_TENANT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "+255712345678",
    "mac_address": "AA:BB:CC:DD:EE:FF"
  }'
```

**Without MAC address (disconnects all devices for this user):**

```bash
curl -X POST "https://api.kitonga.klikcell.com/api/portal/router/1/disconnect-user/" \
  -H "Authorization: Bearer YOUR_TENANT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "+255712345678"
  }'
```

---

## ✅ Success Response (200 OK)

```json
{
  "success": true,
  "message": "User +255712345678 disconnected from Main Office Router",
  "router": {
    "id": 1,
    "name": "Main Office Router"
  },
  "details": {
    "session_removed": true,
    "binding_removed": true,
    "user_disabled": false
  }
}
```

### Response Fields

| Field                     | Type    | Description                     |
| ------------------------- | ------- | ------------------------------- |
| `success`                 | boolean | Whether the operation succeeded |
| `message`                 | string  | Human-readable success message  |
| `router`                  | object  | Router information              |
| `router.id`               | integer | Router database ID              |
| `router.name`             | string  | Router name                     |
| `details`                 | object  | Disconnection details           |
| `details.session_removed` | boolean | Active hotspot session removed  |
| `details.binding_removed` | boolean | IP binding removed              |
| `details.user_disabled`   | boolean | Hotspot user disabled           |

### What Gets Disconnected?

The API performs comprehensive disconnection:

1. **Removes active sessions** - Kicks user off the network immediately
2. **Removes IP bindings** - Clears IP address associations
3. **Disables hotspot user** - Prevents automatic reconnection (if applicable)

---

## ❌ Error Responses

### Missing Username (400)

```json
{
  "success": false,
  "error": "username is required"
}
```

**Cause:** Request body doesn't include `username` field

### Router Not Found (404)

```json
{
  "success": false,
  "error": "Router not found or access denied"
}
```

**Cause:** Router ID doesn't exist or doesn't belong to your tenant

### User Not Found (404)

```json
{
  "success": false,
  "error": "User not found or does not belong to your tenant"
}
```

**Cause:** Username doesn't exist in your tenant's user database

### Router Connection Failed (503)

```json
{
  "success": false,
  "error": "Cannot connect to router Main Office Router. Please check router configuration."
}
```

**Cause:** Cannot establish connection to MikroTik router

### Disconnection Failed (500)

```json
{
  "success": false,
  "error": "Failed to disconnect user from Main Office Router",
  "details": ["Session not found", "Could not remove IP binding"]
}
```

**Cause:** MikroTik API errors during disconnection process

---

## 💡 Use Cases

### 1. Manual Disconnection from Dashboard

Quick disconnect button next to active users:

```javascript
async function disconnectUser(routerId, username, macAddress) {
  const response = await fetch(`/api/portal/router/${routerId}/disconnect-user/`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      username: username,
      mac_address: macAddress
    })
  })

  const data = await response.json()

  if (data.success) {
    alert(`User ${username} disconnected successfully`)
    // Refresh active users list
    refreshActiveUsers(routerId)
  } else {
    alert(`Failed to disconnect: ${data.error}`)
  }
}
```

### 2. Disconnect Expired Users

Manually disconnect users who should have expired:

```javascript
async function disconnectExpiredUsers(routerId, activeUsers) {
  const now = new Date()

  for (const user of activeUsers) {
    const dbInfo = user.database_info

    if (dbInfo && !dbInfo.has_active_access) {
      console.log(`Disconnecting expired user: ${user.username}`)

      await fetch(`/api/portal/router/${routerId}/disconnect-user/`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          username: user.username,
          mac_address: user.mac_address
        })
      })

      // Wait a bit between disconnections
      await new Promise(resolve => setTimeout(resolve, 500))
    }
  }

  console.log('Expired users disconnected')
}
```

### 3. React Component with Active Users Table

```jsx
import React, { useState } from 'react'

function ActiveUsersTable({ routerId, users, apiKey, onRefresh }) {
  const [disconnecting, setDisconnecting] = useState({})

  const handleDisconnect = async (username, macAddress) => {
    setDisconnecting({ ...disconnecting, [username]: true })

    try {
      const response = await fetch(`/api/portal/router/${routerId}/disconnect-user/`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          username: username,
          mac_address: macAddress
        })
      })

      const data = await response.json()

      if (data.success) {
        alert(`${username} disconnected successfully`)
        onRefresh() // Refresh the users list
      } else {
        alert(`Failed: ${data.error}`)
      }
    } catch (error) {
      alert(`Error: ${error.message}`)
    } finally {
      setDisconnecting({ ...disconnecting, [username]: false })
    }
  }

  return (
    <table>
      <thead>
        <tr>
          <th>User</th>
          <th>IP Address</th>
          <th>Uptime</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {users.map(user => (
          <tr key={user.session_id}>
            <td>{user.username}</td>
            <td>{user.ip_address}</td>
            <td>{user.uptime}</td>
            <td>{user.database_info?.has_active_access ? <span className="badge-success">Active</span> : <span className="badge-danger">Expired</span>}</td>
            <td>
              <button onClick={() => handleDisconnect(user.username, user.mac_address)} disabled={disconnecting[user.username]} className="btn-danger">
                {disconnecting[user.username] ? 'Disconnecting...' : 'Disconnect'}
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
```

### 4. Bulk Disconnect Multiple Users

```javascript
async function bulkDisconnect(routerId, usernames, apiKey) {
  const results = []

  for (const username of usernames) {
    try {
      const response = await fetch(`/api/portal/router/${routerId}/disconnect-user/`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ username })
      })

      const data = await response.json()
      results.push({
        username,
        success: data.success,
        message: data.message || data.error
      })
    } catch (error) {
      results.push({
        username,
        success: false,
        message: error.message
      })
    }

    // Delay between requests to avoid overwhelming the router
    await new Promise(resolve => setTimeout(resolve, 300))
  }

  return results
}

// Usage
const usersToDisconnect = ['+255712345678', '+255787654321']
const results = await bulkDisconnect(1, usersToDisconnect, apiKey)
console.log('Disconnect results:', results)
```

### 5. Troubleshooting Helper

Disconnect and log details for support:

```javascript
async function troubleshootUserConnection(routerId, username, apiKey) {
  console.log(`=== Troubleshooting ${username} ===`)

  // Step 1: Check if user is currently connected
  const activeResponse = await fetch(`/api/portal/router/${routerId}/active-users/`, {
    headers: { Authorization: `Bearer ${apiKey}` }
  })

  const activeData = await activeResponse.json()
  const userSession = activeData.active_users?.find(u => u.username === username)

  if (!userSession) {
    console.log('User is not currently connected')
    return
  }

  console.log('User found:', {
    ip: userSession.ip_address,
    mac: userSession.mac_address,
    uptime: userSession.uptime,
    hasAccess: userSession.database_info?.has_active_access
  })

  // Step 2: Disconnect user
  console.log('Attempting to disconnect...')

  const disconnectResponse = await fetch(`/api/portal/router/${routerId}/disconnect-user/`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      username: username,
      mac_address: userSession.mac_address
    })
  })

  const disconnectData = await disconnectResponse.json()
  console.log('Disconnect result:', disconnectData)

  // Step 3: Wait and verify
  await new Promise(resolve => setTimeout(resolve, 2000))

  const verifyResponse = await fetch(`/api/portal/router/${routerId}/active-users/`, {
    headers: { Authorization: `Bearer ${apiKey}` }
  })

  const verifyData = await verifyResponse.json()
  const stillConnected = verifyData.active_users?.find(u => u.username === username)

  if (stillConnected) {
    console.error('WARNING: User still appears connected after disconnect!')
  } else {
    console.log('SUCCESS: User successfully disconnected')
  }
}
```

---

## 🔄 Integration with Active Users API

Perfect workflow combining both APIs:

```javascript
class RouterUserManager {
  constructor(routerId, apiKey) {
    this.routerId = routerId
    this.apiKey = apiKey
  }

  async getActiveUsers() {
    const response = await fetch(`/api/portal/router/${this.routerId}/active-users/`, {
      headers: {
        Authorization: `Bearer ${this.apiKey}`
      }
    })
    return await response.json()
  }

  async disconnectUser(username, macAddress = null) {
    const response = await fetch(`/api/portal/router/${this.routerId}/disconnect-user/`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        username: username,
        mac_address: macAddress
      })
    })
    return await response.json()
  }

  async disconnectExpiredUsers() {
    const activeData = await this.getActiveUsers()

    if (!activeData.success) {
      throw new Error(activeData.error)
    }

    const expiredUsers = activeData.active_users.filter(user => user.database_info && !user.database_info.has_active_access)

    console.log(`Found ${expiredUsers.length} expired users to disconnect`)

    const results = []
    for (const user of expiredUsers) {
      const result = await this.disconnectUser(user.username, user.mac_address)
      results.push(result)
      await new Promise(resolve => setTimeout(resolve, 300))
    }

    return results
  }
}

// Usage
const manager = new RouterUserManager(1, 'YOUR_API_KEY')
await manager.disconnectExpiredUsers()
```

---

## 🎯 Key Differences: Portal vs Admin APIs

| Feature              | Portal API (`/portal/router/.../disconnect-user/`) | Admin API (`/admin/mikrotik/disconnect-user/`) |
| -------------------- | -------------------------------------------------- | ---------------------------------------------- |
| **Access**           | Tenant API Key only                                | Platform Admin authentication                  |
| **Scope**            | Specific router only                               | Global (all routers)                           |
| **Router ID**        | Required in URL                                    | Uses default router from settings              |
| **Tenant Isolation** | Automatic (only tenant's users)                    | No restriction (all tenants)                   |
| **Validation**       | Validates user belongs to tenant                   | No tenant validation                           |

---

## 🔐 Security Features

1. **Tenant Isolation** - Tenants can only disconnect users from their own routers
2. **User Validation** - Verifies user belongs to the tenant before disconnection
3. **Router Ownership** - Ensures router belongs to the requesting tenant
4. **Audit Logging** - All disconnections are logged with tenant and router info
5. **API Key Required** - Must provide valid tenant API key

---

## 📊 Response Time & Performance

- **Average response time:** 1-3 seconds
- **MikroTik operations:** Typically < 500ms per operation
- **Network latency:** Depends on router location
- **Bulk operations:** Use 300-500ms delay between requests

---

## 🚨 Important Notes

### MAC Address Parameter

- **With MAC:** Disconnects only that specific device
- **Without MAC:** Disconnects all devices for that username

### Disconnection Scope

This API disconnects users from **ONE specific router**. To disconnect from all tenant routers, use the existing user-level API:

```bash
POST /api/portal/users/<user_id>/disconnect/
```

### Rate Limiting

When disconnecting multiple users, add delays between requests to avoid:

- Overwhelming the MikroTik router
- API rate limits
- Connection timeouts

---

## 🎉 Summary

The Portal Router Disconnect User API gives tenants complete control over their router connections:

✅ **Router-specific** - Target specific routers in multi-router setups  
✅ **Immediate effect** - User disconnected within seconds  
✅ **Safe & secure** - Tenant isolation ensures security  
✅ **Detailed feedback** - Know exactly what was disconnected  
✅ **Easy integration** - Works perfectly with Active Users API

**Perfect for:**

- Manual network management
- Troubleshooting connection issues
- Enforcing access policies
- Cleaning up expired sessions
- Multi-router environments

**Ready to deploy!** 🚀
