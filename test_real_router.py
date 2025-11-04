#!/usr/bin/env python
"""
Test MikroTik Router Connection Script
Tests connectivity to your real MikroTik router
"""
import os
import sys
import django
import socket
import requests
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from django.conf import settings
from billing.mikrotik import MikrotikIntegration

def test_router_connectivity():
    """Test basic connectivity to MikroTik router"""
    print("🔍 Testing MikroTik Router Connection")
    print("=" * 50)
    
    # Get router settings
    router_ip = settings.MIKROTIK_ROUTER_IP
    admin_user = settings.MIKROTIK_ADMIN_USER
    admin_pass = settings.MIKROTIK_ADMIN_PASS
    api_port = settings.MIKROTIK_API_PORT
    hotspot_name = settings.MIKROTIK_HOTSPOT_NAME
    
    print(f"📊 Router Configuration:")
    print(f"   IP Address: {router_ip}")
    print(f"   Admin User: {admin_user}")
    print(f"   Admin Pass: {'*' * len(admin_pass)}")
    print(f"   API Port: {api_port}")
    print(f"   Hotspot Name: {hotspot_name}")
    print()
    
    # Test 1: Basic ping test
    print("1️⃣ Testing Basic Connectivity (ping)...")
    try:
        import subprocess
        result = subprocess.run(['ping', '-c', '3', router_ip], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"   ✅ Router {router_ip} is reachable via ping")
        else:
            print(f"   ❌ Router {router_ip} is NOT reachable via ping")
            print(f"   Output: {result.stdout}")
    except Exception as e:
        print(f"   ❌ Ping test failed: {e}")
    
    # Test 2: HTTP Web Interface
    print("\n2️⃣ Testing HTTP Web Interface...")
    try:
        response = requests.get(f"http://{router_ip}", timeout=5)
        if response.status_code == 200:
            print(f"   ✅ HTTP web interface accessible")
            if "mikrotik" in response.text.lower() or "routeros" in response.text.lower():
                print(f"   ✅ Confirmed MikroTik router")
            else:
                print(f"   ⚠️  HTTP accessible but may not be MikroTik")
        else:
            print(f"   ❌ HTTP interface returned status {response.status_code}")
    except requests.exceptions.Timeout:
        print(f"   ❌ HTTP interface timeout")
    except requests.exceptions.ConnectionError:
        print(f"   ❌ HTTP interface connection refused")
    except Exception as e:
        print(f"   ❌ HTTP test failed: {e}")
    
    # Test 3: API Port
    print("\n3️⃣ Testing MikroTik API Port...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((router_ip, api_port))
        sock.close()
        
        if result == 0:
            print(f"   ✅ API port {api_port} is open")
        else:
            print(f"   ❌ API port {api_port} is closed or filtered")
    except Exception as e:
        print(f"   ❌ API port test failed: {e}")
    
    # Test 4: SSH Port (22)
    print("\n4️⃣ Testing SSH Port...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((router_ip, 22))
        sock.close()
        
        if result == 0:
            print(f"   ✅ SSH port 22 is open")
        else:
            print(f"   ❌ SSH port 22 is closed or filtered")
    except Exception as e:
        print(f"   ❌ SSH port test failed: {e}")
    
    # Test 5: Hotspot Login Page
    print("\n5️⃣ Testing Hotspot Login Page...")
    try:
        # Try common hotspot login paths
        hotspot_paths = ['/login', '/hotspot/login', f'/{hotspot_name}/login']
        
        for path in hotspot_paths:
            try:
                response = requests.get(f"http://{router_ip}{path}", timeout=5)
                if "login" in response.text.lower() and "hotspot" in response.text.lower():
                    print(f"   ✅ Hotspot login page found at {path}")
                    break
            except:
                continue
        else:
            print(f"   ❌ Hotspot login page not found")
    except Exception as e:
        print(f"   ❌ Hotspot test failed: {e}")
    
    # Test 6: MikroTik Integration Class
    print("\n6️⃣ Testing MikroTik Integration Class...")
    try:
        mikrotik = MikrotikIntegration(router_ip, admin_user, admin_pass)
        print(f"   ✅ MikrotikIntegration class initialized")
        print(f"   Router IP: {mikrotik.router_ip}")
        print(f"   Login URL: {mikrotik.login_url}")
    except Exception as e:
        print(f"   ❌ MikrotikIntegration failed: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 ROUTER CONNECTION TEST COMPLETE")
    print()
    print("Next Steps:")
    print("• If ping fails: Check network connectivity")
    print("• If HTTP fails: Check if router web interface is enabled")
    print("• If API port fails: Enable API service in MikroTik")
    print("• If SSH fails: Enable SSH service in MikroTik")
    print()
    print("To enable API on MikroTik:")
    print("1. Connect to router web interface")
    print("2. Go to IP > Services")
    print("3. Enable 'api' service")
    print("4. Set port to 8728 (default)")

def test_router_authentication():
    """Test authentication endpoints with real router"""
    print("\n🔐 Testing Router Authentication")
    print("=" * 50)
    
    router_ip = settings.MIKROTIK_ROUTER_IP
    
    # Test authentication endpoint that router would call
    test_username = "0772236727"
    test_data = {
        "username": test_username,
        "password": test_username,
        "mac": "AA:BB:CC:DD:EE:FF",
        "ip": "192.168.1.100"
    }
    
    print(f"Testing authentication with test user: {test_username}")
    
    # This would be called by your MikroTik router
    try:
        # Test local Django authentication endpoint
        import requests
        auth_url = "http://localhost:8000/api/mikrotik/auth/"
        
        print(f"Testing Django auth endpoint: {auth_url}")
        response = requests.post(auth_url, json=test_data, timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
    except Exception as e:
        print(f"Auth test failed: {e}")

if __name__ == "__main__":
    test_router_connectivity()
    test_router_authentication()
