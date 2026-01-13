"""
WireGuard VPN Service for Router Management
Handles VPN IP allocation, key generation, and VPS configuration
"""
import subprocess
import paramiko
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# VPN Configuration Constants
VPN_NETWORK = "10.100.0"
VPN_SERVER_IP = "10.100.0.1"
VPN_START_IP = 10  # First usable IP for routers (10.100.0.10)
VPN_END_IP = 250   # Last usable IP (10.100.0.250)
VPS_PUBLIC_IP = "66.29.143.116"
VPS_WIREGUARD_PORT = 51820
VPS_SERVER_PUBLIC_KEY = "0ItNRIAXdf090Z3RpIVsmrA1JjRJrZveYweNZXXo3mQ="

# VPS SSH Configuration (from settings or environment)
VPS_SSH_HOST = getattr(settings, 'VPS_SSH_HOST', '66.29.143.116')
VPS_SSH_USER = getattr(settings, 'VPS_SSH_USER', 'root')
VPS_SSH_KEY_PATH = getattr(settings, 'VPS_SSH_KEY_PATH', '/var/www/kitonga/vps_ssh_key')


def get_used_vpn_ips():
    """Get list of VPN IPs already in use"""
    from billing.models import Router
    used_ips = Router.objects.exclude(vpn_ip__isnull=True).values_list('vpn_ip', flat=True)
    return list(used_ips)


def get_next_free_vpn_ip():
    """Get the next available VPN IP address"""
    used_ips = get_used_vpn_ips()
    
    for i in range(VPN_START_IP, VPN_END_IP + 1):
        ip = f"{VPN_NETWORK}.{i}"
        if ip not in used_ips:
            return ip
    
    raise Exception("No free VPN IPs available. Maximum capacity reached.")


def get_vpn_ip_stats():
    """Get VPN IP allocation statistics"""
    used_ips = get_used_vpn_ips()
    total_available = VPN_END_IP - VPN_START_IP + 1
    
    return {
        'total': total_available,
        'used': len(used_ips),
        'free': total_available - len(used_ips),
        'used_ips': used_ips,
        'next_free': get_next_free_vpn_ip() if len(used_ips) < total_available else None
    }


def generate_wireguard_keys():
    """Generate WireGuard private and public key pair"""
    try:
        # Generate private key
        private_key_result = subprocess.run(
            ['wg', 'genkey'],
            capture_output=True,
            text=True,
            check=True
        )
        private_key = private_key_result.stdout.strip()
        
        # Generate public key from private key
        public_key_result = subprocess.run(
            ['wg', 'pubkey'],
            input=private_key,
            capture_output=True,
            text=True,
            check=True
        )
        public_key = public_key_result.stdout.strip()
        
        return {
            'private_key': private_key,
            'public_key': public_key
        }
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to generate WireGuard keys: {e}")
        raise Exception("Failed to generate WireGuard keys. Ensure wg command is available.")
    except FileNotFoundError:
        # wg command not available locally, generate via VPS
        return generate_wireguard_keys_via_ssh()


def generate_wireguard_keys_via_ssh():
    """Generate WireGuard keys on VPS via SSH"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(VPS_SSH_HOST, username=VPS_SSH_USER, key_filename=VPS_SSH_KEY_PATH)
        
        # Generate keys on VPS
        stdin, stdout, stderr = ssh.exec_command('wg genkey | tee /tmp/wg_priv | wg pubkey')
        public_key = stdout.read().decode().strip()
        
        stdin, stdout, stderr = ssh.exec_command('cat /tmp/wg_priv && rm /tmp/wg_priv')
        private_key = stdout.read().decode().strip()
        
        ssh.close()
        
        return {
            'private_key': private_key,
            'public_key': public_key
        }
    except Exception as e:
        logger.error(f"Failed to generate keys via SSH: {e}")
        raise Exception(f"Failed to generate WireGuard keys via SSH: {e}")


def add_peer_to_vps(vpn_ip, public_key, tenant_name):
    """Add a WireGuard peer to the VPS configuration"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(VPS_SSH_HOST, username=VPS_SSH_USER, key_filename=VPS_SSH_KEY_PATH)
        
        # Add peer using wg command (live, no restart needed)
        add_peer_cmd = f'wg set wg0 peer {public_key} allowed-ips {vpn_ip}/32'
        stdin, stdout, stderr = ssh.exec_command(add_peer_cmd)
        error = stderr.read().decode().strip()
        
        if error:
            logger.error(f"Error adding peer: {error}")
            ssh.close()
            return False, error
        
        # Also add to config file for persistence
        config_entry = f'''
# Tenant: {tenant_name}
# Added: {timezone.now().isoformat()}
[Peer]
PublicKey = {public_key}
AllowedIPs = {vpn_ip}/32
'''
        append_cmd = f"echo '{config_entry}' >> /etc/wireguard/wg0.conf"
        ssh.exec_command(append_cmd)
        
        ssh.close()
        logger.info(f"Successfully added VPN peer for {tenant_name} with IP {vpn_ip}")
        return True, None
        
    except Exception as e:
        logger.error(f"Failed to add peer to VPS: {e}")
        return False, str(e)


def remove_peer_from_vps(public_key):
    """Remove a WireGuard peer from the VPS"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(VPS_SSH_HOST, username=VPS_SSH_USER, key_filename=VPS_SSH_KEY_PATH)
        
        # Remove peer using wg command
        remove_cmd = f'wg set wg0 peer {public_key} remove'
        stdin, stdout, stderr = ssh.exec_command(remove_cmd)
        
        # Note: We should also remove from config file, but that's more complex
        # For now, we just remove the live peer
        
        ssh.close()
        return True, None
        
    except Exception as e:
        logger.error(f"Failed to remove peer from VPS: {e}")
        return False, str(e)


def check_peer_connection(vpn_ip):
    """Check if a router is connected via VPN (ping test)"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(VPS_SSH_HOST, username=VPS_SSH_USER, key_filename=VPS_SSH_KEY_PATH)
        
        # Ping the router's VPN IP
        ping_cmd = f'ping -c 2 -W 2 {vpn_ip}'
        stdin, stdout, stderr = ssh.exec_command(ping_cmd)
        exit_status = stdout.channel.recv_exit_status()
        
        ssh.close()
        return exit_status == 0
        
    except Exception as e:
        logger.error(f"Failed to check peer connection: {e}")
        return False


def get_peer_last_handshake(public_key):
    """Get the last handshake time for a peer"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(VPS_SSH_HOST, username=VPS_SSH_USER, key_filename=VPS_SSH_KEY_PATH)
        
        # Get peer info
        cmd = f"wg show wg0 latest-handshakes | grep {public_key}"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode().strip()
        
        ssh.close()
        
        if output:
            parts = output.split()
            if len(parts) >= 2:
                timestamp = int(parts[1])
                if timestamp > 0:
                    return timezone.datetime.fromtimestamp(timestamp, tz=timezone.utc)
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to get peer handshake: {e}")
        return None


def generate_mikrotik_commands(vpn_ip, private_key):
    """Generate MikroTik RouterOS commands for WireGuard setup"""
    commands = f'''# ============================================
# Kitonga WiFi - WireGuard VPN Configuration
# Router VPN IP: {vpn_ip}
# Generated: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}
# ============================================

# Step 1: Create WireGuard interface
/interface wireguard add name=wg-kitonga listen-port=51820 private-key="{private_key}"

# Step 2: Add Kitonga VPS as peer
/interface wireguard peers add \\
    interface=wg-kitonga \\
    public-key="{VPS_SERVER_PUBLIC_KEY}" \\
    endpoint-address={VPS_PUBLIC_IP} \\
    endpoint-port={VPS_WIREGUARD_PORT} \\
    allowed-address={VPN_NETWORK}.0/24 \\
    persistent-keepalive=25

# Step 3: Assign VPN IP address
/ip address add address={vpn_ip}/24 interface=wg-kitonga

# Step 4: Allow API access from VPN (for Kitonga to manage hotspot)
/ip firewall filter add chain=input src-address={VPN_NETWORK}.0/24 protocol=tcp dst-port=8728 action=accept comment="Kitonga API Access"

# Step 5: Create API user for Kitonga (if not exists)
/user group add name=kitonga-api policy=api,read,write,policy,test
/user add name=kitonga-api password=CHANGE_THIS_PASSWORD group=kitonga-api

# Step 6: Enable API service
/ip service enable api
/ip service set api address={VPN_NETWORK}.0/24

# ============================================
# Verification Commands (run after setup):
# ============================================
# /ping {VPN_SERVER_IP}
# /interface wireguard peers print
# /interface wireguard print
'''
    return commands


def generate_router_vpn_config(router):
    """
    Generate complete VPN configuration for a router
    Returns dict with all necessary info
    """
    from billing.models import Router
    
    # Allocate VPN IP if not already assigned
    if not router.vpn_ip:
        router.vpn_ip = get_next_free_vpn_ip()
    
    # Generate keys if not already generated
    if not router.vpn_private_key or not router.vpn_public_key:
        keys = generate_wireguard_keys()
        router.vpn_private_key = keys['private_key']
        router.vpn_public_key = keys['public_key']
    
    router.vpn_config_generated_at = timezone.now()
    router.vpn_status = 'pending'
    router.host = router.vpn_ip  # Set host to VPN IP
    router.save()
    
    # Add peer to VPS
    success, error = add_peer_to_vps(
        router.vpn_ip,
        router.vpn_public_key,
        f"{router.tenant.business_name} - {router.name}"
    )
    
    if success:
        router.vpn_status = 'configured'
        router.save()
    else:
        router.vpn_status = 'error'
        router.last_error = f"Failed to add VPN peer: {error}"
        router.save()
    
    # Generate MikroTik commands
    mikrotik_commands = generate_mikrotik_commands(
        router.vpn_ip,
        router.vpn_private_key
    )
    
    return {
        'success': success,
        'error': error,
        'vpn_ip': router.vpn_ip,
        'private_key': router.vpn_private_key,
        'public_key': router.vpn_public_key,
        'mikrotik_commands': mikrotik_commands,
        'vps_endpoint': f"{VPS_PUBLIC_IP}:{VPS_WIREGUARD_PORT}",
        'server_public_key': VPS_SERVER_PUBLIC_KEY,
    }


def test_router_vpn_connection(router):
    """Test if router is connected and reachable via VPN"""
    if not router.vpn_ip:
        return {
            'connected': False,
            'error': 'No VPN IP assigned'
        }
    
    # Check ping
    is_reachable = check_peer_connection(router.vpn_ip)
    
    # Check handshake
    last_handshake = None
    if router.vpn_public_key:
        last_handshake = get_peer_last_handshake(router.vpn_public_key)
    
    # Update router status
    if is_reachable:
        router.vpn_status = 'connected'
        router.vpn_last_handshake = last_handshake
        router.status = 'online'
    else:
        router.vpn_status = 'configured'  # Keep as configured, not connected
    
    router.save()
    
    return {
        'connected': is_reachable,
        'vpn_ip': router.vpn_ip,
        'last_handshake': last_handshake,
        'error': None if is_reachable else 'Router not reachable via VPN'
    }
