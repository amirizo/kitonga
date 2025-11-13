# 🔧 HTTP Development Server - Quick Fix

## ⚡ THE PROBLEM

```
ERROR: You're accessing the development server over HTTPS, but it only supports HTTP.
```

## ✅ THE SOLUTION

### 1. Use the Easy Start Script

```bash
./start_dev.sh
```

### 2. Or Manually

```bash
# Make sure DEBUG is enabled
export DEBUG=True

# Start server
python manage.py runserver
```

### 3. Access Using HTTP (NOT HTTPS)

```
✅ CORRECT:   http://localhost:8000/admin/
❌ WRONG:     https://localhost:8000/admin/
```

---

## 🚀 Quick Commands

```bash
# Start development server
./start_dev.sh

# Or manually:
python manage.py runserver

# Stop server: Press Ctrl+C
```

---

## 🌐 Access URLs

| Service | URL |
|---------|-----|
| Admin Panel | `http://localhost:8000/admin/` |
| API Root | `http://localhost:8000/api/` |
| Users API | `http://localhost:8000/api/users/` |
| Payments API | `http://localhost:8000/api/payments/` |
| Bundles API | `http://localhost:8000/api/bundles/` |

**IMPORTANT:** Always use `http://` NOT `https://` in development!

---

## 🔍 Browser Issues?

### Clear HTTPS Cache

**Chrome:**
1. Go to `chrome://net-internals/#hsts`
2. Enter `localhost` in "Delete domain"
3. Click "Delete"

**Or use Incognito/Private mode:**
- Chrome: Cmd+Shift+N (Mac) or Ctrl+Shift+N (Windows)
- Safari: Cmd+Shift+N
- Firefox: Cmd+Shift+P (Mac) or Ctrl+Shift+P (Windows)

---

## 📋 What Was Fixed

### In `settings.py`:

```python
# Before: HTTPS forced even in development
# After: HTTP allowed in development

if not DEBUG:
    # Production: HTTPS required
    SECURE_SSL_REDIRECT = True
else:
    # Development: HTTP allowed
    SECURE_SSL_REDIRECT = False
```

### In `.env`:

```bash
DEBUG=True  # Enables HTTP mode
```

---

## ✅ Verification

Test that everything works:

```bash
# 1. Start server
./start_dev.sh

# 2. In another terminal, test:
curl http://localhost:8000/api/

# Should return JSON response, not an error
```

---

## 🐛 Still Having Issues?

1. **Check DEBUG mode:**
   ```bash
   python -c "from kitonga.settings import DEBUG; print(f'DEBUG={DEBUG}')"
   ```
   Should print: `DEBUG=True`

2. **Check if server is running:**
   ```bash
   ps aux | grep runserver
   ```

3. **Check port availability:**
   ```bash
   lsof -i :8000
   ```

4. **Kill stuck server:**
   ```bash
   pkill -f runserver
   ```

5. **Check firewall:**
   ```bash
   # Make sure port 8000 is not blocked
   ```

---

## 📚 More Help

- Full guide: See `DEVELOPMENT_SERVER_GUIDE.md`
- All documentation: See `QUICK_REFERENCE.md`
- Test system: Run `python test_system.py`

---

## 🎯 TL;DR

```bash
# 1. Start server
./start_dev.sh

# 2. Open browser
http://localhost:8000/admin/

# 3. Use HTTP, not HTTPS! ✅
```

That's it! 🎉
