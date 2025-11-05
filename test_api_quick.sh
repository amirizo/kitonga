#!/bin/bash

# Quick API Tests for Kitonga WiFi Billing System
# Simple curl-based tests for all major endpoints

BASE_URL="http://127.0.0.1:8000/api"
PHONE="255772236727"
MAC="AA:BB:CC:DD:EE:FF"
IP="192.168.0.100"

echo "🧪 Kitonga API Quick Test Suite"
echo "==============================="
echo "Base URL: $BASE_URL"
echo "Test Phone: $PHONE"
echo ""

# Function to test an endpoint
test_endpoint() {
    local method=$1
    local endpoint=$2
    local data=$3
    local description=$4
    
    echo "🔍 Testing: $description"
    echo "   Method: $method"
    echo "   Endpoint: $endpoint"
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X GET "$BASE_URL$endpoint" \
                   -H "Content-Type: application/json")
    else
        response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "$BASE_URL$endpoint" \
                   -H "Content-Type: application/json" \
                   -d "$data")
    fi
    
    http_code=$(echo $response | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    body=$(echo $response | sed -e 's/HTTPSTATUS\:.*//g')
    
    if [ "$http_code" -lt 500 ]; then
        echo "   ✅ Status: $http_code"
    else
        echo "   ❌ Status: $http_code"
    fi
    
    echo "   Response: $(echo $body | head -c 100)..."
    echo ""
}

# Test 1: Health Check
test_endpoint "GET" "/health/" "" "System Health Check"

# Test 2: List Bundles
test_endpoint "GET" "/bundles/" "" "List Available Bundles"

# Test 3: Verify Access
test_endpoint "POST" "/verify/" "{\"phone_number\":\"$PHONE\"}" "Verify User Access"

# Test 4: User Status
test_endpoint "GET" "/user-status/$PHONE/" "" "Check User Status"

# Test 5: MikroTik Auth
test_endpoint "POST" "/mikrotik/auth/" "{\"username\":\"$PHONE\",\"mac\":\"$MAC\",\"ip\":\"$IP\"}" "MikroTik Authentication"

# Test 6: MikroTik Status
test_endpoint "GET" "/mikrotik/status/" "" "MikroTik Status Check"

# Test 7: List User Devices
test_endpoint "GET" "/devices/$PHONE/" "" "List User Devices"

# Test 8: Dashboard Stats (Admin)
test_endpoint "GET" "/dashboard-stats/" "" "Dashboard Statistics"

# Test 9: System Status (Admin)
test_endpoint "GET" "/admin/status/" "" "System Status"

# Test 10: Admin Login
test_endpoint "POST" "/auth/login/" "{\"username\":\"admin\",\"password\":\"admin123\"}" "Admin Login"

echo "🏁 Quick test suite completed!"
echo ""
echo "📝 Notes:"
echo "   - ✅ Status codes 200-499 are considered successful"
echo "   - ❌ Status codes 500+ indicate server errors"
echo "   - Some endpoints require authentication"
echo "   - Check Django server logs for detailed errors"
