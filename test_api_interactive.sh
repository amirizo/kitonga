#!/bin/bash

# Kitonga API Testing Script
# Quick and easy way to test all API endpoints

echo "🚀 Kitonga WiFi Billing System - API Testing"
echo "============================================="

# Check if server is running
echo "📡 Checking if Django server is running..."
if curl -s http://127.0.0.1:8000/api/health/ > /dev/null; then
    echo "✅ Server is running"
else
    echo "❌ Server is not running. Please start it with:"
    echo "   python manage.py runserver"
    exit 1
fi

echo ""
echo "🧪 Available Test Options:"
echo "=========================="
echo "1. Run comprehensive Python test suite (recommended)"
echo "2. Quick health check"
echo "3. Test authentication endpoints"
echo "4. Test user access flow"
echo "5. Test MikroTik integration"
echo "6. Test admin endpoints"
echo "7. Custom endpoint test"
echo ""

read -p "Choose an option (1-7): " choice

case $choice in
    1)
        echo "🔄 Running comprehensive test suite..."
        python3 test_all_api_urls.py
        ;;
    2)
        echo "🔍 Quick health check..."
        curl -X GET http://127.0.0.1:8000/api/health/ \
             -H "Content-Type: application/json" | jq .
        ;;
    3)
        echo "🔐 Testing authentication endpoints..."
        echo "Login attempt:"
        curl -X POST http://127.0.0.1:8000/api/auth/login/ \
             -H "Content-Type: application/json" \
             -d '{"username":"admin","password":"admin123"}' | jq .
        ;;
    4)
        echo "👤 Testing user access flow..."
        read -p "Enter phone number (default: 255772236727): " phone
        phone=${phone:-255772236727}
        
        echo "Verifying access for $phone..."
        curl -X POST http://127.0.0.1:8000/api/verify/ \
             -H "Content-Type: application/json" \
             -d "{\"phone_number\":\"$phone\"}" | jq .
        
        echo ""
        echo "Checking user status..."
        curl -X GET http://127.0.0.1:8000/api/user-status/$phone/ \
             -H "Content-Type: application/json" | jq .
        ;;
    5)
        echo "📡 Testing MikroTik integration..."
        read -p "Enter phone number (default: 255772236727): " phone
        phone=${phone:-255772236727}
        
        echo "MikroTik authentication for $phone..."
        curl -X POST http://127.0.0.1:8000/api/mikrotik/auth/ \
             -H "Content-Type: application/json" \
             -d "{\"username\":\"$phone\",\"mac\":\"AA:BB:CC:DD:EE:FF\",\"ip\":\"192.168.0.100\"}" | jq .
        
        echo ""
        echo "MikroTik status check..."
        curl -X GET http://127.0.0.1:8000/api/mikrotik/status/ \
             -H "Content-Type: application/json" | jq .
        ;;
    6)
        echo "🛡️ Testing admin endpoints..."
        echo "Note: These require admin authentication"
        
        echo "Dashboard stats:"
        curl -X GET http://127.0.0.1:8000/api/dashboard-stats/ \
             -H "Content-Type: application/json" | jq .
        
        echo ""
        echo "System status:"
        curl -X GET http://127.0.0.1:8000/api/admin/status/ \
             -H "Content-Type: application/json" | jq .
        ;;
    7)
        echo "🎯 Custom endpoint test"
        read -p "Enter endpoint path (e.g., /bundles/): " endpoint
        read -p "Enter HTTP method (GET/POST): " method
        
        if [ "$method" = "POST" ]; then
            read -p "Enter JSON data (or press Enter for empty): " data
            if [ -n "$data" ]; then
                curl -X POST http://127.0.0.1:8000/api$endpoint \
                     -H "Content-Type: application/json" \
                     -d "$data" | jq .
            else
                curl -X POST http://127.0.0.1:8000/api$endpoint \
                     -H "Content-Type: application/json" | jq .
            fi
        else
            curl -X GET http://127.0.0.1:8000/api$endpoint \
                 -H "Content-Type: application/json" | jq .
        fi
        ;;
    *)
        echo "❌ Invalid option. Please choose 1-7."
        ;;
esac

echo ""
echo "✅ Test completed!"
echo ""
echo "💡 Tips:"
echo "   - Run option 1 for comprehensive testing"
echo "   - Check Django logs for detailed error information"
echo "   - Ensure test data exists in your database"
echo "   - Some endpoints require admin authentication"
