# MikroTik Admin Management - Step-by-Step Implementation

## Step 1: Update Models (models.py)

### 1.1 Install Encryption Package
```bash
pip install django-encrypted-model-fields
```

### 1.2 Add Imports to models.py
```python
from encrypted_model_fields.fields import EncryptedCharField
from django.utils import timezone
from django.contrib.auth import get_user_model
```

### 1.3 Update Router Model
```python
class Router(models.Model):
    """
    MikroTik router configuration per tenant
    Each tenant can have multiple routers
    """
    STATUS_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('configuring', 'Configuring'),
        ('error', 'Error'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='routers')
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='routers')
    
    # Router identification
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Connection settings
    host = models.CharField(max_length=255)  # IP or hostname
    port = models.IntegerField(default=8728)
    username = models.CharField(max_length=100)
    password = EncryptedCharField(max_length=255)  # Encrypted
    use_ssl = models.BooleanField(default=False)
    
    # Router info (populated from router)
    router_model = models.CharField(max_length=100, blank=True)
    router_version = models.CharField(max_length=50, blank=True)
    router_identity = models.CharField(max_length=100, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='configuring')
    last_seen = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    
    # Hotspot settings
    hotspot_interface = models.CharField(max_length=50, default='bridge')
    hotspot_profile = models.CharField(max_length=50, default='default')
    
    # Admin management fields (NEW)
    created_by = models.ForeignKey(
        get_user_model(), 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='routers_created'
    )
    last_configured_by = models.ForeignKey(
        get_user_model(), 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='routers_configured'
    )
    last_configured_at = models.DateTimeField(null=True, blank=True)
    config_version = models.IntegerField(default=1)
    admin_notes = models.TextField(blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['tenant', 'name']
        unique_together = ['tenant', 'name']
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.tenant.business_name} - {self.name} ({self.host})"
    
    def is_healthy(self):
        """Check if router is considered healthy"""
        if self.status == 'offline':
            return False
        if not self.last_seen:
            return False
        
        # Consider offline if not seen in 5 minutes
        delta = timezone.now() - self.last_seen
        return delta.total_seconds() < 300
```

### 1.4 Create RouterConfigurationLog Model
```python
class RouterConfigurationLog(models.Model):
    """
    Audit trail for router configuration changes
    """
    router = models.ForeignKey(Router, on_delete=models.CASCADE, related_name='config_logs')
    changed_by = models.ForeignKey(
        get_user_model(), 
        on_delete=models.SET_NULL, 
        null=True
    )
    
    CHANGE_TYPES = [
        ('credentials', 'Credentials Changed'),
        ('interface', 'Interface Changed'),
        ('profile', 'Profile Changed'),
        ('status', 'Status Changed'),
        ('other', 'Other'),
    ]
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPES)
    
    old_value = models.JSONField(default=dict, blank=True)
    new_value = models.JSONField(default=dict, blank=True)
    description = models.TextField()
    
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.CharField(max_length=45, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['router', '-timestamp']),
            models.Index(fields=['changed_by', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.router} - {self.change_type} by {self.changed_by} on {self.timestamp}"
```

---

## Step 2: Create Migrations

```bash
python manage.py makemigrations billing
python manage.py migrate billing
```

---

## Step 3: Create Serializers (serializers.py)

```python
from rest_framework import serializers
from .models import Router, RouterConfigurationLog

class RouterConfigurationLogSerializer(serializers.ModelSerializer):
    changed_by = serializers.CharField(source='changed_by.username', read_only=True)
    
    class Meta:
        model = RouterConfigurationLog
        fields = [
            'id', 'change_type', 'changed_by', 'description',
            'old_value', 'new_value', 'timestamp', 'ip_address'
        ]
        read_only_fields = fields

class RouterDetailSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source='created_by.username', read_only=True)
    last_configured_by = serializers.CharField(source='last_configured_by.username', read_only=True)
    tenant = serializers.CharField(source='tenant.slug', read_only=True)
    
    class Meta:
        model = Router
        fields = [
            'id', 'tenant', 'name', 'description', 'host', 'port',
            'username', 'use_ssl', 'status', 'last_seen', 'last_error',
            'router_model', 'router_version', 'router_identity',
            'hotspot_interface', 'hotspot_profile', 'is_active',
            'created_by', 'last_configured_by', 'last_configured_at',
            'config_version', 'admin_notes', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'created_by', 'last_configured_by', 'last_configured_at',
            'config_version', 'router_model', 'router_version',
            'router_identity', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'password': {'write_only': True}  # Never return password in response
        }

class RouterListSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source='created_by.username', read_only=True)
    tenant = serializers.CharField(source='tenant.slug', read_only=True)
    
    class Meta:
        model = Router
        fields = [
            'id', 'tenant', 'name', 'host', 'port', 'status',
            'last_seen', 'is_active', 'created_by', 'config_version'
        ]
        read_only_fields = fields
```

---

## Step 4: Create Permission Classes (permissions.py)

```python
from rest_framework import permissions

class CanManageRouter(permissions.BasePermission):
    """
    Custom permission to check if user can manage a router.
    - Super admin: can manage all routers
    - Tenant admin: can manage only their tenant's routers
    """
    
    def has_permission(self, request, view):
        # Must be authenticated
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Allow super admin
        if request.user.is_superuser:
            return True
        
        # For non-super admins, check if user is admin of the router's tenant
        try:
            tenant = Tenant.objects.get(admin_user=request.user)
            return obj.tenant == tenant
        except Tenant.DoesNotExist:
            return False
```

---

## Step 5: Create Views (views.py)

### 5.1 Helper Function
```python
def get_user_tenant(user):
    """Get the tenant associated with a user"""
    if user.is_superuser:
        return None  # Super admin, no single tenant
    
    try:
        return Tenant.objects.get(admin_user=user)
    except Tenant.DoesNotExist:
        return None
```

### 5.2 List Routers Endpoint
```python
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_list_routers(request):
    """
    List routers - filtered by user role.
    Super Admin: All routers
    Tenant Admin: Only their tenant's routers
    """
    try:
        if request.user.is_superuser:
            # Super admin sees all routers
            routers = Router.objects.select_related('tenant', 'created_by', 'last_configured_by').all()
            filter_type = 'all_routers'
        else:
            # Tenant admin sees only their routers
            user_tenant = get_user_tenant(request.user)
            if not user_tenant:
                return Response({
                    'success': False,
                    'message': 'User is not associated with any tenant'
                }, status=status.HTTP_403_FORBIDDEN)
            
            routers = Router.objects.select_related(
                'tenant', 'created_by', 'last_configured_by'
            ).filter(tenant=user_tenant)
            filter_type = f'tenant_{user_tenant.slug}'
        
        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        
        total = routers.count()
        start = (page - 1) * page_size
        end = start + page_size
        routers_page = routers[start:end]
        
        serializer = RouterListSerializer(routers_page, many=True)
        
        return Response({
            'success': True,
            'routers': serializer.data,
            'pagination': {
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': (total + page_size - 1) // page_size
            },
            'filter_type': filter_type
        })
        
    except Exception as e:
        logger.error(f'Error listing routers: {str(e)}')
        return Response({
            'success': False,
            'message': 'Error retrieving routers'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

### 5.3 Create Router Endpoint
```python
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_create_router(request):
    """
    Create new router configuration.
    Super Admin: Can create for any tenant
    Tenant Admin: Can only create for own tenant
    """
    try:
        # Get tenant
        tenant_slug = request.data.get('tenant')
        if not tenant_slug:
            return Response({
                'success': False,
                'message': 'Tenant slug is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            tenant = Tenant.objects.get(slug=tenant_slug)
        except Tenant.DoesNotExist:
            return Response({
                'success': False,
                'message': f'Tenant "{tenant_slug}" not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Authorization check
        if not request.user.is_superuser:
            user_tenant = get_user_tenant(request.user)
            if not user_tenant or user_tenant != tenant:
                return Response({
                    'success': False,
                    'message': 'Not authorized to create routers for this tenant'
                }, status=status.HTTP_403_FORBIDDEN)
        
        # Validate required fields
        required_fields = ['name', 'host', 'username', 'password']
        for field in required_fields:
            if not request.data.get(field):
                return Response({
                    'success': False,
                    'message': f'{field.capitalize()} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate IP format
        try:
            ipaddress.ip_address(request.data['host'])
        except ValueError:
            return Response({
                'success': False,
                'message': 'Invalid IP address format'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if router with same name already exists for this tenant
        if Router.objects.filter(tenant=tenant, name=request.data['name']).exists():
            return Response({
                'success': False,
                'message': f'Router with name "{request.data["name"]}" already exists for this tenant'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Test connection BEFORE saving
        from .mikrotik import test_mikrotik_connection
        test_result = test_mikrotik_connection(
            host=request.data['host'],
            username=request.data['username'],
            password=request.data['password'],
            port=int(request.data.get('port', 8728))
        )
        
        if not test_result['success']:
            return Response({
                'success': False,
                'message': f'Connection test failed',
                'error': test_result.get('error', 'Unknown error'),
                'test_details': test_result
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create router
        router = Router.objects.create(
            tenant=tenant,
            name=request.data['name'],
            description=request.data.get('description', ''),
            host=request.data['host'],
            port=int(request.data.get('port', 8728)),
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
                'port': router.port,
                'username': router.username,
                'hotspot_interface': router.hotspot_interface,
                'hotspot_profile': router.hotspot_profile,
            },
            description='Router created',
            ip_address=get_request_info(request)['ip_address'],
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        serializer = RouterDetailSerializer(router)
        return Response({
            'success': True,
            'message': 'Router created successfully',
            'router': serializer.data
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f'Error creating router: {str(e)}', exc_info=True)
        return Response({
            'success': False,
            'message': f'Error creating router: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

### 5.4 Update Router Endpoint
```python
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def admin_update_router(request, router_id):
    """
    Update router configuration with audit logging
    """
    try:
        router = Router.objects.get(id=router_id)
        
        # Authorization check
        if not request.user.is_superuser:
            user_tenant = get_user_tenant(request.user)
            if not user_tenant or router.tenant != user_tenant:
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
        
        # Update simple fields
        simple_fields = ['name', 'description', 'hotspot_interface', 'hotspot_profile', 'admin_notes', 'is_active']
        for field in simple_fields:
            if field in request.data:
                setattr(router, field, request.data[field])
        
        # Update connection fields with validation
        if 'host' in request.data:
            try:
                ipaddress.ip_address(request.data['host'])
                router.host = request.data['host']
            except ValueError:
                return Response({
                    'success': False,
                    'message': 'Invalid IP address format'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        if 'port' in request.data:
            router.port = int(request.data['port'])
        
        if 'username' in request.data:
            router.username = request.data['username']
        
        if 'password' in request.data:
            router.password = request.data['password']
        
        # Test connection if credentials changed
        if any(k in request.data for k in ['host', 'username', 'password', 'port']):
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
                    'message': f'Connection test failed',
                    'error': test_result.get('error', 'Unknown error')
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Update router info from connection test
            if 'router_info' in test_result:
                router.router_model = test_result['router_info'].get('model', '')
                router.router_version = test_result['router_info'].get('version', '')
                router.router_identity = test_result['router_info'].get('identity', '')
            
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
            change_type = 'credentials' if any(k in changed_fields for k in ['username', 'password']) else 'other'
            
            RouterConfigurationLog.objects.create(
                router=router,
                changed_by=request.user,
                change_type=change_type,
                old_value={k: old_values[k] for k in changed_fields},
                new_value={k: new_values[k] for k in changed_fields},
                description=f'Updated: {", ".join(changed_fields)}',
                ip_address=get_request_info(request)['ip_address'],
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
        
        serializer = RouterDetailSerializer(router)
        return Response({
            'success': True,
            'message': 'Router updated successfully',
            'router': serializer.data,
            'changed_fields': changed_fields,
            'new_config_version': router.config_version
        })
        
    except Router.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Router not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Error updating router: {str(e)}', exc_info=True)
        return Response({
            'success': False,
            'message': f'Error updating router: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

### 5.5 View Configuration History Endpoint
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
        if not request.user.is_superuser:
            user_tenant = get_user_tenant(request.user)
            if not user_tenant or router.tenant != user_tenant:
                return Response({
                    'success': False,
                    'message': 'Not authorized to view this router'
                }, status=status.HTTP_403_FORBIDDEN)
        
        # Get logs
        logs = RouterConfigurationLog.objects.filter(router=router).select_related('changed_by')
        
        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        total = logs.count()
        start = (page - 1) * page_size
        end = start + page_size
        logs_page = logs[start:end]
        
        serializer = RouterConfigurationLogSerializer(logs_page, many=True)
        
        return Response({
            'success': True,
            'router': {
                'id': router.id,
                'name': router.name,
                'tenant': router.tenant.slug,
                'config_version': router.config_version
            },
            'history': serializer.data,
            'pagination': {
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': (total + page_size - 1) // page_size
            }
        })
        
    except Router.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Router not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Error getting router history: {str(e)}')
        return Response({
            'success': False,
            'message': f'Error retrieving router history: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

---

## Step 6: Update URLs

Add to `urls.py`:

```python
# New Admin Router Management Endpoints
path('admin/routers/', views.admin_list_routers, name='admin_list_routers'),
path('admin/routers/create/', views.admin_create_router, name='admin_create_router'),
path('admin/routers/<int:router_id>/', views.admin_update_router, name='admin_update_router'),
path('admin/routers/<int:router_id>/history/', views.admin_router_config_history, name='admin_router_config_history'),
```

---

## Step 7: Update Admin Interface (admin.py)

```python
from django.contrib import admin
from .models import Router, RouterConfigurationLog

@admin.register(Router)
class RouterAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant', 'host', 'status', 'last_seen', 'is_active')
    list_filter = ('tenant', 'status', 'is_active', 'created_at')
    search_fields = ('name', 'host', 'router_identity')
    readonly_fields = (
        'router_model', 'router_version', 'router_identity',
        'created_by', 'last_configured_by', 'last_configured_at',
        'config_version', 'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'name', 'description')
        }),
        ('Connection Settings', {
            'fields': ('host', 'port', 'username', 'password', 'use_ssl')
        }),
        ('Router Information', {
            'fields': ('router_model', 'router_version', 'router_identity'),
            'classes': ('collapse',)
        }),
        ('Hotspot Configuration', {
            'fields': ('hotspot_interface', 'hotspot_profile')
        }),
        ('Status & Monitoring', {
            'fields': ('status', 'last_seen', 'last_error', 'is_active')
        }),
        ('Admin Information', {
            'fields': ('created_by', 'last_configured_by', 'last_configured_at', 'config_version', 'admin_notes'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

@admin.register(RouterConfigurationLog)
class RouterConfigurationLogAdmin(admin.ModelAdmin):
    list_display = ('router', 'change_type', 'changed_by', 'timestamp')
    list_filter = ('router', 'change_type', 'timestamp')
    search_fields = ('router__name', 'changed_by__username', 'description')
    readonly_fields = ('router', 'changed_by', 'change_type', 'old_value', 'new_value', 'description', 'timestamp', 'ip_address')
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False  # Prevent manual creation
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only super admin can delete
```

---

## Step 8: Run Tests

```bash
# Create test file: tests.py
python manage.py test billing.tests.RouterAdminTests

# Or run all tests
python manage.py test
```

---

## Step 9: Update Settings

In `settings.py`:

```python
# Encrypted model fields
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY', 'your-secret-key-here')

# Add to INSTALLED_APPS if not present
INSTALLED_APPS = [
    # ...
    'encrypted_model_fields',
    # ...
]
```

---

## Step 10: Deploy

```bash
# 1. Create migration
python manage.py makemigrations

# 2. Test migration locally
python manage.py migrate --plan

# 3. Apply migration
python manage.py migrate

# 4. Test new endpoints
pytest billing/tests/

# 5. Deploy to staging
git commit -am "Add MikroTik admin management endpoints"
git push origin feature/mikrotik-admin

# 6. After staging tests pass, merge to main and deploy to production
```

This completes the full implementation!
