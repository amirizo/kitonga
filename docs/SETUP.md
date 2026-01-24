# Kitonga Setup Guide

## Quick Start

### 1. Backend Setup (5 minutes)

\`\`\`bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Setup database
python manage.py migrate
python manage.py createsuperuser

# Create default bundles
python scripts/create_default_bundles.py

# Start server
python manage.py runserver
\`\`\`

### 2. Frontend Setup (3 minutes)

\`\`\`bash
cd portal
npm install
cp .env.local.example .env.local
npm run dev
\`\`\`

### 3. Access the System

- **Portal**: http://localhost:3000
- **API**: http://localhost:8000/api
- **Admin**: http://localhost:8000/admin

## Environment Variables

### Required for Development

\`\`\`env
# Django
SECRET_KEY=any-random-string-for-development
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# ClickPesa (get from clickpesa.com)
CLICKPESA_CLIENT_ID=your-client-id
CLICKPESA_API_KEY=your-api-key

# NEXTSMS (get from messaging-service.co.tz)
NEXTSMS_USERNAME=your-username
NEXTSMS_PASSWORD=your-password
\`\`\`

### Optional Settings

\`\`\`env
# Device limits
MAX_DEVICES_PER_USER=3

# CORS (for production)
CORS_ALLOWED_ORIGINS=https://yourdomain.com

# Webhook URL (for production)
CLICKPESA_WEBHOOK_URL=https://yourdomain.com/api/clickpesa-webhook/
\`\`\`

## Testing the System

### 1. Test User Registration

1. Open portal at http://localhost:3000
2. Enter a phone number (e.g., 255712345678)
3. Select a bundle
4. Initiate payment

### 2. Test Voucher System

\`\`\`bash
# Generate vouchers via admin
python manage.py shell
>>> from billing.models import Voucher
>>> voucher = Voucher.objects.create(code=Voucher.generate_code(), duration_hours=24)
>>> print(voucher.code)
\`\`\`

Then redeem via portal.

### 3. Test Admin Dashboard

1. Go to http://localhost:8000/admin
2. Login with superuser credentials
3. View dashboard at http://localhost:8000/admin/dashboard/

## Common Issues

### Port Already in Use

\`\`\`bash
# Django (port 8000)
lsof -ti:8000 | xargs kill -9

# Next.js (port 3000)
lsof -ti:3000 | xargs kill -9
\`\`\`

### Database Locked

\`\`\`bash
# Reset database
rm db.sqlite3
python manage.py migrate
python manage.py createsuperuser
\`\`\`

### CORS Errors

Add portal URL to CORS_ALLOWED_ORIGINS in .env:
\`\`\`env
CORS_ALLOWED_ORIGINS=http://localhost:3000
\`\`\`

## Next Steps

1. Configure ClickPesa webhook for production
2. Set up cron jobs for expiry checks
3. Configure router integration
4. Deploy to production

See [DEPLOYMENT.md](DEPLOYMENT.md) for production setup.
