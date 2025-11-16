#!/bin/bash

# Fixed Environment Update Script for VPS
# This script safely handles special characters in environment variables

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[✅]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[⚠️]${NC} $1"
}

print_error() {
    echo -e "${RED}[❌]${NC} $1"
}

# Function to safely update environment variables (handles special characters)
safe_update_env_var() {
    local key=$1
    local value=$2
    local env_file=".env"
    
    # Escape special characters for sed
    local escaped_value=$(printf '%s\n' "$value" | sed 's/[[\.*^$()+?{|]/\\&/g')
    
    if grep -q "^${key}=" "$env_file" 2>/dev/null; then
        # Use a different delimiter for sed to avoid conflicts
        sed -i "s|^${key}=.*|${key}=${escaped_value}|" "$env_file"
        print_status "Updated ${key}"
    else
        echo "${key}=${value}" >> "$env_file"
        print_status "Added ${key}"
    fi
}

# Alternative method using Python for complex values
python_update_env() {
    python3 -c "
import os
import re

env_file = '.env'
key = '$1'
value = '$2'

# Read current content
try:
    with open(env_file, 'r') as f:
        content = f.read()
except FileNotFoundError:
    content = ''

# Update or add the key
pattern = f'^{re.escape(key)}=.*$'
new_line = f'{key}={value}'

if re.search(pattern, content, re.MULTILINE):
    content = re.sub(pattern, new_line, content, flags=re.MULTILINE)
else:
    if content and not content.endswith('\n'):
        content += '\n'
    content += new_line + '\n'

# Write back
with open(env_file, 'w') as f:
    f.write(content)

print(f'Updated {key}')
"
}

echo "🔧 Fixing VPS Environment Configuration"
echo "======================================"

# Change to project directory
cd /var/www/kitonga

# Check if .env exists
if [ ! -f .env ]; then
    print_error ".env file not found!"
    exit 1
fi

print_status "Found .env file"

# Backup current .env
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
print_status "Created backup of .env file"

# Fix the MIKROTIK_MOCK_MODE setting (this should work fine)
if grep -q "MIKROTIK_MOCK_MODE=true" .env 2>/dev/null; then
    sed -i 's/MIKROTIK_MOCK_MODE=true/MIKROTIK_MOCK_MODE=false/' .env
    print_status "Disabled MIKROTIK_MOCK_MODE"
fi

# Update router IP to use WireGuard tunnel IP if available
if ip route | grep -q "10.10.0."; then
    print_status "WireGuard tunnel detected, using tunnel IP"
    python_update_env "MIKROTIK_HOST" "10.10.0.1"
else
    print_status "Using direct router connection"
    python_update_env "MIKROTIK_HOST" "192.168.0.173"
fi

# Update other critical settings using Python method for safety
python_update_env "MIKROTIK_PORT" "8728"
python_update_env "MIKROTIK_USER" "admin"
python_update_env "MIKROTIK_MOCK_MODE" "false"
python_update_env "DEBUG" "False"
python_update_env "ALLOWED_HOSTS" "api.kitonga.klikcell.com,kitonga.klikcell.com,66.29.143.116,localhost,127.0.0.1"
python_update_env "CORS_ALLOWED_ORIGINS" "https://kitonga.klikcell.com,https://api.kitonga.klikcell.com"
python_update_env "CSRF_TRUSTED_ORIGINS" "https://kitonga.klikcell.com,https://api.kitonga.klikcell.com"

print_status "Environment configuration completed successfully!"

echo ""
echo "🧪 Testing Configuration"
echo "======================"

# Test router connectivity
print_status "Testing router connectivity..."
if nc -zv 192.168.0.173 8728 2>/dev/null; then
    print_status "✅ Router connection successful!"
else
    print_warning "⚠️ Direct router connection failed - checking WireGuard tunnel..."
    if nc -zv 10.10.0.1 8728 2>/dev/null; then
        print_status "✅ Router connection via WireGuard tunnel successful!"
    else
        print_error "❌ Router connection failed on both direct and tunnel IPs"
    fi
fi

# Test Django settings loading
print_status "Testing Django environment loading..."
if python3 manage.py shell -c "
from django.conf import settings
print('MIKROTIK_MOCK_MODE:', getattr(settings, 'MIKROTIK_MOCK_MODE', 'Not set'))
print('MIKROTIK_HOST:', getattr(settings, 'MIKROTIK_HOST', 'Not set'))
print('DEBUG:', settings.DEBUG)
" 2>/dev/null; then
    print_status "✅ Django settings loaded successfully!"
else
    print_warning "⚠️ Django settings test failed - check dependencies"
fi

echo ""
echo "🎉 VPS Environment Fix Complete!"
echo "==============================="
echo "Next steps:"
echo "1. Install Python dependencies: pip install -r requirements.txt"
echo "2. Run migrations: python manage.py migrate"
echo "3. Collect static files: python manage.py collectstatic --noinput"
echo "4. Restart your web server"
echo "5. Test API endpoints"
