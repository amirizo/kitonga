# Shared Hosting MikroTik Setup Guide

## Your Hosting Environment

**Provider:** klikcell.com (cPanel Shared Hosting)  
**Server IP:** 162.0.215.155  
**Your Public IP:** 162.0.215.152  
**Home Directory:** /home/thebkihw  
**Control Panel:** cPanel (jupiter theme)

## Problem

❌ **Shared hosting CANNOT connect to your local MikroTik router** because:
1. No VPN installation allowed (requires root access)
2. Cannot modify network/firewall settings
3. Router is on private network (192.168.0.173)
4. No way to create secure tunnel

## ONLY Solution: Mock Mode + Manual Router Management

### Step 1: Enable Mock Mode

1. **Login to cPanel** at your hosting control panel

2. **Navigate to File Manager**
   - Go to: `/home/thebkihw/api.kitonga.klikcell.com/`
   - Find your `.env` file

3. **Edit .env file**
   - Click on `.env` file
   - Click "Edit" button
   - Add this line:
   ```bash
   MIKROTIK_MOCK_MODE=true
   ```
   - Save the file

4. **Restart your application**
   ```bash
   # If using Passenger (most common on shared hosting)
   touch /home/thebkihw/api.kitonga.klikcell.com/tmp/restart.txt
   
   # Or restart via cPanel Terminal
   cd ~/api.kitonga.klikcell.com
   python manage.py collectstatic --noinput
   ```

### Step 2: Update Your Code

**Via cPanel File Manager or Terminal:**

```bash
# Login via SSH (if available)
ssh thebkihw@klikcell.com

# Navigate to project
cd ~/api.kitonga.klikcell.com

# Pull latest changes (if using git)
git pull origin main

# Or upload files via cPanel File Manager
```

### Step 3: Install Updated Dependencies

Via cPanel Terminal or SSH:

```bash
cd ~/api.kitonga.klikcell.com

# If you have pip access
pip install --user -r requirements.txt

# Or via Python Selector in cPanel
# (Most shared hosting uses Python Selector for package management)
```

### Step 4: Verify It Works

Test your API endpoint:

```bash
curl -X GET https://api.kitonga.klikcell.com/api/admin/mikrotik/profiles/ \
  -H "X-Admin-Access: kitonga_admin_2025"
```

**Expected Response:**
```json
{
  "success": false,
  "message": "MikroTik router not accessible in this environment"
}
```

This is **correct behavior** - graceful error instead of 500 crash! ✅

---

## What This Means for Your System

### ✅ What WILL Work (Core Features):

#### User Features (All Working!)
- ✅ **Payment Processing** - ClickPesa integration works
- ✅ **Voucher System** - Generation and redemption works
- ✅ **User Gets Internet After Payment** - Router checks database ✅
- ✅ **Automatic Disconnection** - When bundle expires ✅
- ✅ **User Authentication** - Login and access control works
- ✅ **Bundle Management** - Create, update, delete bundles
- ✅ **Database Operations** - All CRUD operations work

#### How Users Get Internet (THIS WORKS!)
```
1. User Pays
   → Production API processes payment
   → Database updated: user.has_active_access = True
   → User gets confirmation

2. User Connects to WiFi
   → Router (local) checks Production Database
   → Database returns: "User has valid access"
   → Router GRANTS internet access ✅

3. Bundle Expires
   → Database status automatically changes
   → Router checks database again
   → Router DENIES/DISCONNECTS user ✅
```

**🎯 IMPORTANT: Mock Mode does NOT affect user internet access!**
- Router still checks your production database
- Users still get internet after payment
- Automatic disconnection still works
- Only admin remote control is disabled

### ❌ What Won't Work (Admin Features Only):

These are **ADMIN ONLY** features that don't affect end users:

- ❌ View active users from production admin dashboard
- ❌ Disconnect specific user from production admin dashboard
- ❌ View router CPU/memory from production
- ❌ Manage hotspot profiles from production dashboard

**Workaround:** Access these features locally:
- Use MikroTik WinBox/WebFig from your office
- Use your local dev environment for router management
- Or just check router locally when needed

### 🔧 Complete User Flow (WITH Mock Mode)

**Payment → Internet Access Flow:**

1. **Customer Buys Bundle:**
   ```
   Customer phone → Production API (Mock Mode ON)
   ↓
   ✅ Payment processed via ClickPesa
   ✅ Database: user.is_active = True
   ✅ Database: user.access_expires = +24h (or bundle duration)
   ✅ SMS sent to customer
   ```

2. **Customer Connects to WiFi:**
   ```
   Customer device → MikroTik Router (Local, Always ON)
   ↓
   Router checks: Production Database API
   ↓
   Database returns: {"has_access": true, "expires": "2025-11-14 15:30"}
   ↓
   ✅ Router creates hotspot user
   ✅ Router grants internet access
   ✅ Customer browses internet
   ```

3. **Bundle Expires (Automatic):**
   ```
   Time reaches expiry → Database updates automatically
   ↓
   Router checks database periodically
   ↓
   Database returns: {"has_access": false, "expired": true}
   ↓
   ✅ Router disconnects user automatically
   ✅ Router removes hotspot user
   ✅ Customer sees login page again
   ```

**🎉 ALL OF THIS WORKS with Mock Mode enabled!**

### 🔄 What Mock Mode Actually Blocks

Mock Mode ONLY blocks these admin operations from production:

```python
# ❌ These API calls fail from PRODUCTION admin dashboard:
GET /api/admin/mikrotik/active-users/      # Can't see who's online remotely
POST /api/admin/mikrotik/disconnect-user/  # Can't kick users remotely
GET /api/admin/mikrotik/router-info/       # Can't see router stats remotely

# ✅ But router LOCALLY still works for users:
Router.check_user_access()    # ✅ Works - checks production DB
Router.grant_internet()       # ✅ Works - gives internet
Router.disconnect_expired()   # ✅ Works - auto-disconnect
```

### 📱 End User Experience (Unchanged)

**With Mock Mode, customers experience:**

1. ✅ Buy bundle via M-Pesa/ClickPesa
2. ✅ Receive SMS confirmation
3. ✅ Connect to WiFi "Kitonga WiFi"
4. ✅ Get internet immediately
5. ✅ Browse for bundle duration
6. ✅ Auto-disconnected when expired

**Everything works normally for customers!** 🎯

### 🔧 Your Management Options

**Option 1: Local Management (Free)**
- Connect to router locally: http://192.168.0.173
- Use MikroTik WinBox from office computer
- Check active users, disconnect manually if needed
- Works great for small operations

**Option 2: Upgrade to VPS ($6/month)**
- Get full remote control from anywhere
- Monitor active users from admin dashboard
- Disconnect users from anywhere
- Professional operation

---

## Upgrading Options (If You Need Router Control from Production)

### Option A: Upgrade to VPS (Recommended)

**Providers with good pricing:**
1. **DigitalOcean** - $6/month (Droplet)
2. **Vultr** - $6/month
3. **Linode** - $5/month
4. **Hetzner** - $4.5/month

**Benefits:**
- ✅ Full root access
- ✅ Install VPN (WireGuard)
- ✅ Connect to your router
- ✅ Full control over environment

**Migration Steps:**
1. Sign up for VPS
2. Install Python + dependencies
3. Deploy your Django app
4. Set up WireGuard VPN
5. Connect to home router
6. Update DNS to point to new VPS IP

### Option B: Hybrid Setup (Budget-Friendly)

**Keep shared hosting for API, use local machine for router control:**

1. **Production (Shared Hosting):**
   - Handles all API requests
   - Payment processing
   - User management
   - Database operations

2. **Local Machine (Your computer):**
   - Always-on mini PC or Raspberry Pi
   - Manages MikroTik router
   - Syncs with production database
   - Handles real-time router operations

3. **Communication:**
   - Production writes to database
   - Local service reads database and updates router
   - Use webhooks for immediate updates

---

## Immediate Deployment Steps for Shared Hosting

### Via cPanel File Manager (Easiest):

1. **Login to cPanel**
   - Go to: https://klikcell.com:2083
   - Username: `thebkihw`
   - Password: [your password]

2. **Navigate to File Manager**
   - Click "File Manager" icon
   - Go to: `api.kitonga.klikcell.com` folder

3. **Upload/Edit Files**
   - Upload updated `billing/mikrotik.py`
   - Upload updated `requirements.txt`
   - Edit `.env` file, add: `MIKROTIK_MOCK_MODE=true`

4. **Restart Application**
   - Go to Terminal (if available)
   - Or create file: `tmp/restart.txt`
   - Or use "Setup Python App" in cPanel to restart

### Via SSH (If Enabled):

```bash
# Connect via SSH
ssh thebkihw@klikcell.com
# Enter your password

# Navigate to project
cd ~/api.kitonga.klikcell.com

# Pull changes (if using git)
git pull origin main

# Edit .env
nano .env
# Add: MIKROTIK_MOCK_MODE=true
# Save: Ctrl+X, Y, Enter

# Update dependencies
pip install --user -r requirements.txt

# Restart app
touch tmp/restart.txt
```

---

## Testing After Deployment

### Test 1: Check API Works
```bash
curl https://api.kitonga.klikcell.com/api/health/
```

**Expected:** 
```json
{"status": "healthy"}
```

### Test 2: Check Router Endpoint (Should Fail Gracefully)
```bash
curl -X GET https://api.kitonga.klikcell.com/api/admin/mikrotik/profiles/ \
  -H "X-Admin-Access: kitonga_admin_2025"
```

**Expected:**
```json
{
  "success": false,
  "message": "MikroTik router not accessible in this environment"
}
```

### Test 3: Check Other Endpoints Still Work
```bash
# Test user authentication
curl -X POST https://api.kitonga.klikcell.com/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}'

# Test bundles
curl https://api.kitonga.klikcell.com/api/bundles/
```

---

## Frontend Updates Needed

Update your frontend to handle router features being unavailable:

```javascript
// In your admin dashboard

async function loadRouterStatus() {
  try {
    const response = await fetch('/api/admin/mikrotik/active-users/', {
      headers: { 'X-Admin-Access': 'kitonga_admin_2025' }
    });
    
    const data = await response.json();
    
    if (!data.success) {
      // Show friendly message
      document.getElementById('router-status').innerHTML = `
        <div class="alert alert-info">
          <i class="icon-info"></i>
          Router monitoring unavailable in shared hosting environment.
          <br>
          <small>Upgrade to VPS for full router management features.</small>
        </div>
      `;
      return;
    }
    
    // Show active users
    displayActiveUsers(data.active_users);
    
  } catch (error) {
    console.error('Router status error:', error);
  }
}
```

---

## Recommended Action Plan

### TODAY (5 minutes):
1. ✅ Add `MIKROTIK_MOCK_MODE=true` to production `.env`
2. ✅ Upload updated code files
3. ✅ Restart application
4. ✅ Test endpoints

### THIS WEEK:
1. ✅ Update frontend to show "Router features unavailable"
2. ✅ Test all payment and voucher flows work
3. ✅ Document current limitations

### THIS MONTH (Budget Permitting):
1. 🤔 Evaluate VPS providers
2. 🤔 Budget for VPS upgrade ($5-6/month)
3. 🤔 Plan migration if needed

---

## Cost Comparison

### Current: Shared Hosting
- **Cost:** ~$5-10/month
- **Router Control:** ❌ No
- **Limitations:** Many
- **Good for:** Basic web apps

### Upgrade: VPS
- **Cost:** ~$6/month (DigitalOcean/Vultr)
- **Router Control:** ✅ Yes (with VPN)
- **Limitations:** Few
- **Good for:** Full-featured apps

**Difference:** Just $1-6/month for full control! 🎯

---

## Files to Upload to Shared Hosting

Via cPanel File Manager, upload these updated files:

1. **billing/mikrotik.py** - Fixed variable scope bugs
2. **requirements.txt** - Updated routeros-api version
3. **.env** - Add MIKROTIK_MOCK_MODE=true

That's it! Your system will work without router features. ✅

---

## Support

**Need help with cPanel?**
- cPanel documentation: https://docs.cpanel.net/
- Contact your hosting support: klikcell.com support

**Need help upgrading to VPS?**
- See: PRODUCTION_MIKROTIK_SETUP_GUIDE.md (VPS section)

---

## Summary

✅ **Shared hosting = Mock Mode only**  
✅ **VPS = Full router control**  
✅ **Your choice based on budget and needs**

For now, enable Mock Mode and your API will work without router features! 🚀

---

## 🎉 Upgrading to VPS

**Congratulations on upgrading to VPS!** You now have full control over your system.

### Quick Migration Steps:

1. **Run the transition script:**
   ```bash
   cd /path/to/your/project
   ./transition_to_vps.sh
   ```

2. **Setup VPS with automated script:**
   ```bash
   ./setup_vps_mikrotik.sh
   ```

3. **Configure VPN connection** (see VPS_MIKROTIK_SETUP_GUIDE.md)

4. **Test everything works:**
   ```bash
   python test_vps_integration.py
   ```

### New Files Available:
- 📖 **VPS_MIKROTIK_SETUP_GUIDE.md** - Complete VPS setup guide
- 🔧 **setup_vps_mikrotik.sh** - Automated VPS configuration
- 🔄 **transition_to_vps.sh** - Quick transition from shared hosting
- 🧪 **test_vps_integration.py** - Verify everything works

### What You Gain with VPS:
✅ **Real-time user monitoring** - See who's online instantly  
✅ **Remote user management** - Disconnect users from anywhere  
✅ **Full router control** - All management features unlocked  
✅ **No mock mode needed** - Direct router communication  
✅ **Better performance** - Faster response times  
✅ **Professional setup** - Complete control over your system  

**Welcome to the full power of Kitonga Wi-Fi System!** 🚀
