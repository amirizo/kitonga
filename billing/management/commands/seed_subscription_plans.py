"""
Management command to create or update the three Kitonga subscription plans.

Usage:
    python manage.py seed_subscription_plans          # Create/update plans
    python manage.py seed_subscription_plans --reset   # Delete existing & recreate
"""

from django.core.management.base import BaseCommand
from billing.models import SubscriptionPlan


PLANS = [
    {
        "name": "starter",
        "display_name": "Starter",
        "description": (
            "Perfect for small cafes and guest houses with a single location."
        ),
        "monthly_price": 30_000,
        "yearly_price": 300_000,  # ~2 months free
        "currency": "TZS",
        # Limits
        "max_routers": 1,
        "max_wifi_users": 100,
        "max_vouchers_per_month": 500,
        "max_locations": 1,
        "max_staff_accounts": 2,
        # Features
        "analytics_dashboard": True,
        "sms_notifications": True,
        "custom_branding": False,
        "custom_domain": False,
        "api_access": False,
        "white_label": False,
        "priority_support": False,
        "sms_broadcast": False,
        "advanced_analytics": False,
        "auto_sms_campaigns": False,
        "webhook_notifications": False,
        "data_export": False,
        # Meta
        "revenue_share_percentage": 5,
        "display_order": 1,
        "is_active": True,
    },
    {
        "name": "business",
        "display_name": "Business",
        "description": ("Ideal for hotels and businesses with multiple access points."),
        "monthly_price": 60_000,
        "yearly_price": 600_000,  # ~2 months free
        "currency": "TZS",
        # Limits
        "max_routers": 3,
        "max_wifi_users": 500,
        "max_vouchers_per_month": 2_000,
        "max_locations": 3,
        "max_staff_accounts": 5,
        # Features
        "analytics_dashboard": True,
        "sms_notifications": True,
        "custom_branding": True,
        "custom_domain": False,
        "api_access": False,
        "white_label": False,
        "priority_support": True,
        "sms_broadcast": True,
        "advanced_analytics": True,
        "auto_sms_campaigns": False,
        "webhook_notifications": False,
        "data_export": True,
        # Meta
        "revenue_share_percentage": 3,
        "display_order": 2,
        "is_active": True,
    },
    {
        "name": "enterprise",
        "display_name": "Enterprise",
        "description": (
            "For large organizations, chains, and ISPs. "
            "Unlimited usage with full customization."
        ),
        "monthly_price": 120_000,
        "yearly_price": 1_200_000,  # ~2 months free
        "currency": "TZS",
        # Limits
        "max_routers": 9999,
        "max_wifi_users": 999_999,
        "max_vouchers_per_month": 99_999,
        "max_locations": 9999,
        "max_staff_accounts": 999,
        # Features
        "analytics_dashboard": True,
        "sms_notifications": True,
        "custom_branding": True,
        "custom_domain": True,
        "api_access": True,
        "white_label": True,
        "priority_support": True,
        "sms_broadcast": True,
        "advanced_analytics": True,
        "auto_sms_campaigns": True,
        "webhook_notifications": True,
        "data_export": True,
        # Meta
        "revenue_share_percentage": 2,
        "display_order": 3,
        "is_active": True,
    },
]


class Command(BaseCommand):
    help = "Create or update the Kitonga subscription plans (Starter, Business, Enterprise)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all existing plans and recreate them from scratch.",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            deleted, _ = SubscriptionPlan.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f"Deleted {deleted} existing plan(s).")
            )

        for plan_data in PLANS:
            plan, created = SubscriptionPlan.objects.update_or_create(
                name=plan_data["name"],
                defaults=plan_data,
            )
            action = "Created" if created else "Updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"  {action}: {plan.display_name} — "
                    f"TSh {plan.monthly_price:,.0f}/mo | "
                    f"{plan.max_routers} routers, {plan.max_wifi_users} users, "
                    f"{plan.max_locations} locations, {plan.max_staff_accounts} staff"
                )
            )

        self.stdout.write(self.style.SUCCESS("\n✅ All subscription plans ready."))
