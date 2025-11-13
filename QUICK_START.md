# Quick Start Guide - Automatic Connection & Disconnection

## What's New? 🎉

Your Kitonga Wi-Fi system now has **automatic connection** and **automatic disconnection** features!

### ✅ Automatic Connection
- When a user **pays**, they connect to internet **automatically**
- When a user **redeems a voucher**, they connect to internet **automatically**
- **No need** to disconnect and reconnect WiFi
- **Instant** internet access!

### ✅ Automatic Disconnection
- When a user's time **expires**, they are **automatically disconnected**
- Happens every 5 minutes (configurable)
- Fair usage for all customers
- No manual intervention needed!

---

## Setup in 5 Minutes ⏱️

### Step 1: Verify Files
Make sure you have these new files:
- ✅ `billing/tasks.py`
- ✅ `billing/management/commands/disconnect_expired_users.py`
- ✅ `CRON_SETUP_GUIDE.md`
- ✅ `BUG_FIXES_AND_IMPROVEMENTS.md`

### Step 2: Test Manual Disconnection
```bash
cd /Users/macbookair/Desktop/kitonga
python manage.py disconnect_expired_users
```

You should see:
```
Checking for expired users...
✓ Disconnected X expired users
Done!
```

### Step 3: Set Up Automatic Disconnection (Cron)

Open crontab:
```bash
crontab -e
```

Add this line (disconnect every 5 minutes):
```bash
*/5 * * * * cd /Users/macbookair/Desktop/kitonga && /usr/bin/python manage.py disconnect_expired_users >> /var/log/kitonga_disconnect.log 2>&1
```

Save and exit (`:wq` in vim)

### Step 4: Verify Cron is Running

Check in 5 minutes:
```bash
tail -f /var/log/kitonga_disconnect.log
```

You should see activity every 5 minutes!

---

## Testing 🧪

### Test Payment Auto-Connect:

1. Make a test payment (or use sandbox)
2. Check Django logs:
   ```bash
   tail -f logs/django.log  # or wherever your logs are
   ```
3. Look for: `✓ Automatically connected [phone] to internet`
4. User should have internet immediately!

### Test Voucher Auto-Connect:

1. Generate a voucher:
   ```bash
   python manage.py shell
   ```
   ```python
   from billing.models import Voucher
   voucher = Voucher.objects.create(
       code=Voucher.generate_code(),
       duration_hours=24,
       batch_id='TEST'
   )
   print(f"Voucher Code: {voucher.code}")
   ```

2. Redeem the voucher (include MAC and IP)
3. Check logs for: `✓ Automatically connected`
4. User should have internet immediately!

### Test Auto-Disconnect:

1. Create a test user with expired access:
   ```python
   from billing.models import User
   from django.utils import timezone
   from datetime import timedelta
   
   user = User.objects.create(
       phone_number="+255700000000",
       paid_until=timezone.now() - timedelta(hours=1)  # Expired 1 hour ago
   )
   ```

2. Run disconnect command:
   ```bash
   python manage.py disconnect_expired_users
   ```

3. User should be disconnected!
4. Check MikroTik - MAC bypass should be removed

---

## Monitoring 👀

### Check Cron Logs:
```bash
# General cron activity
grep CRON /var/log/syslog

# Your disconnect logs
tail -f /var/log/kitonga_disconnect.log
```

### Check Django Logs:
```bash
tail -f /path/to/your/django/logs/django.log
```

Look for:
- `✓ Automatically connected` - Good!
- `Disconnecting expired user` - Good!
- `Failed to revoke` - Investigate MikroTik connection
- `Error` - Check the error message

### Check MikroTik:

Using Winbox or web interface:
1. IP → Hotspot → IP Bindings - Should show bypassed MACs for active users
2. IP → Hotspot → Users - Should show active users
3. IP → Hotspot → Active - Shows currently connected users

---

## Common Issues & Solutions 🔧

### Issue: "Users not auto-connecting after payment"

**Solution:**
1. Check webhook is being received: Admin panel → Payment Webhooks
2. Check MikroTik is accessible:
   ```bash
   ping 192.168.88.1  # or your router IP
   ```
3. Check MikroTik credentials in settings.py
4. Look for errors in Django logs

### Issue: "Users not being disconnected"

**Solution:**
1. Check cron is running:
   ```bash
   crontab -l  # Should show your cron job
   ```
2. Check cron logs:
   ```bash
   tail -f /var/log/kitonga_disconnect.log
   ```
3. Run manually to test:
   ```bash
   python manage.py disconnect_expired_users
   ```
4. Check for errors in output

### Issue: "Permission denied"

**Solution:**
```bash
chmod +x manage.py
# Make sure the user running cron has access to the project
```

---

## What Happens Behind the Scenes? 🔍

### Payment Flow:
```
User pays → ClickPesa webhook → Mark payment complete →
Find user's devices → For each device:
  - Call grant_user_access()
  - Create/update hotspot user
  - Bypass MAC in MikroTik
→ User has internet!
```

### Voucher Flow:
```
User redeems voucher → Validate voucher → Mark as used →
Grant access time → If MAC provided:
  - Call grant_user_access()
  - Create/update hotspot user  
  - Bypass MAC in MikroTik
→ User has internet!
```

### Expiration Flow:
```
Cron runs every 5 min → Find expired users →
For each expired user:
  - Get their devices
  - Call revoke_user_access()
  - Remove MAC bypass
  - Disable hotspot user
  - Mark user inactive
→ User disconnected!
```

---

## Customization ⚙️

### Change Disconnection Frequency:

Edit crontab:
```bash
# Every 3 minutes
*/3 * * * * cd /Users/macbookair/Desktop/kitonga && python manage.py disconnect_expired_users

# Every 10 minutes
*/10 * * * * cd /Users/macbookair/Desktop/kitonga && python manage.py disconnect_expired_users

# Every hour
0 * * * * cd /Users/macbookair/Desktop/kitonga && python manage.py disconnect_expired_users
```

### Change Inactive Device Threshold:

Edit `billing/tasks.py`, line 79:
```python
# Currently: 30 days
threshold = timezone.now() - timedelta(days=30)

# Change to: 60 days
threshold = timezone.now() - timedelta(days=60)

# Change to: 7 days
threshold = timezone.now() - timedelta(days=7)
```

---

## Production Checklist ✓

Before going live, verify:

- [ ] MikroTik is accessible from Django server
- [ ] MikroTik credentials are correct in settings.py
- [ ] Cron job is set up and running
- [ ] Tested payment auto-connect (works!)
- [ ] Tested voucher auto-connect (works!)
- [ ] Tested auto-disconnect (works!)
- [ ] Logs are being written
- [ ] Log rotation is set up (prevents huge log files)
- [ ] Monitoring is in place
- [ ] Backup is configured

---

## Getting Help 🆘

1. **Check logs first** - Most issues show up in logs
2. **Run commands manually** - Helps isolate the problem
3. **Test MikroTik connectivity** - Ensure API is accessible
4. **Review the documentation**:
   - `BUG_FIXES_AND_IMPROVEMENTS.md` - Detailed technical info
   - `CRON_SETUP_GUIDE.md` - Advanced cron setup
   - This file - Quick reference

---

## Summary 📝

**What you got:**
- ✅ Automatic internet connection after payment
- ✅ Automatic internet connection after voucher redemption  
- ✅ Automatic disconnection when time expires
- ✅ Device management and cleanup
- ✅ Better user experience
- ✅ Less manual work for you!

**What you need to do:**
1. Test the features (5 minutes)
2. Set up cron job (2 minutes)
3. Monitor for a few days
4. Enjoy automated billing! 🎉

---

**That's it! Your system is now fully automated!** 🚀

For detailed information, see:
- `BUG_FIXES_AND_IMPROVEMENTS.md` - Complete technical details
- `CRON_SETUP_GUIDE.md` - Advanced setup options
