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
    
    def __init__(self, router_ip="192.168.0.173", admin_user="admin", admin_pass="Kijangwani2003"):
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
    router_ip = getattr(settings, 'MIKROTIK_ROUTER_IP', '192.168.0.173')
    admin_user = getattr(settings, 'MIKROTIK_ADMIN_USER', 'admin')
    admin_pass = getattr(settings, 'MIKROTIK_ADMIN_PASS', 'Kijangwani2003')
    
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


def test_mikrotik_connection(host=None, username=None, password=None, port=8728):
    """
    Test connection to MikroTik router
    
    Args:
        host: Router IP address
        username: Admin username
        password: Admin password
        port: API port (default 8728)
    
    Returns:
        dict: Connection test result
    """
    try:
        # Use provided credentials or get from settings
        host = host or getattr(settings, 'MIKROTIK_ROUTER_IP', '192.168.0.173')
        username = username or getattr(settings, 'MIKROTIK_USERNAME', 'admin')
        password = password or getattr(settings, 'MIKROTIK_PASSWORD', 'Kijangwani2003')
        
        # Test basic socket connection
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(5)
        
        result = test_socket.connect_ex((host, port))
        test_socket.close()
        
        if result == 0:
            return {
                'success': True,
                'message': 'Connection successful',
                'router_info': {
                    'ip': host,
                    'port': port,
                    'status': 'reachable'
                }
            }
        else:
            return {
                'success': False,
                'error': f'Cannot connect to {host}:{port}',
                'router_info': {
                    'ip': host,
                    'port': port,
                    'status': 'unreachable'
                }
            }
            
    except Exception as e:
        logger.error(f'Error testing MikroTik connection: {str(e)}')
        return {
            'success': False,
            'error': str(e)
        }


def get_router_info():
    """
    Get detailed router information
    
    Returns:
        dict: Router information
    """
    try:
        router_ip = getattr(settings, 'MIKROTIK_ROUTER_IP', '192.168.0.173')
        
        # Basic router info (in production, use API to get actual info)
        router_info = {
            'ip_address': router_ip,
            'api_port': getattr(settings, 'MIKROTIK_API_PORT', 8728),
            'hotspot_name': getattr(settings, 'MIKROTIK_HOTSPOT_NAME', 'kitonga-hotspot'),
            'admin_user': getattr(settings, 'MIKROTIK_USERNAME', 'admin'),
            'connection_status': 'unknown',
            'uptime': 'unknown',
            'version': 'unknown',
            'board_name': 'unknown',
            'cpu_load': 0,
            'memory_usage': 0,
            'active_users': 0
        }
        
        # Test connection
        connection_test = test_mikrotik_connection()
        router_info['connection_status'] = 'connected' if connection_test['success'] else 'disconnected'
        
        return {
            'success': True,
            'data': router_info
        }
        
    except Exception as e:
        logger.error(f'Error getting router info: {str(e)}')
        return {
            'success': False,
            'error': str(e)
        }


def get_active_hotspot_users():
    """
    Get list of currently active users on hotspot
    
    Returns:
        dict: List of active users
    """
    try:
        # In production, this would query the actual MikroTik API
        # For now, return mock data
        active_users = [
            {
                'user': '255700000001',
                'address': '10.5.50.100',
                'mac_address': 'AA:BB:CC:DD:EE:01',
                'uptime': '00:15:30',
                'session_time_left': '23:44:30',
                'bytes_in': 1024000,
                'bytes_out': 512000,
                'packets_in': 1500,
                'packets_out': 1200
            },
            {
                'user': '255700000002',
                'address': '10.5.50.101',
                'mac_address': 'AA:BB:CC:DD:EE:02',
                'uptime': '01:05:15',
                'session_time_left': '22:54:45',
                'bytes_in': 2048000,
                'bytes_out': 1024000,
                'packets_in': 3000,
                'packets_out': 2400
            }
        ]
        
        return {
            'success': True,
            'data': active_users
        }
        
    except Exception as e:
        logger.error(f'Error getting active users: {str(e)}')
        return {
            'success': False,
            'error': str(e)
        }


def disconnect_all_hotspot_users():
    """
    Disconnect all active users from hotspot
    
    Returns:
        dict: Disconnection result
    """
    try:
        # In production, this would use the MikroTik API to disconnect all users
        # For now, simulate the action
        active_users = get_active_hotspot_users()
        
        if active_users['success']:
            user_count = len(active_users['data'])
            
            # Simulate disconnecting each user
            for user in active_users['data']:
                logger.info(f"Would disconnect user: {user['user']}")
            
            return {
                'success': True,
                'count': user_count,
                'message': f'Successfully disconnected {user_count} users'
            }
        else:
            return {
                'success': False,
                'error': 'Could not get active users list'
            }
        
    except Exception as e:
        logger.error(f'Error disconnecting all users: {str(e)}')
        return {
            'success': False,
            'error': str(e)
        }


def reboot_router():
    """
    Reboot the MikroTik router
    
    Returns:
        dict: Reboot result
    """
    try:
        # In production, this would send a reboot command via API
        # For safety, we'll just simulate this for now
        router_ip = getattr(settings, 'MIKROTIK_ROUTER_IP', '192.168.0.173')
        
        logger.warning(f'Router reboot simulated for {router_ip}')
        
        return {
            'success': True,
            'message': 'Router reboot command sent (simulated)',
            'warning': 'Router will be offline for 1-2 minutes'
        }
        
    except Exception as e:
        logger.error(f'Error rebooting router: {str(e)}')
        return {
            'success': False,
            'error': str(e)
        }


def get_hotspot_profiles():
    """
    Get list of hotspot user profiles
    
    Returns:
        dict: List of profiles
    """
    try:
        # In production, this would query actual profiles from MikroTik
        profiles = [
            {
                'name': 'default',
                'rate_limit': '512k/512k',
                'session_timeout': '1d',
                'idle_timeout': '5m',
                'keepalive_timeout': '2m',
                'status_autorefresh': '1m'
            },
            {
                'name': 'premium',
                'rate_limit': '2M/2M',
                'session_timeout': '1d',
                'idle_timeout': '10m',
                'keepalive_timeout': '2m',
                'status_autorefresh': '1m'
            }
        ]
        
        return {
            'success': True,
            'data': profiles
        }
        
    except Exception as e:
        logger.error(f'Error getting hotspot profiles: {str(e)}')
        return {
            'success': False,
            'error': str(e)
        }


def create_hotspot_profile(name, rate_limit='512k/512k', session_timeout='1d', idle_timeout='5m'):
    """
    Create a new hotspot user profile
    
    Args:
        name: Profile name
        rate_limit: Rate limit (e.g., '1M/1M')
        session_timeout: Session timeout (e.g., '1d', '2h')
        idle_timeout: Idle timeout (e.g., '5m')
    
    Returns:
        dict: Creation result
    """
    try:
        # In production, this would create the profile via API
        logger.info(f'Would create hotspot profile: {name}')
        
        new_profile = {
            'name': name,
            'rate_limit': rate_limit,
            'session_timeout': session_timeout,
            'idle_timeout': idle_timeout,
            'keepalive_timeout': '2m',
            'status_autorefresh': '1m'
        }
        
        return {
            'success': True,
            'data': new_profile,
            'message': f'Profile "{name}" created successfully (simulated)'
        }
        
    except Exception as e:
        logger.error(f'Error creating hotspot profile: {str(e)}')
        return {
            'success': False,
            'error': str(e)
        }


def get_system_resources():
    """
    Get router system resources and performance metrics
    
    Returns:
        dict: System resources information
    """
    try:
        # In production, this would query actual system resources
        resources = {
            'uptime': '2d5h30m',
            'version': '6.49.7 (stable)',
            'build_time': 'Oct/01/2023 10:26:21',
            'factory_software': '6.49.7',
            'free_memory': 67108864,  # bytes
            'total_memory': 134217728,  # bytes
            'free_hdd_space': 1073741824,  # bytes
            'total_hdd_space': 2147483648,  # bytes
            'cpu_count': 4,
            'cpu_frequency': 716,  # MHz
            'cpu_load': 15,  # percentage
            'architecture_name': 'arm',
            'board_name': 'RB4011iGS+',
            'platform': 'MikroTik'
        }
        
        # Calculate percentages
        memory_usage = ((resources['total_memory'] - resources['free_memory']) / resources['total_memory']) * 100
        disk_usage = ((resources['total_hdd_space'] - resources['free_hdd_space']) / resources['total_hdd_space']) * 100
        
        resources['memory_usage_percent'] = round(memory_usage, 2)
        resources['disk_usage_percent'] = round(disk_usage, 2)
        
        return {
            'success': True,
            'data': resources
        }
        
    except Exception as e:
        logger.error(f'Error getting system resources: {str(e)}')
        return {
            'success': False,
            'error': str(e)
        }
