#!/usr/bin/env python
"""
Test MikroTik API Connection
This script tests the connection to your MikroTik router and displays diagnostic information.
"""
import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from django.conf import settings
from billing.mikrotik import test_mikrotik_connection, get_router_info, get_active_hotspot_users
import socket


def test_tcp_connection(host, port):
    """Test basic TCP connectivity"""
    print(f"\n{'='*60}")
    print(f"Testing TCP Connection to {host}:{port}")
    print(f"{'='*60}")
    
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(5)
        result = test_socket.connect_ex((host, port))
        test_socket.close()
        
        if result == 0:
            print(f"✅ TCP Port {port} is OPEN and reachable")
            return True
        else:
            print(f"❌ TCP Port {port} is CLOSED or unreachable (Error code: {result})")
            return False
    except socket.gaierror as e:
        print(f"❌ DNS/Host resolution failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False


def test_router_api():
    """Test MikroTik RouterOS API connection"""
    print(f"\n{'='*60}")
    print("Testing MikroTik RouterOS API")
    print(f"{'='*60}")
    
    try:
        result = test_mikrotik_connection()
        
        if result['success']:
            print("✅ MikroTik API connection SUCCESSFUL!")
            print(f"\nRouter Information:")
            router_info = result.get('router_info', {})
            print(f"  • IP Address: {router_info.get('ip', 'N/A')}")
            print(f"  • Port: {router_info.get('port', 'N/A')}")
            print(f"  • Status: {router_info.get('status', 'N/A')}")
            print(f"  • API Status: {router_info.get('api_status', 'N/A')}")
            return True
        else:
            print(f"❌ MikroTik API connection FAILED")
            print(f"   Error: {result.get('message', 'Unknown error')}")
            if 'error' in result:
                print(f"   Details: {result['error']}")
            return False
    except Exception as e:
        print(f"❌ API test error: {e}")
        import traceback
        print(f"\nTraceback:")
        traceback.print_exc()
        return False


def test_router_system_info():
    """Get detailed router system information"""
    print(f"\n{'='*60}")
    print("Getting Router System Information")
    print(f"{'='*60}")
    
    try:
        result = get_router_info()
        
        if result['success']:
            print("✅ Successfully retrieved router information!")
            data = result.get('data', {})
            
            if data:
                print(f"\nSystem Details:")
                print(f"  • Board Name: {data.get('board_name', 'N/A')}")
                print(f"  • Version: {data.get('version', 'N/A')}")
                print(f"  • Platform: {data.get('platform', 'N/A')}")
                print(f"  • Uptime: {data.get('uptime', 'N/A')}")
                print(f"  • CPU Load: {data.get('cpu_load', 'N/A')}")
                print(f"  • Free Memory: {data.get('free_memory', 'N/A')}")
                print(f"  • Total Memory: {data.get('total_memory', 'N/A')}")
                print(f"  • Connection Status: {data.get('connection_status', 'N/A')}")
            else:
                print("⚠️  No detailed system information available")
            return True
        else:
            print(f"❌ Failed to get router information")
            print(f"   Error: {result.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ System info error: {e}")
        return False


def test_active_users():
    """Get active hotspot users"""
    print(f"\n{'='*60}")
    print("Getting Active Hotspot Users")
    print(f"{'='*60}")
    
    try:
        result = get_active_hotspot_users()
        
        if result['success']:
            users = result.get('data', [])
            print(f"✅ Successfully retrieved active users!")
            print(f"\nActive Users Count: {len(users)}")
            
            if users:
                print(f"\nActive Users List:")
                for i, user in enumerate(users, 1):
                    print(f"\n  User #{i}:")
                    print(f"    • Username: {user.get('user', 'N/A')}")
                    print(f"    • IP Address: {user.get('address', 'N/A')}")
                    print(f"    • MAC Address: {user.get('mac_address', 'N/A')}")
                    print(f"    • Uptime: {user.get('uptime', 'N/A')}")
                    print(f"    • Bytes In: {user.get('bytes_in', 'N/A')}")
                    print(f"    • Bytes Out: {user.get('bytes_out', 'N/A')}")
            else:
                print("  No active users at the moment")
            return True
        else:
            print(f"❌ Failed to get active users")
            print(f"   Error: {result.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Active users error: {e}")
        return False


def main():
    """Main test function"""
    print("\n" + "="*60)
    print("KITONGA WI-FI MIKROTIK CONNECTION TEST")
    print("="*60)
    
    # Display configuration
    print(f"\nConfiguration:")
    print(f"  • Host: {settings.MIKROTIK_HOST}")
    print(f"  • Port: {settings.MIKROTIK_PORT}")
    print(f"  • Username: {settings.MIKROTIK_USER}")
    print(f"  • Password: {'*' * len(settings.MIKROTIK_PASSWORD)}")
    print(f"  • Use SSL: {settings.MIKROTIK_USE_SSL}")
    print(f"  • Default Profile: {settings.MIKROTIK_DEFAULT_PROFILE}")
    
    # Run tests
    test_results = []
    
    # Test 1: TCP Connection
    tcp_ok = test_tcp_connection(settings.MIKROTIK_HOST, settings.MIKROTIK_PORT)
    test_results.append(('TCP Connection', tcp_ok))
    
    if not tcp_ok:
        print("\n⚠️  WARNING: TCP connection failed. Please check:")
        print("   1. Router IP address is correct")
        print("   2. Router API port (8728) is enabled")
        print("   3. Network connectivity between server and router")
        print("   4. Firewall rules allow API access")
    
    # Test 2: API Connection
    api_ok = test_router_api()
    test_results.append(('API Connection', api_ok))
    
    if tcp_ok and not api_ok:
        print("\n⚠️  WARNING: TCP works but API failed. Please check:")
        print("   1. API service is enabled on router (/ip service print)")
        print("   2. Username and password are correct")
        print("   3. User has API permissions")
    
    # Test 3: Router System Info
    if api_ok:
        info_ok = test_router_system_info()
        test_results.append(('System Info', info_ok))
        
        # Test 4: Active Users
        users_ok = test_active_users()
        test_results.append(('Active Users', users_ok))
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:.<40} {status}")
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! MikroTik connection is working perfectly!")
    elif tcp_ok and api_ok:
        print("\n✅ Core connectivity is working. Some advanced features may need configuration.")
    else:
        print("\n❌ Connection issues detected. Please review the warnings above.")
    
    print("\n" + "="*60)


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
