#!/usr/bin/env python3
"""Test all MikroTik Admin API endpoints"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000/api"
ADMIN_TOKEN = "8d7ed4a9d0cd4848a68eeb4bea435d3f0d1ec9fd"
HEADERS = {
    "Authorization": f"Token {ADMIN_TOKEN}",
    "Content-Type": "application/json"
}

def test_endpoint(method, path, data=None, description=""):
    """Test an API endpoint"""
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            response = requests.get(url, headers=HEADERS, timeout=15)
        elif method == "POST":
            response = requests.post(url, headers=HEADERS, json=data or {}, timeout=15)
        
        result = {
            "endpoint": path,
            "method": method,
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "description": description
        }
        
        try:
            json_response = response.json()
            result["api_success"] = json_response.get("success", False)
        except:
            result["api_success"] = False
            
        return result
    except Exception as e:
        return {
            "endpoint": path,
            "method": method,
            "status_code": 0,
            "success": False,
            "api_success": False,
            "description": description,
            "error": str(e)
        }

def main():
    print("=" * 70)
    print("MIKROTIK ADMIN API TEST RESULTS")
    print("=" * 70)
    
    tests = [
        ("GET", "/admin/mikrotik/config/", None, "Get MikroTik configuration"),
        ("POST", "/admin/mikrotik/test-connection/", {}, "Test router connection"),
        ("GET", "/admin/mikrotik/router-info/", None, "Get router information"),
        ("GET", "/admin/mikrotik/active-users/", None, "List active hotspot users"),
        ("POST", "/admin/mikrotik/disconnect-user/", {"username": "test_fake"}, "Disconnect single user"),
        ("GET", "/admin/mikrotik/profiles/", None, "List hotspot profiles"),
        ("GET", "/admin/mikrotik/resources/", None, "Get system resources"),
    ]
    
    passed = 0
    failed = 0
    
    for method, path, data, desc in tests:
        result = test_endpoint(method, path, data, desc)
        status = "✅ PASS" if result["success"] and result.get("api_success") else "❌ FAIL"
        if result["success"] and result.get("api_success"):
            passed += 1
        else:
            failed += 1
        print(f"\n{status}: {method} {path}")
        print(f"   Description: {desc}")
        print(f"   HTTP Status: {result['status_code']}")
        if "error" in result:
            print(f"   Error: {result['error']}")
    
    print("\n" + "=" * 70)
    print(f"SUMMARY: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 70)
    
    # Note about dangerous endpoints
    print("\n⚠️  NOT TESTED (Dangerous operations):")
    print("   - POST /admin/mikrotik/disconnect-all/ - Disconnects all users")
    print("   - POST /admin/mikrotik/reboot/ - Reboots the router")
    print("   - POST /admin/mikrotik/profiles/create/ - Creates profile (tested separately)")

if __name__ == "__main__":
    main()
