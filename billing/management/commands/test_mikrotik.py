"""
Management command to test Mikrotik router connectivity and authentication
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from billing.mikrotik import (
    test_mikrotik_connection,
    authenticate_user_with_mikrotik,
    get_router_info,
    get_active_hotspot_users,
    list_interfaces,
    get_hotspot_interfaces,
    get_hotspot_active_users_by_interface,
)
import requests
import socket


class Command(BaseCommand):
    help = 'Test Mikrotik router connectivity and authentication'

    def add_arguments(self, parser):
        parser.add_argument(
            '--router-ip',
            type=str,
            help='Mikrotik router IP address (default from settings)',
        )
        parser.add_argument(
            '--test-user',
            type=str,
            default='255772236727',
            help='Test phone number for authentication (default: 255772236727)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Testing Mikrotik Router Connectivity\n'))
        
        # Get router IP
        router_ip = options.get('router_ip') or getattr(settings, 'MIKROTIK_HOST', '10.50.0.2')
        test_user = options['test_user']
        
        self.stdout.write(f'Router IP: {router_ip}')
        self.stdout.write(f'Test User: {test_user}')
        self.stdout.write('-' * 50)
        
        # Test 1: Basic connectivity
        self.stdout.write('\n1. Testing basic connectivity...')
        try:
            response = requests.get(f'http://{router_ip}', timeout=5)
            if response.status_code == 200:
                self.stdout.write(self.style.SUCCESS('✓ Router is reachable'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠ Router responded with status {response.status_code}'))
        except requests.exceptions.ConnectTimeout:
            self.stdout.write(self.style.ERROR('✗ Connection timeout - router not reachable'))
            return
        except requests.exceptions.ConnectionError:
            self.stdout.write(self.style.ERROR('✗ Connection error - router not reachable'))
            return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error connecting to router: {str(e)}'))
            return
        
        # Test 2: Check hotspot login page
        self.stdout.write('\n2. Testing hotspot login page...')
        try:
            login_url = f'http://{router_ip}/login'
            response = requests.get(login_url, timeout=5)
            if 'username' in response.text.lower() and 'password' in response.text.lower():
                self.stdout.write(self.style.SUCCESS('✓ Hotspot login page found'))
            else:
                self.stdout.write(self.style.WARNING('⚠ Login page found but may not be hotspot'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error accessing login page: {str(e)}'))
        
        # Test 3: Test Mikrotik API connection
        self.stdout.write('\n3. Testing Mikrotik API connection...')
        try:
            result = test_mikrotik_connection(
                host=router_ip,
                username=getattr(settings, 'MIKROTIK_USER', 'admin'),
                password=getattr(settings, 'MIKROTIK_PASSWORD', ''),
                port=getattr(settings, 'MIKROTIK_PORT', 8728)
            )
            if result.get('success'):
                self.stdout.write(self.style.SUCCESS(f'✓ Mikrotik API connection successful'))
                self.stdout.write(f'  - Router IP: {router_ip}')
                self.stdout.write(f'  - Admin User: {getattr(settings, "MIKROTIK_USER", "admin")}')
                self.stdout.write(f'  - SSL: {getattr(settings, "MIKROTIK_USE_SSL", False)} (verify={getattr(settings, "MIKROTIK_SSL_VERIFY", False)})')
            else:
                self.stdout.write(self.style.ERROR(f'✗ Mikrotik API connection failed: {result.get("message", "Unknown error")}'))
                self.stdout.write(self.style.WARNING('⚠ Make sure API is enabled on the router'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error connecting to Mikrotik API: {str(e)}'))
            self.stdout.write(self.style.WARNING('⚠ This is normal if API is disabled on the router'))

        # 3b. Example usage: List interfaces
        self.stdout.write('\n3b. Listing MikroTik interfaces...')
        try:
            iface_result = list_interfaces()
            if iface_result.get('success'):
                data = iface_result.get('data', [])
                if not data:
                    self.stdout.write(self.style.WARNING('⚠ No interfaces returned'))
                for i, it in enumerate(data, 1):
                    self.stdout.write(f"  {i}. {it.get('name')}\tType: {it.get('type')}\tMAC: {it.get('mac_address')}\tRunning: {it.get('running')}\tDisabled: {it.get('disabled')}")
                self.stdout.write(self.style.SUCCESS('✓ Interfaces listed'))
            else:
                self.stdout.write(self.style.ERROR(f"✗ Failed to list interfaces: {iface_result.get('error')}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error listing interfaces: {str(e)}'))

        # 3c. List hotspot interfaces
        self.stdout.write('\n3c. Listing hotspot interfaces...')
        try:
            hotspot_result = get_hotspot_interfaces()
            if hotspot_result.get('success'):
                hotspots = hotspot_result.get('data', [])
                if not hotspots:
                    self.stdout.write(self.style.WARNING('⚠ No hotspot interfaces found'))
                else:
                    for i, hs in enumerate(hotspots, 1):
                        self.stdout.write(f"  {i}. {hs.get('name')}\tInterface: {hs.get('interface')}\tPool: {hs.get('address_pool')}\tDisabled: {hs.get('disabled')}")
                    self.stdout.write(self.style.SUCCESS(f'✓ Found {len(hotspots)} hotspot interface(s)'))
            else:
                self.stdout.write(self.style.ERROR(f"✗ Failed to list hotspot interfaces: {hotspot_result.get('error')}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error listing hotspot interfaces: {str(e)}'))

        # 3d. Test hotspot-specific active users
        self.stdout.write('\n3d. Testing hotspot-specific active users...')
        try:
            hotspot_name = getattr(settings, 'MIKROTIK_HOTSPOT_NAME', 'hotspot1')
            hotspot_users_result = get_hotspot_active_users_by_interface(hotspot_name)
            if hotspot_users_result.get('success'):
                users = hotspot_users_result.get('data', [])
                self.stdout.write(self.style.SUCCESS(f'✓ Found {len(users)} active user(s) on hotspot "{hotspot_name}"'))
                if users:
                    for i, user in enumerate(users[:3], 1):  # Show first 3 users
                        self.stdout.write(f"  {i}. {user.get('user')} ({user.get('address')}) Server: {user.get('server')}")
            else:
                self.stdout.write(self.style.ERROR(f"✗ Failed to get users for hotspot {hotspot_name}: {hotspot_users_result.get('error')}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error getting hotspot users: {str(e)}'))

        # Test 4: Test authentication (this will fail if user doesn't exist in Django)
        self.stdout.write('\n4. Testing authentication flow...')
        try:
            result = authenticate_user_with_mikrotik(test_user, 'aa:bb:cc:dd:ee:ff', '192.168.88.100')
            if result.get('success'):
                self.stdout.write(self.style.SUCCESS(f'✓ Authentication test: {result.get("message", "Success")}'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠ Authentication test: {result.get("message", "Failed")}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error in authentication test: {str(e)}'))
        
        # Test 5: Check API port accessibility
        self.stdout.write('\n5. Testing API port accessibility...')
        try:
            api_port = getattr(settings, 'MIKROTIK_PORT', 8728)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((router_ip, api_port))
            sock.close()
            
            if result == 0:
                self.stdout.write(self.style.SUCCESS(f'✓ API port {api_port} is accessible'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠ API port {api_port} is not accessible (this is normal if API is disabled)'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error testing API port: {str(e)}'))
        
        # Test configuration summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('Configuration Summary:'))
        self.stdout.write(f'Router Host: {getattr(settings, "MIKROTIK_HOST", "N/A")}')
        self.stdout.write(f'API Port: {getattr(settings, "MIKROTIK_PORT", 8728)}')
        self.stdout.write(f'Use SSL: {getattr(settings, "MIKROTIK_USE_SSL", False)} (verify={getattr(settings, "MIKROTIK_SSL_VERIFY", False)})')
        self.stdout.write(f'Admin User: {getattr(settings, "MIKROTIK_USER", "admin")}')
        self.stdout.write(f'Admin Pass: {"Set" if getattr(settings, "MIKROTIK_PASSWORD", "") else "Not Set"}')
        self.stdout.write(f'Hotspot Name: {getattr(settings, "MIKROTIK_HOTSPOT_NAME", "hotspot1")}')
        self.stdout.write(f'Default Profile: {getattr(settings, "MIKROTIK_DEFAULT_PROFILE", "default")}')
        self.stdout.write(f'Hotspot Name: {getattr(settings, "MIKROTIK_HOTSPOT_NAME", "hotspot1")}')
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('Next Steps:'))
        self.stdout.write('1. Configure your Mikrotik router with external HTTP authentication')
        self.stdout.write('2. Set the authentication URL to: http://your-django-server/api/mikrotik/auth/')
        self.stdout.write('3. Test with a real user that exists in your Django database')
        self.stdout.write('4. Monitor logs for authentication attempts')
