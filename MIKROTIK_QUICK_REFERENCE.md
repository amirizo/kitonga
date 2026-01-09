# MikroTik Admin Management - Quick Reference

## Current Problem & Solution

| Aspect | Current | Proposed |
|--------|---------|----------|
| Config Storage | Environment variables | Database |
| Routers Supported | 1 (hardcoded) | Multiple per tenant |
| Tenants Supported | 1 (platform-wide) | All tenants isolated |
| Self-Service | ❌ | ✅ |
| Audit Trail | ❌ | ✅ |
| Encrypted Passwords | ❌ | ✅ |
| Multi-Tenant Safe | ❌ | ✅ |
| Admin Control | Limited | Fine-grained |

---

## New Database Models

### Router (Enhanced)
```python
Router
├── Identification
│   ├── tenant (ForeignKey to Tenant)
│   ├── name (CharField)
│   ├── description (TextField)
│   └── location (ForeignKey to Location, optional)
├── Connection Settings
│   ├── host (CharField - IP/hostname)
│   ├── port (Integer, default: 8728)
│   ├── username (CharField)
│   ├── password (EncryptedCharField) ⭐ NEW
│   └── use_ssl (BooleanField)
├── Router Information
│   ├── router_model (CharField)
│   ├── router_version (CharField)
│   └── router_identity (CharField)
├── Hotspot Settings
│   ├── hotspot_interface (CharField, default: bridge)
│   └── hotspot_profile (CharField, default: default)
├── Status Monitoring
│   ├── status (choices: online/offline/configuring/error)
│   ├── last_seen (DateTime)
│   ├── last_error (TextField)
│   └── is_active (BooleanField)
└── Admin Management ⭐ NEW
    ├── created_by (ForeignKey to User)
    ├── last_configured_by (ForeignKey to User)
    ├── last_configured_at (DateTime)
    ├── config_version (Integer, starts at 1)
    └── admin_notes (TextField)
```

### RouterConfigurationLog (NEW)
```python
RouterConfigurationLog
├── Identification
│   ├── id (PrimaryKey)
│   └── router (ForeignKey to Router)
├── Change Details
│   ├── change_type (choices: credentials/interface/profile/status/other)
│   ├── old_value (JSONField)
│   ├── new_value (JSONField)
│   └── description (TextField)
├── Audit Information
│   ├── changed_by (ForeignKey to User)
│   ├── timestamp (DateTime, auto_now_add)
│   ├── ip_address (CharField)
│   └── user_agent (TextField)
```

---

## New API Endpoints

### 1. List Routers
```
GET /billing/admin/routers/
Authorization: Token <admin_token>

Query Parameters:
  - page: int (default: 1)
  - page_size: int (default: 10)

Response:
{
  "success": bool,
  "routers": [
    {
      "id": int,
      "tenant": str,
      "name": str,
      "host": str,
      "port": int,
      "status": str,
      "last_seen": datetime,
      "created_by": str,
      "config_version": int,
      "is_active": bool
    }
  ],
  "pagination": {
    "total": int,
    "page": int,
    "page_size": int,
    "total_pages": int
  },
  "filter_type": str  # "all_routers" or "tenant_<slug>"
}
```

### 2. Create Router
```
POST /billing/admin/routers/create/
Authorization: Token <admin_token>
Content-Type: application/json

Request Body:
{
  "tenant": str,           # Required
  "name": str,             # Required
  "host": str,             # Required (IP address)
  "port": int,             # Optional (default: 8728)
  "username": str,         # Required
  "password": str,         # Required
  "use_ssl": bool,         # Optional (default: false)
  "hotspot_interface": str,# Optional (default: bridge)
  "hotspot_profile": str,  # Optional (default: default)
  "description": str,      # Optional
  "is_active": bool        # Optional (default: true)
}

Response:
{
  "success": bool,
  "message": str,
  "router": {
    "id": int,
    "tenant": str,
    "name": str,
    "host": str,
    "port": int,
    "status": str,
    "router_model": str,
    "router_version": str,
    "created_by": str,
    "created_at": datetime
  }
}

Status Codes:
  201 Created     - Router created successfully
  400 Bad Request - Validation error or connection test failed
  403 Forbidden   - Not authorized for this tenant
  404 Not Found   - Tenant not found
  500 Error       - Server error
```

### 3. Update Router
```
PUT /billing/admin/routers/<router_id>/
Authorization: Token <admin_token>
Content-Type: application/json

Request Body (all optional):
{
  "name": str,
  "description": str,
  "host": str,             # Tests connection on update
  "port": int,
  "username": str,
  "password": str,
  "hotspot_interface": str,
  "hotspot_profile": str,
  "admin_notes": str,
  "is_active": bool
}

Response:
{
  "success": bool,
  "message": str,
  "router": { ... },       # Full router object
  "changed_fields": [str], # List of fields that changed
  "new_config_version": int
}

Status Codes:
  200 OK          - Router updated successfully
  400 Bad Request - Validation error or connection test failed
  403 Forbidden   - Not authorized for this router
  404 Not Found   - Router not found
  500 Error       - Server error
```

### 4. View Configuration History
```
GET /billing/admin/routers/<router_id>/history/
Authorization: Token <admin_token>

Query Parameters:
  - page: int (default: 1)
  - page_size: int (default: 20)

Response:
{
  "success": bool,
  "router": {
    "id": int,
    "name": str,
    "tenant": str,
    "config_version": int
  },
  "history": [
    {
      "id": int,
      "change_type": str,        # credentials/interface/profile/status/other
      "changed_by": str,         # Username
      "description": str,
      "old_value": object,       # JSON of old values
      "new_value": object,       # JSON of new values
      "timestamp": datetime,
      "ip_address": str
    }
  ],
  "pagination": {
    "total": int,
    "page": int,
    "page_size": int,
    "total_pages": int
  }
}

Status Codes:
  200 OK        - History retrieved successfully
  403 Forbidden - Not authorized for this router
  404 Not found - Router not found
  500 Error     - Server error
```

---

## Access Control Matrix

```
ACTION                 | SuperAdmin | TenantAdmin | User
-----------------------|-----------|-----------|-------
List all routers       |    ✅     |     ❌     |  ❌
List own routers       |    ✅     |     ✅     |  ❌
Create router          |    ✅     |  ✅ own    |  ❌
Edit router            |    ✅     |  ✅ own    |  ❌
Delete router          |    ✅     |     ❌     |  ❌
View config history    |    ✅     |  ✅ own    |  ❌
View other tenant data |    ✅     |     ❌     |  ❌
```

---

## Code Examples

### List Routers (Super Admin - All Routers)
```bash
curl -X GET "http://localhost:8000/billing/admin/routers/" \
  -H "Authorization: Token abc123def456"

# Response: All routers from all tenants
{
  "success": true,
  "routers": [
    {"id": 1, "tenant": "downtown", "name": "Main", "status": "online"},
    {"id": 2, "tenant": "airport", "name": "Terminal 1", "status": "online"},
    {"id": 3, "tenant": "airport", "name": "Terminal 2", "status": "offline"}
  ],
  "filter_type": "all_routers",
  "total": 3
}
```

### List Routers (Tenant Admin - Own Routers Only)
```bash
curl -X GET "http://localhost:8000/billing/admin/routers/" \
  -H "Authorization: Token xyz789"

# Response: Only this tenant's routers
{
  "success": true,
  "routers": [
    {"id": 1, "tenant": "downtown", "name": "Main", "status": "online"}
  ],
  "filter_type": "tenant_downtown",
  "total": 1
}
```

### Create Router
```bash
curl -X POST "http://localhost:8000/billing/admin/routers/create/" \
  -H "Authorization: Token abc123def456" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant": "downtown",
    "name": "Backup Router",
    "host": "192.168.1.3",
    "port": 8728,
    "username": "admin",
    "password": "secure_password",
    "hotspot_profile": "premium",
    "description": "Backup access point"
  }'

# Response:
{
  "success": true,
  "message": "Router created successfully",
  "router": {
    "id": 4,
    "tenant": "downtown",
    "name": "Backup Router",
    "host": "192.168.1.3",
    "status": "online",
    "router_model": "hEX PoE",
    "router_version": "7.10.1",
    "created_by": "admin",
    "created_at": "2026-01-10T15:30:00Z"
  }
}
```

### Update Router
```bash
curl -X PUT "http://localhost:8000/billing/admin/routers/1/" \
  -H "Authorization: Token abc123def456" \
  -H "Content-Type: application/json" \
  -d '{
    "hotspot_profile": "premium",
    "admin_notes": "Updated for premium users - Jan 10, 2026"
  }'

# Response:
{
  "success": true,
  "message": "Router updated successfully",
  "router": { ... },
  "changed_fields": ["hotspot_profile", "admin_notes"],
  "new_config_version": 3
}
```

### View History
```bash
curl -X GET "http://localhost:8000/billing/admin/routers/1/history/" \
  -H "Authorization: Token abc123def456"

# Response:
{
  "success": true,
  "router": {
    "id": 1,
    "name": "Main Router",
    "tenant": "downtown",
    "config_version": 3
  },
  "history": [
    {
      "id": 3,
      "change_type": "other",
      "changed_by": "admin",
      "description": "Updated: hotspot_profile, admin_notes",
      "old_value": {"hotspot_profile": "default", "admin_notes": ""},
      "new_value": {"hotspot_profile": "premium", "admin_notes": "Updated for premium users"},
      "timestamp": "2026-01-10T15:45:00Z",
      "ip_address": "192.168.1.100"
    },
    {
      "id": 2,
      "change_type": "credentials",
      "changed_by": "admin",
      "description": "Updated: username",
      "old_value": {"username": "guest"},
      "new_value": {"username": "admin"},
      "timestamp": "2026-01-10T10:20:00Z",
      "ip_address": "192.168.1.100"
    },
    {
      "id": 1,
      "change_type": "other",
      "changed_by": "admin",
      "description": "Router created",
      "old_value": {},
      "new_value": {"host": "192.168.1.1", "port": 8728, "username": "admin"},
      "timestamp": "2025-12-01T10:00:00Z",
      "ip_address": "192.168.1.100"
    }
  ],
  "total": 3
}
```

---

## Error Responses

### 400 Bad Request - Missing Field
```json
{
  "success": false,
  "message": "username is required"
}
```

### 400 Bad Request - Invalid IP
```json
{
  "success": false,
  "message": "Invalid IP address format"
}
```

### 400 Bad Request - Connection Test Failed
```json
{
  "success": false,
  "message": "Connection test failed",
  "error": "Authentication failed: invalid credentials",
  "test_details": { ... }
}
```

### 403 Forbidden - Not Authorized
```json
{
  "success": false,
  "message": "Not authorized to modify this router"
}
```

### 404 Not Found - Router
```json
{
  "success": false,
  "message": "Router not found"
}
```

### 404 Not Found - Tenant
```json
{
  "success": false,
  "message": "Tenant \"invalid-slug\" not found"
}
```

### 500 Internal Server Error
```json
{
  "success": false,
  "message": "Error updating router: database connection failed"
}
```

---

## Environment Variables

Add to `.env`:
```bash
# Encryption key for password field
ENCRYPTION_KEY=your-random-secret-key-min-32-chars-long

# Database (already configured)
DATABASE_URL=sqlite:///db.sqlite3

# MikroTik defaults (can be overridden per router in database)
MIKROTIK_HOST=192.168.1.1
MIKROTIK_USER=admin
MIKROTIK_PASSWORD=your_password
MIKROTIK_PORT=8728
```

---

## Settings Configuration

Add to `settings.py`:
```python
# Encrypted model fields
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')

INSTALLED_APPS = [
    # ...
    'encrypted_model_fields',
    # ...
]
```

---

## Implementation Checklist

- [ ] Update Router model with new fields
- [ ] Create RouterConfigurationLog model
- [ ] Create and run migrations
- [ ] Create serializers
- [ ] Create permission classes
- [ ] Implement admin_list_routers endpoint
- [ ] Implement admin_create_router endpoint
- [ ] Implement admin_update_router endpoint
- [ ] Implement admin_router_config_history endpoint
- [ ] Update URL routes
- [ ] Update Django admin interface
- [ ] Write unit tests
- [ ] Write integration tests
- [ ] Deploy to staging
- [ ] Test with real routers
- [ ] Deploy to production
- [ ] Monitor and iterate

---

## Performance Considerations

- **Indexing**: Added indexes on (tenant, is_active) and (status)
- **Pagination**: Always use pagination for large result sets
- **Encryption**: Use efficient encryption (FernetEncryption by default)
- **Queries**: Use select_related() and prefetch_related() where applicable
- **Rate Limiting**: Implement on sensitive operations

---

## Security Checklist

- [x] Passwords encrypted in database
- [x] Authorization checks on all endpoints
- [x] Audit logging of all changes
- [x] Connection validation before saving
- [x] Sensitive data not logged
- [x] IP address tracking
- [x] User attribution
- [ ] Rate limiting (to be added)
- [ ] HTTPS enforcement in production
- [ ] API key rotation strategy

---

## Support & Troubleshooting

**Question**: Why is connection test required?
**Answer**: To prevent invalid credentials from being saved. Saves debug time later.

**Question**: Can tenant admins delete routers?
**Answer**: No. Only super admins can delete. Tenant admins can deactivate (set is_active=false).

**Question**: How are passwords encrypted?
**Answer**: Using django-encrypted-model-fields with Fernet encryption (AES128).

**Question**: Can configuration changes be reverted?
**Answer**: Not automatically. But history shows old values. Manual revert is needed.

**Question**: What happens if a router goes offline?
**Answer**: Status changes to 'offline'. Admins see in last_seen timestamp.

---

## Documentation Files

1. **MIKROTIK_ADMIN_EXECUTIVE_SUMMARY.md** - This overview document
2. **MIKROTIK_ADMIN_MANAGEMENT_STRATEGY.md** - Architecture & detailed design
3. **MIKROTIK_BEFORE_AFTER_COMPARISON.md** - Current vs proposed analysis
4. **MIKROTIK_IMPLEMENTATION_GUIDE.md** - Step-by-step code implementation
5. **This file** - Quick reference card

---

## Questions?

Refer to detailed documentation or implementation guide.
