"""
Quick Device Tracking Test
"""
from billing.models import User, Device
from billing.views import mikrotik_auth
from django.test import RequestFactory
import json

def test_device_count():
    """Test device count for user 255684106419"""
    try:
        user = User.objects.get(phone_number='255684106419')
        print(f"User: {user.phone_number}")
        print(f"Max devices: {user.max_devices}")
        print(f"Has access: {user.has_active_access()}")
        
        # Get device counts
        active_devices = user.get_active_devices()
        all_devices = user.devices.all()
        
        print(f"Active devices: {active_devices.count()}")
        print(f"Total devices: {all_devices.count()}")
        
        for device in all_devices:
            status = "Active" if device.is_active else "Inactive"
            print(f"  {status}: {device.mac_address} - {device.device_name}")
        
        return active_devices.count()
    except Exception as e:
        print(f"Error: {e}")
        return 0

def test_api_response():
    """Test API response"""
    factory = RequestFactory()
    
    # Test 1: Form data
    print("\nTesting form data:")
    request = factory.post('/auth/', {
        'username': '255684106419',
        'mac': 'AA:BB:CC:DD:EE:FF',
        'ip': '192.168.88.100'
    })
    
    response = mikrotik_auth(request)
    print(f"Status: {response.status_code}")
    print(f"Content: {response.content.decode()}")
    
    # Test 2: JSON data
    print("\nTesting JSON data:")
    request = factory.post('/auth/', 
                          data=json.dumps({
                              'username': '255684106419',
                              'mac': 'AA:BB:CC:DD:EE:FF',
                              'ip': '192.168.88.100'
                          }),
                          content_type='application/json')
    request.META['HTTP_ACCEPT'] = 'application/json'
    request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0'
    
    response = mikrotik_auth(request)
    print(f"Status: {response.status_code}")
    try:
        data = json.loads(response.content)
        print(f"JSON Response: {data}")
        print(f"Device count: {data.get('device_count', 'N/A')}")
    except:
        print(f"Content: {response.content.decode()}")

# Run tests
print("=" * 50)
print("DEVICE TRACKING TEST")
print("=" * 50)

device_count = test_device_count()
test_api_response()

print(f"\nDevice count result: {device_count}")
print("Test completed!")
