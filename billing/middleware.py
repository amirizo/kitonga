"""
Custom middleware for access control
"""
from django.utils import timezone
from .models import User, AccessLog
import logging

logger = logging.getLogger(__name__)


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
