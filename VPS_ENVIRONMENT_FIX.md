# Quick Fix Commands for VPS Environment Issue

## 🚨 **Issue**: sed command failed due to special characters in SECRET_KEY

The error occurred because your Django SECRET_KEY contains special characters (`=`, `+`, `$`, etc.) that broke the sed command in the setup script.

## ✅ **Quick Fix Solution**

Run these commands on your VPS to fix the environment configuration:

### 1. **Upload the fix script to your VPS:**
```bash
# From your local machine:
scp fix_vps_env.sh root@66.29.143.116:/var/www/kitonga/
```

### 2. **Run the fix script on your VPS:**
```bash
# On your VPS:
ssh root@66.29.143.116
cd /var/www/kitonga
chmod +x fix_vps_env.sh
./fix_vps_env.sh
```

### 3. **Alternative Manual Fix (if needed):**
If you prefer to fix manually, run these commands on your VPS:

```bash
cd /var/www/kitonga

# Backup your .env file
cp .env .env.backup

# Manually set the critical settings
python3 -c "
import re

# Read .env file
with open('.env', 'r') as f:
    content = f.read()

# Fix MIKROTIK_MOCK_MODE
content = re.sub(r'^MIKROTIK_MOCK_MODE=.*$', 'MIKROTIK_MOCK_MODE=false', content, flags=re.MULTILINE)

# Update MIKROTIK_HOST
content = re.sub(r'^MIKROTIK_HOST=.*$', 'MIKROTIK_HOST=192.168.0.173', content, flags=re.MULTILINE)

# Write back
with open('.env', 'w') as f:
    f.write(content)

print('Environment fixed successfully!')
"
```

## 🧪 **Test the Fix**

After running the fix, test that everything works:

```bash
# Test router connection
nc -zv 192.168.0.173 8728

# Test Django settings
python3 manage.py shell -c "
from django.conf import settings
print('MIKROTIK_MOCK_MODE:', getattr(settings, 'MIKROTIK_MOCK_MODE', 'Not set'))
print('MIKROTIK_HOST:', getattr(settings, 'MIKROTIK_HOST', 'Not set'))
"

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Test API endpoint
curl -X GET https://api.kitonga.klikcell.com/api/admin/mikrotik/router-info/ \
     -H "X-Admin-Access: kitonga_admin_2025"
```

## 🎯 **What the Fix Does**

1. **Handles Special Characters**: Uses Python instead of sed to safely update environment variables
2. **Sets Router Control**: Ensures `MIKROTIK_MOCK_MODE=false` for full router control
3. **Configures Domains**: Sets proper CORS and CSRF settings for your domains
4. **Tests Connectivity**: Verifies router connection and Django settings

## 📝 **Expected Results**

After the fix, you should see:
- ✅ Router connection successful
- ✅ MIKROTIK_MOCK_MODE=false (no more mock mode!)
- ✅ Django settings loaded correctly
- ✅ API endpoints responding

This will resolve the connection issues you experienced with shared hosting!
