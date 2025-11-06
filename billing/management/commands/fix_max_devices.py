from django.core.management.base import BaseCommand
from billing.models import User

class Command(BaseCommand):
    help = 'Fix users with null max_devices field'

    def handle(self, *args, **options):
        self.stdout.write("🔧 FIXING USER MAX_DEVICES FIELD")
        self.stdout.write("=" * 40)
        
        # Find users with null max_devices
        users_with_null_max_devices = User.objects.filter(max_devices__isnull=True)
        count = users_with_null_max_devices.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS("✅ All users already have valid max_devices values"))
            return
        
        self.stdout.write(f"Found {count} users with null max_devices")
        
        # Fix them
        users_with_null_max_devices.update(max_devices=1)
        
        self.stdout.write(self.style.SUCCESS(f"✅ Fixed {count} users - set max_devices to 1"))
        
        # Verify fix
        remaining_null = User.objects.filter(max_devices__isnull=True).count()
        if remaining_null == 0:
            self.stdout.write(self.style.SUCCESS("✅ All users now have valid max_devices values"))
        else:
            self.stdout.write(self.style.WARNING(f"⚠️  {remaining_null} users still have null max_devices"))
        
        # Show sample of fixed users
        self.stdout.write("\nSample of users:")
        for user in User.objects.all()[:5]:
            self.stdout.write(f"  {user.phone_number}: max_devices={user.max_devices}")
