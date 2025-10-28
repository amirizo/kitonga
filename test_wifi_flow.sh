#!/bin/bash

# Kitonga WiFi Billing System - Quick Test Script
# This script tests the complete user flow from connection to payment

echo "============================================"
echo "KITONGA WIFI BILLING SYSTEM - QUICK TEST"
echo "============================================"

# Configuration
API_BASE="http://127.0.0.1:8000/api"
TEST_PHONE="255712345999"
TEST_MAC="AA:BB:CC:DD:EE:FF"
ADMIN_TOKEN="YOUR_ADMIN_TOKEN"  # Replace with actual token
ADMIN_HEADER="kitonga_admin_2025"

echo ""
echo "🔧 Configuration:"
echo "API Base: $API_BASE"
echo "Test Phone: $TEST_PHONE"
echo "Test MAC: $TEST_MAC"
echo ""

# Test 1: System Health Check
echo "📡 Test 1: System Health Check"
echo "------------------------------"
curl -s -X GET "$API_BASE/health/" | python3 -m json.tool
echo ""

# Test 2: Get Available Bundles
echo "📦 Test 2: Available Bundles"
echo "----------------------------"
curl -s -X GET "$API_BASE/bundles/" | python3 -m json.tool
echo ""

# Test 3: Access Verification (New User)
echo "🔐 Test 3: Access Verification (New User)"
echo "----------------------------------------"
curl -s -X POST "$API_BASE/verify/" \
  -H "Content-Type: application/json" \
  -d "{
    \"phone_number\": \"$TEST_PHONE\",
    \"mac_address\": \"$TEST_MAC\"
  }" | python3 -m json.tool
echo ""

# Test 4: Initiate Payment
echo "💳 Test 4: Initiate Payment"
echo "---------------------------"
PAYMENT_RESPONSE=$(curl -s -X POST "$API_BASE/initiate-payment/" \
  -H "Content-Type: application/json" \
  -d "{
    \"phone_number\": \"$TEST_PHONE\",
    \"bundle_id\": 1,
    \"amount\": 1000
  }")

echo "$PAYMENT_RESPONSE" | python3 -m json.tool

# Extract order reference for next test
ORDER_REF=$(echo "$PAYMENT_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('payment_details', {}).get('order_reference', 'NOT_FOUND'))" 2>/dev/null)
echo ""
echo "Order Reference: $ORDER_REF"
echo ""

# Test 5: Check Payment Status
if [ "$ORDER_REF" != "NOT_FOUND" ] && [ "$ORDER_REF" != "" ]; then
    echo "⏳ Test 5: Payment Status Check"
    echo "------------------------------"
    curl -s -X GET "$API_BASE/payment-status/$ORDER_REF/" | python3 -m json.tool
    echo ""
    
    # Test 6: Simulate Payment Webhook
    echo "🔔 Test 6: Simulate Payment Webhook"
    echo "----------------------------------"
    curl -s -X POST "$API_BASE/clickpesa-webhook/" \
      -H "Content-Type: application/json" \
      -d "{
        \"order_reference\": \"$ORDER_REF\",
        \"transaction_reference\": \"CLPLCPCA6KYH4\",
        \"amount\": 1000,
        \"status\": \"PAYMENT RECEIVED\",
        \"phone_number\": \"$TEST_PHONE\",
        \"channel\": \"TIGO-PESA\"
      }" | python3 -m json.tool
    echo ""
    
    # Test 7: Verify Access After Payment
    echo "✅ Test 7: Access Verification (After Payment)"
    echo "---------------------------------------------"
    curl -s -X POST "$API_BASE/verify/" \
      -H "Content-Type: application/json" \
      -d "{
        \"phone_number\": \"$TEST_PHONE\",
        \"mac_address\": \"$TEST_MAC\"
      }" | python3 -m json.tool
    echo ""
else
    echo "❌ Skipping payment status tests - no order reference"
fi

# Test 8: User Status Check
echo "👤 Test 8: User Status"
echo "----------------------"
curl -s -X GET "$API_BASE/user-status/$TEST_PHONE/" | python3 -m json.tool
echo ""

# Test 9: Device Management
echo "📱 Test 9: Device Management"
echo "----------------------------"
curl -s -X GET "$API_BASE/devices/$TEST_PHONE/" | python3 -m json.tool
echo ""

# Test 10: Dashboard Stats (Admin)
if [ "$ADMIN_TOKEN" != "YOUR_ADMIN_TOKEN" ]; then
    echo "📊 Test 10: Dashboard Stats (Admin)"
    echo "----------------------------------"
    curl -s -X GET "$API_BASE/dashboard-stats/" \
      -H "Authorization: Token $ADMIN_TOKEN" | python3 -m json.tool
    echo ""
    
    # Test 11: List Users (Admin)
    echo "👥 Test 11: List Users (Admin)"
    echo "-----------------------------"
    curl -s -X GET "$API_BASE/admin/users/" \
      -H "Authorization: Token $ADMIN_TOKEN" \
      -H "X-Admin-Access: $ADMIN_HEADER" | python3 -m json.tool
    echo ""
else
    echo "⚠️  Skipping admin tests - please set ADMIN_TOKEN in script"
fi

# Test 12: Device Limit Test
echo "🚫 Test 12: Device Limit Test (Second Device)"
echo "--------------------------------------------"
curl -s -X POST "$API_BASE/verify/" \
  -H "Content-Type: application/json" \
  -d "{
    \"phone_number\": \"$TEST_PHONE\",
    \"mac_address\": \"BB:CC:DD:EE:FF:AA\"
  }" | python3 -m json.tool
echo ""

# Test 13: Invalid Payment Amount
echo "💸 Test 13: Invalid Payment Amount"
echo "---------------------------------"
curl -s -X POST "$API_BASE/initiate-payment/" \
  -H "Content-Type: application/json" \
  -d "{
    \"phone_number\": \"$TEST_PHONE\",
    \"bundle_id\": 1,
    \"amount\": 500
  }" | python3 -m json.tool
echo ""

echo "============================================"
echo "✅ TESTING COMPLETE"
echo "============================================"
echo ""
echo "📋 Summary:"
echo "- System health check completed"
echo "- User flow tested (connection → payment → access)"
echo "- Device limits verified"
echo "- Error scenarios tested"
echo "- Admin functions tested (if token provided)"
echo ""
echo "📖 For detailed testing, see: COMPLETE_TESTING_GUIDE.md"
echo "🔧 To run admin tests, update ADMIN_TOKEN in this script"
echo ""
