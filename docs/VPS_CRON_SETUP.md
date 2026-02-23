# VPS Cron Job Setup for Automatic User Disconnection

## 🚀 CRITICAL: This Must Be Done on Your VPS

The automatic user disconnection **will NOT work** until you set up cron jobs on your VPS server. This guide shows you exactly how to do it.

## 📋 Prerequisites

- SSH access to your VPS
- Application deployed to `/var/www/kitonga` (or your deployment path)
- Python virtual environment activated

## 🔧 Quick Setup (Recommended)

### Option 1: Use the Automated Setup Script

1. **SSH into your VPS:**

```bash
ssh your-user@your-vps-ip
```

2. **Navigate to your project:**

```bash
cd /var/www/kitonga
```

3. **Run the setup script:**

```bash
bash setup_tasks.sh
```

4. **Follow the prompts** - it will automatically:
   - Detect your Python environment
   - Create cron entries
   - Backup existing crontab
   - Install the jobs

### Option 2: Manual Setup

If you prefer to set up manually:

1. **SSH into your VPS:**

```bash
ssh your-user@your-vps-ip
```

2. **Edit crontab:**

```bash
crontab -e
```

3. **Add these lines** (replace paths if your setup is different):

```bash
# Kitonga WiFi - Automatic User Disconnection
# Runs every 5 minutes to disconnect expired users from MikroTik
*/5 * * * * cd /var/www/kitonga && /var/www/kitonga/venv/bin/python manage.py disconnect_expired_users >> /var/www/kitonga/logs/cron.log 2>&1

# Kitonga WiFi - Expiry Notifications
# Runs every hour to send 1-hour warning SMS to users
0 * * * * cd /var/www/kitonga && /var/www/kitonga/venv/bin/python manage.py send_expiry_notifications >> /var/www/kitonga/logs/cron.log 2>&1

# Kitonga WiFi - Clean Up Old Devices
# Runs daily at 2 AM to deactivate devices not seen in 30+ days
0 2 * * * cd /var/www/kitonga && /var/www/kitonga/venv/bin/python manage.py cleanup_inactive_devices >> /var/www/kitonga/logs/cron.log 2>&1

# ── VPN / Remote Access Tasks ──
# Disable expired remote VPN users every 5 minutes
*/5 * * * * cd /var/www/kitonga && /var/www/kitonga/venv/bin/python manage.py vpn_tasks --expire >> /var/www/kitonga/logs/cron.log 2>&1

# Send VPN expiry warnings every hour (24h and 3h before)
0 * * * * cd /var/www/kitonga && /var/www/kitonga/venv/bin/python manage.py vpn_tasks --notify >> /var/www/kitonga/logs/cron.log 2>&1

# Health check VPN interfaces every 15 minutes
*/15 * * * * cd /var/www/kitonga && /var/www/kitonga/venv/bin/python manage.py vpn_tasks --health >> /var/www/kitonga/logs/cron.log 2>&1
```

4. **Save and exit** (Ctrl+X, then Y, then Enter for nano)

5. **Verify cron jobs are installed:**

```bash
crontab -l
```

## ✅ Verification Steps

### 1. Check Cron Jobs Are Running

Wait 5-10 minutes, then check the log:

```bash
tail -f /var/www/kitonga/logs/cron.log
```

You should see entries like:

```
INFO: 🔍 Found X expired users to disconnect
INFO: 🎯 Expired user cleanup complete: X users disconnected, X devices deactivated
```

### 2. Check Django Logs

```bash
tail -f /var/www/kitonga/logs/django.log
```

Look for emoji markers:

- 🔍 = Scanning for expired users
- ✅ = Successfully disconnected
- ❌ = Error occurred
- ⚠️ = Warning
- 📱 = SMS sent
- 📊 = Statistics

### 3. Manual Test

Run the command manually to verify it works:

```bash
cd /var/www/kitonga
source venv/bin/activate
python manage.py disconnect_expired_users
```

Expected output:

```
INFO: 🔍 Found X expired users to disconnect
INFO: ⏰ Processing expired user: +255... (tenant: your-tenant, paid_until: ...)
INFO: 📱 Device XX:XX:XX:XX:XX:XX connected to router: RouterName (ID: X)
INFO: ✅ Successfully disconnected user from tenant routers
INFO: 🎯 Expired user cleanup complete: X users disconnected, X devices deactivated, X SMS sent
```

### 4. Check Task Status

```bash
python manage.py check_task_status
```

This diagnostic tool will show:

- Any expired users still connected
- Which routers they're on
- Recommendations for action

## 🛠️ Troubleshooting

### Cron Jobs Not Running?

**Check cron service is running:**

```bash
sudo systemctl status cron
```

**Check syslog for cron execution:**

```bash
grep CRON /var/log/syslog | tail -20
```

### No Log Output?

**Ensure logs directory exists:**

```bash
mkdir -p /var/www/kitonga/logs
chmod 755 /var/www/kitonga/logs
```

**Check file permissions:**

```bash
ls -la /var/www/kitonga/logs/
```

### Python Command Fails?

**Verify virtual environment path:**

```bash
which python
# Should show: /var/www/kitonga/venv/bin/python
```

**Test Python can find Django:**

```bash
cd /var/www/kitonga
source venv/bin/activate
python -c "import django; print(django.get_version())"
```

### Database Connection Errors?

**Check .env file on VPS:**

```bash
cat /var/www/kitonga/.env | grep DB_
```

Ensure these are set correctly:

- `DB_HOST=localhost` (or your database server)
- `DB_NAME=kitonga`
- `DB_USER=root` (or your database user)
- `DB_PASSWORD=YourSecurePassword`

**Test database connection:**

```bash
python manage.py dbshell
# Should connect to MySQL/PostgreSQL
```

## 📊 What Happens When Cron Runs?

Every 5 minutes, the system:

1. **Scans for expired users** (paid_until <= now)
2. **Identifies their routers** (which MikroTik each device is on)
3. **Identifies their tenant** (which business they belong to)
4. **Sends expiry SMS** (via NextSMS)
5. **Disconnects from MikroTik:**
   - Removes active sessions
   - Deletes IP bindings
   - Disables hotspot user
6. **Deactivates devices** (marks as inactive in database)
7. **Deactivates user** (sets is_active=False)
8. **Logs everything** with emoji markers for easy monitoring

## 🔐 Security Notes

- Cron runs as the user who installed it (typically `www-data` or your deployment user)
- Logs are written to `/var/www/kitonga/logs/cron.log` - rotate these regularly
- Database credentials are in `.env` - ensure proper file permissions (600)
- MikroTik API credentials are in `.env` - keep secure

## 📝 Monitoring Best Practices

### Set up log rotation

Create `/etc/logrotate.d/kitonga`:

```
/var/www/kitonga/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload kitonga
    endscript
}
```

### Monitor cron execution

Add this to your monitoring:

```bash
# Check last successful run
grep "🎯 Expired user cleanup complete" /var/www/kitonga/logs/cron.log | tail -1
```

### Alert on errors

```bash
# Count errors in last hour
grep "❌" /var/www/kitonga/logs/cron.log | grep "$(date +'%Y-%m-%d %H')" | wc -l
```

## 🚨 IMPORTANT: After Deployment

1. **Test immediately** after setting up cron:
   - Create a test user with short expiry (5 minutes)
   - Wait for expiry
   - Verify they receive SMS
   - Verify they get disconnected within 5 minutes
   - Check MikroTik shows user disabled

2. **Monitor logs for first 24 hours** to ensure:
   - Cron runs every 5 minutes
   - No permission errors
   - No database connection issues
   - MikroTik disconnections succeed

3. **Set up alerting** for:
   - Failed disconnections
   - Database errors
   - MikroTik connection failures

## 🎯 Success Criteria

You'll know it's working when:

✅ `crontab -l` shows the scheduled tasks
✅ `/var/www/kitonga/logs/cron.log` has entries every 5 minutes
✅ Expired users appear in logs with 🔍 emoji
✅ Successful disconnections show ✅ emoji
✅ `python manage.py check_task_status` shows no expired users still connected
✅ Test user gets disconnected within 5 minutes of expiry
✅ MikroTik admin panel shows users disabled

## 📞 Need Help?

If automatic disconnection still doesn't work after setup:

1. Check cron is running: `sudo systemctl status cron`
2. Check logs: `tail -f /var/www/kitonga/logs/cron.log`
3. Run manually: `python manage.py disconnect_expired_users`
4. Check task status: `python manage.py check_task_status`
5. Verify MikroTik connectivity from VPS: `python manage.py test_mikrotik_connection`

---

**Remember:** This setup must be done **on your VPS**, not on your local development machine!
