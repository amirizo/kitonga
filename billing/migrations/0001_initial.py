# Generated migration file for initial database schema

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Bundle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
                ('duration_hours', models.IntegerField()),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('is_active', models.BooleanField(default=True)),
                ('description', models.TextField(blank=True)),
                ('display_order', models.IntegerField(default=0)),
            ],
            options={
                'ordering': ['display_order', 'duration_hours'],
            },
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone_number', models.CharField(db_index=True, max_length=15, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('paid_until', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=False)),
                ('total_payments', models.IntegerField(default=0)),
                ('expiry_notification_sent', models.BooleanField(default=False)),
                ('max_devices', models.IntegerField(default=3)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Voucher',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(db_index=True, max_length=16, unique=True)),
                ('duration_hours', models.IntegerField(choices=[(24, '24 Hours (1 Day)'), (168, '168 Hours (7 Days)'), (720, '720 Hours (30 Days)')], default=24)),
                ('is_used', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.CharField(blank=True, max_length=100)),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('batch_id', models.CharField(blank=True, db_index=True, max_length=50)),
                ('notes', models.TextField(blank=True)),
                ('used_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='vouchers_used', to='billing.user')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='SMSLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone_number', models.CharField(db_index=True, max_length=15)),
                ('message', models.TextField()),
                ('sms_type', models.CharField(choices=[('payment', 'Payment Confirmation'), ('expiry_warning', 'Expiry Warning'), ('expired', 'Access Expired'), ('voucher', 'Voucher Redemption'), ('other', 'Other')], default='other', max_length=20)),
                ('success', models.BooleanField(default=False)),
                ('response_data', models.JSONField(blank=True, null=True)),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-sent_at'],
            },
        ),
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('phone_number', models.CharField(max_length=15)),
                ('payment_reference', models.CharField(blank=True, max_length=100, null=True)),
                ('transaction_id', models.CharField(max_length=100, unique=True)),
                ('order_reference', models.CharField(blank=True, max_length=100, null=True, unique=True)),
                ('payment_channel', models.CharField(blank=True, max_length=50, null=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('completed', 'Completed'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('bundle', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payments', to='billing.bundle')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='billing.user')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Device',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mac_address', models.CharField(db_index=True, max_length=17)),
                ('ip_address', models.GenericIPAddressField()),
                ('device_name', models.CharField(blank=True, max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('first_seen', models.DateTimeField(auto_now_add=True)),
                ('last_seen', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='devices', to='billing.user')),
            ],
            options={
                'ordering': ['-last_seen'],
                'unique_together': {('user', 'mac_address')},
            },
        ),
        migrations.CreateModel(
            name='AccessLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ip_address', models.GenericIPAddressField()),
                ('mac_address', models.CharField(blank=True, max_length=17)),
                ('access_granted', models.BooleanField(default=False)),
                ('denial_reason', models.CharField(blank=True, max_length=100)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('device', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='access_logs', to='billing.device')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='access_logs', to='billing.user')),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
    ]
