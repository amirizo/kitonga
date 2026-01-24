"""
Custom middleware for access control and multi-tenancy
"""
from django.utils import timezone
from django.http import JsonResponse
import threading
import logging

logger = logging.getLogger(__name__)

# Thread-local storage for current tenant
_thread_locals = threading.local()


def get_current_tenant():
    """Get the current tenant from thread-local storage"""
    return getattr(_thread_locals, 'tenant', None)


def set_current_tenant(tenant):
    """Set the current tenant in thread-local storage"""
    _thread_locals.tenant = tenant


def clear_current_tenant():
    """Clear the current tenant from thread-local storage"""
    if hasattr(_thread_locals, 'tenant'):
        del _thread_locals.tenant


class TenantMiddleware:
    """
    Middleware to identify and set the current tenant based on:
    1. Subdomain (e.g., hotel.kitonga.com)
    2. Custom domain (e.g., wifi.hotel.com)
    3. API key in headers
    4. Query parameter (for testing)
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip tenant resolution for admin URLs
        if request.path.startswith('/admin/'):
            clear_current_tenant()
            response = self.get_response(request)
            return response
        
        tenant = None
        
        # Try to resolve tenant
        try:
            # 1. Check for API key in headers
            api_key = request.META.get('HTTP_X_API_KEY') or request.META.get('HTTP_API_KEY')
            if api_key:
                from .models import Tenant
                try:
                    tenant = Tenant.objects.get(api_key=api_key, is_active=True)
                    logger.debug(f'Tenant resolved from API key: {tenant.slug}')
                except Tenant.DoesNotExist:
                    pass
            
            # 2. Check for tenant slug in query params (for testing/development)
            if not tenant:
                tenant_slug = request.GET.get('tenant')
                if tenant_slug:
                    from .models import Tenant
                    try:
                        tenant = Tenant.objects.get(slug=tenant_slug, is_active=True)
                        logger.debug(f'Tenant resolved from query param: {tenant.slug}')
                    except Tenant.DoesNotExist:
                        pass
            
            # 3. Check subdomain
            if not tenant:
                host = request.get_host().split(':')[0]  # Remove port
                subdomain = self._get_subdomain(host)
                if subdomain and subdomain not in ['www', 'api', 'admin']:
                    from .models import Tenant
                    try:
                        tenant = Tenant.objects.get(slug=subdomain, is_active=True)
                        logger.debug(f'Tenant resolved from subdomain: {tenant.slug}')
                    except Tenant.DoesNotExist:
                        pass
            
            # 4. Check custom domain
            if not tenant:
                host = request.get_host().split(':')[0]
                from .models import Tenant
                try:
                    tenant = Tenant.objects.get(custom_domain=host, is_active=True)
                    logger.debug(f'Tenant resolved from custom domain: {tenant.slug}')
                except Tenant.DoesNotExist:
                    pass
            
        except Exception as e:
            logger.error(f'Error resolving tenant: {e}')
        
        # Set tenant in thread-local storage
        set_current_tenant(tenant)
        
        # Add tenant to request for easy access
        request.tenant = tenant
        
        # Process request
        response = self.get_response(request)
        
        # Clear tenant after request
        clear_current_tenant()
        
        return response
    
    def _get_subdomain(self, host):
        """Extract subdomain from host"""
        parts = host.split('.')
        if len(parts) >= 3:
            return parts[0]
        return None


class TenantRequiredMiddleware:
    """
    Middleware to require a valid tenant for API endpoints
    Returns 400 error if tenant not found for /api/ endpoints (except public ones)
    """
    
    PUBLIC_ENDPOINTS = [
        '/api/health/',
        '/api/bundles/',  # Public bundle listing
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip for non-API endpoints
        if not request.path.startswith('/api/'):
            return self.get_response(request)
        
        # Skip for public endpoints
        for endpoint in self.PUBLIC_ENDPOINTS:
            if request.path.startswith(endpoint):
                return self.get_response(request)
        
        # Skip for admin endpoints (they use different auth)
        if '/admin/' in request.path:
            return self.get_response(request)
        
        # Check if tenant is required
        # For now, we'll allow requests without tenant for backwards compatibility
        # Enable strict mode by uncommenting below:
        # if not getattr(request, 'tenant', None):
        #     return JsonResponse({
        #         'success': False,
        #         'message': 'Tenant not specified. Provide tenant via subdomain, API key, or query parameter.'
        #     }, status=400)
        
        return self.get_response(request)


class AccessControlMiddleware:
    """
    Middleware to log and control access attempts
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Process request
        response = self.get_response(request)
        return response
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Log access attempts for monitoring
        """
        # Skip logging for admin and static files
        if request.path.startswith('/admin/') or request.path.startswith('/static/'):
            return None
        
        # Get client info
        ip_address = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Log in debug mode
        logger.debug(f'Access attempt from {ip_address} - {user_agent}')
        
        return None
    
    @staticmethod
    def get_client_ip(request):
        """
        Get client IP address from request
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
