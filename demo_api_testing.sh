#!/bin/bash

# Demo script to show all testing options
# Run this to see what testing tools are available

echo "🎯 Kitonga API Testing Demo"
echo "=========================="
echo ""

echo "📁 Available Test Files:"
echo "├── 🆕 test_all_api_urls.py         - Complete endpoint testing (RECOMMENDED)"
echo "├── 🆕 test_api_interactive.sh      - Interactive menu-driven testing"
echo "├── 🆕 test_api_quick.sh            - Quick health check"
echo "├── 📋 comprehensive_api_test.py    - Existing comprehensive test"
echo "└── 📖 COMPLETE_API_TESTING_GUIDE.md - Full documentation"
echo ""

echo "🚀 Quick Start Commands:"
echo ""

echo "1️⃣  Full comprehensive test (recommended):"
echo "   python3 test_all_api_urls.py"
echo ""

echo "2️⃣  Interactive testing menu:"
echo "   ./test_api_interactive.sh"
echo ""

echo "3️⃣  Quick health check:"
echo "   ./test_api_quick.sh"
echo ""

echo "4️⃣  Legacy comprehensive test:"
echo "   python3 comprehensive_api_test.py"
echo ""

echo "📊 Your URLs file contains these endpoint categories:"
echo "├── Authentication (5 endpoints)"
echo "├── Wi-Fi Access (8 endpoints)"
echo "├── Vouchers (4 endpoints)"
echo "├── Admin (4 endpoints)"
echo "├── User Management (6 endpoints)"
echo "├── Payment Management (6 endpoints)"
echo "├── Bundle Management (3 endpoints)"
echo "├── System (3 endpoints)"
echo "├── MikroTik Integration (5 endpoints)"
echo "└── MikroTik Admin (10 endpoints)"
echo ""
echo "💡 Total: 54+ unique endpoints ready for testing!"
echo ""

echo "⚡ To start testing right now:"
echo ""
if curl -s http://127.0.0.1:8000/api/health/ > /dev/null 2>&1; then
    echo "✅ Django server is running - you can start testing!"
    echo ""
    echo "Try this quick test:"
    echo "curl -X GET http://127.0.0.1:8000/api/health/ | jq ."
    echo ""
else
    echo "❌ Django server is not running. Start it first:"
    echo "python manage.py runserver"
    echo ""
fi

echo "📖 For detailed instructions, see: COMPLETE_API_TESTING_GUIDE.md"
echo ""
echo "🎉 Happy testing!"
