# MikroTik Configuration and Management - Admin Strategy

## Overview
The MikroTik management endpoints currently exist at `/admin/mikrotik/*` but need proper **admin access control, database persistence, and multi-tenant support**. This document outlines how to implement professional admin management.

---

## Current Issues

### 1. **No Database Persistence**
- Configuration is read from Django settings (environment variables)
- No way to update router credentials through API
- No audit trail of configuration changes

### 2. **Hardcoded Settings**
```python
# Current approach - READ ONLY
router_ip = getattr(django_settings, 'MIKROTIK_HOST', '')
username = getattr(django_settings, 'MIKROTIK_USER', '')
password = getattr(django_settings, 'MIKROTIK_PASSWORD', '')
```

### 3. **No Multi-Tenancy**
- Platform-wide router settings only
- But `Router` model already exists with `tenant` ForeignKey!
- Admin endpoints ignore existing Router database model

### 4. **No Admin Authorization Control**
```python
@permission_classes([SimpleAdminTokenPermission])  # Generic admin check
```
Should differentiate:
- **Super Admin**: Manage all routers (platform-wide)
- **Tenant Admin**: Manage only their routers

### 5. **No Audit Logging**
- No record of who changed what router settings
- No history of configuration changes

---

## Proposed Solution

### Architecture: 3-Tier Admin Management

```
┌─────────────────────────────────────────┐
│       SUPER ADMIN (Platform)            │
│  • View all routers (all tenants)       │
│  • Create/Delete routers                │
│  • Manage router credentials            │
│  • Monitor all tenants' usage           │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│    TENANT ADMIN (Business Owner)        │
│  • View own routers only                │
│  • Configure router settings            │
│  • Monitor own users & bandwidth        │
│  • Cannot access other tenant's data    │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│      ROUTER API (Real-time)             │
│  • Get active users                     │
│  • Disconnect user                      │
│  • Monitor bandwidth                    │
│  • Reboot/Configure                     │
└─────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Enhanced Router Model & Admin Class

#### 1. Update `Router` Model (models.py)
Add audit tracking:

```python
class Router(models.Model):
    # ...existing fields...
    
    # NEW FIELDS FOR ADMIN MANAGEMENT
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='routers_created'
    )
    last_configured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='routers_configured'
    )
    last_configured_at = models.DateTimeField(null=True, blank=True)
    
    # Configuration versioning
    config_version = models.IntegerField(default=1)
    previous_config = models.JSONField(null=True, blank=True)  # Store backup
    
    # Admin notes
    admin_notes = models.TextField(blank=True)
    
    # Encryption for sensitive fields (use django-encrypted-model-fields)
    password = EncryptedCharField(max_length=255)  # Encrypted
```

#### 2. Create `RouterConfigurationLog` Model
Track all configuration changes:

```python
class RouterConfigurationLog(models.Model):
    """Audit trail for router configuration changes"""
    router = models.ForeignKey(Router, on_delete=models.CASCADE, related_name='config_logs')
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    CHANGE_TYPES = [
        ('credentials', 'Credentials Changed'),
        ('interface', 'Interface Changed'),
        ('profile', 'Profile Changed'),
        ('status', 'Status Changed'),
        ('other', 'Other'),
    ]
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPES)
    
    old_value = models.JSONField()
    new_value = models.JSONField()
    
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.CharField(max_length=45)  # IPv4 or IPv6
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.router} - {self.change_type} by {self.changed_by} on {self.timestamp}"
```

---

### Phase 2: Admin Endpoints with Authorization

#### A. NEW ENDPOINT: List Routers
```python
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_list_routers(request):
    """
    List routers - filtered by user role
    Super Admin: All routers
    Tenant Admin: Only their tenant's routers
    """
    if request.user.is_superuser:
        # Super admin sees all routers
        routers = Router.objects.all()
        filter_type = 'all_routers'
    else:
        # Tenant admin sees only their routers
        try:
            tenant = Tenant.objects.get(admin_user=request.user)
            routers = Router.objects.filter(tenant=tenant)
            filter_type = f'tenant_{tenant.slug}'
        except Tenant.DoesNotExist:
            return Response({
                'success': False,
                'message': 'User is not associated with any tenant'
            }, status=status.HTTP_403_FORBIDDEN)
    
    # Pagination
    page = request.query_params.get('page', 1)
    page_size = request.query_params.get('page_size', 10)
    paginator = Paginator(routers, page_size)
    routers = paginator.get_page(page)
    
    routers_data = []
    for router in routers:
        routers_data.append({
            'id': router.id,
            'tenant': router.tenant.slug,
            'name': router.name,
            'description': router.description,
            'host': router.host,
            'port': router.port,
            'status': router.status,
            'last_seen': router.last_seen.isoformat() if router.last_seen else None,
            'router_model': router.router_model,
            'router_version': router.router_version,
            'is_active': router.is_active,
            'created_at': router.created_at.isoformat(),
            'last_configured_at': router.last_configured_at.isoformat() if router.last_configured_at else None,
            'created_by': router.created_by.username if router.created_by else None,
        })
    
    return Response({
        'success': True,
        'routers': routers_data,
        'total': paginator.count,
        'page': page,
        'page_size': page_size,
        'filter_type': filter_type
    })
```

#### B. NEW ENDPOINT: Create Router
```python
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_create_router(request):
    """
    Create new router configuration
    Super Admin: Can create for any tenant
    Tenant Admin: Can only create for own tenant
    """
    try:
        # Authorization check
        tenant_slug = request.data.get('tenant')
        if not request.user.is_superuser:
            try:
                user_tenant = Tenant.objects.get(admin_user=request.user)
                if user_tenant.slug != tenant_slug:
                    return Response({
                        'success': False,
                        'message': 'Not authorized to create routers for this tenant'
                    }, status=status.HTTP_403_FORBIDDEN)
            except Tenant.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'User is not associated with any tenant'
                }, status=status.HTTP_403_FORBIDDEN)
        
        # Validate tenant
        try:
            tenant = Tenant.objects.get(slug=tenant_slug)
        except Tenant.DoesNotExist:
            return Response({
                'success': False,
                'message': f'Tenant "{tenant_slug}" not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Validate required fields
        required = ['name', 'host', 'username', 'password']
        missing = [f for f in required if not request.data.get(f)]
        if missing:
            return Response({
                'success': False,
                'message': f'Missing required fields: {", ".join(missing)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate IP format
        try:
            ipaddress.ip_address(request.data['host'])
        except ValueError:
            return Response({
                'success': False,
                'message': 'Invalid IP address format'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Test connection BEFORE saving
        from .mikrotik import test_mikrotik_connection
        test_result = test_mikrotik_connection(
            host=request.data['host'],
            username=request.data['username'],
            password=request.data['password'],
            port=request.data.get('port', 8728)
        )
        
        if not test_result['success']:
            return Response({
                'success': False,
                'message': f'Connection test failed: {test_result.get("error", "Unknown error")}',
                'test_error': test_result.get('error')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create router
        router = Router.objects.create(
            tenant=tenant,
            name=request.data['name'],
            description=request.data.get('description', ''),
            host=request.data['host'],
            port=request.data.get('port', 8728),
            username=request.data['username'],
            password=request.data['password'],
            use_ssl=request.data.get('use_ssl', False),
            hotspot_interface=request.data.get('hotspot_interface', 'bridge'),
            hotspot_profile=request.data.get('hotspot_profile', 'default'),
            is_active=request.data.get('is_active', True),
            created_by=request.user,
            last_configured_by=request.user,
            last_configured_at=timezone.now(),
            router_model=test_result.get('router_info', {}).get('model', ''),
            router_version=test_result.get('router_info', {}).get('version', ''),
            router_identity=test_result.get('router_info', {}).get('identity', ''),
            status='online',
            last_seen=timezone.now()
        )
        
        # Create first config log
        RouterConfigurationLog.objects.create(
            router=router,
            changed_by=request.user,
            change_type='other',
            old_value={},
            new_value={
                'host': router.host,
                'username': router.username,
                'port': router.port,
            },
            description='Router created',
            ip_address=get_request_info(request)['ip_address']
        )
        
        return Response({
            'success': True,
            'message': 'Router created successfully',
            'router': {
                'id': router.id,
                'tenant': router.tenant.slug,
                'name': router.name,
                'status': router.status
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f'Error creating router: {str(e)}')
        return Response({
            'success': False,
            'message': f'Error creating router: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

#### C. UPDATE ENDPOINT: Modify Router Configuration
```python
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def admin_update_router(request, router_id):
    """
    Update router configuration with audit logging
    """
    try:
        router = Router.objects.get(id=router_id)
        
        # Authorization check
        if not request.user.is_superuser and router.tenant.admin_user != request.user:
            return Response({
                'success': False,
                'message': 'Not authorized to modify this router'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Track old values for audit log
        old_values = {
            'host': router.host,
            'port': router.port,
            'username': router.username,
            'hotspot_interface': router.hotspot_interface,
            'hotspot_profile': router.hotspot_profile,
        }
        
        # Update fields
        if 'name' in request.data:
            router.name = request.data['name']
        if 'description' in request.data:
            router.description = request.data['description']
        if 'host' in request.data:
            router.host = request.data['host']
            # Validate IP
            try:
                ipaddress.ip_address(request.data['host'])
            except ValueError:
                return Response({
                    'success': False,
                    'message': 'Invalid IP address'
                }, status=status.HTTP_400_BAD_REQUEST)
        if 'port' in request.data:
            router.port = request.data['port']
        if 'username' in request.data:
            router.username = request.data['username']
        if 'password' in request.data:
            router.password = request.data['password']
        if 'hotspot_interface' in request.data:
            router.hotspot_interface = request.data['hotspot_interface']
        if 'hotspot_profile' in request.data:
            router.hotspot_profile = request.data['hotspot_profile']
        if 'is_active' in request.data:
            router.is_active = request.data['is_active']
        if 'admin_notes' in request.data:
            router.admin_notes = request.data['admin_notes']
        
        # Test connection if credentials changed
        if 'host' in request.data or 'username' in request.data or 'password' in request.data:
            from .mikrotik import test_mikrotik_connection
            test_result = test_mikrotik_connection(
                host=router.host,
                username=router.username,
                password=router.password,
                port=router.port
            )
            
            if not test_result['success']:
                return Response({
                    'success': False,
                    'message': f'Connection test failed: {test_result.get("error")}',
                    'test_error': test_result.get('error')
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Update router info from connection test
            router.router_model = test_result.get('router_info', {}).get('model', '')
            router.router_version = test_result.get('router_info', {}).get('version', '')
            router.router_identity = test_result.get('router_info', {}).get('identity', '')
            router.status = 'online'
            router.last_seen = timezone.now()
        
        # Save and log
        router.last_configured_by = request.user
        router.last_configured_at = timezone.now()
        router.config_version += 1
        router.save()
        
        # Create audit log
        new_values = {
            'host': router.host,
            'port': router.port,
            'username': router.username,
            'hotspot_interface': router.hotspot_interface,
            'hotspot_profile': router.hotspot_profile,
        }
        
        changed_fields = [k for k in old_values if old_values[k] != new_values[k]]
        
        if changed_fields:
            RouterConfigurationLog.objects.create(
                router=router,
                changed_by=request.user,
                change_type='credentials' if 'username' in changed_fields or 'password' in changed_fields else 'other',
                old_value={k: old_values[k] for k in changed_fields},
                new_value={k: new_values[k] for k in changed_fields},
                description=f'Updated: {", ".join(changed_fields)}',
                ip_address=get_request_info(request)['ip_address']
            )
        
        return Response({
            'success': True,
            'message': 'Router updated successfully',
            'router': {
                'id': router.id,
                'name': router.name,
                'status': router.status,
                'config_version': router.config_version,
                'changed_fields': changed_fields
            }
        })
        
    except Router.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Router not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Error updating router: {str(e)}')
        return Response({
            'success': False,
            'message': f'Error updating router: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

#### D. NEW ENDPOINT: View Configuration History
```python
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_router_config_history(request, router_id):
    """
    View router configuration change history
    """
    try:
        router = Router.objects.get(id=router_id)
        
        # Authorization check
        if not request.user.is_superuser and router.tenant.admin_user != request.user:
            return Response({
                'success': False,
                'message': 'Not authorized to view this router'
            }, status=status.HTTP_403_FORBIDDEN)
        
        logs = RouterConfigurationLog.objects.filter(router=router).order_by('-timestamp')
        
        logs_data = []
        for log in logs:
            logs_data.append({
                'id': log.id,
                'change_type': log.change_type,
                'changed_by': log.changed_by.username,
                'description': log.description,
                'old_value': log.old_value,
                'new_value': log.new_value,
                'timestamp': log.timestamp.isoformat(),
                'ip_address': log.ip_address
            })
        
        return Response({
            'success': True,
            'router': {
                'id': router.id,
                'name': router.name,
                'config_version': router.config_version
            },
            'history': logs_data,
            'total': len(logs_data)
        })
        
    except Router.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Router not found'
        }, status=status.HTTP_404_NOT_FOUND)
```

---

### Phase 3: Updated URL Routes

```python
# Admin MikroTik Management (NEW)
path('admin/routers/', views.admin_list_routers, name='admin_list_routers'),
path('admin/routers/create/', views.admin_create_router, name='admin_create_router'),
path('admin/routers/<int:router_id>/', views.admin_update_router, name='admin_update_router'),
path('admin/routers/<int:router_id>/history/', views.admin_router_config_history, name='admin_router_config_history'),

# MikroTik Configuration (OLD - TO BE DEPRECATED)
path('admin/mikrotik/config/', views.mikrotik_configuration, name='mikrotik_configuration'),
path('admin/mikrotik/test-connection/', views.test_mikrotik_connection, name='test_mikrotik_connection'),
path('admin/mikrotik/router-info/', views.mikrotik_router_info, name='mikrotik_router_info'),
path('admin/mikrotik/active-users/', views.mikrotik_active_users, name='mikrotik_active_users'),
path('admin/mikrotik/disconnect-user/', views.mikrotik_disconnect_user, name='mikrotik_disconnect_user'),
path('admin/mikrotik/disconnect-all/', views.mikrotik_disconnect_all_users, name='mikrotik_disconnect_all_users'),
```

---

## API Usage Examples

### 1. List All Routers (Super Admin)
```bash
curl -X GET http://localhost:8000/billing/admin/routers/ \
  -H "Authorization: Token <super_admin_token>"

# Response
{
  "success": true,
  "routers": [
    {
      "id": 1,
      "tenant": "downtown",
      "name": "Main Router",
      "host": "192.168.1.1",
      "status": "online",
      "last_seen": "2026-01-10T14:30:00Z",
      "created_by": "admin"
    },
    {
      "id": 2,
      "tenant": "airport",
      "name": "Terminal 1",
      "host": "192.168.1.2",
      "status": "online",
      "created_by": "admin"
    }
  ],
  "filter_type": "all_routers",
  "total": 2
}
```

### 2. List Routers (Tenant Admin - Auto-filtered)
```bash
curl -X GET http://localhost:8000/billing/admin/routers/ \
  -H "Authorization: Token <tenant_admin_token>"

# Response - Only tenant's routers shown
{
  "success": true,
  "routers": [
    {
      "id": 1,
      "tenant": "downtown",
      "name": "Main Router",
      "status": "online"
    }
  ],
  "filter_type": "tenant_downtown",
  "total": 1
}
```

### 3. Create New Router
```bash
curl -X POST http://localhost:8000/billing/admin/routers/create/ \
  -H "Authorization: Token <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant": "downtown",
    "name": "Backup Router",
    "host": "192.168.1.3",
    "port": 8728,
    "username": "admin",
    "password": "secure_password",
    "hotspot_interface": "bridge",
    "hotspot_profile": "default"
  }'

# Response
{
  "success": true,
  "message": "Router created successfully",
  "router": {
    "id": 3,
    "tenant": "downtown",
    "name": "Backup Router",
    "status": "online"
  }
}
```

### 4. Update Router Configuration
```bash
curl -X PUT http://localhost:8000/billing/admin/routers/1/ \
  -H "Authorization: Token <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "hotspot_profile": "premium",
    "admin_notes": "Updated profile for premium users"
  }'

# Response
{
  "success": true,
  "message": "Router updated successfully",
  "router": {
    "id": 1,
    "name": "Main Router",
    "status": "online",
    "config_version": 3,
    "changed_fields": ["hotspot_profile"]
  }
}
```

### 5. View Configuration History
```bash
curl -X GET http://localhost:8000/billing/admin/routers/1/history/ \
  -H "Authorization: Token <admin_token>"

# Response
{
  "success": true,
  "router": {
    "id": 1,
    "name": "Main Router",
    "config_version": 3
  },
  "history": [
    {
      "id": 5,
      "change_type": "other",
      "changed_by": "admin",
      "description": "Updated: hotspot_profile",
      "old_value": {"hotspot_profile": "default"},
      "new_value": {"hotspot_profile": "premium"},
      "timestamp": "2026-01-10T14:45:00Z",
      "ip_address": "192.168.1.100"
    }
  ],
  "total": 1
}
```

---

## Security Considerations

1. **Encryption**: Use `django-encrypted-model-fields` for password storage
2. **Rate Limiting**: Apply rate limits to sensitive operations (disconnect-all, reboot)
3. **Audit Trail**: Every configuration change logged with user, timestamp, IP
4. **Authorization**: Two-level access control (Super Admin vs Tenant Admin)
5. **Connection Testing**: Always test before saving credentials
6. **HTTPS**: Require SSL in production
7. **Token Expiration**: Implement token rotation for long-lived sessions

---

## Benefits of This Approach

✅ **Professional Grade**: Proper authorization and audit logging
✅ **Multi-Tenant Safe**: Tenants can't access each other's routers
✅ **Scalable**: Support multiple routers per tenant
✅ **Traceable**: Full history of who changed what and when
✅ **Reliable**: Connection testing before credential updates
✅ **Backward Compatible**: Can deprecate old endpoints gradually

---

## Migration Path

### Step 1: Create migrations for new models
```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 2: Add new endpoints (Phase 1 & 2)
- Deploy new endpoints alongside old ones
- Update frontend to use new endpoints

### Step 3: Deprecate old endpoints (after 1-2 months)
- Remove old endpoints from production
- Old endpoints return 410 Gone with migration guide

### Step 4: Database cleanup
- Archive old configuration data
- Delete unused fields
