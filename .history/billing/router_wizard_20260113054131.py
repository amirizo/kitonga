"""
Router Configuration Wizard for Kitonga Tenant Portal
Provides step-by-step router setup and auto-configuration
"""

import logging
import socket
from typing import Dict, List, Optional, Any, Tuple
from django.utils import timezone
from django.conf import settings

from .models import Tenant, Router, Location

logger = logging.getLogger(__name__)

# Try to import routeros-api
try:
    import routeros_api
except ImportError:
    routeros_api = None


class RouterWizard:
    """
    Router configuration wizard for tenants
    Handles connection testing, auto-configuration, and setup validation
    """

    def __init__(self, tenant: Tenant, router: Optional[Router] = None):
        self.tenant = tenant
        self.router = router
        self.api = None
        self.errors = []
        self.warnings = []

    def test_connection(
        self,
        host: str,
        port: int = 8728,
        username: str = "admin",
        password: str = "",
        use_ssl: bool = False,
        timeout: int = 10,
    ) -> Dict[str, Any]:
        """
        Test connection to a MikroTik router

        Returns:
            dict with connection status and router info
        """
        if routeros_api is None:
            return {
                "success": False,
                "error": "RouterOS API library not installed. Run: pip install routeros-api",
                "step": "library_check",
            }

        # Step 1: Check if host is reachable
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()

            if result != 0:
                return {
                    "success": False,
                    "error": f"Cannot reach {host}:{port}. Check firewall settings and ensure API is enabled.",
                    "step": "connectivity",
                    "troubleshooting": [
                        "Ensure the router IP is correct",
                        "Check that API service is enabled on the router",
                        f"Verify port {port} is not blocked by firewall",
                        "Try from the same network as the router",
                    ],
                }
        except socket.error as e:
            return {
                "success": False,
                "error": f"Network error: {str(e)}",
                "step": "connectivity",
            }

        # Step 2: Try to connect via API
        try:
            ssl_verify = False  # Allow self-signed certificates

            try:
                # Try with keepalive support
                pool = routeros_api.RouterOsApiPool(
                    host,
                    username=username,
                    password=password,
                    port=port,
                    use_ssl=use_ssl,
                    plaintext_login=True,
                    use_keepalive=True,
                    ssl_verify=ssl_verify,
                )
            except TypeError:
                # Fallback for older library versions
                pool = routeros_api.RouterOsApiPool(
                    host,
                    username=username,
                    password=password,
                    port=port,
                    use_ssl=use_ssl,
                    plaintext_login=True,
                    ssl_verify=ssl_verify,
                )

            self.api = pool.get_api()

            # Step 3: Get router info
            router_info = self._get_router_info()

            # Step 4: Check hotspot configuration
            hotspot_status = self._check_hotspot_status()

            # Close connection
            try:
                self.api.get_communicator().close()
            except:
                pass

            return {
                "success": True,
                "message": "Connection successful!",
                "step": "connected",
                "router_info": router_info,
                "hotspot_status": hotspot_status,
                "recommendations": self._get_recommendations(hotspot_status),
            }

        except routeros_api.exceptions.RouterOsApiConnectionError as e:
            return {
                "success": False,
                "error": f"Connection failed: {str(e)}",
                "step": "authentication",
                "troubleshooting": [
                    "Verify username and password",
                    "Check if API access is allowed for this user",
                    "Ensure API service is enabled",
                    "Check IP > Services in Winbox",
                ],
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "step": "unknown",
            }

    def _get_router_info(self) -> Dict[str, Any]:
        """Get router system information"""
        if not self.api:
            return {}

        try:
            # Get identity
            identity_resource = self.api.get_resource("/system/identity")
            identity = identity_resource.get()[0] if identity_resource.get() else {}

            # Get router board info
            routerboard_resource = self.api.get_resource("/system/routerboard")
            routerboard = (
                routerboard_resource.get()[0] if routerboard_resource.get() else {}
            )

            # Get resource info
            resource_resource = self.api.get_resource("/system/resource")
            resource = resource_resource.get()[0] if resource_resource.get() else {}

            return {
                "identity": identity.get("name", "Unknown"),
                "model": routerboard.get("model", "Unknown"),
                "serial_number": routerboard.get("serial-number", "Unknown"),
                "firmware": routerboard.get("firmware", "Unknown"),
                "version": resource.get("version", "Unknown"),
                "uptime": resource.get("uptime", "Unknown"),
                "cpu_load": resource.get("cpu-load", "Unknown"),
                "free_memory": resource.get("free-memory", "Unknown"),
                "total_memory": resource.get("total-memory", "Unknown"),
            }
        except Exception as e:
            logger.error(f"Failed to get router info: {e}")
            return {"error": str(e)}

    def _check_hotspot_status(self) -> Dict[str, Any]:
        """Check if hotspot is configured and running"""
        if not self.api:
            return {}

        try:
            # Check hotspot servers
            hotspot_resource = self.api.get_resource("/ip/hotspot")
            hotspot_servers = hotspot_resource.get()

            # Check hotspot profiles
            profile_resource = self.api.get_resource("/ip/hotspot/profile")
            profiles = profile_resource.get()

            # Check hotspot users
            user_resource = self.api.get_resource("/ip/hotspot/user")
            users = user_resource.get()

            # Check active connections
            active_resource = self.api.get_resource("/ip/hotspot/active")
            active = active_resource.get()

            # Get interfaces
            interface_resource = self.api.get_resource("/interface")
            interfaces = interface_resource.get()

            return {
                "configured": len(hotspot_servers) > 0,
                "servers": [
                    {
                        "name": s.get("name", ""),
                        "interface": s.get("interface", ""),
                        "disabled": s.get("disabled", "false") == "true",
                        "profile": s.get("profile", ""),
                    }
                    for s in hotspot_servers
                ],
                "profiles": [p.get("name", "") for p in profiles],
                "user_count": len(users),
                "active_count": len(active),
                "available_interfaces": [
                    {
                        "name": i.get("name", ""),
                        "type": i.get("type", ""),
                        "running": i.get("running", "false") == "true",
                    }
                    for i in interfaces
                    if i.get("type") in ["bridge", "ether", "wlan"]
                ],
            }
        except Exception as e:
            logger.error(f"Failed to check hotspot status: {e}")
            return {"error": str(e)}

    def _get_recommendations(self, hotspot_status: Dict) -> List[str]:
        """Generate setup recommendations based on router status"""
        recommendations = []

        if not hotspot_status.get("configured"):
            recommendations.append(
                "Hotspot is not configured. Use the auto-setup feature to configure it."
            )

        if hotspot_status.get("configured"):
            servers = hotspot_status.get("servers", [])
            for server in servers:
                if server.get("disabled"):
                    recommendations.append(
                        f"Hotspot server '{server.get('name')}' is disabled. Enable it for the system to work."
                    )

        if hotspot_status.get("user_count", 0) == 0:
            recommendations.append(
                "No hotspot users configured. Users will be created automatically when they purchase access."
            )

        return recommendations

    def auto_configure_hotspot(
        self,
        interface: str = "bridge",
        server_name: str = "kitonga-hotspot",
        profile_name: str = "kitonga-profile",
        network: str = "192.168.88.0/24",
        gateway: str = "192.168.88.1",
    ) -> Dict[str, Any]:
        """
        Auto-configure hotspot on the router

        This creates:
        1. Hotspot profile with Kitonga branding
        2. Hotspot server on the specified interface
        3. Necessary firewall rules
        4. DHCP configuration (if needed)
        """
        if not self.api:
            return {"success": False, "error": "Not connected to router"}

        steps_completed = []

        try:
            # Step 1: Create/update hotspot profile
            try:
                profile_resource = self.api.get_resource("/ip/hotspot/profile")

                # Check if profile exists
                existing = [
                    p for p in profile_resource.get() if p.get("name") == profile_name
                ]

                profile_settings = {
                    "name": profile_name,
                    "hotspot-address": gateway,
                    "login-by": "http-chap,http-pap,mac",
                    "html-directory": "hotspot",
                    "use-radius": "no",
                }

                if existing:
                    profile_resource.set(id=existing[0]["id"], **profile_settings)
                else:
                    profile_resource.add(**profile_settings)

                steps_completed.append(
                    {
                        "step": "profile",
                        "status": "success",
                        "message": f'Hotspot profile "{profile_name}" configured',
                    }
                )
            except Exception as e:
                steps_completed.append(
                    {"step": "profile", "status": "error", "message": str(e)}
                )

            # Step 2: Create/update hotspot server
            try:
                hotspot_resource = self.api.get_resource("/ip/hotspot")

                # Check if server exists
                existing = [
                    s for s in hotspot_resource.get() if s.get("name") == server_name
                ]

                server_settings = {
                    "name": server_name,
                    "interface": interface,
                    "profile": profile_name,
                    "disabled": "no",
                }

                if existing:
                    hotspot_resource.set(id=existing[0]["id"], **server_settings)
                else:
                    hotspot_resource.add(**server_settings)

                steps_completed.append(
                    {
                        "step": "server",
                        "status": "success",
                        "message": f'Hotspot server "{server_name}" configured on {interface}',
                    }
                )
            except Exception as e:
                steps_completed.append(
                    {"step": "server", "status": "error", "message": str(e)}
                )

            # Step 3: Configure walled garden (allow Kitonga API)
            try:
                walled_garden = self.api.get_resource("/ip/hotspot/walled-garden")

                # Add Kitonga API to walled garden
                kitonga_domains = [
                    "api.kitonga.klikcell.com",
                    "kitonga.klikcell.com",
                    "*.clickpesa.com",
                ]

                existing_entries = walled_garden.get()
                existing_hosts = [e.get("dst-host", "") for e in existing_entries]

                for domain in kitonga_domains:
                    if domain not in existing_hosts:
                        walled_garden.add(
                            **{
                                "dst-host": domain,
                                "action": "allow",
                                "server": server_name,
                            }
                        )

                steps_completed.append(
                    {
                        "step": "walled_garden",
                        "status": "success",
                        "message": "Walled garden configured for Kitonga API",
                    }
                )
            except Exception as e:
                steps_completed.append(
                    {
                        "step": "walled_garden",
                        "status": "warning",
                        "message": f"Walled garden configuration warning: {str(e)}",
                    }
                )

            # Determine overall success
            errors = [s for s in steps_completed if s["status"] == "error"]

            return {
                "success": len(errors) == 0,
                "steps": steps_completed,
                "message": (
                    "Hotspot configuration completed successfully!"
                    if len(errors) == 0
                    else "Some steps failed"
                ),
                "next_steps": [
                    "Upload custom login page to the router",
                    "Configure the login page to call Kitonga API",
                    "Test the captive portal flow",
                ],
            }

        except Exception as e:
            return {"success": False, "error": str(e), "steps": steps_completed}

    def save_router_config(
        self,
        name: str,
        host: str,
        port: int = 8728,
        username: str = "admin",
        password: str = "",
        use_ssl: bool = False,
        location_id: Optional[int] = None,
        hotspot_interface: str = "bridge",
        hotspot_profile: str = "default",
    ) -> Tuple[bool, str, Optional[Router]]:
        """
        Save router configuration to database

        Returns:
            Tuple of (success, message, router_instance)
        """
        # Check tenant router limit
        from .subscription import UsageMeter

        meter = UsageMeter(self.tenant)
        can_add, limit_message = meter.can_add_router()

        if not can_add and not self.router:  # Only check if adding new
            return False, limit_message, None

        try:
            # Test connection first
            test_result = self.test_connection(
                host=host,
                port=port,
                username=username,
                password=password,
                use_ssl=use_ssl,
            )

            router_info = test_result.get("router_info", {})

            # Get location if specified
            location = None
            if location_id:
                try:
                    location = Location.objects.get(id=location_id, tenant=self.tenant)
                except Location.DoesNotExist:
                    pass

            if self.router:
                # Update existing router
                self.router.name = name
                self.router.host = host
                self.router.port = port
                self.router.username = username
                if password:  # Only update password if provided
                    self.router.password = password
                self.router.use_ssl = use_ssl
                self.router.location = location
                self.router.hotspot_interface = hotspot_interface
                self.router.hotspot_profile = hotspot_profile
                self.router.router_model = router_info.get("model", "")
                self.router.router_version = router_info.get("version", "")
                self.router.router_identity = router_info.get("identity", "")
                self.router.status = "online" if test_result.get("success") else "error"
                self.router.last_seen = (
                    timezone.now() if test_result.get("success") else None
                )
                self.router.last_error = (
                    "" if test_result.get("success") else test_result.get("error", "")
                )
                self.router.save()

                return True, "Router configuration updated successfully", self.router
            else:
                # Create new router
                router = Router.objects.create(
                    tenant=self.tenant,
                    name=name,
                    host=host,
                    port=port,
                    username=username,
                    password=password,
                    use_ssl=use_ssl,
                    location=location,
                    hotspot_interface=hotspot_interface,
                    hotspot_profile=hotspot_profile,
                    router_model=router_info.get("model", ""),
                    router_version=router_info.get("version", ""),
                    router_identity=router_info.get("identity", ""),
                    status="online" if test_result.get("success") else "configuring",
                    last_seen=timezone.now() if test_result.get("success") else None,
                    last_error=(
                        ""
                        if test_result.get("success")
                        else test_result.get("error", "")
                    ),
                )

                return True, "Router added successfully", router

        except Exception as e:
            logger.error(f"Failed to save router config: {e}")
            return False, str(e), None

    def generate_hotspot_html(self) -> Dict[str, str]:
        """
        Generate custom hotspot HTML pages for the tenant

        Returns dict with HTML content for each page type
        """
        tenant = self.tenant

        # Base CSS with tenant branding
        base_css = f"""
        :root {{
            --primary-color: {tenant.primary_color};
            --secondary-color: {tenant.secondary_color};
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
            min-height: 100vh;
            margin: 0;
            padding: 20px;
            box-sizing: border-box;
        }}
        .container {{
            max-width: 400px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            padding: 30px;
        }}
        .logo {{
            text-align: center;
            margin-bottom: 20px;
        }}
        .logo img {{
            max-width: 150px;
            height: auto;
        }}
        h1, h2 {{
            color: var(--primary-color);
            text-align: center;
            margin: 0 0 20px 0;
        }}
        .form-group {{
            margin-bottom: 20px;
        }}
        label {{
            display: block;
            margin-bottom: 5px;
            color: #333;
            font-weight: 500;
        }}
        input[type="text"], input[type="tel"], select {{
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
            box-sizing: border-box;
            transition: border-color 0.3s;
        }}
        input:focus, select:focus {{
            outline: none;
            border-color: var(--primary-color);
        }}
        .btn {{
            width: 100%;
            padding: 14px;
            background: var(--primary-color);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.2);
        }}
        .btn-secondary {{
            background: var(--secondary-color);
        }}
        .bundles {{
            display: grid;
            gap: 10px;
            margin: 20px 0;
        }}
        .bundle-card {{
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            padding: 15px;
            cursor: pointer;
            transition: all 0.3s;
        }}
        .bundle-card:hover, .bundle-card.selected {{
            border-color: var(--primary-color);
            background: #f8f9ff;
        }}
        .bundle-name {{
            font-weight: 600;
            font-size: 18px;
        }}
        .bundle-price {{
            color: var(--primary-color);
            font-size: 24px;
            font-weight: 700;
        }}
        .bundle-duration {{
            color: #666;
            font-size: 14px;
        }}
        .message {{
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
            text-align: center;
        }}
        .message.success {{
            background: #d4edda;
            color: #155724;
        }}
        .message.error {{
            background: #f8d7da;
            color: #721c24;
        }}
        .message.info {{
            background: #d1ecf1;
            color: #0c5460;
        }}
        """

        # Login page HTML
        login_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{tenant.business_name} - WiFi Login</title>
    <style>{base_css}</style>
</head>
<body>
    <div class="container">
        <div class="logo">
            <h2>{tenant.business_name}</h2>
        </div>
        
        <h1>WiFi Access</h1>
        
        <div id="phone-section">
            <form id="phone-form">
                <div class="form-group">
                    <label for="phone">Phone Number</label>
                    <input type="tel" id="phone" name="phone" placeholder="0712345678" required>
                </div>
                <button type="submit" class="btn">Continue</button>
            </form>
        </div>
        
        <div id="bundles-section" style="display:none;">
            <p>Select a package:</p>
            <div id="bundles" class="bundles"></div>
            <button id="pay-btn" class="btn" style="display:none;">Pay Now</button>
            
            <div style="margin-top: 20px; text-align: center;">
                <p>Have a voucher code?</p>
                <input type="text" id="voucher" placeholder="XXXX-XXXX-XXXX">
                <button id="voucher-btn" class="btn btn-secondary" style="margin-top: 10px;">Redeem Voucher</button>
            </div>
        </div>
        
        <div id="message" class="message" style="display:none;"></div>
    </div>
    
    <script>
    const API_BASE = 'https://api.kitonga.klikcell.com/api';
    const TENANT_KEY = '{tenant.api_key}';
    
    let selectedBundle = null;
    let phoneNumber = '';
    
    document.getElementById('phone-form').onsubmit = async (e) => {{
        e.preventDefault();
        phoneNumber = document.getElementById('phone').value;
        
        // Fetch bundles
        const res = await fetch(`${{API_BASE}}/bundles/?tenant={tenant.slug}`);
        const data = await res.json();
        
        const bundlesDiv = document.getElementById('bundles');
        bundlesDiv.innerHTML = data.map(b => `
            <div class="bundle-card" data-id="${{b.id}}" onclick="selectBundle(${{b.id}})">
                <div class="bundle-name">${{b.name}}</div>
                <div class="bundle-price">TZS ${{b.price.toLocaleString()}}</div>
                <div class="bundle-duration">${{b.duration_hours}} hours</div>
            </div>
        `).join('');
        
        document.getElementById('phone-section').style.display = 'none';
        document.getElementById('bundles-section').style.display = 'block';
    }};
    
    function selectBundle(id) {{
        selectedBundle = id;
        document.querySelectorAll('.bundle-card').forEach(c => c.classList.remove('selected'));
        document.querySelector(`[data-id="${{id}}"]`).classList.add('selected');
        document.getElementById('pay-btn').style.display = 'block';
    }}
    
    document.getElementById('pay-btn').onclick = async () => {{
        showMessage('Processing payment...', 'info');
        
        const res = await fetch(`${{API_BASE}}/initiate-payment/`, {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json', 'X-API-Key': TENANT_KEY}},
            body: JSON.stringify({{phone_number: phoneNumber, bundle_id: selectedBundle}})
        }});
        
        const data = await res.json();
        if (data.success) {{
            showMessage('Check your phone for payment prompt!', 'success');
        }} else {{
            showMessage(data.message || 'Payment failed', 'error');
        }}
    }};
    
    document.getElementById('voucher-btn').onclick = async () => {{
        const code = document.getElementById('voucher').value;
        if (!code) return;
        
        const res = await fetch(`${{API_BASE}}/vouchers/redeem/`, {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json', 'X-API-Key': TENANT_KEY}},
            body: JSON.stringify({{voucher_code: code, phone_number: phoneNumber}})
        }});
        
        const data = await res.json();
        if (data.success) {{
            showMessage('Voucher redeemed! Connecting...', 'success');
            setTimeout(() => location.reload(), 2000);
        }} else {{
            showMessage(data.message || 'Invalid voucher', 'error');
        }}
    }};
    
    function showMessage(text, type) {{
        const msg = document.getElementById('message');
        msg.textContent = text;
        msg.className = `message ${{type}}`;
        msg.style.display = 'block';
    }}
    </script>
</body>
</html>
"""

        # Status page HTML
        status_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{tenant.business_name} - Connection Status</title>
    <style>{base_css}</style>
</head>
<body>
    <div class="container">
        <div class="logo">
            <h2>{tenant.business_name}</h2>
        </div>
        
        <h1>✓ Connected</h1>
        
        <div class="message success">
            <p>You're connected to WiFi!</p>
        </div>
        
        <div id="status">
            <p><strong>Time Remaining:</strong> <span id="time">--</span></p>
            <p><strong>Expires:</strong> <span id="expires">--</span></p>
        </div>
        
        <button class="btn" onclick="location.href='$(link-logout)'">Logout</button>
        <button class="btn btn-secondary" style="margin-top: 10px;" onclick="location.href='$(link-login)'">Extend Access</button>
    </div>
</body>
</html>
"""

        # Logout page HTML
        logout_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{tenant.business_name} - Logged Out</title>
    <style>{base_css}</style>
</head>
<body>
    <div class="container">
        <div class="logo">
            <h2>{tenant.business_name}</h2>
        </div>
        
        <h1>Logged Out</h1>
        
        <div class="message info">
            <p>You have been disconnected from WiFi.</p>
        </div>
        
        <button class="btn" onclick="location.href='$(link-login)'">Connect Again</button>
    </div>
</body>
</html>
"""

        return {
            "login.html": login_html,
            "status.html": status_html,
            "logout.html": logout_html,
            "alogin.html": login_html,  # After login redirect
            "error.html": f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{tenant.business_name} - Error</title>
    <style>{base_css}</style>
</head>
<body>
    <div class="container">
        <div class="logo">
            <h2>{tenant.business_name}</h2>
        </div>
        
        <h1>Connection Error</h1>
        
        <div class="message error">
            <p>$(error)</p>
        </div>
        
        <button class="btn" onclick="location.href='$(link-login)'">Try Again</button>
    </div>
</body>
</html>
""",
        }

    def upload_hotspot_html(self) -> Dict[str, Any]:
        """
        Upload custom hotspot HTML to the router via FTP or API
        This is a placeholder - actual implementation depends on router access method
        """
        if not self.api or not self.router:
            return {"success": False, "error": "Not connected to router"}

        html_files = self.generate_hotspot_html()

        # Note: Uploading files to MikroTik typically requires FTP access
        # The API doesn't directly support file uploads
        # This would need FTP implementation or manual upload

        return {
            "success": True,
            "message": "HTML files generated. Please upload manually via FTP or Winbox.",
            "files": list(html_files.keys()),
            "instructions": [
                "Connect to the router via FTP or Winbox",
                "Navigate to the hotspot folder (usually /flash/hotspot/)",
                "Upload the generated HTML files",
                "Restart the hotspot server",
            ],
            "html_content": html_files,  # Provide content for manual upload
        }


class RouterHealthChecker:
    """
    Monitor router health and connectivity
    """

    def __init__(self, tenant: Tenant):
        self.tenant = tenant

    def check_all_routers(self) -> List[Dict[str, Any]]:
        """Check health of all tenant routers"""
        routers = Router.objects.filter(tenant=self.tenant, is_active=True)
        results = []

        for router in routers:
            results.append(self.check_router(router))

        return results

    def check_router(self, router: Router) -> Dict[str, Any]:
        """Check health of a specific router"""
        wizard = RouterWizard(self.tenant, router)

        result = wizard.test_connection(
            host=router.host,
            port=router.port,
            username=router.username,
            password=router.password,
            use_ssl=router.use_ssl,
            timeout=5,
        )

        # Update router status
        if result.get("success"):
            router.status = "online"
            router.last_seen = timezone.now()
            router.last_error = ""
        else:
            router.status = "offline"
            router.last_error = result.get("error", "Connection failed")

        router.save()

        return {
            "router_id": router.id,
            "name": router.name,
            "host": router.host,
            **result,
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get health summary for all routers"""
        routers = Router.objects.filter(tenant=self.tenant, is_active=True)

        return {
            "total": routers.count(),
            "online": routers.filter(status="online").count(),
            "offline": routers.filter(status="offline").count(),
            "configuring": routers.filter(status="configuring").count(),
            "error": routers.filter(status="error").count(),
        }
