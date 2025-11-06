#!/usr/bin/env python3
"""
Fix users with null max_devices field
This script ensures all users have a valid max_devices value
"""

import os
import sys
import django

# Setup Django
sys.path.append('/Users/macbookair/Desktop/kitonga')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from billing.models import User

def fix_max_devices():
    """Fix users with null max_devices"""
    print("🔧 FIXING USER MAX_DEVICES FIELD")
    print("=" * 40)
    
    # Find users with null max_devices
    users_with_null_max_devices = User.objects.filter(max_devices__isnull=True)
    count = users_with_null_max_devices.count()
    
    if count == 0:
        print("✅ All users already have valid max_devices values")
        return
    
    print(f"Found {count} users with null max_devices")
    
    # Fix them
    users_with_null_max_devices.update(max_devices=1)
    
    print(f"✅ Fixed {count} users - set max_devices to 1")
    
    # Verify fix
    remaining_null = User.objects.filter(max_devices__isnull=True).count()
    if remaining_null == 0:
        print("✅ All users now have valid max_devices values")
    else:
        print(f"⚠️  {remaining_null} users still have null max_devices")
    
    # Show sample of fixed users
    print("\nSample of fixed users:")
    for user in User.objects.all()[:5]:
        print(f"  {user.phone_number}: max_devices={user.max_devices}")

if __name__ == "__main__":
    fix_max_devices()
