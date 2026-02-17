# Generated migration for Snippe payment gateway integration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0016_router_monitoring_features"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="snippe_api_key",
            field=models.CharField(
                blank=True,
                help_text="Snippe API key (snp_...)",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="tenant",
            name="snippe_webhook_secret",
            field=models.CharField(
                blank=True,
                help_text="Snippe webhook signing secret",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="tenant",
            name="preferred_payment_gateway",
            field=models.CharField(
                choices=[("clickpesa", "ClickPesa"), ("snippe", "Snippe")],
                default="clickpesa",
                help_text="Which payment gateway to use for collecting WiFi payments",
                max_length=20,
            ),
        ),
    ]
