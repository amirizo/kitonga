"""
Custom permissions for Kitonga Wi-Fi Billing System
"""
from rest_framework import permissions
from django.conf import settings
from rest_framework.authtoken.models import Token
import hashlib
import hmac


class IsAdminOrHasAdminToken(permissions.BasePermission):
    """
    Custom permission that allows access if user is Django admin OR has valid admin token
    """

    def has_permission(self, request, view):
        # Check if user is authenticated Django admin (session-based)
        if request.user and request.user.is_authenticated and request.user.is_staff:
            return True
        
        # Check for token authentication
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Token '):
            token_key = auth_header.split(' ')[1]
            try:
                token = Token.objects.get(key=token_key)
                if token.user.is_staff:
                    return True
            except Token.DoesNotExist:
                pass
        
        # Check for admin access token in headers
        admin_token = request.META.get('HTTP_X_ADMIN_ACCESS')
        if admin_token:
            # You can implement different token validation strategies here
            
            # Strategy 1: Simple static token (for development)
            expected_token = getattr(settings, 'ADMIN_ACCESS_TOKEN', 'admin123')
            if admin_token == expected_token:
                return True
            
            # Strategy 2: Dynamic token based on secret + timestamp (more secure)
            # You can implement this if needed
            
        return False


class IsAdminWithValidToken(permissions.BasePermission):
    """
    Advanced permission class with time-based token validation
    """
    
    def has_permission(self, request, view):
        # Check if user is authenticated Django admin
        if request.user and request.user.is_authenticated and request.user.is_staff:
            return True
        
        # Check for admin access token in headers
        admin_token = request.META.get('HTTP_X_ADMIN_ACCESS')
        if not admin_token:
            return False
        
        # Validate token format: should be "token:timestamp"
        try:
            token_parts = admin_token.split(':')
            if len(token_parts) != 2:
                return False
            
            provided_token, timestamp = token_parts
            
            # Check if timestamp is recent (within 1 hour)
            import time
            current_time = int(time.time())
            request_time = int(timestamp)
            
            # Token expires after 1 hour
            if current_time - request_time > 3600:
                return False
            
            # Generate expected token
            secret_key = getattr(settings, 'ADMIN_TOKEN_SECRET', settings.SECRET_KEY)
            expected_token = hmac.new(
                secret_key.encode(),
                timestamp.encode(),
                hashlib.sha256
            ).hexdigest()[:16]  # Use first 16 characters
            
            return provided_token == expected_token
            
        except (ValueError, AttributeError):
            return False


class SimpleAdminTokenPermission(permissions.BasePermission):
    """
    Simple permission class that checks for multiple authentication methods
    """
    
    def has_permission(self, request, view):
        # Check if user is authenticated Django admin (session-based)
        if request.user and request.user.is_authenticated and request.user.is_staff:
            return True
        
        # Check for token authentication
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Token '):
            token_key = auth_header.split(' ')[1]
            try:
                token = Token.objects.get(key=token_key)
                if token.user.is_staff:
                    return True
            except Token.DoesNotExist:
                pass
        
        # Check for simple admin token
        admin_token = request.META.get('HTTP_X_ADMIN_ACCESS')
        if admin_token:
            expected_token = getattr(settings, 'SIMPLE_ADMIN_TOKEN', 'kitonga_admin_2025')
            return admin_token == expected_token
        
        return False
