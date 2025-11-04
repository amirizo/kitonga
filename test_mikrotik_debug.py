#!/usr/bin/env python
"""
Test script to debug MikroTik endpoints
"""
import os
import sys
import django
import requests
import json
from datetime import timedelta
from django.utils import timezone

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from billing.models import User, Bundle, Payment

def test_mikrotik_endpoints():
    print("🔍 Debugging MikroTik Endpoints")
    print("=" * 50)
    
    # Test data
    phone = "0772236727"
    test_data = {
        "username": phone,
        "password": phone,
        "mac": "AA:BB:CC:DD:EE:FF",
        "ip": "192.168.1.100"
    }
    
    # Check/create user
    try:
        user = User.objects.get(phone_number=phone)
        print(f"✅ Found user: {user.phone_number}")
    except User.DoesNotExist:
        print(f"❌ User {phone} not found. Creating...")
        user = User.objects.create(
            phone_number=phone,
            max_devices=3,
            is_active=True
        )
        print(f"✅ Created user: {user.phone_number}")
    
    # Check active payments
    has_active = user.has_active_access()
    print(f"📊 Has active access: {has_active}")
    
    if not has_active:
        print("💰 Creating test payment...")
        bundle = Bundle.objects.first()
        
        # Create payment and activate user
        payment = Payment.objects.create(
            user=user,
            bundle=bundle,
            amount=bundle.price,
            status='completed',
            phone_number=phone,
            transaction_id=f"DEBUG_TXN_{timezone.now().strftime('%Y%m%d_%H%M%S')}",
            order_reference=f"DEBUG_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        )
        print(f"✅ Created payment: {payment.bundle.name}")
        
        # Mark as completed and update user
        payment.mark_completed()
        print(f"✅ Payment marked as completed")
        
        # Refresh user and check access
        user.refresh_from_db()
        print(f"✅ User now has active access: {user.has_active_access()}")
        print(f"✅ User paid until: {user.paid_until}")
    else:
        print(f"✅ User already has access until: {user.paid_until}")
    
    # Test the views directly
    print("\n🧪 Testing view functions directly...")
    
    # Import views
    from billing.views import mikrotik_auth, mikrotik_logout, mikrotik_user_status
    from django.test import RequestFactory
    from django.http import JsonResponse
    
    factory = RequestFactory()
    
    # Test Auth
    print("\n1️⃣ Testing mikrotik_auth:")
    request = factory.post('/api/mikrotik/auth/', 
                          data=json.dumps(test_data),
                          content_type='application/json')
    try:
        response = mikrotik_auth(request)
        response.render()  # Render the response
        print(f"   Status: {response.status_code}")
        if hasattr(response, 'content'):
            content = json.loads(response.content.decode())
            print(f"   Response: {content}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test Logout
    print("\n2️⃣ Testing mikrotik_logout:")
    logout_data = {"username": phone, "ip": "192.168.1.100"}
    request = factory.post('/api/mikrotik/logout/', 
                          data=json.dumps(logout_data),
                          content_type='application/json')
    try:
        response = mikrotik_logout(request)
        response.render()  # Render the response
        print(f"   Status: {response.status_code}")
        if hasattr(response, 'content'):
            content = json.loads(response.content.decode())
            print(f"   Response: {content}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test User Status
    print("\n3️⃣ Testing mikrotik_user_status:")
    request = factory.get(f'/api/mikrotik/user-status/?username={phone}')
    try:
        response = mikrotik_user_status(request)
        response.render()  # Render the response
        print(f"   Status: {response.status_code}")
        if hasattr(response, 'content'):
            content = json.loads(response.content.decode())
            print(f"   Response: {content}")
    except Exception as e:
        print(f"   Error: {e}")

if __name__ == "__main__":
    test_mikrotik_endpoints()
