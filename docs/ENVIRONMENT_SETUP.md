# Environment Configuration Guide

This guide explains how to set up your environment variables for the Kitonga Wi-Fi system.

## Quick Setup

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file with your actual credentials and configuration.

## Environment Variables Explained

### Django Configuration

- **SECRET_KEY**: A secret key for Django security. Generate a new one for production.
- **DEBUG**: Set to `True` for development, `False` for production.
- **ALLOWED_HOSTS**: Comma-separated list of allowed hostnames.

### ClickPesa Payment Gateway

ClickPesa is used for mobile money payments (M-Pesa, Tigo Pesa, Airtel Money, Halopesa).

1. **Sign up for ClickPesa**: Visit [ClickPesa](https://clickpesa.com) and create a merchant account.

2. **Get your credentials**:
   - `CLICKPESA_CLIENT_ID`: Your merchant client ID
   - `CLICKPESA_API_KEY`: Your API key from the merchant dashboard
   - `CLICKPESA_WEBHOOK_URL`: Your webhook URL (e.g., `https://yourdomain.com/api/clickpesa-webhook/`)

3. **Configure webhook**: In your ClickPesa dashboard, set the webhook URL to receive payment notifications.

### NextSMS Configuration

NextSMS is used for sending SMS notifications to users.

1. **Sign up for NextSMS**: Visit [NextSMS](https://nextsms.co.tz) and create an account.

2. **Get your credentials**:
   - `NEXTSMS_USERNAME`: Your NextSMS username
   - `NEXTSMS_PASSWORD`: Your NextSMS password
   - `NEXTSMS_SENDER_ID`: Your approved sender ID (e.g., "KITONGA")

3. **Test Mode**: Set `IS_TEST_MODE=True` for development to use test endpoints.

### System Configuration

- **MAX_DEVICES_PER_USER**: Maximum number of devices a user can connect simultaneously (default: 3).

## Example Configuration

### Development Environment

```env
# Django
SECRET_KEY=your-development-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# ClickPesa (Sandbox)
CLICKPESA_CLIENT_ID=sandbox_client_id
CLICKPESA_API_KEY=sandbox_api_key
CLICKPESA_BASE_URL=https://api.clickpesa.com
CLICKPESA_WEBHOOK_URL=https://yourdomain.com/api/clickpesa-webhook/

# NextSMS (Test Mode)
NEXTSMS_USERNAME=your_username
NEXTSMS_PASSWORD=your_password
NEXTSMS_SENDER_ID=KITONGA
IS_TEST_MODE=True

# System
MAX_DEVICES_PER_USER=3
```

### Production Environment

```env
# Django
SECRET_KEY=your-super-secure-production-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database (PostgreSQL recommended for production)
DATABASE_URL=postgresql://username:password@localhost:5432/kitonga_db

# ClickPesa (Production)
CLICKPESA_CLIENT_ID=production_client_id
CLICKPESA_API_KEY=production_api_key
CLICKPESA_BASE_URL=https://api.clickpesa.com
CLICKPESA_WEBHOOK_URL=https://yourdomain.com/api/clickpesa-webhook/

# NextSMS (Production)
NEXTSMS_USERNAME=your_username
NEXTSMS_PASSWORD=your_password
NEXTSMS_SENDER_ID=KITONGA
IS_TEST_MODE=False

# System
MAX_DEVICES_PER_USER=3
```

## Security Notes

1. **Never commit the `.env` file** to version control. It's already in `.gitignore`.

2. **Generate a strong SECRET_KEY** for production:
   ```python
   from django.core.management.utils import get_random_secret_key
   print(get_random_secret_key())
   ```

3. **Use environment-specific values** for different deployment environments.

4. **Keep credentials secure** and rotate them regularly.

## Testing Configuration

To test if your configuration is working:

1. **Test Django settings**:
   ```bash
   python manage.py check
   ```

2. **Test ClickPesa integration**:
   ```bash
   python manage.py shell
   >>> from billing.clickpesa import ClickPesaAPI
   >>> api = ClickPesaAPI()
   >>> # Test connection
   ```

3. **Test NextSMS integration**:
   ```bash
   python manage.py shell
   >>> from billing.nextsms import NextSMSAPI
   >>> api = NextSMSAPI()
   >>> # Test SMS sending
   ```

## Troubleshooting

### Common Issues

1. **ClickPesa webhook not receiving notifications**:
   - Ensure your webhook URL is publicly accessible
   - Check that the URL is correctly configured in ClickPesa dashboard
   - Verify SSL certificate is valid

2. **SMS not sending**:
   - Check NextSMS account balance
   - Verify sender ID is approved
   - Ensure phone numbers are in correct format (+255...)

3. **Environment variables not loading**:
   - Ensure `.env` file is in the project root
   - Check for syntax errors in `.env` file
   - Restart the Django server after changes

### Getting Help

- ClickPesa Support: [ClickPesa Documentation](https://clickpesa.com/docs)
- NextSMS Support: [NextSMS Documentation](https://nextsms.co.tz/docs)
- Django Documentation: [Django Settings](https://docs.djangoproject.com/en/stable/topics/settings/)
