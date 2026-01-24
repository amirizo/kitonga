# Real-Time Access Expiry Watcher Setup Guide

This guide explains how to set up the real-time access expiry watcher on your VPS. The watcher monitors user access expiration and **automatically disconnects users the moment their access expires** (not every 5 minutes like cron).

## 📋 Overview

The Expiry Watcher system provides:

1. **Real-time monitoring** - Checks for expired users every 30 seconds
2. **Immediate disconnection** - Users are kicked off MikroTik the moment their time expires
3. **Multiple deployment options** - Run as a service, with Django, or via cron

---

## 🚀 Option 1: Systemd Service (Recommended for Production)

This runs the watcher as a dedicated background service that starts automatically on boot.

### Step 1: Copy the service file

```bash
# SSH into your VPS
ssh user@your-vps-ip

# Copy the service file
sudo cp /path/to/kitonga/kitonga-expiry-watcher.service /etc/systemd/system/

# Or create it manually:
sudo nano /etc/systemd/system/kitonga-expiry-watcher.service
```

### Step 2: Edit the service file paths

Make sure the paths match your VPS setup:

```ini
[Unit]
Description=Kitonga WiFi Access Expiry Watcher
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/kitonga
Environment="PATH=/var/www/kitonga/venv/bin"
Environment="DJANGO_SETTINGS_MODULE=kitonga.settings"
ExecStart=/var/www/kitonga/venv/bin/python manage.py run_expiry_watcher --interval 30
Restart=always
RestartSec=10
StandardOutput=append:/var/log/kitonga/expiry_watcher.log
StandardError=append:/var/log/kitonga/expiry_watcher_error.log

[Install]
WantedBy=multi-user.target
```

### Step 3: Create log directory

```bash
sudo mkdir -p /var/log/kitonga
sudo chown www-data:www-data /var/log/kitonga
```

### Step 4: Enable and start the service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable kitonga-expiry-watcher

# Start the service
sudo systemctl start kitonga-expiry-watcher

# Check status
sudo systemctl status kitonga-expiry-watcher
```

### Step 5: View logs

```bash
# View live logs
sudo tail -f /var/log/kitonga/expiry_watcher.log

# View errors
sudo tail -f /var/log/kitonga/expiry_watcher_error.log
```

### Managing the service

```bash
# Stop watcher
sudo systemctl stop kitonga-expiry-watcher

# Restart watcher
sudo systemctl restart kitonga-expiry-watcher

# Check if running
sudo systemctl is-active kitonga-expiry-watcher
```

---

## 🔧 Option 2: Run with Django (Auto-start)

The watcher can auto-start when Django starts by setting an environment variable.

### Enable auto-start

Add to your Django environment (e.g., in `/etc/environment`, `.env`, or Gunicorn service):

```bash
EXPIRY_WATCHER_ENABLED=true
```

For Gunicorn, add to your service file:

```ini
Environment="EXPIRY_WATCHER_ENABLED=true"
```

Then restart Gunicorn:

```bash
sudo systemctl restart gunicorn  # or your Django service name
```

⚠️ **Note**: This runs the watcher inside Django's process. If Django restarts, the watcher also restarts. For more reliability, use Option 1.

---

## ⏰ Option 3: Use Cron (Simpler but less real-time)

If you prefer cron, you can run the watcher check every minute:

```bash
# Edit crontab
crontab -e

# Add this line (runs every minute):
* * * * * cd /var/www/kitonga && /var/www/kitonga/venv/bin/python manage.py run_expiry_watcher --once >> /var/log/kitonga/cron_expiry.log 2>&1
```

This is less real-time (up to 1-minute delay) but simpler to set up.

---

## 🧪 Testing the Watcher

### Test via Management Command

```bash
# SSH to your VPS
cd /var/www/kitonga
source venv/bin/activate

# Run a single check
python manage.py run_expiry_watcher --once

# Run continuously (for testing, Ctrl+C to stop)
python manage.py run_expiry_watcher --interval 10
```

### Test via API

```bash
# Check watcher status
curl -X GET "https://api.kitonga.klikcell.com/api/admin/expiry-watcher/" \
  -H "X-Admin-Token: kitonga_admin_2025"

# Trigger manual check
curl -X POST "https://api.kitonga.klikcell.com/api/admin/expiry-watcher/" \
  -H "X-Admin-Token: kitonga_admin_2025"
```

### Expected API Response

```json
{
  "success": true,
  "watcher": {
    "running": true,
    "check_interval_seconds": 30
  },
  "statistics": {
    "total_active_users": 15,
    "expiring_in_30_min": 2,
    "expired_but_still_active": 0
  },
  "expiring_soon": [
    {
      "id": 42,
      "phone_number": "255772236727",
      "expires_at": "2025-12-15T12:30:00Z",
      "remaining_minutes": 5
    }
  ],
  "expired_not_disconnected": [],
  "health": "healthy",
  "timestamp": "2025-12-15T12:25:00Z"
}
```

If `expired_not_disconnected` is empty, the watcher is working correctly!

---

## 📊 Monitoring

### Check for problems

The watcher logs to `/var/log/kitonga/expiry_watcher.log`. Look for:

```
✅ Good:
⏰ Found 2 expired user(s) to disconnect
🔌 Disconnecting expired user: 255772236727
  ✓ Disconnected device AA:BB:CC:DD:EE:FF
  ✓ User 255772236727 fully disconnected

❌ Problems:
Error disconnecting device: Connection refused
Error in expiry watcher loop: Database connection failed
```

### Health check endpoint

```bash
# Returns health status
curl "https://api.kitonga.klikcell.com/api/admin/expiry-watcher/" \
  -H "X-Admin-Token: kitonga_admin_2025"
```

If `health: "needs_attention"`, there are expired users still connected. Trigger a manual cleanup:

```bash
curl -X POST "https://api.kitonga.klikcell.com/api/admin/cleanup-expired/" \
  -H "X-Admin-Token: kitonga_admin_2025"
```

---

## 🔄 Comparison: Watcher vs Cron

| Feature | Expiry Watcher | Cron (every 5 min) |
|---------|----------------|-------------------|
| **Delay** | ~30 seconds | Up to 5 minutes |
| **Real-time** | ✅ Yes | ❌ No |
| **Resource usage** | Constant (low) | Periodic |
| **Complexity** | Medium | Simple |
| **Reliability** | High (systemd) | Medium |

---

## 🛠 Troubleshooting

### Watcher not starting

```bash
# Check service status
sudo systemctl status kitonga-expiry-watcher

# Check logs for errors
sudo journalctl -u kitonga-expiry-watcher -n 50
```

### Database connection errors

The watcher handles database reconnection automatically, but if issues persist:

```bash
# Restart the watcher
sudo systemctl restart kitonga-expiry-watcher
```

### MikroTik connection errors

Check that:
1. MikroTik API is enabled on the router
2. Network connectivity between VPS and router is working
3. MikroTik credentials in Django settings are correct

```bash
# Test MikroTik connection via API
curl "https://api.kitonga.klikcell.com/api/admin/mikrotik/test-connection/" \
  -H "X-Admin-Token: kitonga_admin_2025"
```

---

## ✅ Quick Setup Checklist

1. [ ] SSH into VPS
2. [ ] Pull latest code: `git pull`
3. [ ] Install requirements: `pip install -r requirements.txt`
4. [ ] Run migrations: `python manage.py migrate`
5. [ ] Copy service file: `sudo cp kitonga-expiry-watcher.service /etc/systemd/system/`
6. [ ] Create log dir: `sudo mkdir -p /var/log/kitonga && sudo chown www-data:www-data /var/log/kitonga`
7. [ ] Enable service: `sudo systemctl enable kitonga-expiry-watcher`
8. [ ] Start service: `sudo systemctl start kitonga-expiry-watcher`
9. [ ] Verify: `sudo systemctl status kitonga-expiry-watcher`
10. [ ] Test API: `curl -X GET "https://api.kitonga.klikcell.com/api/admin/expiry-watcher/" -H "X-Admin-Token: kitonga_admin_2025"`

Done! Users will now be disconnected within 30 seconds of their access expiring. 🎉
