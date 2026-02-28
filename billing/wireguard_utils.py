"""
WireGuard Key Generation & Utility Functions for Kitonga Remote User Access.

Uses the `cryptography` library (Curve25519 / X25519) to generate
WireGuard-compatible key pairs and preshared keys.

All keys are returned as base64-encoded strings, matching the format
expected by WireGuard and MikroTik RouterOS /interface/wireguard.
"""

import os
import base64
import logging
import re
import ipaddress

from django.db import IntegrityError
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives import serialization

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Key Generation
# ---------------------------------------------------------------------------


def generate_wireguard_keypair() -> dict:
    """
    Generate a WireGuard-compatible Curve25519 key pair.

    Returns:
        dict with 'private_key' and 'public_key' as base64-encoded strings.
    """
    private_key_obj = X25519PrivateKey.generate()

    # Raw 32-byte private key → base64
    private_bytes = private_key_obj.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    private_key_b64 = base64.b64encode(private_bytes).decode("ascii")

    # Derive public key → base64
    public_bytes = private_key_obj.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    public_key_b64 = base64.b64encode(public_bytes).decode("ascii")

    logger.debug("Generated new WireGuard key pair")
    return {
        "private_key": private_key_b64,
        "public_key": public_key_b64,
    }


def generate_preshared_key() -> str:
    """
    Generate a random 256-bit (32 bytes) WireGuard preshared key.

    Returns:
        base64-encoded preshared key string.
    """
    psk = base64.b64encode(os.urandom(32)).decode("ascii")
    logger.debug("Generated new WireGuard preshared key")
    return psk


# ---------------------------------------------------------------------------
# Key Validation
# ---------------------------------------------------------------------------

_WG_KEY_PATTERN = re.compile(r"^[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]==$")


def is_valid_wireguard_key(key: str) -> bool:
    """
    Validate that a string looks like a valid WireGuard base64 key (44 chars).

    This performs a format check only — it does not verify the key is
    cryptographically valid on a specific curve.

    Args:
        key: The base64-encoded key string to validate.

    Returns:
        True if the key has a valid WireGuard key format.
    """
    if not key or not isinstance(key, str):
        return False
    # Must be exactly 44 characters of base64 ending with '='
    if len(key) != 44:
        return False
    try:
        decoded = base64.b64decode(key, validate=True)
        return len(decoded) == 32
    except Exception:
        return False


def derive_public_key(private_key_b64: str) -> str:
    """
    Derive the WireGuard public key from a base64-encoded private key.

    Args:
        private_key_b64: Base64-encoded 32-byte private key.

    Returns:
        Base64-encoded public key string.

    Raises:
        ValueError: If the private key is invalid.
    """
    try:
        private_bytes = base64.b64decode(private_key_b64)
        if len(private_bytes) != 32:
            raise ValueError("Private key must be exactly 32 bytes")
        private_key_obj = X25519PrivateKey.from_private_bytes(private_bytes)
        public_bytes = private_key_obj.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return base64.b64encode(public_bytes).decode("ascii")
    except Exception as e:
        raise ValueError(f"Invalid WireGuard private key: {e}") from e


# ---------------------------------------------------------------------------
# Network Helpers
# ---------------------------------------------------------------------------


def validate_vpn_address_pool(cidr: str) -> dict:
    """
    Validate and analyse a VPN address pool CIDR string.

    Args:
        cidr: Network in CIDR notation (e.g. '10.100.0.0/24').

    Returns:
        dict with:
            valid (bool), network (str), netmask (str),
            total_hosts (int), first_host (str), last_host (str),
            error (str or '').
    """
    result = {
        "valid": False,
        "network": "",
        "netmask": "",
        "total_hosts": 0,
        "first_host": "",
        "last_host": "",
        "error": "",
    }
    try:
        net = ipaddress.ip_network(cidr, strict=False)
        hosts = list(net.hosts())
        if len(hosts) < 2:
            result["error"] = "Network too small — need at least 2 usable host IPs"
            return result
        result["valid"] = True
        result["network"] = str(net.network_address)
        result["netmask"] = str(net.netmask)
        result["total_hosts"] = len(hosts)
        result["first_host"] = str(hosts[0])
        result["last_host"] = str(hosts[-1])
    except ValueError as e:
        result["error"] = str(e)
    return result


def generate_client_config_text(
    private_key: str,
    address: str,
    dns: str,
    mtu: int,
    server_public_key: str,
    endpoint: str,
    allowed_ips: str = "0.0.0.0/0",
    preshared_key: str = "",
    persistent_keepalive: int = 25,
) -> str:
    """
    Build a WireGuard client configuration file string.

    This is a standalone helper (not tied to model instances) that can be
    used from management commands, API views, etc.

    Args:
        private_key: Client private key (base64).
        address: Client VPN IP with CIDR (e.g. '10.100.0.5/32').
        dns: Comma-separated DNS servers.
        mtu: Tunnel MTU.
        server_public_key: Server public key (base64).
        endpoint: Server address:port (e.g. '203.0.113.1:51820').
        allowed_ips: Allowed IPs for the peer section.
        preshared_key: Optional preshared key (base64).
        persistent_keepalive: Keepalive interval (0 to omit).

    Returns:
        Complete WireGuard .conf file content as a string.
    """
    lines = [
        "[Interface]",
        (
            f"PrivateKey = {private_key}"
            if private_key
            else "# PrivateKey = <INSERT_YOUR_PRIVATE_KEY>"
        ),
        f"Address = {address}",
        f"DNS = {dns}",
        f"MTU = {mtu}",
        "",
        "[Peer]",
        f"PublicKey = {server_public_key}",
    ]
    if preshared_key:
        lines.append(f"PresharedKey = {preshared_key}")
    lines.append(f"AllowedIPs = {allowed_ips}")
    lines.append(f"Endpoint = {endpoint}")
    if persistent_keepalive > 0:
        lines.append(f"PersistentKeepalive = {persistent_keepalive}")

    return "\n".join(lines)


def generate_qr_code_data(config_text: str) -> str:
    """
    Return the raw text that should be encoded into a QR code for the
    WireGuard mobile app.  The WireGuard app can import configs from
    QR codes that contain the plain-text configuration.

    Args:
        config_text: Complete WireGuard .conf content.

    Returns:
        The same config text (WireGuard QR codes are simply the raw conf).
    """
    return config_text


# ---------------------------------------------------------------------------
# Provisioning Helpers (used by views / management commands)
# ---------------------------------------------------------------------------


def provision_remote_user_keys(
    vpn_config,
    name: str,
    email: str = "",
    phone: str = "",
    notes: str = "",
    plan=None,
    created_by=None,
    use_preshared_key: bool = True,
) -> dict:
    """
    High-level helper: generate keys, pick next IP, and create a RemoteUser.

    This function encapsulates the full provisioning flow so that views
    and management commands don't need to repeat key-generation logic.

    Args:
        vpn_config: TenantVPNConfig instance.
        name: Display name for the remote user.
        email: Optional email.
        phone: Optional phone number.
        notes: Optional admin notes.
        plan: Optional RemoteAccessPlan instance.
        created_by: Optional User who initiated creation.
        use_preshared_key: Whether to generate a preshared key.

    Returns:
        dict with success (bool), remote_user (instance or None),
        private_key (str — ONLY available at creation time),
        config_text (str), error (str).
    """
    from billing.models import RemoteUser, RemoteAccessLog

    result = {
        "success": False,
        "remote_user": None,
        "private_key": "",
        "config_text": "",
        "error": "",
    }

    # 1. Validate that the tenant can still add remote users
    tenant = vpn_config.tenant
    if not tenant.can_add_remote_user():
        result["error"] = "Tenant has reached the maximum number of remote users"
        return result

    # 2. Get next available IP
    assigned_ip = vpn_config.get_next_available_ip()
    if assigned_ip is None:
        result["error"] = "VPN address pool exhausted — no IPs available"
        return result

    # 3. Generate key pair + optional preshared key
    keypair = generate_wireguard_keypair()
    psk = generate_preshared_key() if use_preshared_key else ""

    # 4. Set bandwidth from plan (if any)
    bandwidth_up = 0
    bandwidth_down = 0
    expires_at = None
    if plan:
        bandwidth_up = plan.bandwidth_limit_up
        bandwidth_down = plan.bandwidth_limit_down

    # 5. Create the RemoteUser instance (with retry on IP collision)
    remote_user = None
    for attempt in range(3):
        try:
            remote_user = RemoteUser.objects.create(
                tenant=tenant,
                vpn_config=vpn_config,
                name=name,
                email=email,
                phone=phone,
                notes=notes,
                plan=plan,
                public_key=keypair["public_key"],
                private_key=keypair["private_key"],  # stored temporarily
                preshared_key=psk,
                assigned_ip=assigned_ip,
                status="active",
                is_active=True,
                bandwidth_limit_up=bandwidth_up,
                bandwidth_limit_down=bandwidth_down,
                expires_at=expires_at,
                created_by=created_by,
            )
            break  # Success
        except IntegrityError:
            logger.warning(
                "IP %s collision for vpn_config=%s (attempt %d/3), retrying...",
                assigned_ip, vpn_config.id, attempt + 1
            )
            if attempt == 2:
                result["error"] = f"Failed to allocate VPN address after retries"
                return result
            assigned_ip = vpn_config.get_next_available_ip()
            if not assigned_ip:
                result["error"] = "VPN address pool exhausted — no IPs available"
                return result
            keypair = generate_wireguard_keypair()
            psk = generate_preshared_key() if use_preshared_key else ""
        except Exception as e:
            logger.error(f"Failed to create RemoteUser for {name}: {e}")
            result["error"] = f"Database error: {e}"
            return result

    # 6. Generate client config
    config_text = generate_client_config_text(
        private_key=keypair["private_key"],
        address=f"{assigned_ip}/32",
        dns=vpn_config.dns_servers,
        mtu=vpn_config.mtu,
        server_public_key=vpn_config.server_public_key,
        endpoint=f"{vpn_config.router.host}:{vpn_config.listen_port}",
        allowed_ips=vpn_config.allowed_ips,
        preshared_key=psk,
        persistent_keepalive=vpn_config.persistent_keepalive,
    )

    # 7. Log the event
    try:
        RemoteAccessLog.objects.create(
            tenant=tenant,
            remote_user=remote_user,
            event="config_generated",
            details=f"Keys generated and config created for {name} ({assigned_ip})",
        )
    except Exception as e:
        logger.warning(f"Failed to create RemoteAccessLog: {e}")

    result["success"] = True
    result["remote_user"] = remote_user
    result["private_key"] = keypair["private_key"]
    result["config_text"] = config_text

    logger.info(
        f"Provisioned remote user '{name}' ({assigned_ip}) for tenant {tenant.business_name}"
    )
    return result
