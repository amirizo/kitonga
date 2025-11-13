# Cron Job Setup Guide for Automatic Disconnection

This guide explains how to set up automatic disconnection of expired users.

## Overview

The system now includes automatic connection and disconnection features:

1. **Automatic Connection**: When a user makes a payment or redeems a voucher, they are automatically connected to the internet via MikroTik
2. **Automatic Disconnection**: When a user's access expires, they should be automatically disconnected

## Setup Automatic Disconnection

### Option 1: Using Cron (Recommended for Production)

1. Open your crontab:
```bash
crontab -e
```

2. Add the following line to check for expired users every 5 minutes:
```bash
*/5 * * * * cd /Users/macbookair/Desktop/kitonga && /usr/bin/python manage.py disconnect_expired_users >> /var/log/kitonga_disconnect.log 2>&1
```

3. For daily device cleanup (at 2 AM):
```bash
0 2 * * * cd /Users/macbookair/Desktop/kitonga && /usr/bin/python manage.py disconnect_expired_users --cleanup-devices >> /var/log/kitonga_cleanup.log 2>&1
```

### Option 2: Using Django-Cron

1. Install django-cron:
```bash
pip install django-cron
```

2. Add to `INSTALLED_APPS` in `settings.py`:
```python
INSTALLED_APPS = [
    ...
    'django_cron',
    ...
]
```

3. Add to `settings.py`:
```python
CRON_CLASSES = [
    'billing.cron.DisconnectExpiredUsersCronJob',
]
```

4. Create `billing/cron.py`:
```python
from django_cron import CronJobBase, Schedule
from .tasks import disconnect_expired_users

class DisconnectExpiredUsersCronJob(CronJobBase):
    RUN_EVERY_MINS = 5  # every 5 minutes
    
    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'billing.disconnect_expired_users'
    
    def do(self):
        disconnect_expired_users()
```

5. Run the cron jobs:
```bash
python manage.py runcrons
```

### Option 3: Using Celery Beat (Best for Large Scale)

1. Install celery:
```bash
pip install celery redis
```

2. Create `billing/celery.py`:
```python
from celery import Celery
from celery.schedules import crontab

app = Celery('kitonga')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'disconnect-expired-users-every-5-minutes': {
        'task': 'billing.tasks.disconnect_expired_users',
        'schedule': 300.0,  # 5 minutes
    },
}
```

3. Start celery worker and beat:
```bash
celery -A billing worker --loglevel=info
celery -A billing beat --loglevel=info
```

## Manual Testing

Test the disconnect command manually:

```bash
python manage.py disconnect_expired_users
```

With device cleanup:

```bash
python manage.py disconnect_expired_users --cleanup-devices
```

## How It Works

### Automatic Connection
- **Payment**: When a payment is completed via webhook, the system automatically calls `grant_user_access()` to create/update the hotspot user and bypass their MAC address
- **Voucher**: When a voucher is redeemed, the system immediately calls `grant_user_access()` with the user's MAC and IP to grant instant internet access

### Automatic Disconnection
- The cron job runs every 5 minutes
- It finds all users where `paid_until <= now()` and `is_active = True`
- For each expired user:
  - Calls `revoke_user_access()` to remove MAC bypass and disable hotspot user
  - Deactivates the user in the database
  - Logs the disconnection

## Logs

Check logs at:
- `/var/log/kitonga_disconnect.log` - Disconnection logs
- `/var/log/kitonga_cleanup.log` - Cleanup logs
- Django logs - Check your Django log configuration

## Troubleshooting

1. **Users not disconnecting?**
   - Check if cron job is running: `grep CRON /var/log/syslog`
   - Run manually: `python manage.py disconnect_expired_users`
   - Check MikroTik connection: Test in admin panel

2. **Users not auto-connecting after payment?**
   - Check webhook logs in admin panel
   - Ensure MikroTik API is accessible
   - Check payment webhook is being received

3. **Permission errors?**
   - Ensure the cron user has permission to run the command
   - Check file permissions on manage.py

## Production Recommendations

1. Use Option 1 (Cron) or Option 3 (Celery) for production
2. Set up log rotation for the log files
3. Monitor the logs regularly
4. Set up alerts for failed disconnections
5. Test thoroughly before deploying

## Testing Checklist

- [ ] Payment creates hotspot user
- [ ] Payment bypasses MAC address
- [ ] User can access internet after payment
- [ ] Voucher redem creates hotspot user
- [ ] Voucher redemption bypasses MAC address
- [ ] User can access internet after voucher redemption
- [ ] Expired users are disconnected by cron job
- [ ] MAC bypass is removed on expiration
- [ ] Hotspot user is disabled on expiration
- [ ] Logs show disconnection activity
