"""
Local test server using SQLite (no MySQL needed).
Usage: python run_local.py
"""
import os
import sys
import django
from django.conf import settings

os.environ['DJANGO_SETTINGS_MODULE'] = 'kitonga.settings'
os.environ['DEBUG'] = 'True'

# Must override BEFORE django.setup()
from decouple import config
# Temporarily patch settings after import
import kitonga.settings as s
s.DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(os.path.dirname(__file__), 'test_db.sqlite3'),
    }
}

django.setup()

from django.core.management import call_command

if __name__ == '__main__':
    # Run migrations first
    print("🔄 Running migrations...")
    call_command('migrate', verbosity=1)
    print("✅ Database ready!")
    print("")
    
    # Start server
    call_command('runserver', '0.0.0.0:8000')
