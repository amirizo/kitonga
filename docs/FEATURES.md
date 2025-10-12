# Kitonga Wi-Fi Billing System - Features Documentation

## Overview

Kitonga is a comprehensive Wi-Fi billing system designed for hotspot operators in Tanzania. It provides mobile money payment integration, voucher management, SMS notifications, and multi-device support.

---

## Core Features

### 1. Mobile Money Payment Integration (ClickPesa)

**Description:** Seamless mobile money payments via USSD-PUSH requests.

**Supported Networks:**
- Vodacom M-Pesa
- Tigo Pesa
- Airtel Money
- Halopesa

**Payment Flow:**
1. User selects a bundle package
2. System initiates USSD-PUSH request via ClickPesa
3. User receives mobile money prompt on their phone
4. User enters PIN to complete payment
5. System receives webhook notification
6. Access is automatically activated
7. SMS confirmation sent to user

**API Endpoints:**
- `POST /api/initiate-payment/` - Initiate payment
- `POST /api/clickpesa-webhook/` - Receive payment notifications
- `GET /api/payment-status/{order_reference}/` - Query payment status

---

### 2. Bundle Packages

**Description:** Flexible pricing packages for different access durations.

**Default Bundles:**
- **Daily Package:** TSh 1,000 for 24 hours
- **Weekly Package:** TSh 6,000 for 7 days (Save TSh 1,000)
- **Monthly Package:** TSh 25,000 for 30 days (Save TSh 5,000)

**Features:**
- Customizable bundle names, prices, and durations
- Bundle descriptions for marketing
- Display order control
- Active/inactive status toggle
- Automatic savings calculation

**Admin Management:**
- Create/edit bundles via Django admin
- Set custom pricing and durations
- Reorder bundles for display priority

**API Endpoints:**
- `GET /api/bundles/` - List all active bundles

---

### 3. Voucher Code System

**Description:** Offline access codes for distribution without online payment.

**Use Cases:**
- Bulk sales to resellers
- Corporate packages
- Promotional campaigns
- Gift cards
- Offline sales points

**Voucher Format:** `XXXX-XXXX-XXXX` (12 characters with dashes)

**Features:**
- Batch generation with unique IDs
- Multiple duration options (1 day, 7 days, 30 days)
- Usage tracking (used/unused status)
- User redemption history
- CSV export for distribution
- Batch notes for organization

**Admin Operations:**
- Generate vouchers in bulk
- Export vouchers to CSV
- Filter by status, batch, duration
- View redemption history
- Mark as used/unused (for testing)

**API Endpoints:**
- `POST /api/vouchers/generate/` - Generate vouchers (Admin only)
- `POST /api/vouchers/redeem/` - Redeem voucher code
- `GET /api/vouchers/` - List vouchers (Admin only)

**Example Generation Request:**
\`\`\`json
{
  "quantity": 100,
  "duration_hours": 168,
  "batch_id": "PROMO-2024-JAN",
  "notes": "January promotion batch"
}
\`\`\`

---

### 4. SMS Notifications (NEXTSMS)

**Description:** Automated SMS notifications for user engagement and retention.

**Notification Types:**

#### Payment Confirmation
Sent immediately after successful payment.
\`\`\`
Payment confirmed! TSh 1000 received. Your Kitonga Wi-Fi access is now active for 1 day. Thank you!
\`\`\`

#### Expiry Warning
Sent 2 hours before access expires (configurable).
\`\`\`
Kitonga Wi-Fi: Your access will expire in 2 hours. Renew now to stay connected. Reply RENEW or visit the portal.
\`\`\`

#### Access Expired
Sent when access expires.
\`\`\`
Kitonga Wi-Fi: Your access has expired. Purchase a new package to continue enjoying our service. Visit the portal or dial *150*00#
\`\`\`

#### Voucher Redemption
Sent after successful voucher redemption.
\`\`\`
Voucher ABCD-1234-EFGH redeemed successfully! Your Kitonga Wi-Fi access is now active for 7 days. Enjoy!
\`\`\`

**Configuration:**
- Sender ID: Customizable (default: KITONGA)
- Base URL: https://messaging-service.co.tz
- Authentication: Basic Auth (Base64 encoded)
- Test mode available for development

**SMS Logging:**
- All SMS tracked in database
- Success/failure status
- Response data from provider
- SMS type categorization
- Timestamp tracking

**Management Command:**
\`\`\`bash
# Send expiry notifications (run hourly via cron)
python manage.py send_expiry_notifications --hours 2

# Check and deactivate expired users (run every 5 minutes)
python manage.py check_expired_users
\`\`\`

---

### 5. Multi-Device Support

**Description:** Allow users to connect multiple devices simultaneously with configurable limits.

**Features:**
- Default limit: 3 devices per user (configurable)
- Automatic device detection via MAC address
- Device tracking (IP, MAC, last seen)
- Active/inactive status
- Device removal capability
- Real-time device status

**Device Management:**
- View all connected devices
- See active device count
- Remove inactive devices
- Device type detection (phone, tablet, computer)
- Last seen timestamp
- Live connection indicator

**Access Control:**
- Automatic device limit enforcement
- Denial reason logging
- Device-based access logs
- MAC address whitelisting

**API Endpoints:**
- `GET /api/devices/{phone_number}/` - List user devices
- `POST /api/devices/remove/` - Remove device

---

### 6. Admin Dashboard

**Description:** Comprehensive analytics and management interface.

**Statistics:**
- Active users count
- Revenue (today, 7 days, 30 days)
- Total payments breakdown
- Payment status distribution
- Voucher statistics (total, used, available)
- Device statistics (total, active, inactive)

**Recent Activity:**
- Last 10 payments
- Last 10 registered users
- Payment status breakdown

**Management Features:**
- User management (view, edit, deactivate)
- Payment history and status
- Access logs and denial reasons
- Voucher generation and tracking
- Bundle configuration
- SMS log viewing

**Access:**
- URL: `/admin/dashboard/`
- Requires staff/admin authentication
- Real-time statistics
- Export capabilities

---

## Technical Specifications

### Database Models

**User Model:**
- Phone number (unique identifier)
- Access status and expiry
- Total payments count
- Device limit
- Notification status

**Payment Model:**
- User reference
- Bundle reference
- Amount and currency
- Transaction IDs
- Payment channel
- Status tracking
- Timestamps

**Device Model:**
- User reference
- MAC and IP addresses
- Device name
- Active status
- First seen / last seen

**Voucher Model:**
- Unique code
- Duration hours
- Usage status
- Batch tracking
- Redemption history

**Bundle Model:**
- Name and description
- Duration and pricing
- Active status
- Display order

**AccessLog Model:**
- User and device references
- Access granted/denied
- Denial reasons
- Timestamps

**SMSLog Model:**
- Phone number
- Message content
- SMS type
- Success status
- Response data

---

## Environment Variables

\`\`\`bash
# Django Settings
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# ClickPesa Configuration
CLICKPESA_CLIENT_ID=your-client-id
CLICKPESA_API_KEY=your-api-key
CLICKPESA_BASE_URL=https://api.clickpesa.com
CLICKPESA_WEBHOOK_URL=https://yourdomain.com/api/clickpesa-webhook/

# NEXTSMS Configuration
NEXTSMS_USERNAME=your-username
NEXTSMS_PASSWORD=your-password
NEXTSMS_SENDER_ID=KITONGA
NEXTSMS_BASE_URL=https://messaging-service.co.tz

# System Configuration
MAX_DEVICES_PER_USER=3
CORS_ALLOWED_ORIGINS=https://yourdomain.com

# Frontend Configuration
NEXT_PUBLIC_API_URL=https://yourdomain.com
\`\`\`

---

## Cron Jobs

Set up these cron jobs for automated operations:

\`\`\`bash
# Check and deactivate expired users (every 5 minutes)
*/5 * * * * cd /path/to/kitonga && python manage.py check_expired_users

# Send expiry notifications (every hour)
0 * * * * cd /path/to/kitonga && python manage.py send_expiry_notifications --hours 2
\`\`\`

---

## API Reference

### Public Endpoints

**Verify Access**
\`\`\`
POST /api/verify-access/
Body: {
  "phone_number": "255712345678",
  "ip_address": "192.168.1.100",
  "mac_address": "AA:BB:CC:DD:EE:FF"
}
\`\`\`

**Initiate Payment**
\`\`\`
POST /api/initiate-payment/
Body: {
  "phone_number": "255712345678",
  "bundle_id": 1
}
\`\`\`

**Redeem Voucher**
\`\`\`
POST /api/vouchers/redeem/
Body: {
  "voucher_code": "ABCD-1234-EFGH",
  "phone_number": "255712345678"
}
\`\`\`

**Get User Status**
\`\`\`
GET /api/user-status/{phone_number}/
\`\`\`

**List Bundles**
\`\`\`
GET /api/bundles/
\`\`\`

**List User Devices**
\`\`\`
GET /api/devices/{phone_number}/
\`\`\`

**Remove Device**
\`\`\`
POST /api/devices/remove/
Body: {
  "phone_number": "255712345678",
  "device_id": 1
}
\`\`\`

### Admin Endpoints

**Generate Vouchers**
\`\`\`
POST /api/vouchers/generate/
Headers: Authorization: Token <admin-token>
Body: {
  "quantity": 100,
  "duration_hours": 168,
  "batch_id": "BATCH-001",
  "notes": "Promotional batch"
}
\`\`\`

**List Vouchers**
\`\`\`
GET /api/vouchers/?is_used=false&batch_id=BATCH-001
Headers: Authorization: Token <admin-token>
\`\`\`

---

## Security Features

- CSRF protection on all POST endpoints
- Phone number validation
- MAC address tracking
- Device limit enforcement
- Payment verification via webhooks
- Secure token generation
- Access log auditing
- Admin-only endpoints
- Environment variable configuration

---

## Support & Maintenance

**Monitoring:**
- Health check endpoint: `/api/health/`
- Access logs for troubleshooting
- Payment status tracking
- SMS delivery logs

**Backup:**
- Regular database backups
- Voucher code exports
- Payment history exports
- User data exports

**Updates:**
- Bundle price adjustments
- Device limit configuration
- SMS template customization
- Notification timing adjustments
\`\`\`

I've added a comprehensive device management UI to the active session screen and created detailed feature documentation. The system now displays all connected devices with real-time status indicators, allows users to remove devices, and shows device limits. The documentation covers all features including payment integration, bundles, vouchers, SMS notifications, multi-device support, and the admin dashboard.
