#!/bin/bash
# Simple API Test Script for User Access Logic
# Tests both payment and voucher users without requiring Django setup

BASE_URL="http://127.0.0.1:8000/api"

echo "🧪 TESTING KITONGA WIFI BILLING SYSTEM"
echo "======================================="
echo ""

# Test payment user
echo "1. Testing Payment User Access"
echo "------------------------------"

echo "Testing MikroTik auth for payment user..."
curl -s -X POST "${BASE_URL}/mikrotik/auth/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=255123456789&password=&mac=00:11:22:33:44:55&ip=192.168.0.100" \
  | head -c 100
echo ""

echo "Testing user status for payment user..."
curl -s -X GET "${BASE_URL}/mikrotik/user-status/?username=255123456789" \
  | jq -r '.user.has_active_access // "Error"'
echo ""

# Test voucher user
echo "2. Testing Voucher User Access"
echo "------------------------------"

echo "Testing MikroTik auth for voucher user..."
curl -s -X POST "${BASE_URL}/mikrotik/auth/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=255987654321&password=&mac=00:11:22:33:44:66&ip=192.168.0.101" \
  | head -c 100
echo ""

echo "Testing user status for voucher user..."
curl -s -X GET "${BASE_URL}/mikrotik/user-status/?username=255987654321" \
  | jq -r '.user.has_active_access // "Error"'
echo ""

# Test new user
echo "3. Testing New User (Should Fail)"
echo "--------------------------------"

echo "Testing MikroTik auth for new user..."
curl -s -X POST "${BASE_URL}/mikrotik/auth/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=255111222333&password=&mac=00:11:22:33:44:77&ip=192.168.0.102" \
  | head -c 100
echo ""

# Test debug endpoint
echo "4. Testing Debug Endpoint"
echo "------------------------"

echo "Debug payment user..."
curl -s -X GET "${BASE_URL}/mikrotik/debug-user/?phone_number=255123456789" \
  | jq -r '.debug_info.system_check.has_active_access // "Error"'
echo ""

# Test health check
echo "5. Testing System Health"
echo "-----------------------"

echo "Health check..."
curl -s -X GET "${BASE_URL}/health/" \
  | jq -r '.status // "Error"'
echo ""

echo "✅ Test completed! Check the output above for any errors."
echo ""
echo "💡 To see detailed debug info, run:"
echo "curl -X GET '${BASE_URL}/mikrotik/debug-user/?phone_number=255123456789' | jq"
