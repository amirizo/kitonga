#!/bin/bash

# Test MikroTik Logout Fix
# This script tests the logout endpoint with the phone number you mentioned

echo "🔍 Testing MikroTik Logout Fix for 400 Error"
echo "=============================================="
echo ""

API_BASE="https://api.kitonga.klikcell.com/api"
TEST_PHONE="0772236727"
TEST_IP="10.5.50.200"
TEST_MAC="AA:BB:CC:DD:EE:99"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Testing Phone Number: $TEST_PHONE${NC}"
echo ""

# Function to test logout with different parameters
test_logout() {
    local data="$1"
    local description="$2"
    
    echo -e "${YELLOW}Testing: $description${NC}"
    echo "Data: $data"
    echo "URL: $API_BASE/mikrotik/logout/"
    
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "$API_BASE/mikrotik/logout/" \
        -H "Content-Type: application/json" \
        -d "$data")
    
    http_code=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    echo "HTTP Status: $http_code"
    echo "Response: $body"
    
    if [ "$http_code" -eq 200 ]; then
        echo -e "${GREEN}✅ SUCCESS - Logout works!${NC}"
        return 0
    elif [ "$http_code" -eq 400 ]; then
        echo -e "${RED}❌ BAD REQUEST (400) - Still broken${NC}"
        return 1
    else
        echo -e "${YELLOW}⚠️ UNEXPECTED STATUS: $http_code${NC}"
        return 2
    fi
    
    echo ""
}

# Test 1: Basic username only
echo "1️⃣ Test 1: Username only"
test_logout "{\"username\":\"$TEST_PHONE\"}" "Basic username parameter"
echo ""

# Test 2: Username + IP
echo "2️⃣ Test 2: Username + IP"
test_logout "{\"username\":\"$TEST_PHONE\",\"ip\":\"$TEST_IP\"}" "Username with IP"
echo ""

# Test 3: Username + ip_address
echo "3️⃣ Test 3: Username + ip_address"
test_logout "{\"username\":\"$TEST_PHONE\",\"ip_address\":\"$TEST_IP\"}" "Username with ip_address field"
echo ""

# Test 4: All parameters
echo "4️⃣ Test 4: All parameters"
test_logout "{\"username\":\"$TEST_PHONE\",\"ip\":\"$TEST_IP\",\"mac\":\"$TEST_MAC\"}" "All parameters"
echo ""

# Test 5: Missing username (should fail)
echo "5️⃣ Test 5: Missing username (should return 400)"
test_logout "{\"ip\":\"$TEST_IP\"}" "Missing username - expected failure"
echo ""

# Test 6: Empty object (should fail)
echo "6️⃣ Test 6: Empty object (should return 400)"
test_logout "{}" "Empty object - expected failure"
echo ""

echo -e "${BLUE}=== Testing Complete ===${NC}"
echo ""
echo "If tests 1-4 show ✅ SUCCESS, the logout bug is fixed!"
echo "If tests 1-4 show ❌ BAD REQUEST, there are still issues."
echo ""
echo "Next, let's test the complete user flow:"
echo ""

# Test complete user authentication flow
echo -e "${YELLOW}🔍 Testing Complete User Flow${NC}"
echo ""

# Test authentication
echo "Testing MikroTik Auth:"
auth_response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "$API_BASE/mikrotik/auth/" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$TEST_PHONE\",\"password\":\"$TEST_PHONE\",\"mac\":\"$TEST_MAC\",\"ip\":\"$TEST_IP\"}")

auth_code=$(echo "$auth_response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
auth_body=$(echo "$auth_response" | sed -E 's/HTTPSTATUS:[0-9]*$//')

echo "Auth Status: $auth_code"
echo "Auth Response: $auth_body"

if [ "$auth_code" -eq 200 ]; then
    echo -e "${GREEN}✅ Authentication successful${NC}"
elif [ "$auth_code" -eq 403 ]; then
    echo -e "${YELLOW}🚫 Authentication denied - user needs to pay${NC}"
else
    echo -e "${RED}❌ Authentication error: $auth_code${NC}"
fi

echo ""

# Test user status
echo "Testing User Status:"
status_response=$(curl -s -w "HTTPSTATUS:%{http_code}" "$API_BASE/user-status/$TEST_PHONE/")
status_code=$(echo "$status_response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
status_body=$(echo "$status_response" | sed -E 's/HTTPSTATUS:[0-9]*$//')

echo "Status Code: $status_code"
echo "Status Response: $status_body"

echo ""
echo -e "${GREEN}=== All Tests Completed ===${NC}"
