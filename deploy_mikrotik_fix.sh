#!/bin/bash
# Deploy fixes to production server

echo "======================================================================"
echo "🚀 Production MikroTik Fix Deployment"
echo "======================================================================"
echo ""

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    echo "❌ Error: Must run from project root (where manage.py is)"
    exit 1
fi

echo "📝 Summary of changes:"
echo "  ✅ Fixed 6 functions in billing/mikrotik.py (variable scope bugs)"
echo "  ✅ Added MIKROTIK_MOCK_MODE support"
echo "  ✅ Updated routeros-api to 0.21.0"
echo ""

echo "======================================================================"
echo "Step 1: Commit Changes"
echo "======================================================================"
read -p "Commit and push changes to git? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git add billing/mikrotik.py requirements.txt
    git add PRODUCTION_*.md fix_production_mikrotik.sh
    git commit -m "Fix MikroTik production connection issues

- Fixed variable scope bugs in 6 mikrotik.py functions
- Added MIKROTIK_MOCK_MODE environment variable support
- Updated routeros-api to 0.21.0
- Added production deployment documentation"
    
    git push origin main
    echo "✅ Changes pushed to repository"
else
    echo "⏭️  Skipping git commit"
fi

echo ""
echo "======================================================================"
echo "Step 2: Production Deployment"
echo "======================================================================"
echo ""
echo "On your production server, run:"
echo ""
echo "# Pull latest code"
echo "cd /path/to/your/project"
echo "git pull origin main"
echo ""
echo "# Install updated dependencies"
echo "pip install -r requirements.txt"
echo ""
echo "# Add to .env file"
echo "echo 'MIKROTIK_MOCK_MODE=true' >> .env"
echo ""
echo "# Restart application"
echo "sudo systemctl restart gunicorn"
echo "# OR"
echo "sudo supervisorctl restart kitonga"
echo "# OR"
echo "docker-compose restart"
echo ""
echo "======================================================================"
echo "Step 3: Verify Deployment"
echo "======================================================================"
echo ""
echo "Test API endpoint:"
echo ""
echo "curl -X GET https://api.kitonga.klikcell.com/api/admin/mikrotik/profiles/ \\"
echo "  -H 'X-Admin-Access: kitonga_admin_2025'"
echo ""
echo "Expected response:"
echo '{"success": false, "message": "MikroTik router not accessible in this environment"}'
echo ""
echo "======================================================================"
echo "Next Steps"
echo "======================================================================"
echo ""
echo "1. ✅ Immediate fix applied (Mock Mode)"
echo "2. 📖 Read: PRODUCTION_MIKROTIK_SETUP_GUIDE.md"
echo "3. 🔧 Setup VPN for permanent solution"
echo ""
echo "======================================================================"
