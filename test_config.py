#!/usr/bin/env python
"""
Configuration Test Script for Kitonga Wi-Fi Billing System
Run this to verify all configurations are working properly
"""

import os
import sys
import django
from pathlib import Path

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from django.conf import settings
from decouple import config
from billing.mikrotik import get_mikrotik_client
import requests

def test_environment_variables():
    """Test that environment variables are loaded correctly"""
    print("🔧 Testing Environment Variables...")
    
    env_vars = [
        'SECRET_KEY',
        'DEBUG',
        'MIKROTIK_ROUTER_IP',
        'MIKROTIK_ADMIN_USER', 
        'MIKROTIK_ADMIN_PASS',
        'MIKROTIK_HOTSPOT_NAME',
        'CLICKPESA_CLIENT_ID',
        'NEXTSMS_USERNAME'
    ]
    
    results = {}
    for var in env_vars:
        try:
            value = config(var, default='NOT_SET')
            results[var] = value if var not in ['SECRET_KEY', 'MIKROTIK_ADMIN_PASS', 'CLICKPESA_API_KEY'] else '***MASKED***'
            print(f"  ✅ {var}: {results[var]}")
        except Exception as e:
            results[var] = f"ERROR: {str(e)}"
            print(f"  ❌ {var}: {results[var]}")
    
    return results

def test_django_settings():
    """Test Django settings configuration"""
    print("\n⚙️  Testing Django Settings...")
    
    settings_to_check = [
        ('DEBUG', settings.DEBUG),
        ('ALLOWED_HOSTS', settings.ALLOWED_HOSTS),
        ('MIKROTIK_ROUTER_IP', settings.MIKROTIK_ROUTER_IP),
        ('MIKROTIK_ADMIN_USER', settings.MIKROTIK_ADMIN_USER),
        ('MIKROTIK_HOTSPOT_NAME', settings.MIKROTIK_HOTSPOT_NAME),
        ('DAILY_ACCESS_PRICE', settings.DAILY_ACCESS_PRICE),
        ('MAX_DEVICES_PER_USER', settings.MAX_DEVICES_PER_USER)
    ]
    
    for setting_name, setting_value in settings_to_check:
        if setting_name == 'MIKROTIK_ADMIN_PASS':
            print(f"  ✅ {setting_name}: ***MASKED***")
        else:
            print(f"  ✅ {setting_name}: {setting_value}")

def test_mikrotik_connection():
    """Test MikroTik router connectivity"""
    print("\n🌐 Testing MikroTik Router Connection...")
    
    router_ip = settings.MIKROTIK_ROUTER_IP
    
    try:
        # Test basic connectivity (ping substitute)
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((router_ip, 80))  # Test HTTP port
        sock.close()
        
        if result == 0:
            print(f"  ✅ Router accessible at {router_ip}:80")
        else:
            print(f"  ⚠️  Router not accessible at {router_ip}:80 (may be normal if HTTP is disabled)")
        
        # Test API port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        api_result = sock.connect_ex((router_ip, settings.MIKROTIK_API_PORT))
        sock.close()
        
        if api_result == 0:
            print(f"  ✅ API port accessible at {router_ip}:{settings.MIKROTIK_API_PORT}")
        else:
            print(f"  ⚠️  API port not accessible at {router_ip}:{settings.MIKROTIK_API_PORT}")
            print(f"      Make sure API is enabled on the router")
        
    except Exception as e:
        print(f"  ❌ Connection test failed: {str(e)}")

def test_mikrotik_client():
    """Test MikroTik client initialization"""
    print("\n🔌 Testing MikroTik Client...")
    
    try:
        client = get_mikrotik_client()
        print(f"  ✅ Client created successfully")
        print(f"  ✅ Router IP: {client.router_ip}")
        print(f"  ✅ Admin User: {client.admin_user}")
        print(f"  ✅ Admin Pass: ***MASKED***")
        
        # Test authentication method (simulation)
        result = client.login_user_to_hotspot("255700000000", "aa:bb:cc:dd:ee:ff", "192.168.88.100")
        if result['success']:
            print(f"  ✅ Authentication method works: {result['message']}")
        else:
            print(f"  ❌ Authentication method failed: {result['message']}")
            
    except Exception as e:
        print(f"  ❌ Client test failed: {str(e)}")

def test_database():
    """Test database connectivity"""
    print("\n💾 Testing Database...")
    
    try:
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        if result[0] == 1:
            print(f"  ✅ Database connection successful")
            
        # Check if tables exist
        from billing.models import User, Payment
        user_count = User.objects.count()
        payment_count = Payment.objects.count()
        print(f"  ✅ Users in database: {user_count}")
        print(f"  ✅ Payments in database: {payment_count}")
        
    except Exception as e:
        print(f"  ❌ Database test failed: {str(e)}")
        print(f"      Run: python manage.py migrate")

def main():
    """Run all configuration tests"""
    print("🚀 Kitonga Wi-Fi Configuration Test")
    print("=" * 50)
    
    test_environment_variables()
    test_django_settings()
    test_mikrotik_connection()
    test_mikrotik_client()
    test_database()
    
    print("\n" + "=" * 50)
    print("✨ Configuration test completed!")
    print("\n📋 Next Steps:")
    print("1. If MikroTik connection failed, ensure router is powered on and connected")
    print("2. Configure MikroTik hotspot using the provided configuration files")
    print("3. Test end-to-end authentication flow")
    print("4. Run: python manage.py runserver to start the Django application")

if __name__ == "__main__":
    main()
