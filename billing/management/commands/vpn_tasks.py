"""
Django management command for VPN (Remote Access) tasks.

Usage:
    python manage.py vpn_tasks --expire       # Disable expired remote users
    python manage.py vpn_tasks --notify       # Send expiry notifications
    python manage.py vpn_tasks --health       # Health check VPN interfaces
    python manage.py vpn_tasks --all          # Run all tasks
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run VPN / Remote Access automation tasks"

    def add_arguments(self, parser):
        parser.add_argument(
            "--expire",
            action="store_true",
            help="Disable expired remote VPN users on routers",
        )
        parser.add_argument(
            "--notify",
            action="store_true",
            help="Send SMS/email expiry warnings (24h and 3h before)",
        )
        parser.add_argument(
            "--health",
            action="store_true",
            help="Health check all active VPN interfaces on routers",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Run all VPN tasks (expire + notify + health)",
        )

    def handle(self, *args, **options):
        run_expire = options["expire"] or options["all"]
        run_notify = options["notify"] or options["all"]
        run_health = options["health"] or options["all"]

        if not any([run_expire, run_notify, run_health]):
            self.stdout.write(
                self.style.WARNING(
                    "No task specified. Use --expire, --notify, --health, or --all"
                )
            )
            return

        # ── 1. Expire remote users ──────────────────────────────────
        if run_expire:
            from billing.tasks import disconnect_expired_remote_users

            self.stdout.write("⏰ Checking for expired remote VPN users...")
            result = disconnect_expired_remote_users()

            if result.get("success"):
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Disabled {result["disabled"]} expired remote users'
                    )
                )
                if result.get("webhook_sent"):
                    self.stdout.write(
                        f'  └─ {result["webhook_sent"]} webhook notifications sent'
                    )
                if result.get("failed"):
                    self.stdout.write(
                        self.style.WARNING(f'  └─ {result["failed"]} failures')
                    )
            else:
                self.stdout.write(self.style.ERROR(f'✗ Error: {result.get("error")}'))

        # ── 2. Expiry notifications ─────────────────────────────────
        if run_notify:
            from billing.tasks import send_remote_user_expiry_notifications

            self.stdout.write("📢 Sending VPN expiry notifications...")
            result = send_remote_user_expiry_notifications()

            if result.get("success"):
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Sent {result["notified"]} expiry notifications'
                    )
                )
                if result.get("failed"):
                    self.stdout.write(
                        self.style.WARNING(f'  └─ {result["failed"]} failures')
                    )
            else:
                self.stdout.write(self.style.ERROR(f'✗ Error: {result.get("error")}'))

        # ── 3. VPN health check ─────────────────────────────────────
        if run_health:
            from billing.tasks import health_check_vpn_interfaces

            self.stdout.write("🏥 Running VPN interface health check...")
            result = health_check_vpn_interfaces()

            if result.get("success"):
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Health check: {result["healthy"]} healthy, '
                        f'{result["unhealthy"]} unhealthy '
                        f'({result["peers_updated"]} peers updated)'
                    )
                )
                if result.get("errors"):
                    for err in result["errors"]:
                        self.stdout.write(self.style.WARNING(f"  └─ {err}"))
            else:
                self.stdout.write(self.style.ERROR(f'✗ Error: {result.get("error")}'))

        self.stdout.write(self.style.SUCCESS("\n✅ VPN tasks completed."))
