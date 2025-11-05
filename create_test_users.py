#!/usr/bin/env python3
"""
Create a test user with active access for testing MikroTik authentication
"""

import os
import sys
import django

# Add the project directory to Python path
sys.path.append('/Users/macbookair/Desktop/kitonga')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from billing.models import User, Bundle
from django.utils import timezone
from datetime import timedelta

def create_test_user():
    """Create a test user with active access"""
    phone_number = "255999888777"
    
    # Delete existing test user if exists
    User.objects.filter(phone_number=phone_number).delete()
    
    # Create new user with 24 hours of access
    user = User.objects.create(
        phone_number=phone_number,
        is_active=True,
        paid_until=timezone.now() + timedelta(hours=24),
        total_payments=1,
        max_devices=2
    )
    
    print(f"✅ Created test user: {phone_number}")
    print(f"   - Active: {user.is_active}")
    print(f"   - Paid until: {user.paid_until}")
    print(f"   - Has access: {user.has_active_access()}")
    print(f"   - Max devices: {user.max_devices}")
    
    return user

def create_test_user_expired():
    """Create a test user with expired access"""
    phone_number = "255111222333"
    
    # Delete existing test user if exists
    User.objects.filter(phone_number=phone_number).delete()
    
    # Create user with expired access
    user = User.objects.create(
        phone_number=phone_number,
        is_active=False,
        paid_until=timezone.now() - timedelta(hours=1),  # Expired 1 hour ago
        total_payments=1,
        max_devices=1
    )
    
    print(f"✅ Created test user (expired): {phone_number}")
    print(f"   - Active: {user.is_active}")
    print(f"   - Paid until: {user.paid_until}")
    print(f"   - Has access: {user.has_active_access()}")
    print(f"   - Max devices: {user.max_devices}")
    
    return user

def main():
    print("Creating test users for MikroTik authentication testing...")
    print("=" * 60)
    
    # Create test user with active access
    active_user = create_test_user()
    
    print()
    
    # Create test user with expired access
    expired_user = create_test_user_expired()
    
    print()
    print("Test Users Created!")
    print("=" * 60)
    print("Use these phone numbers to test MikroTik authentication:")
    print(f"✅ Active user:  {active_user.phone_number} (should get internet)")
    print(f"❌ Expired user: {expired_user.phone_number} (should be denied)")
    print()
    print("Test commands:")
    print(f"curl -X POST 'http://127.0.0.1:8000/api/mikrotik/auth/' \\")
    print(f"     -d 'username={active_user.phone_number}&mac=AA:BB:CC:DD:EE:FF&ip=192.168.1.100'")
    print()
    print(f"curl -X POST 'http://127.0.0.1:8000/api/mikrotik/auth/' \\")
    print(f"     -d 'username={expired_user.phone_number}&mac=AA:BB:CC:DD:EE:FF&ip=192.168.1.101'")

if __name__ == "__main__":
    main()
