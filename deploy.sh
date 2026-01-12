#!/bin/bash
# ==============================================
# KITONGA WIFI - PRODUCTION DEPLOYMENT SCRIPT
# ==============================================
# Run this script on your VPS to deploy/update the application
# Usage: ./deploy.sh

set -e  # Exit on any error

echo "=========================================="
echo "  KITONGA WIFI - PRODUCTION DEPLOYMENT"
echo "=========================================="

# Configuration
APP_DIR="/var/www/kitonga"
VENV_DIR="$APP_DIR/venv"
PROJECT_DIR="$APP_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Step 1: Activate virtual environment
echo ""
echo "Step 1: Activating virtual environment..."
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
    print_status "Virtual environment activated"
else
    print_error "Virtual environment not found at $VENV_DIR"
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    print_status "Virtual environment created and activated"
fi

# Step 2: Install/Update dependencies
echo ""
echo "Step 2: Installing dependencies..."
cd "$PROJECT_DIR"
pip install --upgrade pip
pip install -r requirements.txt
print_status "Dependencies installed"

# Step 3: Run database migrations
echo ""
echo "Step 3: Running database migrations..."
python manage.py migrate --noinput
print_status "Database migrations complete"

# Step 4: Collect static files
echo ""
echo "Step 4: Collecting static files..."
python manage.py collectstatic --noinput
print_status "Static files collected"

# Step 5: Run deployment checks
echo ""
echo "Step 5: Running deployment checks..."
python manage.py check --deploy
print_status "Deployment checks passed"

# Step 6: Restart application server
echo ""
echo "Step 6: Restarting application..."

# For Passenger (cPanel/Plesk)
if [ -f "$PROJECT_DIR/tmp/restart.txt" ]; then
    touch "$PROJECT_DIR/tmp/restart.txt"
    print_status "Passenger restart triggered"
fi

# For systemd (if using gunicorn service)
if systemctl is-active --quiet kitonga; then
    sudo systemctl restart kitonga
    print_status "Gunicorn service restarted"
fi

# For supervisor (if using supervisorctl)
if command -v supervisorctl &> /dev/null; then
    supervisorctl restart kitonga 2>/dev/null || true
fi

echo ""
echo "=========================================="
echo "  DEPLOYMENT COMPLETE!"
echo "=========================================="
echo ""
echo "Your application should now be running at:"
echo "  - API: https://api.kitonga.klikcell.com"
echo "  - Frontend: https://kitonga.klikcell.com"
echo ""
echo "To check logs:"
echo "  - tail -f $PROJECT_DIR/logs/django.log"
echo ""
