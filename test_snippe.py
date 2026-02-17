"""
Quick test script for Snippe API integration.
Tests: API key authentication, account balance, and a test mobile payment.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kitonga.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from billing.snippe import SnippeAPI


def test_snippe():
    snippe = SnippeAPI()

    print("=" * 55)
    print("🧪 SNIPPE API INTEGRATION TEST")
    print("=" * 55)

    # 1. Check API key is loaded
    api_key = snippe.api_key
    if not api_key:
        print("❌ SNIPPE_API_KEY not configured!")
        return
    print(f"✅ API Key loaded: {api_key[:10]}...{api_key[-6:]}")
    print(f"✅ Base URL: {snippe.base_url}")
    print(f"✅ Webhook Secret: {'configured' if snippe.webhook_secret else 'not set'}")
    print()

    # 2. Test account balance (verifies API key works)
    print("📊 Test 1: Account Balance")
    print("-" * 40)
    result = snippe.get_account_balance()
    if result["success"]:
        print(
            f"   ✅ Balance: {result.get('balance', 'N/A')} {result.get('currency', 'TZS')}"
        )
        print(
            f"   ✅ Available: {result.get('available', 'N/A')} {result.get('currency', 'TZS')}"
        )
    else:
        print(f"   ❌ Error: {result.get('message', 'Unknown error')}")
        if result.get("error_code"):
            print(f"   ❌ Error code: {result['error_code']}")
    print()

    # 3. Test list payments (verifies read access)
    print("📋 Test 2: List Payments")
    print("-" * 40)
    result = snippe.list_payments(limit=5)
    if result["success"]:
        data = result.get("data", {})
        items = data.get("items", data) if isinstance(data, dict) else data
        count = len(items) if isinstance(items, list) else "N/A"
        print(f"   ✅ Payments retrieved: {count}")
    else:
        print(f"   ❌ Error: {result.get('message', 'Unknown error')}")
    print()

    # 4. Test mobile payment initiation (with a small amount)
    print("💰 Test 3: Initiate Mobile Payment (TSh 100)")
    print("-" * 40)
    test_phone = input(
        "   Enter test phone number (255XXXXXXXXX) or press Enter to skip: "
    ).strip()

    if test_phone:
        result = snippe.create_mobile_payment(
            phone_number=test_phone,
            amount=1000,
            currency="TZS",
            firstname="Test",
            lastname="User",
            metadata={"test": "true", "source": "kitonga_test_script"},
        )
        if result["success"]:
            print(f"   ✅ Payment initiated!")
            print(f"   📎 Reference: {result.get('reference', 'N/A')}")
            print(f"   📊 Status: {result.get('status', 'N/A')}")
            print(f"   ⏰ Expires: {result.get('expires_at', 'N/A')}")
            print(f"   📱 Check your phone for USSD prompt!")
        else:
            print(f"   ❌ Error: {result.get('message', 'Unknown error')}")
    else:
        print("   ⏭️  Skipped (no phone number provided)")
    print()

    print("=" * 55)
    print("🏁 TEST COMPLETE")
    print("=" * 55)


if __name__ == "__main__":
    test_snippe()
