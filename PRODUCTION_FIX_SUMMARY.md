# Production MikroTik Error Fix Summary

## Problem
```
Error: [Errno 111] Connection refused
URL: https://api.kitonga.klikcell.com/api/admin/mikrotik/active-users/
Status: 500 Internal Server Error
```

## Root Cause
Your **production server** at `api.kitonga.klikcell.com` cannot connect to your **MikroTik router** at `192.168.0.173:8728` because:

1. ❌ **Private IP Address** - `192.168.0.173` is only accessible on your local network
2. ❌ **Network Separation** - Production server is on the internet, router is on home network
3. ✅ **Works Locally** - Your dev machine can reach the router (same network)

## Immediate Fix (5 Minutes) ⚡

Add this to your production `.env` file:

```bash
MIKROTIK_MOCK_MODE=true
```

**Effect:**
- ✅ Stops 500 errors
- ✅ Returns graceful error messages
- ✅ Other API endpoints continue working
- ❌ Router features unavailable until proper solution implemented

### How to Apply:

```bash
# SSH to production
ssh user@api.kitonga.klikcell.com

# Edit environment file
nano /path/to/your/.env

# Add this line
MIKROTIK_MOCK_MODE=true

# Restart your Django app
sudo systemctl restart gunicorn
# OR
sudo supervisorctl restart kitonga
# OR
docker-compose restart
```

## Permanent Solutions

### Option 1: VPN (Best Practice) ⭐

**Time:** 1-2 hours  
**Security:** Excellent  
**Complexity:** Medium

Set up WireGuard VPN to securely connect production server to your home network.

📖 **Full Guide:** See `PRODUCTION_MIKROTIK_SETUP_GUIDE.md` → Option 1

**Quick Steps:**
1. Configure WireGuard on MikroTik router
2. Install WireGuard on production server
3. Connect via VPN tunnel
4. Router becomes accessible at `192.168.0.173` through VPN

### Option 2: Port Forwarding (Quick but Less Secure) ⚠️

**Time:** 30 minutes  
**Security:** Moderate (requires strong passwords + firewall rules)  
**Complexity:** Low

Forward port 8728 from your public IP to the router.

📖 **Full Guide:** See `PRODUCTION_MIKROTIK_SETUP_GUIDE.md` → Option 3

**Security Requirements:**
- Strong router password
- IP whitelisting (only allow production server IP)
- Consider changing default port 8728
- Enable API SSL if possible

## Code Changes Made

### 1. Fixed Variable Scope Bugs ✅
Fixed 6 functions in `billing/mikrotik.py` that had the bug:
- `get_hotspot_profiles()` ✅
- `create_hotspot_profile()` ✅
- `disconnect_all_hotspot_users()` ✅
- `cleanup_disabled_users()` ✅
- `get_router_health()` ✅
- `monitor_interface_traffic()` ✅

**What was wrong:**
```python
# BEFORE (Bug)
def get_hotspot_profiles():
    try:
        api = get_mikrotik_api()  # api defined inside try
        # ...
    finally:
        safe_close(api)  # ERROR: api not defined if exception before assignment
```

**What was fixed:**
```python
# AFTER (Fixed)
def get_hotspot_profiles():
    api = None  # Initialize before try
    try:
        api = get_mikrotik_api()
        # ...
    finally:
        if api is not None:  # Check before closing
            safe_close(api)
```

### 2. Added Mock Mode Support ✅
Added `MIKROTIK_MOCK_MODE` environment variable to gracefully handle connection failures.

```python
# At top of billing/mikrotik.py
MIKROTIK_MOCK_MODE = os.getenv('MIKROTIK_MOCK_MODE', 'false').lower() == 'true'

def get_mikrotik_api():
    if MIKROTIK_MOCK_MODE:
        raise ConnectionRefusedError('MikroTik router not accessible in this environment')
    # ... rest of code
```

## Testing

### Test Local (Should Work) ✅
```bash
python test_mikrotik_specific_endpoints.py
```

Expected: All tests pass ✅

### Test Production (Before Fix) ❌
```bash
curl https://api.kitonga.klikcell.com/api/admin/mikrotik/profiles/ \
  -H "X-Admin-Access: kitonga_admin_2025"
```

Expected: `{"success": false, "message": "[Errno 111] Connection refused"}`

### Test Production (After Mock Mode) ✅
```bash
# After adding MIKROTIK_MOCK_MODE=true
curl https://api.kitonga.klikcell.com/api/admin/mikrotik/profiles/ \
  -H "X-Admin-Access: kitonga_admin_2025"
```

Expected: `{"success": false, "message": "MikroTik router not accessible in this environment"}`

### Test Production (After VPN Setup) ✅
```bash
# After configuring VPN and setting MIKROTIK_MOCK_MODE=false
curl https://api.kitonga.klikcell.com/api/admin/mikrotik/profiles/ \
  -H "X-Admin-Access: kitonga_admin_2025"
```

Expected: `{"success": true, "profiles": [...]}`

## Files Created

1. ✅ `PRODUCTION_MIKROTIK_SETUP_GUIDE.md` - Comprehensive setup guide
2. ✅ `fix_production_mikrotik.sh` - Quick reference script
3. ✅ `PRODUCTION_FIX_SUMMARY.md` - This file

## Files Modified

1. ✅ `billing/mikrotik.py` - Fixed 6 functions + added mock mode
2. ✅ `requirements.txt` - Updated routeros-api to 0.21.0

## Deployment Checklist

### Immediate (Do Now)
- [ ] Push code changes to production
- [ ] Add `MIKROTIK_MOCK_MODE=true` to production `.env`
- [ ] Restart Django application
- [ ] Verify API returns graceful errors

### Short Term (This Week)
- [ ] Set up WireGuard VPN on MikroTik router
- [ ] Install WireGuard on production server
- [ ] Test VPN connection
- [ ] Update `.env` with `MIKROTIK_MOCK_MODE=false`
- [ ] Test all MikroTik endpoints work from production

### Long Term (Future)
- [ ] Monitor connection stability
- [ ] Set up alerts for connection failures
- [ ] Consider infrastructure improvements
- [ ] Document network architecture

## Support & Troubleshooting

### Connection Still Fails After VPN
1. Check VPN is active: `sudo wg show`
2. Test router reachable: `ping 192.168.0.173`
3. Test port open: `nc -zv 192.168.0.173 8728`
4. Check Django logs: `tail -f /var/log/django/error.log`

### Frontend Shows Router Errors
Update frontend to handle graceful errors:
```javascript
try {
  const profiles = await api.getMikrotikHotspotProfiles();
} catch (error) {
  if (error.message.includes('not accessible')) {
    // Show friendly message: "Router features temporarily unavailable"
  }
}
```

### Need Help?
- Full documentation: `PRODUCTION_MIKROTIK_SETUP_GUIDE.md`
- MikroTik VPN guide: https://help.mikrotik.com/docs/display/ROS/WireGuard
- WireGuard docs: https://www.wireguard.com/quickstart/

---

**Last Updated:** November 13, 2025  
**Status:** ✅ Code fixes applied, awaiting production deployment
