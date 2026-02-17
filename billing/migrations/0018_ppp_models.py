"""
Migration to add PPP/PPPoE models for Enterprise plan tenants.
Creates PPPProfile and PPPCustomer tables.
"""

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0017_add_snippe_payment_gateway"),
    ]

    operations = [
        migrations.CreateModel(
            name="PPPProfile",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Profile name (e.g., 'basic-5m', 'premium-50m')",
                        max_length=100,
                    ),
                ),
                (
                    "display_name",
                    models.CharField(
                        blank=True,
                        help_text="Human-friendly name (e.g., 'Basic 5Mbps')",
                        max_length=200,
                    ),
                ),
                ("description", models.TextField(blank=True)),
                (
                    "rate_limit",
                    models.CharField(
                        help_text="MikroTik rate limit format: upload/download (e.g., '5M/10M', '2M/5M')",
                        max_length=50,
                    ),
                ),
                (
                    "burst_limit",
                    models.CharField(
                        blank=True,
                        help_text="Burst rate limit (e.g., '10M/20M')",
                        max_length=50,
                    ),
                ),
                (
                    "burst_threshold",
                    models.CharField(
                        blank=True,
                        help_text="Burst threshold (e.g., '4M/8M')",
                        max_length=50,
                    ),
                ),
                (
                    "burst_time",
                    models.CharField(
                        blank=True,
                        help_text="Burst time (e.g., '10/10')",
                        max_length=50,
                    ),
                ),
                (
                    "local_address",
                    models.GenericIPAddressField(
                        blank=True,
                        help_text="PPP local (gateway) address",
                        null=True,
                    ),
                ),
                (
                    "remote_address",
                    models.CharField(
                        blank=True,
                        help_text="IP pool name or IP range for PPP clients",
                        max_length=100,
                    ),
                ),
                (
                    "dns_server",
                    models.CharField(
                        blank=True,
                        help_text="DNS servers (comma-separated, e.g., '8.8.8.8,8.8.4.4')",
                        max_length=100,
                    ),
                ),
                (
                    "monthly_price",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        help_text="Monthly subscription price in TZS",
                        max_digits=10,
                    ),
                ),
                ("currency", models.CharField(default="TZS", max_length=3)),
                (
                    "session_timeout",
                    models.CharField(
                        blank=True,
                        help_text="Session timeout (e.g., '00:00:00' for unlimited)",
                        max_length=20,
                    ),
                ),
                (
                    "idle_timeout",
                    models.CharField(
                        blank=True,
                        help_text="Idle timeout (e.g., '00:05:00' for 5 minutes)",
                        max_length=20,
                    ),
                ),
                (
                    "keepalive_timeout",
                    models.CharField(
                        blank=True,
                        default="10",
                        help_text="Keepalive timeout in seconds",
                        max_length=20,
                    ),
                ),
                ("synced_to_router", models.BooleanField(default=False)),
                (
                    "mikrotik_id",
                    models.CharField(
                        blank=True,
                        help_text="MikroTik internal ID (.id) for this profile",
                        max_length=50,
                    ),
                ),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ppp_profiles",
                        to="billing.tenant",
                    ),
                ),
                (
                    "router",
                    models.ForeignKey(
                        blank=True,
                        help_text="Specific router for this profile. Null = apply to all tenant routers.",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ppp_profiles",
                        to="billing.router",
                    ),
                ),
            ],
            options={
                "ordering": ["tenant", "name"],
                "unique_together": {("tenant", "name")},
            },
        ),
        migrations.CreateModel(
            name="PPPCustomer",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "username",
                    models.CharField(
                        help_text="PPP login username", max_length=100
                    ),
                ),
                (
                    "password",
                    models.CharField(
                        help_text="PPP login password", max_length=255
                    ),
                ),
                (
                    "service",
                    models.CharField(
                        choices=[
                            ("pppoe", "PPPoE"),
                            ("pptp", "PPTP"),
                            ("l2tp", "L2TP"),
                            ("ovpn", "OpenVPN"),
                            ("sstp", "SSTP"),
                        ],
                        default="pppoe",
                        help_text="PPP service type",
                        max_length=10,
                    ),
                ),
                (
                    "customer_name",
                    models.CharField(
                        help_text="Customer full name", max_length=200
                    ),
                ),
                (
                    "phone_number",
                    models.CharField(blank=True, max_length=20),
                ),
                ("email", models.EmailField(blank=True, max_length=254)),
                (
                    "address",
                    models.TextField(
                        blank=True,
                        help_text="Physical installation address",
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                (
                    "remote_address",
                    models.GenericIPAddressField(
                        blank=True,
                        help_text="Static IP assignment (leave blank for pool)",
                        null=True,
                    ),
                ),
                (
                    "mac_address",
                    models.CharField(
                        blank=True,
                        help_text="Caller-ID / MAC binding (e.g., 'AA:BB:CC:DD:EE:FF')",
                        max_length=17,
                    ),
                ),
                (
                    "monthly_price",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        help_text="Monthly price (overrides profile price if set)",
                        max_digits=10,
                    ),
                ),
                ("currency", models.CharField(default="TZS", max_length=3)),
                (
                    "billing_day",
                    models.IntegerField(
                        default=1,
                        help_text="Day of month for billing (1-28)",
                    ),
                ),
                (
                    "paid_until",
                    models.DateTimeField(
                        blank=True,
                        help_text="Service is active until this date",
                        null=True,
                    ),
                ),
                (
                    "last_payment_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                ("total_payments", models.IntegerField(default=0)),
                (
                    "total_amount_paid",
                    models.DecimalField(
                        decimal_places=2, default=0, max_digits=12
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("suspended", "Suspended"),
                            ("expired", "Expired"),
                            ("disabled", "Disabled"),
                        ],
                        default="active",
                        max_length=20,
                    ),
                ),
                (
                    "disabled",
                    models.BooleanField(
                        default=False,
                        help_text="Whether the PPP secret is disabled on the router",
                    ),
                ),
                (
                    "expiry_notification_sent",
                    models.BooleanField(default=False),
                ),
                (
                    "last_logged_in",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "last_logged_out",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "last_disconnect_reason",
                    models.CharField(blank=True, max_length=200),
                ),
                (
                    "uptime",
                    models.CharField(
                        blank=True,
                        help_text="Current session uptime",
                        max_length=50,
                    ),
                ),
                (
                    "last_caller_id",
                    models.CharField(
                        blank=True,
                        help_text="Last seen caller-ID / MAC from router",
                        max_length=50,
                    ),
                ),
                ("synced_to_router", models.BooleanField(default=False)),
                (
                    "mikrotik_id",
                    models.CharField(
                        blank=True,
                        help_text="MikroTik internal ID (.id) for this secret",
                        max_length=50,
                    ),
                ),
                (
                    "last_synced_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ppp_customers",
                        to="billing.tenant",
                    ),
                ),
                (
                    "profile",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="customers",
                        to="billing.pppprofile",
                    ),
                ),
                (
                    "router",
                    models.ForeignKey(
                        help_text="Router where this PPP secret is configured",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ppp_customers",
                        to="billing.router",
                    ),
                ),
                (
                    "wifi_user",
                    models.ForeignKey(
                        blank=True,
                        help_text="Link to a WiFi user for unified billing",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ppp_accounts",
                        to="billing.user",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "unique_together": {("tenant", "username")},
            },
        ),
    ]
