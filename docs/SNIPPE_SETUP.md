# Snippe Payment Gateway Integration

## Overview

Kitonga supports **Snippe** (https://api.snippe.sh) as a payment gateway alongside ClickPesa. Snippe provides:

- **Mobile Money** — Airtel Money, M-Pesa, Mixx by Yas, Halotel (USSD push)
- **Card Payments** — Visa, Mastercard, local debit cards (redirect checkout)
- **Dynamic QR** — Customer scans QR code with their mobile money app
- **Disbursements** — Send money to mobile money accounts
- **Payment Sessions** — Hosted checkout pages with shareable links

---

## Configuration

### Environment Variables

Add the following to your `.env` file:

```bash
# Snippe API Configuration
SNIPPE_API_KEY=snp_your_api_key_here
SNIPPE_WEBHOOK_SECRET=your_webhook_signing_secret
SNIPPE_BASE_URL=https://api.snippe.sh/v1
SNIPPE_WEBHOOK_URL=https://api.kitonga.klikcell.com/api/snippe/webhook/
```

### Per-Tenant Configuration

Each tenant can configure their own Snippe credentials in the Django Admin or via the Portal:

| Field                       | Description                                    |
| --------------------------- | ---------------------------------------------- |
| `snippe_api_key`            | Tenant's own Snippe API key                    |
| `snippe_webhook_secret`     | Webhook signing secret for verification        |
| `preferred_payment_gateway` | `clickpesa` or `snippe` — which gateway to use |

---

## API Endpoints

### Initiate Payment

```
POST /api/snippe/initiate-payment/
```

**Request Body:**

```json
{
  "phone_number": "255712345678",
  "bundle_id": 1,
  "router_id": 5,
  "payment_type": "mobile",
  "tenant": "hotel-wifi"
}
```

| Field          | Type    | Required | Description                                          |
| -------------- | ------- | -------- | ---------------------------------------------------- |
| `phone_number` | string  | **Yes**  | Customer phone (255XXXXXXXXX)                        |
| `bundle_id`    | integer | No       | Bundle package ID                                    |
| `router_id`    | integer | No       | Router where user is connecting                      |
| `payment_type` | string  | No       | `mobile` (default), `card`, `dynamic-qr`             |
| `tenant`       | string  | No       | Tenant slug (auto-resolved from API key / subdomain) |
| `redirect_url` | string  | For card | URL after successful card payment                    |
| `cancel_url`   | string  | For card | URL after cancelled card payment                     |

**Response (Mobile):**

```json
{
  "success": true,
  "message": "Payment request sent to your phone",
  "transaction_id": "uuid",
  "order_reference": "SNP123ABC",
  "snippe_reference": "9015c155-9e29-4e8e-...",
  "amount": 1000.0,
  "payment_type": "mobile",
  "status": "pending",
  "bundle": { "name": "Daily", "duration_hours": 24, "price": "1000.00" }
}
```

**Response (Card/QR — includes extra fields):**

```json
{
  "success": true,
  "payment_url": "https://tz.selcom.online/paymentgw/checkout/...",
  "payment_qr_code": "000201010212...",
  "expires_at": "2026-01-25T05:04:54Z"
}
```

---

### Webhook

```
POST /api/snippe/webhook/
```

Snippe sends webhooks for:

| Event               | Description                                |
| ------------------- | ------------------------------------------ |
| `payment.completed` | Payment successful → activates WiFi access |
| `payment.failed`    | Payment failed → sends SMS notification    |
| `payout.completed`  | Payout successful                          |
| `payout.failed`     | Payout failed                              |

The webhook handler:

1. Verifies the `X-Webhook-Signature` header (HMAC-SHA256)
2. Logs the webhook in `PaymentWebhook` table
3. Finds the local `Payment` record by `order_reference` in metadata
4. Marks payment completed/failed
5. Auto-connects user to MikroTik hotspot (same as ClickPesa flow)
6. Sends SMS confirmation via NextSMS

---

### Query Payment Status

```
GET /api/snippe/payment-status/{reference}/
```

Checks both local DB and Snippe API. If Snippe reports completed but local is still pending, it auto-completes the payment.

---

### Trigger USSD Push (Retry)

```
POST /api/snippe/trigger-push/{reference}/
```

Retry a USSD push for a pending mobile money payment.

**Optional body:**

```json
{
  "phone_number": "255787654321"
}
```

---

### Account Balance

```
GET /api/snippe/balance/
```

Returns current Snippe account balance.

---

## Payment Flow

### Mobile Money

```
Customer → POST /api/snippe/initiate-payment/ (payment_type=mobile)
         → Snippe sends USSD push to phone
         → Customer enters PIN
         → Snippe sends webhook to /api/snippe/webhook/
         → Kitonga activates WiFi access + sends SMS
```

### Card Payment

```
Customer → POST /api/snippe/initiate-payment/ (payment_type=card)
         → Frontend redirects to payment_url
         → Customer enters card details
         → Snippe redirects to redirect_url / cancel_url
         → Snippe sends webhook to /api/snippe/webhook/
         → Kitonga activates WiFi access
```

### Dynamic QR

```
Customer → POST /api/snippe/initiate-payment/ (payment_type=dynamic-qr)
         → Frontend renders payment_qr_code as QR image
         → Customer scans with mobile money app
         → Snippe sends webhook to /api/snippe/webhook/
         → Kitonga activates WiFi access
```

---

## Migration

Run the migration to add Snippe fields to the Tenant model:

```bash
python manage.py migrate billing 0017_add_snippe_payment_gateway
```

---

## Differences from ClickPesa

| Feature         | ClickPesa                       | Snippe                             |
| --------------- | ------------------------------- | ---------------------------------- |
| Auth            | Client ID + API Key → JWT token | Bearer API key (no token exchange) |
| Mobile Money    | USSD push                       | USSD push                          |
| Card Payments   | ❌                              | ✅ (redirect checkout)             |
| Dynamic QR      | ❌                              | ✅                                 |
| Hosted Checkout | ❌                              | ✅ (Payment Sessions)              |
| Webhook Signing | ❌                              | ✅ (HMAC-SHA256)                   |
| Idempotency     | ❌                              | ✅ (Idempotency-Key header)        |
| Payouts         | ✅ (Mobile + Bank)              | ✅ (Mobile)                        |
| Payment Expiry  | Varies                          | 4 hours                            |

---

## Files

| File                        | Purpose                              |
| --------------------------- | ------------------------------------ |
| `billing/snippe.py`         | Snippe API client (SnippeAPI class)  |
| `billing/views.py`          | Webhook + endpoint views             |
| `billing/urls.py`           | URL routes (`/api/snippe/*`)         |
| `billing/migrations/0017_*` | Database migration for Tenant fields |
| `kitonga/settings.py`       | Snippe env config                    |
| `docs/SNIPPE_SETUP.md`      | This documentation                   |
