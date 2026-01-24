# Voucher Code System

## Overview
The voucher system allows administrators to generate prepaid access codes that users can redeem for Wi-Fi access without requiring online payment. This is ideal for:
- Physical voucher card sales
- Promotional campaigns
- Offline distribution channels
- Corporate bulk purchases

## Voucher Types

### Duration Options
- **24 Hours (1 Day)** - TSh 1,000 equivalent
- **168 Hours (7 Days)** - TSh 7,000 equivalent  
- **720 Hours (30 Days)** - TSh 30,000 equivalent

## Generating Vouchers

### Via API (Admin Only)

**Endpoint:** `POST /api/vouchers/generate/`

**Authentication:** Requires admin authentication

**Request Body:**
\`\`\`json
{
  "quantity": 100,
  "duration_hours": 24,
  "batch_id": "PROMO-2024-JAN",
  "notes": "January promotion batch"
}
\`\`\`

**Response:**
\`\`\`json
{
  "success": true,
  "message": "Successfully generated 100 vouchers",
  "batch_id": "PROMO-2024-JAN",
  "vouchers": [
    {
      "code": "A1B2-C3D4-E5F6",
      "duration_hours": 24,
      "is_used": false,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
\`\`\`

### Via Django Admin

1. Log in to Django admin at `/admin/`
2. Navigate to **Vouchers** section
3. Use the admin interface to view and manage vouchers
4. Export vouchers to CSV for printing

## Redeeming Vouchers

### Via API (Public)

**Endpoint:** `POST /api/vouchers/redeem/`

**Request Body:**
\`\`\`json
{
  "voucher_code": "A1B2-C3D4-E5F6",
  "phone_number": "255712345678"
}
\`\`\`

**Response (Success):**
\`\`\`json
{
  "success": true,
  "message": "Voucher redeemed successfully. Access granted for 24 hours.",
  "user": {
    "phone_number": "255712345678",
    "paid_until": "2024-01-16T10:30:00Z",
    "is_active": true
  }
}
\`\`\`

**Response (Error):**
\`\`\`json
{
  "success": false,
  "message": "Voucher has already been used"
}
\`\`\`

### Via Captive Portal

1. User enters phone number on welcome screen
2. On payment screen, user sees "Have a Voucher Code?" section
3. User enters voucher code (format: XXXX-XXXX-XXXX)
4. System validates and redeems voucher
5. User gets immediate Wi-Fi access

## Voucher Code Format

- **Format:** `XXXX-XXXX-XXXX` (12 alphanumeric characters with dashes)
- **Example:** `A1B2-C3D4-E5F6`
- **Case-insensitive:** Users can enter codes in any case
- **Dash-flexible:** Codes work with or without dashes

## Admin Management

### Listing Vouchers

**Endpoint:** `GET /api/vouchers/list/`

**Query Parameters:**
- `is_used` - Filter by usage status (true/false)
- `batch_id` - Filter by batch ID
- `duration_hours` - Filter by duration (24, 168, 720)

**Example:**
\`\`\`bash
GET /api/vouchers/list/?is_used=false&batch_id=PROMO-2024-JAN
\`\`\`

### Exporting Vouchers

1. Go to Django admin vouchers page
2. Select vouchers to export
3. Choose "Export selected vouchers to CSV" action
4. Download CSV file for printing

### CSV Format
\`\`\`csv
Code,Duration (Hours),Status,Batch ID,Created At,Used At,Used By
A1B2-C3D4-E5F6,24,Available,PROMO-2024-JAN,2024-01-15 10:30,-,-
B2C3-D4E5-F6G7,24,Used,PROMO-2024-JAN,2024-01-15 10:30,2024-01-15 14:20,255712345678
\`\`\`

## Batch Management

### Creating Batches
Batches help organize vouchers by:
- Campaign name
- Distribution channel
- Time period
- Customer segment

**Example Batch IDs:**
- `PROMO-2024-JAN` - January promotion
- `RETAIL-STORE-A` - Specific retail location
- `CORPORATE-XYZ` - Corporate client
- `EVENT-CONFERENCE` - Event-specific codes

### Tracking Batches
- View all vouchers in a batch
- Check redemption rates
- Export batch reports
- Analyze usage patterns

## Security Features

1. **Unique Codes** - Each voucher code is cryptographically unique
2. **One-time Use** - Vouchers can only be redeemed once
3. **Audit Trail** - Track who created and redeemed each voucher
4. **Batch Tracking** - Organize and monitor voucher distribution

## Best Practices

### For Administrators
1. Use descriptive batch IDs for easy tracking
2. Add notes to batches for context
3. Export vouchers immediately after generation
4. Store voucher lists securely
5. Monitor redemption rates regularly

### For Distribution
1. Print vouchers on secure paper
2. Include clear redemption instructions
3. Display expiry information if applicable
4. Provide customer support contact
5. Track distribution channels

### For Printing
1. Use the CSV export feature
2. Include QR codes for easy scanning (optional)
3. Add branding and instructions
4. Use tamper-evident materials
5. Number vouchers for inventory control

## Troubleshooting

### Voucher Not Working
- Check if voucher has already been used
- Verify code is entered correctly (case-insensitive)
- Ensure voucher exists in system
- Check for typos in phone number

### Bulk Generation Issues
- Maximum 1000 vouchers per request
- Ensure admin authentication
- Check server resources for large batches
- Use batch IDs to organize large generations

## API Examples

### Generate 50 Daily Vouchers
\`\`\`bash
curl -X POST https://yourdomain.com/api/vouchers/generate/ \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "quantity": 50,
    "duration_hours": 24,
    "batch_id": "DAILY-BATCH-001",
    "notes": "Daily vouchers for retail"
  }'
\`\`\`

### Redeem Voucher
\`\`\`bash
curl -X POST https://yourdomain.com/api/vouchers/redeem/ \
  -H "Content-Type: application/json" \
  -d '{
    "voucher_code": "A1B2-C3D4-E5F6",
    "phone_number": "255712345678"
  }'
\`\`\`

### List Unused Vouchers
\`\`\`bash
curl -X GET "https://yourdomain.com/api/vouchers/list/?is_used=false" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
