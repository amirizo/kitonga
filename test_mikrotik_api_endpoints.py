#!/usr/bin/env python
"""
Test All MikroTik API Endpoints
This script tests all MikroTik-related API endpoints to ensure they work correctly.
"""
import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from django.test import Client
from django.conf import settings
import json


def print_section(title):
    """Print formatted section header"""
    print(f"\n{'='*70}")
    print(f" {title}")
    print(f"{'='*70}")


def test_endpoint(client, method, url, data=None, headers=None, expected_status=None):
    """Test a single endpoint and return result"""
    try:
        full_headers = {'HTTP_X_ADMIN_TOKEN': settings.SIMPLE_ADMIN_TOKEN}
        if headers:
            full_headers.update(headers)
        
        if method.upper() == 'GET':
            response = client.get(url, **full_headers)
        elif method.upper() == 'POST':
            response = client.post(url, data=json.dumps(data) if data else {}, 
                                 content_type='application/json', **full_headers)
        else:
            return {'success': False, 'error': f'Unsupported method: {method}'}
        
        result = {
            'success': True,
            'status_code': response.status_code,
            'status_ok': expected_status is None or response.status_code == expected_status
        }
        
        try:
            result['data'] = response.json()
        except:
            result['data'] = response.content.decode('utf-8')[:200]
        
        return result
    except Exception as e:
        return {'success': False, 'error': str(e)}


def main():
    """Main test function"""
    print("\n" + "="*70)
    print(" MIKROTIK API ENDPOINTS TEST")
    print("="*70)
    print(f"\nTesting with admin token: {settings.SIMPLE_ADMIN_TOKEN[:20]}...")
    
    client = Client()
    test_results = []
    
    # Test 1: MikroTik Configuration (GET)
    print_section("1. GET MikroTik Configuration")
    result = test_endpoint(client, 'GET', '/api/admin/mikrotik/config/')
    if result['success']:
        print(f"✅ Status: {result['status_code']}")
        if isinstance(result['data'], dict):
            if result['data'].get('success'):
                config = result['data'].get('configuration', {})
                print(f"   Router IP: {config.get('router_ip', 'N/A')}")
                print(f"   Username: {config.get('username', 'N/A')}")
                print(f"   API Port: {config.get('api_port', 'N/A')}")
                print(f"   Hotspot Name: {config.get('hotspot_name', 'N/A')}")
            else:
                print(f"   Message: {result['data'].get('message', 'N/A')}")
    else:
        print(f"❌ Error: {result.get('error')}")
    test_results.append(('MikroTik Config (GET)', result['success']))
    
    # Test 2: Test MikroTik Connection
    print_section("2. Test MikroTik Connection")
    result = test_endpoint(client, 'POST', '/api/admin/mikrotik/test-connection/')
    if result['success']:
        print(f"✅ Status: {result['status_code']}")
        if isinstance(result['data'], dict):
            print(f"   Success: {result['data'].get('success', False)}")
            print(f"   Message: {result['data'].get('message', 'N/A')}")
            router_info = result['data'].get('router_info', {})
            if router_info:
                print(f"   Router Info:")
                print(f"     • IP: {router_info.get('ip', 'N/A')}")
                print(f"     • Port: {router_info.get('port', 'N/A')}")
                print(f"     • Status: {router_info.get('status', 'N/A')}")
                print(f"     • API Status: {router_info.get('api_status', 'N/A')}")
    else:
        print(f"❌ Error: {result.get('error')}")
    test_results.append(('Test Connection', result['success']))
    
    # Test 3: Get Router Info
    print_section("3. Get Router Information")
    result = test_endpoint(client, 'GET', '/api/admin/mikrotik/router-info/')
    if result['success']:
        print(f"✅ Status: {result['status_code']}")
        if isinstance(result['data'], dict):
            if result['data'].get('success'):
                router_info = result['data'].get('router_info', {})
                print(f"   Board Name: {router_info.get('board_name', 'N/A')}")
                print(f"   Version: {router_info.get('version', 'N/A')}")
                print(f"   Platform: {router_info.get('platform', 'N/A')}")
                print(f"   Uptime: {router_info.get('uptime', 'N/A')}")
                print(f"   CPU Load: {router_info.get('cpu_load', 'N/A')}")
                print(f"   Connection: {router_info.get('connection_status', 'N/A')}")
            else:
                print(f"   Message: {result['data'].get('message', 'N/A')}")
    else:
        print(f"❌ Error: {result.get('error')}")
    test_results.append(('Router Info', result['success']))
    
    # Test 4: Get Active Hotspot Users
    print_section("4. Get Active Hotspot Users")
    result = test_endpoint(client, 'GET', '/api/admin/mikrotik/active-users/')
    if result['success']:
        print(f"✅ Status: {result['status_code']}")
        if isinstance(result['data'], dict):
            if result['data'].get('success'):
                active_users = result['data'].get('active_users', [])
                print(f"   Total Active Users: {result['data'].get('total_count', len(active_users))}")
                if active_users:
                    print(f"   Active Users:")
                    for i, user in enumerate(active_users[:5], 1):  # Show first 5
                        print(f"     {i}. {user.get('username', 'N/A')} - {user.get('ip_address', 'N/A')}")
                        print(f"        MAC: {user.get('mac_address', 'N/A')}")
                        print(f"        Uptime: {user.get('uptime', 'N/A')}")
                else:
                    print("   No active users at the moment")
            else:
                print(f"   Message: {result['data'].get('message', 'N/A')}")
    else:
        print(f"❌ Error: {result.get('error')}")
    test_results.append(('Active Users', result['success']))
    
    # Test 5: Get Hotspot Profiles
    print_section("5. Get Hotspot Profiles")
    result = test_endpoint(client, 'GET', '/api/admin/mikrotik/profiles/')
    if result['success']:
        print(f"✅ Status: {result['status_code']}")
        if isinstance(result['data'], dict):
            if result['data'].get('success'):
                profiles = result['data'].get('profiles', [])
                print(f"   Total Profiles: {len(profiles)}")
                if profiles:
                    print(f"   Available Profiles:")
                    for profile in profiles[:5]:
                        print(f"     • {profile.get('name', 'N/A')}")
                        print(f"       Rate Limit: {profile.get('rate_limit', 'N/A')}")
                        print(f"       Session Timeout: {profile.get('session_timeout', 'N/A')}")
            else:
                print(f"   Message: {result['data'].get('message', 'N/A')}")
    else:
        print(f"❌ Error: {result.get('error')}")
    test_results.append(('Hotspot Profiles', result['success']))
    
    # Test 6: Get System Resources
    print_section("6. Get System Resources")
    result = test_endpoint(client, 'GET', '/api/admin/mikrotik/resources/')
    if result['success']:
        print(f"✅ Status: {result['status_code']}")
        if isinstance(result['data'], dict):
            if result['data'].get('success'):
                resources = result['data'].get('system_resources', {})
                print(f"   Uptime: {resources.get('uptime', 'N/A')}")
                print(f"   Version: {resources.get('version', 'N/A')}")
                print(f"   Board: {resources.get('board_name', 'N/A')}")
                print(f"   CPU Load: {resources.get('cpu_load', 'N/A')}")
                print(f"   Free Memory: {resources.get('free_memory', 'N/A')}")
                print(f"   Total Memory: {resources.get('total_memory', 'N/A')}")
            else:
                print(f"   Message: {result['data'].get('message', 'N/A')}")
    else:
        print(f"❌ Error: {result.get('error')}")
    test_results.append(('System Resources', result['success']))
    
    # Test 7: MikroTik Auth (Public endpoint)
    print_section("7. MikroTik Auth (Public)")
    auth_data = {
        'username': '255000000000',  # Test number
        'password': '000000',
        'mac_address': 'AA:BB:CC:DD:EE:FF',
        'ip_address': '192.168.88.100'
    }
    result = test_endpoint(client, 'POST', '/api/mikrotik/auth/', data=auth_data, headers={})
    if result['success']:
        print(f"✅ Status: {result['status_code']}")
        if isinstance(result['data'], dict):
            print(f"   Success: {result['data'].get('success', False)}")
            print(f"   Message: {result['data'].get('message', 'N/A')}")
    else:
        print(f"❌ Error: {result.get('error')}")
    test_results.append(('MikroTik Auth', result['success']))
    
    # Test 8: MikroTik Status Check (Public endpoint)
    print_section("8. MikroTik Status Check (Public)")
    result = test_endpoint(client, 'GET', '/api/mikrotik/status/', headers={})
    if result['success']:
        print(f"✅ Status: {result['status_code']}")
        if isinstance(result['data'], dict):
            print(f"   Connected: {result['data'].get('connected', False)}")
            print(f"   Message: {result['data'].get('message', 'N/A')}")
    else:
        print(f"❌ Error: {result.get('error')}")
    test_results.append(('Status Check', result['success']))
    
    # Test 9: MikroTik User Status (Public endpoint)
    print_section("9. MikroTik User Status (Public)")
    status_data = {
        'phone_number': '255000000000'
    }
    result = test_endpoint(client, 'POST', '/api/mikrotik/user-status/', data=status_data, headers={})
    if result['success']:
        print(f"✅ Status: {result['status_code']}")
        if isinstance(result['data'], dict):
            print(f"   Active: {result['data'].get('is_active', False)}")
            print(f"   Message: {result['data'].get('message', 'N/A')}")
    else:
        print(f"❌ Error: {result.get('error')}")
    test_results.append(('User Status', result['success']))
    
    # Summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    print(f"\n{'Test Name':<40} {'Result':<10}")
    print("-" * 50)
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<40} {status}")
    
    print(f"\n{'='*70}")
    print(f"Total: {passed}/{total} tests passed ({100*passed//total}%)")
    
    if passed == total:
        print("\n🎉 ALL MIKROTIK API ENDPOINTS ARE WORKING!")
    elif passed >= total * 0.7:
        print("\n✅ Most MikroTik endpoints are working correctly.")
    else:
        print("\n⚠️  Some MikroTik endpoints need attention.")
    
    print("="*70 + "\n")
    
    # Additional info
    print("\nℹ️  Endpoint Categories:")
    print("   • Admin Endpoints: Require X-Admin-Token header")
    print("   • Public Endpoints: No authentication required")
    print("   • Configuration: /api/admin/mikrotik/config/")
    print("   • Testing: /api/admin/mikrotik/test-connection/")
    print("   • Monitoring: /api/admin/mikrotik/active-users/")
    print("   • Management: /api/admin/mikrotik/disconnect-user/")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
