"""
VPS WireGuard Hub – Peer Management
=====================================
Manages WireGuard peers on the VPS ``wg0`` interface via subprocess.

KTN Architecture:
    User Phone ──encrypted tunnel──► VPS wg0 (WireGuard Hub, 66.29.143.116:51820)
                                        │
                                  site-to-site tunnel
                                        │
                                  MikroTik (Infrastructure Controller, 10.100.0.40)
                                        │
                                     Internet

    VPS  = WireGuard Hub (public IP, accepts client tunnels)
    MikroTik = Infrastructure Controller (traffic control, bandwidth, QoS)
    User pays → gets encrypted tunnel → direct routed internet
"""

import logging
import re
import subprocess
from pathlib import Path
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)

WG_INTERFACE = getattr(settings, "WG_VPS_INTERFACE", "wg0")
WG_CONF_PATH = Path(f"/etc/wireguard/{WG_INTERFACE}.conf")

# The Django process runs as www-data; wg requires root.
# A sudoers rule grants www-data NOPASSWD access to /usr/bin/wg:
#   www-data ALL=(root) NOPASSWD: /usr/bin/wg
WG_BIN = ["sudo", "/usr/bin/wg"]


def _run(cmd: list, check: bool = True, timeout: int = 10):
    logger.debug("VPS WG cmd: %s", " ".join(cmd))
    return subprocess.run(
        cmd, capture_output=True, text=True, check=check, timeout=timeout
    )


def _wg_show_peers() -> dict:
    try:
        proc = _run(WG_BIN + ["show", WG_INTERFACE, "dump"], check=False)
    except FileNotFoundError:
        return {}
    if proc.returncode != 0:
        return {}
    peers = {}
    for line in proc.stdout.strip().splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) >= 8:
            peers[parts[0]] = {"allowed_ips": parts[3]}
    return peers


def vps_peer_exists(public_key: str) -> bool:
    return public_key in _wg_show_peers()


def vps_add_peer(
    public_key: str,
    allowed_ips: str,
    preshared_key: Optional[str] = None,
    persistent_keepalive: int = 25,
    comment: str = "",
) -> dict:
    """Add or update a peer on VPS wg0 (live + conf file)."""
    result = {"success": False, "message": "", "errors": []}
    if not public_key:
        result["errors"].append("public_key is required")
        return result

    cmd = WG_BIN + ["set", WG_INTERFACE, "peer", public_key, "allowed-ips", allowed_ips]

    psk_path = None
    if preshared_key:
        psk_path = Path(f"/tmp/.wg_psk_{public_key[:8]}")
        try:
            psk_path.write_text(preshared_key + "\n")
            psk_path.chmod(0o600)
            cmd += ["preshared-key", str(psk_path)]
        except Exception as e:
            logger.warning("Could not write PSK temp file: %s", e)

    if persistent_keepalive > 0:
        cmd += ["persistent-keepalive", str(persistent_keepalive)]

    try:
        proc = _run(cmd, check=False)
        if psk_path:
            psk_path.unlink(missing_ok=True)
        if proc.returncode != 0:
            err = proc.stderr.strip() or proc.stdout.strip()
            result["errors"].append(f"wg set failed: {err}")
            result["message"] = f"VPS peer add failed: {err}"
            return result
    except FileNotFoundError:
        result["errors"].append("wg binary not found on this host")
        result["message"] = "VPS WireGuard not available"
        return result
    except subprocess.TimeoutExpired:
        result["errors"].append("wg set timed out")
        return result

    _persist_peer(public_key, allowed_ips, preshared_key, persistent_keepalive, comment)
    result["success"] = True
    result["message"] = f"VPS peer {public_key[:12]}… added to {WG_INTERFACE}"
    logger.info(
        "VPS WG: added peer %s allowed=%s comment=%s",
        public_key[:16],
        allowed_ips,
        comment,
    )
    return result


def vps_remove_peer(public_key: str) -> dict:
    """Remove a peer from VPS wg0 (live + conf file)."""
    result = {"success": False, "message": "", "errors": []}
    if not public_key:
        result["errors"].append("public_key is required")
        return result

    try:
        proc = _run(
            WG_BIN + ["set", WG_INTERFACE, "peer", public_key, "remove"], check=False
        )
        if proc.returncode != 0:
            err = proc.stderr.strip()
            if "not found" not in err.lower():
                result["errors"].append(f"wg set remove failed: {err}")
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        result["errors"].append(str(e))

    _remove_peer_from_conf(public_key)
    result["success"] = True
    result["message"] = f"VPS peer {public_key[:12]}… removed from {WG_INTERFACE}"
    logger.info("VPS WG: removed peer %s", public_key[:16])
    return result


def sync_remote_user_to_vps(remote_user) -> dict:
    """Sync a RemoteUser's peer to VPS wg0. Remove if disabled/revoked."""
    if remote_user.status in ("disabled", "expired", "revoked"):
        return vps_remove_peer(remote_user.public_key)

    comment = f"{remote_user.name} | {remote_user.tenant.business_name} | {remote_user.assigned_ip}"
    keepalive = 25
    vpn_config = remote_user.vpn_config
    if vpn_config and vpn_config.persistent_keepalive:
        keepalive = vpn_config.persistent_keepalive

    return vps_add_peer(
        public_key=remote_user.public_key,
        allowed_ips=f"{remote_user.assigned_ip}/32",
        preshared_key=remote_user.preshared_key or None,
        persistent_keepalive=keepalive,
        comment=comment,
    )


# ── Conf-file helpers ────────────────────────────────────────────────


def _read_conf() -> str:
    """Read wg0.conf using sudo cat (file is root-only)."""
    try:
        proc = subprocess.run(
            ["sudo", "cat", str(WG_CONF_PATH)],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if proc.returncode == 0:
            return proc.stdout
    except Exception as e:
        logger.warning("Cannot read %s: %s", WG_CONF_PATH, e)
    return ""


def _write_conf(content: str) -> bool:
    """Write wg0.conf using sudo tee (file is root-only)."""
    try:
        proc = subprocess.run(
            ["sudo", "tee", str(WG_CONF_PATH)],
            input=content,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return proc.returncode == 0
    except Exception as e:
        logger.error("Cannot write %s: %s", WG_CONF_PATH, e)
        return False


def _persist_peer(
    public_key, allowed_ips, preshared_key, persistent_keepalive, comment=""
):
    conf = _read_conf()
    if not conf:
        logger.warning("VPS WG conf empty or unreadable — skip persist")
        return

    lines = []
    if comment:
        lines.append(f"# {comment}")
    lines.append("[Peer]")
    lines.append(f"PublicKey = {public_key}")
    if preshared_key:
        lines.append(f"PresharedKey = {preshared_key}")
    lines.append(f"AllowedIPs = {allowed_ips}")
    if persistent_keepalive > 0:
        lines.append(f"PersistentKeepalive = {persistent_keepalive}")
    new_block = "\n".join(lines)

    cleaned = _strip_peer_block(conf, public_key)
    updated = cleaned.rstrip("\n") + "\n\n" + new_block + "\n"

    _write_conf(updated)


def _remove_peer_from_conf(public_key):
    conf = _read_conf()
    if not conf:
        return
    updated = _strip_peer_block(conf, public_key)
    if updated != conf:
        _write_conf(updated)


def _strip_peer_block(conf_text: str, public_key: str) -> str:
    escaped = re.escape(public_key)
    # Match optional comment + [Peer] block containing this PublicKey
    pattern = (
        r"(?:#[^\n]*\n)?"
        r"\[Peer\]\n"
        r"(?:(?!\[)[^\n]*\n)*?"
        r"PublicKey\s*=\s*" + escaped + r"\n"
        r"(?:(?!\[)[^\n]*\n)*"
    )
    cleaned = re.sub(pattern, "", conf_text)
    # Also handle PublicKey as first field after [Peer]
    pattern2 = (
        r"(?:#[^\n]*\n)?"
        r"\[Peer\]\n"
        r"PublicKey\s*=\s*" + escaped + r"\n"
        r"(?:(?!\[)[^\n]*\n)*"
    )
    cleaned = re.sub(pattern2, "", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned)
