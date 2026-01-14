# Security Recommendations for WireGuard VPN IP Allocation

## 🔒 Current Security Status

### ✅ What We Have:
- ✅ API Key authentication required
- ✅ Tenant isolation (each tenant sees only their routers)
- ✅ Automatic IP conflict prevention
- ✅ IP range validation (10.100.0.0/24)
- ✅ Reserved IPs protection (0, 1, 255)

### ⚠️ Security Gaps:

1. **No IP Reservation System**
   - Problem: Tenant gets IP but might not complete setup
   - Risk: IP appears "available" but is already assigned
   - Impact: IP leakage over time

2. **Manual VPS Configuration Required**
   - Problem: Admin must manually add WireGuard peer to VPS
   - Risk: Human error, delays, security gaps
   - Impact: Router can't connect until admin configures VPS

3. **No Public Key Validation**
   - Problem: System doesn't verify router's WireGuard public key
   - Risk: Invalid or duplicate keys
   - Impact: Connection failures after setup

4. **No Audit Trail**
   - Problem: No record of who got which IP when
   - Risk: Can't track IP allocation history
   - Impact: Troubleshooting difficulties

---

## 🎯 Recommended Security Enhancements

### Priority 1: IP Reservation System (CRITICAL)

**Problem:** IPs are suggested but not reserved, leading to potential conflicts.

**Solution:** Add `vpn_ip` and `vpn_status` fields to Router model:

```python
# billing/models.py

class Router(models.Model):
    # ...existing fields...
    
    # WireGuard VPN Configuration
    vpn_ip = models.GenericIPAddressField(
        protocol='IPv4',
        null=True,
        blank=True,
        unique=True,  # Prevents duplicate IPs
        help_text="WireGuard VPN IP (10.100.0.0/24)"
    )
    
    vpn_public_key = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,  # Prevents duplicate keys
        help_text="Router's WireGuard public key"
    )
    
    vpn_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Setup'),
            ('configured', 'Router Configured'),
            ('vps_ready', 'VPS Peer Added'),
            ('connected', 'Fully Connected'),
            ('failed', 'Connection Failed'),
        ],
        default='pending',
        help_text="WireGuard connection status"
    )
    
    vpn_configured_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When router WireGuard was configured"
    )
    
    vpn_connected_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When VPN connection was established"
    )
    
    class Meta:
        indexes = [
            models.Index(fields=['vpn_ip']),
            models.Index(fields=['vpn_status']),
        ]
```

**Migration:**
```bash
python manage.py makemigrations
python manage.py migrate
```

---

### Priority 2: Reserve IP When Router Created (CRITICAL)

**Current Flow:**
1. Tenant calls `next-vpn-ip` → Gets IP 10.100.0.30
2. Tenant configures MikroTik
3. Tenant calls `save-router` → Stores host as "10.100.0.30"
4. **PROBLEM:** Between step 1-3, another tenant could get same IP!

**Improved Flow:**
1. Tenant creates router record FIRST with status='pending'
2. System auto-assigns next available VPN IP
3. Tenant gets IP + commands
4. Tenant configures MikroTik
5. Tenant updates router with public key
6. System marks VPN as 'configured'

**Updated API:**
```python
@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_router_reserve_vpn_ip(request):
    """
    Reserve a VPN IP for a new router
    Creates router record with 'pending' status
    """
    tenant = request.tenant
    
    # Check quota
    if not tenant.can_add_router():
        return Response({
            "success": False,
            "error": "Router limit reached for your plan"
        }, status=403)
    
    try:
        # Find next available IP (checking vpn_ip field)
        next_ip = find_next_available_vpn_ip()
        
        # Create router with reserved IP
        router = Router.objects.create(
            tenant=tenant,
            name=f"Router {tenant.router_set.count() + 1}",
            host=next_ip,  # Temporary, will update after config
            vpn_ip=next_ip,  # Reserved!
            vpn_status='pending',
            port=8728,
            username='admin',
            password='',  # Tenant will set
        )
        
        # Generate setup instructions
        config = generate_wireguard_config(router)
        
        return Response({
            "success": True,
            "router_id": router.id,
            "vpn_ip": next_ip,
            "reservation_expires": "24 hours",
            "wireguard_config": config,
            "next_step": f"POST /api/portal/router/{router.id}/wireguard/"
        })
        
    except Exception as e:
        return Response({
            "success": False,
            "error": str(e)
        }, status=500)
```

---

### Priority 3: Capture WireGuard Public Key (HIGH)

**Problem:** We don't collect the router's WireGuard public key.

**Solution:** Add endpoint to capture key after router configuration:

```python
@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_router_submit_wireguard_key(request, router_id):
    """
    Submit router's WireGuard public key after configuration
    This triggers VPS peer addition
    """
    tenant = request.tenant
    
    try:
        router = Router.objects.get(id=router_id, tenant=tenant)
    except Router.DoesNotExist:
        return Response({
            "success": False,
            "error": "Router not found"
        }, status=404)
    
    public_key = request.data.get('public_key', '').strip()
    
    if not public_key:
        return Response({
            "success": False,
            "error": "public_key is required"
        }, status=400)
    
    # Validate key format (base64, 44 characters)
    if len(public_key) != 44 or not public_key.endswith('='):
        return Response({
            "success": False,
            "error": "Invalid WireGuard public key format"
        }, status=400)
    
    # Check for duplicate key
    if Router.objects.filter(vpn_public_key=public_key).exclude(id=router_id).exists():
        return Response({
            "success": False,
            "error": "This public key is already in use"
        }, status=400)
    
    # Update router
    router.vpn_public_key = public_key
    router.vpn_status = 'configured'
    router.vpn_configured_at = timezone.now()
    router.save()
    
    # OPTIONAL: Auto-add peer to VPS (requires SSH access)
    # add_vps_wireguard_peer(router.vpn_ip, public_key)
    
    # For now, notify admin
    notify_admin_new_wireguard_peer(router)
    
    return Response({
        "success": True,
        "message": "Public key received. Admin will add peer to VPS within 1 hour.",
        "status": router.vpn_status,
        "next_step": "Wait for admin approval, then test connection"
    })
```

---

### Priority 4: VPS Peer Auto-Addition (MEDIUM)

**Problem:** Admin must manually SSH to VPS and run `wg set` command.

**Solution:** Automate VPS peer addition via SSH:

```python
import paramiko
from django.conf import settings

def add_vps_wireguard_peer(router):
    """
    Automatically add WireGuard peer to VPS server
    Requires SSH access to VPS
    """
    try:
        # VPS credentials (store in .env)
        vps_host = settings.VPS_HOST  # 66.29.143.116
        vps_user = settings.VPS_USER  # root
        vps_key_path = settings.VPS_SSH_KEY  # /path/to/key
        
        # Connect via SSH
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(vps_host, username=vps_user, key_filename=vps_key_path)
        
        # Add WireGuard peer
        command = f"""
        wg set wg0 peer {router.vpn_public_key} allowed-ips {router.vpn_ip}/32
        wg-quick save wg0
        """
        
        stdin, stdout, stderr = ssh.exec_command(command)
        
        exit_code = stdout.channel.recv_exit_status()
        
        if exit_code == 0:
            # Update router status
            router.vpn_status = 'vps_ready'
            router.save()
            
            logger.info(f"✅ VPS peer added for router {router.id} ({router.vpn_ip})")
            return True
        else:
            error = stderr.read().decode()
            logger.error(f"❌ Failed to add VPS peer: {error}")
            return False
            
    except Exception as e:
        logger.error(f"❌ VPS SSH error: {e}")
        return False
    finally:
        ssh.close()
```

**Required .env variables:**
```bash
VPS_HOST=66.29.143.116
VPS_USER=root
VPS_SSH_KEY=/path/to/vps_ssh_key
WIREGUARD_INTERFACE=wg0
```

---

### Priority 5: IP Reservation Cleanup (LOW)

**Problem:** Tenants reserve IP but abandon setup.

**Solution:** Auto-cleanup pending routers after 24 hours:

```python
# billing/management/commands/cleanup_pending_vpn_ips.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from billing.models import Router

class Command(BaseCommand):
    help = 'Clean up pending VPN IP reservations older than 24 hours'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=24)
        
        pending_routers = Router.objects.filter(
            vpn_status='pending',
            created_at__lt=cutoff
        )
        
        count = pending_routers.count()
        
        for router in pending_routers:
            self.stdout.write(
                f"🗑️  Deleting abandoned router: {router.name} ({router.vpn_ip})"
            )
            router.delete()
        
        self.stdout.write(
            self.style.SUCCESS(f"✅ Cleaned up {count} abandoned VPN reservations")
        )
```

**Cron job:**
```bash
# Run every 6 hours
0 */6 * * * cd /var/www/kitonga && /var/www/kitonga/venv/bin/python manage.py cleanup_pending_vpn_ips >> /var/log/kitonga/vpn_cleanup.log 2>&1
```

---

## 🔐 Security Best Practices

### 1. Rate Limiting
```python
from rest_framework.throttling import UserRateThrottle

class VPNConfigThrottle(UserRateThrottle):
    rate = '5/hour'  # Max 5 IP reservations per hour

@permission_classes([TenantAPIKeyPermission])
@throttle_classes([VPNConfigThrottle])
def portal_router_reserve_vpn_ip(request):
    # ...
```

### 2. Audit Logging
```python
# Log all VPN IP allocations
logger.info(
    f"🔐 VPN IP allocated: {next_ip} | "
    f"Tenant: {tenant.slug} | "
    f"Router: {router.id} | "
    f"Time: {timezone.now()}"
)
```

### 3. IP Validation
```python
def validate_vpn_ip(ip_str):
    """Ensure IP is in valid range"""
    try:
        ip = ipaddress.ip_address(ip_str)
        network = ipaddress.ip_network('10.100.0.0/24')
        
        if ip not in network:
            raise ValueError("IP not in VPN range")
        
        if ip in [
            ipaddress.ip_address('10.100.0.0'),
            ipaddress.ip_address('10.100.0.1'),
            ipaddress.ip_address('10.100.0.255'),
        ]:
            raise ValueError("IP is reserved")
        
        return True
    except ValueError as e:
        return False
```

### 4. Public Key Validation
```python
import base64

def validate_wireguard_public_key(key):
    """Validate WireGuard public key format"""
    try:
        # Must be 44 characters base64
        if len(key) != 44:
            return False
        
        # Must be valid base64
        decoded = base64.b64decode(key)
        
        # Must be 32 bytes (256 bits)
        if len(decoded) != 32:
            return False
        
        return True
    except Exception:
        return False
```

---

## 📋 Implementation Checklist

### Phase 1: Database Updates (Critical)
- [ ] Add `vpn_ip`, `vpn_public_key`, `vpn_status` to Router model
- [ ] Create migration
- [ ] Add unique constraints
- [ ] Add indexes

### Phase 2: API Updates (Critical)
- [ ] Create `portal_router_reserve_vpn_ip` endpoint
- [ ] Create `portal_router_submit_wireguard_key` endpoint
- [ ] Update `portal_router_save_config` to validate VPN IP
- [ ] Add rate limiting

### Phase 3: VPS Automation (Medium)
- [ ] Add VPS SSH credentials to .env
- [ ] Create `add_vps_wireguard_peer()` function
- [ ] Test SSH connection to VPS
- [ ] Add error handling and retry logic

### Phase 4: Cleanup & Monitoring (Low)
- [ ] Create `cleanup_pending_vpn_ips` command
- [ ] Add cron job for cleanup
- [ ] Add monitoring dashboard for VPN status
- [ ] Create admin notification system

---

## 🚨 Risk Assessment

### Without Improvements:
- **IP Conflicts:** MEDIUM risk - Race condition possible
- **IP Leakage:** HIGH risk - Abandoned setups waste IPs
- **Manual Errors:** HIGH risk - Admin typos in VPS config
- **No Audit Trail:** MEDIUM risk - Can't track who got which IP

### With Improvements:
- **IP Conflicts:** LOW risk - Database constraints prevent duplicates
- **IP Leakage:** LOW risk - Auto-cleanup after 24 hours
- **Manual Errors:** LOW risk - Automated VPS configuration
- **No Audit Trail:** NONE - Full logging in place

---

## 💡 Recommendation

**Minimum viable security:** Implement Phase 1 + Phase 2 (database + API updates)

This gives you:
✅ IP reservation system  
✅ Conflict prevention  
✅ Public key validation  
✅ Status tracking

**Optional but recommended:** Phase 3 (VPS automation)

This gives you:
✅ No manual admin work  
✅ Faster setup  
✅ Fewer errors

**For production:** All 4 phases

Full automation with monitoring and cleanup.

---

## 🎯 Your Choice

Do you want me to:

**Option A:** Keep current implementation (quick but requires manual VPS setup)  
**Option B:** Add IP reservation system (safer, prevents conflicts)  
**Option C:** Full automation including VPS peer addition (best, zero manual work)

Let me know and I'll implement it! 🚀
