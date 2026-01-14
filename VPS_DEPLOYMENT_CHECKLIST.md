# 🚀 VPS Deployment Checklist - Automatic User Disconnection

## ✅ Pre-Deployment (Do This First)

- [ ] Your code is committed and pushed to Git
- [ ] `.env` file has correct production settings (DB password, MikroTik credentials, NextSMS)
- [ ] You have SSH access to your VPS
- [ ] You know your VPS deployment path (default: `/var/www/kitonga`)

## 📦 Deployment Steps

### 1. SSH into Your VPS

```bash
ssh your-user@your-vps-ip
# Example: ssh root@api.kitonga.klikcell.com
```

### 2. Navigate to Your Project

```bash
cd /var/www/kitonga
# Or wherever your project is deployed
```

### 3. Pull Latest Code

```bash
git pull origin main
# Or your branch name
```

### 4. Run Deployment Script

```bash
bash deploy.sh
```

**The script will:**

- ✅ Activate virtual environment
- ✅ Install/update dependencies
- ✅ Run database migrations
- ✅ Collect static files
- ✅ **Ask if you want to setup cron jobs** (SAY YES!)
- ✅ Restart the application

### 5. Verify Cron Jobs Were Installed

```bash
crontab -l
```

**You should see:**

```
*/5 * * * * cd /var/www/kitonga && .../python manage.py disconnect_expired_users >> .../logs/cron.log 2>&1
0 * * * * cd /var/www/kitonga && .../python manage.py send_expiry_notifications >> .../logs/cron.log 2>&1
0 2 * * * cd /var/www/kitonga && .../python manage.py cleanup_inactive_devices >> .../logs/cron.log 2>&1
```

### 6. Test Manually (Important!)

```bash
cd /var/www/kitonga
source venv/bin/activate
python manage.py disconnect_expired_users
```

**Expected output:**

```
INFO: 🔍 Found X expired users to disconnect
INFO: 🎯 Expired user cleanup complete: X users disconnected...
```

### 7. Wait 5-10 Minutes, Then Check Logs

```bash
tail -f /var/www/kitonga/logs/cron.log
```

**You should see new entries every 5 minutes** with timestamps and emoji markers (🔍 ✅ ❌ 📱).

## 🧪 Testing the Complete Flow

### Create a Test User with Short Expiry

1. **Via Admin Panel:**

   - Create user: `+255123456789` (or your test number)
   - Set paid_until: `Current time + 5 minutes`
   - Activate user

2. **Connect to WiFi:**

   - Connect device to your WiFi hotspot
   - Login with the test phone number

3. **Wait and Monitor:**
   - **After 4 minutes:** User should receive expiry warning SMS
   - **After 5 minutes:** User should be disconnected from MikroTik
   - **Check MikroTik:** User should be disabled
   - **Check logs:** Should show disconnection with router details

### Verify Disconnection

```bash
# Check task status
python manage.py check_task_status

# Should show:
# ✅ No expired users found - tasks working correctly!
```

## 🔍 Monitoring Commands

### Check Cron is Running

```bash
sudo systemctl status cron
```

### View Recent Cron Executions

```bash
grep CRON /var/log/syslog | tail -20
```

### Monitor Live Logs

```bash
# Cron task logs
tail -f /var/www/kitonga/logs/cron.log

# Django application logs
tail -f /var/www/kitonga/logs/django.log
```

### Check for Errors

```bash
# Errors in last hour
grep "❌" /var/www/kitonga/logs/cron.log | grep "$(date +'%Y-%m-%d %H')"

# Failed disconnections
grep "Failed to disconnect" /var/www/kitonga/logs/django.log | tail -20
```

## 🚨 Troubleshooting

### Cron Jobs Not Running?

**Problem:** No entries in `cron.log` after 10 minutes

**Solutions:**

1. Check cron service: `sudo systemctl status cron`
2. Check syslog: `grep CRON /var/log/syslog | tail`
3. Verify crontab: `crontab -l`
4. Check permissions: `ls -la /var/www/kitonga/logs/`
5. Create logs dir: `mkdir -p /var/www/kitonga/logs`

### Users Not Getting Disconnected?

**Problem:** Users receive SMS but stay connected

**Solutions:**

1. Check cron is installed: `crontab -l`
2. Run manually: `python manage.py disconnect_expired_users`
3. Check MikroTik connection: Test from VPS, not local machine
4. Verify `.env` has correct MikroTik credentials
5. Check logs for error messages with ❌ emoji

### Database Connection Errors?

**Problem:** `Can't connect to MySQL server`

**Solutions:**

1. Check `.env` file: `cat /var/www/kitonga/.env | grep DB_`
2. Test connection: `python manage.py dbshell`
3. Verify database is running: `sudo systemctl status mysql`
4. Check database user has permissions

### Permission Errors?

**Problem:** `Permission denied` in logs

**Solutions:**

1. Check file ownership: `ls -la /var/www/kitonga`
2. Fix permissions: `sudo chown -R www-data:www-data /var/www/kitonga`
3. Logs directory: `sudo chmod 755 /var/www/kitonga/logs`

## ✅ Success Indicators

You'll know everything is working when:

- ✅ `crontab -l` shows 3 scheduled tasks
- ✅ `/var/www/kitonga/logs/cron.log` has entries every 5 minutes
- ✅ `python manage.py check_task_status` shows no expired users
- ✅ Test user gets SMS 1 hour before expiry
- ✅ Test user gets disconnected within 5 minutes of expiry
- ✅ MikroTik shows user disabled
- ✅ Logs show emoji markers (🔍 ✅ 📱 📊)
- ✅ No error messages (❌) in logs

## 📊 What Gets Logged?

Every 5 minutes you should see:

```
[2026-01-14 10:00:01] INFO: 🔍 Found 3 expired users to disconnect
[2026-01-14 10:00:01] INFO: ⏰ Processing expired user: +255712345678 (tenant: abc-company, paid_until: 2026-01-14 09:55:00, expired 5h ago)
[2026-01-14 10:00:01] INFO:   📱 Device AA:BB:CC:DD:EE:FF connected to router: Main Office (ID: 1)
[2026-01-14 10:00:02] INFO:   ✅ Successfully disconnected user from tenant routers
[2026-01-14 10:00:02] INFO:   ✅ Device marked as inactive
[2026-01-14 10:00:02] INFO: ✅ User +255712345678 deactivated after expiration
[2026-01-14 10:00:03] INFO: 📊 Router disconnect statistics:
[2026-01-14 10:00:03] INFO:   - Main Office: 2 users disconnected
[2026-01-14 10:00:03] INFO:   - Branch Router: 1 users disconnected
[2026-01-14 10:00:03] INFO: 🎯 Expired user cleanup complete: 3 users disconnected, 5 devices deactivated, 3 SMS sent, 0 failures
```

## 📖 Additional Resources

- **Full Setup Guide:** `docs/VPS_CRON_SETUP.md`
- **Task Scheduling:** `docs/TASK_SCHEDULING_SETUP.md`
- **Changes Summary:** `FIXES_APPLIED.md`
- **General Deployment:** `docs/DEPLOYMENT.md`

## 🎯 Remember

**The CODE is ready!** All the fixes are done. Now you just need to:

1. Deploy to VPS (`bash deploy.sh`)
2. Setup cron jobs (automated in deploy script)
3. Test with a short-expiry user
4. Monitor logs for 24 hours

After that, users **WILL** be automatically disconnected within 5 minutes of their access expiring! 🎉

---

**Need Help?**

- Check logs: `tail -f /var/www/kitonga/logs/cron.log`
- Run diagnostics: `python manage.py check_task_status`
- Test manually: `python manage.py disconnect_expired_users`
