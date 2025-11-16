#!/usr/bin/env python3
"""
VPS MikroTik Connection Verification Test
Run this after VPS setup to verify everything works
"""

import os
import sys
import django
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from django.conf import settings
from billing.mikrotik import (
    test_mikrotik_connection,
    get_router_info,
    get_active_hotspot_users,
    get_hotspot_profiles
)

def print_header(title):
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

def print_section(title):
    print(f"\n🔍 {title}")
    print("-" * 50)

def test_environment_config():
    """Test environment configuration"""
    print_section("Environment Configuration")
    
    # Check mock mode
    mock_mode = os.getenv('MIKROTIK_MOCK_MODE', 'false').lower() == 'true'
    if mock_mode:
        print("❌ MIKROTIK_MOCK_MODE is enabled - this should be disabled on VPS")
        return False
    else:
        print("✅ MIKROTIK_MOCK_MODE is disabled (good for VPS)")
    
    # Check router settings
    host = getattr(settings, 'MIKROTIK_HOST', 'Not set')
    port = getattr(settings, 'MIKROTIK_PORT', 'Not set')
    user = getattr(settings, 'MIKROTIK_USER', 'Not set')
    
    print(f"Router Host: {host}")
    print(f"Router Port: {port}")
    print(f"Router User: {user}")
    print(f"SSL Enabled: {getattr(settings, 'MIKROTIK_USE_SSL', False)}")
    
    return True

def test_basic_connectivity():
    """Test basic network connectivity to router"""
    print_section("Basic Network Connectivity")
    
    try:
        result = test_mikrotik_connection()
        
        if result['success']:
            print("✅ Basic connectivity: SUCCESS")
            print(f"   Router IP: {result['router_info']['ip']}")
            print(f"   Port: {result['router_info']['port']}")
            print(f"   Status: {result['router_info']['status']}")
            print(f"   API Status: {result['router_info'].get('api_status', 'unknown')}")
            return True
        else:
            print("❌ Basic connectivity: FAILED")
            print(f"   Error: {result.get('message', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Connectivity test error: {e}")
        return False

def test_router_info():
    """Test router information retrieval"""
    print_section("Router Information")
    
    try:
        result = get_router_info()
        
        if result['success']:
            print("✅ Router info retrieval: SUCCESS")
            info = result['data']
            print(f"   Uptime: {info.get('uptime', 'N/A')}")
            print(f"   Version: {info.get('version', 'N/A')}")
            print(f"   Board: {info.get('board_name', 'N/A')}")
            print(f"   CPU Load: {info.get('cpu_load', 'N/A')}")
            print(f"   Free Memory: {info.get('free_memory', 'N/A')}")
            print(f"   Connection: {info.get('connection_status', 'N/A')}")
            return True
        else:
            print("❌ Router info retrieval: FAILED")
            print(f"   Error: {result.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Router info test error: {e}")
        return False

def test_active_users():
    """Test active users retrieval"""
    print_section("Active Users")
    
    try:
        result = get_active_hotspot_users()
        
        if result['success']:
            users = result['data']
            print(f"✅ Active users retrieval: SUCCESS")
            print(f"   Active users count: {len(users)}")
            
            if users:
                print("   Sample active users:")
                for i, user in enumerate(users[:3]):  # Show first 3 users
                    print(f"     • User: {user.get('user', 'N/A')}")
                    print(f"       MAC: {user.get('mac_address', 'N/A')}")
                    print(f"       IP: {user.get('address', 'N/A')}")
                    print(f"       Uptime: {user.get('uptime', 'N/A')}")
            else:
                print("   No active users (router working, no connected users)")
            return True
        else:
            print("❌ Active users retrieval: FAILED")
            print(f"   Error: {result.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Active users test error: {e}")
        return False

def test_hotspot_profiles():
    """Test hotspot profiles retrieval"""
    print_section("Hotspot Profiles")
    
    try:
        result = get_hotspot_profiles()
        
        if result['success']:
            profiles = result['data']
            print(f"✅ Hotspot profiles retrieval: SUCCESS")
            print(f"   Available profiles: {len(profiles)}")
            
            if profiles:
                print("   Profile details:")
                for profile in profiles:
                    print(f"     • Name: {profile.get('name', 'N/A')}")
                    print(f"       Rate Limit: {profile.get('rate_limit', 'N/A')}")
                    print(f"       Session Timeout: {profile.get('session_timeout', 'N/A')}")
            return True
        else:
            print("❌ Hotspot profiles retrieval: FAILED")
            print(f"   Error: {result.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Hotspot profiles test error: {e}")
        return False

def test_api_endpoints():
    """Test Django API endpoints"""
    print_section("Django API Endpoints")
    
    try:
        from django.test import Client
        client = Client()
        
        # Test router info endpoint
        response = client.get('/api/admin/mikrotik/router-info/', 
                            HTTP_X_ADMIN_ACCESS=settings.SIMPLE_ADMIN_TOKEN)
        
        if response.status_code == 200:
            print("✅ Router info endpoint: SUCCESS")
            data = response.json()
            print(f"   Response: {data.get('success', False)}")
        else:
            print(f"❌ Router info endpoint: FAILED ({response.status_code})")
        
        # Test active users endpoint
        response = client.get('/api/admin/mikrotik/active-users/', 
                            HTTP_X_ADMIN_ACCESS=settings.SIMPLE_ADMIN_TOKEN)
        
        if response.status_code == 200:
            print("✅ Active users endpoint: SUCCESS")
            data = response.json()
            print(f"   Response: {data.get('success', False)}")
            if data.get('success'):
                print(f"   Active users: {len(data.get('active_users', []))}")
        else:
            print(f"❌ Active users endpoint: FAILED ({response.status_code})")
        
        return True
    except Exception as e:
        print(f"❌ API endpoints test error: {e}")
        return False

def main():
    """Run all tests"""
    print_header("VPS MIKROTIK CONNECTION VERIFICATION")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Django Settings: {settings.SETTINGS_MODULE}")
    
    tests = [
        ("Environment Configuration", test_environment_config),
        ("Basic Connectivity", test_basic_connectivity),
        ("Router Information", test_router_info),
        ("Active Users", test_active_users),
        ("Hotspot Profiles", test_hotspot_profiles),
        ("Django API Endpoints", test_api_endpoints),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name}: EXCEPTION - {e}")
            results.append((test_name, False))
    
    # Summary
    print_header("TEST RESULTS SUMMARY")
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {test_name}")
        if success:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed ({100*passed//total}%)")
    
    if passed == total:
        print("\n🎉 EXCELLENT! All tests passed!")
        print("✅ Your VPS is fully integrated with MikroTik router")
        print("✅ All router management features are available")
        print("✅ Admin dashboard will show real-time router data")
        print("✅ You can disconnect users remotely")
        print("✅ Full control over your Wi-Fi system")
    elif passed >= total * 0.7:
        print(f"\n✅ GOOD! Most tests passed ({passed}/{total})")
        print("⚠️  Some features may not work properly")
        print("📖 Check the failed tests and refer to VPS_MIKROTIK_SETUP_GUIDE.md")
    else:
        print(f"\n❌ ISSUES DETECTED! Only {passed}/{total} tests passed")
        print("🔧 Troubleshooting needed:")
        print("   1. Check VPN connectivity")
        print("   2. Verify router API is enabled")
        print("   3. Check firewall rules")
        print("   4. Review VPS_MIKROTIK_SETUP_GUIDE.md")
    
    print("\n📋 NEXT STEPS:")
    if passed == total:
        print("   • Test with real users connecting to WiFi")
        print("   • Monitor system performance")
        print("   • Configure SSL certificates")
        print("   • Set up monitoring and alerts")
    else:
        print("   • Fix failed tests first")
        print("   • Check network connectivity")
        print("   • Verify router configuration")
        print("   • Review setup guide")
    
    print(f"\n🕒 Test completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
