#!/bin/bash

# Comprehensive test script for MikroTik Integration APIs
# Tests all 4 MikroTik endpoints with various scenarios

BASE_URL="https://api.kitonga.klikcell.com/api"
TEST_PHONE="255743000999"  # This should be a real test user in your system
TEST_MAC="AA:BB:CC:DD:EE:FF"
TEST_IP="192.168.1.100"

echo "=== TESTING MIKROTIK INTEGRATION APIS ==="
echo "Base URL: $BASE_URL"
echo "Test Phone: $TEST_PHONE"
echo ""

# Function to make API call and show result
test_api() {
    local endpoint="$1"
    local method="$2"
    local data="$3"
    local description="$4"
    
    echo "--- Test: $description ---"
    echo "Endpoint: $method $BASE_URL$endpoint"
    echo "Data: $data"
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "$BASE_URL$endpoint")
    else
        response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X "$method" -H "Content-Type: application/json" -d "$data" "$BASE_URL$endpoint")
    fi
    
    # Extract HTTP status and body
    http_status=$(echo "$response" | grep "HTTP_STATUS:" | cut -d: -f2)
    body=$(echo "$response" | sed '/HTTP_STATUS:/d')
    
    echo "HTTP Status: $http_status"
    echo "Response: $body"
    echo ""
}

# Test 1: MikroTik Auth - Valid user with parameters
echo "=== 1. MIKROTIK AUTH TESTS ==="
test_api "/mikrotik/auth/" "POST" "{\"username\":\"$TEST_PHONE\",\"password\":\"\",\"mac\":\"$TEST_MAC\",\"ip\":\"$TEST_IP\"}" "Auth with all parameters (POST)"

# Test 2: MikroTik Auth - GET method
test_api "/mikrotik/auth/?username=$TEST_PHONE&mac=$TEST_MAC&ip=$TEST_IP" "GET" "" "Auth with GET parameters"

# Test 3: MikroTik Auth - No username
test_api "/mikrotik/auth/" "POST" "{\"password\":\"\",\"mac\":\"$TEST_MAC\",\"ip\":\"$TEST_IP\"}" "Auth without username (should fail)"

# Test 4: MikroTik Auth - Non-existent user
test_api "/mikrotik/auth/" "POST" "{\"username\":\"255999999999\",\"password\":\"\",\"mac\":\"$TEST_MAC\",\"ip\":\"$TEST_IP\"}" "Auth with non-existent user"

echo "=== 2. MIKROTIK LOGOUT TESTS ==="
# Test 5: MikroTik Logout - Valid user
test_api "/mikrotik/logout/" "POST" "{\"username\":\"$TEST_PHONE\",\"ip\":\"$TEST_IP\"}" "Logout with valid user (POST)"

# Test 6: MikroTik Logout - GET method
test_api "/mikrotik/logout/?username=$TEST_PHONE&ip=$TEST_IP" "GET" "" "Logout with GET parameters"

# Test 7: MikroTik Logout - No username
test_api "/mikrotik/logout/" "POST" "{\"ip\":\"$TEST_IP\"}" "Logout without username (should fail)"

# Test 8: MikroTik Logout - Non-existent user (should still return OK)
test_api "/mikrotik/logout/" "POST" "{\"username\":\"255999999999\",\"ip\":\"$TEST_IP\"}" "Logout with non-existent user (should still be OK)"

echo "=== 3. MIKROTIK STATUS CHECK TESTS ==="
# Test 9: MikroTik Status Check (requires admin token)
test_api "/mikrotik/status/" "GET" "" "Status check (needs admin auth - will likely fail)"

echo "=== 4. MIKROTIK USER STATUS TESTS ==="
# Test 10: User Status - Valid user
test_api "/mikrotik/user-status/?username=$TEST_PHONE" "GET" "" "User status for valid user"

# Test 11: User Status - No username
test_api "/mikrotik/user-status/" "GET" "" "User status without username (should fail)"

# Test 12: User Status - Non-existent user
test_api "/mikrotik/user-status/?username=255999999999" "GET" "" "User status for non-existent user"

echo "=== 5. ADDITIONAL VALIDATION TESTS ==="
# Test 13: Test with minimal parameters
test_api "/mikrotik/auth/" "POST" "{\"username\":\"$TEST_PHONE\"}" "Auth with minimal parameters (username only)"

# Test 14: Test logout with minimal parameters
test_api "/mikrotik/logout/" "POST" "{\"username\":\"$TEST_PHONE\"}" "Logout with minimal parameters (username only)"

echo "=== TEST SUMMARY ==="
echo "Tested all 4 MikroTik integration endpoints:"
echo "1. /mikrotik/auth/ - Captive portal authentication"
echo "2. /mikrotik/logout/ - User logout tracking"
echo "3. /mikrotik/status/ - Router status (admin only)"
echo "4. /mikrotik/user-status/ - Individual user status"
echo ""
echo "Expected results:"
echo "- Auth: 200 for valid paid users, 403 for unpaid/invalid users"
echo "- Logout: 200 for all valid requests, 400 for missing username"
echo "- Status: 403 without admin token, 200 with valid admin token"
echo "- User Status: 200 for existing users, 404 for non-existent users"
