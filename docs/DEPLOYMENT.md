# Kitonga Deployment Guide

## Prerequisites

- Ubuntu 20.04+ server
- Python 3.8+
- Node.js 18+
- Nginx
- PostgreSQL or MySQL (optional, for production)
- Domain name (optional)

## Backend Deployment

### 1. Server Setup

\`\`\`bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install python3-pip python3-venv nginx postgresql postgresql-contrib -y
\`\`\`

### 2. Clone and Setup Project

\`\`\`bash
# Create project directory
mkdir -p /var/www/kitonga
cd /var/www/kitonga

# Clone your repository
git clone <your-repo-url> .

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install gunicorn psycopg2-binary
\`\`\`

### 3. Configure Environment

\`\`\`bash
# Create .env file
cp .env.example .env
nano .env
\`\`\`

Update with production values:
\`\`\`
SECRET_KEY=your-secure-secret-key
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
DATABASE_URL=postgresql://user:password@localhost/kitonga
MPESA_CONSUMER_KEY=your-production-key
MPESA_CONSUMER_SECRET=your-production-secret
MPESA_ENVIRONMENT=production
\`\`\`

### 4. Setup Database

\`\`\`bash
# Create PostgreSQL database
sudo -u postgres psql
CREATE DATABASE kitonga;
CREATE USER kitonga_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE kitonga TO kitonga_user;
\q

# Run migrations
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
\`\`\`

### 5. Configure Gunicorn

Create `/etc/systemd/system/kitonga.service`:

\`\`\`ini
[Unit]
Description=Kitonga Wi-Fi Billing System
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/kitonga
Environment="PATH=/var/www/kitonga/venv/bin"
ExecStart=/var/www/kitonga/venv/bin/gunicorn --workers 3 --bind unix:/var/www/kitonga/kitonga.sock kitonga.wsgi:application

[Install]
WantedBy=multi-user.target
\`\`\`

Start service:
\`\`\`bash
sudo systemctl start kitonga
sudo systemctl enable kitonga
\`\`\`

### 6. Configure Nginx

Create `/etc/nginx/sites-available/kitonga`:

\`\`\`nginx
server {
    listen 80;
    server_name your-domain.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        root /var/www/kitonga;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/kitonga/kitonga.sock;
    }
}
\`\`\`

Enable site:
\`\`\`bash
sudo ln -s /etc/nginx/sites-available/kitonga /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
\`\`\`

## Frontend Deployment

### 1. Build Portal

\`\`\`bash
cd portal
npm install
npm run build
\`\`\`

### 2. Configure Nginx for Portal

Add to Nginx config:

\`\`\`nginx
server {
    listen 80;
    server_name portal.your-domain.com;

    root /var/www/kitonga/portal/out;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
\`\`\`

## Router Integration

### OpenWRT + Nodogsplash

1. Install Nodogsplash:
\`\`\`bash
opkg update
opkg install nodogsplash
\`\`\`

2. Configure `/etc/nodogsplash/nodogsplash.conf`:
\`\`\`
GatewayInterface br-lan
GatewayAddress 192.168.1.1
GatewayPort 2050
MaxClients 250
SplashPage http://portal.your-domain.com
\`\`\`

3. Create auth script `/etc/nodogsplash/auth.sh`:
\`\`\`bash
#!/bin/sh
PHONE=$1
API_URL="http://your-domain.com/api/verify/"

# Verify access
RESPONSE=$(curl -s -X POST $API_URL -H "Content-Type: application/json" -d "{\"phone_number\":\"$PHONE\"}")
ACCESS=$(echo $RESPONSE | grep -o '"access_granted":true')

if [ -n "$ACCESS" ]; then
    echo "allow"
else
    echo "deny"
fi
\`\`\`

## Monitoring

### Setup Cron Job for Expired Users

\`\`\`bash
crontab -e
\`\`\`

Add:
\`\`\`
*/5 * * * * /var/www/kitonga/venv/bin/python /var/www/kitonga/manage.py check_expired_users
\`\`\`

### Health Check

Setup monitoring for:
- `http://your-domain.com/api/health/`
- Database connectivity
- M-Pesa API availability

## SSL Certificate (Optional but Recommended)

\`\`\`bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
\`\`\`

## Backup Strategy

\`\`\`bash
# Database backup script
#!/bin/bash
pg_dump kitonga > /backups/kitonga_$(date +%Y%m%d).sql
\`\`\`

Add to crontab:
\`\`\`
0 2 * * * /path/to/backup-script.sh
\`\`\`

## Security Checklist

- [ ] Change default SECRET_KEY
- [ ] Set DEBUG=False
- [ ] Configure ALLOWED_HOSTS
- [ ] Setup SSL/TLS
- [ ] Configure firewall (ufw)
- [ ] Secure M-Pesa credentials
- [ ] Setup rate limiting
- [ ] Enable Django security middleware
- [ ] Regular security updates
- [ ] Monitor access logs

## Troubleshooting

### Check Service Status
\`\`\`bash
sudo systemctl status kitonga
sudo systemctl status nginx
\`\`\`

### View Logs
\`\`\`bash
sudo journalctl -u kitonga -f
sudo tail -f /var/log/nginx/error.log
\`\`\`

### Test M-Pesa Connection
\`\`\`bash
python manage.py shell
from billing.mpesa import MPesaAPI
mpesa = MPesaAPI()
token = mpesa.get_access_token()
print(token)
\`\`\`
