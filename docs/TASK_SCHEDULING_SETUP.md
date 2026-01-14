# Task Scheduling Setup for Kitonga WiFi

## ⚠️ CRITICAL: Automatic User Disconnection

**IMPORTANT**: Users receiving expiry notifications but still connected? This happens when the disconnect task is not running!

## The Problem You're Experiencing

**Symptoms:**

- Users receive SMS: "Your internet access expires in X minutes"
- After expiry time passes, users can still access internet
- Users are NOT disabled in MikroTik
- They stay connected until they buy access again

**Root Cause:**
The `disconnect_expired_users()` task is NOT running automatically. It must run every 5 minutes to actually disconnect expired users from MikroTik.

---

## Required Background Tasks

### 1. `disconnect_expired_users()` - **CRITICAL** ⚠️

**Purpose**: Actually disconnect expired users from MikroTik routers
**Frequency**: Every 5 minutes
**What it does**:

- Finds users whose `paid_until` has passed
- Disconnects them from MikroTik (removes sessions, IP bindings, disables user)
- Deactivates their database account
- Sends expiry SMS notification
- **Tracks which router/tenant each user belongs to**

### 2. `send_expiry_notifications()` - Optional but recommended

**Purpose**: Send advance warning SMS before expiry
**Frequency**: Every hour
**What it does**:

- Finds users expiring in the next hour
- Sends SMS warning: "Your access expires in X minutes"
- Does NOT disconnect - that's done by task #1

### 3. `cleanup_inactive_devices()` - Maintenance

**Purpose**: Clean up old device records
**Frequency**: Once daily
**What it does**:

- Removes devices not seen in 30 days

---

## Setup Instructions

### Method 1: Using Crontab (Linux/Mac)

1. **Edit crontab:**

```bash
crontab -e
```

2. **Add these lines:**

```bash
# CRITICAL: Disconnect expired users every 5 minutes
*/5 * * * * cd /Users/macbookair/Desktop/kitonga && /Users/macbookair/Desktop/kitonga/venv/bin/python manage.py disconnect_expired_users >> /Users/macbookair/Desktop/kitonga/logs/cron.log 2>&1

# Send expiry notifications hourly
0 * * * * cd /Users/macbookair/Desktop/kitonga && /Users/macbookair/Desktop/kitonga/venv/bin/python manage.py send_expiry_notifications >> /Users/macbookair/Desktop/kitonga/logs/cron.log 2>&1

# Clean up old devices daily at 3 AM
0 3 * * * cd /Users/macbookair/Desktop/kitonga && /Users/macbookair/Desktop/kitonga/venv/bin/python manage.py cleanup_inactive_devices >> /Users/macbookair/Desktop/kitonga/logs/cron.log 2>&1
```

3. **Save and exit** (in vi/vim: press `ESC`, type `:wq`, press ENTER)

4. **Verify crontab is set:**

```bash
crontab -l
```

---

### Method 2: Using systemd Timers (Linux - Recommended)

#### 1. Create disconnect service file:

```bash
sudo nano /etc/systemd/system/kitonga-disconnect.service
```

**Content:**

```ini
[Unit]
Description=Disconnect Expired WiFi Users
After=network.target

[Service]
Type=oneshot
User=yourusername
WorkingDirectory=/path/to/kitonga
Environment="PATH=/path/to/kitonga/venv/bin"
ExecStart=/path/to/kitonga/venv/bin/python manage.py disconnect_expired_users
StandardOutput=append:/path/to/kitonga/logs/disconnect.log
StandardError=append:/path/to/kitonga/logs/disconnect_error.log

[Install]
WantedBy=multi-user.target
```

#### 2. Create timer file:

```bash
sudo nano /etc/systemd/system/kitonga-disconnect.timer
```

**Content:**

```ini
[Unit]
Description=Run disconnect expired users every 5 minutes
Requires=kitonga-disconnect.service

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min
AccuracySec=1s

[Install]
WantedBy=timers.target
```

#### 3. Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable kitonga-disconnect.timer
sudo systemctl start kitonga-disconnect.timer
sudo systemctl status kitonga-disconnect.timer
```

---

### Method 3: Manual Testing (Before Automation)

**Test disconnect task manually:**

```bash
cd /Users/macbookair/Desktop/kitonga
source venv/bin/activate
python manage.py disconnect_expired_users
```

**Expected output:**

```
🔍 Found X expired users to disconnect
⏰ Processing expired user: 255XXXXXXXXX (tenant: tenant-name, paid_until: 2026-01-14 10:00:00, expired 2h ago)
  📱 Device AA:BB:CC:DD:EE:FF connected to router: Router1 (ID: 5)
  🏢 Tenant mode: Business Name (tenant-slug)
  📡 Tenant has 2 active routers: ['Router1', 'Router2']
  🔌 Disconnecting device AA:BB:CC:DD:EE:FF from tenant routers...
  ✅ Successfully disconnected 255XXXXXXXXX - AA:BB:CC:DD:EE:FF from 2/2 tenant routers
  ✅ Device AA:BB:CC:DD:EE:FF marked as inactive
✅ User 255XXXXXXXXX deactivated after expiration
📊 Router disconnect statistics:
  - tenant-slug:Router1: 1 users disconnected
  - tenant-slug:Router2: 1 users disconnected
🎯 Expired user cleanup complete: 1 users disconnected, 1 devices deactivated, 1 SMS sent, 0 failures
```

---

## Verification

### 1. Check if tasks are running:

```bash
# View cron jobs
crontab -l

# Check systemd timers
systemctl list-timers | grep kitonga

# View recent logs
tail -f /Users/macbookair/Desktop/kitonga/logs/cron.log
tail -f /Users/macbookair/Desktop/kitonga/logs/django.log
```

### 2. Check database for expired users:

```bash
python manage.py shell
```

```python
from billing.models import User
from django.utils import timezone

now = timezone.now()
expired = User.objects.filter(is_active=True, paid_until__lte=now)
print(f"Found {expired.count()} expired but still active users")

for user in expired:
    print(f"- {user.phone_number}: expired {(now - user.paid_until).total_seconds() / 3600:.1f} hours ago")
```

### 3. Test router connectivity:

```python
from billing.models import Router, User

# Check which routers users are connected to
for user in User.objects.filter(is_active=True):
    devices = user.devices.filter(is_active=True)
    for device in devices:
        print(f"{user.phone_number} -> {device.mac_address} -> Router: {device.router.name if device.router else 'Unknown'}")
```

---

## Troubleshooting

### Problem: Cron job not running

**Solution:**

1. Check cron is running: `sudo systemctl status cron`
2. Check logs: `grep CRON /var/log/syslog`
3. Verify Python path in crontab
4. Check file permissions

### Problem: Task runs but users not disconnected

**Solution:**

1. Check MikroTik connectivity
2. Verify router credentials in settings
3. Check tenant router associations
4. Run task manually to see detailed logs

### Problem: No router association for devices

**Solution:**

- Device should be associated with router when user connects
- Check `track_device_connection()` function in `mikrotik.py`
- Ensure router is passed when granting access

---

## Enhanced Logging

The updated task now provides detailed logs showing:

- ✅ Which router each user is connected to
- ✅ Which tenant the user belongs to
- ✅ How long they've been expired
- ✅ Disconnect success/failure per router
- ✅ Statistics per router
- ⚠️ Warnings if no routers found for tenant

**Example log output:**

```
🔍 Found 3 expired users to disconnect
⏰ Processing expired user: 255712345678 (tenant: hotel-abc, paid_until: 2026-01-14 08:00:00, expired 4h ago)
  📱 Device 11:22:33:44:55:66 connected to router: HotelRouter1 (ID: 5)
  🏢 Tenant mode: Hotel ABC (hotel-abc)
  📡 Tenant has 2 active routers: ['HotelRouter1', 'HotelRouter2']
  🔌 Disconnecting device 11:22:33:44:55:66 from tenant routers...
  ✅ Successfully disconnected 255712345678 - 11:22:33:44:55:66 from 2/2 tenant routers
  ✅ Device 11:22:33:44:55:66 marked as inactive
  🧹 Cleaning up orphaned sessions for 255712345678...
✅ User 255712345678 deactivated after expiration
📊 Router disconnect statistics:
  - hotel-abc:HotelRouter1: 3 users disconnected
  - hotel-abc:HotelRouter2: 3 users disconnected
🎯 Expired user cleanup complete: 3 users disconnected, 3 devices deactivated, 3 SMS sent, 0 failures
```

---

## Quick Fix Checklist

If users are not being disconnected after expiry:

- [ ] 1. Verify cron job is configured and running (`crontab -l`)
- [ ] 2. Run task manually to test: `python manage.py disconnect_expired_users`
- [ ] 3. Check logs for errors: `tail -f logs/django.log`
- [ ] 4. Verify MikroTik routers are accessible from server
- [ ] 5. Check router associations: users.devices should have router set
- [ ] 6. Verify tenant has active routers configured
- [ ] 7. Test MikroTik connection from admin panel

---

## Support

If you still experience issues:

1. Check logs in `/Users/macbookair/Desktop/kitonga/logs/django.log`
2. Run manual test with verbose output
3. Verify router connectivity
4. Check tenant-router associations in database
