# Development Server Guide - HTTP Configuration

## ✅ ISSUE FIXED

The errors you were seeing:
```
ERROR: You're accessing the development server over HTTPS, but it only supports HTTP.
```

These occurred because your browser was trying to access the development server using HTTPS, but Django's `runserver` only supports HTTP.

---

## 🚀 How to Run Development Server

### 1. **Enable DEBUG Mode**

Make sure your `.env` file has:
```bash
DEBUG=True
```

Or set it in your environment:
```bash
export DEBUG=True
```

### 2. **Start the Server**

```bash
python manage.py runserver
```

Or specify a custom port:
```bash
python manage.py runserver 8000
```

To make it accessible from other devices on your network:
```bash
python manage.py runserver 0.0.0.0:8000
```

### 3. **Access the Server Using HTTP (NOT HTTPS)**

✅ **CORRECT URLs:**
- `http://localhost:8000/`
- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/admin/`
- `http://192.168.0.x:8000/` (your local IP)

❌ **WRONG URLs (Will cause errors):**
- ~~`https://localhost:8000/`~~ (HTTPS won't work in development)
- ~~`https://127.0.0.1:8000/`~~ (HTTPS won't work in development)

---

## 🔧 What Was Fixed

### In `settings.py`:

```python
if not DEBUG:
    # Production security - HTTPS required
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
else:
    # Development mode - HTTP allowed
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
```

This ensures that:
- **In development (DEBUG=True)**: HTTP is allowed, no HTTPS redirects
- **In production (DEBUG=False)**: HTTPS is enforced for security

---

## 🌐 Browser Cache Issues

If your browser keeps redirecting to HTTPS, clear the cache:

### Chrome/Edge:
1. Open Developer Tools (F12)
2. Right-click the refresh button
3. Select "Empty Cache and Hard Reload"

Or use Incognito/Private mode:
- **Chrome**: Ctrl+Shift+N (Windows) or Cmd+Shift+N (Mac)
- **Safari**: Cmd+Shift+N
- **Firefox**: Ctrl+Shift+P (Windows) or Cmd+Shift+P (Mac)

### Clear HSTS Settings (if needed):
If Chrome remembers HTTPS for localhost:

1. Go to: `chrome://net-internals/#hsts`
2. In "Delete domain security policies", enter: `localhost`
3. Click "Delete"

---

## 🐳 Docker Development (Alternative)

If you want to use HTTPS in development, use Docker with nginx:

```bash
docker-compose up
```

This will set up:
- Django app on port 8000
- Nginx with SSL on port 443

---

## 📝 Common Development Commands

```bash
# Start development server (HTTP only)
python manage.py runserver

# Run on specific port
python manage.py runserver 8080

# Run on all interfaces (accessible from other devices)
python manage.py runserver 0.0.0.0:8000

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic

# Run tests
python test_system.py
```

---

## 🔒 Production Deployment

For production, always use:
- DEBUG=False
- HTTPS/SSL certificate
- nginx or Apache as reverse proxy
- gunicorn or uWSGI as WSGI server

**Never use `runserver` in production!**

---

## 🎯 Quick Start

1. **Set DEBUG mode:**
   ```bash
   export DEBUG=True
   ```

2. **Run server:**
   ```bash
   python manage.py runserver
   ```

3. **Open browser:**
   ```
   http://localhost:8000/admin/
   ```

4. **Login with your admin credentials**

That's it! Your development server is now running on HTTP. 🎉

---

## 🆘 Still Having Issues?

Check:
1. ✅ DEBUG=True in your environment
2. ✅ Using `http://` not `https://`
3. ✅ Browser cache cleared
4. ✅ No HSTS policy for localhost
5. ✅ Port 8000 is not blocked by firewall

If issues persist, check the console output for specific error messages.
