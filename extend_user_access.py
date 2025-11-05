#!/usr/bin/env python3
"""
Create a voucher and extend access for the test user 255772236727
"""

import os
import sys
import django

# Add the project directory to Python path
sys.path.append('/Users/macbookair/Desktop/kitonga')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from billing.models import User, Voucher
from django.utils import timezone

def create_voucher_and_extend_user():
    """Create a voucher and use it to extend user access"""
    phone_number = "255772236727"
    
    try:
        # Get the existing user
        user = User.objects.get(phone_number=phone_number)
        print(f"Found user: {phone_number}")
        print(f"Current status: Active={user.is_active}, Paid until={user.paid_until}")
        print(f"Has access: {user.has_active_access()}")
        
        # Create a test voucher
        voucher = Voucher.objects.create(
            code=Voucher.generate_code(),
            duration_hours=24,
            batch_id="TEST-BATCH-001",
            created_by="admin",
            notes="Test voucher for fixing internet access"
        )
        
        print(f"\nCreated voucher: {voucher.code}")
        print(f"Duration: {voucher.duration_hours} hours")
        
        # Redeem the voucher
        success, message = voucher.redeem(user)
        
        if success:
            print(f"\n✅ Voucher redeemed successfully!")
            print(f"Message: {message}")
            
            # Refresh user from database
            user.refresh_from_db()
            print(f"\nUpdated user status:")
            print(f"- Active: {user.is_active}")
            print(f"- Paid until: {user.paid_until}")
            print(f"- Has access: {user.has_active_access()}")
            print(f"- Time remaining: {(user.paid_until - timezone.now()).total_seconds() / 3600:.1f} hours")
            
            return voucher.code
        else:
            print(f"❌ Failed to redeem voucher: {message}")
            return None
            
    except User.DoesNotExist:
        print(f"❌ User {phone_number} not found")
        return None

def main():
    print("Creating voucher and extending access for user 255772236727...")
    print("=" * 60)
    
    voucher_code = create_voucher_and_extend_user()
    
    if voucher_code:
        print(f"\n🎉 SUCCESS! User 255772236727 now has internet access!")
        print(f"Voucher code used: {voucher_code}")
        print("\nTest MikroTik authentication:")
        print("curl -X POST 'http://127.0.0.1:8000/api/mikrotik/auth/' \\")
        print("     -d 'username=255772236727&mac=AA:BB:CC:DD:EE:FF&ip=192.168.1.102'")
        print("\nExpected result: OK (allowing internet access)")
    else:
        print("❌ Failed to extend user access")

if __name__ == "__main__":
    main()
