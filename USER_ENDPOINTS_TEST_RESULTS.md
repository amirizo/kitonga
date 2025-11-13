# User Management API Endpoints - Test Results

**Test Date:** November 13, 2025  
**Base URL:** `http://127.0.0.1:8000/api`  
**Authentication:** Required (X-Admin-Access header)  
**Test Status:** ✅ 4/4 Tests Passed (100%)

---

## API Endpoints Tested

1. `GET /api/users/` - List all users
2. `GET /api/users/<user_id>/` - Get user detail

---

## Test Results

### TEST 1: List All Users

**Endpoint:** `GET /api/users/`

**Request:**
```http
GET /api/users/ HTTP/1.1
Host: 127.0.0.1:8000
X-Admin-Access: kitonga_admin_2025
Content-Type: application/json
```

**Response Status:** `200 OK`

**JSON Response:**
```json
[
  {
    "id": 20,
    "phone_number": "+255743852695",
    "is_active": true,
    "created_at": "2025-11-13T11:57:40.415066+00:00",
    "paid_until": "2025-11-14T12:07:56.120114+00:00",
    "has_active_access": true,
    "max_devices": 3,
    "total_payments": 0,
    "device_count": 1,
    "payment_count": 1,
    "last_payment": {
      "amount": "1000.00",
      "bundle_name": "Test Bundle",
      "completed_at": null
    }
  },
  {
    "id": 19,
    "phone_number": "+255684106419",
    "is_active": true,
    "created_at": "2025-11-13T11:55:37.693766+00:00",
    "paid_until": null,
    "has_active_access": false,
    "max_devices": 3,
    "total_payments": 0,
    "device_count": 0,
    "payment_count": 0,
    "last_payment": null
  },
  {
    "id": 18,
    "phone_number": "+255772236727",
    "is_active": true,
    "created_at": "2025-11-12T14:14:50.929681+00:00",
    "paid_until": null,
    "has_active_access": false,
    "max_devices": 3,
    "total_payments": 0,
    "device_count": 0,
    "payment_count": 0,
    "last_payment": null
  }
]
```

**Response Fields Explanation:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Unique user identifier |
| `phone_number` | string | User's phone number (E.164 format) |
| `is_active` | boolean | Whether the user account is active |
| `created_at` | string (ISO 8601) | User account creation timestamp |
| `paid_until` | string/null (ISO 8601) | Expiry date of current access (null if no active payment) |
| `has_active_access` | boolean | Whether user currently has valid internet access |
| `max_devices` | integer | Maximum number of devices allowed |
| `total_payments` | number | Total amount paid by user (all time) |
| `device_count` | integer | Number of registered devices |
| `payment_count` | integer | Total number of completed payments |
| `last_payment` | object/null | Details of most recent payment (null if none) |

**Last Payment Object:**
- `amount`: Payment amount (string with 2 decimal places)
- `bundle_name`: Name of the purchased bundle
- `completed_at`: Payment completion timestamp (ISO 8601 format, null if pending)

---

### TEST 2: Get User Detail

**Endpoint:** `GET /api/users/<user_id>/`

**Request:**
```http
GET /api/users/20/ HTTP/1.1
Host: 127.0.0.1:8000
X-Admin-Access: kitonga_admin_2025
Content-Type: application/json
```

**Response Status:** `200 OK`

**JSON Response:**
```json
{
  "success": true,
  "user": {
    "id": 20,
    "phone_number": "+255743852695",
    "is_active": true,
    "created_at": "2025-11-13T11:57:40.415066+00:00",
    "has_active_access": true,
    "payments": [
      {
        "id": 29,
        "amount": "1000.00",
        "status": "completed",
        "bundle_name": "Test Bundle",
        "order_reference": "ORD-4068da428195",
        "created_at": "2025-11-13T11:59:52.001534+00:00",
        "completed_at": null
      }
    ],
    "devices": [
      {
        "id": 8,
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "device_name": "Device-DD:EE:FF",
        "is_active": true,
        "last_seen": "2025-11-13T12:00:31.290368+00:00",
        "first_seen": "2025-11-13T12:00:31.286509+00:00"
      }
    ],
    "access_logs": [
      {
        "id": 50,
        "access_granted": false,
        "denial_reason": "Disconnected by admin user: Unknown",
        "ip_address": "127.0.0.1",
        "mac_address": "",
        "timestamp": "2025-11-13T12:07:56.548141+00:00"
      },
      {
        "id": 49,
        "access_granted": false,
        "denial_reason": "Disconnected by admin user: Unknown",
        "ip_address": "127.0.0.1",
        "mac_address": "",
        "timestamp": "2025-11-13T12:07:02.285593+00:00"
      },
      {
        "id": 48,
        "access_granted": false,
        "denial_reason": "Disconnected by admin user: Unknown",
        "ip_address": "127.0.0.1",
        "mac_address": "",
        "timestamp": "2025-11-13T12:06:27.445595+00:00"
      },
      {
        "id": 47,
        "access_granted": false,
        "denial_reason": "Mikrotik logout",
        "ip_address": "192.168.0.100",
        "mac_address": "",
        "timestamp": "2025-11-13T12:00:31.295208+00:00"
      },
      {
        "id": 46,
        "access_granted": false,
        "denial_reason": "Mikrotik logout",
        "ip_address": "192.168.0.100",
        "mac_address": "",
        "timestamp": "2025-11-13T12:00:31.294128+00:00"
      },
      {
        "id": 45,
        "access_granted": true,
        "denial_reason": "",
        "ip_address": "192.168.0.100",
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "timestamp": "2025-11-13T12:00:31.291781+00:00"
      },
      {
        "id": 44,
        "access_granted": true,
        "denial_reason": "",
        "ip_address": "192.168.0.100",
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "timestamp": "2025-11-13T12:00:31.288177+00:00"
      }
    ],
    "statistics": {
      "total_payments": 1,
      "total_spent": 1000.0,
      "device_count": 1,
      "active_devices": 1
    }
  }
}
```

**Response Structure:**

**Root Level:**
| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether the request was successful |
| `user` | object | Detailed user information object |

**User Object Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Unique user identifier |
| `phone_number` | string | User's phone number |
| `is_active` | boolean | Account active status |
| `created_at` | string (ISO 8601) | Account creation timestamp |
| `has_active_access` | boolean | Current internet access status |
| `payments` | array | List of all payment transactions |
| `devices` | array | List of registered devices |
| `access_logs` | array | Connection/disconnection history |
| `statistics` | object | Aggregated user statistics |

**Payment Object Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Payment transaction ID |
| `amount` | string | Payment amount (decimal string) |
| `status` | string | Payment status (pending/completed/failed/refunded) |
| `bundle_name` | string | Name of purchased bundle |
| `order_reference` | string | Unique order reference code |
| `created_at` | string (ISO 8601) | Payment initiation timestamp |
| `completed_at` | string/null (ISO 8601) | Payment completion timestamp |

**Device Object Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Device ID |
| `mac_address` | string | Device MAC address |
| `device_name` | string | Human-readable device name |
| `is_active` | boolean | Whether device is currently active |
| `last_seen` | string (ISO 8601) | Last connection timestamp |
| `first_seen` | string (ISO 8601) | First registration timestamp |

**Access Log Object Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Log entry ID |
| `access_granted` | boolean | Whether access was granted |
| `denial_reason` | string | Reason for denial (empty if granted) |
| `ip_address` | string | IP address of connection attempt |
| `mac_address` | string | MAC address of device |
| `timestamp` | string (ISO 8601) | When the event occurred |

**Statistics Object Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `total_payments` | integer | Total number of completed payments |
| `total_spent` | number | Total amount spent (all time) |
| `device_count` | integer | Total registered devices |
| `active_devices` | integer | Currently active devices |

---

### TEST 3: Get Non-Existent User (Error Handling)

**Endpoint:** `GET /api/users/99999/`

**Request:**
```http
GET /api/users/99999/ HTTP/1.1
Host: 127.0.0.1:8000
X-Admin-Access: kitonga_admin_2025
Content-Type: application/json
```

**Response Status:** `404 Not Found`

**JSON Response:**
```json
{
  "success": false,
  "message": "User not found"
}
```

---

### TEST 4: Unauthorized Access (No Admin Token)

**Endpoint:** `GET /api/users/`

**Request:**
```http
GET /api/users/ HTTP/1.1
Host: 127.0.0.1:8000
Content-Type: application/json
```

**Response Status:** `403 Forbidden`

**JSON Response:**
```json
{
  "detail": "Authentication credentials were not provided."
}
```

---

## Frontend Integration Examples

### Example 1: Fetch All Users (JavaScript)

```javascript
async function fetchAllUsers() {
  try {
    const response = await fetch('http://127.0.0.1:8000/api/users/', {
      method: 'GET',
      headers: {
        'X-Admin-Access': 'kitonga_admin_2025',
        'Content-Type': 'application/json'
      }
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const users = await response.json();
    console.log(`Retrieved ${users.length} users`);
    
    // Display users in table
    users.forEach(user => {
      console.log(`
        ID: ${user.id}
        Phone: ${user.phone_number}
        Access: ${user.has_active_access ? 'Active' : 'Inactive'}
        Devices: ${user.device_count}
        Paid Until: ${user.paid_until || 'No active payment'}
      `);
    });
    
    return users;
  } catch (error) {
    console.error('Error fetching users:', error);
    throw error;
  }
}
```

### Example 2: Fetch Single User Detail (JavaScript)

```javascript
async function fetchUserDetail(userId) {
  try {
    const response = await fetch(`http://127.0.0.1:8000/api/users/${userId}/`, {
      method: 'GET',
      headers: {
        'X-Admin-Access': 'kitonga_admin_2025',
        'Content-Type': 'application/json'
      }
    });
    
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('User not found');
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    
    if (data.success) {
      const user = data.user;
      console.log('User Details:', {
        phone: user.phone_number,
        activeAccess: user.has_active_access,
        totalPayments: user.statistics.total_payments,
        totalSpent: user.statistics.total_spent,
        deviceCount: user.devices.length,
        recentPayments: user.payments.slice(0, 5)
      });
      
      return user;
    }
  } catch (error) {
    console.error('Error fetching user detail:', error);
    throw error;
  }
}
```

### Example 3: React Component Usage

```javascript
import React, { useState, useEffect } from 'react';

function UserList() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function loadUsers() {
      try {
        const response = await fetch('http://127.0.0.1:8000/api/users/', {
          headers: {
            'X-Admin-Access': 'kitonga_admin_2025',
            'Content-Type': 'application/json'
          }
        });
        
        if (!response.ok) {
          throw new Error('Failed to fetch users');
        }
        
        const data = await response.json();
        setUsers(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    
    loadUsers();
  }, []);

  if (loading) return <div>Loading users...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div>
      <h2>Users ({users.length})</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Phone Number</th>
            <th>Status</th>
            <th>Devices</th>
            <th>Paid Until</th>
          </tr>
        </thead>
        <tbody>
          {users.map(user => (
            <tr key={user.id}>
              <td>{user.id}</td>
              <td>{user.phone_number}</td>
              <td>
                <span className={user.has_active_access ? 'active' : 'inactive'}>
                  {user.has_active_access ? '🟢 Active' : '🔴 Inactive'}
                </span>
              </td>
              <td>{user.device_count}</td>
              <td>{user.paid_until ? new Date(user.paid_until).toLocaleString() : 'N/A'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

### Example 4: Python Client

```python
import requests

class KitongaUserAPI:
    def __init__(self, base_url, admin_token):
        self.base_url = base_url
        self.headers = {
            'X-Admin-Access': admin_token,
            'Content-Type': 'application/json'
        }
    
    def get_all_users(self):
        """Fetch all users"""
        response = requests.get(
            f'{self.base_url}/users/',
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def get_user_detail(self, user_id):
        """Fetch detailed information for a specific user"""
        response = requests.get(
            f'{self.base_url}/users/{user_id}/',
            headers=self.headers
        )
        response.raise_for_status()
        data = response.json()
        return data.get('user') if data.get('success') else None
    
    def get_active_users(self):
        """Get list of users with active access"""
        all_users = self.get_all_users()
        return [u for u in all_users if u.get('has_active_access')]

# Usage
api = KitongaUserAPI('http://127.0.0.1:8000/api', 'kitonga_admin_2025')

# Get all users
users = api.get_all_users()
print(f"Total users: {len(users)}")

# Get specific user
user = api.get_user_detail(20)
if user:
    print(f"User: {user['phone_number']}")
    print(f"Total spent: {user['statistics']['total_spent']}")

# Get active users only
active_users = api.get_active_users()
print(f"Active users: {len(active_users)}")
```

---

## Summary Statistics

**Test Execution Summary:**
- ✅ **List Users:** Passed - Retrieved 17 users successfully
- ✅ **Get User Detail:** Passed - Retrieved full user details including payments, devices, and access logs
- ✅ **Error Handling:** Passed - Returns proper 404 for non-existent users
- ✅ **Authentication:** Passed - Blocks unauthorized access with 403 Forbidden

**Overall Result:** 🎉 **4/4 Tests Passed (100%)**

---

## Notes

1. **Authentication Required:** All endpoints require the `X-Admin-Access` header with valid admin token
2. **Response Format:** 
   - List endpoint returns array directly
   - Detail endpoint returns object with `success` flag and nested `user` object
3. **Date Format:** All timestamps use ISO 8601 format (e.g., `2025-11-13T11:57:40.415066+00:00`)
4. **Pagination:** Not implemented in current version (returns all users)
5. **Error Responses:** Consistent error format with descriptive messages

---

## Related Documentation

- See `ADMIN_API_REFERENCE.md` for complete API documentation
- See `FRONTEND_API_GUIDE.md` for frontend integration examples
- See `API_TESTING_GUIDE.md` for testing procedures
