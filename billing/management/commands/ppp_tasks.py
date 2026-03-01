"""
Django management command for PPPoE customer tasks.

Usage:
    python manage.py ppp_tasks --expire       # Disconnect expired PPP customers
    python manage.py ppp_tasks --notify       # Send expiry warning SMS (24h, 3h)
    python manage.py ppp_tasks --all          # Run all PPP tasks

Cron schedule (recommended):
    */5 * * * *  ... ppp_tasks --expire --notify   # Every 5 min
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run PPPoE customer automation tasks (expire + notify)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--expire",
            action="store_true",
            help="Disconnect expired PPP customers (disable secret, kick session, send SMS)",
        )
        parser.add_argument(
            "--notify",
            action="store_true",
            help="Send expiry warning SMS (24h and 3h before expiry)",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Run all PPP tasks (expire + notify)",
        )

    def handle(self, *args, **options):
        run_expire = options["expire"] or options["all"]
        run_notify = options["notify"] or options["all"]

        if not any([run_expire, run_notify]):
            self.stdout.write(
                self.style.WARNING(
                    "No task specified. Use --expire, --notify, or --all"
                )
            )
            return

        # ── 1. Disconnect expired PPP customers ─────────────────────
        if run_expire:
            from billing.tasks import disconnect_expired_ppp_customers

            self.stdout.write("⏰ Checking for expired PPP customers...")
            result = disconnect_expired_ppp_customers()

            if result.get("success"):
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Disconnected {result["disconnected"]} expired PPP customers'
                    )
                )
                if result.get("sms_sent"):
                    self.stdout.write(
                        f'  └─ {result["sms_sent"]} SMS notifications sent'
                    )
                if result.get("failed"):
                    self.stdout.write(
                        self.style.WARNING(f'  └─ {result["failed"]} failures')
                    )
            else:
                self.stdout.write(self.style.ERROR(f'✗ Error: {result.get("error")}'))

        # ── 2. Expiry warning notifications ──────────────────────────
        if run_notify:
            from billing.tasks import send_ppp_expiry_notifications

            self.stdout.write("📢 Sending PPP expiry warning notifications...")
            result = send_ppp_expiry_notifications()

            if result.get("success"):
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Sent {result["notified"]} PPP expiry warnings'
                    )
                )
                if result.get("failed"):
                    self.stdout.write(
                        self.style.WARNING(f'  └─ {result["failed"]} failures')
                    )
            else:
                self.stdout.write(self.style.ERROR(f'✗ Error: {result.get("error")}'))

        self.stdout.write(self.style.SUCCESS("Done."))
