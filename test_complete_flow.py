#!/usr/bin/env python3
"""
Complete WiFi Access Flow Test
Tests payment initiation and voucher redemption with MikroTik auto-login
"""
import requests
import json
import time

BASE_URL = "http://192.168.0.85:8000/api"
ADMIN_TOKEN = "kitonga_admin_2025"
TEST_PHONE = "255684106419"  # User provided: 0684106419
TEST_MAC = "AA:BB:CC:DD:EE:FF"

def print_section(title):
    print("\n" + "=" * 60)
    print(f"🔹 {title}")
    print("=" * 60)

def print_json(data):
    print(json.dumps(data, indent=2))

def test_payment_flow():
    """Test mobile payment initiation via ClickPesa"""
    print("\n" + "=" * 60)
    print("💳 MOBILE PAYMENT FLOW TEST")
    print("=" * 60)
    
    # Step 1: Check user status before
    print_section("STEP 1: Check user status BEFORE payment")
    resp = requests.get(f"{BASE_URL}/user-status/{TEST_PHONE}/")
    user_before = resp.json()
    print_json(user_before)
    print(f"\n📊 User Active: {user_before.get('is_active', 'N/A')}")
    print(f"📊 Has Active Access: {user_before.get('has_active_access', 'N/A')}")
    
    # Step 2: Get available bundles
    print_section("STEP 2: Get available bundles")
    resp = requests.get(f"{BASE_URL}/bundles/")
    bundles_data = resp.json()
    print_json(bundles_data)
    
    # Handle both formats: list or dict with 'bundles' key
    bundles_list = bundles_data.get('bundles', bundles_data) if isinstance(bundles_data, dict) else bundles_data
    
    if bundles_list and isinstance(bundles_list, list):
        print(f"\n📦 Available Bundles: {len(bundles_list)}")
        for bundle in bundles_list:
            if isinstance(bundle, dict):
                print(f"   - ID: {bundle.get('id')} | {bundle.get('name')} | TZS {bundle.get('price')} | {bundle.get('duration_hours')}h")
    
    # Step 3: Initiate payment (USSD Push)
    print_section("STEP 3: Initiate Mobile Payment (USSD Push)")
    print(f"📱 Sending payment request to: {TEST_PHONE}")
    print("⏳ This will trigger a USSD prompt on the phone...")
    
    resp = requests.post(
        f"{BASE_URL}/initiate-payment/",
        headers={"Content-Type": "application/json"},
        json={
            "phone_number": TEST_PHONE,
            "mac_address": TEST_MAC
            # bundle_id is optional, will use default 24h bundle
        }
    )
    payment_data = resp.json()
    print_json(payment_data)
    
    if payment_data.get('success'):
        print("\n✅ Payment initiated successfully!")
        print(f"   - Order Reference: {payment_data.get('order_reference')}")
        print(f"   - Amount: TZS {payment_data.get('amount')}")
        print(f"   - Transaction ID: {payment_data.get('transaction_id')}")
        
        order_ref = payment_data.get('order_reference')
        
        # Step 4: Check payment status (poll)
        print_section("STEP 4: Checking payment status...")
        print("⏳ Waiting for user to confirm payment on phone...")
        print("   (Polling every 5 seconds for up to 60 seconds)")
        
        max_attempts = 12  # 60 seconds
        for attempt in range(1, max_attempts + 1):
            time.sleep(5)
            print(f"\n🔄 Attempt {attempt}/{max_attempts}...")
            
            resp = requests.get(f"{BASE_URL}/payment-status/{order_ref}/")
            status_data = resp.json()
            
            # Get status from both payment and clickpesa_status
            payment_info = status_data.get('payment', {})
            clickpesa_info = status_data.get('clickpesa_status', {})
            
            payment_status = payment_info.get('status', 'unknown')
            clickpesa_status = clickpesa_info.get('status', 'unknown')
            
            print(f"   Payment Status: {payment_status}")
            print(f"   ClickPesa Status: {clickpesa_status}")
            
            if clickpesa_info.get('message'):
                print(f"   Message: {clickpesa_info.get('message')}")
            
            if payment_status == 'completed' or clickpesa_status in ['SUCCESSFUL', 'SUCCESS', 'SETTLED']:
                print("\n✅ PAYMENT COMPLETED!")
                print_json(status_data)
                
                # If ClickPesa shows success but local status is still pending, 
                # the webhook might not have been received
                if payment_status != 'completed' and clickpesa_status in ['SUCCESS', 'SETTLED']:
                    print("\n⚠️ WARNING: ClickPesa shows payment success, but local status is still pending!")
                    print("   This may indicate the webhook wasn't received.")
                    print("   Checking if payment was processed...")
                
                # Check if MikroTik auto-login was done
                mikrotik_info = status_data.get('mikrotik_auto_login', {})
                if mikrotik_info:
                    print("\n🔐 MikroTik Auto-Login Details:")
                    print(f"   - Success: {mikrotik_info.get('success', 'N/A')}")
                    print(f"   - Message: {mikrotik_info.get('message', 'N/A')}")
                
                break
            elif payment_status == 'failed' or clickpesa_status == 'FAILED':
                print("\n❌ Payment failed!")
                print(f"   Reason: {clickpesa_info.get('message', 'Unknown')}")
                if clickpesa_info.get('customer'):
                    print(f"   Customer: {clickpesa_info['customer'].get('customerName', 'N/A')}")
                print_json(status_data)
                break
            elif payment_status == 'cancelled' or clickpesa_status == 'CANCELLED':
                print("\n⚠️ Payment was cancelled!")
                print_json(status_data)
                break
        else:
            print("\n⏰ Timeout waiting for payment confirmation")
            print("   The payment may still be processed. Check again later.")
        
        # Step 5: Check user status after payment
        print_section("STEP 5: Check user status AFTER payment attempt")
        resp = requests.get(f"{BASE_URL}/user-status/{TEST_PHONE}/")
        user_after = resp.json()
        print_json(user_after)
        print(f"\n📊 User Active: {user_after.get('is_active', 'N/A')}")
        print(f"📊 Has Active Access: {user_after.get('has_active_access', 'N/A')}")
        print(f"📊 Paid Until: {user_after.get('paid_until', 'N/A')}")
        
        # Step 6: Verify internet access
        print_section("STEP 6: Verify internet access")
        resp = requests.post(
            f"{BASE_URL}/verify/",
            headers={"Content-Type": "application/json"},
            json={
                "phone_number": TEST_PHONE,
                "mac_address": TEST_MAC
            }
        )
        verify_data = resp.json()
        print_json(verify_data)
        
        if verify_data.get('access_granted'):
            print("\n✅ ACCESS GRANTED! User should have internet.")
        else:
            print(f"\n❌ Access denied: {verify_data.get('denial_reason', 'Unknown')}")
        
        return order_ref
    else:
        print(f"\n❌ Failed to initiate payment: {payment_data.get('message', 'Unknown error')}")
        return None

def test_voucher_flow():
    print("\n" + "=" * 60)
    print("🧪 COMPLETE WIFI ACCESS FLOW TEST")
    print("=" * 60)
    
    # Step 1: Check user status before
    print_section("STEP 1: Check user status BEFORE voucher redemption")
    resp = requests.get(f"{BASE_URL}/user-status/{TEST_PHONE}/")
    user_before = resp.json()
    print_json(user_before)
    print(f"\n📊 User Active: {user_before.get('is_active', 'N/A')}")
    print(f"📊 Has Active Access: {user_before.get('has_active_access', 'N/A')}")
    
    # Step 2: Generate new voucher
    print_section("STEP 2: Generate new voucher (Admin)")
    resp = requests.post(
        f"{BASE_URL}/vouchers/generate/",
        headers={
            "Content-Type": "application/json",
            "X-Admin-Access": ADMIN_TOKEN
        },
        json={
            "quantity": 1,
            "duration_hours": 24,
            "admin_phone_number": TEST_PHONE
        }
    )
    voucher_data = resp.json()
    print_json(voucher_data)
    
    if not voucher_data.get('success'):
        print("❌ Failed to generate voucher!")
        return
    
    voucher_code = voucher_data['vouchers'][0]['code']
    print(f"\n✅ Generated Voucher Code: {voucher_code}")
    
    # Step 3: Redeem voucher
    print_section("STEP 3: Redeem voucher (should auto-connect to MikroTik)")
    resp = requests.post(
        f"{BASE_URL}/vouchers/redeem/",
        headers={"Content-Type": "application/json"},
        json={
            "voucher_code": voucher_code,
            "phone_number": TEST_PHONE,
            "mac_address": TEST_MAC
        }
    )
    redeem_data = resp.json()
    print_json(redeem_data)
    
    if redeem_data.get('success'):
        print("\n✅ Voucher redeemed successfully!")
        
        # Check MikroTik auto-login info
        mikrotik_info = redeem_data.get('mikrotik_auto_login', {})
        if mikrotik_info:
            print("\n🔐 MikroTik Auto-Login Details:")
            print(f"   - Success: {mikrotik_info.get('success', 'N/A')}")
            print(f"   - Hotspot User Created: {mikrotik_info.get('hotspot_user_created', 'N/A')}")
            print(f"   - IP Binding Created: {mikrotik_info.get('ip_binding_created', 'N/A')}")
            print(f"   - Message: {mikrotik_info.get('message', 'N/A')}")
        
        # Check credentials
        credentials = redeem_data.get('hotspot_credentials', {})
        if credentials:
            print("\n🔑 Hotspot Credentials:")
            print(f"   - Username: {credentials.get('username', 'N/A')}")
            print(f"   - Password: {credentials.get('password', 'N/A')}")
    else:
        print(f"\n❌ Failed to redeem voucher: {redeem_data.get('message', 'Unknown error')}")
        return
    
    # Step 4: Verify user status after
    print_section("STEP 4: Check user status AFTER voucher redemption")
    resp = requests.get(f"{BASE_URL}/user-status/{TEST_PHONE}/")
    user_after = resp.json()
    print_json(user_after)
    print(f"\n📊 User Active: {user_after.get('is_active', 'N/A')}")
    print(f"📊 Has Active Access: {user_after.get('has_active_access', 'N/A')}")
    print(f"📊 Paid Until: {user_after.get('paid_until', 'N/A')}")
    print(f"📊 Time Remaining: {user_after.get('time_remaining', 'N/A')}")
    
    # Step 5: Verify access
    print_section("STEP 5: Verify access (should be granted)")
    resp = requests.post(
        f"{BASE_URL}/verify/",
        headers={"Content-Type": "application/json"},
        json={
            "phone_number": TEST_PHONE,
            "mac_address": TEST_MAC
        }
    )
    verify_data = resp.json()
    print_json(verify_data)
    
    if verify_data.get('access_granted'):
        print("\n✅ ACCESS GRANTED! User is connected to internet.")
    else:
        print(f"\n❌ Access denied: {verify_data.get('denial_reason', 'Unknown')}")
    
    # Summary
    print_section("SUMMARY")
    print(f"✅ Voucher Code: {voucher_code}")
    print(f"✅ Phone Number: {TEST_PHONE}")
    print(f"✅ MAC Address: {TEST_MAC}")
    print(f"✅ User Active: {user_after.get('is_active', 'N/A')}")
    print(f"✅ Access Granted: {verify_data.get('access_granted', 'N/A')}")
    print(f"✅ MikroTik Connected: {redeem_data.get('mikrotik_auto_login', {}).get('success', 'N/A')}")

def main():
    """Main entry point - runs payment flow test"""
    print("\n" + "=" * 60)
    print("🚀 KITONGA WIFI - MOBILE PAYMENT TEST")
    print("=" * 60)
    print(f"\n📱 Test Phone: {TEST_PHONE}")
    print(f"📶 Test MAC: {TEST_MAC}")
    print(f"🌐 API Base: {BASE_URL}")
    
    print("\n" + "-" * 60)
    print("Choose test mode:")
    print("  1. Mobile Payment Flow (ClickPesa USSD Push)")
    print("  2. Voucher Redemption Flow")
    print("  3. Both (Payment first, then Voucher)")
    print("-" * 60)
    
    choice = input("\nEnter choice (1/2/3) or press Enter for Payment test: ").strip()
    
    if choice == "2":
        test_voucher_flow()
    elif choice == "3":
        test_payment_flow()
        print("\n" + "=" * 60)
        print("Now testing voucher flow...")
        time.sleep(2)
        test_voucher_flow()
    else:
        # Default to payment test
        test_payment_flow()

if __name__ == "__main__":
    main()
