"""
Email utility functions for Kitonga WiFi Billing
Handles OTP emails, welcome emails, and notifications
"""
import logging
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_otp_email(email, otp_code, purpose='registration', tenant_name=None):
    """
    Send OTP verification email
    
    Args:
        email: Recipient email address
        otp_code: The 6-digit OTP code
        purpose: Purpose of OTP (registration, password_reset, email_change)
        tenant_name: Name of the tenant/business (optional)
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        purpose_messages = {
            'registration': {
                'subject': 'Verify your email - Kitonga WiFi',
                'heading': 'Welcome to Kitonga WiFi!',
                'message': 'Thank you for registering. Please use the following code to verify your email address:'
            },
            'password_reset': {
                'subject': 'Password Reset - Kitonga WiFi',
                'heading': 'Password Reset Request',
                'message': 'You requested a password reset. Use the following code to reset your password:'
            },
            'email_change': {
                'subject': 'Email Verification - Kitonga WiFi',
                'heading': 'Email Change Verification',
                'message': 'Please use the following code to verify your new email address:'
            }
        }
        
        purpose_info = purpose_messages.get(purpose, purpose_messages['registration'])
        
        # HTML email template
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; margin: 0; padding: 0; background-color: #f4f4f5; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .card {{ background: white; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); }}
        .logo {{ text-align: center; margin-bottom: 30px; }}
        .logo h1 {{ color: #2563eb; margin: 0; font-size: 28px; }}
        .heading {{ color: #1f2937; font-size: 24px; margin-bottom: 20px; text-align: center; }}
        .message {{ color: #4b5563; font-size: 16px; line-height: 1.6; margin-bottom: 30px; text-align: center; }}
        .otp-box {{ background: linear-gradient(135deg, #3b82f6, #2563eb); border-radius: 8px; padding: 20px; text-align: center; margin: 30px 0; }}
        .otp-code {{ color: white; font-size: 36px; font-weight: bold; letter-spacing: 8px; margin: 0; }}
        .note {{ color: #6b7280; font-size: 14px; text-align: center; margin-top: 20px; }}
        .footer {{ text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e7eb; }}
        .footer p {{ color: #9ca3af; font-size: 12px; margin: 5px 0; }}
        .tenant-name {{ color: #059669; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="logo">
                <h1>🌐 Kitonga WiFi</h1>
            </div>
            <h2 class="heading">{purpose_info['heading']}</h2>
            <p class="message">{purpose_info['message']}</p>
            {f'<p style="text-align: center; color: #4b5563;">Business: <span class="tenant-name">{tenant_name}</span></p>' if tenant_name else ''}
            <div class="otp-box">
                <p class="otp-code">{otp_code}</p>
            </div>
            <p class="note">This code will expire in <strong>15 minutes</strong>.</p>
            <p class="note">If you didn't request this code, please ignore this email.</p>
        </div>
        <div class="footer">
            <p>© Kitonga WiFi Billing System</p>
            <p>This is an automated message, please do not reply.</p>
        </div>
    </div>
</body>
</html>
"""
        
        # Plain text version
        text_content = f"""
{purpose_info['heading']}

{purpose_info['message']}

Your verification code: {otp_code}

{f'Business: {tenant_name}' if tenant_name else ''}

This code will expire in 15 minutes.

If you didn't request this code, please ignore this email.

---
Kitonga WiFi Billing System
"""
        
        # Send email
        result = send_mail(
            subject=purpose_info['subject'],
            message=text_content,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@kitonga.klikcell.com'),
            recipient_list=[email],
            html_message=html_content,
            fail_silently=False
        )
        
        logger.info(f"OTP email sent to {email} for {purpose}")
        return result > 0
        
    except Exception as e:
        logger.error(f"Failed to send OTP email to {email}: {e}")
        # In development, log the OTP so testing is still possible
        if settings.DEBUG:
            logger.info(f"[DEV] OTP for {email}: {otp_code}")
            print(f"\n{'='*50}")
            print(f"📧 EMAIL WOULD BE SENT (Development Mode)")
            print(f"   To: {email}")
            print(f"   Purpose: {purpose}")
            print(f"   OTP Code: {otp_code}")
            print(f"{'='*50}\n")
            return True  # Return True in dev mode so tests can continue
        return False


def send_welcome_email(email, tenant_name, owner_name=None, api_key=None):
    """
    Send welcome email after successful registration
    
    Args:
        email: Recipient email address
        tenant_name: Business/tenant name
        owner_name: Owner's name (optional)
        api_key: API key for the tenant (optional, for security, only partial)
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; margin: 0; padding: 0; background-color: #f4f4f5; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .card {{ background: white; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); }}
        .logo {{ text-align: center; margin-bottom: 30px; }}
        .logo h1 {{ color: #2563eb; margin: 0; font-size: 28px; }}
        .heading {{ color: #1f2937; font-size: 24px; margin-bottom: 20px; }}
        .message {{ color: #4b5563; font-size: 16px; line-height: 1.8; }}
        .highlight {{ background: #f0f9ff; border-left: 4px solid #3b82f6; padding: 15px 20px; margin: 20px 0; border-radius: 0 8px 8px 0; }}
        .steps {{ background: #f8fafc; border-radius: 8px; padding: 20px; margin: 20px 0; }}
        .step {{ display: flex; align-items: flex-start; margin: 15px 0; }}
        .step-number {{ background: #3b82f6; color: white; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 12px; flex-shrink: 0; font-size: 12px; }}
        .button {{ display: inline-block; background: linear-gradient(135deg, #3b82f6, #2563eb); color: white; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 20px 0; }}
        .footer {{ text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e7eb; }}
        .footer p {{ color: #9ca3af; font-size: 12px; margin: 5px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="logo">
                <h1>🌐 Kitonga WiFi</h1>
            </div>
            <h2 class="heading">Welcome to Kitonga WiFi! 🎉</h2>
            <p class="message">
                {f'Dear {owner_name},' if owner_name else 'Hello!'}
                <br><br>
                Your account for <strong>{tenant_name}</strong> has been successfully created and verified!
            </p>
            
            <div class="highlight">
                <strong>Your account is now active!</strong><br>
                You can start setting up your WiFi hotspot business right away.
            </div>
            
            <div class="steps">
                <h3 style="margin-top: 0; color: #1f2937;">Getting Started:</h3>
                <div class="step">
                    <div class="step-number">1</div>
                    <div><strong>Add a Router</strong> - Connect your MikroTik router to start managing users</div>
                </div>
                <div class="step">
                    <div class="step-number">2</div>
                    <div><strong>Create Packages</strong> - Set up WiFi packages with pricing and data limits</div>
                </div>
                <div class="step">
                    <div class="step-number">3</div>
                    <div><strong>Accept Payments</strong> - Configure M-Pesa or other payment methods</div>
                </div>
                <div class="step">
                    <div class="step-number">4</div>
                    <div><strong>Start Earning</strong> - Your customers can now buy WiFi access!</div>
                </div>
            </div>
            
            <p style="text-align: center;">
                <a href="https://kitonga.klikcell.com/portal" class="button">Go to Dashboard →</a>
            </p>
            
            <p class="message" style="font-size: 14px; color: #6b7280;">
                Need help? Check our documentation or contact support at support@kitonga.klikcell.com
            </p>
        </div>
        <div class="footer">
            <p>© Kitonga WiFi Billing System</p>
            <p>Empowering WiFi businesses across Africa</p>
        </div>
    </div>
</body>
</html>
"""
        
        text_content = f"""
Welcome to Kitonga WiFi!

{'Dear ' + owner_name + ',' if owner_name else 'Hello!'}

Your account for {tenant_name} has been successfully created and verified!

Your account is now active and you can start setting up your WiFi hotspot business.

Getting Started:
1. Add a Router - Connect your MikroTik router to start managing users
2. Create Packages - Set up WiFi packages with pricing and data limits
3. Accept Payments - Configure M-Pesa or other payment methods
4. Start Earning - Your customers can now buy WiFi access!

Need help? Contact support at support@kitonga.klikcell.com

---
Kitonga WiFi Billing System
Empowering WiFi businesses across Africa
"""
        
        result = send_mail(
            subject=f'Welcome to Kitonga WiFi - {tenant_name}',
            message=text_content,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@kitonga.klikcell.com'),
            recipient_list=[email],
            html_message=html_content,
            fail_silently=False
        )
        
        logger.info(f"Welcome email sent to {email}")
        return result > 0
        
    except Exception as e:
        logger.error(f"Failed to send welcome email to {email}: {e}")
        return False


def send_password_reset_confirmation(email, tenant_name=None):
    """
    Send password reset confirmation email
    
    Args:
        email: Recipient email address
        tenant_name: Business/tenant name (optional)
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; margin: 0; padding: 0; background-color: #f4f4f5; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .card {{ background: white; border-radius: 12px; padding: 40px; }}
        .logo {{ text-align: center; margin-bottom: 30px; }}
        .logo h1 {{ color: #2563eb; margin: 0; }}
        .heading {{ color: #1f2937; font-size: 24px; text-align: center; }}
        .message {{ color: #4b5563; font-size: 16px; line-height: 1.6; text-align: center; }}
        .success {{ background: #d1fae5; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0; }}
        .success-icon {{ font-size: 48px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="logo"><h1>🌐 Kitonga WiFi</h1></div>
            <h2 class="heading">Password Reset Successful</h2>
            <div class="success">
                <div class="success-icon">✅</div>
                <p style="color: #065f46; margin: 0; font-weight: 600;">Your password has been successfully reset!</p>
            </div>
            <p class="message">
                You can now log in to your account with your new password.
                {f'<br><br>Business: <strong>{tenant_name}</strong>' if tenant_name else ''}
            </p>
            <p class="message" style="font-size: 14px; color: #6b7280;">
                If you didn't make this change, please contact support immediately.
            </p>
        </div>
    </div>
</body>
</html>
"""
        
        result = send_mail(
            subject='Password Reset Successful - Kitonga WiFi',
            message=f'Your password has been successfully reset. You can now log in with your new password.',
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@kitonga.klikcell.com'),
            recipient_list=[email],
            html_message=html_content,
            fail_silently=False
        )
        
        return result > 0
        
    except Exception as e:
        logger.error(f"Failed to send password reset confirmation to {email}: {e}")
        return False


# Alias for backward compatibility
send_password_reset_success_email = send_password_reset_confirmation
