#!/bin/bash

# Test Portal Router APIs
# API Key: 4c5ae7bc7712a2fccd6f3fb9b2d61566f538a3a85b6bc8a2899953329b0438f9
# Base URL: https://api.kitonga.klikcell.com
# Router ID: 5

API_KEY="4c5ae7bc7712a2fccd6f3fb9b2d61566f538a3a85b6bc8a2899953329b0438f9"
BASE_URL="https://api.kitonga.klikcell.com"
ROUTER_ID="5"

echo "============================================"
echo "Testing Portal Router APIs"
echo "Router ID: $ROUTER_ID"
echo "============================================"
echo ""

# Test 1: Get Active Users on Router
echo "📊 Test 1: GET Active Users on Router $ROUTER_ID"
echo "--------------------------------------------"
curl -X GET "${BASE_URL}/api/portal/router/${ROUTER_ID}/active-users/" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -w "\n\nHTTP Status: %{http_code}\n" \
  -s | jq '.'

echo ""
echo ""

# Test 2: Disconnect User from Router
echo "🔌 Test 2: POST Disconnect User from Router $ROUTER_ID"
echo "--------------------------------------------"
echo "⚠️  This will disconnect a user. Enter user ID when prompted."
read -p "Enter User ID to disconnect (or press Enter to skip): " USER_ID

if [ -n "$USER_ID" ]; then
  curl -X POST "${BASE_URL}/api/portal/router/${ROUTER_ID}/disconnect-user/" \
    -H "Authorization: Bearer ${API_KEY}" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\": ${USER_ID}}" \
    -w "\n\nHTTP Status: %{http_code}\n" \
    -s | jq '.'
else
  echo "Skipped disconnect test"
fi

echo ""
echo "============================================"
echo "✅ Tests completed!"
echo "============================================"
