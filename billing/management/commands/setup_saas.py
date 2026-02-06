"""
Management command to set up SaaS subscription plans and create initial tenant
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User as DjangoUser
from billing.models import SubscriptionPlan, Tenant
from decimal import Decimal


class Command(BaseCommand):
    help = 'Set up initial SaaS subscription plans and optionally create a tenant'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--create-tenant',
            action='store_true',
            help='Create an initial tenant for migration purposes',
        )
        parser.add_argument(
            '--tenant-slug',
            type=str,
            default='default',
            help='Slug for the initial tenant (default: "default")',
        )
        parser.add_argument(
            '--owner-email',
            type=str,
            help='Email for the tenant owner (uses first superuser if not provided)',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Setting up Kitonga SaaS Platform...'))
        
        # Create subscription plans
        self._create_subscription_plans()
        
        # Optionally create initial tenant
        if options['create_tenant']:
            self._create_initial_tenant(
                slug=options['tenant_slug'],
                owner_email=options.get('owner_email')
            )
        
        self.stdout.write(self.style.SUCCESS('✓ SaaS setup complete!'))
    
    def _create_subscription_plans(self):
        """Create the default subscription plans"""
        
        plans = [
            {
                'name': 'starter',
                'display_name': 'Starter',
                'description': 'Perfect for small cafes and guest houses with a single location.',
                'monthly_price': Decimal('30000.00'),
                'yearly_price': Decimal('300000.00'),
                'currency': 'TZS',
                'max_routers': 1,
                'max_wifi_users': 100,
                'max_vouchers_per_month': 100,
                'max_locations': 1,
                'max_staff_accounts': 2,
                'custom_branding': False,
                'custom_domain': False,
                'api_access': False,
                'white_label': False,
                'priority_support': False,
                'analytics_dashboard': True,
                'sms_notifications': True,
                'revenue_share_percentage': Decimal('0.00'),
                'display_order': 1,
            },
            {
                'name': 'business',
                'display_name': 'Business',
                'description': 'Ideal for hotels and businesses with multiple access points.',
                'monthly_price': Decimal('60000.00'),
                'yearly_price': Decimal('600000.00'),
                'currency': 'TZS',
                'max_routers': 3,
                'max_wifi_users': 500,
                'max_vouchers_per_month': 999999,  # Unlimited
                'max_locations': 3,
                'max_staff_accounts': 5,
                'custom_branding': True,
                'custom_domain': False,
                'api_access': False,
                'white_label': False,
                'priority_support': True,
                'analytics_dashboard': True,
                'sms_notifications': True,
                'revenue_share_percentage': Decimal('0.00'),
                'display_order': 2,
            },
            {
                'name': 'enterprise',
                'display_name': 'Enterprise',
                'description': 'For large organizations, chains, and ISPs. Unlimited usage with full customization.',
                'monthly_price': Decimal('120000.00'),
                'yearly_price': Decimal('1200000.00'),
                'currency': 'TZS',
                'max_routers': 999999,  # Unlimited
                'max_wifi_users': 999999,  # Unlimited
                'max_vouchers_per_month': 999999,  # Unlimited
                'max_locations': 999999,  # Unlimited
                'max_staff_accounts': 999,  # Unlimited
                'custom_branding': True,
                'custom_domain': True,
                'api_access': True,
                'white_label': True,
                'priority_support': True,
                'analytics_dashboard': True,
                'sms_notifications': True,
                'revenue_share_percentage': Decimal('0.00'),
                'display_order': 3,
            },
        ]
        
        for plan_data in plans:
            plan, created = SubscriptionPlan.objects.update_or_create(
                name=plan_data['name'],
                defaults=plan_data
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(f'  {action} plan: {plan.display_name}')
        
        self.stdout.write(self.style.SUCCESS(f'✓ {len(plans)} subscription plans configured'))
    
    def _create_initial_tenant(self, slug, owner_email=None):
        """Create an initial tenant (useful for migrating existing data)"""
        
        # Find or create owner
        if owner_email:
            owner = DjangoUser.objects.filter(email=owner_email).first()
            if not owner:
                self.stdout.write(self.style.ERROR(f'User with email {owner_email} not found'))
                return
        else:
            # Use first superuser
            owner = DjangoUser.objects.filter(is_superuser=True).first()
            if not owner:
                self.stdout.write(self.style.ERROR('No superuser found. Create one first.'))
                return
        
        # Get starter plan
        starter_plan = SubscriptionPlan.objects.get(name='starter')
        
        # Create tenant
        tenant, created = Tenant.objects.get_or_create(
            slug=slug,
            defaults={
                'business_name': 'Default Tenant (Migration)',
                'business_email': owner.email,
                'business_phone': '',
                'owner': owner,
                'subscription_plan': starter_plan,
                'subscription_status': 'active',
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created tenant: {tenant.business_name} ({tenant.slug})'))
            self.stdout.write(f'  Owner: {owner.email}')
            self.stdout.write(f'  API Key: {tenant.api_key}')
        else:
            self.stdout.write(f'  Tenant already exists: {tenant.slug}')
        
        return tenant
