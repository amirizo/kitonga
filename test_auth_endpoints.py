#!/usr/bin/env python
"""
Test script for Tenant Authentication Endpoints
Tests: Registration with OTP, Email Verification, Login, Password Reset
"""
import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000/api"

# Test data - use unique email for each test run
TEST_EMAIL = f"test_{int(time.time())}@example.com"
TEST_PASSWORD = "SecurePassword123!"
TEST_BUSINESS = f"Test WiFi Business {int(time.time())}"

headers = {
    "Content-Type": "application/json"
}

def print_response(name, response):
    """Pretty print response"""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    print(f"Status: {response.status_code}")
    try:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
    except:
        print(f"Response: {response.text[:500]}")
    return response

def test_registration():
    """Test tenant registration with OTP"""
    print("\n" + "="*60)
    print("1. TESTING REGISTRATION")
    print("="*60)
    
    response = requests.post(
        f"{BASE_URL}/saas/register/",
        headers=headers,
        json={
            "business_name": TEST_BUSINESS,
            "business_email": TEST_EMAIL,
            "business_phone": "+255712345678",
            "admin_email": TEST_EMAIL,
            "admin_password": TEST_PASSWORD,
            "admin_first_name": "Test",
            "admin_last_name": "User"
        }
    )
    
    print_response("Register Tenant", response)
    
    if response.status_code == 201:
        data = response.json()
        print(f"\n✅ Registration successful!")
        print(f"   Email: {data.get('email')}")
        print(f"   Requires verification: {data.get('requires_verification')}")
        return data
    else:
        print(f"\n❌ Registration failed!")
        return None

def test_resend_otp():
    """Test resend OTP"""
    print("\n" + "="*60)
    print("2. TESTING RESEND OTP")
    print("="*60)
    
    # First try should fail due to rate limit (within 60 seconds)
    response = requests.post(
        f"{BASE_URL}/saas/resend-otp/",
        headers=headers,
        json={
            "email": TEST_EMAIL,
            "purpose": "registration"
        }
    )
    
    print_response("Resend OTP (may be rate limited)", response)
    return response

def test_verify_email_wrong_otp():
    """Test email verification with wrong OTP"""
    print("\n" + "="*60)
    print("3. TESTING VERIFY EMAIL - WRONG OTP")
    print("="*60)
    
    response = requests.post(
        f"{BASE_URL}/saas/verify-email/",
        headers=headers,
        json={
            "email": TEST_EMAIL,
            "otp_code": "000000"  # Wrong OTP
        }
    )
    
    print_response("Verify Email (wrong OTP)", response)
    
    if response.status_code == 400:
        print(f"\n✅ Correctly rejected wrong OTP")
    return response

def test_login_before_verification():
    """Test login before email verification"""
    print("\n" + "="*60)
    print("4. TESTING LOGIN BEFORE VERIFICATION")
    print("="*60)
    
    response = requests.post(
        f"{BASE_URL}/saas/login/",
        headers=headers,
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
    )
    
    print_response("Login (before verification)", response)
    
    if response.status_code == 403:
        data = response.json()
        if data.get('requires_verification'):
            print(f"\n✅ Correctly requires email verification")
    return response

def test_verify_email_correct_otp(otp_code):
    """Test email verification with correct OTP"""
    print("\n" + "="*60)
    print("5. TESTING VERIFY EMAIL - CORRECT OTP")
    print("="*60)
    
    response = requests.post(
        f"{BASE_URL}/saas/verify-email/",
        headers=headers,
        json={
            "email": TEST_EMAIL,
            "otp_code": otp_code
        }
    )
    
    print_response("Verify Email (correct OTP)", response)
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Email verified successfully!")
        print(f"   Tenant: {data.get('tenant', {}).get('business_name')}")
        print(f"   API Key: {data.get('tenant', {}).get('api_key', '')[:20]}...")
        return data
    return None

def test_login_after_verification():
    """Test login after email verification"""
    print("\n" + "="*60)
    print("6. TESTING LOGIN AFTER VERIFICATION")
    print("="*60)
    
    response = requests.post(
        f"{BASE_URL}/saas/login/",
        headers=headers,
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
    )
    
    print_response("Login (after verification)", response)
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Login successful!")
        print(f"   User: {data.get('user', {}).get('email')}")
        print(f"   Role: {data.get('user', {}).get('role')}")
        print(f"   Tenant: {data.get('tenant', {}).get('business_name')}")
        return data
    return None

def test_login_wrong_password():
    """Test login with wrong password"""
    print("\n" + "="*60)
    print("7. TESTING LOGIN - WRONG PASSWORD")
    print("="*60)
    
    response = requests.post(
        f"{BASE_URL}/saas/login/",
        headers=headers,
        json={
            "email": TEST_EMAIL,
            "password": "WrongPassword123!"
        }
    )
    
    print_response("Login (wrong password)", response)
    
    if response.status_code == 401:
        print(f"\n✅ Correctly rejected wrong password")
    return response

def test_password_reset_request():
    """Test password reset request"""
    print("\n" + "="*60)
    print("8. TESTING PASSWORD RESET REQUEST")
    print("="*60)
    
    response = requests.post(
        f"{BASE_URL}/saas/password-reset/",
        headers=headers,
        json={
            "email": TEST_EMAIL
        }
    )
    
    print_response("Password Reset Request", response)
    
    if response.status_code == 200:
        print(f"\n✅ Password reset email sent (check console/logs for OTP)")
    return response

def get_otp_from_db():
    """Get OTP from database for testing (would normally be from email)"""
    import subprocess
    result = subprocess.run(
        ['python', 'manage.py', 'shell', '-c', f'''
from billing.models import EmailOTP
otp = EmailOTP.objects.filter(email="{TEST_EMAIL}", is_used=False).order_by("-created_at").first()
if otp:
    print(otp.otp_code)
else:
    print("NO_OTP")
'''],
        capture_output=True,
        text=True,
        cwd="/Users/macbookair/Desktop/kitonga"
    )
    otp = result.stdout.strip().split('\n')[-1]
    return otp if otp != "NO_OTP" else None

def main():
    print("\n" + "="*60)
    print("KITONGA TENANT AUTHENTICATION TEST SUITE")
    print("="*60)
    print(f"\nTest Email: {TEST_EMAIL}")
    print(f"Test Business: {TEST_BUSINESS}")
    
    # 1. Register
    reg_result = test_registration()
    if not reg_result:
        print("\n❌ Registration failed, stopping tests")
        return
    
    # 2. Try resend OTP (should be rate limited)
    test_resend_otp()
    
    # 3. Try wrong OTP
    test_verify_email_wrong_otp()
    
    # 4. Try login before verification
    test_login_before_verification()
    
    # 5. Get OTP from database and verify
    print("\n📧 Getting OTP from database (simulating email receipt)...")
    otp_code = get_otp_from_db()
    
    if otp_code:
        print(f"   OTP Code: {otp_code}")
        verify_result = test_verify_email_correct_otp(otp_code)
        
        if verify_result:
            # 6. Test login after verification
            test_login_after_verification()
            
            # 7. Test wrong password
            test_login_wrong_password()
            
            # 8. Test password reset
            test_password_reset_request()
    else:
        print("\n❌ Could not get OTP from database")
    
    print("\n" + "="*60)
    print("TEST SUITE COMPLETE")
    print("="*60)

if __name__ == "__main__":
    main()
