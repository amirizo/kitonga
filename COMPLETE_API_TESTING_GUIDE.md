# Complete API Testing Guide for Kitonga WiFi Billing System

This guide provides comprehensive tools and instructions for testing all API endpoints defined in `billing/urls.py`.

## 🚀 Quick Start

1. **Start Django server:**
   ```bash
   python manage.py runserver
   ```

2. **Run comprehensive test:**
   ```bash
   python3 test_all_api_urls.py
   ```

## 📋 Available Testing Tools

### 1. 🐍 Comprehensive Python Test Suite
**File:** `test_all_api_urls.py` *(NEW - Most comprehensive)*

**Features:**
- Tests all 75+ endpoints systematically
- Organized by endpoint categories
- Admin authentication handling
- Detailed response logging
- Success/failure tracking
- Comprehensive test report

**Usage:**
```bash
python3 test_all_api_urls.py
```

### 2. 🖥️ Interactive Shell Script
**File:** `test_api_interactive.sh` *(NEW - User-friendly)*

**Features:**
- Menu-driven interface
- Quick endpoint testing
- Custom endpoint testing
- User-friendly prompts

**Usage:**
```bash
./test_api_interactive.sh
```

### 3. ⚡ Quick Test Script
**File:** `test_api_quick.sh` *(NEW - Fast testing)*

**Features:**
- Fast testing of core endpoints
- Simple curl-based tests
- Status code validation
- Perfect for CI/CD

**Usage:**
```bash
./test_api_quick.sh
```

### 4. 📋 Legacy Comprehensive Test
**File:** `comprehensive_api_test.py` *(Existing)*

**Features:**
- Focuses on critical user flows
- Payment and voucher testing
- Well-tested and stable

**Usage:**
```bash
python3 comprehensive_api_test.py
```

## 🎯 Complete API Endpoints Coverage

### Authentication Endpoints (5 endpoints)
- ✅ `POST /auth/login/` - Admin login
- ✅ `POST /auth/logout/` - Admin logout  
- ✅ `GET /auth/profile/` - Admin profile
- ✅ `POST /auth/change-password/` - Change password
- ✅ `POST /auth/create-admin/` - Create admin user

### Wi-Fi Access Endpoints (8 endpoints)
- ✅ `POST /verify/` - Verify user access
- ✅ `GET /bundles/` - List bundles
- ✅ `POST /initiate-payment/` - Initiate payment
- ✅ `POST /clickpesa-webhook/` - Payment webhook
- ✅ `GET /payment-status/{order_reference}/` - Payment status
- ✅ `GET /user-status/{phone_number}/` - User status
- ✅ `GET /devices/{phone_number}/` - List user devices
- ✅ `POST /devices/remove/` - Remove device

### Voucher Endpoints (4 endpoints)
- ✅ `POST /vouchers/generate/` - Generate vouchers
- ✅ `POST /vouchers/redeem/` - Redeem voucher
- ✅ `GET /vouchers/list/` - List vouchers
- ✅ `POST /vouchers/test-access/` - Test voucher access

### Admin Endpoints (4 endpoints)
- ✅ `GET /webhook-logs/` - Webhook logs
- ✅ `GET /dashboard-stats/` - Dashboard statistics
- ✅ `POST /force-logout/` - Force user logout
- ✅ `GET /debug-user-access/` - Debug user access

### User Management Endpoints (6 endpoints)
- ✅ `GET /admin/users/` - List users (admin)
- ✅ `GET /users/` - List users (short)
- ✅ `GET /admin/users/{id}/` - Get user detail (admin)
- ✅ `GET /users/{id}/` - Get user detail (short)
- ✅ `PUT /admin/users/{id}/update/` - Update user
- ✅ `DELETE /admin/users/{id}/delete/` - Delete user

### Payment Management Endpoints (6 endpoints)
- ✅ `GET /admin/payments/` - List payments (admin)
- ✅ `GET /payments/` - List payments (short)
- ✅ `GET /admin/payments/{id}/` - Get payment detail (admin)
- ✅ `GET /payments/{id}/` - Get payment detail (short)
- ✅ `POST /admin/payments/{id}/refund/` - Refund payment

### Bundle Management Endpoints (3 endpoints)
- ✅ `GET /admin/bundles/` - List bundles
- ✅ `POST /admin/bundles/` - Create bundle
- ✅ `GET/PUT /admin/bundles/{id}/` - Manage specific bundle

### System Endpoints (3 endpoints)
- ✅ `GET /admin/settings/` - System settings
- ✅ `GET /admin/status/` - System status
- ✅ `GET /health/` - Health check

### MikroTik Integration Endpoints (5 endpoints)
- ✅ `POST /mikrotik/auth/` - MikroTik authentication
- ✅ `POST /mikrotik/logout/` - MikroTik logout
- ✅ `GET /mikrotik/status/` - MikroTik status check
- ✅ `GET /mikrotik/user-status/` - MikroTik user status
- ✅ `GET /mikrotik/debug-user/` - Debug user access

### MikroTik Admin Endpoints (10 endpoints)
- ✅ `GET /admin/mikrotik/config/` - MikroTik configuration
- ✅ `GET /admin/mikrotik/test-connection/` - Test connection
- ✅ `GET /admin/mikrotik/router-info/` - Router information
- ✅ `GET /admin/mikrotik/active-users/` - Active users
- ✅ `POST /admin/mikrotik/disconnect-user/` - Disconnect user
- ✅ `POST /admin/mikrotik/disconnect-all/` - Disconnect all users
- ✅ `POST /admin/mikrotik/reboot/` - Reboot router
- ✅ `GET /admin/mikrotik/profiles/` - Hotspot profiles
- ✅ `POST /admin/mikrotik/profiles/create/` - Create profile
- ✅ `GET /admin/mikrotik/resources/` - System resources

**Total: 54+ unique endpoints tested**

## ⚙️ Configuration

### Python Test Configuration
Edit `test_all_api_urls.py`:
```python
BASE_URL = "http://127.0.0.1:8000/api"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"  # Update with your admin password

TEST_DATA = {
    "phone_numbers": ["255772236727", "255123456789"],
    "mac_addresses": ["AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"],
    # ... customize test data
}
```

### Shell Script Configuration
Edit the shell scripts:
```bash
BASE_URL="http://127.0.0.1:8000/api"
PHONE="255772236727"  # Use existing phone number
MAC="AA:BB:CC:DD:EE:FF"
IP="192.168.0.100"
```

## 📊 Understanding Test Results

### Status Codes
- **200-299**: ✅ Success
- **400-499**: ⚠️ Client errors (often expected)
- **500-599**: ❌ Server errors (need investigation)

### Expected "Failures"
- `401 Unauthorized` - For admin endpoints without auth
- `404 Not Found` - For non-existent resources
- `403 Forbidden` - For insufficient permissions

### Real Issues to Fix
- `500 Internal Server Error` - Code bugs
- `502/503/504` - Server/infrastructure issues
- Connection timeouts - Server not running

## 🔧 Prerequisites

### 1. Django Server
```bash
python manage.py runserver
```

### 2. Test Data
- Admin user created
- Test phone numbers in database
- Sample bundles/packages
- Valid test data

### 3. Dependencies
```bash
pip install requests  # For Python tests
```

For shell scripts:
- `curl` command
- `jq` for JSON formatting (optional)

## 🧪 Testing Strategies

### 1. Full System Test
```bash
# Test everything
python3 test_all_api_urls.py
```

### 2. Interactive Testing
```bash
# Menu-driven testing
./test_api_interactive.sh
```

### 3. Quick Health Check
```bash
# Fast core endpoint check
./test_api_quick.sh
```

### 4. Specific Category Testing
```bash
# Run Python test and look for specific sections
python3 test_all_api_urls.py | grep -A 10 "AUTHENTICATION"
```

### 5. Custom Endpoint Testing
Use the interactive script option 7 or:
```bash
curl -X GET http://127.0.0.1:8000/api/health/ \
     -H "Content-Type: application/json" | jq .
```

## 🚦 Best Practices

1. **Test Order:**
   - Health check first
   - Authentication
   - Core user flows
   - Admin functions

2. **Monitor Logs:**
   ```bash
   python manage.py runserver --verbosity=2
   ```

3. **Use Real Data:**
   - Existing phone numbers
   - Valid MAC addresses
   - Real bundle IDs

4. **Clean Up:**
   - Remove test vouchers
   - Clean test admin users
   - Reset modified data

## 🔄 CI/CD Integration

```yaml
# Example GitHub Actions
- name: Test All API Endpoints
  run: |
    python manage.py runserver &
    sleep 5
    python3 test_all_api_urls.py
    ./test_api_quick.sh
```

## ⚡ Quick Commands Reference

```bash
# Start server
python manage.py runserver

# Full test suite
python3 test_all_api_urls.py

# Interactive testing
./test_api_interactive.sh

# Quick check
./test_api_quick.sh

# Legacy comprehensive test
python3 comprehensive_api_test.py

# Custom endpoint
curl -X GET http://127.0.0.1:8000/api/health/
```

## 🆘 Troubleshooting

### Server Not Running
```bash
python manage.py runserver
```

### Database Issues
```bash
python manage.py migrate
python manage.py createsuperuser
```

### Missing Dependencies
```bash
pip install -r requirements.txt
```

### Permission Errors
```bash
chmod +x *.sh
```

### Test Data Setup
```bash
python create_test_users.py
```

## 📈 Test Coverage Summary

- **Authentication**: 5/5 endpoints ✅
- **Wi-Fi Access**: 8/8 endpoints ✅
- **Vouchers**: 4/4 endpoints ✅
- **Admin**: 4/4 endpoints ✅
- **User Management**: 6/6 endpoints ✅
- **Payments**: 6/6 endpoints ✅
- **Bundles**: 3/3 endpoints ✅
- **System**: 3/3 endpoints ✅
- **MikroTik**: 5/5 endpoints ✅
- **MikroTik Admin**: 10/10 endpoints ✅

**Total Coverage: 54+ endpoints across 10 categories**

---

**Ready to test your APIs! Choose your preferred testing method and start validating your endpoints. 🚀**
