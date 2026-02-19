"""
Django settings for Kitonga Wi-Fi Billing System
"""

from pathlib import Path
from decouple import config, Csv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config(
    "SECRET_KEY", default="django-insecure-kitonga-dev-key-change-in-production"
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config("DEBUG", default=False, cast=bool)

# Development vs Production URL Configuration
ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1,api.kitonga.klikcell.com,kitonga.klikcell.com,testserver",
    cast=Csv(),
)

# Add development-specific hosts when DEBUG is True
if DEBUG:
    additional_dev_hosts = ["192.168.1.1", "10.0.0.1"]
    for host in additional_dev_hosts:
        if host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(host)

# Application definition
INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "django_crontab",  # For scheduled tasks
    "billing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Multi-tenant middleware
    "billing.middleware.TenantMiddleware",
]

# Add debugging middleware in development
if DEBUG:
    # Ensure no middleware tries to force HTTPS in development
    pass  # All middleware above is fine for development

ROOT_URLCONF = "kitonga.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "kitonga.wsgi.application"

# Database
# MySQL Configuration (production-ready)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": config("DB_NAME", default="kitonga"),
        "USER": config("DB_USER", default="root"),
        "PASSWORD": config("DB_PASSWORD", default="Kijangwani2003"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Dar_es_Salaam"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise configuration for static files in production
# In production, nginx serves static files directly for better performance
# WhiteNoise handles compression and manifest during collectstatic
if DEBUG:
    # Development: Use simple storage for faster reloads
    STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
else:
    # Production: Use custom storage that handles missing source maps gracefully
    STATICFILES_STORAGE = "kitonga.storage.IgnoreMissingStaticFilesStorage"

# WhiteNoise settings
WHITENOISE_USE_FINDERS = DEBUG  # Only use finders in development
WHITENOISE_AUTOREFRESH = DEBUG  # Only in development
WHITENOISE_MAX_AGE = 31536000 if not DEBUG else 0  # 1 year cache in production

# Static files configuration
STATICFILES_DIRS = []
if (BASE_DIR / "static").exists():
    STATICFILES_DIRS.append(BASE_DIR / "static")
if (BASE_DIR / "kitonga" / "static").exists():
    STATICFILES_DIRS.append(BASE_DIR / "kitonga" / "static")

# Media files configuration (for user uploads if needed)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Security Settings - Environment Aware Configuration
if not DEBUG:
    # Production Security Settings (ONLY enabled when DEBUG=False)
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_REDIRECT_EXEMPT = []
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    # Session security for production
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_PRELOAD = True

    # Additional production security
    X_FRAME_OPTIONS = "DENY"
    SECURE_REFERRER_POLICY = "same-origin"
else:
    # Development mode - disable ALL HTTPS-related security features
    SECURE_SSL_REDIRECT = False
    SECURE_BROWSER_XSS_FILTER = False
    SECURE_CONTENT_TYPE_NOSNIFF = False
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_PRELOAD = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    X_FRAME_OPTIONS = "SAMEORIGIN"
    SECURE_REFERRER_POLICY = None

    # Ensure no proxy SSL headers are processed in development
    SECURE_PROXY_SSL_HEADER = None

# Production Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs" / "django.log",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO" if DEBUG else "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"] if not DEBUG else ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "billing": {
            "handlers": ["console", "file"] if not DEBUG else ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# REST Framework Configuration
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "EXCEPTION_HANDLER": "billing.exception_handler.custom_exception_handler",
}

# CORS settings - Environment Aware
if DEBUG:
    # Development: Allow all origins for testing
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOWED_ORIGINS = []
else:
    # Production: Restrict to specific origins
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = config(
        "CORS_ALLOWED_ORIGINS",
        default="https://kitonga.klikcell.com,https://api.kitonga.klikcell.com,http://localhost:3000",
        cast=Csv(),
    )

# CORS preflight settings
CORS_PREFLIGHT_MAX_AGE = 86400  # 24 hours

# Allow cookies and authorization headers
CORS_ALLOW_CREDENTIALS = True

# CSRF settings - Environment Aware
if DEBUG:
    # Development: More permissive CSRF settings
    CSRF_TRUSTED_ORIGINS = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",  # For frontend development
    ]
else:
    # Production: Strict CSRF settings
    CSRF_TRUSTED_ORIGINS = [
        "https://kitonga.klikcell.com",
        "https://api.kitonga.klikcell.com",
        "http://localhost:3000",
    ]

# Allow specific headers for CORS
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-api-key",
    "x-requested-with",
    "x-admin-access",  # Custom header for admin authentication
    "cache-control",  # For static file caching
    "expires",  # For static file caching
]

# Allow specific methods
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

# ClickPesa Configuration
CLICKPESA_CLIENT_ID = config("CLICKPESA_CLIENT_ID", default="")
CLICKPESA_API_KEY = config("CLICKPESA_API_KEY", default="")
CLICKPESA_BASE_URL = config("CLICKPESA_BASE_URL", default="https://api.clickpesa.com")
CLICKPESA_WEBHOOK_URL = config("CLICKPESA_WEBHOOK_URL", default="")

# Snippe Payment API Configuration (https://api.snippe.sh)
SNIPPE_API_KEY = config("SNIPPE_API_KEY", default="")
SNIPPE_WEBHOOK_SECRET = config("SNIPPE_WEBHOOK_SECRET", default="")
SNIPPE_BASE_URL = config("SNIPPE_BASE_URL", default="https://api.snippe.sh/v1")
SNIPPE_WEBHOOK_URL = config("SNIPPE_WEBHOOK_URL", default="")

# NEXTSMS Configuration
NEXTSMS_USERNAME = config("NEXTSMS_USERNAME", default="")
NEXTSMS_PASSWORD = config("NEXTSMS_PASSWORD", default="")
NEXTSMS_SENDER_ID = config("NEXTSMS_SENDER_ID", default="Klikcell")
NEXTSMS_BASE_URL = config("NEXTSMS_BASE_URL", default="https://messaging-service.co.tz")
IS_TEST_MODE = config("IS_TEST_MODE", default=False, cast=bool)

# NextSMS API URLs
NEXTSMS_TEST_URL = "https://messaging-service.co.tz/api/sms/v1/test/text/single"
NEXTSMS_PROD_URL = "https://messaging-service.co.tz/api/sms/v1/text/single"
NEXTSMS_API_URL = NEXTSMS_TEST_URL if IS_TEST_MODE else NEXTSMS_PROD_URL


# Wi-Fi Access Configuration
DAILY_ACCESS_PRICE = 1000  # TSh 1,000
ACCESS_DURATION_HOURS = 24

# Device Management
MAX_DEVICES_PER_USER = config("MAX_DEVICES_PER_USER", default=1, cast=int)

# Admin Authentication Token (for frontend API access)
SIMPLE_ADMIN_TOKEN = config("SIMPLE_ADMIN_TOKEN", default="kitonga_admin_2025")
ADMIN_TOKEN_SECRET = config("ADMIN_TOKEN_SECRET", default=SECRET_KEY)


# MikroTik API Configuration (env-driven)
try:
    from decouple import config as _cfg

    # Default to WireGuard VPN tunnel IP for remote router access
    MIKROTIK_HOST = _cfg("MIKROTIK_HOST", default="10.50.0.2")
    MIKROTIK_PORT = _cfg("MIKROTIK_PORT", default=8728, cast=int)
    MIKROTIK_USER = _cfg("MIKROTIK_USER", default="admin")
    MIKROTIK_PASSWORD = _cfg("MIKROTIK_PASSWORD", default="Kijangwani2003")
    MIKROTIK_USE_SSL = _cfg("MIKROTIK_USE_SSL", default=False, cast=bool)
    # Control SSL certificate verification for self-signed certs (default: disabled)
    MIKROTIK_SSL_VERIFY = _cfg("MIKROTIK_SSL_VERIFY", default=False, cast=bool)
    MIKROTIK_DEFAULT_PROFILE = _cfg("MIKROTIK_DEFAULT_PROFILE", default="default")
    MIKROTIK_HOTSPOT_NAME = _cfg("MIKROTIK_HOTSPOT", default="hotspot1")
except Exception:
    # Fallback defaults (WireGuard VPN tunnel)
    MIKROTIK_HOST = "10.50.0.2"
    MIKROTIK_PORT = 8728
    MIKROTIK_USER = "admin"
    MIKROTIK_PASSWORD = "Kijangwani2003"
    MIKROTIK_USE_SSL = False
    MIKROTIK_SSL_VERIFY = False
    MIKROTIK_DEFAULT_PROFILE = "default"
    MIKROTIK_HOTSPOT_NAME = "hotspot1"

# Jazzmin Configuration
JAZZMIN_SETTINGS = {
    # Title of the window
    "site_title": "Kitonga SaaS Admin",
    # Title on the login screen (19 chars max)
    "site_header": "Kitonga SaaS",
    # Title on the brand (19 chars max)
    "site_brand": "Kitonga SaaS",
    # Logo to use for your site, must be present in static files, used for brand on top left
    "site_logo": None,
    # Logo to use for your site, must be present in static files, used for login form logo
    "login_logo": None,
    # Logo to use for login form in dark themes
    "login_logo_dark": None,
    # CSS classes that are applied to the logo above
    "site_logo_classes": "img-circle",
    # Relative path to a favicon for your site, will default to site_logo if absent (ideally 32x32 px)
    "site_icon": None,
    # Welcome text on the login screen
    "welcome_sign": "Welcome to Kitonga SaaS Platform",
    # Copyright on the footer
    "copyright": "Kitonga WiFi SaaS Platform",
    # List of model admins to search from the search bar
    "search_model": [
        "auth.User",
        "billing.Tenant",
        "billing.User",
        "billing.Payment",
        "billing.Router",
    ],
    # Field name on user model that contains avatar
    "user_avatar": None,
    ############
    # Top Menu #
    ############
    # Links to put along the top menu
    "topmenu_links": [
        # Url that gets reversed (Permissions can be added)
        {"name": "Home", "url": "admin:index", "permissions": ["auth.view_user"]},
        # external url that opens in a new window (Permissions can be added)
        {"name": "Portal", "url": "https://kitonga.klikcell.com", "new_window": True},
        # model admin to link to (Permissions checked against model)
        {"model": "auth.User"},
        # App with dropdown menu to all its models pages (Permissions checked against models)
        {"app": "billing"},
    ],
    #############
    # User Menu #
    #############
    # Additional links to include in the user menu on the top right ("app" url type is not allowed)
    "usermenu_links": [
        {
            "name": "Portal Home",
            "url": "https://kitonga.klikcell.com",
            "new_window": True,
        },
        {"model": "auth.user"},
    ],
    #############
    # Side Menu #
    #############
    # Whether to display the side menu
    "show_sidebar": True,
    # Whether to aut expand the menu
    "navigation_expanded": True,
    # Hide these apps when generating side menu e.g (auth)
    "hide_apps": [],
    # Hide these models when generating side menu (e.g auth.user)
    "hide_models": [],
    # List of apps (and/or models) to base side menu ordering off of (does not need to contain all apps/models)
    "order_with_respect_to": ["auth", "billing"],
    # Custom links to append to app groups, keyed on app name
    "custom_links": {
        "billing": [
            {
                "name": "System Statistics",
                "url": "admin:billing_statistics",
                "icon": "fas fa-chart-bar",
                "permissions": ["billing.view_payment"],
            }
        ]
    },
    # Custom icons for side menu apps/models
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        # SaaS Platform Models
        "billing.SubscriptionPlan": "fas fa-layer-group",
        "billing.Tenant": "fas fa-building",
        "billing.TenantStaff": "fas fa-user-tie",
        "billing.Location": "fas fa-map-marker-alt",
        "billing.Router": "fas fa-network-wired",
        "billing.TenantSubscriptionPayment": "fas fa-file-invoice-dollar",
        # WiFi Billing Models
        "billing.User": "fas fa-wifi",
        "billing.Bundle": "fas fa-boxes",
        "billing.Payment": "fas fa-credit-card",
        "billing.Voucher": "fas fa-ticket-alt",
        "billing.Device": "fas fa-mobile-alt",
        "billing.AccessLog": "fas fa-history",
        "billing.SMSLog": "fas fa-sms",
        "billing.PaymentWebhook": "fas fa-plug",
    },
    # Icons that are used when one is not manually specified
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    #################
    # Related Modal #
    #################
    # Use modals instead of popups
    "related_modal_active": False,
    #############
    # UI Tweaks #
    #############
    # Relative paths to custom CSS/JS scripts (must be present in static files)
    "custom_css": None,
    "custom_js": None,
    # Whether to link font from fonts.googleapis.com (use custom_css to supply font otherwise)
    "use_google_fonts_cdn": True,
    # Whether to show the UI customizer on the sidebar
    "show_ui_builder": True,
    ###############
    # Change view #
    ###############
    # Render out the change view as a single form, or in tabs, current options are
    # - single
    # - horizontal_tabs (default)
    # - vertical_tabs
    # - collapsible
    # - carousel
    "changeform_format": "horizontal_tabs",
    # override change forms on a per modeladmin basis
    "changeform_format_overrides": {
        "auth.user": "collapsible",
        "auth.group": "vertical_tabs",
    },
    # Add a language dropdown into the admin
    "language_chooser": False,
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-primary",
    "accent": "accent-primary",
    "navbar": "navbar-white navbar-light",
    "no_navbar_border": False,
    "navbar_fixed": False,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": False,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-outline-primary",
        "secondary": "btn-outline-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}

# ============================================
# EMAIL CONFIGURATION
# ============================================
# Email settings for OTP, notifications, and transactional emails
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="klikcell.com")
EMAIL_PORT = config("EMAIL_PORT", default=465, cast=int)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=True, cast=bool)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=False, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="info@klikcell.com")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="Kijangwani2003")
DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL", default="Kitonga WiFi <info@klikcell.com>"
)
SERVER_EMAIL = config("SERVER_EMAIL", default="info@klikcell.com")

# Contact form recipient email
CONTACT_EMAIL = config("CONTACT_EMAIL", default="info@klikcell.com")

# Email timeout settings
EMAIL_TIMEOUT = 30  # seconds


# CRONTAB CONFIGURATION FOR SCHEDULED TASKS
# ============================================
# These tasks run automatically at scheduled intervals
# Run 'python manage.py crontab add' to install cron jobs
# Run 'python manage.py crontab show' to list active cron jobs
# Run 'python manage.py crontab remove' to uninstall cron jobs

CRONJOBS = [
    # Disconnect expired users every 5 minutes
    # This removes MikroTik sessions, IP bindings, and deactivates users whose access has expired
    (
        "*/5 * * * *",
        "billing.tasks.disconnect_expired_users",
        ">> /var/log/kitonga_cron.log 2>&1",
    ),
    # Send expiry notifications every hour
    # Notifies users 1 hour before their access expires
    (
        "0 * * * *",
        "billing.tasks.send_expiry_notifications",
        ">> /var/log/kitonga_cron.log 2>&1",
    ),
    # Cleanup inactive devices daily at 3 AM
    # Deactivates devices that haven't been seen in 30 days
    (
        "0 3 * * *",
        "billing.tasks.cleanup_inactive_devices",
        ">> /var/log/kitonga_cron.log 2>&1",
    ),
    # PPP: Disconnect expired PPPoE customers every 5 minutes
    # Disables secret on MikroTik, kicks active session, sets status to 'expired'
    (
        "*/5 * * * *",
        "billing.tasks.disconnect_expired_ppp_customers",
        ">> /var/log/kitonga_cron.log 2>&1",
    ),
    # PPP: Send expiry warning SMS every hour
    # Warns PPP customers 24h and 3h before their subscription expires
    (
        "0 * * * *",
        "billing.tasks.send_ppp_expiry_notifications",
        ">> /var/log/kitonga_cron.log 2>&1",
    ),
]

# For development/testing, you can also manually run:
# python manage.py disconnect_expired_users
# python manage.py send_expiry_notifications

# Development Configuration Summary (for debugging)
if DEBUG:
    print("=" * 50)
    print("🔧 DEVELOPMENT MODE DETECTED")
    print("=" * 50)
    print(f"DEBUG: {DEBUG}")
    print(f"SECURE_SSL_REDIRECT: {globals().get('SECURE_SSL_REDIRECT', 'Not Set')}")
    print(f"SESSION_COOKIE_SECURE: {globals().get('SESSION_COOKIE_SECURE', 'Not Set')}")
    print(f"CSRF_COOKIE_SECURE: {globals().get('CSRF_COOKIE_SECURE', 'Not Set')}")
    print(
        f"CORS_ALLOW_ALL_ORIGINS: {globals().get('CORS_ALLOW_ALL_ORIGINS', 'Not Set')}"
    )
    print(f"ALLOWED_HOSTS: {ALLOWED_HOSTS}")
    print("🚀 Server should accept HTTP requests on:")
    print("   - http://localhost:8000")
    print("   - http://127.0.0.1:8000")
    print("⚠️  Do NOT use HTTPS URLs in development!")
    print("=" * 50)
