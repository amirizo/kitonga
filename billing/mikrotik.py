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
MIKROTIK_MOCK_MODE = os.getenv("MIKROTIK_MOCK_MODE", "false").lower() == "true"

# Resolve SSL verify preference from Django settings (default False for self-signed)
SSL_VERIFY = bool(getattr(settings, "MIKROTIK_SSL_VERIFY", False))


def safe_close(api):
    """Safely close routeros_api communicator if present."""
    try:
        if api:
            api.get_communicator().close()
    except Exception:
        pass


def get_mikrotik_api(retries: int = 3, timeout: int = 10):
    """
    Return an authenticated RouterOS API connection using env-driven settings.
    Caller should close with api.get_communicator().close() in a finally block.

    Args:
        retries: Number of connection attempts before giving up
        timeout: Socket timeout in seconds
    """
    if MIKROTIK_MOCK_MODE:
        raise ConnectionRefusedError(
            "MikroTik router not accessible in this environment. Configure VPN or set MIKROTIK_MOCK_MODE=false"
        )

    if routeros_api is None:
        raise ImportError("routeros-api is not installed. Add it to requirements.txt")

    host = getattr(settings, "MIKROTIK_HOST", "10.50.0.2")
    port = int(getattr(settings, "MIKROTIK_PORT", 8728))
    user = getattr(settings, "MIKROTIK_USER", "admin")
    password = getattr(settings, "MIKROTIK_PASSWORD", "Kijangwani2003")
    use_ssl = bool(getattr(settings, "MIKROTIK_USE_SSL", False))

    # Set socket timeout for the connection
    original_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)

    last_error = None
    for attempt in range(retries):
        try:
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

            api = pool.get_api()
            socket.setdefaulttimeout(original_timeout)  # Restore timeout
            logger.debug(
                f"MikroTik API connected successfully on attempt {attempt + 1}"
            )
            return api

        except Exception as e:
            last_error = e
            logger.warning(
                f"MikroTik connection attempt {attempt + 1}/{retries} failed: {e}"
            )
            if attempt < retries - 1:
                import time

                time.sleep(1)  # Wait 1 second before retry

    socket.setdefaulttimeout(original_timeout)  # Restore timeout
    raise last_error or Exception("Failed to connect to MikroTik router")


def get_tenant_mikrotik_api(router, retries: int = 3, timeout: int = 10):
    """
    Return an authenticated RouterOS API connection for a specific tenant's router.

    Args:
        router: Router model instance with host, port, username, password, use_ssl
        retries: Number of connection attempts before giving up
        timeout: Socket timeout in seconds

    Returns:
        RouterOS API object or None if connection fails
    """
    if MIKROTIK_MOCK_MODE:
        logger.warning("MikroTik mock mode enabled, cannot connect to tenant router")
        return None

    if routeros_api is None:
        raise ImportError("routeros-api is not installed. Add it to requirements.txt")

    host = router.host
    port = int(router.port) if router.port else 8728
    user = router.username
    password = router.password
    use_ssl = bool(router.use_ssl) if hasattr(router, "use_ssl") else False

    # Set socket timeout for the connection
    original_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)

    last_error = None
    for attempt in range(retries):
        try:
            try:
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
                pool = routeros_api.RouterOsApiPool(
                    host,
                    username=user,
                    password=password,
                    port=port,
                    use_ssl=use_ssl,
                    plaintext_login=True,
                    ssl_verify=SSL_VERIFY,
                )

            api = pool.get_api()
            socket.setdefaulttimeout(original_timeout)
            logger.debug(
                f"Tenant MikroTik API connected to {host}:{port} on attempt {attempt + 1}"
            )
            return api

        except Exception as e:
            last_error = e
            logger.warning(
                f"Tenant MikroTik connection attempt {attempt + 1}/{retries} to {host}:{port} failed: {e}"
            )
            if attempt < retries - 1:
                import time

                time.sleep(1)

    socket.setdefaulttimeout(original_timeout)
    logger.error(f"Failed to connect to tenant router {host}:{port}: {last_error}")
    return None


def disconnect_user_with_api(api, username: str, mac_address: str = None) -> dict:
    """
    Disconnect a user from MikroTik hotspot using a provided API connection.
    Used for tenant-specific router disconnection.

    Args:
        api: RouterOS API connection object
        username: Phone number (hotspot username)
        mac_address: Optional MAC address for more targeted removal

    Returns:
        dict with disconnect results
    """
    result = {
        "success": False,
        "session_removed": False,
        "binding_removed": False,
        "user_disabled": False,
        "errors": [],
    }

    if api is None:
        result["errors"].append("No API connection")
        return result

    try:
        # Step 1: Remove active sessions
        try:
            active = api.get_resource("/ip/hotspot/active")
            all_sessions = active.get()

            for session in all_sessions:
                session_user = session.get("user", "")
                session_mac = session.get("mac-address", "")

                should_remove = False
                if username and session_user == username:
                    should_remove = True
                if mac_address and session_mac.upper() == mac_address.upper():
                    should_remove = True

                if should_remove:
                    try:
                        session_id = session.get(".id") or session.get("id")
                        if session_id:
                            active.remove(id=session_id)
                            result["session_removed"] = True
                            logger.info(
                                f"Removed active session for {username}: {session_mac}"
                            )
                    except Exception as rem_err:
                        result["errors"].append(f"session_remove: {rem_err}")

        except Exception as e:
            result["errors"].append(f"active_sessions: {e}")

        # Step 2: Remove IP bindings
        try:
            bindings = api.get_resource("/ip/hotspot/ip-binding")

            if mac_address:
                binding_list = bindings.get(mac_address=mac_address)
                for binding in binding_list:
                    try:
                        bindings.remove(id=binding[".id"])
                        result["binding_removed"] = True
                        logger.info(f"Removed IP binding for {mac_address}")
                    except Exception:
                        pass

            all_bindings = bindings.get()
            for binding in all_bindings:
                comment = binding.get("comment", "") or ""
                if username in comment:
                    try:
                        bindings.remove(id=binding[".id"])
                        result["binding_removed"] = True
                    except Exception:
                        pass

        except Exception as e:
            result["errors"].append(f"ip_bindings: {e}")

        # Step 3: Disable hotspot user
        try:
            users = api.get_resource("/ip/hotspot/user")
            # Get all users and filter manually - more reliable across API versions
            all_users = users.get()
            user_found = False

            # Log all users for debugging
            logger.debug(
                f"Looking for username: '{username}' among {len(all_users)} hotspot users"
            )

            for user in all_users:
                user_name = user.get("name", "")
                # Try exact match first, then normalized match
                if user_name == username or user_name == username.lstrip("+"):
                    user_found = True
                    try:
                        user_id = user.get(".id") or user.get("id")
                        if user_id:
                            users.set(id=user_id, disabled="yes")
                            result["user_disabled"] = True
                            logger.info(
                                f"Disabled hotspot user: {username} (router user: {user_name}, id: {user_id})"
                            )
                    except Exception as disable_err:
                        logger.error(
                            f"Failed to disable user {username}: {disable_err}"
                        )
                        result["errors"].append(f"disable_user_set: {disable_err}")

            if not user_found:
                # Log available usernames to help debug
                available_users = [
                    u.get("name", "?") for u in all_users[:10]
                ]  # First 10
                logger.warning(
                    f"Hotspot user not found: '{username}'. Available users (sample): {available_users}"
                )
                result["errors"].append(f"user_not_found: {username}")

        except Exception as e:
            logger.error(f"Failed to get/disable hotspot user {username}: {e}")
            result["errors"].append(f"disable_user: {e}")

        # Consider success if any operation worked
        result["success"] = (
            result["session_removed"]
            or result["binding_removed"]
            or result["user_disabled"]
        )

    except Exception as e:
        result["errors"].append(f"general: {e}")

    return result


# =============================================================================
# MULTI-TENANT FUNCTIONS - Use these for production multi-tenant SaaS
# =============================================================================


def allow_mac_on_router(api, mac_address: str, comment: str = "Paid user") -> bool:
    """Create/ensure bypass binding for a MAC on a specific router (tenant-aware).

    Args:
        api: RouterOS API connection object (from get_tenant_mikrotik_api)
        mac_address: MAC address to bypass
        comment: Comment for the binding

    Returns:
        bool: True if successful, False otherwise
    """
    if not mac_address or api is None:
        return False

    try:
        bindings = api.get_resource("/ip/hotspot/ip-binding")
        existing = bindings.get(mac_address=mac_address)

        if existing:
            for item in existing:
                binding_id = item.get(".id") or item.get("id")
                if binding_id:
                    bindings.set(
                        id=binding_id,
                        type="bypassed",
                        comment=comment,
                        mac_address=mac_address,
                    )
            logger.info(f"Updated bypass binding for {mac_address}")
            return True

        bindings.add(type="bypassed", mac_address=mac_address, comment=comment)
        logger.info(f"Created bypass binding for {mac_address}")
        return True
    except Exception as e:
        logger.error(f"allow_mac_on_router failed for {mac_address}: {e}")
        return False


def revoke_mac_on_router(api, mac_address: str) -> bool:
    """Remove any /ip/hotspot/ip-binding entries for a MAC on specific router (tenant-aware).

    Args:
        api: RouterOS API connection object
        mac_address: MAC address to revoke

    Returns:
        bool: True if successful, False otherwise
    """
    if not mac_address or api is None:
        return False

    try:
        bindings = api.get_resource("/ip/hotspot/ip-binding")
        items = bindings.get(mac_address=mac_address)

        if not items:
            logger.info(f"No bindings found for {mac_address}")
            return True

        count = 0
        for item in items:
            binding_id = item.get(".id") or item.get("id")
            if binding_id:
                bindings.remove(id=binding_id)
                count += 1

        logger.info(f"Revoked {count} binding(s) for {mac_address}")
        return True
    except Exception as e:
        logger.error(f"revoke_mac_on_router failed for {mac_address}: {e}")
        return False


def create_hotspot_user_on_router(
    api, username: str, password: str, profile: Optional[str] = None
) -> bool:
    """Create or update /ip/hotspot/user entry on a specific router (tenant-aware).

    Args:
        api: RouterOS API connection object
        username: Hotspot username (usually phone number)
        password: Hotspot password
        profile: MikroTik user profile (default from settings)

    Returns:
        bool: True if successful, False otherwise
    """
    if not username or api is None:
        return False

    try:
        profile = profile or getattr(settings, "MIKROTIK_DEFAULT_PROFILE", "default")
        users = api.get_resource("/ip/hotspot/user")
        exist = users.get(name=username)

        if exist:
            for item in exist:
                user_id = item.get(".id") or item.get("id")
                if user_id:
                    users.set(
                        id=user_id, password=password, profile=profile, disabled="no"
                    )
                    logger.info(f"Updated and RE-ENABLED hotspot user {username}")
            return True

        users.add(name=username, password=password, profile=profile, disabled="no")
        logger.info(f"Created hotspot user {username}")
        return True
    except Exception as e:
        logger.error(f"create_hotspot_user_on_router failed for {username}: {e}")
        return False


def grant_user_access_on_router(
    router,
    username: str,
    mac_address: Optional[str] = None,
    password: Optional[str] = None,
    profile: Optional[str] = None,
    comment: str = "Paid user",
) -> dict:
    """Grant user access on a specific tenant's router.

    This is the MULTI-TENANT version of grant_user_access().

    Args:
        router: Router model instance with connection details
        username: Phone number (hotspot username)
        mac_address: Optional MAC address for bypass binding
        password: Optional password (defaults to username)
        profile: MikroTik user profile
        comment: Comment for the binding

    Returns:
        dict: Result with user_created, mac_bypassed, errors, success
    """
    result = {
        "user_created": False,
        "mac_bypassed": False,
        "errors": [],
        "router_id": router.id if router else None,
    }

    if password is None:
        password = username

    api = get_tenant_mikrotik_api(router)
    if api is None:
        result["errors"].append(f"Cannot connect to router {router.host}:{router.port}")
        return result

    try:
        # Create/update hotspot user
        try:
            user_ok = create_hotspot_user_on_router(api, username, password, profile)
            result["user_created"] = user_ok
        except Exception as e:
            logger.error(
                f"grant_user_access_on_router: create_hotspot_user failed for {username}: {e}"
            )
            result["errors"].append(f"user:{e}")

        # Create MAC bypass binding
        if mac_address:
            try:
                mac_ok = allow_mac_on_router(api, mac_address, comment=comment)
                result["mac_bypassed"] = mac_ok
                if not mac_ok:
                    result["errors"].append("mac:bypass_failed")
            except Exception as e:
                logger.error(
                    f"grant_user_access_on_router: allow_mac failed for {mac_address}: {e}"
                )
                result["errors"].append(f"mac:{e}")

        result["success"] = result["user_created"] or result["mac_bypassed"]
    finally:
        safe_close(api)

    return result


def revoke_user_access_on_router(
    router, mac_address: Optional[str] = None, username: Optional[str] = None
) -> dict:
    """Revoke user access on a specific tenant's router.

    This is the MULTI-TENANT version of revoke_user_access().
    Revokes MAC bypass, disables hotspot user, AND kicks active session.

    Args:
        router: Router model instance with connection details
        mac_address: MAC address to revoke
        username: Username (phone number) to disable/kick

    Returns:
        dict: Result with mac_revoked, user_revoked, session_kicked, errors, success
    """
    result = {
        "mac_revoked": False,
        "user_revoked": False,
        "session_kicked": False,
        "errors": [],
        "router_id": router.id if router else None,
    }

    api = get_tenant_mikrotik_api(router)
    if api is None:
        result["errors"].append(f"Cannot connect to router {router.host}:{router.port}")
        return result

    try:
        # Step 1: Revoke MAC binding
        if mac_address:
            try:
                result["mac_revoked"] = revoke_mac_on_router(api, mac_address)
                if not result["mac_revoked"]:
                    result["errors"].append("mac:revoke_failed")
            except Exception as e:
                logger.error(
                    f"revoke_user_access_on_router: revoke_mac failed for {mac_address}: {e}"
                )
                result["errors"].append(f"mac:{e}")

        # Step 2: Disable hotspot user
        if username:
            try:
                users = api.get_resource("/ip/hotspot/user")
                all_users = users.get()
                for item in all_users:
                    if item.get("name") == username:
                        user_id = item.get(".id") or item.get("id")
                        if user_id:
                            users.set(id=user_id, disabled="yes")
                            result["user_revoked"] = True
                            logger.info(f"Disabled hotspot user: {username}")
            except Exception as e:
                logger.error(
                    f"revoke_user_access_on_router: disable user failed for {username}: {e}"
                )
                result["errors"].append(f"user:{e}")

        # Step 3: Kick active session
        try:
            active = api.get_resource("/ip/hotspot/active")
            active_sessions = active.get()

            for session in active_sessions:
                session_user = session.get("user", "")
                session_mac = session.get("mac-address", "")

                should_kick = False
                if username and session_user == username:
                    should_kick = True
                if mac_address and session_mac.upper() == mac_address.upper():
                    should_kick = True

                if should_kick:
                    try:
                        session_id = session.get(".id") or session.get("id")
                        if session_id:
                            active.remove(id=session_id)
                            result["session_kicked"] = True
                            logger.info(
                                f"Kicked active session: user={session_user}, mac={session_mac}"
                            )
                    except Exception as kick_err:
                        logger.error(
                            f"Failed to kick session {session_user}: {kick_err}"
                        )
                        result["errors"].append(f"kick:{kick_err}")
        except Exception as e:
            logger.error(
                f"revoke_user_access_on_router: kick active session failed: {e}"
            )
            result["errors"].append(f"active:{e}")

        result["success"] = (
            result["mac_revoked"] or result["user_revoked"] or result["session_kicked"]
        )
    finally:
        safe_close(api)

    return result


def authenticate_user_on_tenant_routers(
    user, mac_address: str = "", ip_address: str = ""
) -> dict:
    """Authenticate (provision) user on ALL of the tenant's routers.

    This is the MULTI-TENANT version of authenticate_user_with_mikrotik().

    Args:
        user: User model instance (has tenant FK)
        mac_address: MAC address for bypass binding
        ip_address: IP address (for logging)

    Returns:
        dict: Result with success, router_results, message
    """
    result = {
        "success": False,
        "router_results": [],
        "message": "",
        "routers_tried": 0,
        "routers_succeeded": 0,
    }

    if not user or not user.tenant:
        result["message"] = "User has no tenant assigned"
        return result

    # Import Router model here to avoid circular imports
    from .models import Router

    # Get all active routers for this tenant
    routers = Router.objects.filter(tenant=user.tenant, is_active=True)

    if not routers.exists():
        result["message"] = "No active routers found for tenant"
        return result

    # If user has a primary router, try that first
    if user.primary_router and user.primary_router.is_active:
        routers = list(routers)
        # Move primary router to front
        if user.primary_router in routers:
            routers.remove(user.primary_router)
        routers.insert(0, user.primary_router)

    for router in routers:
        result["routers_tried"] += 1
        try:
            router_result = grant_user_access_on_router(
                router=router,
                username=user.phone_number,
                mac_address=mac_address,
                password=user.phone_number,
                comment=f"Auth: {user.phone_number}",
            )
            router_result["router_name"] = router.name
            router_result["router_host"] = router.host
            result["router_results"].append(router_result)

            if router_result.get("success"):
                result["routers_succeeded"] += 1
        except Exception as e:
            logger.error(
                f"authenticate_user_on_tenant_routers: Failed on router {router.name}: {e}"
            )
            result["router_results"].append(
                {
                    "router_id": router.id,
                    "router_name": router.name,
                    "router_host": router.host,
                    "success": False,
                    "errors": [str(e)],
                }
            )

    result["success"] = result["routers_succeeded"] > 0
    result["message"] = (
        f"Authenticated on {result['routers_succeeded']}/{result['routers_tried']} routers"
        if result["success"]
        else "Failed to authenticate on any router"
    )

    return result


def revoke_user_access_on_tenant_routers(
    user, mac_address: Optional[str] = None
) -> dict:
    """Revoke user access on ALL of the tenant's routers.

    This is the MULTI-TENANT version of revoke_user_access().

    Args:
        user: User model instance (has tenant FK)
        mac_address: MAC address to revoke

    Returns:
        dict: Result with success, router_results, message
    """
    result = {
        "success": False,
        "router_results": [],
        "message": "",
        "routers_tried": 0,
        "routers_succeeded": 0,
    }

    if not user or not user.tenant:
        result["message"] = "User has no tenant assigned"
        return result

    from .models import Router

    routers = Router.objects.filter(tenant=user.tenant, is_active=True)

    if not routers.exists():
        result["message"] = "No active routers found for tenant"
        return result

    for router in routers:
        result["routers_tried"] += 1
        try:
            router_result = revoke_user_access_on_router(
                router=router, mac_address=mac_address, username=user.phone_number
            )
            router_result["router_name"] = router.name
            router_result["router_host"] = router.host
            result["router_results"].append(router_result)

            if router_result.get("success"):
                result["routers_succeeded"] += 1
        except Exception as e:
            logger.error(
                f"revoke_user_access_on_tenant_routers: Failed on router {router.name}: {e}"
            )
            result["router_results"].append(
                {
                    "router_id": router.id,
                    "router_name": router.name,
                    "router_host": router.host,
                    "success": False,
                    "errors": [str(e)],
                }
            )

    result["success"] = result["routers_succeeded"] > 0
    result["message"] = (
        f"Revoked on {result['routers_succeeded']}/{result['routers_tried']} routers"
        if result["success"]
        else "Failed to revoke on any router"
    )

    return result


def force_immediate_internet_access_on_tenant_routers(
    user, mac_address: str, ip_address: str, access_type: str = "payment"
) -> dict:
    """
    Force immediate internet access on ALL of the tenant's routers.

    This is the MULTI-TENANT version of force_immediate_internet_access().

    Args:
        user: User model instance (has tenant FK and phone_number)
        mac_address: MAC address of the device
        ip_address: IP address of the device
        access_type: Type of access ("payment", "voucher")

    Returns:
        dict: Result with success, router_results, message
    """
    result = {
        "success": False,
        "message": "",
        "username": user.phone_number if user else "",
        "mac_address": mac_address,
        "ip_address": ip_address,
        "access_type": access_type,
        "router_results": [],
        "routers_tried": 0,
        "routers_succeeded": 0,
        "errors": [],
    }

    if not user or not user.tenant:
        result["message"] = "User has no tenant assigned"
        result["errors"].append("no_tenant")
        return result

    from .models import Router

    routers = Router.objects.filter(tenant=user.tenant, is_active=True)

    if not routers.exists():
        result["message"] = "No active routers found for tenant"
        result["errors"].append("no_routers")
        return result

    # If user has a primary router, try that first
    routers_list = list(routers)
    if user.primary_router and user.primary_router.is_active:
        if user.primary_router in routers_list:
            routers_list.remove(user.primary_router)
        routers_list.insert(0, user.primary_router)

    for router in routers_list:
        result["routers_tried"] += 1
        router_result = {
            "router_id": router.id,
            "router_name": router.name,
            "router_host": router.host,
            "success": False,
            "hotspot_user_created": False,
            "ip_binding_created": False,
            "errors": [],
        }

        try:
            api = get_tenant_mikrotik_api(router)
            if api is None:
                router_result["errors"].append(
                    f"Cannot connect to router {router.host}:{router.port}"
                )
                result["router_results"].append(router_result)
                continue

            try:
                # Step 1: Create/update hotspot user on this router
                try:
                    user_created = create_hotspot_user_on_router(
                        api, user.phone_number, user.phone_number
                    )
                    router_result["hotspot_user_created"] = user_created
                    if user_created:
                        logger.info(
                            f"✓ Hotspot user created on {router.name} for {user.phone_number}"
                        )
                except Exception as user_error:
                    router_result["errors"].append(f"hotspot_user: {user_error}")

                # Step 2: Create IP binding bypass for the MAC
                if mac_address:
                    try:
                        mac_ok = allow_mac_on_router(
                            api,
                            mac_address,
                            comment=f"{access_type}:{user.phone_number}",
                        )
                        router_result["ip_binding_created"] = mac_ok
                        if mac_ok:
                            logger.info(
                                f"✓ IP binding created on {router.name} for {mac_address}"
                            )
                    except Exception as mac_error:
                        router_result["errors"].append(f"ip_binding: {mac_error}")

                # Consider success if either operation worked
                router_result["success"] = (
                    router_result["hotspot_user_created"]
                    or router_result["ip_binding_created"]
                )

                if router_result["success"]:
                    result["routers_succeeded"] += 1

            finally:
                safe_close(api)

        except Exception as e:
            logger.error(
                f"force_immediate_internet_access_on_tenant_routers: Failed on router {router.name}: {e}"
            )
            router_result["errors"].append(str(e))

        result["router_results"].append(router_result)

    result["success"] = result["routers_succeeded"] > 0

    if result["success"]:
        result["message"] = (
            f"Internet access granted on {result['routers_succeeded']}/{result['routers_tried']} routers"
        )
        result["method_used"] = "multi_tenant_bypass"
        result["instructions"] = [
            "Device should now have immediate internet access",
            "If browser shows login page, it should auto-redirect",
            "If still not working, disconnect and reconnect to WiFi",
        ]
    else:
        result["message"] = "Failed to grant access on any router"
        result["instructions"] = [
            "Auto-login setup encountered issues",
            "User may need to manually authenticate",
            "Connect to WiFi and open browser",
            "Enter phone number as username and password",
        ]

    return result


def disconnect_user_from_tenant_routers(user, mac_address: str = None) -> dict:
    """
    Disconnect a user from ALL of the tenant's routers.

    This is the MULTI-TENANT version of disconnect_user_from_mikrotik().
    Used by the expiry watcher to disconnect expired users.

    Args:
        user: User model instance (has tenant FK)
        mac_address: Optional MAC address for targeted removal

    Returns:
        dict: Result with success, router_results, message
    """
    result = {
        "success": False,
        "router_results": [],
        "message": "",
        "routers_tried": 0,
        "routers_succeeded": 0,
    }

    if not user or not user.tenant:
        result["message"] = "User has no tenant assigned"
        return result

    from .models import Router

    routers = Router.objects.filter(tenant=user.tenant, is_active=True)

    if not routers.exists():
        result["message"] = "No active routers found for tenant"
        return result

    username = user.phone_number

    for router in routers:
        result["routers_tried"] += 1
        router_result = {
            "router_id": router.id,
            "router_name": router.name,
            "router_host": router.host,
            "success": False,
            "session_removed": False,
            "binding_removed": False,
            "user_disabled": False,
            "errors": [],
        }

        try:
            api = get_tenant_mikrotik_api(router)
            if api is None:
                router_result["errors"].append(
                    f"Cannot connect to router {router.host}:{router.port}"
                )
                result["router_results"].append(router_result)
                continue

            try:
                # Use the disconnect_user_with_api helper which handles all steps
                disconnect_result = disconnect_user_with_api(api, username, mac_address)

                router_result["session_removed"] = disconnect_result.get(
                    "session_removed", False
                )
                router_result["binding_removed"] = disconnect_result.get(
                    "binding_removed", False
                )
                router_result["user_disabled"] = disconnect_result.get(
                    "user_disabled", False
                )
                router_result["errors"].extend(disconnect_result.get("errors", []))
                router_result["success"] = disconnect_result.get("success", False)

                if router_result["success"]:
                    result["routers_succeeded"] += 1
                    logger.info(f"✓ Disconnected {username} from router {router.name}")

            finally:
                safe_close(api)

        except Exception as e:
            logger.error(
                f"disconnect_user_from_tenant_routers: Failed on router {router.name}: {e}"
            )
            router_result["errors"].append(str(e))

        result["router_results"].append(router_result)

    result["success"] = result["routers_succeeded"] > 0
    result["message"] = (
        f"Disconnected from {result['routers_succeeded']}/{result['routers_tried']} routers"
        if result["success"]
        else "Failed to disconnect from any router"
    )

    return result


def authorize_user_on_specific_router(
    user,
    router_id: int,
    mac_address: str,
    ip_address: str,
    access_type: str = "payment",
) -> dict:
    """
    Authorize a user on a SPECIFIC router only.

    This is crucial for multi-tenant SaaS:
    - User connects to WiFi on Router A
    - We authorize ONLY on Router A (not Router B)
    - Ensures tenant isolation

    Args:
        user: User model instance (has tenant FK and phone_number)
        router_id: Specific router ID to authorize on
        mac_address: MAC address of the device
        ip_address: IP address of the device
        access_type: Type of access ("payment", "voucher")

    Returns:
        dict: Result with success, router info, and details
    """
    result = {
        "success": False,
        "message": "",
        "router_id": router_id,
        "router_name": "",
        "username": user.phone_number if user else "",
        "mac_address": mac_address,
        "ip_address": ip_address,
        "access_type": access_type,
        "hotspot_user_created": False,
        "ip_binding_created": False,
        "method_used": None,
        "errors": [],
    }

    if not user:
        result["message"] = "No user provided"
        result["errors"].append("no_user")
        return result

    from .models import Router

    try:
        router = Router.objects.get(id=router_id)
    except Router.DoesNotExist:
        result["message"] = f"Router with ID {router_id} not found"
        result["errors"].append("router_not_found")
        return result

    result["router_name"] = router.name

    # CRITICAL: Validate tenant isolation
    # User must belong to the same tenant as the router
    if user.tenant and router.tenant:
        if user.tenant.id != router.tenant.id:
            result["message"] = (
                f"Access denied: User belongs to tenant '{user.tenant.slug}', router belongs to '{router.tenant.slug}'"
            )
            result["errors"].append("tenant_mismatch")
            logger.warning(
                f"SECURITY: Tenant mismatch! User {user.phone_number} ({user.tenant.slug}) tried to access router {router_id} ({router.tenant.slug})"
            )
            return result
    elif user.tenant and not router.tenant:
        # Router has no tenant - might be a legacy/global router
        logger.warning(
            f"Router {router_id} has no tenant assigned, but user {user.phone_number} has tenant {user.tenant.slug}"
        )
    elif not user.tenant and router.tenant:
        # User has no tenant - legacy user trying to access tenant router
        result["message"] = "Access denied: User has no tenant assigned"
        result["errors"].append("user_no_tenant")
        return result

    if not router.is_active:
        result["message"] = f"Router {router.name} is not active"
        result["errors"].append("router_inactive")
        return result

    try:
        api = get_tenant_mikrotik_api(router)
        if api is None:
            result["message"] = f"Cannot connect to router {router.host}:{router.port}"
            result["errors"].append("connection_failed")
            return result

        try:
            # Step 1: Create/update hotspot user on this router
            try:
                user_created = create_hotspot_user_on_router(
                    api, user.phone_number, user.phone_number
                )
                result["hotspot_user_created"] = user_created
                if user_created:
                    logger.info(
                        f"✓ Hotspot user created on {router.name} for {user.phone_number}"
                    )
            except Exception as user_error:
                result["errors"].append(f"hotspot_user: {user_error}")
                logger.error(
                    f"Failed to create hotspot user on {router.name}: {user_error}"
                )

            # Step 2: Create IP binding bypass for the MAC
            if mac_address:
                try:
                    mac_ok = allow_mac_on_router(
                        api, mac_address, comment=f"{access_type}:{user.phone_number}"
                    )
                    result["ip_binding_created"] = mac_ok
                    if mac_ok:
                        logger.info(
                            f"✓ IP binding created on {router.name} for {mac_address}"
                        )
                except Exception as mac_error:
                    result["errors"].append(f"ip_binding: {mac_error}")
                    logger.error(
                        f"Failed to create IP binding on {router.name}: {mac_error}"
                    )

            # Success if either operation worked
            result["success"] = (
                result["hotspot_user_created"] or result["ip_binding_created"]
            )

            if result["success"]:
                result["method_used"] = "specific_router_bypass"
                result["message"] = f"Access granted on router {router.name}"
                result["instructions"] = [
                    "Device should now have immediate internet access",
                    "If browser shows login page, enter your phone number",
                    "If still not working, disconnect and reconnect to WiFi",
                ]
                logger.info(
                    f"✓ User {user.phone_number} authorized on router {router.name} (ID: {router_id})"
                )
            else:
                result["message"] = f"Failed to grant access on router {router.name}"

        finally:
            safe_close(api)

    except Exception as e:
        logger.error(
            f"authorize_user_on_specific_router: Failed on router {router.name}: {e}"
        )
        result["errors"].append(str(e))
        result["message"] = f"Error authorizing on router: {str(e)}"

    return result


def revoke_user_on_specific_router(
    user, router_id: int, mac_address: str = None
) -> dict:
    """
    Revoke a user's access on a SPECIFIC router only.

    Args:
        user: User model instance
        router_id: Specific router ID to revoke on
        mac_address: Optional MAC address for targeted removal

    Returns:
        dict: Result with success and details
    """
    result = {
        "success": False,
        "message": "",
        "router_id": router_id,
        "router_name": "",
        "session_removed": False,
        "binding_removed": False,
        "user_disabled": False,
        "errors": [],
    }

    from .models import Router

    try:
        router = Router.objects.get(id=router_id)
    except Router.DoesNotExist:
        result["message"] = f"Router with ID {router_id} not found"
        result["errors"].append("router_not_found")
        return result

    result["router_name"] = router.name

    # Tenant isolation check
    if user.tenant and router.tenant and user.tenant.id != router.tenant.id:
        result["message"] = "Access denied: Tenant mismatch"
        result["errors"].append("tenant_mismatch")
        return result

    try:
        api = get_tenant_mikrotik_api(router)
        if api is None:
            result["message"] = f"Cannot connect to router {router.host}:{router.port}"
            result["errors"].append("connection_failed")
            return result

        try:
            disconnect_result = disconnect_user_with_api(
                api, user.phone_number, mac_address
            )

            result["session_removed"] = disconnect_result.get("session_removed", False)
            result["binding_removed"] = disconnect_result.get("binding_removed", False)
            result["user_disabled"] = disconnect_result.get("user_disabled", False)
            result["errors"].extend(disconnect_result.get("errors", []))
            result["success"] = disconnect_result.get("success", False)

            if result["success"]:
                result["message"] = f"Access revoked on router {router.name}"
                logger.info(f"✓ Revoked {user.phone_number} from router {router.name}")
            else:
                result["message"] = f"Failed to revoke access on router {router.name}"

        finally:
            safe_close(api)

    except Exception as e:
        logger.error(
            f"revoke_user_on_specific_router: Failed on router {router.name}: {e}"
        )
        result["errors"].append(str(e))
        result["message"] = f"Error revoking on router: {str(e)}"

    return result


# =============================================================================
# LEGACY FUNCTIONS - Use global settings, kept for backwards compatibility
# =============================================================================


def allow_mac(mac_address: str, comment: str = "Paid user") -> bool:
    """Create/ensure bypass binding for a MAC in /ip/hotspot/ip-binding.

    If binding already exists, it will be updated to 'bypassed' type.
    This ensures that previously disabled/blocked MACs get re-enabled.
    """
    if not mac_address:
        logger.warning("allow_mac called with empty mac_address")
        return False
    api = get_mikrotik_api()
    try:
        bindings = api.get_resource("/ip/hotspot/ip-binding")
        existing = bindings.get(mac_address=mac_address)

        if existing:
            for item in existing:
                # Use .get() for safety - MikroTik API can return '.id' or 'id'
                binding_id = item.get(".id") or item.get("id")
                if binding_id:
                    # Update to bypassed type (re-enable if was blocked)
                    bindings.set(
                        id=binding_id,
                        type="bypassed",
                        comment=comment,
                        mac_address=mac_address,
                    )
            logger.info(f"Updated bypass binding for {mac_address}")
            return True

        bindings.add(type="bypassed", mac_address=mac_address, comment=comment)
        logger.info(f"Created bypass binding for {mac_address}")
        return True
    except Exception as e:
        logger.error(f"allow_mac failed for {mac_address}: {e}")
        return False
    finally:
        safe_close(api)


def force_login_hotspot_user(
    username: str, mac_address: str, ip_address: str = None
) -> dict:
    """
    Force login a user to the hotspot by creating an active session.
    This is used after payment to immediately grant internet access.

    Methods tried (in order):
    1. Direct active session creation via /ip/hotspot/active
    2. Login via /ip/hotspot/active/login command
    3. IP binding bypass as fallback
    """
    if not username or not mac_address:
        return {"success": False, "message": "Username and MAC address required"}

    api = get_mikrotik_api()
    result = {
        "success": False,
        "active_session_created": False,
        "login_command_executed": False,
        "ip_binding_created": False,
        "method_used": None,
        "errors": [],
    }

    try:
        # Method 1: Try to check if user already has an active session
        try:
            active = api.get_resource("/ip/hotspot/active")
            existing_sessions = active.get(user=username)

            if existing_sessions:
                logger.info(f"User {username} already has active hotspot session")
                result["success"] = True
                result["active_session_created"] = True
                result["method_used"] = "existing_session"
                result["message"] = "User already has active session"
                return result
        except Exception as e:
            logger.warning(f"Could not check active sessions: {e}")
            result["errors"].append(f"active_check: {e}")

        # Method 2: Try to use the login command (if router supports it)
        try:
            # Some MikroTik versions support /ip/hotspot/active/login
            # This creates an active session programmatically
            hotspot_resource = api.get_resource("/ip/hotspot")

            # Get the hotspot server name (usually 'server1' or similar)
            servers = hotspot_resource.get()
            if servers:
                server_name = servers[0].get("name", "hotspot1")

                # Try using the login command via API
                try:
                    active = api.get_resource("/ip/hotspot/active")
                    # Try to add an active session directly
                    active.call(
                        "login",
                        {
                            "user": username,
                            "mac-address": mac_address,
                            "ip": ip_address or "0.0.0.0",
                            "server": server_name,
                        },
                    )

                    result["login_command_executed"] = True
                    result["success"] = True
                    result["method_used"] = "login_command"
                    result["message"] = "User logged in via hotspot login command"
                    logger.info(
                        f"Successfully logged in user {username} via hotspot login command"
                    )
                    return result

                except Exception as login_error:
                    logger.warning(
                        f"Hotspot login command failed (normal if not supported): {login_error}"
                    )
                    result["errors"].append(f"login_command: {login_error}")

        except Exception as e:
            logger.warning(f"Could not execute hotspot login: {e}")
            result["errors"].append(f"hotspot_login: {e}")

        # Method 3: Fall back to IP binding bypass (always works)
        # The bypassed binding will grant access when user connects/refreshes
        try:
            bindings = api.get_resource("/ip/hotspot/ip-binding")
            existing = bindings.get(mac_address=mac_address)

            if existing:
                for item in existing:
                    # Use .get() for safety - MikroTik API can return '.id' or 'id'
                    binding_id = item.get(".id") or item.get("id")
                    if binding_id:
                        bindings.set(
                            id=binding_id,
                            type="bypassed",
                            comment=f"Auto-login: {username}",
                        )
                logger.info(f"Updated bypass binding for {mac_address}")
            else:
                bindings.add(
                    type="bypassed",
                    mac_address=mac_address,
                    comment=f"Auto-login: {username}",
                )
                logger.info(f"Created bypass binding for {mac_address}")

            result["ip_binding_created"] = True
            result["success"] = True
            result["method_used"] = "ip_binding_bypass"
            result["message"] = (
                "IP binding bypass created - user will have access on next connection/refresh"
            )

        except Exception as e:
            logger.error(f"IP binding creation failed for {mac_address}: {e}")
            result["errors"].append(f"ip_binding: {e}")

        return result

    except Exception as e:
        logger.error(f"force_login_hotspot_user failed for {username}: {e}")
        result["errors"].append(str(e))
        result["message"] = f"Force login failed: {e}"
        return result
    finally:
        safe_close(api)


def revoke_mac(mac_address: str) -> bool:
    """Remove any /ip/hotspot/ip-binding entries for a MAC."""
    if not mac_address:
        return False
    api = get_mikrotik_api()
    try:
        bindings = api.get_resource("/ip/hotspot/ip-binding")
        items = bindings.get(mac_address=mac_address)

        if not items:
            logger.info(f"No bindings found for {mac_address}")
            return True  # Nothing to revoke, but not an error

        count = 0
        for item in items:
            # Use .get() for safety - MikroTik API can return '.id' or 'id'
            binding_id = item.get(".id") or item.get("id")
            if binding_id:
                bindings.remove(id=binding_id)
                count += 1

        logger.info(f"Revoked {count} binding(s) for {mac_address}")
        return True
    except Exception as e:
        logger.error(f"revoke_mac failed for {mac_address}: {e}")
        return False
    finally:
        safe_close(api)


def create_hotspot_user(
    username: str, password: str, profile: Optional[str] = None
) -> bool:
    """Create or update /ip/hotspot/user entry (no usage limits applied).

    IMPORTANT: If user already exists (even if disabled), this function will:
    - Update password and profile
    - RE-ENABLE the user (set disabled='no')

    This ensures that when a user pays again or uses a voucher after their
    access expired (and they were disabled), they get re-enabled automatically.
    """
    if not username:
        return False
    api = get_mikrotik_api()
    try:
        profile = profile or getattr(settings, "MIKROTIK_DEFAULT_PROFILE", "default")
        users = api.get_resource("/ip/hotspot/user")
        exist = users.get(name=username)

        if exist:
            for item in exist:
                # Use .get() for safety - MikroTik API can return '.id' or 'id'
                user_id = item.get(".id") or item.get("id")
                if user_id:
                    # Update password, profile AND re-enable the user
                    users.set(
                        id=user_id, password=password, profile=profile, disabled="no"
                    )
                    logger.info(
                        f"Updated and RE-ENABLED hotspot user {username} (was possibly disabled)"
                    )
            return True

        users.add(name=username, password=password, profile=profile, disabled="no")
        logger.info(f"Created hotspot user {username}")
        return True
    except Exception as e:
        logger.error(f"create_hotspot_user failed for {username}: {e}")
        return False
    finally:
        safe_close(api)


# Consolidated helpers


def grant_user_access(
    username: str,
    mac_address: Optional[str] = None,
    password: Optional[str] = None,
    profile: Optional[str] = None,
    comment: str = "Paid user",
) -> dict:
    """Create/update hotspot user, optionally bypass MAC, and return status dict."""
    result = {"user_created": False, "mac_bypassed": False, "errors": []}
    if password is None:
        password = username  # simple fallback
    try:
        # Use the hotspot-aware user creation
        user_ok = create_hotspot_user(username, password, profile)
        result["user_created"] = user_ok
    except Exception as e:
        logger.error(
            f"grant_user_access: create_hotspot_user failed for {username}: {e}"
        )
        result["errors"].append(f"user:{e}")
    if mac_address:
        try:
            mac_ok = allow_mac(mac_address, comment=comment)
            result["mac_bypassed"] = mac_ok
            if not mac_ok:
                result["errors"].append("mac:bypass_failed")
        except Exception as e:
            logger.error(f"grant_user_access: allow_mac failed for {mac_address}: {e}")
            result["errors"].append(f"mac:{e}")
    result["success"] = result["user_created"] or result["mac_bypassed"]
    return result


def revoke_user_access(
    mac_address: Optional[str] = None, username: Optional[str] = None
) -> dict:
    """Revoke MAC bypass, disable hotspot user, AND kick active session."""
    result = {
        "mac_revoked": False,
        "user_revoked": False,
        "session_kicked": False,
        "errors": [],
    }
    api = None

    try:
        if routeros_api is not None:
            api = get_mikrotik_api()

        # Step 1: Revoke MAC binding (IP bypass)
        if mac_address:
            try:
                result["mac_revoked"] = revoke_mac(mac_address)
                if not result["mac_revoked"]:
                    result["errors"].append("mac:revoke_failed")
            except Exception as e:
                logger.error(
                    f"revoke_user_access: revoke_mac failed for {mac_address}: {e}"
                )
                result["errors"].append(f"mac:{e}")

        # Step 2: Disable hotspot user account
        if username and api is not None:
            try:
                users = api.get_resource("/ip/hotspot/user")
                all_users = users.get()
                for item in all_users:
                    if item.get("name") == username:
                        user_id = item.get(".id") or item.get("id")
                        if user_id:
                            users.set(id=user_id, disabled="yes")
                            result["user_revoked"] = True
                            logger.info(f"Disabled hotspot user: {username}")
            except Exception as e:
                logger.error(
                    f"revoke_user_access: disable user failed for {username}: {e}"
                )
                result["errors"].append(f"user:{e}")

        # Step 3: KICK ACTIVE SESSION - This is the critical step!
        # Remove user from /ip/hotspot/active to immediately disconnect them
        if api is not None:
            try:
                active = api.get_resource("/ip/hotspot/active")
                active_sessions = active.get()

                for session in active_sessions:
                    session_user = session.get("user", "")
                    session_mac = session.get("mac-address", "")

                    # Match by username OR MAC address
                    should_kick = False
                    if username and session_user == username:
                        should_kick = True
                    if mac_address and session_mac.upper() == mac_address.upper():
                        should_kick = True

                    if should_kick:
                        try:
                            session_id = session.get(".id") or session.get("id")
                            if session_id:
                                active.remove(id=session_id)
                                result["session_kicked"] = True
                                logger.info(
                                    f"Kicked active session: user={session_user}, mac={session_mac}"
                                )
                            else:
                                logger.warning(f"No ID found for session: {session}")
                        except Exception as kick_err:
                            logger.error(
                                f"Failed to kick session {session_user}: {kick_err}"
                            )
                            result["errors"].append(f"kick:{kick_err}")

            except Exception as e:
                logger.error(f"revoke_user_access: kick active session failed: {e}")
                result["errors"].append(f"active:{e}")

        result["success"] = (
            result["mac_revoked"] or result["user_revoked"] or result["session_kicked"]
        )
        return result

    except Exception as e:
        logger.error(f"revoke_user_access failed: {e}")
        result["errors"].append(f"general:{e}")
        return result
    finally:
        if api is not None:
            safe_close(api)


def authenticate_user_with_mikrotik(
    phone_number: str, mac_address: str = "", ip_address: str = ""
) -> dict:
    """Authenticate (provision) user on MikroTik using routeros-api."""
    try:
        access = grant_user_access(
            phone_number, mac_address=mac_address, password=phone_number, comment="auth"
        )
        return {
            "success": access.get("success", False),
            "message": (
                "User provisioned on router"
                if access.get("success")
                else "Provisioning failed"
            ),
            "details": access,
        }
    except Exception as e:
        logger.error(f"authenticate_user_with_mikrotik failed for {phone_number}: {e}")
        return {"success": False, "message": str(e)}


def logout_user_from_mikrotik(phone_number: str, mac_address: str = "") -> dict:
    """Disable user / revoke MAC."""
    try:
        result = revoke_user_access(
            mac_address=mac_address or None, username=phone_number
        )
        return {
            "success": result.get("success", False),
            "message": "User revoked" if result.get("success") else "Revocation failed",
            "details": result,
        }
    except Exception as e:
        logger.error(f"logout_user_from_mikrotik failed for {phone_number}: {e}")
        return {"success": False, "message": str(e)}


def test_mikrotik_connection(host=None, username=None, password=None, port=8728):
    """Test low-level TCP connectivity to MikroTik API port."""
    try:
        host = host or getattr(settings, "MIKROTIK_HOST", "10.50.0.2")
        username = username or getattr(settings, "MIKROTIK_USER", "admin")
        password = password or getattr(settings, "MIKROTIK_PASSWORD", "")

        # Socket connectivity
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(5)
        result = test_socket.connect_ex((host, port))
        test_socket.close()

        api_status = "unverified"
        if result == 0 and routeros_api is not None:
            try:
                api = get_mikrotik_api()
                # simple call to list users (non-fatal)
                api.get_resource("/ip/hotspot/user").get()  # may be empty
                api_status = "api_ok"
            except Exception as e:
                api_status = f"api_error:{e}"
            finally:
                try:
                    safe_close(api)
                except Exception:
                    pass

        return {
            "success": result == 0,
            "message": (
                "Connection successful"
                if result == 0
                else f"Cannot connect to {host}:{port}"
            ),
            "router_info": {
                "ip": host,
                "port": port,
                "status": "reachable" if result == 0 else "unreachable",
                "api_status": api_status,
            },
        }
    except Exception as e:
        logger.error(f"Error testing MikroTik connection: {e}")
        return {"success": False, "error": str(e)}


def get_router_info():
    """Get basic router info via /system/resource/print."""
    try:
        api = None
        info = {}
        if routeros_api is not None:
            try:
                api = get_mikrotik_api()
                resource = api.get_resource("/system/resource")
                data = resource.get()
                if data:
                    d = data[0]
                    info = {
                        "uptime": d.get("uptime"),
                        "version": d.get("version"),
                        "board_name": d.get("board-name"),
                        "platform": d.get("platform"),
                        "cpu_load": d.get("cpu-load"),
                        "free_memory": d.get("free-memory"),
                        "total_memory": d.get("total-memory"),
                    }
            except Exception as e:
                logger.warning(f"get_router_info API error: {e}")
            finally:
                safe_close(api)
        connection_test = test_mikrotik_connection()
        info["connection_status"] = (
            "connected" if connection_test["success"] else "disconnected"
        )
        return {"success": True, "data": info}
    except Exception as e:
        logger.error(f"Error getting router info: {e}")
        return {"success": False, "error": str(e)}


def get_active_hotspot_users():
    """List active hotspot users using /ip/hotspot/active."""
    try:
        api = get_mikrotik_api()
        active = api.get_resource("/ip/hotspot/active").get()
        users = []
        for u in active:
            users.append(
                {
                    "user": u.get("user"),
                    "address": u.get("address"),
                    "mac_address": u.get("mac-address"),
                    "uptime": u.get("uptime"),
                    "session_time_left": u.get("session-time-left"),
                    "bytes_in": u.get("bytes-in"),
                    "bytes_out": u.get("bytes-out"),
                }
            )
        return {"success": True, "data": users}
    except Exception as e:
        logger.error(f"Error getting active users: {e}")
        return {"success": False, "error": str(e)}
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
        resource = api.get_resource("/ip/hotspot/active")
        active = resource.get()
        count = 0
        for u in active:
            try:
                resource.remove(id=u[".id"])
                count += 1
            except Exception as rem_err:
                logger.warning(f'Failed to remove user {u.get("user")}: {rem_err}')
        return {
            "success": True,
            "count": count,
            "message": f"Disconnected {count} users",
        }
    except Exception as e:
        logger.error(f"Error disconnecting users: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if api is not None:
            safe_close(api)


def reboot_router():
    """Reboot router (simulated unless explicit setting allows)."""
    api = None
    try:
        if not getattr(settings, "ALLOW_ROUTER_REBOOT", False):
            return {"success": False, "message": "Reboot disabled by settings"}
        api = get_mikrotik_api()
        try:
            # RouterOS reboot command
            api.get_resource("/system/reboot").call(
                ""
            )  # library-specific call, may vary
            return {"success": True, "message": "Router reboot issued"}
        except Exception as e:
            logger.error(f"Reboot command failed: {e}")
            return {"success": False, "error": str(e)}
        finally:
            if api is not None:
                safe_close(api)
    except Exception as outer:
        return {"success": False, "error": str(outer)}


def get_hotspot_profiles():
    """Get hotspot user profiles via /ip/hotspot/user/profile."""
    api = None
    try:
        api = get_mikrotik_api()
        profiles = api.get_resource("/ip/hotspot/user/profile").get()
        data = []
        for p in profiles:
            data.append(
                {
                    "name": p.get("name"),
                    "rate_limit": p.get("rate-limit"),
                    "shared_users": p.get("shared-users"),
                    "session_timeout": p.get("session-timeout"),
                    "idle_timeout": p.get("idle-timeout"),
                }
            )
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"Error getting hotspot profiles: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if api is not None:
            safe_close(api)


def create_hotspot_profile(
    name, rate_limit="512k/512k", session_timeout="1d", idle_timeout="5m"
):
    """Create hotspot profile using routeros-api (fields mapped to RouterOS)."""
    api = None
    try:
        api = get_mikrotik_api()
        res = api.get_resource("/ip/hotspot/user/profile")
        res.add(
            name=name,
            **{
                "rate-limit": rate_limit,
                "session-timeout": session_timeout,
                "idle-timeout": idle_timeout,
            },
        )
        return {
            "success": True,
            "data": {"name": name, "rate_limit": rate_limit},
            "message": "Profile created",
        }
    except Exception as e:
        logger.error(f"Error creating hotspot profile {name}: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if api is not None:
            safe_close(api)


# Advanced management helpers (no usage limiting)


def list_bypass_bindings() -> dict:
    """Return all bypass (and other) ip-bindings."""
    try:
        api = get_mikrotik_api()
        bindings = api.get_resource("/ip/hotspot/ip-binding").get()
        data = []
        for b in bindings:
            data.append(
                {
                    "id": b.get(".id"),
                    "mac_address": b.get("mac-address"),
                    "type": b.get("type"),
                    "comment": b.get("comment"),
                }
            )
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"list_bypass_bindings error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        try:
            safe_close(api)
        except Exception:
            pass


def sync_user_provisioning(usernames: List[str]) -> dict:
    """Ensure all provided usernames exist as hotspot users (no limits)."""
    summary = {"created": 0, "updated": 0, "errors": []}
    for u in usernames:
        try:
            ok = create_hotspot_user(u, password=u)
            if ok:
                summary[
                    "created"
                ] += 1  # treat as created/updated, we don't distinguish
        except Exception as e:
            summary["errors"].append(f"{u}:{e}")
    summary["success"] = len(summary["errors"]) == 0
    return summary


def cleanup_disabled_users() -> dict:
    """Remove disabled hotspot users (housekeeping)."""
    api = None
    try:
        api = get_mikrotik_api()
        users = api.get_resource("/ip/hotspot/user")
        existing = users.get()
        removed = 0
        for u in existing:
            if u.get("disabled") == "true" or u.get("disabled") == "yes":
                try:
                    users.remove(id=u[".id"])
                    removed += 1
                except Exception as inner:
                    logger.warning(
                        f'Failed removing disabled user {u.get("name")}: {inner}'
                    )
        return {"success": True, "removed": removed}
    except Exception as e:
        logger.error(f"cleanup_disabled_users error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if api is not None:
            safe_close(api)


def get_router_health() -> dict:
    """Fetch health metrics if available (/system/health)."""
    api = None
    try:
        api = get_mikrotik_api()
        health_res = api.get_resource("/system/health")
        data = health_res.get()
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"get_router_health error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if api is not None:
            safe_close(api)


def monitor_interface_traffic(interface: str, once: bool = True) -> dict:
    """Monitor traffic for a given interface (single snapshot)."""
    api = None
    try:
        api = get_mikrotik_api()
        monitor = api.get_resource("/interface/monitor-traffic")
        args = {"interface": interface, "once": "yes" if once else "no"}
        # routeros_api may require .call('monitor-traffic', **params), but using get_resource path wrapper
        data = monitor.call(**args)
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"monitor_interface_traffic error for {interface}: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if api is not None:
            safe_close(api)


def trigger_immediate_hotspot_login(phone_number, mac_address, ip_address):
    """
    Provision user immediately after voucher redemption with "Last Device Wins" logic.

    When a user redeems a voucher from a new device:
    1. All other active devices are deactivated and revoked from MikroTik
    2. The new device becomes the only active device
    3. Access is granted only to the new device
    """
    try:
        device_tracked = False
        device_switch_info = None

        try:
            from .models import User, Device

            user = User.objects.get(phone_number=phone_number)

            # LAST DEVICE WINS: Deactivate all other devices first
            other_active_devices = user.devices.filter(is_active=True).exclude(
                mac_address__iexact=mac_address
            )

            if other_active_devices.exists():
                logger.info(
                    f"VOUCHER REDEMPTION - LAST DEVICE WINS: User {phone_number} "
                    f"using new device {mac_address}. Deactivating {other_active_devices.count()} other device(s)."
                )

                # Deactivate other devices and revoke from MikroTik
                switch_result = deactivate_user_other_devices(
                    user=user, new_mac_address=mac_address, new_ip_address=ip_address
                )

                device_switch_info = {
                    "devices_switched": True,
                    "deactivated_count": len(
                        switch_result.get("deactivated_devices", [])
                    ),
                    "deactivated_devices": switch_result.get("deactivated_devices", []),
                }

            # Now register/update the new device
            device, created = Device.objects.get_or_create(
                user=user,
                mac_address=mac_address,
                defaults={
                    "ip_address": ip_address,
                    "is_active": True,
                    "device_name": f"Device-{mac_address[-8:]}",
                    "first_seen": timezone.now(),
                    "tenant": user.tenant,
                },
            )

            if not created:
                device.ip_address = ip_address
                device.is_active = True
                device.last_seen = timezone.now()
                if not device.tenant and user.tenant:
                    device.tenant = user.tenant
                device.save()

            device_tracked = True

        except User.DoesNotExist:
            logger.error(f"User not found for voucher login: {phone_number}")
            return {
                "success": False,
                "message": "User not found",
                "device_tracked": False,
            }
        except Exception as de:
            logger.error(f"Device tracking error for {phone_number}: {de}")

        # Grant access on MikroTik
        access = grant_user_access(
            phone_number,
            mac_address=mac_address,
            password=phone_number,
            comment="voucher",
        )

        result = {
            "success": access.get("success", False),
            "message": (
                "Access granted (bypassed / user created)"
                if access.get("success")
                else "Access provisioning failed"
            ),
            "method": "routeros_api",
            "device_tracked": device_tracked,
            "details": access,
        }

        # Add device switch info if applicable
        if device_switch_info:
            result["device_switch"] = device_switch_info

        return result

    except Exception as e:
        logger.error(f"trigger_immediate_hotspot_login error for {phone_number}: {e}")
        return {"success": False, "message": str(e)}


def deactivate_user_other_devices(user, new_mac_address, new_ip_address=None):
    """
    Deactivate all other devices for a user except the new one.
    This implements "Last Device Wins" - only one device can be active at a time.

    Args:
        user: User model instance
        new_mac_address: MAC address of the new device (the one to keep active)
        new_ip_address: Optional IP address of new device

    Returns:
        dict: Result with deactivated_devices, revoked_macs, errors
    """
    from .models import Device, Router

    result = {
        "success": True,
        "deactivated_devices": [],
        "revoked_macs": [],
        "errors": [],
        "new_device_mac": new_mac_address,
    }

    try:
        # Get all other active devices (excluding the new one)
        other_devices = user.devices.filter(is_active=True).exclude(
            mac_address__iexact=new_mac_address
        )

        if not other_devices.exists():
            logger.info(
                f"No other active devices to deactivate for {user.phone_number}"
            )
            return result

        logger.info(
            f"Deactivating {other_devices.count()} other device(s) for {user.phone_number} "
            f"(new device: {new_mac_address})"
        )

        # Get tenant's routers for MikroTik revocation
        tenant_routers = []
        if user.tenant:
            tenant_routers = list(
                Router.objects.filter(tenant=user.tenant, is_active=True)
            )

        # Deactivate each other device
        for device in other_devices:
            old_mac = device.mac_address

            try:
                # Step 1: Revoke MAC from MikroTik
                if tenant_routers:
                    # Multi-tenant: revoke on all tenant routers
                    for router in tenant_routers:
                        try:
                            revoke_result = revoke_user_access_on_router(
                                router=router,
                                mac_address=old_mac,
                                username=user.phone_number,
                            )
                            if revoke_result.get("success"):
                                result["revoked_macs"].append(
                                    {
                                        "mac": old_mac,
                                        "router": router.name,
                                        "session_kicked": revoke_result.get(
                                            "session_kicked", False
                                        ),
                                    }
                                )
                                logger.info(
                                    f"Revoked old device {old_mac} from router {router.name} for {user.phone_number}"
                                )
                        except Exception as router_err:
                            result["errors"].append(
                                f"Router {router.name}: {str(router_err)}"
                            )
                            logger.warning(
                                f"Failed to revoke {old_mac} from {router.name}: {router_err}"
                            )
                else:
                    # Legacy: use global router
                    try:
                        revoke_result = revoke_user_access(
                            mac_address=old_mac, username=user.phone_number
                        )
                        if revoke_result.get("success"):
                            result["revoked_macs"].append(
                                {
                                    "mac": old_mac,
                                    "router": "global",
                                    "session_kicked": revoke_result.get(
                                        "session_kicked", False
                                    ),
                                }
                            )
                            logger.info(
                                f"Revoked old device {old_mac} from global router for {user.phone_number}"
                            )
                    except Exception as global_err:
                        result["errors"].append(f"Global router: {str(global_err)}")
                        logger.warning(
                            f"Failed to revoke {old_mac} from global router: {global_err}"
                        )

                # Step 2: Mark device as inactive in database
                device.is_active = False
                device.save()
                result["deactivated_devices"].append(
                    {
                        "device_id": device.id,
                        "mac_address": old_mac,
                        "device_name": device.device_name,
                    }
                )

                logger.info(f"Deactivated old device {old_mac} for {user.phone_number}")

            except Exception as device_err:
                result["errors"].append(f"Device {old_mac}: {str(device_err)}")
                logger.error(f"Error deactivating device {old_mac}: {device_err}")

        if result["errors"]:
            result["success"] = len(result["deactivated_devices"]) > 0

        logger.info(
            f"Device switch complete for {user.phone_number}: "
            f"deactivated {len(result['deactivated_devices'])} devices, "
            f"revoked {len(result['revoked_macs'])} MACs, "
            f"errors: {len(result['errors'])}"
        )

        return result

    except Exception as e:
        logger.error(
            f"Error in deactivate_user_other_devices for {user.phone_number}: {e}"
        )
        result["success"] = False
        result["errors"].append(str(e))
        return result


def track_device_connection(
    phone_number,
    mac_address,
    ip_address,
    connection_type="wifi",
    access_method="unknown",
):
    """
    Track device connection with "Last Device Wins" logic.

    When a user connects from a new device:
    1. All other active devices are deactivated and revoked from MikroTik
    2. The new device becomes the only active device
    3. User can only use ONE device at a time

    This ensures strict single-device enforcement (max_devices=1 by default).
    """
    try:
        from .models import User, Device
        from django.utils import timezone

        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            logger.error(f"Device tracking failed: User {phone_number} not found")
            return {
                "success": False,
                "message": "User not found",
                "device_tracked": False,
            }

        # Check if this is the same device or a different one
        existing_device = user.devices.filter(mac_address__iexact=mac_address).first()
        is_new_device = existing_device is None

        # Check for other active devices
        other_active_devices = user.devices.filter(is_active=True).exclude(
            mac_address__iexact=mac_address
        )
        has_other_devices = other_active_devices.exists()

        switched_devices_info = None

        # LAST DEVICE WINS: If there are other active devices, deactivate them
        if has_other_devices:
            logger.info(
                f"LAST DEVICE WINS: User {phone_number} connecting from new device {mac_address}. "
                f"Deactivating {other_active_devices.count()} other device(s)."
            )

            # Deactivate all other devices and revoke from MikroTik
            switch_result = deactivate_user_other_devices(
                user=user, new_mac_address=mac_address, new_ip_address=ip_address
            )

            switched_devices_info = {
                "devices_switched": True,
                "deactivated_count": len(switch_result.get("deactivated_devices", [])),
                "deactivated_devices": switch_result.get("deactivated_devices", []),
                "revoked_macs": switch_result.get("revoked_macs", []),
                "switch_errors": switch_result.get("errors", []),
            }

            if switch_result.get("deactivated_devices"):
                logger.info(
                    f"Successfully switched devices for {phone_number}: "
                    f"old devices deactivated, new device {mac_address} now active"
                )

        # Create or update the current device
        device, device_created = Device.objects.get_or_create(
            user=user,
            mac_address=mac_address,
            defaults={
                "ip_address": ip_address,
                "is_active": True,
                "device_name": f"Device-{mac_address[-8:]}",
                "first_seen": timezone.now(),
                "tenant": user.tenant,
            },
        )

        if not device_created:
            # Update existing device
            device.ip_address = ip_address
            device.is_active = True
            device.last_seen = timezone.now()
            if not device.tenant and user.tenant:
                device.tenant = user.tenant
            device.save()
            logger.info(f"Updated existing device {mac_address} for {phone_number}")
        else:
            logger.info(f"Registered new device {mac_address} for {phone_number}")

        # Build response
        device_info = {
            "device_id": device.id,
            "mac_address": mac_address,
            "ip_address": ip_address,
            "device_name": device.device_name,
            "is_new_device": device_created,
            "first_seen": device.first_seen.isoformat(),
            "last_seen": device.last_seen.isoformat(),
            "connection_type": connection_type,
            "access_method": access_method,
            "active_devices": 1,  # Always 1 with "Last Device Wins"
            "max_devices": user.max_devices,
        }

        response = {
            "success": True,
            "message": "Device connection tracked",
            "device_tracked": True,
            "device_info": device_info,
            "device_limit_exceeded": False,
        }

        # Add switch info if devices were switched
        if switched_devices_info:
            response["device_switch"] = switched_devices_info
            if switched_devices_info["deactivated_count"] > 0:
                response["message"] = (
                    f"Device switched. Previous device(s) disconnected. "
                    f"Now using {mac_address}"
                )

        return response

    except Exception as e:
        logger.error(f"Error tracking device connection for {phone_number}: {e}")
        return {
            "success": False,
            "message": f"Device tracking error: {e}",
            "device_tracked": False,
        }


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
            logger.warning(
                f"Payment device tracking: No MAC address provided for {payment_user.phone_number}"
            )
            return {
                "success": False,
                "message": "No MAC address provided",
                "device_tracked": False,
            }
        result = track_device_connection(
            payment_user.phone_number,
            mac_address,
            ip_address,
            connection_type="wifi",
            access_method="payment",
        )
        if result["success"]:
            logger.info(
                f"Payment device tracking successful for {payment_user.phone_number}: {mac_address}"
            )
        else:
            logger.warning(
                f'Payment device tracking failed for {payment_user.phone_number}: {result["message"]}'
            )
        return result
    except Exception as e:
        logger.error(
            f"Error in payment device tracking for {payment_user.phone_number}: {e}"
        )
        return {
            "success": False,
            "message": f"Payment device tracking error: {e}",
            "device_tracked": False,
        }


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
            logger.warning(
                f"Voucher device tracking: No MAC address provided for {voucher_user.phone_number}"
            )
            return {
                "success": False,
                "message": "No MAC address provided",
                "device_tracked": False,
            }

        result = track_device_connection(
            voucher_user.phone_number,
            mac_address,
            ip_address,
            connection_type="wifi",
            access_method="voucher",
        )

        if result["success"]:
            logger.info(
                f"Voucher device tracking successful for {voucher_user.phone_number}: {mac_address}"
            )
        else:
            logger.warning(
                f'Voucher device tracking failed for {voucher_user.phone_number}: {result["message"]}'
            )

        return result
    except Exception as e:
        logger.error(
            f"Error in voucher device tracking for {voucher_user.phone_number}: {e}"
        )
        return {
            "success": False,
            "message": f"Voucher device tracking error: {e}",
            "device_tracked": False,
        }


def create_hotspot_user_and_login(
    username: str,
    mac_address: str = None,
    ip_address: str = None,
    password: str = None,
    profile: Optional[str] = None,
) -> dict:
    """
    Complete auto-login process: Create hotspot user + IP binding + immediate access

    This function implements the full flow:
    1. Create/update hotspot user
    2. Add IP binding bypass for MAC address (if provided)
    3. Return comprehensive result for auto-login
    """
    if not username:
        return {
            "success": False,
            "message": "Username required",
            "user_created": False,
            "ip_binding_created": False,
        }

    password = password or username
    result = {"user_created": False, "ip_binding_created": False, "errors": []}

    try:
        # Step 1: Create hotspot user
        user_created = create_hotspot_user(username, password, profile)
        result["user_created"] = user_created

        if not user_created:
            result["errors"].append("Failed to create hotspot user")
        else:
            logger.info(f"Hotspot user created for auto-login: {username}")

        # Step 2: Create IP binding bypass if MAC address provided
        if mac_address:
            binding_created = allow_mac(mac_address, comment=f"Auto-login: {username}")
            result["ip_binding_created"] = binding_created

            if not binding_created:
                result["errors"].append("Failed to create IP binding bypass")
            else:
                logger.info(
                    f"IP binding bypass created for auto-login: {mac_address} -> {username}"
                )
        else:
            # No MAC address, but user can still login manually
            result["ip_binding_created"] = True  # Not needed
            logger.info(f"Hotspot user created without IP binding (no MAC): {username}")

        # Overall success if user created (IP binding is optional)
        result["success"] = result["user_created"]

        if result["success"]:
            result["message"] = "Auto-login setup completed"
            logger.info(
                f'Auto-login setup successful for {username}: user={user_created}, binding={result["ip_binding_created"]}'
            )
        else:
            result["message"] = "Auto-login setup failed: " + ", ".join(
                result["errors"]
            )
            logger.error(f'Auto-login setup failed for {username}: {result["errors"]}')

        return result

    except Exception as e:
        logger.error(f"create_hotspot_user_and_login failed for {username}: {e}")
        return {
            "success": False,
            "message": f"Auto-login setup error: {e}",
            "user_created": False,
            "ip_binding_created": False,
            "errors": [str(e)],
        }


def get_device_info_from_mikrotik(
    mac_address: str = None, username: str = None
) -> dict:
    """
    Get device info from MikroTik active hotspot sessions or IP bindings.

    This is used after auto-login to capture the actual IP and MAC from the router.

    Args:
        mac_address: MAC address to look up
        username: Username to look up (phone number)

    Returns:
        dict with device info from MikroTik
    """
    if not mac_address and not username:
        return {"success": False, "message": "MAC address or username required"}

    result = {
        "success": False,
        "found_in": None,
        "mac_address": None,
        "ip_address": None,
        "uptime": None,
        "bytes_in": None,
        "bytes_out": None,
        "session_info": None,
    }

    api = None
    try:
        api = get_mikrotik_api()

        # First, try to find in active sessions
        try:
            active = api.get_resource("/ip/hotspot/active")

            if username:
                sessions = active.get(user=username)
            elif mac_address:
                # Note: MikroTik uses 'mac-address' with hyphen
                sessions = active.get()
                sessions = [
                    s
                    for s in sessions
                    if s.get("mac-address", "").lower() == mac_address.lower()
                ]
            else:
                sessions = []

            if sessions:
                session = sessions[0]  # Take the first match
                result["success"] = True
                result["found_in"] = "active_sessions"
                result["mac_address"] = session.get("mac-address")
                result["ip_address"] = session.get("address")
                result["uptime"] = session.get("uptime")
                result["bytes_in"] = session.get("bytes-in")
                result["bytes_out"] = session.get("bytes-out")
                result["session_info"] = {
                    "user": session.get("user"),
                    "server": session.get("server"),
                    "session_time_left": session.get("session-time-left"),
                    "idle_time": session.get("idle-time"),
                    "login_by": session.get("login-by"),
                    "session_id": session.get(".id"),
                }
                logger.info(
                    f'Found device in active sessions: {result["mac_address"]} / {result["ip_address"]}'
                )
                return result

        except Exception as e:
            logger.warning(f"Error checking active sessions: {e}")

        # If not found in active, check IP bindings
        try:
            bindings = api.get_resource("/ip/hotspot/ip-binding")

            if mac_address:
                binding_list = bindings.get(mac_address=mac_address)
            else:
                # Search by comment (which might contain username)
                binding_list = bindings.get()
                binding_list = [
                    b for b in binding_list if username in (b.get("comment", "") or "")
                ]

            if binding_list:
                binding = binding_list[0]
                result["success"] = True
                result["found_in"] = "ip_bindings"
                result["mac_address"] = binding.get("mac-address")
                result["ip_address"] = binding.get(
                    "address"
                )  # May be empty for MAC-based bindings
                result["session_info"] = {
                    "binding_type": binding.get("type"),
                    "comment": binding.get("comment"),
                    "binding_id": binding.get(".id"),
                }
                logger.info(f'Found device in IP bindings: {result["mac_address"]}')
                return result

        except Exception as e:
            logger.warning(f"Error checking IP bindings: {e}")

        result["message"] = "Device not found in MikroTik"
        return result

    except Exception as e:
        logger.error(f"get_device_info_from_mikrotik failed: {e}")
        result["message"] = str(e)
        return result
    finally:
        if api:
            safe_close(api)


def disconnect_user_from_mikrotik(username: str, mac_address: str = None) -> dict:
    """
    Disconnect a user from MikroTik hotspot completely.

    This is called when user's session/access expires. It:
    1. Removes active hotspot session
    2. Removes IP binding bypass
    3. Disables hotspot user

    Args:
        username: Phone number (hotspot username)
        mac_address: Optional MAC address for more targeted removal

    Returns:
        dict with disconnect results
    """
    result = {
        "success": False,
        "session_removed": False,
        "binding_removed": False,
        "user_disabled": False,
        "errors": [],
    }

    api = None
    try:
        api = get_mikrotik_api()

        # Step 1: Remove active sessions
        try:
            active = api.get_resource("/ip/hotspot/active")
            # Get ALL sessions and filter manually (more reliable)
            all_sessions = active.get()

            for session in all_sessions:
                session_user = session.get("user", "")
                session_mac = session.get("mac-address", "")

                # Match by username OR MAC address
                should_remove = False
                if username and session_user == username:
                    should_remove = True
                if mac_address and session_mac.upper() == mac_address.upper():
                    should_remove = True

                if should_remove:
                    try:
                        # Try different ID key formats
                        session_id = (
                            session.get(".id")
                            or session.get("id")
                            or session.get(".id")
                        )
                        if session_id:
                            active.remove(id=session_id)
                            result["session_removed"] = True
                            logger.info(
                                f"Removed active session for {username}: {session_mac}"
                            )
                        else:
                            logger.warning(f"No ID found for session: {session}")
                            result["errors"].append(f"session_no_id: {session_user}")
                    except Exception as rem_err:
                        logger.warning(
                            f"Failed to remove session for {session_user}: {rem_err}"
                        )
                        result["errors"].append(f"session_remove: {rem_err}")

        except Exception as e:
            logger.warning(f"Error removing active sessions for {username}: {e}")
            result["errors"].append(f"active_sessions: {e}")

        # Step 2: Remove IP bindings
        try:
            bindings = api.get_resource("/ip/hotspot/ip-binding")

            # Remove by MAC if provided
            if mac_address:
                binding_list = bindings.get(mac_address=mac_address)
                for binding in binding_list:
                    try:
                        bindings.remove(id=binding[".id"])
                        result["binding_removed"] = True
                        logger.info(f"Removed IP binding for {mac_address}")
                    except Exception as rem_err:
                        logger.warning(
                            f'Failed to remove binding {binding.get(".id")}: {rem_err}'
                        )
                        result["errors"].append(f"binding_remove: {rem_err}")

            # Also remove any bindings that have the username in comment
            all_bindings = bindings.get()
            for binding in all_bindings:
                comment = binding.get("comment", "") or ""
                if username in comment:
                    try:
                        bindings.remove(id=binding[".id"])
                        result["binding_removed"] = True
                        logger.info(f"Removed IP binding by comment for {username}")
                    except Exception as rem_err:
                        # May already be removed
                        pass

        except Exception as e:
            logger.warning(f"Error removing IP bindings for {username}: {e}")
            result["errors"].append(f"ip_bindings: {e}")

        # Step 3: Disable hotspot user
        try:
            users = api.get_resource("/ip/hotspot/user")
            # Get all users and filter manually
            all_users = users.get()

            for user in all_users:
                user_name = user.get("name", "")
                if user_name == username:
                    try:
                        # Try different ID key formats
                        user_id = user.get(".id") or user.get("id")
                        if user_id:
                            users.set(id=user_id, disabled="yes")
                            result["user_disabled"] = True
                            logger.info(f"Disabled hotspot user {username}")
                        else:
                            logger.warning(f"No ID found for user: {user}")
                    except Exception as dis_err:
                        logger.warning(f"Failed to disable user {username}: {dis_err}")
                        result["errors"].append(f"user_disable: {dis_err}")

        except Exception as e:
            logger.warning(f"Error disabling hotspot user {username}: {e}")
            result["errors"].append(f"hotspot_user: {e}")

        # Consider success if any cleanup action succeeded
        result["success"] = (
            result["session_removed"]
            or result["binding_removed"]
            or result["user_disabled"]
        )

        if result["success"]:
            result["message"] = "User disconnected from MikroTik"
            logger.info(
                f'Successfully disconnected {username} from MikroTik: session={result["session_removed"]}, binding={result["binding_removed"]}, user_disabled={result["user_disabled"]}'
            )
        else:
            result["message"] = "No MikroTik resources found to disconnect"
            logger.info(f"No MikroTik resources found to disconnect for {username}")

        return result

    except Exception as e:
        logger.error(f"disconnect_user_from_mikrotik failed for {username}: {e}")
        result["errors"].append(str(e))
        result["message"] = f"Disconnect error: {e}"
        return result
    finally:
        if api:
            safe_close(api)


def update_device_from_mikrotik_session(username: str, mac_address: str = None) -> dict:
    """
    Get device info from MikroTik and update the Device model in database.

    Call this after auto-login to capture actual device details from the router.

    Args:
        username: Phone number (to find user)
        mac_address: Optional MAC to narrow search

    Returns:
        dict with update results
    """
    from django.utils import timezone

    result = {
        "success": False,
        "device_updated": False,
        "device_created": False,
        "mikrotik_info": None,
    }

    try:
        # Get device info from MikroTik
        mikrotik_info = get_device_info_from_mikrotik(
            mac_address=mac_address, username=username
        )

        result["mikrotik_info"] = mikrotik_info

        if not mikrotik_info.get("success"):
            result["message"] = mikrotik_info.get(
                "message", "Device not found in MikroTik"
            )
            return result

        # Get or create user
        from .models import User, Device

        try:
            user = User.objects.get(phone_number=username)
        except User.DoesNotExist:
            result["message"] = f"User {username} not found in database"
            return result

        # Get the MAC and IP from MikroTik
        router_mac = mikrotik_info.get("mac_address")
        router_ip = mikrotik_info.get("ip_address")

        if not router_mac:
            result["message"] = "No MAC address found in MikroTik response"
            return result

        # Update or create device in database
        device, created = Device.objects.get_or_create(
            user=user,
            mac_address=router_mac,
            defaults={
                "ip_address": router_ip or "0.0.0.0",
                "is_active": True,
                "device_name": (
                    f"Device-{router_mac[-8:]}"
                    if len(router_mac) > 8
                    else f"Device-{router_mac}"
                ),
                "first_seen": timezone.now(),
            },
        )

        if created:
            result["device_created"] = True
            logger.info(
                f"Created device from MikroTik session: {router_mac} for {username}"
            )
        else:
            # Update existing device with latest info
            device.ip_address = router_ip or device.ip_address
            device.is_active = True
            device.last_seen = timezone.now()
            device.save()
            result["device_updated"] = True
            logger.info(
                f"Updated device from MikroTik session: {router_mac} for {username}"
            )

        result["success"] = True
        result["device"] = {
            "id": device.id,
            "mac_address": device.mac_address,
            "ip_address": device.ip_address,
            "device_name": device.device_name,
            "is_active": device.is_active,
        }
        result["message"] = "Device info updated from MikroTik"

        return result

    except Exception as e:
        logger.error(f"update_device_from_mikrotik_session failed for {username}: {e}")
        result["message"] = str(e)
        return result


def force_immediate_internet_access(
    username: str, mac_address: str, ip_address: str, access_type: str = "payment"
) -> dict:
    """
    Force immediate internet access after payment/voucher redemption

    This is the comprehensive auto-login function that:
    1. Creates hotspot user (for authentication records)
    2. Attempts to force login the user to create active session
    3. Creates IP binding bypass as fallback
    4. Captures and updates device info from MikroTik
    5. Returns detailed status for debugging

    The goal is to grant internet access WITHOUT requiring the user to visit login page.
    """
    try:
        logger.info(
            f"Starting force_immediate_internet_access for {username} (MAC: {mac_address}, IP: {ip_address}, Type: {access_type})"
        )

        result = {
            "success": False,
            "message": "",
            "username": username,
            "mac_address": mac_address,
            "ip_address": ip_address,
            "access_type": access_type,
            "hotspot_user_created": False,
            "ip_binding_created": False,
            "force_login_result": None,
            "method_used": None,
            "errors": [],
        }

        # Step 1: Create hotspot user (for record keeping and manual login fallback)
        try:
            user_created = create_hotspot_user(username, username)
            result["hotspot_user_created"] = user_created
            if user_created:
                logger.info(f"✓ Hotspot user created/updated for {username}")
            else:
                logger.warning(f"⚠ Failed to create hotspot user for {username}")
                result["errors"].append("hotspot_user_creation_failed")
        except Exception as user_error:
            logger.error(f"Error creating hotspot user for {username}: {user_error}")
            result["errors"].append(f"hotspot_user: {user_error}")

        # Step 2: Force login the user to the hotspot (creates active session or IP binding)
        if mac_address:
            try:
                force_login_result = force_login_hotspot_user(
                    username=username, mac_address=mac_address, ip_address=ip_address
                )

                result["force_login_result"] = force_login_result
                result["method_used"] = force_login_result.get("method_used")

                if force_login_result.get("success"):
                    result["success"] = True
                    result["ip_binding_created"] = force_login_result.get(
                        "ip_binding_created", False
                    )

                    if force_login_result.get("active_session_created"):
                        result["message"] = (
                            "Immediate internet access granted - active session created"
                        )
                        logger.info(
                            f'✓ Active session created for {username} via {result["method_used"]}'
                        )
                    elif force_login_result.get("login_command_executed"):
                        result["message"] = (
                            "Immediate internet access granted - user logged in"
                        )
                        logger.info(f"✓ User {username} logged in via hotspot command")
                    elif force_login_result.get("ip_binding_created"):
                        result["message"] = (
                            "Internet access prepared - IP binding bypass created"
                        )
                        logger.info(
                            f"✓ IP binding bypass created for {username} - MAC: {mac_address}"
                        )
                    else:
                        result["message"] = force_login_result.get(
                            "message", "Access granted"
                        )
                else:
                    result["errors"].extend(force_login_result.get("errors", []))
                    logger.warning(
                        f'Force login failed for {username}: {force_login_result.get("message")}'
                    )

            except Exception as login_error:
                logger.error(f"Error during force login for {username}: {login_error}")
                result["errors"].append(f"force_login: {login_error}")
        else:
            # No MAC address provided - can only create hotspot user
            logger.warning(
                f"No MAC address provided for {username} - only hotspot user created"
            )
            result["message"] = (
                "Hotspot user created - user must connect to WiFi for access"
            )

        # Step 3: If we have hotspot user created and/or IP binding, consider it a success
        if result["hotspot_user_created"] or result["ip_binding_created"]:
            result["success"] = True
            if not result["message"]:
                result["message"] = "Access setup completed"

        # Step 4: Capture and update device info from MikroTik
        if result["success"] and mac_address:
            try:
                device_update = update_device_from_mikrotik_session(
                    username=username, mac_address=mac_address
                )

                result["device_capture"] = {
                    "success": device_update.get("success", False),
                    "device_updated": device_update.get("device_updated", False),
                    "device_created": device_update.get("device_created", False),
                    "device": device_update.get("device"),
                    "mikrotik_info": device_update.get("mikrotik_info"),
                }

                if device_update.get("success"):
                    logger.info(
                        f'✓ Device info captured from MikroTik for {username}: {device_update.get("device")}'
                    )
                else:
                    logger.warning(
                        f'Device capture from MikroTik incomplete for {username}: {device_update.get("message")}'
                    )

            except Exception as capture_error:
                logger.error(
                    f"Error capturing device info from MikroTik for {username}: {capture_error}"
                )
                result["device_capture"] = {
                    "success": False,
                    "error": str(capture_error),
                }

        # Add instructions based on result
        if result["success"]:
            result["instructions"] = [
                "Device should now have immediate internet access",
                "If browser shows login page, it should auto-redirect",
                "If still not working, disconnect and reconnect to WiFi",
                "The MAC address is now bypassed from captive portal",
            ]
        else:
            result["instructions"] = [
                "Auto-login setup encountered issues",
                "User may need to manually authenticate",
                "Connect to WiFi and open browser",
                "Enter phone number as username and password",
            ]
            result["message"] = (
                result["message"] or "Partial access setup - may require manual login"
            )

        logger.info(
            f'force_immediate_internet_access completed for {username}: success={result["success"]}, method={result["method_used"]}'
        )
        return result

    except Exception as e:
        logger.error(f"force_immediate_internet_access failed for {username}: {e}")
        return {
            "success": False,
            "message": f"Immediate access setup error: {e}",
            "username": username,
            "mac_address": mac_address,
            "ip_address": ip_address,
            "access_type": access_type,
            "errors": [str(e)],
            "instructions": [
                "Auto-login failed - please connect to WiFi manually",
                "Enter your phone number as username and password",
            ],
        }


# =============================================================================
# PPP (Point-to-Point Protocol) SYNC FUNCTIONS — Enterprise Plan
# =============================================================================


def sync_ppp_profile_to_router(profile) -> dict:
    """
    Push a PPPProfile to MikroTik /ppp/profile.
    Creates or updates the profile on the router.

    Args:
        profile: PPPProfile model instance

    Returns:
        dict with success, mikrotik_id, message, errors
    """
    result = {
        "success": False,
        "mikrotik_id": "",
        "message": "",
        "errors": [],
    }

    router = profile.router
    api = get_tenant_mikrotik_api(router)
    if api is None:
        result["errors"].append(f"Cannot connect to router {router.host}:{router.port}")
        result["message"] = "Router connection failed"
        return result

    try:
        resource = api.get_resource("/ppp/profile")

        # Build the parameter dict for MikroTik
        params = {"name": profile.name}
        if profile.rate_limit:
            params["rate-limit"] = profile.rate_limit
        if profile.local_address:
            params["local-address"] = str(profile.local_address)
        if profile.remote_address:
            params["remote-address"] = profile.remote_address
        if profile.dns_server:
            params["dns-server"] = profile.dns_server
        if profile.session_timeout:
            params["session-timeout"] = profile.session_timeout
        if profile.idle_timeout:
            params["idle-timeout"] = profile.idle_timeout
        if profile.address_pool:
            params["address-pool"] = profile.address_pool

        # Check if profile already exists on router
        existing = resource.get(name=profile.name)

        if existing:
            # Update existing profile
            item = existing[0]
            mk_id = item.get(".id") or item.get("id")
            if mk_id:
                resource.set(id=mk_id, **params)
                profile.mikrotik_id = mk_id
                profile.synced_to_router = True
                profile.save(update_fields=["mikrotik_id", "synced_to_router", "updated_at"])
                result["success"] = True
                result["mikrotik_id"] = mk_id
                result["message"] = f"PPP profile '{profile.name}' updated on router"
                logger.info(f"Updated PPP profile {profile.name} on {router.name}")
        else:
            # Create new profile
            resource.add(**params)
            # Fetch back to get the .id
            created = resource.get(name=profile.name)
            mk_id = ""
            if created:
                mk_id = created[0].get(".id") or created[0].get("id") or ""
            profile.mikrotik_id = mk_id
            profile.synced_to_router = True
            profile.save(update_fields=["mikrotik_id", "synced_to_router", "updated_at"])
            result["success"] = True
            result["mikrotik_id"] = mk_id
            result["message"] = f"PPP profile '{profile.name}' created on router"
            logger.info(f"Created PPP profile {profile.name} on {router.name}")

    except Exception as e:
        logger.error(f"sync_ppp_profile_to_router failed for {profile.name}: {e}")
        result["errors"].append(str(e))
        result["message"] = f"Sync failed: {e}"
    finally:
        safe_close(api)

    return result


def remove_ppp_profile_from_router(profile) -> dict:
    """
    Remove a PPP profile from MikroTik /ppp/profile.

    Args:
        profile: PPPProfile model instance

    Returns:
        dict with success, message, errors
    """
    result = {"success": False, "message": "", "errors": []}

    router = profile.router
    api = get_tenant_mikrotik_api(router)
    if api is None:
        result["errors"].append(f"Cannot connect to router {router.host}:{router.port}")
        return result

    try:
        resource = api.get_resource("/ppp/profile")
        existing = resource.get(name=profile.name)

        if existing:
            mk_id = existing[0].get(".id") or existing[0].get("id")
            if mk_id:
                resource.remove(id=mk_id)
                logger.info(f"Removed PPP profile {profile.name} from {router.name}")

        profile.synced_to_router = False
        profile.mikrotik_id = ""
        profile.save(update_fields=["synced_to_router", "mikrotik_id", "updated_at"])
        result["success"] = True
        result["message"] = f"PPP profile '{profile.name}' removed from router"

    except Exception as e:
        logger.error(f"remove_ppp_profile_from_router failed for {profile.name}: {e}")
        result["errors"].append(str(e))
        result["message"] = f"Remove failed: {e}"
    finally:
        safe_close(api)

    return result


def sync_ppp_secret_to_router(customer) -> dict:
    """
    Push a PPPCustomer to MikroTik /ppp/secret.
    Creates or updates the secret on the router.

    Args:
        customer: PPPCustomer model instance

    Returns:
        dict with success, mikrotik_id, message, errors
    """
    result = {
        "success": False,
        "mikrotik_id": "",
        "message": "",
        "errors": [],
    }

    router = customer.router
    api = get_tenant_mikrotik_api(router)
    if api is None:
        result["errors"].append(f"Cannot connect to router {router.host}:{router.port}")
        result["message"] = "Router connection failed"
        return result

    try:
        resource = api.get_resource("/ppp/secret")

        # Build the parameter dict for MikroTik
        params = {
            "name": customer.username,
            "password": customer.password,
            "profile": customer.profile.name,
        }
        if customer.service:
            params["service"] = customer.service
        else:
            params["service"] = "pppoe"
        if customer.static_ip:
            params["remote-address"] = str(customer.static_ip)
        if customer.caller_id:
            params["caller-id"] = customer.caller_id
        elif customer.mac_address:
            params["caller-id"] = customer.mac_address

        # Build comment from customer info
        comment_parts = []
        if customer.full_name:
            comment_parts.append(customer.full_name)
        if customer.phone_number:
            comment_parts.append(customer.phone_number)
        if customer.comment:
            comment_parts.append(customer.comment)
        if comment_parts:
            params["comment"] = " | ".join(comment_parts)

        # Disabled state maps to MikroTik disabled flag
        if customer.status in ("suspended", "disabled", "expired"):
            params["disabled"] = "yes"
        else:
            params["disabled"] = "no"

        # Check if secret already exists on router
        existing = resource.get(name=customer.username)

        if existing:
            item = existing[0]
            mk_id = item.get(".id") or item.get("id")
            if mk_id:
                resource.set(id=mk_id, **params)
                customer.mikrotik_id = mk_id
                customer.synced_to_router = True
                customer.save(update_fields=["mikrotik_id", "synced_to_router", "updated_at"])
                result["success"] = True
                result["mikrotik_id"] = mk_id
                result["message"] = f"PPP secret '{customer.username}' updated on router"
                logger.info(f"Updated PPP secret {customer.username} on {router.name}")
        else:
            resource.add(**params)
            created = resource.get(name=customer.username)
            mk_id = ""
            if created:
                mk_id = created[0].get(".id") or created[0].get("id") or ""
            customer.mikrotik_id = mk_id
            customer.synced_to_router = True
            customer.save(update_fields=["mikrotik_id", "synced_to_router", "updated_at"])
            result["success"] = True
            result["mikrotik_id"] = mk_id
            result["message"] = f"PPP secret '{customer.username}' created on router"
            logger.info(f"Created PPP secret {customer.username} on {router.name}")

    except Exception as e:
        logger.error(f"sync_ppp_secret_to_router failed for {customer.username}: {e}")
        result["errors"].append(str(e))
        result["message"] = f"Sync failed: {e}"
    finally:
        safe_close(api)

    return result


def remove_ppp_secret_from_router(customer) -> dict:
    """
    Remove a PPP secret from MikroTik /ppp/secret.

    Args:
        customer: PPPCustomer model instance

    Returns:
        dict with success, message, errors
    """
    result = {"success": False, "message": "", "errors": []}

    router = customer.router
    api = get_tenant_mikrotik_api(router)
    if api is None:
        result["errors"].append(f"Cannot connect to router {router.host}:{router.port}")
        return result

    try:
        resource = api.get_resource("/ppp/secret")
        existing = resource.get(name=customer.username)

        if existing:
            mk_id = existing[0].get(".id") or existing[0].get("id")
            if mk_id:
                resource.remove(id=mk_id)
                logger.info(f"Removed PPP secret {customer.username} from {router.name}")

        customer.synced_to_router = False
        customer.mikrotik_id = ""
        customer.save(update_fields=["synced_to_router", "mikrotik_id", "updated_at"])
        result["success"] = True
        result["message"] = f"PPP secret '{customer.username}' removed from router"

    except Exception as e:
        logger.error(f"remove_ppp_secret_from_router failed for {customer.username}: {e}")
        result["errors"].append(str(e))
        result["message"] = f"Remove failed: {e}"
    finally:
        safe_close(api)

    return result


def suspend_ppp_customer_on_router(customer) -> dict:
    """
    Disable a PPP secret on MikroTik (set disabled=yes) and kick active session.

    Args:
        customer: PPPCustomer model instance

    Returns:
        dict with success, secret_disabled, session_kicked, errors
    """
    result = {
        "success": False,
        "secret_disabled": False,
        "session_kicked": False,
        "errors": [],
    }

    router = customer.router
    api = get_tenant_mikrotik_api(router)
    if api is None:
        result["errors"].append(f"Cannot connect to router {router.host}:{router.port}")
        return result

    try:
        # Step 1: Disable the PPP secret
        try:
            secrets_res = api.get_resource("/ppp/secret")
            existing = secrets_res.get(name=customer.username)
            if existing:
                mk_id = existing[0].get(".id") or existing[0].get("id")
                if mk_id:
                    secrets_res.set(id=mk_id, disabled="yes")
                    result["secret_disabled"] = True
                    logger.info(f"Disabled PPP secret {customer.username} on {router.name}")
        except Exception as e:
            result["errors"].append(f"disable_secret: {e}")
            logger.error(f"Failed to disable PPP secret {customer.username}: {e}")

        # Step 2: Kick active PPP session
        try:
            active_res = api.get_resource("/ppp/active")
            sessions = active_res.get(name=customer.username)
            for session in sessions:
                session_id = session.get(".id") or session.get("id")
                if session_id:
                    active_res.remove(id=session_id)
                    result["session_kicked"] = True
                    logger.info(f"Kicked PPP session for {customer.username} on {router.name}")
        except Exception as e:
            result["errors"].append(f"kick_session: {e}")
            logger.warning(f"Failed to kick PPP session for {customer.username}: {e}")

        result["success"] = result["secret_disabled"] or result["session_kicked"]

    except Exception as e:
        result["errors"].append(str(e))
        logger.error(f"suspend_ppp_customer_on_router failed for {customer.username}: {e}")
    finally:
        safe_close(api)

    return result


def activate_ppp_customer_on_router(customer) -> dict:
    """
    Re-enable a PPP secret on MikroTik (set disabled=no).

    Args:
        customer: PPPCustomer model instance

    Returns:
        dict with success, message, errors
    """
    result = {"success": False, "message": "", "errors": []}

    router = customer.router
    api = get_tenant_mikrotik_api(router)
    if api is None:
        result["errors"].append(f"Cannot connect to router {router.host}:{router.port}")
        return result

    try:
        secrets_res = api.get_resource("/ppp/secret")
        existing = secrets_res.get(name=customer.username)
        if existing:
            mk_id = existing[0].get(".id") or existing[0].get("id")
            if mk_id:
                secrets_res.set(id=mk_id, disabled="no")
                result["success"] = True
                result["message"] = f"PPP secret '{customer.username}' re-enabled on router"
                logger.info(f"Re-enabled PPP secret {customer.username} on {router.name}")
        else:
            # Secret doesn't exist on router, create it
            sync_result = sync_ppp_secret_to_router(customer)
            result["success"] = sync_result["success"]
            result["message"] = sync_result["message"]
            result["errors"] = sync_result["errors"]

    except Exception as e:
        result["errors"].append(str(e))
        result["message"] = f"Activate failed: {e}"
        logger.error(f"activate_ppp_customer_on_router failed for {customer.username}: {e}")
    finally:
        safe_close(api)

    return result


def get_ppp_active_sessions(router) -> dict:
    """
    Get all active PPP sessions from a router.

    Args:
        router: Router model instance

    Returns:
        dict with success, sessions list, errors
    """
    result = {"success": False, "sessions": [], "errors": []}

    api = get_tenant_mikrotik_api(router)
    if api is None:
        result["errors"].append(f"Cannot connect to router {router.host}:{router.port}")
        return result

    try:
        active_res = api.get_resource("/ppp/active")
        sessions = active_res.get()

        for s in sessions:
            result["sessions"].append({
                "id": s.get(".id") or s.get("id"),
                "name": s.get("name", ""),
                "service": s.get("service", ""),
                "caller_id": s.get("caller-id", ""),
                "address": s.get("address", ""),
                "uptime": s.get("uptime", ""),
                "encoding": s.get("encoding", ""),
                "session_id": s.get("session-id", ""),
                "radius": s.get("radius", "false"),
            })

        result["success"] = True

    except Exception as e:
        result["errors"].append(str(e))
        logger.error(f"get_ppp_active_sessions failed on {router.name}: {e}")
    finally:
        safe_close(api)

    return result


def kick_ppp_session(router, username: str) -> dict:
    """
    Kick a specific PPP active session by username.

    Args:
        router: Router model instance
        username: PPP username to disconnect

    Returns:
        dict with success, message, errors
    """
    result = {"success": False, "message": "", "errors": []}

    api = get_tenant_mikrotik_api(router)
    if api is None:
        result["errors"].append(f"Cannot connect to router {router.host}:{router.port}")
        return result

    try:
        active_res = api.get_resource("/ppp/active")
        sessions = active_res.get(name=username)

        if not sessions:
            result["message"] = f"No active PPP session found for '{username}'"
            result["success"] = True  # Not an error — user just isn't connected
            return result

        for session in sessions:
            session_id = session.get(".id") or session.get("id")
            if session_id:
                active_res.remove(id=session_id)
                logger.info(f"Kicked PPP session for {username} on {router.name}")

        result["success"] = True
        result["message"] = f"PPP session for '{username}' terminated"

    except Exception as e:
        result["errors"].append(str(e))
        result["message"] = f"Kick failed: {e}"
        logger.error(f"kick_ppp_session failed for {username} on {router.name}: {e}")
    finally:
        safe_close(api)

    return result
