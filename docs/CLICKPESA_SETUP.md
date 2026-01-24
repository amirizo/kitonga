# ClickPesa Integration Setup

## Overview
Kitonga uses ClickPesa for mobile money payments in Tanzania. ClickPesa supports:
- M-PESA (Vodacom)
- TIGO-PESA (Tigo)
- AIRTEL-MONEY (Airtel)
- HALOPESA (Halotel)

## Prerequisites

### 1. Create ClickPesa Account
1. Visit [ClickPesa Dashboard](https://dashboard.clickpesa.com)
2. Sign up for a business account
3. Complete KYC verification

### 2. Create Application
1. Log in to ClickPesa Dashboard
2. Navigate to Applications
3. Create a new application
4. Note down your **Client ID** and **API Key**

### 3. Configure Webhook
1. In your application settings, set the webhook URL
2. Use: `https://yourdomain.com/api/clickpesa-webhook/`
3. ClickPesa will send payment notifications to this URL

## Environment Variables

Add these to your `.env` file or environment configuration:

\`\`\`bash
# ClickPesa Configuration
CLICKPESA_CLIENT_ID=your_client_id_here
CLICKPESA_API_KEY=your_api_key_here
CLICKPESA_BASE_URL=https://api.clickpesa.com
CLICKPESA_WEBHOOK_URL=https://yourdomain.com/api/clickpesa-webhook/
\`\`\`

## Testing

### Test Mode
ClickPesa provides a sandbox environment for testing:

\`\`\`bash
CLICKPESA_BASE_URL=https://api.clickpesa.com/sandbox
\`\`\`

### Test Phone Numbers
Use these test numbers in sandbox mode:
- M-PESA: 255123456789
- TIGO-PESA: 255123456790
- AIRTEL-MONEY: 255123456791

## Payment Flow

1. **User initiates payment** → Frontend calls `/api/initiate-payment/`
2. **Backend creates payment record** → Generates unique order reference
3. **ClickPesa sends USSD-PUSH** → User receives payment prompt on phone
4. **User enters PIN** → Completes payment on mobile device
5. **ClickPesa sends webhook** → Backend receives payment confirmation
6. **Access granted** → User gets 24-hour Wi-Fi access

## Webhook Events

ClickPesa sends two types of webhook events:

### PAYMENT RECEIVED
\`\`\`json
{
  "event": "PAYMENT RECEIVED",
  "payment": {
    "id": "transaction_id",
    "orderReference": "KITONGA123ABC12345",
    "status": "COMPLETED",
    "amount": "1000",
    "currency": "TZS",
    "channel": "M-PESA",
    "phoneNumber": "255712345678"
  }
}
\`\`\`

### PAYMENT FAILED
\`\`\`json
{
  "event": "PAYMENT FAILED",
  "payment": {
    "id": "transaction_id",
    "orderReference": "KITONGA123ABC12345",
    "status": "FAILED",
    "amount": "1000",
    "currency": "TZS"
  }
}
\`\`\`

## API Endpoints

### Initiate Payment
\`\`\`bash
POST /api/initiate-payment/
Content-Type: application/json

{
  "phone_number": "255712345678"
}
\`\`\`

### Query Payment Status
\`\`\`bash
GET /api/payment-status/KITONGA123ABC12345/
\`\`\`

### Webhook Endpoint
\`\`\`bash
POST /api/clickpesa-webhook/
Content-Type: application/json

# ClickPesa sends payment notifications here
\`\`\`

## Security

1. **Validate webhook signatures** - Verify requests are from ClickPesa
2. **Use HTTPS** - All API calls must use HTTPS
3. **Secure credentials** - Never commit API keys to version control
4. **Rate limiting** - Implement rate limiting on payment endpoints

## Troubleshooting

### Payment not completing
1. Check webhook URL is publicly accessible
2. Verify webhook is configured in ClickPesa dashboard
3. Check server logs for webhook errors
4. Query payment status using order reference

### Token expiration
- Tokens expire after 1 hour
- The API client automatically refreshes tokens
- Check `CLICKPESA_CLIENT_ID` and `CLICKPESA_API_KEY` are correct

### Phone number format
- Must start with 255 (Tanzania country code)
- Example: 255712345678
- The API automatically formats numbers

## Support

- ClickPesa Documentation: https://docs.clickpesa.com

## Webhook Events Reference

### PAYMENT RECEIVED
When a payment is successful, ClickPesa sends:
```json
{
  "event": "PAYMENT RECEIVED",
  "data": {
    "paymentId": "PAY123456",
    "orderReference": "KITONGA123ABC12345",
    "collectedAmount": "10000.00",
    "collectedCurrency": "TZS",
    "status": "SUCCESS",
    "customer": {
      "name": "John Doe",
      "email": "john@example.com",
      "phone": "255700000000"
    },
    "createdAt": "2024-04-10T18:22:16.949Z",
    "updatedAt": "2024-04-10T18:22:56.153Z",
    "clientId": "ID1234XHYAJK"
  }
}
```

### PAYMENT FAILED
When a payment fails, ClickPesa sends:
```json
{
  "eventType": "PAYMENT FAILED",
  "data": {
    "id": "0969231256LCP2C95",
    "status": "FAILED",
    "orderReference": "KITONGA123ABC12345",
    "message": "Insufficient balance",
    "updatedAt": "2024-04-11T04:58:31.036Z",
    "createdAt": "2024-04-11T04:58:31.036Z",
    "clientId": "ID1234XHYAJK"
  }
}
```

## Testing Webhooks

### Test Webhook Endpoint (Admin only)
```bash
POST /api/test-webhook/
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "order_reference": "KITONGA123ABC12345",
  "event_type": "PAYMENT RECEIVED",
  "status": "SUCCESS"
}
```

### View Webhook Logs (Admin only)
```bash
GET /api/webhook-logs/
Authorization: Bearer <admin_token>

# Optional filters:
GET /api/webhook-logs/?processing_status=failed
GET /api/webhook-logs/?event_type=PAYMENT RECEIVED
GET /api/webhook-logs/?order_reference=KITONGA123
```
- ClickPesa Support: support@clickpesa.com
- Dashboard: https://dashboard.clickpesa.com
