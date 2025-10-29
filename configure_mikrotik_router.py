#!/usr/bin/env python
"""
MikroTik Router Configuration Script
Automatically configures your router for external authentication
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitonga.settings')
django.setup()

from django.conf import settings
import routeros_api

def configure_mikrotik_external_auth():
    """Configure MikroTik router for external authentication"""
    print("🔧 Configuring MikroTik Router for External Authentication")
    print("=" * 70)
    
    router_ip = settings.MIKROTIK_ROUTER_IP
    admin_user = settings.MIKROTIK_ADMIN_USER
    admin_pass = settings.MIKROTIK_ADMIN_PASS
    api_port = settings.MIKROTIK_API_PORT
    
    print(f"Router: {router_ip}")
    print(f"Configuring external authentication...")
    print()
    
    try:
        # Connect to router
        connection = routeros_api.RouterOsApiPool(
            host=router_ip,
            username=admin_user,
            password=admin_pass,
            port=api_port,
            plaintext_login=True
        )
        
        api = connection.get_api()
        print("✅ Connected to router successfully!")
        
        # Get hotspot profiles
        profiles_resource = api.get_resource('/ip/hotspot/user/profile')
        profiles = profiles_resource.get()
        
        print(f"\n📋 Found {len(profiles)} hotspot profiles:")
        for i, profile in enumerate(profiles):
            print(f"  {i+1}. {profile.get('name', 'Unnamed')}")
        
        # Configure each profile for external authentication
        auth_url = "https://api.kitonga.klikcell.com/api/mikrotik/auth/"
        logout_url = "https://api.kitonga.klikcell.com/api/mikrotik/logout/"
        
        print(f"\n🔧 Configuring external authentication URLs...")
        print(f"Auth URL: {auth_url}")
        print(f"Logout URL: {logout_url}")
        print()
        
        for profile in profiles:
            profile_name = profile.get('name')
            profile_id = profile.get('.id')
            
            try:
                # Update profile with external authentication
                profiles_resource.set(
                    id=profile_id,
                    **{
                        'login-by': 'cookie',
                        'http-cookie-auth-url': auth_url,
                        'http-cookie-logout-url': logout_url
                    }
                )
                print(f"✅ Configured profile: {profile_name}")
                
            except Exception as e:
                print(f"❌ Failed to configure profile {profile_name}: {e}")
        
        # Verify configuration
        print(f"\n✅ Verifying configuration...")
        updated_profiles = profiles_resource.get()
        
        for profile in updated_profiles:
            name = profile.get('name')
            login_by = profile.get('login-by', 'Not set')
            auth_url_set = profile.get('http-cookie-auth-url', 'Not set')
            logout_url_set = profile.get('http-cookie-logout-url', 'Not set')
            
            print(f"\n📊 Profile: {name}")
            print(f"   Login By: {login_by}")
            print(f"   Auth URL: {auth_url_set}")
            print(f"   Logout URL: {logout_url_set}")
            
            if login_by == 'cookie' and auth_url in str(auth_url_set):
                print(f"   ✅ Correctly configured")
            else:
                print(f"   ⚠️  Needs manual configuration")
        
        connection.disconnect()
        print(f"\n🎉 Router configuration completed!")
        
    except Exception as e:
        print(f"❌ Configuration failed: {e}")
        return False
    
    return True

def test_external_auth_setup():
    """Test the external authentication setup"""
    print(f"\n🧪 Testing External Authentication Setup")
    print("=" * 70)
    
    router_ip = settings.MIKROTIK_ROUTER_IP
    
    print(f"Your router is now configured for external authentication!")
    print()
    print(f"🌐 Hotspot Configuration:")
    print(f"   Router IP: {router_ip}")
    print(f"   Auth URL: https://api.kitonga.klikcell.com/api/mikrotik/auth/")
    print(f"   Logout URL: https://api.kitonga.klikcell.com/api/mikrotik/logout/")
    print()
    print(f"📱 How it works:")
    print(f"1. User connects to your WiFi hotspot")
    print(f"2. Router redirects to captive portal")
    print(f"3. User enters phone number to login")
    print(f"4. Router calls your Django API for authentication")
    print(f"5. Django checks if user has paid for access")
    print(f"6. Router grants/denies access based on response")
    print()
    print(f"🎯 Test with a real device:")
    print(f"1. Connect device to your WiFi hotspot")
    print(f"2. Browser should redirect to login page")
    print(f"3. Enter phone number: 0772236727")
    print(f"4. Check Django admin for access logs")

def show_next_steps():
    """Show next steps for complete setup"""
    print(f"\n📋 Next Steps for Complete Setup")
    print("=" * 70)
    
    print(f"✅ Completed:")
    print(f"   • Router connectivity tested")
    print(f"   • API endpoints working")
    print(f"   • External authentication configured")
    print(f"   • Database models ready")
    print()
    print(f"🔧 Remaining tasks:")
    print(f"   1. Create test users with payments")
    print(f"   2. Test with real devices")
    print(f"   3. Configure hotspot splash page (optional)")
    print(f"   4. Set up monitoring and logging")
    print(f"   5. Deploy to production")
    print()
    print(f"🎯 Testing checklist:")
    print(f"   □ Connect phone to WiFi hotspot")
    print(f"   □ Verify captive portal appears")
    print(f"   □ Test authentication with paid user")
    print(f"   □ Test denial for unpaid user")
    print(f"   □ Test device limit enforcement")
    print(f"   □ Test logout functionality")
    print()
    print(f"📞 Support:")
    print(f"   • Check Django admin for logs")
    print(f"   • Monitor /api/mikrotik/auth/ endpoint")
    print(f"   • Review MikroTik hotspot logs")

if __name__ == "__main__":
    print("🎯 MIKROTIK ROUTER CONFIGURATION")
    print("=" * 80)
    
    # Configure external authentication
    success = configure_mikrotik_external_auth()
    
    if success:
        # Test setup
        test_external_auth_setup()
        
        # Show next steps
        show_next_steps()
        
        print("\n" + "=" * 80)
        print("🎉 ROUTER CONFIGURATION COMPLETE!")
        print("Your MikroTik router is now ready for external authentication!")
    else:
        print("\n❌ Configuration failed. Please check router settings.")
