"""
Mikrotik Router Integration for Kitonga Wi-Fi Billing System
"""
import requests
import socket
import hashlib
import binascii
import logging
from django.conf import settings
from urllib.parse import quote

logger = logging.getLogger(__name__)


class MikrotikIntegration:
    """
    Mikrotik router integration for hotspot authentication
    """
    
    def __init__(self, router_ip="192.168.88.1", admin_user="admin", admin_pass=""):
        self.router_ip = router_ip
        self.admin_user = admin_user
        self.admin_pass = admin_pass
        self.login_url = f"http://{router_ip}/login"
        self.api_port = 8728
    
    def login_user_to_hotspot(self, phone_number, mac_address="", ip_address=""):
        """
        Login user to Mikrotik hotspot using HTTP login
        
        Args:
            phone_number: User's phone number (used as username)
            mac_address: User's MAC address
            ip_address: User's IP address
        
        Returns:
            dict: Success status and message
        """
        try:
            # For Mikrotik external authentication, we just return success
            # The actual authentication is handled by Django
            # Mikrotik will allow/deny based on our HTTP response
            
            logger.info(f'Mikrotik authentication request for user {phone_number}')
            return {
                'success': True,
                'message': 'User authentication validated by Django',
                'mikrotik_response': 'External authentication successful'
            }
            
        except Exception as e:
            logger.error(f'Error in Mikrotik authentication for user {phone_number}: {str(e)}')
            return {
                'success': False,
                'message': f'Authentication error: {str(e)}'
            }
    
    def logout_user_from_hotspot(self, phone_number, ip_address=""):
        """
        Logout user from Mikrotik hotspot
        
        Args:
            phone_number: User's phone number
            ip_address: User's IP address
        
        Returns:
            dict: Success status and message
        """
        try:
            logout_url = f"http://{self.router_ip}/logout"
            logout_data = {
                'username': phone_number,
                'erase-cookie': 'true'
            }
            
            response = requests.post(logout_url, data=logout_data, timeout=10)
            
            if response.status_code == 200:
                logger.info(f'User {phone_number} logged out from Mikrotik successfully')
                return {
                    'success': True,
                    'message': 'User logged out successfully'
                }
            else:
                logger.error(f'Mikrotik logout failed for {phone_number}')
                return {
                    'success': False,
                    'message': 'Logout failed'
                }
                
        except Exception as e:
            logger.error(f'Error logging out user {phone_number} from Mikrotik: {str(e)}')
            return {
                'success': False,
                'message': f'Logout error: {str(e)}'
            }
    
    def check_user_status(self, phone_number):
        """
        Check if user is currently logged in to hotspot
        Note: This requires Mikrotik API access, simplified version here
        
        Args:
            phone_number: User's phone number
        
        Returns:
            dict: User status information
        """
        try:
            # This is a simplified check - in production you'd use Mikrotik API
            # For now, we'll just return basic status
            return {
                'success': True,
                'is_online': False,  # Would need API to check actual status
                'message': 'Status check requires API access'
            }
        except Exception as e:
            logger.error(f'Error checking user status for {phone_number}: {str(e)}')
            return {
                'success': False,
                'message': f'Status check error: {str(e)}'
            }


class SimpleMikrotikAPI:
    """
    Simplified Mikrotik API client for basic operations
    Note: For production use, consider using a full-featured library like librouteros
    """
    
    def __init__(self, host, username, password, port=8728):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.socket = None
        self.current_tag = 0
    
    def connect(self):
        """Connect to Mikrotik API"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))
            return True
        except Exception as e:
            logger.error(f'Failed to connect to Mikrotik API: {str(e)}')
            return False
    
    def disconnect(self):
        """Disconnect from Mikrotik API"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
    
    def login(self):
        """Login to Mikrotik API"""
        # Simplified login - in production, implement full API authentication
        try:
            # This is a placeholder - implement actual API login
            return True
        except Exception as e:
            logger.error(f'Mikrotik API login failed: {str(e)}')
            return False
    
    def add_hotspot_active_user(self, username, address="", mac_address=""):
        """
        Add user to hotspot active list
        
        Args:
            username: Username (phone number)
            address: IP address
            mac_address: MAC address
        
        Returns:
            bool: Success status
        """
        try:
            # This would use the actual Mikrotik API protocol
            # For now, return success for demonstration
            logger.info(f'Would add hotspot user {username} via API')
            return True
        except Exception as e:
            logger.error(f'Error adding hotspot user via API: {str(e)}')
            return False
    
    def remove_hotspot_active_user(self, username):
        """
        Remove user from hotspot active list
        
        Args:
            username: Username to remove
        
        Returns:
            bool: Success status
        """
        try:
            # This would use the actual Mikrotik API protocol
            logger.info(f'Would remove hotspot user {username} via API')
            return True
        except Exception as e:
            logger.error(f'Error removing hotspot user via API: {str(e)}')
            return False


def get_mikrotik_client():
    """
    Get configured Mikrotik client from settings
    
    Returns:
        MikrotikIntegration: Configured client
    """
    router_ip = getattr(settings, 'MIKROTIK_ROUTER_IP', '192.168.88.1')
    admin_user = getattr(settings, 'MIKROTIK_ADMIN_USER', 'admin')
    admin_pass = getattr(settings, 'MIKROTIK_ADMIN_PASS', '')
    
    return MikrotikIntegration(router_ip, admin_user, admin_pass)


def authenticate_user_with_mikrotik(phone_number, mac_address="", ip_address=""):
    """
    Authenticate user with Mikrotik router
    
    Args:
        phone_number: User's phone number
        mac_address: User's MAC address
        ip_address: User's IP address
    
    Returns:
        dict: Authentication result
    """
    mikrotik = get_mikrotik_client()
    return mikrotik.login_user_to_hotspot(phone_number, mac_address, ip_address)


def logout_user_from_mikrotik(phone_number, ip_address=""):
    """
    Logout user from Mikrotik router
    
    Args:
        phone_number: User's phone number
        ip_address: User's IP address
    
    Returns:
        dict: Logout result
    """
    mikrotik = get_mikrotik_client()
    return mikrotik.logout_user_from_hotspot(phone_number, ip_address)
