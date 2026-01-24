#!/bin/bash

# Quick setup script for Kitonga WiFi task scheduling
# Run with: bash setup_tasks.sh

echo "=========================================="
echo "🚀 KITONGA WIFI TASK SETUP"
echo "=========================================="
echo ""

# Get the current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
KITONGA_DIR="$SCRIPT_DIR"

echo "Kitonga directory: $KITONGA_DIR"
echo ""

# Check if venv exists
if [ ! -d "$KITONGA_DIR/venv" ]; then
    echo "❌ Virtual environment not found at $KITONGA_DIR/venv"
    echo "Please create it first: python3 -m venv venv"
    exit 1
fi

PYTHON_PATH="$KITONGA_DIR/venv/bin/python"
MANAGE_PY="$KITONGA_DIR/manage.py"

echo "✅ Found Python: $PYTHON_PATH"
echo ""

# Test if management commands work
echo "Testing management commands..."
if ! $PYTHON_PATH $MANAGE_PY check_task_status &> /dev/null; then
    echo "⚠️  check_task_status command not working, but continuing..."
fi

# Create cron entries
CRON_ENTRIES="
# Kitonga WiFi Background Tasks
# CRITICAL: Disconnect expired users every 5 minutes
*/5 * * * * cd $KITONGA_DIR && $PYTHON_PATH $MANAGE_PY disconnect_expired_users >> $KITONGA_DIR/logs/cron.log 2>&1

# Send expiry notifications hourly
0 * * * * cd $KITONGA_DIR && $PYTHON_PATH $MANAGE_PY send_expiry_notifications >> $KITONGA_DIR/logs/cron.log 2>&1

# Clean up old devices daily at 3 AM
0 3 * * * cd $KITONGA_DIR && $PYTHON_PATH $MANAGE_PY cleanup_inactive_devices >> $KITONGA_DIR/logs/cron.log 2>&1
"

echo "=========================================="
echo "CRON ENTRIES TO ADD:"
echo "=========================================="
echo "$CRON_ENTRIES"
echo ""

# Ask user if they want to add to crontab
read -p "Do you want to add these to your crontab now? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Backup current crontab
    crontab -l > /tmp/crontab_backup_$(date +%Y%m%d_%H%M%S).txt 2>/dev/null || true
    
    # Add to crontab
    (crontab -l 2>/dev/null; echo "$CRON_ENTRIES") | crontab -
    
    echo "✅ Cron jobs added successfully!"
    echo ""
    echo "Current crontab:"
    crontab -l | grep -A 10 "Kitonga WiFi"
else
    echo ""
    echo "⚠️  Cron jobs NOT added."
    echo "To add manually, run: crontab -e"
    echo "Then paste the entries shown above."
fi

echo ""
echo "=========================================="
echo "✅ NEXT STEPS:"
echo "=========================================="
echo ""
echo "1. Run status check:"
echo "   python manage.py check_task_status"
echo ""
echo "2. Test disconnect manually:"
echo "   python manage.py disconnect_expired_users"
echo ""
echo "3. Check logs:"
echo "   tail -f logs/django.log"
echo "   tail -f logs/cron.log"
echo ""
echo "4. Verify cron is working:"
echo "   Wait 5 minutes and check logs/cron.log"
echo ""
echo "=========================================="
echo "📚 Full documentation: docs/TASK_SCHEDULING_SETUP.md"
echo "=========================================="
