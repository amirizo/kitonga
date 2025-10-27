# 🚀 KITONGA WI-FI SYSTEM - PRODUCTION DEPLOYMENT CHECKLIST

## ✅ Pre-Deployment Checklist

### Environment Configuration
- [x] Production .env file created with correct settings
- [x] DEBUG=False for production security
- [x] SECRET_KEY updated (⚠️ **Change the default key before deployment!**)
- [x] ClickPesa production credentials configured
- [x] NextSMS production credentials configured
- [x] CORS origins set to production domains
- [ ] SSL certificates ready for domains
- [ ] Domain DNS properly configured

### Security Settings
- [x] Production security headers enabled
- [x] HTTPS redirect configured
- [x] HSTS security enabled
- [x] Secure cookies for HTTPS
- [ ] Firewall rules configured
- [ ] Regular backup schedule set up

### Third-Party Services
- [x] ClickPesa API credentials (production)
- [x] NextSMS credentials (production mode)
- [ ] Mikrotik router admin password updated
- [ ] Router configuration uploaded
- [ ] SSL certificates installed

### Infrastructure
- [x] Docker configuration ready
- [x] Nginx configuration prepared
- [x] Health check endpoint available
- [x] Logging configured
- [x] SQLite database (as requested)
- [ ] Backup scripts scheduled

---

## 🛠️ Quick Deployment Commands

### 1. Test the Application Locally
```bash
# Run with production settings
python manage.py check --deploy
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py runserver
```

### 2. Docker Deployment
```bash
# Deploy with Docker Compose
./deploy.sh
```

### 3. Manual Server Deployment
```bash
# Clone repository
git clone https://github.com/amirizo/kitonga.git
cd kitonga

# Set up environment
cp .env.production .env
# Edit .env with your actual credentials

# Install dependencies
pip install -r requirements.txt

# Run Django setup
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser

# Start with Gunicorn
gunicorn --bind 0.0.0.0:8000 kitonga.wsgi:application
```

---

## 🔧 Critical Production Changes Needed

### 1. **URGENT: Change Secret Key**
```bash
# Generate a new secret key
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
Update in .env:
```
SECRET_KEY=your_new_generated_secret_key_here
```

### 2. **Update Mikrotik Password**
Update in .env:
```
MIKROTIK_ADMIN_PASS=your_actual_router_password
```

### 3. **Set Up SSL Certificates**
For domains: `kitonga.klikcell.com` and `api.kitonga.klikcell.com`

### 4. **Configure Admin Tokens**
Update in .env:
```
SIMPLE_ADMIN_TOKEN=your_secure_admin_token_here
ADMIN_TOKEN_SECRET=your_admin_secret_here
```

---

## 🌐 Domain Configuration

### DNS Records Required:
```
A    kitonga.klikcell.com         → Your_Server_IP
A    api.kitonga.klikcell.com     → Your_Server_IP
```

### SSL Certificate (Let's Encrypt):
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get certificates
sudo certbot --nginx -d kitonga.klikcell.com -d api.kitonga.klikcell.com
```

---

## 📊 Monitoring & Health Checks

### Health Check URLs:
- **API Health**: `https://api.kitonga.klikcell.com/api/health/`
- **Admin Panel**: `https://api.kitonga.klikcell.com/admin/`

### Monitoring Commands:
```bash
# Check application logs
docker-compose -f docker-compose.prod.yml logs -f web

# Check service status
docker-compose -f docker-compose.prod.yml ps

# Test API endpoint
curl -f https://api.kitonga.klikcell.com/api/health/
```

---

## 🔒 Security Recommendations

1. **Change Default Passwords**
   - Django admin password
   - Mikrotik router password
   - Admin API tokens

2. **Enable Firewall**
   ```bash
   sudo ufw enable
   sudo ufw allow 22/tcp    # SSH
   sudo ufw allow 80/tcp    # HTTP
   sudo ufw allow 443/tcp   # HTTPS
   ```

3. **Regular Backups**
   ```bash
   # Automated daily backup
   ./backup_db.sh
   ```

4. **Monitor Failed Login Attempts**
   - Check Django admin logs
   - Monitor API access logs

---

## 🚨 Troubleshooting

### Common Issues:

1. **502 Bad Gateway**
   - Check if application is running: `docker-compose ps`
   - Check logs: `docker-compose logs web`

2. **SSL Certificate Issues**
   - Verify certificates: `sudo certbot certificates`
   - Check nginx configuration

3. **Database Issues**
   - Check SQLite file permissions
   - Verify backup integrity

4. **Mikrotik Authentication Issues**
   - Test router connectivity
   - Verify API credentials
   - Check router configuration

---

## 📞 Support

- **Documentation**: Check `/docs` folder
- **API Documentation**: `kitonga_api_documentation.json`
- **Logs Location**: `./logs/django.log`

---

## ✅ Final Go-Live Checklist

- [ ] All environment variables configured
- [ ] SSL certificates installed and working
- [ ] DNS records pointing to server
- [ ] Database migrations applied
- [ ] Static files collected
- [ ] Admin user created
- [ ] Health checks passing
- [ ] Backup system working
- [ ] Monitoring configured
- [ ] Security hardening complete
- [ ] Load testing completed (if needed)

**🚀 Ready for Production Launch! 🚀**
