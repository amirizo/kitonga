# 🚀 KITONGA WI-FI SYSTEM - PRODUCTION DEPLOYMENT GUIDE

## Overview
Deploy Kitonga Wi-Fi Billing System to production with:
- **Frontend**: https://kitonga.klikcell.com
- **Backend API**: https://api.kitonga.klikcell.com/api
- **Mikrotik Integration**: Full hotspot authentication

---

## 📋 PRE-DEPLOYMENT CHECKLIST

### ✅ Domain & SSL Setup
- [ ] Domain `kitonga.klikcell.com` pointing to frontend server
- [ ] Domain `api.kitonga.klikcell.com` pointing to backend server
- [ ] SSL certificates installed (Let's Encrypt recommended)
- [ ] DNS propagation complete

### ✅ Server Requirements
- [ ] Ubuntu 20.04+ server with 2GB+ RAM
- [ ] Python 3.9+ installed
- [ ] PostgreSQL 13+ installed
- [ ] Nginx installed
- [ ] Git installed
- [ ] SSL certificates configured

### ✅ Third-Party Services
- [ ] ClickPesa production credentials
- [ ] NextSMS production credentials
- [ ] Database backup strategy
- [ ] Monitoring setup

---

## 🔧 BACKEND DEPLOYMENT (api.kitonga.klikcell.com)

### 1. Server Setup
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3-pip python3-venv nginx postgresql postgresql-contrib redis-server

# Create application user
sudo adduser kitonga
sudo usermod -aG sudo kitonga
```

### 2. Database Setup
```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE kitonga_db;
CREATE USER kitonga_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE kitonga_db TO kitonga_user;
ALTER USER kitonga_user CREATEDB;
\q
```

### 3. Application Deployment
```bash
# Switch to application user
sudo su - kitonga

# Clone repository
git clone https://github.com/your-username/kitonga.git
cd kitonga

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy production environment
cp .env.production .env
```

### 4. Configure Environment (.env)
```env
SECRET_KEY=your-super-secret-production-key-here
DEBUG=False
ALLOWED_HOSTS=api.kitonga.klikcell.com,kitonga.klikcell.com
CORS_ALLOWED_ORIGINS=https://kitonga.klikcell.com,https://api.kitonga.klikcell.com

# Database
DATABASE_URL=postgres://kitonga_user:your_secure_password@localhost:5432/kitonga_db

# Payment Gateway
CLICKPESA_CLIENT_ID=your_production_client_id
CLICKPESA_API_KEY=your_production_api_key
CLICKPESA_WEBHOOK_URL=https://api.kitonga.klikcell.com/api/clickpesa-webhook/

# SMS Service
NEXTSMS_USERNAME=your_nextsms_username
NEXTSMS_PASSWORD=your_nextsms_password
IS_TEST_MODE=False

# Mikrotik
MIKROTIK_ROUTER_IP=192.168.88.1
MIKROTIK_ADMIN_PASS=your_router_password
```

### 5. Django Setup
```bash
# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Create superuser
python manage.py createsuperuser

# Test server
python manage.py runserver 0.0.0.0:8000
```

### 6. Gunicorn Setup
```bash
# Test gunicorn
gunicorn --bind 0.0.0.0:8000 kitonga.wsgi

# Create gunicorn socket
sudo nano /etc/systemd/system/gunicorn.socket
```

**gunicorn.socket content:**
```ini
[Unit]
Description=gunicorn socket

[Socket]
ListenStream=/run/gunicorn.sock

[Install]
WantedBy=sockets.target
```

**gunicorn.service content:**
```ini
[Unit]
Description=gunicorn daemon
Requires=gunicorn.socket
After=network.target

[Service]
User=kitonga
Group=www-data
WorkingDirectory=/home/kitonga/kitonga
ExecStart=/home/kitonga/kitonga/venv/bin/gunicorn \
          --access-logfile - \
          --workers 3 \
          --bind unix:/run/gunicorn.sock \
          kitonga.wsgi:application

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start services
sudo systemctl enable gunicorn.socket
sudo systemctl start gunicorn.socket
sudo systemctl enable gunicorn.service
sudo systemctl start gunicorn.service
```

### 7. Nginx Configuration
```bash
sudo nano /etc/nginx/sites-available/kitonga
```

**Nginx configuration:**
```nginx
server {
    listen 80;
    server_name api.kitonga.klikcell.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.kitonga.klikcell.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/api.kitonga.klikcell.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.kitonga.klikcell.com/privkey.pem;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_stapling on;
    ssl_stapling_verify on;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";

    client_max_body_size 10M;

    location /static/ {
        alias /home/kitonga/kitonga/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/kitonga /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 🌐 FRONTEND DEPLOYMENT (kitonga.klikcell.com)

### Option 1: Static Hosting (Recommended)
- Use Vercel, Netlify, or similar
- Configure build command: `npm run build`
- Set environment variables for API URL

### Option 2: Self-Hosted
```bash
# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Clone frontend repository
git clone https://github.com/your-username/kitonga-frontend.git
cd kitonga-frontend

# Install dependencies
npm install

# Build for production
npm run build

# Serve with Nginx (add to existing config)
```

---

## 🔧 MIKROTIK CONFIGURATION

### 1. Upload Custom HTML Files
1. Open Winbox and connect to your router
2. Go to **Files**
3. Create folder: `hotspot`
4. Upload files from `hotspot_files/` directory:
   - `login.html`
   - `status.html` 
   - `logout.html`
   - `error.html`

### 2. Apply Router Configuration
```bash
# Import the configuration file
/import file-name=mikrotik_production_config.rsc
```

### 3. Key Settings to Verify
```bash
# Check hotspot profile
/ip hotspot user profile print

# Verify external auth URL
# Should show: https://api.kitonga.klikcell.com/api/mikrotik/auth/

# Check walled garden
/ip hotspot walled-garden print
# Should include api.kitonga.klikcell.com

# Test connectivity
/tool fetch url="https://api.kitonga.klikcell.com/api/health/"
```

---

## 🔐 SSL CERTIFICATE SETUP

### Using Let's Encrypt (Recommended)
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get certificates
sudo certbot --nginx -d api.kitonga.klikcell.com
sudo certbot --nginx -d kitonga.klikcell.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

---

## 📊 MONITORING & MAINTENANCE

### 1. Log Management
```bash
# View Django logs
sudo journalctl -u gunicorn.service -f

# View Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# View system logs
sudo tail -f /var/log/syslog
```

### 2. Database Backup
```bash
# Create backup script
nano /home/kitonga/backup_db.sh
```

**Backup script:**
```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump -U kitonga_user -h localhost kitonga_db > /home/kitonga/backups/kitonga_db_$DATE.sql
# Keep only last 7 days
find /home/kitonga/backups/ -name "*.sql" -mtime +7 -delete
```

```bash
# Make executable and schedule
chmod +x /home/kitonga/backup_db.sh
crontab -e
# Add: 0 2 * * * /home/kitonga/backup_db.sh
```

### 3. Health Checks
```bash
# Create health check script
nano /home/kitonga/health_check.sh
```

**Health check script:**
```bash
#!/bin/bash
# Check API health
curl -f https://api.kitonga.klikcell.com/api/health/ || echo "API DOWN" | mail -s "Kitonga API Alert" admin@yourdomain.com

# Check database
sudo -u postgres psql -d kitonga_db -c "SELECT 1;" > /dev/null || echo "DB DOWN" | mail -s "Kitonga DB Alert" admin@yourdomain.com
```

---

## 🧪 TESTING CHECKLIST

### Backend API Tests
- [ ] Health check: `https://api.kitonga.klikcell.com/api/health/`
- [ ] Admin login works
- [ ] User registration/payment flow
- [ ] SMS notifications working
- [ ] Webhook receiving payments
- [ ] Mikrotik authentication endpoint responding

### Frontend Tests  
- [ ] Website loads: `https://kitonga.klikcell.com`
- [ ] User can register
- [ ] Payment flow works
- [ ] Bundle purchase successful
- [ ] Admin dashboard accessible

### Mikrotik Integration Tests
- [ ] Hotspot captures users
- [ ] Custom login page loads
- [ ] Authentication with valid user works
- [ ] Authentication rejects invalid users
- [ ] Status page shows correct info
- [ ] Logout works properly

### End-to-End Test
1. [ ] New user registers on website
2. [ ] User purchases bundle via ClickPesa
3. [ ] User receives SMS confirmation
4. [ ] User connects to Wi-Fi hotspot
5. [ ] User enters phone number and gets internet
6. [ ] Session tracking works
7. [ ] User can logout successfully

---

## 🚨 TROUBLESHOOTING

### Common Issues

**1. 502 Bad Gateway**
```bash
# Check gunicorn status
sudo systemctl status gunicorn.service
sudo journalctl -u gunicorn.service -f
```

**2. Database Connection Error**
```bash
# Check PostgreSQL
sudo systemctl status postgresql
sudo -u postgres psql -c "\l"
```

**3. SSL Certificate Issues**
```bash
# Check certificate
sudo certbot certificates
openssl s_client -connect api.kitonga.klikcell.com:443
```

**4. Mikrotik Authentication Fails**
```bash
# Check Mikrotik logs
/log print where topics~"hotspot"

# Test API directly
curl -X POST https://api.kitonga.klikcell.com/api/mikrotik/auth/ \
  -d "username=255708374149&mac=aa:bb:cc:dd:ee:ff&ip=192.168.88.100"
```

---

## 📞 SUPPORT CONTACTS

- **System Admin**: admin@kitonga.klikcell.com
- **Technical Support**: +255 XXX XXX XXX
- **Emergency**: +255 XXX XXX XXX (24/7)

---

## 🎉 GO LIVE CHECKLIST

- [ ] All tests passing
- [ ] SSL certificates valid
- [ ] Monitoring configured
- [ ] Backups scheduled
- [ ] DNS propagated
- [ ] Payment gateway in production mode
- [ ] SMS service in production mode
- [ ] Mikrotik router configured
- [ ] Staff trained on admin panel
- [ ] Customer support ready
- [ ] Launch announcement prepared

**🚀 READY FOR LAUNCH! 🚀**
