# MikroTik Hotspot HTML Files - Setup Guide

These HTML files should be uploaded to your MikroTik router to enable the Kitonga Wi-Fi captive portal integration.

## Files Overview

| File                   | Purpose                                       |
| ---------------------- | --------------------------------------------- |
| `mikrotik_login.html`  | Main login page - redirects to Kitonga portal |
| `mikrotik_alogin.html` | Success page after login                      |
| `mikrotik_status.html` | Session status page                           |
| `mikrotik_logout.html` | Logout confirmation page                      |
| `mikrotik_error.html`  | Error page                                    |

## Step 1: Configure Router ID

**IMPORTANT:** Before uploading, edit `mikrotik_login.html` and change the `ROUTER_ID` value:

```javascript
// Line 97 in mikrotik_login.html
var ROUTER_ID = 6 // <-- CHANGE THIS TO YOUR ROUTER ID FROM KITONGA ADMIN
```

Find your Router ID in Kitonga admin: `https://kitonga.klikcell.com/admin/` → Billing → Routers

## Step 2: Upload Files via WinBox

1. Open **WinBox** and connect to your router
2. Click **Files** in the left menu
3. Navigate to the `hotspot` folder (or create it if it doesn't exist)
4. Drag and drop the files, renaming them:

   | Upload This File       | Rename To     |
   | ---------------------- | ------------- |
   | `mikrotik_login.html`  | `login.html`  |
   | `mikrotik_alogin.html` | `alogin.html` |
   | `mikrotik_status.html` | `status.html` |
   | `mikrotik_logout.html` | `logout.html` |
   | `mikrotik_error.html`  | `error.html`  |

## Step 3: Upload Files via FTP (Alternative)

```bash
# Connect via FTP
ftp YOUR_ROUTER_IP

# Login with admin credentials
# Username: admin
# Password: your_password

# Navigate to hotspot directory
cd hotspot

# Upload files (rename during upload)
put mikrotik_login.html login.html
put mikrotik_alogin.html alogin.html
put mikrotik_status.html status.html
put mikrotik_logout.html logout.html
put mikrotik_error.html error.html

quit
```

## Step 4: Upload via SCP (Alternative)

```bash
# Upload all files at once
scp mikrotik_login.html admin@YOUR_ROUTER_IP:/hotspot/login.html
scp mikrotik_alogin.html admin@YOUR_ROUTER_IP:/hotspot/alogin.html
scp mikrotik_status.html admin@YOUR_ROUTER_IP:/hotspot/status.html
scp mikrotik_logout.html admin@YOUR_ROUTER_IP:/hotspot/logout.html
scp mikrotik_error.html admin@YOUR_ROUTER_IP:/hotspot/error.html
```

## Step 5: Configure Hotspot Profile

Run these commands in MikroTik terminal:

```
# Set HTML directory to use our custom files
/ip hotspot profile set kitonga-profile html-directory=hotspot

# Add Kitonga domains to walled garden (allow access before login)
/ip hotspot walled-garden
add dst-host=api.kitonga.klikcell.com
add dst-host=kitonga.klikcell.com
add dst-host=*.klikcell.com

# Verify walled garden rules
/ip hotspot walled-garden print
```

## Step 6: Test the Setup

1. Connect a device to your WiFi hotspot
2. Open a browser - you should see the Kitonga login page
3. Open browser Developer Tools (F12) → Console
4. Check for: `Router ID: 6` (your router ID)

## Troubleshooting

### Page shows "Redirecting..." but doesn't redirect

1. Check walled garden rules allow `api.kitonga.klikcell.com`
2. Verify HTTPS is working (may need to add SSL certificate exception)

### MikroTik variables not replaced (shows `$(mac)` literally)

- Ensure files are in the correct `hotspot` folder
- Verify hotspot profile uses `html-directory=hotspot`

### Debug Mode

Triple-tap on the login page to show debug information including:

- Router ID
- Detected MAC address
- Detected IP address
- Full redirect URL

## File Locations on Router

After upload, your router's file structure should look like:

```
/
├── hotspot/
│   ├── login.html      (redirects to Kitonga)
│   ├── alogin.html     (login success)
│   ├── status.html     (session status)
│   ├── logout.html     (logout page)
│   └── error.html      (error page)
```

## Multiple Routers

For each router, you need to:

1. Get the Router ID from Kitonga admin
2. Edit `mikrotik_login.html` with the correct `ROUTER_ID`
3. Upload to that specific router

Each router must have its own unique Router ID configured!
