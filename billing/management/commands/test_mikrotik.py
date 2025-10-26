"""
Management command to test Mikrotik router connectivity and authentication
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from billing.mikrotik import MikrotikIntegration, get_mikrotik_client
import requests


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
            default='255700000000',
            help='Test phone number for authentication (default: 255700000000)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Testing Mikrotik Router Connectivity\n'))
        
        # Get router IP
        router_ip = options.get('router_ip') or getattr(settings, 'MIKROTIK_ROUTER_IP', '192.168.88.1')
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
        
        # Test 3: Test Mikrotik integration class
        self.stdout.write('\n3. Testing Mikrotik integration class...')
        try:
            mikrotik = get_mikrotik_client()
            self.stdout.write(f'✓ Mikrotik client created successfully')
            self.stdout.write(f'  - Router IP: {mikrotik.router_ip}')
            self.stdout.write(f'  - Admin User: {mikrotik.admin_user}')
            self.stdout.write(f'  - Login URL: {mikrotik.login_url}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error creating Mikrotik client: {str(e)}'))
            return
        
        # Test 4: Test authentication (this will fail if user doesn't exist in Django)
        self.stdout.write('\n4. Testing authentication flow...')
        try:
            result = mikrotik.login_user_to_hotspot(test_user, 'aa:bb:cc:dd:ee:ff', '192.168.88.100')
            if result['success']:
                self.stdout.write(self.style.SUCCESS(f'✓ Authentication test: {result["message"]}'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠ Authentication test: {result["message"]}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error in authentication test: {str(e)}'))
        
        # Test 5: Check API port accessibility
        self.stdout.write('\n5. Testing API port accessibility...')
        try:
            import socket
            api_port = getattr(settings, 'MIKROTIK_API_PORT', 8728)
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
        self.stdout.write(f'Router IP: {router_ip}')
        self.stdout.write(f'Admin User: {getattr(settings, "MIKROTIK_ADMIN_USER", "admin")}')
        self.stdout.write(f'Admin Pass: {"Set" if getattr(settings, "MIKROTIK_ADMIN_PASS", "") else "Not Set"}')
        self.stdout.write(f'API Port: {getattr(settings, "MIKROTIK_API_PORT", 8728)}')
        self.stdout.write(f'Hotspot Name: {getattr(settings, "MIKROTIK_HOTSPOT_NAME", "hotspot1")}')
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('Next Steps:'))
        self.stdout.write('1. Configure your Mikrotik router with external HTTP authentication')
        self.stdout.write('2. Set the authentication URL to: http://your-django-server/api/mikrotik/auth/')
        self.stdout.write('3. Test with a real user that exists in your Django database')
        self.stdout.write('4. Monitor logs for authentication attempts')
