#!/bin/bash
# Quick transition from shared hosting to VPS
# Removes mock mode and configures real MikroTik connection

set -e

echo "🔄 Transitioning from Shared Hosting to VPS Configuration"
echo "======================================================="

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found in current directory"
    echo "Please run this script from your project root directory"
    exit 1
fi

# Backup original .env
echo "📋 Creating backup of current .env file..."
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
echo "✅ Backup created"

# Remove or disable mock mode
echo "🔧 Disabling MIKROTIK_MOCK_MODE..."

# Check if MIKROTIK_MOCK_MODE exists and remove/disable it
if grep -q "MIKROTIK_MOCK_MODE=true" .env; then
    # Replace true with false
    sed -i.bak 's/MIKROTIK_MOCK_MODE=true/MIKROTIK_MOCK_MODE=false/g' .env
    echo "✅ Changed MIKROTIK_MOCK_MODE from true to false"
elif grep -q "MIKROTIK_MOCK_MODE=false" .env; then
    echo "✅ MIKROTIK_MOCK_MODE already set to false"
elif grep -q "MIKROTIK_MOCK_MODE" .env; then
    # Comment out the line
    sed -i.bak 's/^MIKROTIK_MOCK_MODE/#MIKROTIK_MOCK_MODE/g' .env
    echo "✅ Commented out MIKROTIK_MOCK_MODE line"
else
    echo "ℹ️  MIKROTIK_MOCK_MODE not found in .env (this is good for VPS)"
fi

# Update MikroTik configuration for VPS
echo "⚙️  Updating MikroTik configuration for VPS..."

# Function to update or add environment variable
update_env_var() {
    local key=$1
    local value=$2
    
    if grep -q "^${key}=" .env; then
        # Update existing
        sed -i.bak "s/^${key}=.*/${key}=${value}/g" .env
        echo "✅ Updated ${key}"
    else
        # Add new
        echo "${key}=${value}" >> .env
        echo "✅ Added ${key}"
    fi
}

# Update MikroTik settings for VPS (with VPN IP)
echo "🔧 Updating MikroTik connection settings..."
update_env_var "MIKROTIK_HOST" "10.10.0.1"
update_env_var "MIKROTIK_PORT" "8728"
update_env_var "MIKROTIK_USER" "admin"
update_env_var "MIKROTIK_USE_SSL" "False"
update_env_var "MIKROTIK_DEFAULT_PROFILE" "default"

# Ensure mock mode is disabled
echo "# VPS Configuration - Mock mode disabled for full router control" >> .env
echo "MIKROTIK_MOCK_MODE=false" >> .env

# Update other VPS-specific settings
echo "🌐 Adding VPS-specific configurations..."

# Get current server IP
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "your-vps-ip")

# Update allowed hosts if needed
if ! grep -q "ALLOWED_HOSTS" .env; then
    echo "ALLOWED_HOSTS=localhost,127.0.0.1,${SERVER_IP},your-domain.com" >> .env
    echo "✅ Added ALLOWED_HOSTS"
fi

# Ensure DEBUG is False for production
update_env_var "DEBUG" "False"

# Add CORS settings for frontend
if ! grep -q "CORS_ALLOWED_ORIGINS" .env; then
    echo "CORS_ALLOWED_ORIGINS=https://your-domain.com" >> .env
    echo "✅ Added CORS_ALLOWED_ORIGINS (update with your domain)"
fi

if ! grep -q "CSRF_TRUSTED_ORIGINS" .env; then
    echo "CSRF_TRUSTED_ORIGINS=https://your-domain.com" >> .env
    echo "✅ Added CSRF_TRUSTED_ORIGINS (update with your domain)"
fi

echo
echo "✅ Configuration update complete!"
echo
echo "📋 CHANGES MADE:"
echo "=================="
echo "✅ Disabled MIKROTIK_MOCK_MODE"
echo "✅ Updated MIKROTIK_HOST to VPN IP (10.10.0.1)"
echo "✅ Configured MikroTik connection settings for VPS"
echo "✅ Set DEBUG=False for production"
echo "✅ Added VPS-specific settings"
echo
echo "⚠️  IMPORTANT NEXT STEPS:"
echo "========================"
echo "1. 🔧 Setup WireGuard VPN connection to your router"
echo "2. 📝 Update MIKROTIK_PASSWORD in .env with your actual router password"
echo "3. 🌐 Replace 'your-domain.com' with your actual domain in CORS/CSRF settings"
echo "4. 🧪 Test connection: python manage.py shell -c \"from billing.mikrotik import test_mikrotik_connection; print(test_mikrotik_connection())\""
echo "5. 🔄 Restart your application"
echo
echo "📖 For detailed setup instructions, see: VPS_MIKROTIK_SETUP_GUIDE.md"
echo
echo "🚀 Your system is now configured for full VPS control!"

# Show current MikroTik related settings
echo
echo "📊 CURRENT MIKROTIK SETTINGS:"
echo "=============================="
grep -E "MIKROTIK_|MOCK_MODE" .env | grep -v "^#" | head -10
