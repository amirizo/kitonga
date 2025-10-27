"""
Django settings for Kitonga Wi-Fi Billing System
"""

from pathlib import Path
from decouple import config, Csv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-kitonga-dev-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,api.kitonga.klikcell.com,kitonga.klikcell.com', cast=Csv())

# Application definition
INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'billing',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'kitonga.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'kitonga.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Dar_es_Salaam'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise configuration for static files in production
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Additional WhiteNoise settings for optimal performance
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = DEBUG  # Only in development
WHITENOISE_MANIFEST_STRICT = False  # More forgiving in production
WHITENOISE_SKIP_COMPRESS_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'zip', 'gz', 'tgz', 'bz2', 'tbz', 'xz', 'br']

# Static files configuration
STATICFILES_DIRS = []
if (BASE_DIR / 'static').exists():
    STATICFILES_DIRS.append(BASE_DIR / 'static')

# Media files configuration (for user uploads if needed)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Production Security Settings
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_REDIRECT_EXEMPT = []
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_TZ = True
    
    # Session security
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_PRELOAD = True
    
    # Additional production security
    X_FRAME_OPTIONS = 'DENY'
    SECURE_REFERRER_POLICY = 'same-origin'
    
# Production Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO' if DEBUG else 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'] if not DEBUG else ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'billing': {
            'handlers': ['console', 'file'] if not DEBUG else ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'EXCEPTION_HANDLER': 'rest_framework.views.exception_handler',
}

# CORS settings
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='https://kitonga.klikcell.com,https://api.kitonga.klikcell.com', cast=Csv())

# Allow specific headers for CORS
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-admin-access',  # Custom header for admin authentication
    'cache-control',   # For static file caching
    'expires',         # For static file caching
]

# Allow specific methods
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# Allow credentials (if needed for authentication)
CORS_ALLOW_CREDENTIALS = True

# ClickPesa Configuration
CLICKPESA_CLIENT_ID = config('CLICKPESA_CLIENT_ID', default='')
CLICKPESA_API_KEY = config('CLICKPESA_API_KEY', default='')
CLICKPESA_BASE_URL = config('CLICKPESA_BASE_URL', default='https://api.clickpesa.com')
CLICKPESA_WEBHOOK_URL = config('CLICKPESA_WEBHOOK_URL', default='')

# NEXTSMS Configuration
NEXTSMS_USERNAME = config('NEXTSMS_USERNAME', default='')
NEXTSMS_PASSWORD = config('NEXTSMS_PASSWORD', default='')
NEXTSMS_SENDER_ID = config('NEXTSMS_SENDER_ID', default='Klikcell')
NEXTSMS_BASE_URL = config('NEXTSMS_BASE_URL', default='https://messaging-service.co.tz')
IS_TEST_MODE = config('IS_TEST_MODE', default=False, cast=bool)

# NextSMS API URLs
NEXTSMS_TEST_URL = 'https://messaging-service.co.tz/api/sms/v1/test/text/single'
NEXTSMS_PROD_URL = 'https://messaging-service.co.tz/api/sms/v1/text/single'
NEXTSMS_API_URL = NEXTSMS_TEST_URL if IS_TEST_MODE else NEXTSMS_PROD_URL





# Wi-Fi Access Configuration
DAILY_ACCESS_PRICE = 1000  # TSh 1,000
ACCESS_DURATION_HOURS = 24

# Device Management
MAX_DEVICES_PER_USER = config('MAX_DEVICES_PER_USER', default=1, cast=int)

# Admin Authentication Token (for frontend API access)
SIMPLE_ADMIN_TOKEN = config('SIMPLE_ADMIN_TOKEN', default='kitonga_admin_2025')
ADMIN_TOKEN_SECRET = config('ADMIN_TOKEN_SECRET', default=SECRET_KEY)

# Mikrotik Router Configuration
MIKROTIK_ROUTER_IP = config('MIKROTIK_ROUTER_IP', default='192.168.0.173')
MIKROTIK_ADMIN_USER = config('MIKROTIK_ADMIN_USER', default='admin')
MIKROTIK_ADMIN_PASS = config('MIKROTIK_ADMIN_PASS', default='Kijangwani2003')
MIKROTIK_API_PORT = config('MIKROTIK_API_PORT', default=8728, cast=int)
MIKROTIK_HOTSPOT_NAME = config('MIKROTIK_HOTSPOT_NAME', default='kitonga-hotspot')

# Jazzmin Configuration
JAZZMIN_SETTINGS = {
    # Title of the window (Will default to current_admin_site.site_title if absent or None)
    "site_title": "Kitonga Wi-Fi Admin",

    # Title on the login screen (19 chars max) (defaults to current_admin_site.site_header if absent or None)
    "site_header": "Kitonga Wi-Fi",

    # Title on the brand (19 chars max) (defaults to current_admin_site.site_header if absent or None)
    "site_brand": "Kitonga Wi-Fi",

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
    "welcome_sign": "Welcome to Kitonga Wi-Fi Administration",

    # Copyright on the footer
    "copyright": "Kitonga Wi-Fi Management System",

    # List of model admins to search from the search bar, search bar omitted if excluded
    "search_model": ["auth.User", "billing.User", "billing.Payment"],

    # Field name on user model that contains avatar ImageField/URLField/Charfield or a callable that receives the user
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
        {"name": "Portal Home", "url": "https://kitonga.klikcell.com", "new_window": True},
        {"model": "auth.user"}
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
                "permissions": ["billing.view_payment"]
            }
        ]
    },

    # Custom icons for side menu apps/models See https://fontawesome.com/icons?d=gallery&m=free&v=5.0.0,5.0.1,5.0.10,5.0.11,5.0.12,5.0.13,5.0.2,5.0.3,5.0.4,5.0.5,5.0.6,5.0.7,5.0.8,5.0.9,5.1.0,5.1.1,5.2.0,5.3.0,5.3.1,5.4.0,5.4.1,5.4.2,5.5.0,5.6.0,5.6.1,5.6.3,5.7.0,5.7.1,5.7.2,5.8.0,5.8.1,5.8.2,5.9.0,5.10.0,5.10.1,5.10.2,5.11.0,5.11.1,5.11.2,5.12.0,5.12.1,5.13.0,5.13.1,5.14.0,5.15.0,5.15.1,5.15.2,5.15.3,5.15.4&s=solid
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "billing.User": "fas fa-wifi",
        "billing.Bundle": "fas fa-boxes",
        "billing.Payment": "fas fa-credit-card",
        "billing.Voucher": "fas fa-ticket-alt",
        "billing.Device": "fas fa-mobile-alt",
        "billing.AccessLog": "fas fa-history",
        "billing.SMSLog": "fas fa-sms",
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
    "changeform_format_overrides": {"auth.user": "collapsible", "auth.group": "vertical_tabs"},
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
        "success": "btn-success"
    }
}
