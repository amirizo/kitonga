"""
Mikrotik Router Integration for Kitonga Wi-Fi Billing System
"""
import os
import socket
import logging
from typing import Optional, List
from django.conf import settings
from django.utils import timezone

# Try to import routeros-api for direct RouterOS operations
try:
    import routeros_api
except Exception:  # library might not be installed yet
    routeros_api = None

logger = logging.getLogger(__name__)

# Check if MikroTik should be mocked (for production environments without router access)
MIKROTIK_MOCK_MODE = os.getenv('MIKROTIK_MOCK_MODE', 'false').lower() == 'true'

# Resolve SSL verify preference from Django settings (default False for self-signed)
SSL_VERIFY = bool(getattr(settings, 'MIKROTIK_SSL_VERIFY', False))


def safe_close(api):
    """Safely close routeros_api communicator if present."""
    try:
        if api:
            api.get_communicator().close()
    except Exception:
        pass


def get_mikrotik_api():
    """
    Return an authenticated RouterOS API connection using env-driven settings.
    Caller should close with api.get_communicator().close() in a finally block.
    """
    if MIKROTIK_MOCK_MODE:
        raise ConnectionRefusedError('MikroTik router not accessible in this environment. Configure VPN or set MIKROTIK_MOCK_MODE=false')
    
    if routeros_api is None:
        raise ImportError('routeros-api is not installed. Add it to requirements.txt')

    host = getattr(settings, 'MIKROTIK_HOST', getattr(settings, 'MIKROTIK_ROUTER_IP', '10.50.0.2'))
    port = int(getattr(settings, 'MIKROTIK_PORT', getattr(settings, 'MIKROTIK_API_PORT', 8728)))
    user = getattr(settings, 'MIKROTIK_USER', getattr(settings, 'MIKROTIK_ADMIN_USER', 'admin'))
    password = getattr(settings, 'MIKROTIK_PASSWORD', getattr(settings, 'MIKROTIK_ADMIN_PASS', 'Kijangwani2003'))
    use_ssl = bool(getattr(settings, 'MIKROTIK_USE_SSL', False))

    try:
        # Try with use_keepalive parameter (newer versions)
        pool = routeros_api.RouterOsApiPool(
            host,
            username=user,
            password=password,
            port=port,
            use_ssl=use_ssl,
            plaintext_login=True,
            use_keepalive=True,
            ssl_verify=SSL_VERIFY,
        )
    except TypeError:
        # Fallback for older versions that don't support use_keepalive
        pool = routeros_api.RouterOsApiPool(
            host,
            username=user,
            password=password,
            port=port,
            use_ssl=use_ssl,
            plaintext_login=True,
            ssl_verify=SSL_VERIFY,
        )
    return pool.get_api()


def allow_mac(mac_address: str, comment: str = 'Paid user') -> bool:
    """Create/ensure bypass binding for a MAC in /ip/hotspot/ip-binding."""
    if not mac_address:
        logger.warning('allow_mac called with empty mac_address')
        return False
    api = get_mikrotik_api()
    try:
        bindings = api.get_resource('/ip/hotspot/ip-binding')
        existing = bindings.get(mac_address=mac_address)
        
        if existing:
            for item in existing:
                if '.id' in item:
                    # use set (routeros_api) not update
                    bindings.set(id=item['.id'], type='bypassed', comment=comment, mac_address=mac_address)
            logger.info(f'Updated bypass binding for {mac_address}')
            return True
        
        bindings.add(type='bypassed', mac_address=mac_address, comment=comment)
        logger.info(f'Created bypass binding for {mac_address}')
        return True
    except Exception as e:
        logger.error(f'allow_mac failed for {mac_address}: {e}')
        return False
    finally:
        safe_close(api)


def revoke_mac(mac_address: str) -> bool:
    """Remove any /ip/hotspot/ip-binding entries for a MAC."""
    if not mac_address:
        return False
    api = get_mikrotik_api()
    try:
        bindings = api.get_resource('/ip/hotspot/ip-binding')
        items = bindings.get(mac_address=mac_address)
        
        if not items:
            logger.info(f'No bindings found for {mac_address}')
            return True  # Nothing to revoke, but not an error
        
        count = 0
        for item in items:
            if '.id' in item:
                bindings.remove(id=item['.id'])
                count += 1
        
        logger.info(f'Revoked {count} binding(s) for {mac_address}')
        return True
    except Exception as e:
        logger.error(f'revoke_mac failed for {mac_address}: {e}')
        return False
    finally:
        safe_close(api)


def create_hotspot_user(username: str, password: str, profile: Optional[str] = None) -> bool:
    """Create or update /ip/hotspot/user entry (no usage limits applied)."""
    if not username:
        return False
    api = get_mikrotik_api()
    try:
        profile = profile or getattr(settings, 'MIKROTIK_DEFAULT_PROFILE', 'default')
        users = api.get_resource('/ip/hotspot/user')
        exist = users.get(name=username)
        
        if exist:
            for item in exist:
                if '.id' in item:
                    users.set(id=item['.id'], password=password, profile=profile, disabled='no')
            logger.info(f'Updated hotspot user {username}')
            return True
        
        users.add(name=username, password=password, profile=profile, disabled='no')
        logger.info(f'Created hotspot user {username}')
        return True
    except Exception as e:
        logger.error(f'create_hotspot_user failed for {username}: {e}')
        return False
    finally:
        safe_close(api)


# Consolidated helpers

def grant_user_access(username: str, mac_address: Optional[str] = None, password: Optional[str] = None, profile: Optional[str] = None, comment: str = 'Paid user') -> dict:
    """Create/update hotspot user, optionally bypass MAC, and return status dict."""
    result = {'user_created': False, 'mac_bypassed': False, 'errors': []}
    if password is None:
        password = username  # simple fallback
    try:
        # Use the hotspot-aware user creation
        user_ok = create_hotspot_user_with_server(username, password, profile)
        result['user_created'] = user_ok
    except Exception as e:
        logger.error(f'grant_user_access: create_hotspot_user_with_server failed for {username}: {e}')
        result['errors'].append(f'user:{e}')
    if mac_address:
        try:
            mac_ok = allow_mac(mac_address, comment=comment)
            result['mac_bypassed'] = mac_ok
            if not mac_ok:
                result['errors'].append('mac:bypass_failed')
        except Exception as e:
            logger.error(f'grant_user_access: allow_mac failed for {mac_address}: {e}')
            result['errors'].append(f'mac:{e}')
    result['success'] = result['user_created'] or result['mac_bypassed']
    return result


def revoke_user_access(mac_address: Optional[str] = None, username: Optional[str] = None) -> dict:
    """Revoke MAC bypass and optionally disable hotspot user."""
    result = {'mac_revoked': False, 'user_revoked': False, 'errors': []}
    if mac_address:
        try:
            result['mac_revoked'] = revoke_mac(mac_address)
            if not result['mac_revoked']:
                result['errors'].append('mac:revoke_failed')
        except Exception as e:
            logger.error(f'revoke_user_access: revoke_mac failed for {mac_address}: {e}')
            result['errors'].append(f'mac:{e}')
    if username and routeros_api is not None:
        try:
            api = get_mikrotik_api()
            users = api.get_resource('/ip/hotspot/user')
            existing = users.get(name=username)
            for item in existing:
                users.set(id=item['.id'], disabled='yes')
                result['user_revoked'] = True
            safe_close(api)
        except Exception as e:
            logger.error(f'revoke_user_access: disable user failed for {username}: {e}')
            result['errors'].append(f'user:{e}')
    result['success'] = result['mac_revoked'] or result['user_revoked']
    return result


def authenticate_user_with_mikrotik(phone_number: str, mac_address: str = '', ip_address: str = '') -> dict:
    """Authenticate (provision) user on MikroTik using routeros-api."""
    try:
        access = grant_user_access(phone_number, mac_address=mac_address, password=phone_number, comment='auth')
        return {
            'success': access.get('success', False),
            'message': 'User provisioned on router' if access.get('success') else 'Provisioning failed',
            'details': access
        }
    except Exception as e:
        logger.error(f'authenticate_user_with_mikrotik failed for {phone_number}: {e}')
        return {'success': False, 'message': str(e)}


def logout_user_from_mikrotik(phone_number: str, mac_address: str = '') -> dict:
    """Disable user / revoke MAC."""
    try:
        result = revoke_user_access(mac_address=mac_address or None, username=phone_number)
        return {
            'success': result.get('success', False),
            'message': 'User revoked' if result.get('success') else 'Revocation failed',
            'details': result
        }
    except Exception as e:
        logger.error(f'logout_user_from_mikrotik failed for {phone_number}: {e}')
        return {'success': False, 'message': str(e)}


def test_mikrotik_connection(host=None, username=None, password=None, port=8728):
    """Test low-level TCP connectivity to MikroTik API port."""
    try:
        host = host or getattr(settings, 'MIKROTIK_HOST', getattr(settings, 'MIKROTIK_ROUTER_IP', '10.50.0.2'))
        username = username or getattr(settings, 'MIKROTIK_USER', getattr(settings, 'MIKROTIK_ADMIN_USER', 'admin'))
        password = password or getattr(settings, 'MIKROTIK_PASSWORD', getattr(settings, 'MIKROTIK_ADMIN_PASS', ''))

        # Socket connectivity
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(5)
        result = test_socket.connect_ex((host, port))
        test_socket.close()

        api_status = 'unverified'
        if result == 0 and routeros_api is not None:
            try:
                api = get_mikrotik_api()
                # simple call to list users (non-fatal)
                api.get_resource('/ip/hotspot/user').get()  # may be empty
                api_status = 'api_ok'
            except Exception as e:
                api_status = f'api_error:{e}'
            finally:
                try:
                    safe_close(api)
                except Exception:
                    pass

        return {
            'success': result == 0,
            'message': 'Connection successful' if result == 0 else f'Cannot connect to {host}:{port}',
            'router_info': {
                'ip': host,
                'port': port,
                'status': 'reachable' if result == 0 else 'unreachable',
                'api_status': api_status
            }
        }
    except Exception as e:
        logger.error(f'Error testing MikroTik connection: {e}')
        return {'success': False, 'error': str(e)}


def get_router_info():
    """Get basic router info via /system/resource/print."""
    try:
        api = None
        info = {}
        if routeros_api is not None:
            try:
                api = get_mikrotik_api()
                resource = api.get_resource('/system/resource')
                data = resource.get()
                if data:
                    d = data[0]
                    info = {
                        'uptime': d.get('uptime'),
                        'version': d.get('version'),
                        'board_name': d.get('board-name'),
                        'platform': d.get('platform'),
                        'cpu_load': d.get('cpu-load'),
                        'free_memory': d.get('free-memory'),
                        'total_memory': d.get('total-memory')
                    }
            except Exception as e:
                logger.warning(f'get_router_info API error: {e}')
            finally:
                safe_close(api)
        connection_test = test_mikrotik_connection()
        info['connection_status'] = 'connected' if connection_test['success'] else 'disconnected'
        return {'success': True, 'data': info}
    except Exception as e:
        logger.error(f'Error getting router info: {e}')
        return {'success': False, 'error': str(e)}


def get_active_hotspot_users():
    """List active hotspot users using /ip/hotspot/active."""
    try:
        api = get_mikrotik_api()
        active = api.get_resource('/ip/hotspot/active').get()
        users = []
        for u in active:
            users.append({
                'user': u.get('user'),
                'address': u.get('address'),
                'mac_address': u.get('mac-address'),
                'uptime': u.get('uptime'),
                'session_time_left': u.get('session-time-left'),
                'bytes_in': u.get('bytes-in'),
                'bytes_out': u.get('bytes-out')
            })
        return {'success': True, 'data': users}
    except Exception as e:
        logger.error(f'Error getting active users: {e}')
        return {'success': False, 'error': str(e)}
    finally:
        try:
            safe_close(api)
        except Exception:
            pass


def disconnect_all_hotspot_users():
    """Disconnect all active users via /ip/hotspot/active remove."""
    api = None
    try:
        api = get_mikrotik_api()
        resource = api.get_resource('/ip/hotspot/active')
        active = resource.get()
        count = 0
        for u in active:
            try:
                resource.remove(id=u['.id'])
                count += 1
            except Exception as rem_err:
                logger.warning(f'Failed to remove user {u.get("user")}: {rem_err}')
        return {'success': True, 'count': count, 'message': f'Disconnected {count} users'}
    except Exception as e:
        logger.error(f'Error disconnecting users: {e}')
        return {'success': False, 'error': str(e)}
    finally:
        if api is not None:
            safe_close(api)


def reboot_router():
    """Reboot router (simulated unless explicit setting allows)."""
    api = None
    try:
        if not getattr(settings, 'ALLOW_ROUTER_REBOOT', False):
            return {'success': False, 'message': 'Reboot disabled by settings'}
        api = get_mikrotik_api()
        try:
            # RouterOS reboot command
            api.get_resource('/system/reboot').call('')  # library-specific call, may vary
            return {'success': True, 'message': 'Router reboot issued'}
        except Exception as e:
            logger.error(f'Reboot command failed: {e}')
            return {'success': False, 'error': str(e)}
        finally:
            if api is not None:
                safe_close(api)
    except Exception as outer:
        return {'success': False, 'error': str(outer)}


def get_hotspot_profiles():
    """Get hotspot user profiles via /ip/hotspot/user/profile."""
    api = None
    try:
        api = get_mikrotik_api()
        profiles = api.get_resource('/ip/hotspot/user/profile').get()
        data = []
        for p in profiles:
            data.append({
                'name': p.get('name'),
                'rate_limit': p.get('rate-limit'),
                'shared_users': p.get('shared-users'),
                'session_timeout': p.get('session-timeout'),
                'idle_timeout': p.get('idle-timeout')
            })
        return {'success': True, 'data': data}
    except Exception as e:
        logger.error(f'Error getting hotspot profiles: {e}')
        return {'success': False, 'error': str(e)}
    finally:
        if api is not None:
            safe_close(api)


def create_hotspot_profile(name, rate_limit='512k/512k', session_timeout='1d', idle_timeout='5m'):
    """Create hotspot profile using routeros-api (fields mapped to RouterOS)."""
    api = None
    try:
        api = get_mikrotik_api()
        res = api.get_resource('/ip/hotspot/user/profile')
        res.add(name=name, **{
            'rate-limit': rate_limit,
            'session-timeout': session_timeout,
            'idle-timeout': idle_timeout
        })
        return {'success': True, 'data': {'name': name, 'rate_limit': rate_limit}, 'message': 'Profile created'}
    except Exception as e:
        logger.error(f'Error creating hotspot profile {name}: {e}')
        return {'success': False, 'error': str(e)}
    finally:
        if api is not None:
            safe_close(api)


# Advanced management helpers (no usage limiting)

def list_bypass_bindings() -> dict:
    """Return all bypass (and other) ip-bindings."""
    try:
        api = get_mikrotik_api()
        bindings = api.get_resource('/ip/hotspot/ip-binding').get()
        data = []
        for b in bindings:
            data.append({
                'id': b.get('.id'),
                'mac_address': b.get('mac-address'),
                'type': b.get('type'),
                'comment': b.get('comment')
            })
        return {'success': True, 'data': data}
    except Exception as e:
        logger.error(f'list_bypass_bindings error: {e}')
        return {'success': False, 'error': str(e)}
    finally:
        try:
            safe_close(api)
        except Exception:
            pass


def sync_user_provisioning(usernames: List[str]) -> dict:
    """Ensure all provided usernames exist as hotspot users (no limits)."""
    summary = {'created': 0, 'updated': 0, 'errors': []}
    for u in usernames:
        try:
            ok = create_hotspot_user(u, password=u)
            if ok:
                summary['created'] += 1  # treat as created/updated, we don't distinguish
        except Exception as e:
            summary['errors'].append(f'{u}:{e}')
    summary['success'] = len(summary['errors']) == 0
    return summary


def cleanup_disabled_users() -> dict:
    """Remove disabled hotspot users (housekeeping)."""
    api = None
    try:
        api = get_mikrotik_api()
        users = api.get_resource('/ip/hotspot/user')
        existing = users.get()
        removed = 0
        for u in existing:
            if u.get('disabled') == 'true' or u.get('disabled') == 'yes':
                try:
                    users.remove(id=u['.id'])
                    removed += 1
                except Exception as inner:
                    logger.warning(f'Failed removing disabled user {u.get("name")}: {inner}')
        return {'success': True, 'removed': removed}
    except Exception as e:
        logger.error(f'cleanup_disabled_users error: {e}')
        return {'success': False, 'error': str(e)}
    finally:
        if api is not None:
            safe_close(api)


def get_router_health() -> dict:
    """Fetch health metrics if available (/system/health)."""
    api = None
    try:
        api = get_mikrotik_api()
        health_res = api.get_resource('/system/health')
        data = health_res.get()
        return {'success': True, 'data': data}
    except Exception as e:
        logger.error(f'get_router_health error: {e}')
        return {'success': False, 'error': str(e)}
    finally:
        if api is not None:
            safe_close(api)


def monitor_interface_traffic(interface: str, once: bool = True) -> dict:
    """Monitor traffic for a given interface (single snapshot)."""
    api = None
    try:
        api = get_mikrotik_api()
        monitor = api.get_resource('/interface/monitor-traffic')
        args = {'interface': interface, 'once': 'yes' if once else 'no'}
        # routeros_api may require .call('monitor-traffic', **params), but using get_resource path wrapper
        data = monitor.call(**args)
        return {'success': True, 'data': data}
    except Exception as e:
        logger.error(f'monitor_interface_traffic error for {interface}: {e}')
        return {'success': False, 'error': str(e)}
    finally:
        if api is not None:
            safe_close(api)


def trigger_immediate_hotspot_login(phone_number, mac_address, ip_address):
    """Provision user immediately after voucher redemption enforcing user.max_devices."""
    try:
        device_tracked = False
        device_limit_exceeded = False
        try:
            from .models import User, Device
            user = User.objects.get(phone_number=phone_number)
            device, created = Device.objects.get_or_create(
                user=user,
                mac_address=mac_address,
                defaults={
                    'ip_address': ip_address,
                    'is_active': True,
                    'device_name': f'Device-{mac_address[-8:]}',
                    'first_seen': timezone.now()
                }
            )
            if not created:
                device.ip_address = ip_address
                device.is_active = True
                device.last_seen = timezone.now()
                device.save()
            else:
                # Enforce max devices (default expected 1)
                active_devices = user.get_active_devices().count()
                if active_devices > user.max_devices:
                    # Deactivate this newly added device
                    device.is_active = False
                    device.save()
                    device_limit_exceeded = True
            device_tracked = True
            if device_limit_exceeded:
                return {
                    'success': False,
                    'message': f'Device limit exceeded (max {user.max_devices})',
                    'method': 'device_limit_exceeded',
                    'device_tracked': True,
                    'device_limit_exceeded': True
                }
        except Exception as de:
            logger.error(f'Device tracking error for {phone_number}: {de}')

        access = grant_user_access(phone_number, mac_address=mac_address, password=phone_number, comment='voucher')
        if access.get('success'):
            return {
                'success': True,
                'message': 'Access granted (bypassed / user created)',
                'method': 'routeros_api',
                'device_tracked': device_tracked,
                'details': access
            }
        return {
            'success': False,
            'message': 'Access provisioning failed',
            'method': 'routeros_api',
            'device_tracked': device_tracked,
            'details': access
        }
    except Exception as e:
        logger.error(f'trigger_immediate_hotspot_login error for {phone_number}: {e}')
        return {'success': False, 'message': str(e), 'method': 'error', 'device_tracked': False}


def track_device_connection(phone_number, mac_address, ip_address, connection_type='wifi', access_method='unknown'):
    """Track device connection enforcing user.max_devices (default 1)."""
    try:
        from .models import User, Device
        from django.utils import timezone
        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            logger.error(f'Device tracking failed: User {phone_number} not found')
            return {'success': False, 'message': 'User not found', 'device_tracked': False}
        device, device_created = Device.objects.get_or_create(
            user=user,
            mac_address=mac_address,
            defaults={'ip_address': ip_address, 'is_active': True, 'device_name': f'Device-{mac_address[-8:]}', 'first_seen': timezone.now()}
        )
        if device_created:
            active_devices = user.get_active_devices().count()
            if active_devices > user.max_devices:
                device.is_active = False
                device.save()
                logger.warning(f'Device limit exceeded for {phone_number}: {active_devices}/{user.max_devices}')
                device_info = {
                    'device_id': device.id,
                    'mac_address': mac_address,
                    'ip_address': ip_address,
                    'device_name': device.device_name,
                    'is_new_device': True,
                    'first_seen': device.first_seen.isoformat(),
                    'last_seen': device.last_seen.isoformat(),
                    'connection_type': connection_type,
                    'access_method': access_method
                }
                return {
                    'success': False,
                    'message': f'Device limit exceeded. Max {user.max_devices} device(s) allowed.',
                    'device_tracked': True,
                    'device_info': device_info,
                    'device_limit_exceeded': True,
                    'active_devices': active_devices,
                    'max_devices': user.max_devices
                }
        else:
            device.ip_address = ip_address
            device.is_active = True
            device.last_seen = timezone.now()
            device.save()
        device_info = {
            'device_id': device.id,
            'mac_address': mac_address,
            'ip_address': ip_address,
            'device_name': device.device_name,
            'is_new_device': device_created,
            'first_seen': device.first_seen.isoformat(),
            'last_seen': device.last_seen.isoformat(),
            'connection_type': connection_type,
            'access_method': access_method,
            'active_devices': user.get_active_devices().count(),
            'max_devices': user.max_devices
        }
        return {'success': True, 'message': 'Device connection tracked', 'device_tracked': True, 'device_info': device_info, 'device_limit_exceeded': False}
    except Exception as e:
        logger.error(f'Error tracking device connection for {phone_number}: {e}')
        return {'success': False, 'message': f'Device tracking error: {e}', 'device_tracked': False}


def enhance_device_tracking_for_payment(payment_user, mac_address, ip_address):
    """
    Enhanced device tracking specifically for payment users
    
    Args:
        payment_user: User object who made payment
        mac_address: Device MAC address
        ip_address: Device IP address
    
    Returns:
        dict: Device tracking result
    """
    try:
        if not mac_address:
            logger.warning(f'Payment device tracking: No MAC address provided for {payment_user.phone_number}')
            return {'success': False, 'message': 'No MAC address provided', 'device_tracked': False}
        result = track_device_connection(payment_user.phone_number, mac_address, ip_address, connection_type='wifi', access_method='payment')
        if result['success']:
            logger.info(f'Payment device tracking successful for {payment_user.phone_number}: {mac_address}')
        else:
            logger.warning(f'Payment device tracking failed for {payment_user.phone_number}: {result["message"]}')
        return result
    except Exception as e:
        logger.error(f'Error in payment device tracking for {payment_user.phone_number}: {e}')
        return {'success': False, 'message': f'Payment device tracking error: {e}', 'device_tracked': False}


def enhance_device_tracking_for_voucher(voucher_user, mac_address, ip_address):
    """
    Enhanced device tracking specifically for voucher users
    
    Args:
        voucher_user: User object who redeemed voucher
        mac_address: Device MAC address
        ip_address: Device IP address
    
    Returns:
        dict: Device tracking result
    """
    try:
        if not mac_address:
            logger.warning(f'Voucher device tracking: No MAC address provided for {voucher_user.phone_number}')
            return {'success': False, 'message': 'No MAC address provided', 'device_tracked': False}
        result = track_device_connection(voucher_user.phone_number, mac_address, ip_address, connection_type='wifi', access_method='voucher')
        if result['success']:
            logger.info(f'Voucher device tracking successful for {voucher_user.phone_number}: {mac_address}')
        else:
            logger.warning(f'Voucher device tracking failed for {voucher_user.phone_number}: {result["message"]}')
        return result
    except Exception as e:
        logger.error(f'Error in voucher device tracking for {voucher_user.phone_number}: {e}')
        return {'success': False, 'message': f'Voucher device tracking error: {e}', 'device_tracked': False}


def list_interfaces() -> dict:
    """List MikroTik interfaces and return details suitable for printing."""
    api = None
    try:
        api = get_mikrotik_api()
        res = api.get_resource('/interface')
        items = res.get()
        data = []
        for it in items:
            data.append({
                'name': it.get('name'),
                'type': it.get('type'),
                'mac_address': it.get('mac-address'),
                'mtu': it.get('mtu'),
                'running': it.get('running'),
                'disabled': it.get('disabled'),
            })
        return {'success': True, 'data': data}
    except Exception as e:
        logger.error(f'list_interfaces error: {e}')
        return {'success': False, 'error': str(e)}
    finally:
        safe_close(api)


def get_hotspot_interfaces() -> dict:
    """List hotspot interfaces from /ip/hotspot."""
    api = None
    try:
        api = get_mikrotik_api()
        res = api.get_resource('/ip/hotspot')
        items = res.get()
        data = []
        for item in items:
            data.append({
                'name': item.get('name'),
                'interface': item.get('interface'),
                'address_pool': item.get('address-pool'),
                'profile': item.get('profile'),
                'idle_timeout': item.get('idle-timeout'),
                'disabled': item.get('disabled'),
            })
        return {'success': True, 'data': data}
    except Exception as e:
        logger.error(f'get_hotspot_interfaces error: {e}')
        return {'success': False, 'error': str(e)}
    finally:
        safe_close(api)


def get_hotspot_active_users_by_interface(hotspot_name: str = None) -> dict:
    """Get active users for a specific hotspot interface."""
    if not hotspot_name:
        hotspot_name = getattr(settings, 'MIKROTIK_HOTSPOT_NAME', 'hotspot1')
    
    api = None
    try:
        api = get_mikrotik_api()
        active = api.get_resource('/ip/hotspot/active').get()
        users = []
        for u in active:
            # Filter by hotspot server if specified
            if hotspot_name and u.get('server') != hotspot_name:
                continue
            users.append({
                'user': u.get('user'),
                'server': u.get('server'),
                'address': u.get('address'),
                'mac_address': u.get('mac-address'),
                'uptime': u.get('uptime'),
                'session_time_left': u.get('session-time-left'),
                'bytes_in': u.get('bytes-in'),
                'bytes_out': u.get('bytes-out')
            })
        return {'success': True, 'data': users, 'hotspot': hotspot_name}
    except Exception as e:
        logger.error(f'Error getting active users for hotspot {hotspot_name}: {e}')
        return {'success': False, 'error': str(e), 'hotspot': hotspot_name}
    finally:
        safe_close(api)


def create_hotspot_user_with_server(username: str, password: str, profile: Optional[str] = None, server: str = None) -> bool:
    """Create or update /ip/hotspot/user entry with specific server."""
    if not username:
        return False
    
    api = get_mikrotik_api()
    try:
        profile = profile or getattr(settings, 'MIKROTIK_DEFAULT_PROFILE', 'default')
        server = server or getattr(settings, 'MIKROTIK_HOTSPOT_NAME', 'hotspot1')
        
        users = api.get_resource('/ip/hotspot/user')
        exist = users.get(name=username)
        
        if exist:
            for item in exist:
                if '.id' in item:
                    users.set(id=item['.id'], password=password, profile=profile, server=server, disabled='no')
            logger.info(f'Updated hotspot user {username} on server {server}')
            return True
        
        users.add(name=username, password=password, profile=profile, server=server, disabled='no')
        logger.info(f'Created hotspot user {username} on server {server}')
        return True
    except Exception as e:
        logger.error(f'create_hotspot_user_with_server failed for {username}: {e}')
        return False
    finally:
        safe_close(api)


# Example usage function for quick manual testing
def print_interfaces():
    """Fetch and print interface details to stdout (for ad-hoc testing)."""
    result = list_interfaces()
    if result.get('success'):
        for i, it in enumerate(result['data'], 1):
            print(f"{i}. {it['name']}\tType: {it.get('type')}\tMAC: {it.get('mac_address')}\tRunning: {it.get('running')}\tDisabled: {it.get('disabled')}")
    else:
        print('Failed to list interfaces:', result.get('error'))

