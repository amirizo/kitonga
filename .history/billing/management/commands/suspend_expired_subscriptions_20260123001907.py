from django.core.management.base import BaseCommand
from billing.subscription import suspend_expired_subscriptions


class Command(BaseCommand):
    help = "Suspend tenants whose subscriptions have ended and disconnect their users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--grace-days",
            type=int,
            default=0,
            help="Number of grace days to wait after subscription end before suspending",
        )

    def handle(self, *args, **options):
        grace_days = options.get("grace_days", 0)
        self.stdout.write(
            f"Checking for expired subscriptions (grace_days={grace_days})..."
        )
        result = suspend_expired_subscriptions(grace_days=grace_days)
        self.stdout.write("Summary:")
        self.stdout.write(str(result))
        if result.get("errors"):
            self.stderr.write(
                "Some errors occurred during suspension. Check logs for details."
            )
        else:
            self.stdout.write("Completed without reported errors.")
