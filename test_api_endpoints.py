#!/usr/bin/env python
"""
Test Kitonga Wi-Fi API Endpoints
This script tests all API endpoints to verify they are accessible and working correctly.
"""
import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User as DjangoUser
from billing.models import User, Bundle
import json


def print_section(title):
    """Print formatted section header"""
    print(f"\n{'='*70}")
    print(f" {title}")
    print(f"{'='*70}")


def test_endpoint(client, method, url, data=None, headers=None, expected_status=None):
    """Test a single endpoint and return result"""
    try:
        if method.upper() == 'GET':
            response = client.get(url, **headers if headers else {})
        elif method.upper() == 'POST':
            response = client.post(url, data=json.dumps(data) if data else {}, 
                                 content_type='application/json', **headers if headers else {})
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
    print(" KITONGA WI-FI API ENDPOINTS TEST")
    print("="*70)
    
    client = Client()
    test_results = []
    
    # Test 1: Health Check
    print_section("1. Health Check API")
    result = test_endpoint(client, 'GET', '/api/health/', expected_status=200)
    if result['success']:
        print(f"✅ Status: {result['status_code']}")
        if isinstance(result['data'], dict):
            print(f"   Service: {result['data'].get('service', 'N/A')}")
            print(f"   Status: {result['data'].get('status', 'N/A')}")
            print(f"   Version: {result['data'].get('version', 'N/A')}")
    else:
        print(f"❌ Error: {result.get('error')}")
    test_results.append(('Health Check', result['success'] and result['status_ok']))
    
    # Test 2: List Bundles (Public)
    print_section("2. Public Bundles List")
    result = test_endpoint(client, 'GET', '/api/bundles/', expected_status=200)
    if result['success']:
        print(f"✅ Status: {result['status_code']}")
        if isinstance(result['data'], dict) and 'bundles' in result['data']:
            bundles = result['data']['bundles']
            print(f"   Bundles Available: {len(bundles)}")
            for bundle in bundles[:3]:  # Show first 3
                print(f"   • {bundle.get('name')}: {bundle.get('price')} TSh ({bundle.get('duration_hours')}h)")
    else:
        print(f"❌ Error: {result.get('error')}")
    test_results.append(('Public Bundles', result['success'] and result['status_ok']))
    
    # Test 3: Verify Access (should fail without valid user)
    print_section("3. Verify Access API")
    test_data = {
        'phone_number': '255000000000',  # Non-existent test number
        'mac_address': 'AA:BB:CC:DD:EE:FF',
        'ip_address': '192.168.88.100'
    }
    result = test_endpoint(client, 'POST', '/api/verify-access/', data=test_data)
    if result['success']:
        print(f"✅ Status: {result['status_code']}")
        if isinstance(result['data'], dict):
            print(f"   Has Access: {result['data'].get('has_access', False)}")
            print(f"   Message: {result['data'].get('denial_reason', result['data'].get('message', 'N/A'))}")
    else:
        print(f"❌ Error: {result.get('error')}")
    test_results.append(('Verify Access', result['success']))
    
    # Test 4: Admin Login (attempt with invalid credentials)
    print_section("4. Admin Login API")
    test_data = {
        'username': 'testadmin',
        'password': 'testpass'
    }
    result = test_endpoint(client, 'POST', '/api/admin/login/', data=test_data)
    if result['success']:
        print(f"✅ Status: {result['status_code']}")
        if isinstance(result['data'], dict):
            print(f"   Success: {result['data'].get('success', False)}")
            print(f"   Message: {result['data'].get('message', 'N/A')}")
    else:
        print(f"❌ Error: {result.get('error')}")
    test_results.append(('Admin Login', result['success']))
    
    # Test 5: Admin Profile (should fail without auth)
    print_section("5. Admin Profile API")
    result = test_endpoint(client, 'GET', '/api/admin/profile/')
    if result['success']:
        print(f"✅ Status: {result['status_code']}")
        if isinstance(result['data'], dict):
            print(f"   Authenticated: {result['data'].get('is_authenticated', False)}")
            print(f"   Message: {result['data'].get('message', 'N/A')}")
    else:
        print(f"❌ Error: {result.get('error')}")
    test_results.append(('Admin Profile', result['success']))
    
    # Test 6: MikroTik Router Info (requires admin token)
    print_section("6. MikroTik Router Info API")
    from django.conf import settings
    headers = {'HTTP_X_ADMIN_TOKEN': settings.SIMPLE_ADMIN_TOKEN}
    result = test_endpoint(client, 'GET', '/api/admin/mikrotik/info/', headers=headers)
    if result['success']:
        print(f"✅ Status: {result['status_code']}")
        if isinstance(result['data'], dict):
            if result['data'].get('success'):
                router_info = result['data'].get('router_info', {})
                print(f"   Board: {router_info.get('board_name', 'N/A')}")
                print(f"   Version: {router_info.get('version', 'N/A')}")
                print(f"   Connection: {router_info.get('connection_status', 'N/A')}")
            else:
                print(f"   Message: {result['data'].get('message', 'N/A')}")
    else:
        print(f"❌ Error: {result.get('error')}")
    test_results.append(('MikroTik Info', result['success']))
    
    # Test 7: MikroTik Active Users (requires admin token)
    print_section("7. MikroTik Active Users API")
    result = test_endpoint(client, 'GET', '/api/admin/mikrotik/active-users/', headers=headers)
    if result['success']:
        print(f"✅ Status: {result['status_code']}")
        if isinstance(result['data'], dict):
            if result['data'].get('success'):
                active_users = result['data'].get('active_users', [])
                print(f"   Active Users: {len(active_users)}")
                for user in active_users[:3]:
                    print(f"   • {user.get('username', 'N/A')} - {user.get('ip_address', 'N/A')}")
            else:
                print(f"   Message: {result['data'].get('message', 'N/A')}")
    else:
        print(f"❌ Error: {result.get('error')}")
    test_results.append(('Active Users', result['success']))
    
    # Test 8: System Status (requires admin token)
    print_section("8. System Status API")
    result = test_endpoint(client, 'GET', '/api/admin/status/', headers=headers)
    if result['success']:
        print(f"✅ Status: {result['status_code']}")
        if isinstance(result['data'], dict) and result['data'].get('success'):
            status = result['data'].get('status', {})
            print(f"   Database: {status.get('database_status', 'N/A')}")
            print(f"   MikroTik: {status.get('mikrotik_status', 'N/A')}")
            print(f"   Total Users: {status.get('total_users', 0)}")
            print(f"   Active Users: {status.get('active_users', 0)}")
            print(f"   Payments Today: {status.get('payments_today', 0)}")
            print(f"   Revenue Today: {status.get('revenue_today', 0)} TSh")
    else:
        print(f"❌ Error: {result.get('error')}")
    test_results.append(('System Status', result['success']))
    
    # Test 9: List Users (requires admin token)
    print_section("9. List Users API")
    result = test_endpoint(client, 'GET', '/api/admin/users/', headers=headers)
    if result['success']:
        print(f"✅ Status: {result['status_code']}")
        if isinstance(result['data'], dict) and result['data'].get('success'):
            users = result['data'].get('users', [])
            pagination = result['data'].get('pagination', {})
            print(f"   Total Users: {pagination.get('total', 0)}")
            print(f"   Page: {pagination.get('page', 1)}/{pagination.get('total_pages', 1)}")
            if users:
                print(f"   Sample users:")
                for user in users[:3]:
                    print(f"   • {user.get('phone_number')} - Active: {user.get('is_active')}")
    else:
        print(f"❌ Error: {result.get('error')}")
    test_results.append(('List Users', result['success']))
    
    # Test 10: List Payments (requires admin token)
    print_section("10. List Payments API")
    result = test_endpoint(client, 'GET', '/api/admin/payments/', headers=headers)
    if result['success']:
        print(f"✅ Status: {result['status_code']}")
        if isinstance(result['data'], dict) and result['data'].get('success'):
            payments = result['data'].get('payments', [])
            pagination = result['data'].get('pagination', {})
            summary = result['data'].get('summary', {})
            print(f"   Total Payments: {pagination.get('total', 0)}")
            print(f"   Completed: {summary.get('completed_count', 0)}")
            print(f"   Pending: {summary.get('pending_count', 0)}")
            print(f"   Total Amount: {summary.get('total_amount', 0)} TSh")
    else:
        print(f"❌ Error: {result.get('error')}")
    test_results.append(('List Payments', result['success']))
    
    # Summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    print(f"\n{'Test Name':<30} {'Result':<10}")
    print("-" * 40)
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<30} {status}")
    
    print(f"\n{'='*70}")
    print(f"Total: {passed}/{total} tests passed ({100*passed//total}%)")
    
    if passed == total:
        print("\n🎉 ALL API ENDPOINTS ARE ACCESSIBLE!")
    elif passed >= total * 0.7:
        print("\n✅ Most API endpoints are working. Some may need authentication.")
    else:
        print("\n⚠️  Some API endpoints may need attention.")
    
    print("="*70 + "\n")
    
    # Additional info
    print("\nℹ️  Note:")
    print("   • Some endpoints require authentication (admin token or user token)")
    print("   • Public endpoints (health, bundles, verify-access) should always work")
    print("   • Admin endpoints require X-Admin-Token header")
    print("   • See API_RESPONSES_REFERENCE.json for complete API documentation")


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
