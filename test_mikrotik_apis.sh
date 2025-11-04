#!/bin/bash

# MikroTik API Testing Script
# Tests captive portal integration endpoints

echo "🔍 MikroTik Captive Portal API Testing"
echo "========================================="
echo ""

# Configuration
API_BASE="http://127.0.0.1:8000/api"
TEST_PHONE="0772236727"
TEST_MAC="AA:BB:CC:DD:EE:99"
TEST_IP="10.5.50.200"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

function test_endpoint() {
    local method=$1
    local endpoint=$2
    local data=$3
    local description=$4
    
    echo -e "${BLUE}Testing: $description${NC}"
    echo "Endpoint: $method $endpoint"
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "HTTPSTATUS:%{http_code}" "$endpoint")
    else
        response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X "$method" "$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi
    
    # Extract HTTP status and body
    http_code=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    echo "HTTP Status: $http_code"
    
    if [ "$http_code" -eq 200 ]; then
        echo -e "${GREEN}✅ SUCCESS${NC}"
    elif [ "$http_code" -eq 403 ]; then
        echo -e "${YELLOW}🚫 DENIED (403)${NC}"
    else
        echo -e "${RED}❌ ERROR (HTTP $http_code)${NC}"
    fi
    
    echo "Response: $body"
    echo ""
    return $http_code
}

# Test 1: MikroTik Authentication - New User (Should be denied)
echo -e "${YELLOW}=== Test 1: Authentication - New User ===${NC}"
test_endpoint "POST" "$API_BASE/mikrotik/auth/" \
    "{\"username\":\"$TEST_PHONE\",\"password\":\"$TEST_PHONE\",\"mac\":\"$TEST_MAC\",\"ip\":\"$TEST_IP\"}" \
    "MikroTik Auth - New User"

# Test 2: Create user with payment to test successful auth
echo -e "${YELLOW}=== Test 2: Creating User with Payment ===${NC}"
echo "Initiating payment for user..."
payment_response=$(curl -s -X POST "$API_BASE/initiate-payment/" \
    -H "Content-Type: application/json" \
    -d "{\"phone_number\":\"$TEST_PHONE\",\"bundle_id\":1}")

echo "Payment initiation response: $payment_response"

# Extract order reference
order_reference=$(echo "$payment_response" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('order_reference', ''))
except:
    pass
" 2>/dev/null)

if [ -n "$order_reference" ]; then
    echo "Order reference: $order_reference"
    
    # Simulate payment completion via webhook
    echo "Simulating payment completion..."
    webhook_response=$(curl -s -X POST "$API_BASE/clickpesa-webhook/" \
        -H "Content-Type: application/json" \
        -d "{
            \"event\": \"PAYMENT_RECEIVED\",
            \"data\": {
                \"orderReference\": \"$order_reference\",
                \"status\": \"COMPLETED\",
                \"collectedAmount\": \"1000\"
            }
        }")
    
    echo "Webhook response: $webhook_response"
    sleep 2
else
    echo "Failed to get order reference, creating user manually..."
fi

# Test 3: MikroTik Authentication - Paid User (Should succeed)
echo -e "${YELLOW}=== Test 3: Authentication - Paid User ===${NC}"
test_endpoint "POST" "$API_BASE/mikrotik/auth/" \
    "{\"username\":\"$TEST_PHONE\",\"password\":\"$TEST_PHONE\",\"mac\":\"$TEST_MAC\",\"ip\":\"$TEST_IP\"}" \
    "MikroTik Auth - Paid User"

# Test 4: User Status Check
echo -e "${YELLOW}=== Test 4: User Status Check ===${NC}"
test_endpoint "GET" "$API_BASE/user-status/$TEST_PHONE/" \
    "" \
    "User Status Check"

# Test 5: MikroTik User Status
echo -e "${YELLOW}=== Test 5: MikroTik User Status ===${NC}"
test_endpoint "POST" "$API_BASE/mikrotik/user-status/" \
    "{\"username\":\"$TEST_PHONE\"}" \
    "MikroTik User Status"

# Test 6: MikroTik Status Check
echo -e "${YELLOW}=== Test 6: MikroTik Status Check ===${NC}"
test_endpoint "GET" "$API_BASE/mikrotik/status/" \
    "" \
    "MikroTik Status Check"

# Test 7: MikroTik Logout
echo -e "${YELLOW}=== Test 7: MikroTik Logout ===${NC}"
test_endpoint "POST" "$API_BASE/mikrotik/logout/" \
    "{\"username\":\"$TEST_PHONE\",\"ip\":\"$TEST_IP\",\"mac\":\"$TEST_MAC\"}" \
    "MikroTik Logout"

# Test 8: Verify Access Endpoint
echo -e "${YELLOW}=== Test 8: Verify Access ===${NC}"
test_endpoint "POST" "$API_BASE/verify/" \
    "{\"phone_number\":\"$TEST_PHONE\",\"mac_address\":\"$TEST_MAC\",\"ip_address\":\"$TEST_IP\"}" \
    "Verify Access"

echo -e "${GREEN}=== Testing Complete ===${NC}"
echo ""
echo "Summary:"
echo "- mikrotik/auth/: Handles router authentication requests"
echo "- mikrotik/logout/: Handles user logout"
echo "- mikrotik/status/: Router status check"
echo "- mikrotik/user-status/: Individual user status"
echo "- verify/: General access verification"
echo "- user-status/<phone>/: User status by phone number"
