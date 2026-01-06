"""
Tenant Portal Views for Kitonga Wi-Fi Billing System
Phase 3: Self-service dashboard, router wizard, analytics, and white-label customization
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.http import HttpResponse
from django.db.models import Sum, Count
from django.db import transaction
from django.contrib.auth.models import User as DjangoUser
import logging

from .models import (
    Tenant, Router, Location, TenantStaff, Bundle, User, Payment, Voucher
)
from .serializers import (
    RouterWizardSerializer, RouterConfigSerializer, HotspotAutoConfigSerializer,
    BrandingUpdateSerializer, CustomDomainSerializer, AnalyticsQuerySerializer,
    ExportRequestSerializer, TenantSettingsSerializer, StaffInviteSerializer,
    StaffUpdateSerializer, LocationSerializer, BundleSerializer, TenantStaffSerializer
)
from .permissions import TenantAPIKeyPermission
from .analytics import TenantAnalytics, ComparisonAnalytics, ExportManager
from .router_wizard import RouterWizard, RouterHealthChecker
from .branding import BrandingManager, ThemeGenerator, CaptivePortalGenerator

logger = logging.getLogger(__name__)


# =============================================================================
# TENANT DASHBOARD
# =============================================================================

@api_view(['GET'])
@permission_classes([TenantAPIKeyPermission])
def portal_dashboard(request):
    """
    Get comprehensive tenant dashboard data
    Includes overview stats, trends, and quick insights
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found. Use X-API-Key header.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    analytics = TenantAnalytics(tenant)
    
    try:
        dashboard_data = analytics.get_dashboard_summary()
        
        return Response({
            'success': True,
            'tenant': {
                'id': str(tenant.id),
                'slug': tenant.slug,
                'business_name': tenant.business_name,
                'subscription_status': tenant.subscription_status,
                'subscription_plan': tenant.subscription_plan.display_name if tenant.subscription_plan else None,
                'subscription_ends_at': tenant.subscription_ends_at.isoformat() if tenant.subscription_ends_at else None,
            },
            'dashboard': dashboard_data
        })
    except Exception as e:
        logger.error(f"Dashboard error for {tenant.slug}: {e}")
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([TenantAPIKeyPermission])
def portal_realtime_stats(request):
    """
    Get real-time statistics for live dashboard updates
    Lightweight endpoint for polling
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    analytics = TenantAnalytics(tenant)
    
    return Response({
        'success': True,
        'data': analytics.get_real_time_stats()
    })


@api_view(['GET'])
@permission_classes([TenantAPIKeyPermission])
def portal_comparison(request):
    """
    Get period comparison analytics (week over week, month over month)
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    comparison = ComparisonAnalytics(tenant)
    
    return Response({
        'success': True,
        'week_over_week': comparison.week_over_week(),
        'month_over_month': comparison.month_over_month()
    })


# =============================================================================
# ANALYTICS AND REPORTING
# =============================================================================

@api_view(['GET'])
@permission_classes([TenantAPIKeyPermission])
def portal_revenue_analytics(request):
    """
    Get detailed revenue analytics
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = AnalyticsQuerySerializer(data=request.query_params)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    analytics = TenantAnalytics(tenant)
    
    report = analytics.get_revenue_report(
        start_date=serializer.validated_data.get('start_date'),
        end_date=serializer.validated_data.get('end_date'),
        group_by=serializer.validated_data.get('group_by', 'day')
    )
    
    return Response({
        'success': True,
        'report': report
    })


@api_view(['GET'])
@permission_classes([TenantAPIKeyPermission])
def portal_user_analytics(request):
    """
    Get user analytics including retention and growth
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    analytics = TenantAnalytics(tenant)
    
    return Response({
        'success': True,
        'data': analytics.get_user_analytics()
    })


@api_view(['GET'])
@permission_classes([TenantAPIKeyPermission])
def portal_voucher_analytics(request):
    """
    Get voucher usage analytics
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    analytics = TenantAnalytics(tenant)
    
    return Response({
        'success': True,
        'data': analytics.get_voucher_analytics()
    })


@api_view(['POST'])
@permission_classes([TenantAPIKeyPermission])
def portal_export_data(request):
    """
    Export tenant data (payments, users, vouchers) as CSV
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = ExportRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    export_mgr = ExportManager(tenant)
    export_type = serializer.validated_data['export_type']
    
    try:
        if export_type == 'payments':
            csv_data = export_mgr.export_payments_csv(
                start_date=serializer.validated_data.get('start_date'),
                end_date=serializer.validated_data.get('end_date')
            )
            filename = f'{tenant.slug}_payments.csv'
        elif export_type == 'users':
            csv_data = export_mgr.export_users_csv()
            filename = f'{tenant.slug}_users.csv'
        elif export_type == 'vouchers':
            csv_data = export_mgr.export_vouchers_csv(
                batch_id=serializer.validated_data.get('batch_id')
            )
            filename = f'{tenant.slug}_vouchers.csv'
        else:
            return Response({
                'success': False,
                'message': 'Invalid export type'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        response = HttpResponse(csv_data, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        logger.error(f"Export error for {tenant.slug}: {e}")
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# ROUTER CONFIGURATION WIZARD
# =============================================================================

@api_view(['POST'])
@permission_classes([TenantAPIKeyPermission])
def portal_router_test_connection(request):
    """
    Test connection to a MikroTik router
    Step 1 of the router setup wizard
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = RouterWizardSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    wizard = RouterWizard(tenant)
    
    result = wizard.test_connection(
        host=serializer.validated_data['host'],
        port=serializer.validated_data.get('port', 8728),
        username=serializer.validated_data.get('username', 'admin'),
        password=serializer.validated_data.get('password', ''),
        use_ssl=serializer.validated_data.get('use_ssl', False)
    )
    
    return Response(result)


@api_view(['POST'])
@permission_classes([TenantAPIKeyPermission])
def portal_router_save_config(request):
    """
    Save router configuration
    Step 2 of the router setup wizard
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = RouterConfigSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    wizard = RouterWizard(tenant)
    
    success, message, router = wizard.save_router_config(
        name=serializer.validated_data['name'],
        host=serializer.validated_data['host'],
        port=serializer.validated_data.get('port', 8728),
        username=serializer.validated_data.get('username', 'admin'),
        password=serializer.validated_data.get('password', ''),
        use_ssl=serializer.validated_data.get('use_ssl', False),
        location_id=serializer.validated_data.get('location_id'),
        hotspot_interface=serializer.validated_data.get('hotspot_interface', 'bridge'),
        hotspot_profile=serializer.validated_data.get('hotspot_profile', 'default')
    )
    
    if success:
        return Response({
            'success': True,
            'message': message,
            'router': {
                'id': router.id,
                'name': router.name,
                'host': router.host,
                'status': router.status,
            }
        }, status=status.HTTP_201_CREATED)
    else:
        return Response({
            'success': False,
            'message': message
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([TenantAPIKeyPermission])
def portal_router_auto_configure(request):
    """
    Auto-configure hotspot on a router
    Step 3 of the router setup wizard (optional)
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = HotspotAutoConfigSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        router = Router.objects.get(
            id=serializer.validated_data['router_id'],
            tenant=tenant
        )
    except Router.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Router not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    wizard = RouterWizard(tenant, router)
    
    # First establish connection
    test_result = wizard.test_connection(
        host=router.host,
        port=router.port,
        username=router.username,
        password=router.password,
        use_ssl=router.use_ssl
    )
    
    if not test_result.get('success'):
        return Response({
            'success': False,
            'message': 'Could not connect to router',
            'error': test_result.get('error')
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Perform auto-configuration
    result = wizard.auto_configure_hotspot(
        interface=serializer.validated_data.get('interface', 'bridge'),
        server_name=serializer.validated_data.get('server_name', 'kitonga-hotspot'),
        profile_name=serializer.validated_data.get('profile_name', 'kitonga-profile')
    )
    
    return Response(result)


@api_view(['GET'])
@permission_classes([TenantAPIKeyPermission])
def portal_router_generate_html(request, router_id):
    """
    Generate custom hotspot HTML pages for a router
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        router = Router.objects.get(id=router_id, tenant=tenant)
    except Router.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Router not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    wizard = RouterWizard(tenant, router)
    result = wizard.upload_hotspot_html()
    
    return Response(result)


@api_view(['GET'])
@permission_classes([TenantAPIKeyPermission])
def portal_router_health(request):
    """
    Check health of all tenant routers
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    health_checker = RouterHealthChecker(tenant)
    
    return Response({
        'success': True,
        'summary': health_checker.get_summary(),
        'routers': health_checker.check_all_routers()
    })


# =============================================================================
# WHITE-LABEL CUSTOMIZATION
# =============================================================================

@api_view(['GET'])
@permission_classes([TenantAPIKeyPermission])
def portal_branding(request):
    """
    Get current tenant branding configuration
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    branding = BrandingManager(tenant)
    
    return Response({
        'success': True,
        'branding': branding.get_branding()
    })


@api_view(['PUT'])
@permission_classes([TenantAPIKeyPermission])
def portal_branding_update(request):
    """
    Update tenant branding colors and settings
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Check if plan allows custom branding
    if tenant.subscription_plan and not tenant.subscription_plan.custom_branding:
        return Response({
            'success': False,
            'message': 'Custom branding not available in your subscription plan. Upgrade to unlock this feature.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = BrandingUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    branding = BrandingManager(tenant)
    
    # Update colors if provided
    if 'primary_color' in serializer.validated_data or 'secondary_color' in serializer.validated_data:
        success, message = branding.update_colors(
            primary_color=serializer.validated_data.get('primary_color'),
            secondary_color=serializer.validated_data.get('secondary_color')
        )
        if not success:
            return Response({
                'success': False,
                'message': message
            }, status=status.HTTP_400_BAD_REQUEST)
    
    # Update business name if provided
    if 'business_name' in serializer.validated_data:
        tenant.business_name = serializer.validated_data['business_name']
        tenant.save()
    
    return Response({
        'success': True,
        'message': 'Branding updated successfully',
        'branding': branding.get_branding()
    })


@api_view(['POST'])
@permission_classes([TenantAPIKeyPermission])
def portal_logo_upload(request):
    """
    Upload tenant logo
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Check if plan allows custom branding
    if tenant.subscription_plan and not tenant.subscription_plan.custom_branding:
        return Response({
            'success': False,
            'message': 'Custom branding not available in your subscription plan'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if 'logo' not in request.FILES:
        return Response({
            'success': False,
            'message': 'No logo file provided'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    branding = BrandingManager(tenant)
    success, message = branding.update_logo(request.FILES['logo'])
    
    if success:
        return Response({
            'success': True,
            'message': message,
            'logo_url': tenant.logo.url if tenant.logo else None
        })
    else:
        return Response({
            'success': False,
            'message': message
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([TenantAPIKeyPermission])
def portal_logo_remove(request):
    """
    Remove tenant logo
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    branding = BrandingManager(tenant)
    success, message = branding.remove_logo()
    
    return Response({
        'success': success,
        'message': message
    })


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([TenantAPIKeyPermission])
def portal_custom_domain(request):
    """
    Manage custom domain configuration
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    branding = BrandingManager(tenant)
    
    if request.method == 'GET':
        # Get current domain and DNS instructions
        return Response({
            'success': True,
            'domain': tenant.custom_domain,
            'dns_instructions': branding.get_dns_instructions(),
            'validation': branding.validate_custom_domain()
        })
    
    elif request.method == 'POST':
        # Set custom domain
        if tenant.subscription_plan and not tenant.subscription_plan.custom_domain:
            return Response({
                'success': False,
                'message': 'Custom domain not available in your subscription plan'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = CustomDomainSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        success, message = branding.update_custom_domain(serializer.validated_data['domain'])
        
        if success:
            return Response({
                'success': True,
                'message': message,
                'dns_instructions': branding.get_dns_instructions()
            })
        else:
            return Response({
                'success': False,
                'message': message
            }, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        # Remove custom domain
        success, message = branding.remove_custom_domain()
        return Response({
            'success': success,
            'message': message
        })


@api_view(['GET'])
@permission_classes([TenantAPIKeyPermission])
def portal_theme_css(request):
    """
    Get generated CSS theme based on tenant branding
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    theme = ThemeGenerator(tenant)
    
    # Return as CSS file or JSON
    output_format = request.query_params.get('format', 'json')
    
    if output_format == 'css':
        response = HttpResponse(theme.generate_full_theme(), content_type='text/css')
        response['Content-Disposition'] = f'attachment; filename="{tenant.slug}_theme.css"'
        return response
    
    return Response({
        'success': True,
        'css_variables': theme.generate_css_variables(),
        'full_theme': theme.generate_full_theme()
    })


@api_view(['GET'])
@permission_classes([TenantAPIKeyPermission])
def portal_captive_portal_pages(request):
    """
    Get generated captive portal HTML pages
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    generator = CaptivePortalGenerator(tenant)
    
    return Response({
        'success': True,
        'pages': generator.get_all_pages()
    })


# =============================================================================
# TENANT SETTINGS
# =============================================================================

@api_view(['GET', 'PUT'])
@permission_classes([TenantAPIKeyPermission])
def portal_settings(request):
    """
    Get or update tenant settings
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        return Response({
            'success': True,
            'settings': {
                'business_name': tenant.business_name,
                'business_email': tenant.business_email,
                'business_phone': tenant.business_phone,
                'business_address': tenant.business_address,
                'timezone': tenant.timezone,
                'primary_color': tenant.primary_color,
                'secondary_color': tenant.secondary_color,
                'has_nextsms': bool(tenant.nextsms_username),
                'has_clickpesa': bool(tenant.clickpesa_client_id),
                'nextsms_sender_id': tenant.nextsms_sender_id,
            }
        })
    
    elif request.method == 'PUT':
        serializer = TenantSettingsSerializer(tenant, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save()
        
        return Response({
            'success': True,
            'message': 'Settings updated successfully'
        })


@api_view(['GET'])
@permission_classes([TenantAPIKeyPermission])
def portal_api_keys(request):
    """
    Get tenant API keys
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    return Response({
        'success': True,
        'api_key': tenant.api_key,
        'api_secret': tenant.api_secret[:8] + '...' if tenant.api_secret else None,  # Partially masked
        'usage': {
            'header_name': 'X-API-Key',
            'example': f'curl -H "X-API-Key: {tenant.api_key}" https://api.kitonga.klikcell.com/api/...'
        }
    })


@api_view(['POST'])
@permission_classes([TenantAPIKeyPermission])
def portal_regenerate_api_key(request):
    """
    Regenerate tenant API key
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    import secrets
    tenant.api_key = secrets.token_hex(32)
    tenant.api_secret = secrets.token_hex(64)
    tenant.save()
    
    return Response({
        'success': True,
        'message': 'API keys regenerated successfully',
        'api_key': tenant.api_key,
        'warning': 'Update your integrations with the new API key'
    })


# =============================================================================
# STAFF MANAGEMENT
# =============================================================================

@api_view(['GET', 'POST'])
@permission_classes([TenantAPIKeyPermission])
def portal_staff(request):
    """
    List or invite staff members
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        staff = TenantStaff.objects.filter(tenant=tenant).select_related('user')
        return Response({
            'success': True,
            'staff': TenantStaffSerializer(staff, many=True).data,
            'limit': tenant.subscription_plan.max_staff_accounts if tenant.subscription_plan else 2,
            'used': staff.count()
        })
    
    elif request.method == 'POST':
        # Check limit
        current_count = TenantStaff.objects.filter(tenant=tenant, is_active=True).count()
        limit = tenant.subscription_plan.max_staff_accounts if tenant.subscription_plan else 2
        
        if current_count >= limit:
            return Response({
                'success': False,
                'message': f'Staff limit reached ({limit}). Upgrade your plan to add more staff.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = StaffInviteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data['email']
        
        # Check if user exists or create new
        user, created = DjangoUser.objects.get_or_create(
            email=email,
            defaults={
                'username': email.split('@')[0] + '_' + tenant.slug,
                'first_name': serializer.validated_data.get('first_name', ''),
                'last_name': serializer.validated_data.get('last_name', ''),
            }
        )
        
        # Check if already a staff member
        if TenantStaff.objects.filter(tenant=tenant, user=user).exists():
            return Response({
                'success': False,
                'message': 'User is already a staff member'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create staff record
        staff = TenantStaff.objects.create(
            tenant=tenant,
            user=user,
            role=serializer.validated_data.get('role', 'support'),
            can_manage_routers=serializer.validated_data.get('can_manage_routers', False),
            can_manage_users=serializer.validated_data.get('can_manage_users', True),
            can_manage_payments=serializer.validated_data.get('can_manage_payments', True),
            can_manage_vouchers=serializer.validated_data.get('can_manage_vouchers', True),
            can_view_reports=serializer.validated_data.get('can_view_reports', True),
            can_manage_staff=serializer.validated_data.get('can_manage_staff', False),
            can_manage_settings=serializer.validated_data.get('can_manage_settings', False),
        )
        
        # TODO: Send invitation email
        
        return Response({
            'success': True,
            'message': f'Staff member invited: {email}',
            'staff': TenantStaffSerializer(staff).data
        }, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([TenantAPIKeyPermission])
def portal_staff_detail(request, staff_id):
    """
    Get, update, or remove a staff member
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        staff = TenantStaff.objects.get(id=staff_id, tenant=tenant)
    except TenantStaff.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Staff member not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        return Response({
            'success': True,
            'staff': TenantStaffSerializer(staff).data
        })
    
    elif request.method == 'PUT':
        # Cannot modify owner
        if staff.role == 'owner':
            return Response({
                'success': False,
                'message': 'Cannot modify owner permissions'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = StaffUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        for field, value in serializer.validated_data.items():
            setattr(staff, field, value)
        staff.save()
        
        return Response({
            'success': True,
            'message': 'Staff member updated',
            'staff': TenantStaffSerializer(staff).data
        })
    
    elif request.method == 'DELETE':
        # Cannot delete owner
        if staff.role == 'owner':
            return Response({
                'success': False,
                'message': 'Cannot remove owner'
            }, status=status.HTTP_403_FORBIDDEN)
        
        staff.is_active = False
        staff.save()
        
        return Response({
            'success': True,
            'message': 'Staff member removed'
        })


# =============================================================================
# LOCATION MANAGEMENT
# =============================================================================

@api_view(['GET', 'POST'])
@permission_classes([TenantAPIKeyPermission])
def portal_locations(request):
    """
    List or create locations
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        locations = Location.objects.filter(tenant=tenant, is_active=True)
        return Response({
            'success': True,
            'locations': LocationSerializer(locations, many=True).data,
            'limit': tenant.subscription_plan.max_locations if tenant.subscription_plan else 1,
            'used': locations.count()
        })
    
    elif request.method == 'POST':
        # Check limit
        current_count = Location.objects.filter(tenant=tenant, is_active=True).count()
        limit = tenant.subscription_plan.max_locations if tenant.subscription_plan else 1
        
        if current_count >= limit:
            return Response({
                'success': False,
                'message': f'Location limit reached ({limit}). Upgrade your plan to add more locations.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = LocationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        location = serializer.save(tenant=tenant)
        
        return Response({
            'success': True,
            'message': 'Location created',
            'location': LocationSerializer(location).data
        }, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([TenantAPIKeyPermission])
def portal_location_detail(request, location_id):
    """
    Get, update, or delete a location
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        location = Location.objects.get(id=location_id, tenant=tenant)
    except Location.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Location not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        # Include routers at this location
        routers = Router.objects.filter(location=location, is_active=True)
        return Response({
            'success': True,
            'location': LocationSerializer(location).data,
            'routers': [{'id': r.id, 'name': r.name, 'status': r.status} for r in routers]
        })
    
    elif request.method == 'PUT':
        serializer = LocationSerializer(location, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save()
        
        return Response({
            'success': True,
            'message': 'Location updated',
            'location': serializer.data
        })
    
    elif request.method == 'DELETE':
        location.is_active = False
        location.save()
        
        return Response({
            'success': True,
            'message': 'Location removed'
        })


# =============================================================================
# BUNDLE MANAGEMENT
# =============================================================================

@api_view(['GET', 'POST'])
@permission_classes([TenantAPIKeyPermission])
def portal_bundles(request):
    """
    List or create WiFi bundles
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        bundles = Bundle.objects.filter(tenant=tenant).order_by('display_order', 'duration_hours')
        return Response({
            'success': True,
            'bundles': BundleSerializer(bundles, many=True).data
        })
    
    elif request.method == 'POST':
        serializer = BundleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        bundle = serializer.save(tenant=tenant)
        
        return Response({
            'success': True,
            'message': 'Bundle created',
            'bundle': BundleSerializer(bundle).data
        }, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([TenantAPIKeyPermission])
def portal_bundle_detail(request, bundle_id):
    """
    Get, update, or delete a bundle
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({
            'success': False,
            'message': 'Tenant not found'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        bundle = Bundle.objects.get(id=bundle_id, tenant=tenant)
    except Bundle.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Bundle not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        # Include sales stats
        sales = Payment.objects.filter(bundle=bundle, status='completed')
        return Response({
            'success': True,
            'bundle': BundleSerializer(bundle).data,
            'stats': {
                'total_sales': sales.count(),
                'total_revenue': float(sales.aggregate(total=Sum('amount'))['total'] or 0)
            }
        })
    
    elif request.method == 'PUT':
        serializer = BundleSerializer(bundle, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save()
        
        return Response({
            'success': True,
            'message': 'Bundle updated',
            'bundle': serializer.data
        })
    
    elif request.method == 'DELETE':
        # Soft delete - just deactivate
        bundle.is_active = False
        bundle.save()
        
        return Response({
            'success': True,
            'message': 'Bundle deactivated'
        })
