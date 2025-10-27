#!/bin/bash

# Production Test Suite for Kitonga Wi-Fi System
# Run this script after deployment to verify everything works

echo "=============================================="
echo "🚀 KITONGA WI-FI PRODUCTION TEST SUITE"
echo "=============================================="

# Configuration
API_URL="https://api.kitonga.klikcell.com/api"
FRONTEND_URL="https://kitonga.klikcell.com"
TEST_PHONE="255708374149"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
test_pass() {
    echo -e "${GREEN}✓ $1${NC}"
    ((TESTS_PASSED++))
}

test_fail() {
    echo -e "${RED}✗ $1${NC}"
    ((TESTS_FAILED++))
}

test_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Test 1: API Health Check
echo ""
echo "1. Testing API Health Check..."
HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/health/")
if [ "$HEALTH_RESPONSE" == "200" ]; then
    test_pass "API health check passed"
else
    test_fail "API health check failed (HTTP $HEALTH_RESPONSE)"
fi

# Test 2: Frontend Accessibility
echo ""
echo "2. Testing Frontend Accessibility..."
FRONTEND_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$FRONTEND_URL")
if [ "$FRONTEND_RESPONSE" == "200" ]; then
    test_pass "Frontend is accessible"
else
    test_fail "Frontend not accessible (HTTP $FRONTEND_RESPONSE)"
fi

# Test 3: SSL Certificate Check
echo ""
echo "3. Testing SSL Certificates..."
API_SSL=$(curl -s -I "$API_URL/health/" | grep -i "HTTP" | grep "200")
if [ ! -z "$API_SSL" ]; then
    test_pass "API SSL certificate valid"
else
    test_fail "API SSL certificate issues"
fi

FRONTEND_SSL=$(curl -s -I "$FRONTEND_URL" | grep -i "HTTP" | grep "200")
if [ ! -z "$FRONTEND_SSL" ]; then
    test_pass "Frontend SSL certificate valid"
else
    test_fail "Frontend SSL certificate issues"
fi

# Test 4: Database Connection
echo ""
echo "4. Testing Database Connection..."
DB_TEST=$(curl -s "$API_URL/health/" | grep -o '"database_connected":[^,]*' | grep "true")
if [ ! -z "$DB_TEST" ]; then
    test_pass "Database connection working"
else
    test_fail "Database connection failed"
fi

# Test 5: Bundle Listing
echo ""
echo "5. Testing Bundle API..."
BUNDLES_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/bundles/")
if [ "$BUNDLES_RESPONSE" == "200" ]; then
    test_pass "Bundle listing API working"
else
    test_fail "Bundle listing API failed (HTTP $BUNDLES_RESPONSE)"
fi

# Test 6: Mikrotik Authentication Endpoint
echo ""
echo "6. Testing Mikrotik Authentication..."
MIKROTIK_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/mikrotik/auth/" -d "username=$TEST_PHONE")
if [ "$MIKROTIK_RESPONSE" == "404" ] || [ "$MIKROTIK_RESPONSE" == "403" ]; then
    test_pass "Mikrotik auth endpoint responding (user not found/no bundle is expected)"
elif [ "$MIKROTIK_RESPONSE" == "200" ]; then
    test_pass "Mikrotik auth endpoint working (test user has access)"
else
    test_fail "Mikrotik auth endpoint failed (HTTP $MIKROTIK_RESPONSE)"
fi

# Test 7: Admin Login Endpoint
echo ""
echo "7. Testing Admin Login Endpoint..."
ADMIN_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/auth/login/" -H "Content-Type: application/json" -d '{"username":"test","password":"test"}')
if [ "$ADMIN_RESPONSE" == "401" ] || [ "$ADMIN_RESPONSE" == "400" ]; then
    test_pass "Admin login endpoint responding (invalid credentials expected)"
else
    test_warning "Admin login response: HTTP $ADMIN_RESPONSE"
fi

# Test 8: CORS Headers
echo ""
echo "8. Testing CORS Configuration..."
CORS_TEST=$(curl -s -H "Origin: https://kitonga.klikcell.com" -H "Access-Control-Request-Method: POST" -H "Access-Control-Request-Headers: X-Requested-With" -X OPTIONS "$API_URL/health/" -I | grep "Access-Control-Allow-Origin")
if [ ! -z "$CORS_TEST" ]; then
    test_pass "CORS headers configured"
else
    test_fail "CORS headers missing"
fi

# Test 9: Static Files
echo ""
echo "9. Testing Static Files..."
STATIC_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/static/admin/css/base.css")
if [ "$STATIC_RESPONSE" == "200" ]; then
    test_pass "Static files serving correctly"
else
    test_warning "Static files may not be configured (HTTP $STATIC_RESPONSE)"
fi

# Test 10: Payment Webhook Endpoint
echo ""
echo "10. Testing Payment Webhook..."
WEBHOOK_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/clickpesa-webhook/" -H "Content-Type: application/json" -d '{"test":"data"}')
if [ "$WEBHOOK_RESPONSE" == "400" ] || [ "$WEBHOOK_RESPONSE" == "200" ]; then
    test_pass "Payment webhook endpoint responding"
else
    test_fail "Payment webhook endpoint failed (HTTP $WEBHOOK_RESPONSE)"
fi

# Test 11: DNS Resolution
echo ""
echo "11. Testing DNS Resolution..."
API_DNS=$(nslookup api.kitonga.klikcell.com | grep "Address" | tail -1)
FRONTEND_DNS=$(nslookup kitonga.klikcell.com | grep "Address" | tail -1)

if [ ! -z "$API_DNS" ]; then
    test_pass "API DNS resolution working"
    echo "   API IP: $(echo $API_DNS | cut -d' ' -f2)"
else
    test_fail "API DNS resolution failed"
fi

if [ ! -z "$FRONTEND_DNS" ]; then
    test_pass "Frontend DNS resolution working"
    echo "   Frontend IP: $(echo $FRONTEND_DNS | cut -d' ' -f2)"
else
    test_fail "Frontend DNS resolution failed"
fi

# Test 12: Response Time
echo ""
echo "12. Testing Response Times..."
API_TIME=$(curl -o /dev/null -s -w "%{time_total}" "$API_URL/health/")
FRONTEND_TIME=$(curl -o /dev/null -s -w "%{time_total}" "$FRONTEND_URL")

if (( $(echo "$API_TIME < 2.0" | bc -l) )); then
    test_pass "API response time good (${API_TIME}s)"
else
    test_warning "API response time slow (${API_TIME}s)"
fi

if (( $(echo "$FRONTEND_TIME < 3.0" | bc -l) )); then
    test_pass "Frontend response time good (${FRONTEND_TIME}s)"
else
    test_warning "Frontend response time slow (${FRONTEND_TIME}s)"
fi

# Summary
echo ""
echo "=============================================="
echo "📊 TEST RESULTS SUMMARY"
echo "=============================================="
echo -e "${GREEN}Tests Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Tests Failed: $TESTS_FAILED${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo ""
    echo -e "${GREEN}🎉 ALL CRITICAL TESTS PASSED!${NC}"
    echo -e "${GREEN}✅ System is ready for production use${NC}"
    
    echo ""
    echo "Next Steps:"
    echo "1. Test with real payment using ClickPesa"
    echo "2. Send test SMS to verify NextSMS"
    echo "3. Connect to Wi-Fi hotspot and test authentication"
    echo "4. Configure monitoring and alerts"
    echo "5. Train staff on admin panel"
    
else
    echo ""
    echo -e "${RED}❌ Some tests failed. Please fix issues before going live.${NC}"
    echo ""
    echo "Common fixes:"
    echo "• Check server configuration"
    echo "• Verify SSL certificates"
    echo "• Check DNS propagation"
    echo "• Review application logs"
fi

echo ""
echo "=============================================="
echo "🔧 ADDITIONAL MANUAL TESTS NEEDED"
echo "=============================================="
echo "1. Admin Panel Access:"
echo "   → Visit: $API_URL/admin/"
echo "   → Login with superuser credentials"
echo ""
echo "2. Payment Flow:"
echo "   → Create test user"
echo "   → Purchase bundle via ClickPesa"
echo "   → Verify payment webhook receives data"
echo ""
echo "3. SMS Functionality:"
echo "   → Generate vouchers with SMS"
echo "   → Verify SMS delivery to real phone numbers"
echo ""
echo "4. Mikrotik Integration:"
echo "   → Connect device to Wi-Fi"
echo "   → Test authentication with valid user"
echo "   → Verify internet access granted"
echo ""
echo "5. Complete User Journey:"
echo "   → New user registration"
echo "   → Bundle purchase"
echo "   → SMS notification"
echo "   → Wi-Fi connection"
echo "   → Internet browsing"
echo ""
echo "=============================================="

# Exit with error code if tests failed
if [ $TESTS_FAILED -gt 0 ]; then
    exit 1
else
    exit 0
fi
