"""
Django management command to check task scheduling status
Run with: python manage.py check_task_status
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from billing.models import User, Router
from datetime import timedelta


class Command(BaseCommand):
    help = "Check status of background tasks and expired users"

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("🔍 KITONGA TASK STATUS CHECK"))
        self.stdout.write("=" * 80)

        now = timezone.now()

        # Check for expired users
        expired_users = User.objects.filter(is_active=True, paid_until__lte=now)
        if expired_users.exists():
            self.stdout.write(
                self.style.ERROR(
                    f"\n⚠️  ALERT: {expired_users.count()} EXPIRED USERS STILL ACTIVE!"
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    "These users should have been disconnected but are still active:\n"
                )
            )

            for user in expired_users[:10]:  # Show first 10
                time_expired = now - user.paid_until if user.paid_until else None
                hours_expired = (
                    int(time_expired.total_seconds() / 3600) if time_expired else 0
                )

                self.stdout.write(
                    f"  - {user.phone_number} "
                    f"(Tenant: {user.tenant.slug if user.tenant else 'platform'}) "
                    f"- Expired {hours_expired}h ago "
                    f"(paid_until: {user.paid_until})"
                )

                # Check devices and routers
                devices = user.devices.filter(is_active=True)
                for device in devices:
                    router_info = (
                        f"{device.router.name} (ID:{device.router.id})"
                        if device.router
                        else "No router"
                    )
                    self.stdout.write(f"      Device: {device.mac_address} -> {router_info}")

            if expired_users.count() > 10:
                self.stdout.write(
                    f"  ... and {expired_users.count() - 10} more expired users"
                )

            self.stdout.write(
                self.style.ERROR(
                    "\n❌ ACTION REQUIRED: The disconnect_expired_users() task is NOT running!"
                )
            )
            self.stdout.write(
                "   This task must run every 5 minutes to disconnect expired users."
            )
            self.stdout.write(
                "   See /docs/TASK_SCHEDULING_SETUP.md for setup instructions.\n"
            )

        else:
            self.stdout.write(
                self.style.SUCCESS("\n✅ No expired users found - tasks working correctly!")
            )

        # Check users expiring soon
        expiry_window = now + timedelta(hours=1)
        expiring_soon = User.objects.filter(
            is_active=True, paid_until__gt=now, paid_until__lte=expiry_window
        )

        if expiring_soon.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"\n⏰ {expiring_soon.count()} users expiring in the next hour:"
                )
            )
            for user in expiring_soon[:5]:
                remaining = user.paid_until - now
                minutes_remaining = int(remaining.total_seconds() / 60)
                self.stdout.write(
                    f"  - {user.phone_number} "
                    f"(Tenant: {user.tenant.slug if user.tenant else 'platform'}) "
                    f"- {minutes_remaining} minutes remaining"
                )

        # Check routers
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("📡 ROUTER STATUS"))
        self.stdout.write("=" * 80)

        active_routers = Router.objects.filter(is_active=True)
        if active_routers.exists():
            self.stdout.write(f"\n✅ {active_routers.count()} active routers found:\n")

            for router in active_routers:
                tenant_info = (
                    f"{router.tenant.business_name} ({router.tenant.slug})"
                    if router.tenant
                    else "Global/Legacy"
                )
                connected_devices = router.devices.filter(is_active=True).count()

                self.stdout.write(
                    f"  - {router.name} (ID: {router.id}) "
                    f"[Tenant: {tenant_info}] "
                    f"- {connected_devices} active devices"
                )
        else:
            self.stdout.write(
                self.style.ERROR("❌ No active routers found in database!")
            )

        # Statistics
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("📊 STATISTICS"))
        self.stdout.write("=" * 80 + "\n")

        total_users = User.objects.count()
        active_users = User.objects.filter(
            is_active=True, paid_until__gt=now
        ).count()
        inactive_users = User.objects.filter(is_active=False).count()

        self.stdout.write(f"Total Users: {total_users}")
        self.stdout.write(f"Active with valid access: {active_users}")
        self.stdout.write(f"Inactive: {inactive_users}")
        self.stdout.write(f"Expired but still active: {expired_users.count()}")

        # Recommendations
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("💡 RECOMMENDATIONS"))
        self.stdout.write("=" * 80 + "\n")

        if expired_users.exists():
            self.stdout.write(
                self.style.ERROR("1. ⚠️  SET UP CRON JOB IMMEDIATELY!")
            )
            self.stdout.write(
                "   Add to crontab: */5 * * * * cd /path/to/kitonga && python manage.py disconnect_expired_users"
            )
            self.stdout.write("\n2. Run manual cleanup now:")
            self.stdout.write("   python manage.py disconnect_expired_users\n")
        else:
            self.stdout.write(
                self.style.SUCCESS("✅ All systems operational!")
            )

        self.stdout.write("=" * 80 + "\n")
