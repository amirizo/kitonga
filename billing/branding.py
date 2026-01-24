"""
Branding and White-Label Customization for Kitonga Tenant Portal
Handles tenant branding, themes, and customization options
"""
import logging
import os
import re
from typing import Dict, Any, Optional, Tuple
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.conf import settings
from PIL import Image
import io

from .models import Tenant

logger = logging.getLogger(__name__)


class BrandingManager:
    """
    Manage tenant branding and white-label customization
    """
    
    # Allowed color format
    HEX_COLOR_PATTERN = re.compile(r'^#[0-9A-Fa-f]{6}$')
    
    # Default branding values
    DEFAULT_PRIMARY_COLOR = '#3B82F6'
    DEFAULT_SECONDARY_COLOR = '#1E40AF'
    
    def __init__(self, tenant: Tenant):
        self.tenant = tenant
    
    def get_branding(self) -> Dict[str, Any]:
        """Get current branding configuration"""
        return {
            'business_name': self.tenant.business_name,
            'logo_url': self.tenant.logo.url if self.tenant.logo else None,
            'primary_color': self.tenant.primary_color or self.DEFAULT_PRIMARY_COLOR,
            'secondary_color': self.tenant.secondary_color or self.DEFAULT_SECONDARY_COLOR,
            'custom_domain': self.tenant.custom_domain,
            'slug': self.tenant.slug,
            'portal_url': self._get_portal_url(),
        }
    
    def _get_portal_url(self) -> str:
        """Get the tenant's portal URL"""
        if self.tenant.custom_domain:
            return f"https://{self.tenant.custom_domain}"
        return f"https://{self.tenant.slug}.kitonga.klikcell.com"
    
    def update_colors(
        self,
        primary_color: Optional[str] = None,
        secondary_color: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Update tenant brand colors
        
        Args:
            primary_color: Hex color code (e.g., #3B82F6)
            secondary_color: Hex color code (e.g., #1E40AF)
        
        Returns:
            Tuple of (success, message)
        """
        errors = []
        
        if primary_color:
            if self.HEX_COLOR_PATTERN.match(primary_color):
                self.tenant.primary_color = primary_color.upper()
            else:
                errors.append(f"Invalid primary color format: {primary_color}")
        
        if secondary_color:
            if self.HEX_COLOR_PATTERN.match(secondary_color):
                self.tenant.secondary_color = secondary_color.upper()
            else:
                errors.append(f"Invalid secondary color format: {secondary_color}")
        
        if errors:
            return False, "; ".join(errors)
        
        self.tenant.save()
        return True, "Colors updated successfully"
    
    def update_logo(self, logo_file) -> Tuple[bool, str]:
        """
        Update tenant logo
        
        Args:
            logo_file: Uploaded file object
        
        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate file type
            allowed_types = ['image/png', 'image/jpeg', 'image/gif', 'image/webp']
            content_type = getattr(logo_file, 'content_type', None)
            
            if content_type and content_type not in allowed_types:
                return False, f"Invalid file type: {content_type}. Allowed: PNG, JPEG, GIF, WebP"
            
            # Read and validate image
            image_data = logo_file.read()
            logo_file.seek(0)  # Reset file pointer
            
            try:
                img = Image.open(io.BytesIO(image_data))
            except Exception:
                return False, "Invalid image file"
            
            # Check dimensions
            max_size = (500, 500)
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                # Resize image
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Convert to PNG for consistency
            output = io.BytesIO()
            img.save(output, format='PNG', optimize=True)
            output.seek(0)
            
            # Save to storage
            filename = f"tenant_logos/{self.tenant.slug}_logo.png"
            
            # Delete old logo if exists
            if self.tenant.logo:
                try:
                    self.tenant.logo.delete(save=False)
                except Exception:
                    pass
            
            # Save new logo
            self.tenant.logo.save(
                f"{self.tenant.slug}_logo.png",
                ContentFile(output.getvalue()),
                save=True
            )
            
            return True, "Logo updated successfully"
            
        except Exception as e:
            logger.error(f"Failed to update logo for {self.tenant.slug}: {e}")
            return False, str(e)
    
    def remove_logo(self) -> Tuple[bool, str]:
        """Remove tenant logo"""
        try:
            if self.tenant.logo:
                self.tenant.logo.delete(save=True)
            return True, "Logo removed successfully"
        except Exception as e:
            return False, str(e)
    
    def update_custom_domain(self, domain: str) -> Tuple[bool, str]:
        """
        Update custom domain
        
        Args:
            domain: Custom domain (e.g., wifi.mybusiness.com)
        
        Returns:
            Tuple of (success, message)
        """
        # Check subscription allows custom domain
        if self.tenant.subscription_plan and not self.tenant.subscription_plan.custom_domain:
            return False, "Custom domain not available in your subscription plan"
        
        # Validate domain format
        domain = domain.lower().strip()
        domain_pattern = re.compile(
            r'^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$'
        )
        
        if not domain_pattern.match(domain):
            return False, "Invalid domain format"
        
        # Check if domain is already in use
        existing = Tenant.objects.filter(custom_domain=domain).exclude(id=self.tenant.id).first()
        if existing:
            return False, "Domain is already in use"
        
        self.tenant.custom_domain = domain
        self.tenant.save()
        
        return True, f"Custom domain set to {domain}. Please configure DNS records."
    
    def remove_custom_domain(self) -> Tuple[bool, str]:
        """Remove custom domain"""
        self.tenant.custom_domain = None
        self.tenant.save()
        return True, "Custom domain removed"
    
    def get_dns_instructions(self) -> Dict[str, Any]:
        """Get DNS configuration instructions for custom domain"""
        if not self.tenant.custom_domain:
            return {
                'configured': False,
                'message': 'No custom domain configured'
            }
        
        return {
            'configured': True,
            'domain': self.tenant.custom_domain,
            'records': [
                {
                    'type': 'CNAME',
                    'name': self.tenant.custom_domain,
                    'value': 'kitonga.klikcell.com',
                    'description': 'Point your domain to Kitonga servers'
                },
                {
                    'type': 'TXT',
                    'name': f'_kitonga.{self.tenant.custom_domain}',
                    'value': f'tenant={self.tenant.slug}',
                    'description': 'Verify domain ownership'
                }
            ],
            'instructions': [
                f"1. Log in to your domain registrar (e.g., GoDaddy, Namecheap)",
                f"2. Go to DNS settings for {self.tenant.custom_domain.split('.', 1)[1]}",
                f"3. Add the CNAME record pointing to kitonga.klikcell.com",
                f"4. Add the TXT record for verification",
                f"5. Wait for DNS propagation (usually 24-48 hours)",
                f"6. Contact support if you need SSL certificate setup"
            ]
        }
    
    def validate_custom_domain(self) -> Dict[str, Any]:
        """Validate custom domain DNS configuration"""
        import socket
        
        if not self.tenant.custom_domain:
            return {
                'valid': False,
                'error': 'No custom domain configured'
            }
        
        domain = self.tenant.custom_domain
        
        try:
            # Check CNAME record
            try:
                answers = socket.getaddrinfo(domain, 80)
                dns_resolved = True
            except socket.gaierror:
                dns_resolved = False
            
            return {
                'valid': dns_resolved,
                'domain': domain,
                'dns_resolved': dns_resolved,
                'message': 'DNS is properly configured' if dns_resolved else 'DNS not yet configured or propagating'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e)
            }


class ThemeGenerator:
    """
    Generate CSS themes based on tenant branding
    """
    
    def __init__(self, tenant: Tenant):
        self.tenant = tenant
        self.branding = BrandingManager(tenant)
    
    def generate_css_variables(self) -> str:
        """Generate CSS custom properties for theming"""
        brand = self.branding.get_branding()
        
        # Generate complementary colors
        primary = brand['primary_color']
        secondary = brand['secondary_color']
        
        return f"""
:root {{
    /* Brand Colors */
    --primary-color: {primary};
    --primary-light: {self._lighten_color(primary, 20)};
    --primary-dark: {self._darken_color(primary, 20)};
    --secondary-color: {secondary};
    --secondary-light: {self._lighten_color(secondary, 20)};
    --secondary-dark: {self._darken_color(secondary, 20)};
    
    /* Text Colors */
    --text-primary: #1f2937;
    --text-secondary: #6b7280;
    --text-muted: #9ca3af;
    --text-on-primary: #ffffff;
    
    /* Background Colors */
    --bg-primary: #ffffff;
    --bg-secondary: #f9fafb;
    --bg-tertiary: #f3f4f6;
    
    /* Border Colors */
    --border-color: #e5e7eb;
    --border-focus: var(--primary-color);
    
    /* Status Colors */
    --success-color: #10b981;
    --warning-color: #f59e0b;
    --error-color: #ef4444;
    --info-color: #3b82f6;
    
    /* Shadows */
    --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    
    /* Border Radius */
    --radius-sm: 4px;
    --radius-md: 8px;
    --radius-lg: 12px;
    --radius-full: 9999px;
    
    /* Transitions */
    --transition-fast: 150ms ease;
    --transition-normal: 250ms ease;
    --transition-slow: 350ms ease;
}}
"""
    
    def _lighten_color(self, hex_color: str, percent: int) -> str:
        """Lighten a hex color by percentage"""
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        new_rgb = tuple(
            min(255, int(c + (255 - c) * percent / 100))
            for c in rgb
        )
        
        return f"#{new_rgb[0]:02x}{new_rgb[1]:02x}{new_rgb[2]:02x}"
    
    def _darken_color(self, hex_color: str, percent: int) -> str:
        """Darken a hex color by percentage"""
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        new_rgb = tuple(
            max(0, int(c * (100 - percent) / 100))
            for c in rgb
        )
        
        return f"#{new_rgb[0]:02x}{new_rgb[1]:02x}{new_rgb[2]:02x}"
    
    def generate_full_theme(self) -> str:
        """Generate complete CSS theme"""
        variables = self.generate_css_variables()
        
        return f"""
{variables}

/* Base Styles */
* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: 'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background-color: var(--bg-secondary);
    color: var(--text-primary);
    line-height: 1.5;
}}

/* Button Styles */
.btn {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.625rem 1.25rem;
    font-size: 0.875rem;
    font-weight: 500;
    border-radius: var(--radius-md);
    border: none;
    cursor: pointer;
    transition: all var(--transition-fast);
}}

.btn-primary {{
    background-color: var(--primary-color);
    color: var(--text-on-primary);
}}

.btn-primary:hover {{
    background-color: var(--primary-dark);
}}

.btn-secondary {{
    background-color: var(--secondary-color);
    color: var(--text-on-primary);
}}

.btn-outline {{
    background-color: transparent;
    border: 2px solid var(--primary-color);
    color: var(--primary-color);
}}

.btn-outline:hover {{
    background-color: var(--primary-color);
    color: var(--text-on-primary);
}}

/* Card Styles */
.card {{
    background: var(--bg-primary);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-md);
    padding: 1.5rem;
}}

.card-header {{
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 1rem;
    margin-bottom: 1rem;
}}

/* Form Styles */
.form-group {{
    margin-bottom: 1rem;
}}

.form-label {{
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 500;
    color: var(--text-primary);
}}

.form-input {{
    width: 100%;
    padding: 0.625rem 0.875rem;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    font-size: 0.875rem;
    transition: border-color var(--transition-fast);
}}

.form-input:focus {{
    outline: none;
    border-color: var(--border-focus);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}}

/* Status Badges */
.badge {{
    display: inline-flex;
    align-items: center;
    padding: 0.25rem 0.75rem;
    font-size: 0.75rem;
    font-weight: 500;
    border-radius: var(--radius-full);
}}

.badge-success {{
    background-color: #d1fae5;
    color: #065f46;
}}

.badge-warning {{
    background-color: #fef3c7;
    color: #92400e;
}}

.badge-error {{
    background-color: #fee2e2;
    color: #991b1b;
}}

.badge-info {{
    background-color: #dbeafe;
    color: #1e40af;
}}

/* Table Styles */
.table {{
    width: 100%;
    border-collapse: collapse;
}}

.table th,
.table td {{
    padding: 0.75rem 1rem;
    text-align: left;
    border-bottom: 1px solid var(--border-color);
}}

.table th {{
    background-color: var(--bg-secondary);
    font-weight: 600;
    color: var(--text-secondary);
}}

.table tr:hover {{
    background-color: var(--bg-tertiary);
}}

/* Alerts */
.alert {{
    padding: 1rem;
    border-radius: var(--radius-md);
    margin-bottom: 1rem;
}}

.alert-success {{
    background-color: #d1fae5;
    border-left: 4px solid var(--success-color);
    color: #065f46;
}}

.alert-warning {{
    background-color: #fef3c7;
    border-left: 4px solid var(--warning-color);
    color: #92400e;
}}

.alert-error {{
    background-color: #fee2e2;
    border-left: 4px solid var(--error-color);
    color: #991b1b;
}}

.alert-info {{
    background-color: #dbeafe;
    border-left: 4px solid var(--info-color);
    color: #1e40af;
}}
"""


class CaptivePortalGenerator:
    """
    Generate custom captive portal pages for tenants
    """
    
    def __init__(self, tenant: Tenant):
        self.tenant = tenant
        self.theme = ThemeGenerator(tenant)
        self.branding = BrandingManager(tenant)
    
    def generate_login_page(self) -> str:
        """Generate custom login page HTML"""
        brand = self.branding.get_branding()
        css = self.theme.generate_full_theme()
        
        logo_html = ""
        if brand['logo_url']:
            logo_html = f'<img src="{brand["logo_url"]}" alt="{brand["business_name"]}" class="logo-img">'
        else:
            logo_html = f'<h1 class="logo-text">{brand["business_name"]}</h1>'
        
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{brand['business_name']} - WiFi Login</title>
    <style>
{css}

.login-container {{
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
    padding: 1rem;
}}

.login-card {{
    width: 100%;
    max-width: 400px;
    background: white;
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
    padding: 2rem;
}}

.logo-container {{
    text-align: center;
    margin-bottom: 2rem;
}}

.logo-img {{
    max-width: 150px;
    height: auto;
}}

.logo-text {{
    color: var(--primary-color);
    font-size: 1.5rem;
}}

.bundle-grid {{
    display: grid;
    gap: 0.75rem;
    margin: 1.5rem 0;
}}

.bundle-option {{
    border: 2px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 1rem;
    cursor: pointer;
    transition: all var(--transition-fast);
}}

.bundle-option:hover,
.bundle-option.selected {{
    border-color: var(--primary-color);
    background-color: rgba(59, 130, 246, 0.05);
}}

.bundle-option input {{
    display: none;
}}

.bundle-name {{
    font-weight: 600;
    color: var(--text-primary);
}}

.bundle-price {{
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--primary-color);
}}

.bundle-duration {{
    font-size: 0.875rem;
    color: var(--text-secondary);
}}

.divider {{
    text-align: center;
    margin: 1.5rem 0;
    position: relative;
}}

.divider::before {{
    content: '';
    position: absolute;
    top: 50%;
    left: 0;
    right: 0;
    height: 1px;
    background: var(--border-color);
}}

.divider span {{
    background: white;
    padding: 0 1rem;
    position: relative;
    color: var(--text-muted);
    font-size: 0.875rem;
}}

.footer {{
    margin-top: 2rem;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.75rem;
}}
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-card">
            <div class="logo-container">
                {logo_html}
            </div>
            
            <div id="step-phone">
                <h2 style="text-align: center; margin-bottom: 1.5rem;">Connect to WiFi</h2>
                
                <form id="phone-form">
                    <div class="form-group">
                        <label class="form-label" for="phone">Phone Number</label>
                        <input type="tel" id="phone" name="phone" class="form-input" 
                               placeholder="0712 345 678" required>
                    </div>
                    <button type="submit" class="btn btn-primary" style="width: 100%;">
                        Continue
                    </button>
                </form>
            </div>
            
            <div id="step-bundles" style="display: none;">
                <h2 style="text-align: center; margin-bottom: 1rem;">Choose a Package</h2>
                
                <div class="bundle-grid" id="bundles">
                    <!-- Bundles loaded dynamically -->
                </div>
                
                <button id="pay-btn" class="btn btn-primary" style="width: 100%; display: none;">
                    Pay Now
                </button>
                
                <div class="divider">
                    <span>or</span>
                </div>
                
                <div class="form-group">
                    <label class="form-label" for="voucher">Have a voucher?</label>
                    <input type="text" id="voucher" class="form-input" placeholder="XXXX-XXXX-XXXX">
                </div>
                <button id="voucher-btn" class="btn btn-outline" style="width: 100%;">
                    Redeem Voucher
                </button>
            </div>
            
            <div id="message" class="alert" style="display: none;"></div>
            
            <div class="footer">
                Powered by Kitonga WiFi
            </div>
        </div>
    </div>
    
    <script>
    const API = 'https://api.kitonga.klikcell.com/api';
    const TENANT = '{self.tenant.slug}';
    let phone = '', bundle = null;
    
    document.getElementById('phone-form').onsubmit = async (e) => {{
        e.preventDefault();
        phone = document.getElementById('phone').value;
        
        const res = await fetch(`${{API}}/bundles/?tenant=${{TENANT}}`);
        const bundles = await res.json();
        
        document.getElementById('bundles').innerHTML = bundles.map(b => `
            <label class="bundle-option" onclick="selectBundle(${{b.id}}, this)">
                <input type="radio" name="bundle" value="${{b.id}}">
                <div class="bundle-name">${{b.name}}</div>
                <div class="bundle-price">TZS ${{Number(b.price).toLocaleString()}}</div>
                <div class="bundle-duration">${{b.duration_hours}} hours</div>
            </label>
        `).join('');
        
        document.getElementById('step-phone').style.display = 'none';
        document.getElementById('step-bundles').style.display = 'block';
    }};
    
    function selectBundle(id, el) {{
        bundle = id;
        document.querySelectorAll('.bundle-option').forEach(e => e.classList.remove('selected'));
        el.classList.add('selected');
        document.getElementById('pay-btn').style.display = 'block';
    }}
    
    document.getElementById('pay-btn').onclick = async () => {{
        showMessage('Processing...', 'info');
        const res = await fetch(`${{API}}/initiate-payment/`, {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{phone_number: phone, bundle_id: bundle, tenant: TENANT}})
        }});
        const data = await res.json();
        showMessage(data.success ? 'Check your phone!' : (data.message || 'Failed'), data.success ? 'success' : 'error');
    }};
    
    document.getElementById('voucher-btn').onclick = async () => {{
        const code = document.getElementById('voucher').value;
        if (!code) return;
        
        showMessage('Checking voucher...', 'info');
        const res = await fetch(`${{API}}/vouchers/redeem/`, {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{voucher_code: code, phone_number: phone, tenant: TENANT}})
        }});
        const data = await res.json();
        showMessage(data.success ? 'Voucher redeemed!' : (data.message || 'Invalid voucher'), data.success ? 'success' : 'error');
        if (data.success) setTimeout(() => location.reload(), 2000);
    }};
    
    function showMessage(text, type) {{
        const msg = document.getElementById('message');
        msg.textContent = text;
        msg.className = `alert alert-${{type}}`;
        msg.style.display = 'block';
    }}
    </script>
</body>
</html>
"""
    
    def get_all_pages(self) -> Dict[str, str]:
        """Generate all captive portal pages"""
        return {
            'login.html': self.generate_login_page(),
            'status.html': self._generate_status_page(),
            'logout.html': self._generate_logout_page(),
            'error.html': self._generate_error_page(),
        }
    
    def _generate_status_page(self) -> str:
        """Generate status page"""
        brand = self.branding.get_branding()
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{brand['business_name']} - Connected</title>
    {self._get_style_tag()}
</head>
<body>
    <div class="login-container">
        <div class="login-card">
            <div class="logo-container">
                <h1 class="logo-text">{brand['business_name']}</h1>
            </div>
            <div class="alert alert-success">
                <h2>✓ You're Connected!</h2>
                <p>Enjoy your WiFi access.</p>
            </div>
            <a href="$(link-logout)" class="btn btn-outline" style="width: 100%;">Logout</a>
        </div>
    </div>
</body>
</html>
"""
    
    def _generate_logout_page(self) -> str:
        """Generate logout page"""
        brand = self.branding.get_branding()
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{brand['business_name']} - Logged Out</title>
    {self._get_style_tag()}
</head>
<body>
    <div class="login-container">
        <div class="login-card">
            <div class="logo-container">
                <h1 class="logo-text">{brand['business_name']}</h1>
            </div>
            <div class="alert alert-info">
                <h2>Logged Out</h2>
                <p>You have been disconnected.</p>
            </div>
            <a href="$(link-login)" class="btn btn-primary" style="width: 100%;">Connect Again</a>
        </div>
    </div>
</body>
</html>
"""
    
    def _generate_error_page(self) -> str:
        """Generate error page"""
        brand = self.branding.get_branding()
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{brand['business_name']} - Error</title>
    {self._get_style_tag()}
</head>
<body>
    <div class="login-container">
        <div class="login-card">
            <div class="logo-container">
                <h1 class="logo-text">{brand['business_name']}</h1>
            </div>
            <div class="alert alert-error">
                <h2>Error</h2>
                <p>$(error)</p>
            </div>
            <a href="$(link-login)" class="btn btn-primary" style="width: 100%;">Try Again</a>
        </div>
    </div>
</body>
</html>
"""
    
    def _get_style_tag(self) -> str:
        """Get common style tag"""
        css = self.theme.generate_full_theme()
        return f"""
<style>
{css}
.login-container {{
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
    padding: 1rem;
}}
.login-card {{
    width: 100%;
    max-width: 400px;
    background: white;
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
    padding: 2rem;
    text-align: center;
}}
.logo-text {{
    color: var(--primary-color);
}}
</style>
"""
