"""
API views for Kitonga Wi-Fi Billing System
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
from django.core.cache import cache
import uuid
import json
import logging
import ipaddress
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models import Count, Sum
from datetime import timedelta
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User as DjangoUser
from .models import User, Bundle, Payment, Device, PaymentWebhook, Voucher, AccessLog
from .models import (
    SubscriptionPlan,
    Tenant,
    TenantStaff,
    TenantSubscriptionPayment,
    Router,
    Location,
)
from django.views.decorators.http import require_http_methods
from rest_framework.authtoken.models import Token
from .serializers import (
    UserSerializer,
    PaymentSerializer,
    InitiatePaymentSerializer,
    VerifyAccessSerializer,
    VoucherSerializer,
    GenerateVouchersSerializer,
    RedeemVoucherSerializer,
    BundleSerializer,
    DeviceSerializer,
    # SaaS serializers
    SubscriptionPlanSerializer,
    TenantSerializer,
    TenantRegistrationSerializer,
    SubscriptionPaymentSerializer,
    CreateSubscriptionPaymentSerializer,
    RouterSerializer,
    LocationSerializer,
    TenantStaffSerializer,
    UsageSummarySerializer,
    RevenueReportSerializer,
)
from .clickpesa import ClickPesaAPI
from .utils import get_active_users_count, get_revenue_statistics
from .permissions import (
    SimpleAdminTokenPermission,
    TenantAPIKeyPermission,
    TenantOrAdminPermission,
)
from .mikrotik import (
    authenticate_user_with_mikrotik,
    logout_user_from_mikrotik,
    track_device_connection,
    enhance_device_tracking_for_payment,
    enhance_device_tracking_for_voucher,
    grant_user_access,
    revoke_user_access,
    trigger_immediate_hotspot_login,
    force_immediate_internet_access,
    create_hotspot_user_and_login,
)
import ipaddress

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """
    Extract the real client IP address from request headers
    Handles proxy headers like X-Forwarded-For, X-Real-IP, etc.
    """
    # Check for common proxy headers in order of preference
    proxy_headers = [
        "HTTP_X_FORWARDED_FOR",
        "HTTP_X_REAL_IP",
        "HTTP_X_FORWARDED",
        "HTTP_X_CLUSTER_CLIENT_IP",
        "HTTP_FORWARDED_FOR",
        "HTTP_FORWARDED",
        "REMOTE_ADDR",
    ]

    for header in proxy_headers:
        ip = request.META.get(header)
        if ip:
            # X-Forwarded-For can contain multiple IPs separated by commas
            # The first IP is usually the original client IP
            if "," in ip:
                ip = ip.split(",")[0].strip()

            # Basic validation - check if it's a valid IP format
            try:
                ipaddress.ip_address(ip)
                # For captive portals, 192.168.x.x and 10.x.x.x are valid client IPs
                # Only reject 127.0.0.1 (localhost) unless it's our last resort
                if ip != "127.0.0.1":
                    return ip
                elif header == "REMOTE_ADDR":
                    # If this is the last resort, return it even if it's localhost
                    return ip
            except ValueError:
                # Invalid IP format, continue to next header
                continue

    # Final fallback
    return "127.0.0.1"


def get_user_agent(request):
    """
    Extract user agent string for device tracking
    """
    return request.META.get("HTTP_USER_AGENT", "Unknown")


def get_mac_address_from_request(request):
    """
    Extract MAC address from request data with validation
    Enhanced to handle multiple MAC address sources and formats
    """
    mac_address = ""

    # Try different possible sources in order of preference
    sources = []

    # Check POST/PUT data first
    if hasattr(request, "data") and request.data:
        sources.append(request.data)

    # Check form data
    if hasattr(request, "POST") and request.POST:
        sources.append(request.POST)

    # Check query parameters
    if hasattr(request, "GET") and request.GET:
        sources.append(request.GET)

    # Check various MAC address field names
    mac_field_names = ["mac_address", "macAddress", "mac", "device_mac", "client_mac"]

    for source in sources:
        for field_name in mac_field_names:
            mac_candidate = source.get(field_name, "")
            if mac_candidate:
                mac_address = mac_candidate
                break
        if mac_address:
            break

    # Enhanced MAC address validation and normalization
    if mac_address:
        # Remove whitespace and convert to uppercase
        mac_address = mac_address.strip().upper()

        # Remove common separators for processing
        mac_clean = (
            mac_address.replace(":", "")
            .replace("-", "")
            .replace(".", "")
            .replace(" ", "")
        )

        # Check if it's a valid 12-character hex string
        if len(mac_clean) == 12 and all(c in "0123456789ABCDEF" for c in mac_clean):
            # Format as standard MAC address (XX:XX:XX:XX:XX:XX)
            formatted_mac = ":".join([mac_clean[i : i + 2] for i in range(0, 12, 2)])

            # Additional validation - check for broadcast or invalid MACs
            if (
                formatted_mac != "00:00:00:00:00:00"
                and formatted_mac != "FF:FF:FF:FF:FF:FF"
            ):
                logger.info(f"Valid MAC address extracted: {formatted_mac}")
                return formatted_mac
            else:
                logger.warning(f"Invalid MAC address detected: {formatted_mac}")
        else:
            logger.warning(f"Invalid MAC address format: {mac_address}")

    return ""


def get_request_info(request, serializer_data=None):
    """
    Extract comprehensive request information including IP, MAC, and user agent
    Enhanced to prioritize explicitly provided data over auto-detected values
    """
    # Enhanced IP address extraction with priority for explicitly provided data
    ip_address = "127.0.0.1"  # Default fallback

    # First priority: explicitly provided IP from serializer (from API calls)
    if serializer_data and "ip_address" in serializer_data:
        provided_ip = serializer_data.get("ip_address", "").strip()
        if provided_ip:
            try:
                ipaddress.ip_address(provided_ip)
                ip_address = provided_ip
                logger.info(f"IP address from serializer: {ip_address}")
            except ValueError:
                logger.warning(f"Invalid IP address from serializer: {provided_ip}")

    # Second priority: extract from request headers
    if ip_address == "127.0.0.1":
        ip_address = get_client_ip(request)

    # Enhanced MAC address extraction with multiple fallback methods
    mac_address = ""

    # First priority: explicitly provided data from serializer (from API calls)
    if serializer_data and "mac_address" in serializer_data:
        mac_candidate = serializer_data.get("mac_address", "").strip()
        if mac_candidate:
            # Validate and normalize the MAC address
            mac_clean = (
                mac_candidate.upper()
                .replace(":", "")
                .replace("-", "")
                .replace(".", "")
                .replace(" ", "")
            )
            if len(mac_clean) == 12 and all(c in "0123456789ABCDEF" for c in mac_clean):
                mac_address = ":".join([mac_clean[i : i + 2] for i in range(0, 12, 2)])
                logger.info(f"MAC address from serializer: {mac_address}")

    # Second priority: extract from request data
    if not mac_address:
        mac_address = get_mac_address_from_request(request)
        if mac_address:
            logger.info(f"MAC address from request: {mac_address}")

    # Third priority: try to detect from headers (limited success)
    if not mac_address:
        # Some captive portals or network equipment pass MAC in headers
        header_mac_fields = [
            "HTTP_X_MAC_ADDRESS",
            "HTTP_X_DEVICE_MAC",
            "HTTP_CLIENT_MAC",
        ]
        for header in header_mac_fields:
            header_mac = request.META.get(header, "").strip()
            if header_mac:
                mac_clean = (
                    header_mac.upper()
                    .replace(":", "")
                    .replace("-", "")
                    .replace(".", "")
                    .replace(" ", "")
                )
                if len(mac_clean) == 12 and all(
                    c in "0123456789ABCDEF" for c in mac_clean
                ):
                    mac_address = ":".join(
                        [mac_clean[i : i + 2] for i in range(0, 12, 2)]
                    )
                    logger.info(f"MAC address from header {header}: {mac_address}")
                    break

    # Get user agent
    user_agent = get_user_agent(request)

    # Log the extracted information for debugging
    logger.info(
        f'Request info extracted - IP: {ip_address}, MAC: {mac_address or "Not provided"}, User-Agent: {user_agent[:50]}...'
    )

    return {
        "ip_address": ip_address,
        "mac_address": mac_address,
        "user_agent": user_agent,
    }


# Health Check API
@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint for monitoring and load balancers
    """
    try:
        # Check database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        # Check cache if configured
        try:
            cache.set("health_check", "ok", 10)
            cache.get("health_check")
        except Exception:
            pass  # Cache might not be configured

        return Response(
            {
                "status": "healthy",
                "timestamp": timezone.now().isoformat(),
                "version": "1.0.0",
                "service": "kitonga-wifi-billing",
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return Response(
            {
                "status": "unhealthy",
                "timestamp": timezone.now().isoformat(),
                "error": str(e),
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


# Contact Form API
@api_view(["POST"])
@permission_classes([AllowAny])
def contact_submit(request):
    """
    Public contact form submission endpoint

    Request Body:
    {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "+255 XXX XXX XXX",  // Optional
        "subject": "general",  // general, sales, support, partnership, demo, other
        "message": "Your message here..."
    }
    """
    from .serializers import ContactFormSerializer
    from .models import ContactSubmission
    from django.core.mail import send_mail, EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.conf import settings as django_settings

    serializer = ContactFormSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Get client info
    ip_address = get_client_ip(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]

    # Rate limiting - max 5 submissions per email per day
    from datetime import timedelta

    today = timezone.now() - timedelta(hours=24)
    recent_submissions = ContactSubmission.objects.filter(
        email=serializer.validated_data["email"], created_at__gte=today
    ).count()

    if recent_submissions >= 5:
        return Response(
            {
                "success": False,
                "message": "Too many submissions. Please try again later.",
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # Create submission
    submission = ContactSubmission.objects.create(
        name=serializer.validated_data["name"],
        email=serializer.validated_data["email"],
        phone=serializer.validated_data.get("phone", ""),
        subject=serializer.validated_data.get("subject", "general"),
        message=serializer.validated_data["message"],
        ip_address=ip_address,
        user_agent=user_agent,
    )

    logger.info(
        f"Contact form submission from {submission.email}: {submission.get_subject_display()}"
    )

    # Send email notification to admin
    email_sent = False
    try:
        contact_email = getattr(django_settings, "CONTACT_EMAIL", "info@klikcell.com")

        # Build email content
        subject_display = submission.get_subject_display()
        email_subject = (
            f"[Kitonga Contact] New {subject_display} from {submission.name}"
        )

        # Plain text version
        plain_message = f"""
New Contact Form Submission
============================

Name: {submission.name}
Email: {submission.email}
Phone: {submission.phone or 'Not provided'}
Subject: {subject_display}

Message:
{submission.message}

---
Reference: CONTACT-{submission.id}
Submitted: {submission.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC
IP Address: {submission.ip_address or 'Unknown'}

View in admin: https://api.kitonga.klikcell.com/admin/billing/contactsubmission/{submission.id}/change/
        """.strip()

        # HTML version
        html_message = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #3B82F6; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9fafb; padding: 20px; border: 1px solid #e5e7eb; }}
        .field {{ margin-bottom: 15px; }}
        .label {{ font-weight: bold; color: #374151; }}
        .value {{ color: #6b7280; }}
        .message-box {{ background: white; padding: 15px; border-radius: 8px; border: 1px solid #e5e7eb; margin-top: 15px; }}
        .footer {{ padding: 15px; text-align: center; font-size: 12px; color: #9ca3af; }}
        .btn {{ display: inline-block; background: #3B82F6; color: white; padding: 10px 20px; text-decoration: none; border-radius: 6px; }}
        .subject-badge {{ display: inline-block; background: #22c55e; color: white; padding: 4px 12px; border-radius: 4px; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2 style="margin: 0;">📬 New Contact Form Submission</h2>
        </div>
        <div class="content">
            <p><span class="subject-badge">{subject_display}</span></p>
            
            <div class="field">
                <span class="label">Name:</span>
                <span class="value">{submission.name}</span>
            </div>
            
            <div class="field">
                <span class="label">Email:</span>
                <span class="value"><a href="mailto:{submission.email}">{submission.email}</a></span>
            </div>
            
            <div class="field">
                <span class="label">Phone:</span>
                <span class="value">{submission.phone or 'Not provided'}</span>
            </div>
            
            <div class="message-box">
                <strong>Message:</strong>
                <p style="white-space: pre-wrap;">{submission.message}</p>
            </div>
            
            <p style="margin-top: 20px; text-align: center;">
                <a href="https://api.kitonga.klikcell.com/admin/billing/contactsubmission/{submission.id}/change/" class="btn">
                    View in Admin Panel
                </a>
            </p>
        </div>
        <div class="footer">
            <p>Reference: CONTACT-{submission.id}</p>
            <p>Submitted: {submission.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
        </div>
    </div>
</body>
</html>
        """.strip()

        # Send email
        email = EmailMultiAlternatives(
            subject=email_subject,
            body=plain_message,
            from_email=django_settings.DEFAULT_FROM_EMAIL,
            to=[contact_email],
            reply_to=[submission.email],  # Reply goes to the person who submitted
        )
        email.attach_alternative(html_message, "text/html")
        email.send(fail_silently=False)

        email_sent = True
        logger.info(
            f"Contact notification email sent to {contact_email} for submission {submission.id}"
        )

    except Exception as e:
        logger.error(f"Failed to send contact notification email: {e}")
        email_sent = False

    return Response(
        {
            "success": True,
            "message": "Thank you for contacting us! We will get back to you soon.",
            "reference": f"CONTACT-{submission.id}",
        },
        status=status.HTTP_201_CREATED,
    )


# Authentication APIs
@api_view(["POST"])
@permission_classes([AllowAny])
def admin_login(request):
    """
    Admin login API endpoint
    """
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return Response(
            {"success": False, "message": "Username and password are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Authenticate user
    user = authenticate(request, username=username, password=password)

    if user is not None and user.is_staff:
        # Login successful and user is admin
        login(request, user)

        # Create or get auth token
        token, created = Token.objects.get_or_create(user=user)

        return Response(
            {
                "success": True,
                "message": "Login successful",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_staff": user.is_staff,
                    "is_superuser": user.is_superuser,
                    "last_login": (
                        user.last_login.isoformat() if user.last_login else None
                    ),
                    "date_joined": user.date_joined.isoformat(),
                },
                "token": token.key,
                "admin_access_token": settings.SIMPLE_ADMIN_TOKEN,  # For header-based auth
            },
            status=status.HTTP_200_OK,
        )

    elif user is not None and not user.is_staff:
        return Response(
            {"success": False, "message": "Access denied. Admin privileges required."},
            status=status.HTTP_403_FORBIDDEN,
        )

    else:
        return Response(
            {"success": False, "message": "Invalid username or password"},
            status=status.HTTP_401_UNAUTHORIZED,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def admin_logout(request):
    """
    Admin logout API endpoint
    """
    if request.user.is_authenticated:
        # Delete auth token if exists
        try:
            token = Token.objects.get(user=request.user)
            token.delete()
        except Token.DoesNotExist:
            pass

        logout(request)
        return Response(
            {"success": True, "message": "Logout successful"}, status=status.HTTP_200_OK
        )

    return Response(
        {"success": False, "message": "User not logged in"},
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def admin_profile(request):
    """
    Get current admin user profile
    """
    # Check token authentication first
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if auth_header.startswith("Token "):
        token_key = auth_header.split(" ")[1]
        try:
            token = Token.objects.get(key=token_key)
            user = token.user
            if user.is_staff:
                return Response(
                    {
                        "success": True,
                        "user": {
                            "id": user.id,
                            "username": user.username,
                            "email": user.email,
                            "first_name": user.first_name,
                            "last_name": user.last_name,
                            "is_staff": user.is_staff,
                            "is_superuser": user.is_superuser,
                            "last_login": (
                                user.last_login.isoformat() if user.last_login else None
                            ),
                            "date_joined": user.date_joined.isoformat(),
                        },
                        "is_authenticated": True,
                    }
                )
        except Token.DoesNotExist:
            pass

    # Check session authentication
    if request.user.is_authenticated and request.user.is_staff:
        return Response(
            {
                "success": True,
                "user": {
                    "id": request.user.id,
                    "username": request.user.username,
                    "email": request.user.email,
                    "first_name": request.user.first_name,
                    "last_name": request.user.last_name,
                    "is_staff": request.user.is_staff,
                    "is_superuser": request.user.is_superuser,
                    "last_login": (
                        request.user.last_login.isoformat()
                        if request.user.last_login
                        else None
                    ),
                    "date_joined": request.user.date_joined.isoformat(),
                },
                "is_authenticated": True,
            }
        )

    return Response(
        {
            "success": False,
            "message": "Not authenticated or not admin",
            "is_authenticated": False,
        },
        status=status.HTTP_401_UNAUTHORIZED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def admin_change_password(request):
    """
    Change admin password
    """
    if not request.user.is_authenticated or not request.user.is_staff:
        return Response(
            {"success": False, "message": "Authentication required"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    current_password = request.data.get("current_password")
    new_password = request.data.get("new_password")
    confirm_password = request.data.get("confirm_password")

    if not all([current_password, new_password, confirm_password]):
        return Response(
            {"success": False, "message": "All password fields are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if new_password != confirm_password:
        return Response(
            {"success": False, "message": "New passwords do not match"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Verify current password
    if not request.user.check_password(current_password):
        return Response(
            {"success": False, "message": "Current password is incorrect"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Set new password
    request.user.set_password(new_password)
    request.user.save()

    # Update token
    try:
        token = Token.objects.get(user=request.user)
        token.delete()
        new_token = Token.objects.create(user=request.user)
    except Token.DoesNotExist:
        new_token = Token.objects.create(user=request.user)

    return Response(
        {
            "success": True,
            "message": "Password changed successfully",
            "token": new_token.key,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def create_admin_user(request):
    """
    Create a new admin user (Only for superuser or if no admin exists)
    """
    username = request.data.get("username")
    password = request.data.get("password")
    email = request.data.get("email", "")
    first_name = request.data.get("first_name", "")
    last_name = request.data.get("last_name", "")

    if not username or not password:
        return Response(
            {"success": False, "message": "Username and password are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Check if any admin users exist
    admin_count = DjangoUser.objects.filter(is_staff=True).count()

    # Allow creation only if no admins exist or current user is superuser
    if admin_count > 0 and (
        not request.user.is_authenticated or not request.user.is_superuser
    ):
        return Response(
            {"success": False, "message": "Only superusers can create admin accounts"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check if username already exists
    if DjangoUser.objects.filter(username=username).exists():
        return Response(
            {"success": False, "message": "Username already exists"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Create admin user
        user = DjangoUser.objects.create_user(
            username=username,
            password=password,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_staff=True,
            is_superuser=(admin_count == 0),  # First admin becomes superuser
        )

        logger.info(f"Admin user created: {username}")

        return Response(
            {
                "success": True,
                "message": "Admin user created successfully",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_staff": user.is_staff,
                    "is_superuser": user.is_superuser,
                },
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        logger.error(f"Error creating admin user: {str(e)}")
        return Response(
            {"success": False, "message": "Error creating admin user"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# User Management APIs


@api_view(["GET"])
@permission_classes([SimpleAdminTokenPermission])
def list_users(request):
    """
    List all Wi-Fi users from ALL tenants (Admin only)
    Returns: Phone Number, Tenant, Account Status, Access Status, Devices, Total Payments, Paid Until, Joined Date, MAC Addresses
    Filter by tenant using ?tenant=slug
    """
    try:
        users = User.objects.all().order_by("-created_at")

        # Apply filters
        phone_filter = request.GET.get("phone_number")
        is_active_filter = request.GET.get("is_active")
        has_access_filter = request.GET.get("has_access")
        tenant_filter = request.GET.get("tenant")  # Filter by tenant slug

        if phone_filter:
            users = users.filter(phone_number__icontains=phone_filter)

        if tenant_filter:
            users = users.filter(tenant__slug=tenant_filter)

        if is_active_filter is not None and is_active_filter != "":
            is_active = is_active_filter.lower() == "true"
            users = users.filter(is_active=is_active)

        # Filter by access status (has valid paid_until)
        if has_access_filter is not None and has_access_filter != "":
            from django.utils import timezone
            from django.db.models import Q

            now = timezone.now()
            if has_access_filter.lower() == "true":
                users = users.filter(is_active=True, paid_until__gt=now)
            else:
                users = users.filter(
                    Q(is_active=False)
                    | Q(paid_until__isnull=True)
                    | Q(paid_until__lte=now)
                )

        # Pagination
        page_size = int(request.GET.get("page_size", 20))
        page = int(request.GET.get("page", 1))
        start = (page - 1) * page_size
        end = start + page_size

        total_users = users.count()
        users_page = users[start:end]

        # Serialize users with all required data
        users_data = []
        for user in users_page:
            try:
                # Get active devices with MAC addresses
                active_devices = []
                all_mac_addresses = []
                try:
                    devices = user.devices.all()
                    for device in devices:
                        all_mac_addresses.append(device.mac_address)
                        if device.is_active:
                            active_devices.append(
                                {
                                    "id": device.id,
                                    "mac_address": device.mac_address,
                                    "ip_address": device.ip_address,
                                    "device_name": device.device_name
                                    or f"Device-{device.mac_address[-8:]}",
                                    "is_active": device.is_active,
                                    "last_seen": (
                                        device.last_seen.isoformat()
                                        if device.last_seen
                                        else None
                                    ),
                                }
                            )
                except Exception as e:
                    logger.error(f"Error getting devices for user {user.id}: {str(e)}")

                # Calculate time remaining
                time_remaining = None
                if user.paid_until:
                    from django.utils import timezone

                    now = timezone.now()
                    if user.paid_until > now:
                        remaining = user.paid_until - now
                        hours = int(remaining.total_seconds() // 3600)
                        minutes = int((remaining.total_seconds() % 3600) // 60)
                        time_remaining = {"hours": hours, "minutes": minutes}

                user_data = {
                    "id": user.id,
                    "phone_number": user.phone_number,
                    # Tenant info
                    "tenant": user.tenant.slug if user.tenant else "platform",
                    "tenant_name": (
                        user.tenant.business_name if user.tenant else "Platform"
                    ),
                    # Account Status
                    "is_active": user.is_active,
                    "account_status": "Active" if user.is_active else "Inactive",
                    # Access Status
                    "has_active_access": user.has_active_access(),
                    "access_status": (
                        "Has Access" if user.has_active_access() else "No Access"
                    ),
                    # Dates
                    "created_at": user.created_at.isoformat(),
                    "joined_date": user.created_at.strftime("%Y-%m-%d %H:%M"),
                    "paid_until": (
                        user.paid_until.isoformat() if user.paid_until else None
                    ),
                    "paid_until_formatted": (
                        user.paid_until.strftime("%Y-%m-%d %H:%M")
                        if user.paid_until
                        else "Never"
                    ),
                    "time_remaining": time_remaining,
                    # Device info
                    "max_devices": user.max_devices,
                    "device_count": len(active_devices),
                    "total_devices": len(all_mac_addresses),
                    "devices": active_devices,
                    "mac_addresses": all_mac_addresses,  # List of all MAC addresses
                    "primary_mac": (
                        all_mac_addresses[0] if all_mac_addresses else None
                    ),  # First/primary MAC
                    # Payment info
                    "total_payments": user.total_payments,
                }

                # Get completed payment count and total amount
                try:
                    completed_payments = user.payments.filter(status="completed")
                    user_data["completed_payments"] = completed_payments.count()
                    user_data["total_spent"] = sum(
                        float(p.amount) for p in completed_payments
                    )
                except Exception as e:
                    logger.error(
                        f"Error getting payment stats for user {user.id}: {str(e)}"
                    )
                    user_data["completed_payments"] = 0
                    user_data["total_spent"] = 0

                # Get last payment info
                user_data["last_payment"] = None
                try:
                    last_payment = (
                        user.payments.filter(status="completed")
                        .order_by("-completed_at")
                        .first()
                    )
                    if last_payment:
                        user_data["last_payment"] = {
                            "amount": str(last_payment.amount),
                            "bundle_name": (
                                last_payment.bundle.name
                                if last_payment.bundle
                                else None
                            ),
                            "completed_at": (
                                last_payment.completed_at.isoformat()
                                if last_payment.completed_at
                                else None
                            ),
                        }
                except Exception as e:
                    logger.error(
                        f"Error getting last payment for user {user.id}: {str(e)}"
                    )

                # Get voucher usage
                try:
                    vouchers_used = user.vouchers_used.filter(is_used=True).count()
                    user_data["vouchers_used"] = vouchers_used
                except Exception:
                    user_data["vouchers_used"] = 0

                users_data.append(user_data)

            except Exception as e:
                logger.error(f"Error serializing user {user.id}: {str(e)}")
                # Add basic user data without problematic fields
                users_data.append(
                    {
                        "id": user.id,
                        "phone_number": user.phone_number,
                        "is_active": user.is_active,
                        "account_status": "Active" if user.is_active else "Inactive",
                        "has_active_access": False,
                        "access_status": "Unknown",
                        "created_at": user.created_at.isoformat(),
                        "joined_date": user.created_at.strftime("%Y-%m-%d %H:%M"),
                        "error": "Failed to load complete user data",
                    }
                )

        return Response(
            {
                "success": True,
                "users": users_data,
                "pagination": {
                    "total": total_users,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_users + page_size - 1) // page_size,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        return Response(
            {"success": False, "message": f"Error retrieving users: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([SimpleAdminTokenPermission])
def get_user_detail(request, user_id):
    """
    Get detailed information about a specific user (Admin only)
    Returns all user data including devices, payments, vouchers, and access logs
    """
    try:
        user = User.objects.get(id=user_id)

        # Get user's payments
        payments = user.payments.all().order_by("-created_at")
        payments_data = []
        for payment in payments:
            payments_data.append(
                {
                    "id": payment.id,
                    "amount": str(payment.amount),
                    "status": payment.status,
                    "bundle_name": payment.bundle.name if payment.bundle else None,
                    "bundle_hours": (
                        payment.bundle.duration_hours if payment.bundle else None
                    ),
                    "order_reference": payment.order_reference,
                    "payment_reference": payment.payment_reference,
                    "payment_channel": payment.payment_channel,
                    "created_at": payment.created_at.isoformat(),
                    "completed_at": (
                        payment.completed_at.isoformat()
                        if payment.completed_at
                        else None
                    ),
                }
            )

        # Get user's devices
        devices = user.devices.all()
        devices_data = []
        mac_addresses = []
        for device in devices:
            mac_addresses.append(device.mac_address)
            devices_data.append(
                {
                    "id": device.id,
                    "mac_address": device.mac_address,
                    "ip_address": device.ip_address,
                    "device_name": device.device_name
                    or f"Device-{device.mac_address[-8:]}",
                    "is_active": device.is_active,
                    "last_seen": (
                        device.last_seen.isoformat() if device.last_seen else None
                    ),
                    "first_seen": (
                        device.first_seen.isoformat() if device.first_seen else None
                    ),
                }
            )

        # Get vouchers used
        vouchers = user.vouchers_used.all().order_by("-used_at")
        vouchers_data = []
        for voucher in vouchers:
            vouchers_data.append(
                {
                    "id": voucher.id,
                    "code": voucher.code,
                    "duration_hours": voucher.duration_hours,
                    "used_at": voucher.used_at.isoformat() if voucher.used_at else None,
                }
            )

        # Get access logs
        access_logs = AccessLog.objects.filter(user=user).order_by("-timestamp")[:20]
        logs_data = []
        for log in access_logs:
            logs_data.append(
                {
                    "id": log.id,
                    "access_granted": log.access_granted,
                    "denial_reason": log.denial_reason,
                    "ip_address": log.ip_address,
                    "mac_address": log.mac_address,
                    "timestamp": log.timestamp.isoformat(),
                }
            )

        # Calculate time remaining
        time_remaining = None
        if user.paid_until:
            from django.utils import timezone

            now = timezone.now()
            if user.paid_until > now:
                remaining = user.paid_until - now
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                time_remaining = {
                    "hours": hours,
                    "minutes": minutes,
                    "formatted": f"{hours}h {minutes}m",
                }

        user_data = {
            "id": user.id,
            "phone_number": user.phone_number,
            # Tenant info (which tenant's WiFi this customer uses)
            "tenant": user.tenant.slug if user.tenant else "platform",
            "tenant_name": user.tenant.business_name if user.tenant else "Platform",
            # Status
            "is_active": user.is_active,
            "account_status": "Active" if user.is_active else "Inactive",
            "has_active_access": user.has_active_access(),
            "access_status": "Has Access" if user.has_active_access() else "No Access",
            # Dates
            "created_at": user.created_at.isoformat(),
            "joined_date": user.created_at.strftime("%Y-%m-%d %H:%M"),
            "paid_until": user.paid_until.isoformat() if user.paid_until else None,
            "paid_until_formatted": (
                user.paid_until.strftime("%Y-%m-%d %H:%M")
                if user.paid_until
                else "Never"
            ),
            "time_remaining": time_remaining,
            # Devices
            "max_devices": user.max_devices,
            "mac_addresses": mac_addresses,
            "primary_mac": mac_addresses[0] if mac_addresses else None,
            "devices": devices_data,
            # Payments & Vouchers
            "payments": payments_data,
            "vouchers": vouchers_data,
            # Access logs
            "access_logs": logs_data,
            # Statistics
            "statistics": {
                "total_payments": user.total_payments,
                "completed_payments": len(
                    [p for p in payments_data if p["status"] == "completed"]
                ),
                "total_spent": sum(
                    float(p["amount"])
                    for p in payments_data
                    if p["status"] == "completed"
                ),
                "vouchers_used": len(vouchers_data),
                "total_devices": len(devices_data),
                "active_devices": len([d for d in devices_data if d["is_active"]]),
                "total_access_logs": AccessLog.objects.filter(user=user).count(),
                "successful_access": AccessLog.objects.filter(
                    user=user, access_granted=True
                ).count(),
                "denied_access": AccessLog.objects.filter(
                    user=user, access_granted=False
                ).count(),
            },
        }

        return Response({"success": True, "user": user_data})

    except User.DoesNotExist:
        return Response(
            {"success": False, "message": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Error getting user detail: {str(e)}")
        return Response(
            {"success": False, "message": "Error retrieving user details"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PUT"])
@permission_classes([SimpleAdminTokenPermission])
def update_user(request, user_id):
    """
    Update user information (Admin only)
    """
    try:
        user = User.objects.get(id=user_id)

        # Update allowed fields
        if "is_active" in request.data:
            user.is_active = request.data["is_active"]

        if "phone_number" in request.data:
            new_phone = request.data["phone_number"]
            # Check if phone number is already taken
            if User.objects.filter(phone_number=new_phone).exclude(id=user_id).exists():
                return Response(
                    {"success": False, "message": "Phone number already exists"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.phone_number = new_phone

        user.save()

        return Response(
            {
                "success": True,
                "message": "User updated successfully",
                "user": {
                    "id": user.id,
                    "phone_number": user.phone_number,
                    "is_active": user.is_active,
                    "has_active_access": user.has_active_access(),
                },
            }
        )

    except User.DoesNotExist:
        return Response(
            {"success": False, "message": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Error updating user: {str(e)}")
        return Response(
            {"success": False, "message": "Error updating user"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
@permission_classes([SimpleAdminTokenPermission])
def delete_user(request, user_id):
    """
    Delete a user and all associated data (Admin only)
    """
    try:
        user = User.objects.get(id=user_id)

        # Get user info before deletion
        phone_number = user.phone_number

        # Force logout from MikroTik if active
        try:
            if user.has_active_access():
                logout_user_from_mikrotik(phone_number)
        except Exception as e:
            logger.warning(
                f"Could not logout user {phone_number} from MikroTik: {str(e)}"
            )

        # Delete user (this will cascade delete payments, devices, etc.)
        user.delete()

        logger.info(f"User deleted: {phone_number}")

        return Response(
            {"success": True, "message": f"User {phone_number} deleted successfully"}
        )

    except User.DoesNotExist:
        return Response(
            {"success": False, "message": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Error deleting user: {str(e)}")
        return Response(
            {"success": False, "message": "Error deleting user"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([SimpleAdminTokenPermission])
def disconnect_user(request, user_id):
    """
    Forcefully disconnect a user from MikroTik and revoke their access (Admin only)

    For multi-tenant support:
    - Disconnects from the TENANT'S SPECIFIC ROUTER(S), not the global router
    - If user belongs to a tenant, uses the tenant's router configuration
    - Falls back to global router if no tenant or tenant has no routers

    This endpoint:
    1. Removes the user's active hotspot session from MikroTik
    2. Removes any IP binding/bypass entries for their devices
    3. Disables their hotspot user account on MikroTik
    4. Marks their devices as inactive in the database
    5. Deactivates the user's access

    Use this when a user's access has expired but they're still connected,
    or when you need to immediately terminate a user's access.
    """
    try:
        from .mikrotik import disconnect_user_from_mikrotik, get_tenant_mikrotik_api

        user = User.objects.get(id=user_id)
        phone_number = user.phone_number
        tenant = user.tenant

        logger.info(
            f"Admin requested disconnect for user: {phone_number} (tenant: {tenant.slug if tenant else 'platform'})"
        )

        disconnected_devices = 0
        disconnect_errors = []
        routers_used = []

        # Get all devices for this user
        devices = user.devices.all()

        # Get tenant's routers if user belongs to a tenant
        tenant_routers = []
        if tenant:
            tenant_routers = list(Router.objects.filter(tenant=tenant, is_active=True))
            if tenant_routers:
                routers_used = [r.name for r in tenant_routers]
                logger.info(f"Using tenant routers for disconnect: {routers_used}")

        # Disconnect each device from MikroTik
        for device in devices:
            try:
                device_disconnected = False

                if tenant_routers:
                    # Disconnect from each tenant router
                    for router in tenant_routers:
                        try:
                            # Get tenant-specific MikroTik API connection
                            api = get_tenant_mikrotik_api(router)
                            if api:
                                from .mikrotik import disconnect_user_with_api

                                result = disconnect_user_with_api(
                                    api=api,
                                    username=phone_number,
                                    mac_address=device.mac_address,
                                )
                                if result.get("success") or result.get(
                                    "session_removed"
                                ):
                                    device_disconnected = True
                                    logger.info(
                                        f"Disconnected {device.mac_address} from router {router.name}"
                                    )
                        except Exception as router_err:
                            logger.warning(
                                f"Error disconnecting from router {router.name}: {router_err}"
                            )
                            disconnect_errors.append(
                                f"{router.name}: {str(router_err)}"
                            )
                else:
                    # Fall back to global router
                    result = disconnect_user_from_mikrotik(
                        username=phone_number, mac_address=device.mac_address
                    )
                    if result.get("success"):
                        device_disconnected = True

                if device_disconnected:
                    disconnected_devices += 1
                    logger.info(
                        f"Disconnected device {device.mac_address} for {phone_number}"
                    )
                else:
                    disconnect_errors.append(
                        f"{device.mac_address}: Could not disconnect"
                    )

                # Mark device as inactive
                device.is_active = False
                device.save()

            except Exception as device_error:
                disconnect_errors.append(f"{device.mac_address}: {str(device_error)}")
                logger.error(
                    f"Error disconnecting device {device.mac_address}: {device_error}"
                )

        # Also try to disconnect by username only (for any orphaned sessions)
        if tenant_routers:
            for router in tenant_routers:
                try:
                    api = get_tenant_mikrotik_api(router)
                    if api:
                        from .mikrotik import disconnect_user_with_api

                        result = disconnect_user_with_api(
                            api=api, username=phone_number, mac_address=None
                        )
                        if result.get("success"):
                            logger.info(
                                f"Cleanup disconnect for {phone_number} on router {router.name}"
                            )
                except Exception as cleanup_error:
                    logger.debug(
                        f"Cleanup disconnect for {phone_number} on {router.name}: {cleanup_error}"
                    )
        else:
            try:
                result = disconnect_user_from_mikrotik(
                    username=phone_number, mac_address=None
                )
                if result.get("success"):
                    logger.info(
                        f'Cleanup disconnect for {phone_number}: {result.get("message")}'
                    )
            except Exception as cleanup_error:
                logger.debug(f"Cleanup disconnect for {phone_number}: {cleanup_error}")

        # Deactivate user access in database
        user.deactivate_access()

        # Create access log
        AccessLog.objects.create(
            user=user,
            device=None,
            access_granted=False,
            denial_reason=f"Admin forced disconnect",
            ip_address=get_client_ip(request),
            mac_address="",
        )

        message = f"User {phone_number} disconnected. {disconnected_devices} device(s) processed."
        if disconnect_errors:
            message += f" Errors: {len(disconnect_errors)}"

        logger.info(message)

        return Response(
            {
                "success": True,
                "message": message,
                "details": {
                    "phone_number": phone_number,
                    "tenant": tenant.slug if tenant else "platform",
                    "tenant_name": tenant.business_name if tenant else "Platform",
                    "routers_used": routers_used if routers_used else ["global"],
                    "devices_disconnected": disconnected_devices,
                    "total_devices": devices.count(),
                    "errors": disconnect_errors if disconnect_errors else None,
                    "user_deactivated": True,
                },
            }
        )

    except User.DoesNotExist:
        return Response(
            {"success": False, "message": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Error disconnecting user: {str(e)}")
        return Response(
            {"success": False, "message": f"Error disconnecting user: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# Payment Management APIs


@api_view(["GET"])
@permission_classes([SimpleAdminTokenPermission])
def list_payments(request):
    """
    List all payments with filtering options (Admin only)
    Includes both Wi-Fi customer payments AND tenant subscription payments
    Filter by payment_type: 'wifi' for customer payments, 'subscription' for tenant payments, 'all' for both
    """
    try:
        # Get payment type filter (wifi, subscription, or all)
        payment_type = request.GET.get("payment_type", "all")

        # Apply filters
        status_filter = request.GET.get("status")
        phone_filter = request.GET.get("phone_number")
        date_from = request.GET.get("date_from")
        date_to = request.GET.get("date_to")
        bundle_filter = request.GET.get("bundle_id")
        tenant_filter = request.GET.get("tenant")

        # Parse dates once
        parsed_date_from = None
        parsed_date_to = None
        if date_from:
            try:
                from datetime import datetime

                parsed_date_from = datetime.fromisoformat(
                    date_from.replace("Z", "+00:00")
                )
            except ValueError:
                pass
        if date_to:
            try:
                from datetime import datetime

                parsed_date_to = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
            except ValueError:
                pass

        payments_data = []
        wifi_payments_count = 0
        subscription_payments_count = 0
        wifi_total = 0
        subscription_total = 0

        # Get Wi-Fi customer payments
        if payment_type in ["all", "wifi"]:
            wifi_payments = Payment.objects.all().order_by("-created_at")

            if status_filter:
                wifi_payments = wifi_payments.filter(status=status_filter)
            if phone_filter:
                wifi_payments = wifi_payments.filter(
                    phone_number__icontains=phone_filter
                )
            if parsed_date_from:
                wifi_payments = wifi_payments.filter(created_at__gte=parsed_date_from)
            if parsed_date_to:
                wifi_payments = wifi_payments.filter(created_at__lte=parsed_date_to)
            if bundle_filter:
                wifi_payments = wifi_payments.filter(bundle_id=bundle_filter)
            if tenant_filter:
                wifi_payments = wifi_payments.filter(user__tenant__slug=tenant_filter)

            wifi_payments_count = wifi_payments.count()
            wifi_total = (
                wifi_payments.filter(status="completed").aggregate(total=Sum("amount"))[
                    "total"
                ]
                or 0
            )

            for payment in wifi_payments:
                payments_data.append(
                    {
                        "id": payment.id,
                        "payment_type": "wifi",
                        "tenant": (
                            payment.user.tenant.slug
                            if payment.user and payment.user.tenant
                            else "platform"
                        ),
                        "tenant_name": (
                            payment.user.tenant.business_name
                            if payment.user and payment.user.tenant
                            else "Platform"
                        ),
                        "phone_number": payment.phone_number,
                        "amount": str(payment.amount),
                        "currency": "TZS",
                        "status": payment.status,
                        "order_reference": payment.order_reference,
                        "bundle_name": payment.bundle.name if payment.bundle else None,
                        "bundle_id": payment.bundle.id if payment.bundle else None,
                        "created_at": payment.created_at.isoformat(),
                        "completed_at": (
                            payment.completed_at.isoformat()
                            if payment.completed_at
                            else None
                        ),
                        "user_id": payment.user.id if payment.user else None,
                        "payment_reference": payment.payment_reference,
                        "transaction_id": payment.transaction_id,
                        "payment_channel": payment.payment_channel,
                    }
                )

        # Get tenant subscription payments
        if payment_type in ["all", "subscription"]:
            subscription_payments = TenantSubscriptionPayment.objects.all().order_by(
                "-created_at"
            )

            if status_filter:
                subscription_payments = subscription_payments.filter(
                    status=status_filter
                )
            if parsed_date_from:
                subscription_payments = subscription_payments.filter(
                    created_at__gte=parsed_date_from
                )
            if parsed_date_to:
                subscription_payments = subscription_payments.filter(
                    created_at__lte=parsed_date_to
                )
            if tenant_filter:
                subscription_payments = subscription_payments.filter(
                    tenant__slug=tenant_filter
                )

            subscription_payments_count = subscription_payments.count()
            subscription_total = (
                subscription_payments.filter(status="completed").aggregate(
                    total=Sum("amount")
                )["total"]
                or 0
            )

            for payment in subscription_payments:
                payments_data.append(
                    {
                        "id": payment.id,
                        "payment_type": "subscription",
                        "tenant": payment.tenant.slug,
                        "tenant_name": payment.tenant.business_name,
                        "phone_number": payment.tenant.business_phone or "",
                        "amount": str(payment.amount),
                        "currency": payment.currency,
                        "status": payment.status,
                        "order_reference": payment.transaction_id,
                        "plan_name": (
                            payment.plan.display_name if payment.plan else None
                        ),
                        "plan_id": payment.plan.id if payment.plan else None,
                        "billing_cycle": payment.billing_cycle,
                        "period_start": (
                            payment.period_start.isoformat()
                            if payment.period_start
                            else None
                        ),
                        "period_end": (
                            payment.period_end.isoformat()
                            if payment.period_end
                            else None
                        ),
                        "created_at": payment.created_at.isoformat(),
                        "completed_at": (
                            payment.completed_at.isoformat()
                            if payment.completed_at
                            else None
                        ),
                        "payment_reference": payment.payment_reference,
                        "transaction_id": payment.transaction_id,
                        "payment_channel": payment.payment_method,
                    }
                )

        # Sort combined results by created_at descending
        payments_data.sort(key=lambda x: x["created_at"], reverse=True)

        # Pagination
        page_size = int(request.GET.get("page_size", 20))
        page = int(request.GET.get("page", 1))
        start = (page - 1) * page_size
        end = start + page_size

        total_payments = len(payments_data)
        payments_page = payments_data[start:end]

        return Response(
            {
                "success": True,
                "payments": payments_page,
                "pagination": {
                    "total": total_payments,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (
                        (total_payments + page_size - 1) // page_size
                        if total_payments > 0
                        else 0
                    ),
                },
                "summary": {
                    "wifi_payments": {
                        "count": wifi_payments_count,
                        "total_amount": str(wifi_total),
                    },
                    "subscription_payments": {
                        "count": subscription_payments_count,
                        "total_amount": str(subscription_total),
                    },
                    "combined_total": str(wifi_total + subscription_total),
                },
            }
        )

    except Exception as e:
        logger.error(f"Error listing payments: {str(e)}")
        return Response(
            {"success": False, "message": f"Error retrieving payments: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([SimpleAdminTokenPermission])
def get_payment_detail(request, payment_id):
    """
    Get detailed information about a specific payment (Admin only)
    Use query param ?type=subscription for tenant subscription payments
    """
    try:
        payment_type = request.GET.get("type", "wifi")

        if payment_type == "subscription":
            # Get tenant subscription payment
            payment = TenantSubscriptionPayment.objects.get(id=payment_id)

            payment_data = {
                "id": payment.id,
                "payment_type": "subscription",
                "tenant": {
                    "id": str(payment.tenant.id),
                    "slug": payment.tenant.slug,
                    "business_name": payment.tenant.business_name,
                    "email": payment.tenant.business_email,
                    "phone": payment.tenant.business_phone,
                    "is_active": payment.tenant.is_active,
                },
                "plan": (
                    {
                        "id": payment.plan.id,
                        "name": payment.plan.name,
                        "display_name": payment.plan.display_name,
                        "monthly_price": str(payment.plan.monthly_price),
                        "yearly_price": str(payment.plan.yearly_price),
                    }
                    if payment.plan
                    else None
                ),
                "amount": str(payment.amount),
                "currency": payment.currency,
                "billing_cycle": payment.billing_cycle,
                "status": payment.status,
                "payment_method": payment.payment_method,
                "payment_reference": payment.payment_reference,
                "transaction_id": payment.transaction_id,
                "period_start": (
                    payment.period_start.isoformat() if payment.period_start else None
                ),
                "period_end": (
                    payment.period_end.isoformat() if payment.period_end else None
                ),
                "created_at": payment.created_at.isoformat(),
                "completed_at": (
                    payment.completed_at.isoformat() if payment.completed_at else None
                ),
            }

            return Response({"success": True, "payment": payment_data})

        else:
            # Get Wi-Fi customer payment
            payment = Payment.objects.get(id=payment_id)

            # Get webhook logs for this payment
            webhook_logs = PaymentWebhook.objects.filter(
                order_reference=payment.order_reference
            ).order_by("-received_at")

            webhook_data = []
            for webhook in webhook_logs:
                webhook_data.append(
                    {
                        "id": webhook.id,
                        "event_type": webhook.event_type,
                        "payment_status": webhook.payment_status,
                        "amount": str(webhook.amount) if webhook.amount else None,
                        "transaction_id": webhook.transaction_id,
                        "received_at": webhook.received_at.isoformat(),
                        "processed_at": (
                            webhook.processed_at.isoformat()
                            if webhook.processed_at
                            else None
                        ),
                        "processing_status": webhook.processing_status,
                    }
                )

            payment_data = {
                "id": payment.id,
                "payment_type": "wifi",
                "tenant": (
                    payment.user.tenant.slug
                    if payment.user and payment.user.tenant
                    else "platform"
                ),
                "tenant_name": (
                    payment.user.tenant.business_name
                    if payment.user and payment.user.tenant
                    else "Platform"
                ),
                "phone_number": payment.phone_number,
                "amount": str(payment.amount),
                "status": payment.status,
                "order_reference": payment.order_reference,
                "payment_reference": payment.payment_reference,
                "transaction_id": payment.transaction_id,
                "payment_channel": payment.payment_channel,
                "bundle": (
                    {
                        "id": payment.bundle.id,
                        "name": payment.bundle.name,
                        "price": str(payment.bundle.price),
                        "duration_hours": payment.bundle.duration_hours,
                        "description": payment.bundle.description,
                    }
                    if payment.bundle
                    else None
                ),
                "user": (
                    {
                        "id": payment.user.id,
                        "phone_number": payment.user.phone_number,
                        "is_active": payment.user.is_active,
                        "has_active_access": payment.user.has_active_access(),
                        "tenant": (
                            payment.user.tenant.slug
                            if payment.user.tenant
                            else "platform"
                        ),
                    }
                    if payment.user
                    else None
                ),
                "created_at": payment.created_at.isoformat(),
                "completed_at": (
                    payment.completed_at.isoformat() if payment.completed_at else None
                ),
                "webhook_logs": webhook_data,
            }

            return Response({"success": True, "payment": payment_data})

    except Payment.DoesNotExist:
        return Response(
            {"success": False, "message": "Wi-Fi payment not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except TenantSubscriptionPayment.DoesNotExist:
        return Response(
            {"success": False, "message": "Subscription payment not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Error getting payment detail: {str(e)}")
        return Response(
            {
                "success": False,
                "message": f"Error retrieving payment details: {str(e)}",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([SimpleAdminTokenPermission])
def refund_payment(request, payment_id):
    """
    Refund a payment (Admin only) - marks payment as refunded and revokes access
    """
    try:
        payment = Payment.objects.get(id=payment_id)

        if payment.status != "completed":
            return Response(
                {
                    "success": False,
                    "message": "Only completed payments can be refunded",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update payment status
        payment.status = "refunded"
        payment.save()

        # Force logout user if they have active access
        if payment.user and payment.user.has_active_access():
            try:
                logout_user_from_mikrotik(payment.phone_number)
            except Exception as e:
                logger.warning(
                    f"Could not logout user {payment.phone_number} from MikroTik: {str(e)}"
                )

        logger.info(f"Payment refunded: {payment.order_reference}")

        return Response(
            {
                "success": True,
                "message": f"Payment {payment.order_reference} refunded successfully",
            }
        )

    except Payment.DoesNotExist:
        return Response(
            {"success": False, "message": "Payment not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Error refunding payment: {str(e)}")
        return Response(
            {"success": False, "message": "Error processing refund"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# Bundle/Package Management APIs


@api_view(["GET", "POST"])
@permission_classes([SimpleAdminTokenPermission])
def manage_bundles(request):
    """
    List all bundles (GET) or create new bundle (POST) (Admin only)
    Now supports multi-tenancy - returns bundles for all tenants or specific tenant
    """
    if request.method == "GET":
        try:
            # Get tenant filter from query params (optional)
            tenant_slug = request.query_params.get("tenant")

            if tenant_slug:
                # Filter by specific tenant
                try:
                    tenant = Tenant.objects.get(slug=tenant_slug)
                    bundles = Bundle.objects.filter(tenant=tenant).order_by("price")
                except Tenant.DoesNotExist:
                    return Response(
                        {
                            "success": False,
                            "message": f'Tenant "{tenant_slug}" not found',
                        },
                        status=status.HTTP_404_NOT_FOUND,
                    )
            else:
                # Show ALL bundles (platform bundles + all tenant bundles)
                # Admin can see all bundles across the system
                bundles = Bundle.objects.all().order_by("price")

            bundles_data = []
            for bundle in bundles:
                # Get usage statistics
                total_purchases = Payment.objects.filter(
                    bundle=bundle, status="completed"
                ).count()

                revenue = (
                    Payment.objects.filter(bundle=bundle, status="completed").aggregate(
                        total=Sum("amount")
                    )["total"]
                    or 0
                )

                bundles_data.append(
                    {
                        "id": bundle.id,
                        "tenant": bundle.tenant.slug if bundle.tenant else "platform",
                        "name": bundle.name,
                        "description": bundle.description,
                        "price": str(bundle.price),
                        "currency": bundle.currency,
                        "duration_hours": bundle.duration_hours,
                        "is_active": bundle.is_active,
                        "display_order": bundle.display_order,
                        "total_purchases": total_purchases,
                        "revenue": str(revenue),
                    }
                )

            return Response({"success": True, "bundles": bundles_data})

        except Exception as e:
            logger.error(f"Error listing bundles: {str(e)}")
            return Response(
                {"success": False, "message": "Error retrieving bundles"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    elif request.method == "POST":
        try:
            # Get tenant from request data (optional - platform admin may create global bundles)
            tenant_slug = request.data.get("tenant")
            tenant = None

            if tenant_slug:
                try:
                    tenant = Tenant.objects.get(slug=tenant_slug)
                except Tenant.DoesNotExist:
                    return Response(
                        {
                            "success": False,
                            "message": f'Tenant "{tenant_slug}" not found',
                        },
                        status=status.HTTP_404_NOT_FOUND,
                    )

            # Validate required fields
            required_fields = ["name", "price", "duration_hours"]
            missing_fields = [
                field for field in required_fields if not request.data.get(field)
            ]
            if missing_fields:
                return Response(
                    {
                        "success": False,
                        "message": f'Missing required fields: {", ".join(missing_fields)}',
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create new bundle
            bundle = Bundle.objects.create(
                tenant=tenant,
                name=request.data.get("name"),
                description=request.data.get("description", ""),
                price=request.data.get("price"),
                currency=request.data.get("currency", "TZS"),
                duration_hours=request.data.get("duration_hours"),
                display_order=request.data.get("display_order", 0),
                is_active=request.data.get("is_active", True),
            )

            return Response(
                {
                    "success": True,
                    "message": "Bundle created successfully",
                    "bundle": {
                        "id": bundle.id,
                        "tenant": bundle.tenant.slug if bundle.tenant else "platform",
                        "name": bundle.name,
                        "price": str(bundle.price),
                        "currency": bundle.currency,
                        "duration_hours": bundle.duration_hours,
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            logger.error(f"Error creating bundle: {str(e)}")
            return Response(
                {"success": False, "message": "Error creating bundle"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([SimpleAdminTokenPermission])
def manage_bundle(request, bundle_id):
    """
    Get, update, or delete a specific bundle (Admin only)
    Now validates tenant ownership for security
    """
    try:
        # Get tenant filter from query params (optional)
        tenant_slug = request.query_params.get("tenant")

        # Fetch bundle
        try:
            if tenant_slug:
                try:
                    tenant = Tenant.objects.get(slug=tenant_slug)
                    bundle = Bundle.objects.get(id=bundle_id, tenant=tenant)
                except Tenant.DoesNotExist:
                    return Response(
                        {
                            "success": False,
                            "message": f'Tenant "{tenant_slug}" not found',
                        },
                        status=status.HTTP_404_NOT_FOUND,
                    )
            else:
                # Allow access to platform bundles (tenant=None)
                bundle = Bundle.objects.get(id=bundle_id)
        except Bundle.DoesNotExist:
            return Response(
                {"success": False, "message": "Bundle not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.method == "GET":
            # Get usage statistics
            payments = Payment.objects.filter(bundle=bundle)
            total_purchases = payments.filter(status="completed").count()
            revenue = (
                payments.filter(status="completed").aggregate(total=Sum("amount"))[
                    "total"
                ]
                or 0
            )

            recent_purchases = payments.filter(status="completed").order_by(
                "-completed_at"
            )[:10]
            recent_data = []
            for payment in recent_purchases:
                recent_data.append(
                    {
                        "phone_number": payment.phone_number,
                        "amount": str(payment.amount),
                        "completed_at": (
                            payment.completed_at.isoformat()
                            if payment.completed_at
                            else None
                        ),
                    }
                )

            bundle_data = {
                "id": bundle.id,
                "tenant": bundle.tenant.slug if bundle.tenant else "platform",
                "name": bundle.name,
                "description": bundle.description,
                "price": str(bundle.price),
                "currency": bundle.currency,
                "duration_hours": bundle.duration_hours,
                "is_active": bundle.is_active,
                "display_order": bundle.display_order,
                "statistics": {
                    "total_purchases": total_purchases,
                    "total_revenue": str(revenue),
                    "recent_purchases": recent_data,
                },
            }

            return Response({"success": True, "bundle": bundle_data})

        elif request.method == "PUT":
            # Update bundle
            if "name" in request.data:
                bundle.name = request.data["name"]
            if "description" in request.data:
                bundle.description = request.data["description"]
            if "price" in request.data:
                try:
                    bundle.price = float(request.data["price"])
                except (ValueError, TypeError):
                    return Response(
                        {"success": False, "message": "Invalid price format"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            if "currency" in request.data:
                bundle.currency = request.data["currency"]
            if "duration_hours" in request.data:
                try:
                    bundle.duration_hours = int(request.data["duration_hours"])
                except (ValueError, TypeError):
                    return Response(
                        {"success": False, "message": "Invalid duration_hours format"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            if "display_order" in request.data:
                bundle.display_order = request.data["display_order"]
            if "is_active" in request.data:
                bundle.is_active = request.data["is_active"]

            bundle.save()

            return Response(
                {
                    "success": True,
                    "message": "Bundle updated successfully",
                    "bundle": {
                        "id": bundle.id,
                        "name": bundle.name,
                        "price": str(bundle.price),
                        "currency": bundle.currency,
                        "is_active": bundle.is_active,
                    },
                }
            )

        elif request.method == "DELETE":
            # Check if bundle has any payments
            payment_count = Payment.objects.filter(bundle=bundle).count()
            if payment_count > 0:
                return Response(
                    {
                        "success": False,
                        "message": f"Cannot delete bundle with {payment_count} associated payments. Deactivate instead.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            bundle_name = bundle.name
            bundle.delete()

            return Response(
                {
                    "success": True,
                    "message": f'Bundle "{bundle_name}" deleted successfully',
                }
            )

    except Exception as e:
        logger.error(f"Error managing bundle: {str(e)}")
        return Response(
            {"success": False, "message": "Error managing bundle"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# System Settings APIs


@api_view(["GET", "PUT"])
@permission_classes([SimpleAdminTokenPermission])
@csrf_exempt
def system_settings(request):
    """
    Get or update system settings (Admin only)
    GET: Retrieve current system configuration
    PUT: Update system settings (requires server restart for Django settings changes)
    """
    if request.method == "GET":
        try:
            from django.conf import settings as django_settings

            # Get current settings
            settings_data = {
                "mikrotik": {
                    "router_ip": getattr(django_settings, "MIKROTIK_ROUTER_IP", ""),
                    "username": getattr(django_settings, "MIKROTIK_USERNAME", ""),
                    "hotspot_name": getattr(
                        django_settings, "MIKROTIK_HOTSPOT_NAME", ""
                    ),
                    "api_port": getattr(django_settings, "MIKROTIK_API_PORT", 8728),
                    "connection_status": "Unknown",  # Can add actual test here
                },
                "clickpesa": {
                    "api_key_configured": bool(
                        getattr(django_settings, "CLICKPESA_API_KEY", "")
                    ),
                    "webhook_url": getattr(
                        django_settings, "CLICKPESA_WEBHOOK_URL", ""
                    ),
                    "environment": getattr(
                        django_settings, "CLICKPESA_ENVIRONMENT", "sandbox"
                    ),
                },
                "nextsms": {
                    "api_key_configured": bool(
                        getattr(django_settings, "NEXTSMS_API_KEY", "")
                    ),
                    "sender_id": getattr(django_settings, "NEXTSMS_SENDER_ID", ""),
                },
                "system": {
                    "debug_mode": getattr(django_settings, "DEBUG", False),
                    "allowed_hosts": list(
                        getattr(django_settings, "ALLOWED_HOSTS", [])
                    ),
                    "time_zone": getattr(django_settings, "TIME_ZONE", "UTC"),
                    "language_code": getattr(django_settings, "LANGUAGE_CODE", "en-us"),
                },
            }

            return Response(
                {
                    "success": True,
                    "settings": settings_data,
                    "timestamp": timezone.now().isoformat(),
                }
            )

        except Exception as e:
            logger.error(f"Error getting system settings: {str(e)}")
            return Response(
                {"success": False, "message": "Error retrieving system settings"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    elif request.method == "PUT":
        # Note: In production, settings should be stored in database or environment
        # Modifying Django settings directly requires server restart
        logger.warning(f"System settings update requested by admin (requires restart)")

        return Response(
            {
                "success": True,
                "message": "Settings updates noted. Server restart required to apply changes.",
                "note": "For production, store settings in database or environment variables instead",
                "timestamp": timezone.now().isoformat(),
            }
        )


@api_view(["GET"])
@permission_classes([SimpleAdminTokenPermission])
def system_status(request):
    """
    Get overall system health and status (Admin only)
    """
    try:
        from django.db import connection
        from datetime import datetime, timedelta
        import os

        # Database connection test
        db_status = "OK"
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            db_status = "ERROR"

        # MikroTik connection test
        mikrotik_status = "Unknown"
        try:
            # You can add actual MikroTik connection test here
            mikrotik_status = "OK"  # Placeholder
        except Exception:
            mikrotik_status = "ERROR"

        # Get system statistics
        now = timezone.now()
        today = now.date()
        week_ago = now - timedelta(days=7)

        stats = {
            "database_status": db_status,
            "mikrotik_status": mikrotik_status,
            "uptime": "Unknown",  # You can calculate actual uptime
            "memory_usage": "Unknown",  # You can get actual memory usage
            "disk_usage": "Unknown",  # You can get actual disk usage
            "active_users": User.objects.filter(
                is_active=True, paid_until__gt=now
            ).count(),
            "payments_today": Payment.objects.filter(
                created_at__date=today, status="completed"
            ).count(),
            "revenue_today": Payment.objects.filter(
                created_at__date=today, status="completed"
            ).aggregate(total=Sum("amount"))["total"]
            or 0,
            "payments_week": Payment.objects.filter(
                created_at__gte=week_ago, status="completed"
            ).count(),
            "revenue_week": Payment.objects.filter(
                created_at__gte=week_ago, status="completed"
            ).aggregate(total=Sum("amount"))["total"]
            or 0,
            "total_users": User.objects.count(),
            "active_bundles": Bundle.objects.filter(is_active=True).count(),
            "pending_payments": Payment.objects.filter(status="pending").count(),
        }

        return Response(
            {"success": True, "status": stats, "timestamp": now.isoformat()}
        )

    except Exception as e:
        logger.error(f"Error getting system status: {str(e)}")
        return Response(
            {"success": False, "message": f"Error retrieving system status: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([SimpleAdminTokenPermission])
def cleanup_expired_users(request):
    """
    Manually trigger cleanup of expired users (Admin only)

    This endpoint:
    1. Finds all users whose access has expired (paid_until < now)
    2. Disconnects them from MikroTik router (removes active sessions, IP bindings)
    3. Disables their hotspot user account
    4. Deactivates their devices in the database

    Use this when you notice users with expired access are still connected to the network.
    The cron job runs this automatically every 5 minutes, but you can trigger it manually here.
    """
    try:
        from .tasks import disconnect_expired_users

        logger.info("Manual cleanup of expired users triggered by admin")

        result = disconnect_expired_users()

        if result.get("success"):
            message = f"Successfully processed expired users: {result.get('disconnected', 0)} disconnected, {result.get('devices_deactivated', 0)} devices deactivated"
            if result.get("failed", 0) > 0:
                message += f", {result['failed']} failures"

            logger.info(message)

            return Response(
                {
                    "success": True,
                    "message": message,
                    "details": {
                        "users_disconnected": result.get("disconnected", 0),
                        "devices_deactivated": result.get("devices_deactivated", 0),
                        "failed": result.get("failed", 0),
                        "total_checked": result.get("total_checked", 0),
                    },
                    "timestamp": timezone.now().isoformat(),
                }
            )
        else:
            return Response(
                {
                    "success": False,
                    "message": f"Cleanup failed: {result.get('error', 'Unknown error')}",
                    "timestamp": timezone.now().isoformat(),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except Exception as e:
        logger.error(f"Error in cleanup_expired_users: {str(e)}")
        return Response(
            {"success": False, "message": f"Error during cleanup: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET", "POST"])
@permission_classes([SimpleAdminTokenPermission])
@csrf_exempt
def expiry_watcher_status(request):
    """
    Get the status of the real-time expiry watcher or trigger a manual check (Admin only)

    GET: Returns the watcher status and users about to expire
    POST: Triggers an immediate expiry check (manual enforcement)
    """
    try:
        from .expiry_watcher import get_watcher, AccessExpiryWatcher
        from datetime import timedelta

        now = timezone.now()

        if request.method == "POST":
            # Trigger immediate check
            try:
                watcher = AccessExpiryWatcher()
                watcher._check_and_disconnect_expired()

                logger.info(f"Manual expiry check triggered by admin")

                return Response(
                    {
                        "success": True,
                        "message": "Expiry check triggered successfully",
                        "timestamp": now.isoformat(),
                    }
                )
            except Exception as e:
                logger.error(f"Error during manual expiry check: {str(e)}")
                return Response(
                    {
                        "success": False,
                        "message": f"Error triggering expiry check: {str(e)}",
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        # GET - Return status
        watcher = get_watcher()

        # Get users about to expire (within 30 minutes)
        expiring_soon = User.objects.filter(
            is_active=True,
            paid_until__gt=now,
            paid_until__lte=now + timedelta(minutes=30),
        ).values("id", "phone_number", "paid_until")

        # Get recently expired (should be empty if watcher is working)
        recently_expired = User.objects.filter(
            is_active=True, paid_until__lte=now
        ).values("id", "phone_number", "paid_until")

        # Get stats
        total_active = User.objects.filter(is_active=True, paid_until__gt=now).count()

        expiring_list = []
        for user in expiring_soon:
            remaining = user["paid_until"] - now
            expiring_list.append(
                {
                    "id": user["id"],
                    "phone_number": user["phone_number"],
                    "expires_at": user["paid_until"].isoformat(),
                    "remaining_minutes": int(remaining.total_seconds() / 60),
                }
            )

        expired_list = []
        for user in recently_expired:
            expired_at = user["paid_until"]
            time_expired = now - expired_at
            expired_list.append(
                {
                    "id": user["id"],
                    "phone_number": user["phone_number"],
                    "expired_at": expired_at.isoformat(),
                    "minutes_expired": int(time_expired.total_seconds() / 60),
                }
            )

        # Determine health status
        health_status = "healthy"
        if len(expired_list) > 0:
            health_status = "needs_attention"
            if len(expired_list) > 10:
                health_status = "critical"

        return Response(
            {
                "success": True,
                "watcher": {
                    "running": watcher._running if watcher else False,
                    "check_interval_seconds": (
                        watcher._check_interval if watcher else 30
                    ),
                },
                "statistics": {
                    "total_active_users": total_active,
                    "expiring_in_30_min": len(expiring_list),
                    "expired_but_still_active": len(expired_list),
                },
                "expiring_soon": expiring_list,
                "expired_not_disconnected": expired_list,
                "health": health_status,
                "timestamp": now.isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Error getting watcher status: {str(e)}")
        return Response(
            {"success": False, "message": f"Error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# MikroTik Router Configuration and Management APIs


@api_view(["GET"])
@permission_classes([SimpleAdminTokenPermission])
def admin_list_all_routers(request):
    """
    List ALL routers from ALL tenants (Platform Admin only)
    Returns comprehensive router information with tenant details
    """
    try:
        from .mikrotik import get_tenant_mikrotik_api
        
        routers = Router.objects.all().select_related('tenant', 'location').order_by('tenant__slug', 'name')
        
        # Optional filters
        tenant_filter = request.query_params.get('tenant')
        if tenant_filter:
            routers = routers.filter(tenant__slug=tenant_filter)
        
        status_filter = request.query_params.get('status')
        if status_filter:
            routers = routers.filter(status=status_filter)
        
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            routers = routers.filter(is_active=is_active.lower() == 'true')
        
        # Check connectivity if requested
        check_connectivity = request.query_params.get('check_connectivity', 'false').lower() == 'true'
        
        routers_data = []
        for router in routers:
            router_info = {
                'id': router.id,
                'name': router.name,
                'description': router.description,
                'tenant': router.tenant.slug,
                'tenant_name': router.tenant.business_name,
                'tenant_id': str(router.tenant.id),
                'location': router.location.name if router.location else None,
                'host': router.host,
                'port': router.port,
                'username': router.username,
                'use_ssl': router.use_ssl,
                'router_model': router.router_model,
                'router_version': router.router_version,
                'router_identity': router.router_identity,
                'status': router.status,
                'last_seen': router.last_seen.isoformat() if router.last_seen else None,
                'last_error': router.last_error,
                'hotspot_interface': router.hotspot_interface,
                'hotspot_profile': router.hotspot_profile,
                'is_active': router.is_active,
                'created_at': router.created_at.isoformat(),
                'updated_at': router.updated_at.isoformat(),
            }
            
            # Optionally check real-time connectivity
            if check_connectivity and router.is_active:
                try:
                    api = get_tenant_mikrotik_api(router)
                    if api:
                        router_info['connectivity'] = 'online'
                        api.disconnect()
                    else:
                        router_info['connectivity'] = 'offline'
                except Exception as e:
                    router_info['connectivity'] = 'error'
                    router_info['connectivity_error'] = str(e)
            
            routers_data.append(router_info)
        
        # Summary by tenant
        tenant_summary = {}
        for router in routers:
            slug = router.tenant.slug
            if slug not in tenant_summary:
                tenant_summary[slug] = {
                    'tenant_name': router.tenant.business_name,
                    'total': 0,
                    'online': 0,
                    'offline': 0,
                    'active': 0,
                    'inactive': 0
                }
            tenant_summary[slug]['total'] += 1
            if router.status == 'online':
                tenant_summary[slug]['online'] += 1
            else:
                tenant_summary[slug]['offline'] += 1
            if router.is_active:
                tenant_summary[slug]['active'] += 1
            else:
                tenant_summary[slug]['inactive'] += 1
        
        return Response({
            'success': True,
            'routers': routers_data,
            'total_count': len(routers_data),
            'summary': {
                'total_routers': len(routers_data),
                'by_tenant': tenant_summary
            }
        })
    
    except Exception as e:
        logger.error(f"Error listing all routers: {str(e)}")
        return Response(
            {'success': False, 'message': f'Error listing routers: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["GET"])
@permission_classes([SimpleAdminTokenPermission])
def admin_router_detail(request, router_id):
    """
    Get detailed information for a specific router (Platform Admin only)
    """
    try:
        from .mikrotik import get_tenant_mikrotik_api
        
        router = Router.objects.select_related('tenant', 'location').get(id=router_id)
        
        router_data = {
            'id': router.id,
            'name': router.name,
            'description': router.description,
            'tenant': router.tenant.slug,
            'tenant_name': router.tenant.business_name,
            'tenant_id': str(router.tenant.id),
            'location': router.location.name if router.location else None,
            'host': router.host,
            'port': router.port,
            'username': router.username,
            'use_ssl': router.use_ssl,
            'router_model': router.router_model,
            'router_version': router.router_version,
            'router_identity': router.router_identity,
            'status': router.status,
            'last_seen': router.last_seen.isoformat() if router.last_seen else None,
            'last_error': router.last_error,
            'hotspot_interface': router.hotspot_interface,
            'hotspot_profile': router.hotspot_profile,
            'is_active': router.is_active,
            'created_at': router.created_at.isoformat(),
            'updated_at': router.updated_at.isoformat(),
        }
        
        # Try to get real-time router info
        try:
            api = get_tenant_mikrotik_api(router)
            if api:
                # Get system identity
                identity = api.get_resource('/system/identity').get()
                # Get system resources
                resources = api.get_resource('/system/resource').get()
                
                if identity:
                    router_data['live_identity'] = identity[0].get('name', '')
                if resources:
                    res = resources[0]
                    router_data['live_resources'] = {
                        'uptime': res.get('uptime', ''),
                        'cpu_load': res.get('cpu-load', ''),
                        'free_memory': res.get('free-memory', ''),
                        'total_memory': res.get('total-memory', ''),
                        'version': res.get('version', ''),
                        'board_name': res.get('board-name', ''),
                        'architecture': res.get('architecture-name', ''),
                    }
                
                router_data['connectivity'] = 'online'
            else:
                router_data['connectivity'] = 'offline'
        except Exception as e:
            router_data['connectivity'] = 'error'
            router_data['connectivity_error'] = str(e)
        
        return Response({'success': True, 'router': router_data})
    
    except Router.DoesNotExist:
        return Response(
            {'success': False, 'message': 'Router not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error getting router detail: {str(e)}")
        return Response(
            {'success': False, 'message': f'Error getting router: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["GET"])
@permission_classes([SimpleAdminTokenPermission])
def admin_router_active_users(request, router_id):
    """
    Get active users on a specific router (Platform Admin only)
    """
    try:
        from .mikrotik import get_tenant_mikrotik_api
        
        router = Router.objects.select_related('tenant').get(id=router_id)
        
        api = get_tenant_mikrotik_api(router)
        if not api:
            return Response(
                {'success': False, 'message': f'Cannot connect to router {router.name}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        try:
            # Get active hotspot users
            active = api.get_resource('/ip/hotspot/active').get()
            
            users_data = []
            for session in active:
                username = session.get('user', '')
                
                # Find database user
                db_info = None
                try:
                    db_user = User.objects.get(phone_number=username, tenant=router.tenant)
                    db_info = {
                        'user_id': db_user.id,
                        'is_active': db_user.is_active,
                        'has_active_access': db_user.has_active_access(),
                        'access_expires_at': db_user.access_expires_at.isoformat() if db_user.access_expires_at else None,
                    }
                except User.DoesNotExist:
                    pass
                
                users_data.append({
                    'session_id': session.get('.id', ''),
                    'username': username,
                    'mac_address': session.get('mac-address', ''),
                    'ip_address': session.get('address', ''),
                    'uptime': session.get('uptime', ''),
                    'bytes_in': session.get('bytes-in', ''),
                    'bytes_out': session.get('bytes-out', ''),
                    'database_info': db_info
                })
            
            return Response({
                'success': True,
                'router': {
                    'id': router.id,
                    'name': router.name,
                    'tenant': router.tenant.slug,
                    'tenant_name': router.tenant.business_name,
                },
                'active_users': users_data,
                'total_count': len(users_data)
            })
        
        except Exception as e:
            logger.error(f"Error getting active users: {str(e)}")
            raise
    
    except Router.DoesNotExist:
        return Response(
            {'success': False, 'message': 'Router not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error getting active users for router {router_id}: {str(e)}")
        return Response(
            {'success': False, 'message': f'Error getting active users: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["POST"])
@permission_classes([SimpleAdminTokenPermission])
def admin_router_disconnect_user(request, router_id):
    """
    Disconnect a user from a specific router (Platform Admin only)
    """
    try:
        from .mikrotik import get_tenant_mikrotik_api, disconnect_user_with_api
        
        router = Router.objects.select_related('tenant').get(id=router_id)
        
        username = request.data.get('username')
        mac_address = request.data.get('mac_address')
        
        if not username:
            return Response(
                {'success': False, 'message': 'Username is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        api = get_tenant_mikrotik_api(router)
        if not api:
            return Response(
                {'success': False, 'message': f'Cannot connect to router {router.name}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        try:
            result = disconnect_user_with_api(api, username, mac_address)
            
            return Response({
                'success': True,
                'message': f'User {username} disconnected from router {router.name}',
                'router': {
                    'id': router.id,
                    'name': router.name,
                    'tenant': router.tenant.slug,
                },
                'details': result
            })
        
        finally:
            try:
                api.disconnect()
            except:
                pass
    
    except Router.DoesNotExist:
        return Response(
            {'success': False, 'message': 'Router not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error disconnecting user from router {router_id}: {str(e)}")
        return Response(
            {'success': False, 'message': f'Error disconnecting user: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["POST"])
@permission_classes([SimpleAdminTokenPermission])
def admin_router_test_connection(request, router_id):
    """
    Test connection to a specific router (Platform Admin only)
    """
    try:
        from .mikrotik import get_tenant_mikrotik_api
        
        router = Router.objects.select_related('tenant').get(id=router_id)
        
        try:
            api = get_tenant_mikrotik_api(router)
            if api:
                # Get system identity to verify connection
                identity = api.get_resource('/system/identity').get()
                resources = api.get_resource('/system/resource').get()
                
                router_info = {}
                if identity:
                    router_info['identity'] = identity[0].get('name', '')
                if resources:
                    res = resources[0]
                    router_info['version'] = res.get('version', '')
                    router_info['board_name'] = res.get('board-name', '')
                    router_info['uptime'] = res.get('uptime', '')
                
                api.disconnect()
                
                # Update router status
                router.status = 'online'
                router.last_seen = timezone.now()
                router.router_identity = router_info.get('identity', '')
                router.router_version = router_info.get('version', '')
                router.router_model = router_info.get('board_name', '')
                router.last_error = ''
                router.save()
                
                return Response({
                    'success': True,
                    'message': f'Connection to {router.name} successful',
                    'router': {
                        'id': router.id,
                        'name': router.name,
                        'tenant': router.tenant.slug,
                    },
                    'router_info': router_info
                })
            else:
                router.status = 'offline'
                router.last_error = 'Connection failed'
                router.save()
                
                return Response(
                    {'success': False, 'message': f'Cannot connect to router {router.name}'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
        
        except Exception as e:
            router.status = 'error'
            router.last_error = str(e)
            router.save()
            raise
    
    except Router.DoesNotExist:
        return Response(
            {'success': False, 'message': 'Router not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error testing connection to router {router_id}: {str(e)}")
        return Response(
            {'success': False, 'message': f'Connection test failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["GET", "POST"])
@permission_classes([SimpleAdminTokenPermission])
def mikrotik_configuration(request):
    """
    Get or update MikroTik router configuration (Admin only)
    """
    if request.method == "GET":
        try:
            from django.conf import settings as django_settings

            config_data = {
                "router_ip": getattr(django_settings, "MIKROTIK_HOST", ""),
                "username": getattr(django_settings, "MIKROTIK_USER", ""),
                "password_configured": bool(
                    getattr(django_settings, "MIKROTIK_PASSWORD", "")
                ),
                "api_port": getattr(django_settings, "MIKROTIK_PORT", 8728),
                "use_ssl": getattr(django_settings, "MIKROTIK_USE_SSL", False),
                "default_profile": getattr(
                    django_settings, "MIKROTIK_DEFAULT_PROFILE", "default"
                ),
            }

            return Response({"success": True, "configuration": config_data})

        except Exception as e:
            logger.error(f"Error getting MikroTik configuration: {str(e)}")
            return Response(
                {
                    "success": False,
                    "message": "Error retrieving MikroTik configuration",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    elif request.method == "POST":
        try:
            # In a real implementation, you'd save these to a database table or update environment variables
            # For now, we'll just validate and return success

            required_fields = ["router_ip", "username", "password", "hotspot_name"]
            for field in required_fields:
                if not request.data.get(field):
                    return Response(
                        {"success": False, "message": f"{field} is required"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Validate IP address format
            try:
                ipaddress.ip_address(request.data["router_ip"])
            except ValueError:
                return Response(
                    {"success": False, "message": "Invalid IP address format"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Test connection with new configuration
            try:
                from .mikrotik import test_mikrotik_connection as test_mt_connection

                test_result = test_mt_connection(
                    host=request.data["router_ip"],
                    username=request.data["username"],
                    password=request.data["password"],
                    port=request.data.get("api_port", 8728),
                )

                if not test_result["success"]:
                    return Response(
                        {
                            "success": False,
                            "message": f'Connection test failed: {test_result.get("error", "Unknown error")}',
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            except ImportError:
                logger.warning("MikroTik connection test not available")

            return Response(
                {
                    "success": True,
                    "message": "MikroTik configuration updated successfully",
                    "note": "Server restart may be required for changes to take effect",
                }
            )

        except Exception as e:
            logger.error(f"Error updating MikroTik configuration: {str(e)}")
            return Response(
                {"success": False, "message": "Error updating MikroTik configuration"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@api_view(["POST"])
@permission_classes([SimpleAdminTokenPermission])
def test_mikrotik_connection(request):
    """
    Test MikroTik router connection (Admin only)
    """
    try:
        from .mikrotik import test_mikrotik_connection as test_connection

        # Use provided credentials or default from settings (using correct setting names)
        router_ip = request.data.get("router_ip") or getattr(
            settings, "MIKROTIK_HOST", ""
        )
        username = request.data.get("username") or getattr(
            settings, "MIKROTIK_USER", ""
        )
        password = request.data.get("password") or getattr(
            settings, "MIKROTIK_PASSWORD", ""
        )
        api_port = request.data.get("api_port") or getattr(
            settings, "MIKROTIK_PORT", 8728
        )

        if not all([router_ip, username, password]):
            return Response(
                {
                    "success": False,
                    "message": "Router IP, username, and password are required",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Test connection
        result = test_connection(
            host=router_ip, username=username, password=password, port=api_port
        )

        return Response(
            {
                "success": result["success"],
                "message": result.get("message", "Connection test completed"),
                "router_info": result.get("router_info", {}),
                "error": result.get("error") if not result["success"] else None,
            }
        )

    except ImportError:
        return Response(
            {"success": False, "message": "MikroTik library not available"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as e:
        logger.error(f"Error testing MikroTik connection: {str(e)}")
        return Response(
            {"success": False, "message": f"Connection test error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([SimpleAdminTokenPermission])
def mikrotik_router_info(request):
    """
    Get detailed MikroTik router information (Admin only)
    """
    try:
        from .mikrotik import get_router_info

        result = get_router_info()

        if result["success"]:
            return Response({"success": True, "router_info": result["data"]})
        else:
            return Response(
                {
                    "success": False,
                    "message": result.get("error", "Failed to get router information"),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except ImportError:
        return Response(
            {"success": False, "message": "MikroTik library not available"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as e:
        logger.error(f"Error getting router info: {str(e)}")
        return Response(
            {
                "success": False,
                "message": f"Error retrieving router information: {str(e)}",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([SimpleAdminTokenPermission])
def mikrotik_active_users(request):
    """
    Get list of currently active users on MikroTik hotspot (Admin only)
    """
    try:
        from .mikrotik import get_active_hotspot_users

        result = get_active_hotspot_users()

        if result["success"]:
            # Enhance user data with database information
            active_users = result["data"]
            enhanced_users = []

            for mikrotik_user in active_users:
                username = mikrotik_user.get("user", "")

                # Find corresponding user in database
                try:
                    db_user = User.objects.get(phone_number=username)
                    user_data = {
                        **mikrotik_user,
                        "database_info": {
                            "user_id": db_user.id,
                            "is_active": db_user.is_active,
                            "has_active_access": db_user.has_active_access(),
                            "device_count": db_user.devices.count(),
                        },
                    }
                except User.DoesNotExist:
                    user_data = {**mikrotik_user, "database_info": None}

                enhanced_users.append(user_data)

            return Response(
                {
                    "success": True,
                    "active_users": enhanced_users,
                    "total_count": len(enhanced_users),
                }
            )
        else:
            return Response(
                {
                    "success": False,
                    "message": result.get("error", "Failed to get active users"),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except ImportError:
        return Response(
            {"success": False, "message": "MikroTik library not available"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as e:
        logger.error(f"Error getting active users: {str(e)}")
        return Response(
            {"success": False, "message": f"Error retrieving active users: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([SimpleAdminTokenPermission])
def mikrotik_disconnect_user(request):
    """
    Disconnect a specific user from MikroTik hotspot (Admin only)
    """
    try:
        username = request.data.get("username")
        mac_address = request.data.get(
            "mac_address"
        )  # Optional MAC for targeted disconnect

        if not username:
            return Response(
                {"success": False, "message": "Username is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use the comprehensive disconnect function that kicks active sessions
        from .mikrotik import disconnect_user_from_mikrotik

        result = disconnect_user_from_mikrotik(
            username=username, mac_address=mac_address
        )

        if result.get("success") or result.get("session_removed"):
            # Log the disconnection with proper IP extraction
            try:
                request_info = get_request_info(request)
                user = User.objects.get(phone_number=username)
                AccessLog.objects.create(
                    user=user,
                    ip_address=request_info["ip_address"],
                    mac_address=mac_address or "",
                    access_granted=False,
                    denial_reason=f'Disconnected by admin user: {request.user.username if request.user.is_authenticated else "Unknown"}',
                )
            except User.DoesNotExist:
                pass  # Log anyway without user reference

            return Response(
                {
                    "success": True,
                    "message": f"User {username} disconnected successfully",
                    "details": {
                        "session_removed": result.get("session_removed", False),
                        "binding_removed": result.get("binding_removed", False),
                        "user_disabled": result.get("user_disabled", False),
                    },
                }
            )
        else:
            return Response(
                {
                    "success": False,
                    "message": f"Failed to disconnect user {username}",
                    "errors": result.get("errors", []),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except ImportError:
        return Response(
            {"success": False, "message": "MikroTik library not available"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as e:
        logger.error(f"Error disconnecting user: {str(e)}")
        return Response(
            {"success": False, "message": f"Error disconnecting user: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([SimpleAdminTokenPermission])
def mikrotik_disconnect_all_users(request):
    """
    Disconnect all users from MikroTik hotspot (Admin only)
    """
    try:
        from .mikrotik import disconnect_all_hotspot_users

        result = disconnect_all_hotspot_users()

        if result["success"]:
            # Log the mass disconnection with proper IP extraction
            try:
                request_info = get_request_info(request)
                # Try to create admin log without user reference
                from django.contrib.auth.models import User as AuthUser

                admin_user = request.user if request.user.is_authenticated else None
                AccessLog.objects.create(
                    user=admin_user if isinstance(admin_user, User) else None,
                    ip_address=request_info["ip_address"],
                    mac_address="ADMIN_ACTION",
                    access_granted=False,
                    denial_reason=f'All users disconnected by admin: {request.user.username if request.user.is_authenticated else "Unknown"}',
                )
            except Exception:
                pass  # Don't fail if logging fails

            return Response(
                {
                    "success": True,
                    "message": f'Successfully disconnected {result.get("count", 0)} users',
                    "disconnected_count": result.get("count", 0),
                }
            )
        else:
            return Response(
                {
                    "success": False,
                    "message": result.get("error", "Failed to disconnect all users"),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except ImportError:
        return Response(
            {"success": False, "message": "MikroTik library not available"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as e:
        logger.error(f"Error disconnecting all users: {str(e)}")
        return Response(
            {"success": False, "message": f"Error disconnecting all users: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([SimpleAdminTokenPermission])
def mikrotik_reboot_router(request):
    """
    Reboot MikroTik router (Admin only) - USE WITH CAUTION
    """
    try:
        # Require confirmation
        confirmation = request.data.get("confirm")
        if confirmation != "REBOOT_ROUTER":
            return Response(
                {
                    "success": False,
                    "message": 'Confirmation required. Send {"confirm": "REBOOT_ROUTER"} to proceed.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .mikrotik import reboot_router

        result = reboot_router()

        if result["success"]:
            # Log the reboot with proper IP extraction
            try:
                request_info = get_request_info(request)
                from django.contrib.auth.models import User as AuthUser

                admin_user = request.user if request.user.is_authenticated else None
                AccessLog.objects.create(
                    user=admin_user if isinstance(admin_user, User) else None,
                    ip_address=request_info["ip_address"],
                    mac_address="ADMIN_ACTION",
                    access_granted=False,
                    denial_reason=f'Router reboot initiated by admin: {request.user.username if request.user.is_authenticated else "Unknown"}',
                )
            except Exception:
                pass  # Don't fail if logging fails

            return Response(
                {
                    "success": True,
                    "message": "Router reboot initiated. The router will be offline for 1-2 minutes.",
                    "warning": "All users will be disconnected during reboot",
                }
            )
        else:
            return Response(
                {
                    "success": False,
                    "message": result.get("error", "Failed to reboot router"),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except ImportError:
        return Response(
            {"success": False, "message": "MikroTik library not available"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as e:
        logger.error(f"Error rebooting router: {str(e)}")
        return Response(
            {"success": False, "message": f"Error rebooting router: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET", "POST"])
@permission_classes([SimpleAdminTokenPermission])
def mikrotik_hotspot_profiles(request):
    """
    Get MikroTik hotspot user profiles (Admin only)
    """
    try:
        from .mikrotik import get_hotspot_profiles

        result = get_hotspot_profiles()

        if result["success"]:
            return Response({"success": True, "profiles": result["data"]})
        else:
            return Response(
                {
                    "success": False,
                    "message": result.get("error", "Failed to get hotspot profiles"),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except ImportError:
        return Response(
            {"success": False, "message": "MikroTik library not available"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as e:
        logger.error(f"Error getting hotspot profiles: {str(e)}")
        return Response(
            {
                "success": False,
                "message": f"Error retrieving hotspot profiles: {str(e)}",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([SimpleAdminTokenPermission])
def mikrotik_create_hotspot_profile(request):
    """
    Create a new MikroTik hotspot user profile (Admin only)
    """
    try:
        profile_name = request.data.get("name")
        rate_limit = request.data.get("rate_limit", "512k/512k")
        session_timeout = request.data.get("session_timeout", "1d")
        idle_timeout = request.data.get("idle_timeout", "5m")

        if not profile_name:
            return Response(
                {"success": False, "message": "Profile name is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .mikrotik import create_hotspot_profile

        result = create_hotspot_profile(
            name=profile_name,
            rate_limit=rate_limit,
            session_timeout=session_timeout,
            idle_timeout=idle_timeout,
        )

        if result["success"]:
            return Response(
                {
                    "success": True,
                    "message": f'Hotspot profile "{profile_name}" created successfully',
                    "profile": result.get("data", {}),
                }
            )
        else:
            return Response(
                {
                    "success": False,
                    "message": result.get("error", "Failed to create hotspot profile"),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except ImportError:
        return Response(
            {"success": False, "message": "MikroTik library not available"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as e:
        logger.error(f"Error creating hotspot profile: {str(e)}")
        return Response(
            {"success": False, "message": f"Error creating hotspot profile: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([SimpleAdminTokenPermission])
def mikrotik_system_resources(request):
    """
    Get MikroTik router system resources and performance metrics (Admin only)
    """
    try:
        from .mikrotik import get_router_info

        result = get_router_info()

        if result["success"]:
            return Response({"success": True, "system_resources": result["data"]})
        else:
            return Response(
                {
                    "success": False,
                    "message": result.get("error", "Failed to get system resources"),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except ImportError:
        return Response(
            {"success": False, "message": "MikroTik library not available"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as e:
        logger.error(f"Error getting system resources: {str(e)}")
        return Response(
            {
                "success": False,
                "message": f"Error retrieving system resources: {str(e)}",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# Wi-Fi Access APIs


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_access(request):
    """
    Verify if a user has valid access
    Called by captive portal to check access status
    Works for both payment and voucher users through unified access checking
    """
    serializer = VerifyAccessSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    phone_number = serializer.validated_data["phone_number"]

    # Use improved IP and MAC extraction
    request_info = get_request_info(request, serializer.validated_data)
    ip_address = request_info["ip_address"]
    mac_address = request_info["mac_address"]
    user_agent = request_info["user_agent"]

    try:
        # Find user with normalized phone number
        from .utils import find_user_by_phone

        user = find_user_by_phone(phone_number)

        # Log the access attempt with real user info for debugging
        logger.info(
            f"Access verification request: phone={phone_number}, ip={ip_address}, mac={mac_address}, user_agent={user_agent[:50]}..."
        )

        if not user:
            logger.warning(
                f"User not found during access verification: phone={phone_number}, ip={ip_address}, mac={mac_address}"
            )
            return Response(
                {
                    "access_granted": False,
                    "message": "User not found. Please register and pay to access Wi-Fi.",
                    "suggestion": "Make a payment or redeem a voucher to create account and get access",
                    "normalized_phone": phone_number,  # Show what the system tried to find
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Core access check - works for both payment and voucher users
        has_access = user.has_active_access()
        denial_reason = ""
        device = None
        access_method = "unknown"

        # Determine how user got access (for better logging and debugging)
        if user.paid_until:
            # Check if user has payment history
            has_payments = user.payments.filter(status="completed").exists()
            # Check if user has voucher history
            has_vouchers = user.vouchers_used.filter(is_used=True).exists()

            if has_payments and has_vouchers:
                access_method = "payment_and_voucher"
            elif has_payments:
                access_method = "payment"
            elif has_vouchers:
                access_method = "voucher"
            else:
                access_method = "manual"  # Manually extended by admin

        if not has_access:
            # Provide more specific denial reasons
            if not user.is_active:
                denial_reason = "User account is deactivated"
            elif not user.paid_until:
                denial_reason = "No payment or voucher redemption found"
            else:
                from django.utils import timezone

                now = timezone.now()
                if user.paid_until <= now:
                    expired_hours = int((now - user.paid_until).total_seconds() / 3600)
                    denial_reason = f"Access expired {expired_hours} hours ago - payment or voucher required"
                else:
                    denial_reason = "Access verification failed"

            logger.info(
                f"Access denied for {phone_number}: {denial_reason} (method: {access_method}, paid_until: {user.paid_until})"
            )

        elif mac_address:
            # User has access, now check device management
            try:
                # Enhanced device tracking for access verification
                device_tracking_result = track_device_connection(
                    phone_number=phone_number,
                    mac_address=mac_address,
                    ip_address=ip_address,
                    connection_type="wifi",
                    access_method=access_method,
                )

                if device_tracking_result["success"]:
                    try:
                        device = user.devices.get(mac_address=mac_address)
                        # Update device as active
                        if not device.is_active:
                            device.is_active = True
                            device.save()
                        logger.info(
                            f"Device tracking successful for {phone_number}: {mac_address} (method: {access_method})"
                        )
                    except Device.DoesNotExist:
                        logger.warning(
                            f"Device tracking reported success but device not found for {phone_number}: {mac_address}"
                        )
                        # Try to get or create device manually
                        device, created = Device.objects.get_or_create(
                            user=user,
                            mac_address=mac_address,
                            defaults={
                                "ip_address": ip_address,
                                "is_active": True,
                                "device_name": f"Device-{mac_address[-8:]}",
                            },
                        )
                        if not created:
                            device.ip_address = ip_address
                            device.is_active = True
                            device.last_seen = timezone.now()
                            device.save()
                else:
                    # Check if device limit was exceeded
                    if device_tracking_result.get("device_limit_exceeded"):
                        has_access = False
                        denial_reason = device_tracking_result["message"]
                        logger.warning(
                            f'Device limit exceeded for {phone_number}: {device_tracking_result.get("active_devices", 0)}/{device_tracking_result.get("max_devices", user.max_devices)} (method: {access_method})'
                        )
                    else:
                        logger.warning(
                            f'Device tracking failed for {phone_number}: {device_tracking_result["message"]} (method: {access_method})'
                        )

            except Exception as tracking_error:
                logger.error(
                    f"Device tracking error for {phone_number}: {str(tracking_error)} (method: {access_method})"
                )
                # Fallback to original device tracking method
                try:
                    device, created = Device.objects.get_or_create(
                        user=user,
                        mac_address=mac_address,
                        defaults={
                            "ip_address": ip_address,
                            "is_active": True,
                            "device_name": f"Device-{mac_address[-8:]}",
                        },
                    )

                    if not created:
                        # Update existing device
                        device.ip_address = ip_address
                        device.is_active = True
                        device.last_seen = timezone.now()
                        device.save()
                        logger.info(
                            f"Updated existing device for {phone_number}: {mac_address} (method: {access_method})"
                        )
                    else:
                        # New device - check if limit reached
                        active_devices = user.devices.filter(is_active=True).count()
                        if active_devices > user.max_devices:
                            has_access = False
                            denial_reason = (
                                f"Device limit reached ({user.max_devices} devices max)"
                            )
                            device.is_active = False
                            device.save()
                            logger.warning(
                                f"Device limit exceeded for {phone_number}: {active_devices}/{user.max_devices} (method: {access_method})"
                            )
                        else:
                            logger.info(
                                f"New device registered for {phone_number}: {mac_address} ({active_devices}/{user.max_devices}, method: {access_method})"
                            )
                except Exception as fallback_error:
                    logger.error(
                        f"Fallback device tracking also failed for {phone_number}: {str(fallback_error)}"
                    )
                    device = None

        # ============================================
        # AUTOMATIC MIKROTIK CONNECTION/DISCONNECTION
        # ============================================
        mikrotik_action = "none"
        mikrotik_success = False
        mikrotik_message = ""
        auto_login_result = {}  # Initialize for auto-login details

        if has_access and mac_address:
            # User has valid access - CONNECT to MikroTik
            try:
                logger.info(
                    f"✓ User {phone_number} has valid access - connecting to MikroTik (MAC: {mac_address}, IP: {ip_address})"
                )

                # Use force_immediate_internet_access for comprehensive auto-login
                # This creates hotspot user + IP binding bypass for immediate access
                auto_login_result = force_immediate_internet_access(
                    username=phone_number,
                    mac_address=mac_address,
                    ip_address=ip_address,
                    access_type=access_method,
                )

                if auto_login_result.get("success"):
                    mikrotik_action = "connected"
                    mikrotik_success = True
                    mikrotik_message = "Successfully connected to internet"
                    logger.info(
                        f'✓ Automatically connected {phone_number} to internet via MikroTik (method: {auto_login_result.get("method_used")})'
                    )
                else:
                    mikrotik_action = "connect_failed"
                    mikrotik_success = False
                    mikrotik_message = f'Connection failed: {auto_login_result.get("message", "Unknown error")}'
                    logger.error(
                        f"✗ Failed to connect {phone_number} to MikroTik: {mikrotik_message}"
                    )

            except Exception as e:
                mikrotik_action = "connect_error"
                mikrotik_success = False
                mikrotik_message = f"Connection error: {str(e)}"
                logger.error(f"✗ Error connecting {phone_number} to MikroTik: {str(e)}")

        elif not has_access and mac_address:
            # User does NOT have access - DISCONNECT from MikroTik
            try:
                logger.info(
                    f"✗ User {phone_number} has no valid access - disconnecting from MikroTik (Reason: {denial_reason})"
                )

                # Revoke access on MikroTik router
                revoke_result = revoke_user_access(
                    mac_address=mac_address, username=phone_number
                )

                if revoke_result.get("success"):
                    mikrotik_action = "disconnected"
                    mikrotik_success = True
                    mikrotik_message = "Disconnected from internet (no valid access)"
                    logger.info(
                        f"✓ Automatically disconnected {phone_number} from MikroTik"
                    )
                else:
                    mikrotik_action = "disconnect_failed"
                    mikrotik_success = False
                    mikrotik_message = f'Disconnection failed: {", ".join(revoke_result.get("errors", ["Unknown error"]))}'
                    logger.warning(
                        f"⚠ Failed to disconnect {phone_number} from MikroTik: {mikrotik_message}"
                    )

            except Exception as e:
                mikrotik_action = "disconnect_error"
                mikrotik_success = False
                mikrotik_message = f"Disconnection error: {str(e)}"
                logger.error(
                    f"✗ Error disconnecting {phone_number} from MikroTik: {str(e)}"
                )

        # Log access attempt with enhanced information
        logger.info(
            f'Creating AccessLog: user={user.phone_number}, ip={ip_address}, mac={mac_address}, access_granted={has_access}, device={device.device_name if device else "None"}'
        )

        AccessLog.objects.create(
            user=user,
            device=device,
            ip_address=ip_address,  # Now guaranteed to have a valid IP
            mac_address=mac_address or "",  # Ensure we log empty string instead of None
            access_granted=has_access,
            denial_reason=denial_reason,
        )

        # Update user status if expired (deactivate if no valid access)
        if (
            not has_access
            and user.is_active
            and not denial_reason.startswith("Device limit")
        ):
            user.deactivate_access()
            logger.info(
                f"User {phone_number} deactivated due to expired access (method was: {access_method})"
            )

        # Enhanced response with access method and MikroTik connection status
        response_data = {
            "access_granted": has_access,
            "denial_reason": denial_reason,
            "user": UserSerializer(user).data,
            "access_method": access_method,
            "device": (
                {
                    "mac_address": mac_address,
                    "registered": device is not None,
                    "is_active": device.is_active if device else False,
                    "device_name": device.device_name if device else None,
                }
                if mac_address
                else None
            ),
            "mikrotik_connection": {
                "action": mikrotik_action,
                "success": mikrotik_success,
                "message": mikrotik_message,
            },
            # Include auto-login details when access is granted
            "mikrotik_auto_login": (
                {
                    "success": auto_login_result.get("success", False),
                    "message": auto_login_result.get("message", ""),
                    "device_mac": mac_address,
                    "device_ip": ip_address,
                    "hotspot_user_created": auto_login_result.get(
                        "hotspot_user_created", False
                    ),
                    "ip_binding_created": auto_login_result.get(
                        "ip_binding_created", False
                    ),
                    "method_used": auto_login_result.get("method_used"),
                    "immediate_access": auto_login_result.get("success", False),
                    # Include device capture from MikroTik
                    "device_capture": auto_login_result.get("device_capture", {}),
                }
                if has_access and mac_address
                else None
            ),
            "debug_info": {
                "has_payments": user.payments.filter(status="completed").exists(),
                "has_vouchers": user.vouchers_used.filter(is_used=True).exists(),
                "paid_until": user.paid_until.isoformat() if user.paid_until else None,
                "is_active": user.is_active,
                "device_count": user.devices.filter(is_active=True).count(),
                "max_devices": user.max_devices,
                "client_ip": ip_address,  # Show the detected client IP
                "user_agent_snippet": (
                    user_agent[:50] if user_agent != "Unknown" else "Unknown"
                ),
            },
        }

        return Response(response_data)

    except User.DoesNotExist:
        return Response(
            {
                "access_granted": False,
                "message": "User not found. Please register and pay to access Wi-Fi.",
                "suggestion": "Make a payment or redeem a voucher to create account and get access",
            },
            status=status.HTTP_404_NOT_FOUND,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def initiate_payment(request):
    """
    Initiate ClickPesa USSD-PUSH payment
    """
    serializer = InitiatePaymentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    phone_number = serializer.validated_data["phone_number"]
    bundle_id = serializer.validated_data.get("bundle_id")

    # Extract comprehensive request information
    request_info = get_request_info(request, serializer.validated_data)
    ip_address = request_info["ip_address"]
    mac_address = request_info["mac_address"]
    user_agent = request_info["user_agent"]

    # Get or create user with normalized phone number
    from .utils import get_or_create_user

    try:
        user, created = get_or_create_user(phone_number)
        if created:
            logger.info(
                f"Created new user {user.phone_number} (normalized from {phone_number}) for payment"
            )
        else:
            logger.info(f"Found existing user {user.phone_number} for payment")
    except ValueError as e:
        return Response(
            {"success": False, "message": f"Invalid phone number: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Register device if MAC address provided
    device = None
    device_tracking_result = None
    if mac_address:
        try:
            from .mikrotik import enhance_device_tracking_for_payment

            # Enhanced device tracking for payment initiation
            device_tracking_result = enhance_device_tracking_for_payment(
                payment_user=user, mac_address=mac_address, ip_address=ip_address
            )

            if device_tracking_result["success"]:
                # Get the device object for further processing
                device = user.devices.get(mac_address=mac_address)
                logger.info(
                    f"Device registered during payment initiation for {phone_number}: {mac_address}"
                )
            else:
                logger.warning(
                    f'Device tracking failed during payment initiation for {phone_number}: {device_tracking_result["message"]}'
                )

        except Exception as device_error:
            logger.error(
                f"Device registration error during payment initiation for {phone_number}: {str(device_error)}"
            )
            device_tracking_result = {
                "success": False,
                "message": f"Device registration error: {str(device_error)}",
                "device_tracked": False,
            }

    # Get bundle or use default
    if bundle_id:
        try:
            bundle = Bundle.objects.get(id=bundle_id, is_active=True)
            amount = bundle.price
        except Bundle.DoesNotExist:
            return Response(
                {"success": False, "message": "Invalid bundle selected"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        # Use default daily bundle
        bundle = Bundle.objects.filter(duration_hours=24, is_active=True).first()
        amount = bundle.price if bundle else settings.DAILY_ACCESS_PRICE

    # Generate unique order reference (alphanumeric only)
    order_reference = f"KITONGA{user.id}{uuid.uuid4().hex[:8].upper()}"

    # Create payment record
    payment = Payment.objects.create(
        user=user,
        bundle=bundle,
        amount=amount,
        phone_number=phone_number,
        transaction_id=str(uuid.uuid4()),
        order_reference=order_reference,
        status="pending",
    )

    clickpesa = ClickPesaAPI()
    result = clickpesa.initiate_payment(
        phone_number=phone_number, amount=amount, order_reference=order_reference
    )

    if result["success"]:
        return Response(
            {
                "success": True,
                "message": result["message"],
                "transaction_id": payment.transaction_id,
                "order_reference": order_reference,
                "amount": float(amount),
                "bundle": BundleSerializer(bundle).data if bundle else None,
                "channel": result.get("channel"),
            },
            status=status.HTTP_200_OK,
        )
    else:
        payment.mark_failed()
        return Response(
            {"success": False, "message": result["message"]},
            status=status.HTTP_400_BAD_REQUEST,
        )


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def clickpesa_webhook(request):
    """
    ClickPesa webhook endpoint
    Receives payment notifications from ClickPesa
    Handles both PAYMENT RECEIVED and PAYMENT FAILED events
    """
    webhook_log = None

    try:
        webhook_data = request.data
        logger.info(f"ClickPesa webhook received: {json.dumps(webhook_data)}")

        # Extract webhook data - handle both formats
        event_type = webhook_data.get("event") or webhook_data.get("eventType", "OTHER")
        payment_data = webhook_data.get("data", webhook_data.get("payment", {}))

        # Extract order reference from different possible fields
        order_reference = (
            payment_data.get("orderReference")
            or payment_data.get("order_reference")
            or payment_data.get("id")
            or webhook_data.get("order_reference")  # Check root level too
            or webhook_data.get("orderReference")
        )

        # Extract transaction/payment ID
        transaction_id = (
            payment_data.get("paymentId")
            or payment_data.get("id")
            or payment_data.get("transaction_id")
            or webhook_data.get("transaction_reference")  # Check root level too
            or webhook_data.get("transaction_id")
        )

        # Extract status
        status_code = payment_data.get("status") or webhook_data.get("status")

        # Extract other fields
        channel = payment_data.get("channel")
        amount = payment_data.get("collectedAmount") or payment_data.get("amount")

        # Convert amount to decimal if it's a string
        if amount and isinstance(amount, str):
            try:
                amount = float(amount)
            except ValueError:
                amount = None

        # Create webhook log entry with improved IP extraction
        request_info = get_request_info(request)

        from .models import PaymentWebhook

        webhook_log = PaymentWebhook.objects.create(
            event_type=(
                event_type
                if event_type in dict(PaymentWebhook.WEBHOOK_EVENT_CHOICES)
                else "OTHER"
            ),
            order_reference=order_reference or "UNKNOWN",
            transaction_id=transaction_id or "",
            payment_status=status_code or "UNKNOWN",
            channel=channel or "",
            amount=amount,
            raw_payload=webhook_data,
            source_ip=request_info["ip_address"],
            user_agent=request_info["user_agent"],
        )

        if not order_reference:
            error_msg = "No order reference in webhook data"
            logger.error(error_msg)
            webhook_log.mark_failed(error_msg)
            return Response({"success": False, "message": "Missing order reference"})

        # Check for duplicates
        if webhook_log.is_duplicate:
            webhook_log.mark_ignored("Duplicate webhook - already processed")
            logger.info(f"Duplicate webhook ignored: {order_reference} - {event_type}")
            return Response({"success": True, "message": "Duplicate webhook ignored"})

        # Find payment by order reference
        try:
            payment = Payment.objects.get(order_reference=order_reference)

            if (
                event_type == "PAYMENT RECEIVED" or status_code == "PAYMENT RECEIVED"
            ) and status_code in ["SUCCESS", "COMPLETED", "PAYMENT RECEIVED"]:
                # Payment successful
                payment.mark_completed(
                    payment_reference=transaction_id, channel=channel
                )
                logger.info(f"Payment completed: {order_reference} - {transaction_id}")

                # ============================================================
                # AUTOMATIC CONNECTION (Same logic as voucher redemption)
                # 1. Register/update device
                # 2. Grant MikroTik access (hotspot user + IP binding)
                # 3. Create access log
                # 4. Send SMS confirmation
                # ============================================================

                mikrotik_auth_result = None
                connection_success = False
                immediate_login_success = False
                auto_access_result = {}
                device = None

                try:
                    # Get user and their devices
                    user = payment.user
                    phone_number = payment.phone_number
                    devices = user.devices.filter(is_active=True)

                    if devices.exists():
                        # Grant access for all active user devices (same as voucher)
                        for device in devices:
                            try:
                                mac_address = device.mac_address
                                ip_address = device.ip_address

                                # Enhanced device tracking for payment users (same as voucher)
                                device_tracking_result = (
                                    enhance_device_tracking_for_payment(
                                        payment_user=user,
                                        mac_address=mac_address,
                                        ip_address=ip_address,
                                    )
                                )

                                if device_tracking_result.get("success"):
                                    logger.info(
                                        f"Enhanced device tracking successful for payment user {phone_number}: {mac_address}"
                                    )
                                else:
                                    logger.warning(
                                        f'Enhanced device tracking failed for {phone_number}: {device_tracking_result.get("message")}'
                                    )

                                # Grant immediate access via MikroTik (creates hotspot user + IP binding)
                                # Same function used in voucher redemption
                                auto_access_result = force_immediate_internet_access(
                                    username=phone_number,
                                    mac_address=mac_address,
                                    ip_address=ip_address,
                                    access_type="payment",
                                )

                                if auto_access_result.get("success"):
                                    connection_success = True
                                    immediate_login_success = True
                                    logger.info(
                                        f"✓ Auto-login successful for payment user {phone_number} - device: {mac_address}"
                                    )
                                else:
                                    logger.warning(
                                        f'Auto-login failed for device {mac_address} for {phone_number}: {auto_access_result.get("message")}'
                                    )

                                # Create access log for this device (same as voucher)
                                AccessLog.objects.create(
                                    user=user,
                                    device=device,
                                    ip_address=ip_address or "127.0.0.1",
                                    mac_address=mac_address,
                                    access_granted=True,
                                    denial_reason=f"Payment completed: {order_reference} - Access granted for {payment.bundle.duration_hours if payment.bundle else 24} hours",
                                )

                            except Exception as device_error:
                                logger.error(
                                    f"Error during auto-login for device {device.mac_address} for {phone_number}: {str(device_error)}"
                                )

                        mikrotik_auth_result = {
                            "success": connection_success,
                            "immediate_login_success": immediate_login_success,
                            "devices_processed": devices.count(),
                        }
                    else:
                        # No devices yet - create hotspot user so they can connect immediately when they join WiFi
                        # Same as voucher when no MAC provided
                        auto_access_result = create_hotspot_user_and_login(
                            username=phone_number, password=phone_number
                        )
                        mikrotik_auth_result = {
                            "success": auto_access_result.get("success", False),
                            "hotspot_user_created": True,
                            "immediate_login_success": False,
                            "message": "Hotspot user created - will connect when user joins WiFi",
                        }
                        logger.info(
                            f"No active devices for {phone_number} - created hotspot user for immediate connection"
                        )

                        # Create access log without device (same as voucher)
                        AccessLog.objects.create(
                            user=user,
                            device=None,
                            ip_address="127.0.0.1",
                            mac_address="",
                            access_granted=True,
                            denial_reason=f"Payment completed: {order_reference} - Access granted for {payment.bundle.duration_hours if payment.bundle else 24} hours (no device registered yet)",
                        )

                except Exception as e:
                    logger.error(
                        f"MikroTik auto-login failed after payment for {payment.phone_number}: {str(e)}"
                    )
                    mikrotik_auth_result = {"success": False, "error": str(e)}

                    # Still create access log even if MikroTik fails
                    try:
                        AccessLog.objects.create(
                            user=payment.user,
                            device=None,
                            ip_address="127.0.0.1",
                            mac_address="",
                            access_granted=True,
                            denial_reason=f"Payment completed: {order_reference} - MikroTik sync failed but access granted in database",
                        )
                    except Exception:
                        pass

                # Send SMS confirmation (with appropriate message based on connection status)
                from .nextsms import NextSMSAPI
                from .models import SMSLog

                nextsms = NextSMSAPI()
                duration_hours = payment.bundle.duration_hours if payment.bundle else 24

                # Enhanced SMS with connection instructions
                if mikrotik_auth_result and mikrotik_auth_result.get("success"):
                    sms_result = nextsms.send_payment_confirmation_with_auth_success(
                        payment.phone_number, payment.amount, duration_hours
                    )
                else:
                    sms_result = (
                        nextsms.send_payment_confirmation_with_reconnect_instructions(
                            payment.phone_number, payment.amount, duration_hours
                        )
                    )

                # Log SMS
                SMSLog.objects.create(
                    phone_number=payment.phone_number,
                    message=f"Payment confirmation: TSh {payment.amount}",
                    sms_type="payment",
                    success=sms_result["success"],
                    response_data=sms_result.get("data"),
                )

            elif event_type == "PAYMENT FAILED" or status_code == "FAILED":
                # Payment failed
                payment.mark_failed()
                logger.warning(f"Payment failed: {order_reference}")

                from .nextsms import NextSMSAPI
                from .models import SMSLog

                nextsms = NextSMSAPI()
                sms_result = nextsms.send_payment_failed_notification(
                    payment.phone_number, payment.amount
                )

                # Log SMS
                SMSLog.objects.create(
                    phone_number=payment.phone_number,
                    message=f"Payment failed notification: TSh {payment.amount}",
                    sms_type="payment",
                    success=sms_result["success"],
                    response_data=sms_result.get("data"),
                )

            # Mark webhook as processed
            webhook_log.mark_processed(payment)

            return Response(
                {"success": True, "message": "Webhook processed successfully"}
            )

        except Payment.DoesNotExist:
            error_msg = f"Payment not found for order reference: {order_reference}"
            logger.error(error_msg)
            webhook_log.mark_failed(error_msg)
            return Response(
                {"success": False, "message": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    except Exception as e:
        error_msg = f"Error processing ClickPesa webhook: {str(e)}"
        logger.error(error_msg)
        if webhook_log:
            webhook_log.mark_failed(error_msg)
        return Response(
            {"success": False, "message": "Webhook processing failed"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def clickpesa_payout_webhook(request):
    """
    ClickPesa Payout Webhook endpoint
    Receives payout status notifications from ClickPesa
    Handles: SUCCESS, FAILED, REVERSED, REFUNDED
    """
    try:
        webhook_data = request.data
        logger.info(f"ClickPesa PAYOUT webhook received: {json.dumps(webhook_data)}")

        # Extract payout data
        event_type = webhook_data.get("event") or webhook_data.get(
            "eventType", "PAYOUT"
        )
        payout_data = webhook_data.get("data", webhook_data)

        # Extract order reference (our payout reference)
        order_reference = (
            payout_data.get("orderReference")
            or payout_data.get("order_reference")
            or webhook_data.get("orderReference")
        )

        # Extract status
        payout_status = (
            payout_data.get("status") or webhook_data.get("status", "").upper()
        )

        # Extract transaction ID
        transaction_id = (
            payout_data.get("id")
            or payout_data.get("payoutId")
            or webhook_data.get("id")
        )

        logger.info(
            f"Payout webhook - Reference: {order_reference}, Status: {payout_status}, TxID: {transaction_id}"
        )

        if not order_reference:
            logger.error("No order reference in payout webhook")
            return Response({"success": False, "message": "Missing order reference"})

        # Find payout by reference
        from .models import TenantPayout

        try:
            payout = TenantPayout.objects.get(reference=order_reference)
            old_status = payout.status

            # Update status based on ClickPesa status
            if payout_status in ["SUCCESS", "COMPLETED"]:
                payout.mark_completed(transaction_id)
                logger.info(f"Payout {order_reference} marked as completed")

            elif payout_status in ["FAILED", "REVERSED", "REFUNDED"]:
                error_message = (
                    payout_data.get("notes")
                    or payout_data.get("message")
                    or f"ClickPesa status: {payout_status}"
                )
                payout.mark_failed(error_message)
                logger.warning(
                    f"Payout {order_reference} marked as failed: {error_message}"
                )

            elif payout_status in ["PROCESSING", "PENDING", "AUTHORIZED"]:
                if payout.status != "processing":
                    payout.status = "processing"
                    payout.transaction_id = transaction_id or payout.transaction_id
                    payout.save()
                    logger.info(f"Payout {order_reference} marked as processing")

            return Response(
                {
                    "success": True,
                    "message": f"Payout status updated: {old_status} -> {payout.status}",
                    "payout_reference": order_reference,
                }
            )

        except TenantPayout.DoesNotExist:
            logger.error(f"Payout not found for reference: {order_reference}")
            return Response(
                {"success": False, "message": "Payout not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    except Exception as e:
        error_msg = f"Error processing payout webhook: {str(e)}"
        logger.error(error_msg)
        return Response(
            {"success": False, "message": "Webhook processing failed"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def query_payment_status(request, order_reference):
    """
    Query payment status from ClickPesa
    """
    try:
        payment = Payment.objects.get(order_reference=order_reference)

        # Query ClickPesa for latest status
        clickpesa = ClickPesaAPI()
        result = clickpesa.query_payment_status(order_reference)

        if result["success"]:
            payment_data = result["data"]
            logger.info(
                f"ClickPesa returned data type: {type(payment_data)}, data: {payment_data}"
            )

            # Handle case where ClickPesa returns a list of payments
            if isinstance(payment_data, list):
                if payment_data:
                    # Use the first payment in the list
                    payment_data = payment_data[0]
                    logger.info(f"Using first payment from list: {payment_data}")
                else:
                    # Empty list - no payment found
                    return Response(
                        {"success": False, "message": "Payment not found in ClickPesa"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

            status_code = payment_data.get("status")

            # Initialize MikroTik auto-login result
            mikrotik_auto_login = None

            # Update payment status if changed
            # ClickPesa uses: PROCESSING, SUCCESS, SETTLED, FAILED, CANCELLED
            if (
                status_code in ["COMPLETED", "SUCCESS", "SETTLED"]
                and payment.status == "pending"
            ):
                payment.mark_completed(
                    payment_reference=payment_data.get("paymentReference")
                    or payment_data.get("id"),
                    channel=payment_data.get("channel"),
                )

                # === MIKROTIK AUTO-LOGIN AFTER SUCCESSFUL PAYMENT ===
                # Get user's most recent active device for auto-login
                try:
                    user = payment.user
                    device = (
                        user.devices.filter(is_active=True)
                        .order_by("-last_seen")
                        .first()
                    )

                    if device:
                        logger.info(
                            f"Attempting MikroTik auto-login for payment user {user.phone_number} with device {device.mac_address}"
                        )

                        # Use the comprehensive auto-login function
                        auto_access_result = force_immediate_internet_access(
                            username=user.phone_number,
                            mac_address=device.mac_address,
                            ip_address=device.ip_address or "0.0.0.0",
                            access_type="payment",
                        )

                        mikrotik_auto_login = {
                            "success": auto_access_result.get("success", False),
                            "message": auto_access_result.get("message", ""),
                            "device_mac": device.mac_address,
                            "device_ip": device.ip_address,
                            "hotspot_user_created": auto_access_result.get(
                                "hotspot_user_created", False
                            ),
                            "ip_binding_created": auto_access_result.get(
                                "ip_binding_created", False
                            ),
                            "immediate_access": auto_access_result.get(
                                "success", False
                            ),
                            # Include device capture from MikroTik
                            "device_capture": auto_access_result.get(
                                "device_capture", {}
                            ),
                        }

                        if auto_access_result.get("success"):
                            logger.info(
                                f"✓ MikroTik auto-login successful for payment user {user.phone_number}"
                            )
                        else:
                            logger.warning(
                                f'MikroTik auto-login failed for payment user {user.phone_number}: {auto_access_result.get("message")}'
                            )
                    else:
                        # No device registered yet, create hotspot user for when they connect
                        logger.info(
                            f"No device found for payment user {user.phone_number}, creating hotspot user for later connection"
                        )

                        hotspot_result = create_hotspot_user_and_login(
                            username=user.phone_number, password=user.phone_number
                        )

                        mikrotik_auto_login = {
                            "success": hotspot_result.get("success", False),
                            "message": "Hotspot user created. User will auto-connect when joining WiFi.",
                            "device_mac": None,
                            "device_ip": None,
                            "hotspot_user_created": hotspot_result.get(
                                "success", False
                            ),
                            "ip_binding_created": False,
                            "immediate_access": False,
                            "note": "User needs to connect to WiFi hotspot to get internet access",
                        }

                except Exception as mikrotik_error:
                    logger.error(
                        f"MikroTik auto-login error for payment {order_reference}: {str(mikrotik_error)}"
                    )
                    mikrotik_auto_login = {
                        "success": False,
                        "message": f"MikroTik connection error: {str(mikrotik_error)}",
                        "error": str(mikrotik_error),
                    }
                # === END MIKROTIK AUTO-LOGIN ===

            elif status_code in ["FAILED", "CANCELLED"] and payment.status == "pending":
                payment.mark_failed()

            response_data = {
                "success": True,
                "payment": PaymentSerializer(payment).data,
                "clickpesa_status": payment_data,
            }

            # Include MikroTik auto-login info if payment was just completed
            if mikrotik_auto_login:
                response_data["mikrotik_auto_login"] = mikrotik_auto_login

            return Response(response_data)
        else:
            # ClickPesa query failed, return local payment status
            logger.warning(
                f'ClickPesa query failed for {order_reference}: {result["message"]}'
            )
            return Response(
                {
                    "success": True,
                    "payment": PaymentSerializer(payment).data,
                    "clickpesa_status": None,
                    "message": "Using local payment status (ClickPesa query failed)",
                }
            )

    except Payment.DoesNotExist:
        return Response(
            {"success": False, "message": "Payment not found"},
            status=status.HTTP_404_NOT_FOUND,
        )


@api_view(["POST"])
@permission_classes([SimpleAdminTokenPermission])
def generate_vouchers(request):
    """
    Generate voucher codes (Admin only) and send SMS notification
    """
    serializer = GenerateVouchersSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    quantity = serializer.validated_data["quantity"]
    duration_hours = serializer.validated_data["duration_hours"]
    batch_id = serializer.validated_data.get(
        "batch_id", f"BATCH-{uuid.uuid4().hex[:8].upper()}"
    )
    notes = serializer.validated_data.get("notes", "")
    admin_phone_number = serializer.validated_data["admin_phone_number"]
    language = serializer.validated_data.get("language", "en")

    created_by = request.user.username if request.user.is_authenticated else "admin"

    # Generate vouchers
    vouchers = []
    for _ in range(quantity):
        voucher = Voucher.objects.create(
            code=Voucher.generate_code(),
            duration_hours=duration_hours,
            batch_id=batch_id,
            created_by=created_by,
            notes=notes,
        )
        vouchers.append(voucher)

    logger.info(f"Generated {quantity} vouchers in batch {batch_id} by {created_by}")

    # Send SMS notification to admin
    from .nextsms import NextSMSAPI
    from .models import SMSLog

    nextsms = NextSMSAPI()

    # Send summary notification first
    summary_result = nextsms.send_voucher_generation_notification(
        admin_phone_number, vouchers, language
    )

    # Log summary SMS
    SMSLog.objects.create(
        phone_number=admin_phone_number,
        message=f"Voucher generation summary: {quantity} vouchers in batch {batch_id}",
        sms_type="admin",
        success=summary_result["success"],
        response_data=summary_result.get("data"),
    )

    # Send detailed voucher codes if requested (for small batches)
    detailed_result = None
    if quantity <= 10:  # Only send detailed codes for small batches
        detailed_result = nextsms.send_voucher_summary_sms(
            admin_phone_number, vouchers, language
        )

        # Log detailed SMS
        SMSLog.objects.create(
            phone_number=admin_phone_number,
            message=f"Detailed voucher codes for batch {batch_id}",
            sms_type="admin",
            success=detailed_result["success"],
            response_data=detailed_result.get("details"),
        )

    response_data = {
        "success": True,
        "message": f"Successfully generated {quantity} vouchers",
        "batch_id": batch_id,
        "vouchers": VoucherSerializer(vouchers, many=True).data,
        "sms_notification": {
            "summary_sent": summary_result["success"],
            "detailed_sent": detailed_result["success"] if detailed_result else False,
            "admin_phone": admin_phone_number,
            "language": language,
        },
    }

    # Add warning if SMS failed
    if not summary_result["success"]:
        response_data["warning"] = "Vouchers generated but SMS notification failed"

    return Response(response_data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def redeem_voucher(request):
    """
    Redeem a voucher code and grant internet access
    Creates user account if needed and enables device access
    """
    serializer = RedeemVoucherSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    voucher_code = serializer.validated_data["voucher_code"]
    phone_number = serializer.validated_data["phone_number"]

    # Extract comprehensive request information
    request_info = get_request_info(request, serializer.validated_data)
    ip_address = request_info["ip_address"]
    mac_address = request_info["mac_address"]
    user_agent = request_info["user_agent"]

    try:
        voucher = Voucher.objects.get(code=voucher_code)

        # Check if voucher is already used
        if voucher.is_used:
            logger.warning(
                f"Attempt to redeem already used voucher {voucher_code} by {phone_number}"
            )
            return Response(
                {
                    "success": False,
                    "message": "Voucher has already been used",
                    "voucher_info": {
                        "code": voucher_code,
                        "used_at": (
                            voucher.used_at.isoformat() if voucher.used_at else None
                        ),
                        "used_by": (
                            voucher.used_by.phone_number if voucher.used_by else None
                        ),
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get or create user with normalized phone number
        from .utils import get_or_create_user

        try:
            user, created = get_or_create_user(phone_number, max_devices=1)
            if created:
                logger.info(
                    f"Created new user {user.phone_number} (normalized from {phone_number}) via voucher redemption"
                )
            else:
                logger.info(
                    f"Found existing user {user.phone_number} for voucher redemption"
                )
        except ValueError as e:
            return Response(
                {"success": False, "message": f"Invalid phone number: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Redeem voucher - this will extend user access
        success, message = voucher.redeem(user)

        if success:
            logger.info(
                f"Voucher {voucher_code} redeemed by {phone_number} - access granted for {voucher.duration_hours} hours"
            )

            # Initialize variables that will be used throughout the response
            immediate_login_success = False
            mikrotik_auth_result = False
            auto_access_result = {}  # Initialize for auto-login details

            # Handle device registration if MAC address provided
            device = None
            device_info = {}
            mikrotik_integration_info = {}

            if mac_address:
                try:
                    from .mikrotik import enhance_device_tracking_for_voucher

                    # Enhanced device tracking for voucher redemption
                    device_tracking_result = enhance_device_tracking_for_voucher(
                        voucher_user=user,
                        mac_address=mac_address,
                        ip_address=ip_address or "127.0.0.1",
                    )

                    if device_tracking_result["success"]:
                        device = user.devices.get(mac_address=mac_address)
                        device_info = {
                            "device_registered": True,
                            "device_id": device.id,
                            "mac_address": mac_address,
                            "device_count": user.get_active_devices().count(),
                            "max_devices": user.max_devices,
                            "device_tracking_enhanced": True,
                        }
                        logger.info(
                            f"Enhanced device tracking successful for voucher user {phone_number}: {mac_address}"
                        )
                    else:
                        # Handle device tracking failure
                        if device_tracking_result.get("device_limit_exceeded"):
                            device_info = {
                                "device_registered": False,
                                "device_limit_exceeded": True,
                                "device_count": device_tracking_result.get(
                                    "active_devices", 0
                                ),
                                "max_devices": device_tracking_result.get(
                                    "max_devices", user.max_devices
                                ),
                                "warning": device_tracking_result["message"],
                            }
                        else:
                            device_info = {
                                "device_registered": False,
                                "error": device_tracking_result["message"],
                                "device_tracking_enhanced": False,
                            }
                        logger.warning(
                            f'Enhanced device tracking failed for voucher user {phone_number}: {device_tracking_result["message"]}'
                        )

                except Exception as device_error:
                    logger.error(
                        f"Device tracking error during voucher redemption for {phone_number}: {str(device_error)}"
                    )
                    # Fallback to original device registration method
                    try:
                        device, device_created = Device.objects.get_or_create(
                            user=user,
                            mac_address=mac_address,
                            defaults={
                                "ip_address": ip_address or "127.0.0.1",
                                "is_active": True,
                            },
                        )

                        if device_created:
                            active_devices = user.get_active_devices().count()
                            if active_devices <= user.max_devices:
                                device_info = {
                                    "device_registered": True,
                                    "device_id": device.id,
                                    "mac_address": mac_address,
                                    "device_count": active_devices,
                                    "max_devices": user.max_devices,
                                    "fallback_registration": True,
                                }
                                logger.info(
                                    f"Fallback device registration successful for voucher user {phone_number}: {mac_address}"
                                )
                            else:
                                # Device limit exceeded
                                device.is_active = False
                                device.save()
                                device_info = {
                                    "device_registered": False,
                                    "device_limit_exceeded": True,
                                    "device_count": active_devices,
                                    "max_devices": user.max_devices,
                                    "warning": "Device limit exceeded. Please remove an existing device first.",
                                }
                                logger.warning(
                                    f"Device limit exceeded for voucher user {phone_number}: {active_devices}/{user.max_devices}"
                                )
                        else:
                            # Update existing device
                            device.ip_address = ip_address or device.ip_address
                            device.is_active = True
                            device.save()
                            device_info = {
                                "device_registered": True,
                                "device_id": device.id,
                                "mac_address": mac_address,
                                "existing_device_updated": True,
                                "fallback_registration": True,
                            }
                            logger.info(
                                f"Fallback device update successful for voucher user {phone_number}: {mac_address}"
                            )
                    except Exception as fallback_error:
                        logger.error(
                            f"Fallback device registration also failed for voucher user {phone_number}: {str(fallback_error)}"
                        )
                        device_info = {
                            "device_registered": False,
                            "error": f"Device registration failed: {str(fallback_error)}",
                        }

                # AUTOMATIC CONNECTION: Try to authenticate with MikroTik immediately after successful voucher redemption
                try:
                    # Grant immediate internet access using the new comprehensive method
                    if (
                        mac_address
                        and ip_address
                        and device_info.get("device_registered")
                    ):
                        try:
                            # Use the comprehensive auto-login function for immediate access
                            auto_access_result = force_immediate_internet_access(
                                username=phone_number,
                                mac_address=mac_address,
                                ip_address=ip_address,
                                access_type="voucher",
                            )

                            mikrotik_auth_result = auto_access_result.get(
                                "success", False
                            )
                            immediate_login_success = mikrotik_auth_result

                            if immediate_login_success:
                                logger.info(
                                    f"✓ Auto-login successful for voucher user {phone_number} - device: {mac_address}"
                                )
                            else:
                                logger.warning(
                                    f'Auto-login failed for voucher user {phone_number}: {auto_access_result.get("message")}'
                                )

                        except Exception as login_error:
                            logger.error(
                                f"Error during auto-login for voucher user {phone_number}: {str(login_error)}"
                            )
                            mikrotik_auth_result = False
                            immediate_login_success = False
                    else:
                        # No MAC/IP provided or device registration failed, create hotspot user for manual connection
                        hotspot_user_result = create_hotspot_user_and_login(
                            username=phone_number, password=phone_number
                        )
                        mikrotik_auth_result = hotspot_user_result.get("success", False)
                        immediate_login_success = False
                        logger.info(
                            f"Created hotspot user for voucher user {phone_number} - will connect when they join WiFi"
                        )
                        logger.info(
                            f"Created hotspot user for {phone_number} - will connect when they join WiFi"
                        )

                    mikrotik_integration_info = {
                        "mikrotik_auth_attempted": True,
                        "mikrotik_auth_success": mikrotik_auth_result,
                        "immediate_login_attempted": bool(mac_address and ip_address),
                        "immediate_login_success": immediate_login_success,
                        "ready_for_internet": immediate_login_success
                        or (mikrotik_auth_result and user.has_active_access()),
                        "auto_connect_status": (
                            "connected"
                            if immediate_login_success
                            else "ready_to_connect"
                        ),
                        # Include detailed auto-login info (same as payment flow)
                        "auto_login_details": {
                            "success": auto_access_result.get("success", False),
                            "message": auto_access_result.get(
                                "message", "No auto-login attempted"
                            ),
                            "device_mac": mac_address,
                            "device_ip": ip_address,
                            "hotspot_user_created": auto_access_result.get(
                                "hotspot_user_created", False
                            ),
                            "ip_binding_created": auto_access_result.get(
                                "ip_binding_created", False
                            ),
                            "method_used": auto_access_result.get("method_used"),
                            "immediate_access": immediate_login_success,
                            # Include device capture from MikroTik
                            "device_capture": auto_access_result.get(
                                "device_capture", {}
                            ),
                        },
                        "device_tracking": {
                            "device_registered": bool(device),
                            "device_id": device.id if device else None,
                            "mac_address": mac_address,
                            "ip_address": ip_address,
                            "device_name": device.device_name if device else None,
                            "is_new_device": device_info.get("device_registered", False)
                            and "device_id" in device_info,
                            "device_count": user.get_active_devices().count(),
                            "max_devices": user.max_devices,
                        },
                    }

                    if mikrotik_auth_result or immediate_login_success:
                        logger.info(
                            f"MikroTik integration successful for voucher user {phone_number}"
                        )
                    else:
                        logger.warning(
                            f"MikroTik integration incomplete for voucher user {phone_number} - user will authenticate on next WiFi connection"
                        )

                except Exception as e:
                    logger.error(
                        f"MikroTik authentication error for voucher user {phone_number}: {str(e)}"
                    )
                    mikrotik_integration_info = {
                        "mikrotik_auth_attempted": True,
                        "mikrotik_auth_success": False,
                        "immediate_login_attempted": bool(mac_address and ip_address),
                        "immediate_login_success": False,
                        "mikrotik_error": str(e),
                        "ready_for_internet": user.has_active_access(),  # User still has access, just MikroTik sync failed
                        "auto_connect_status": "will_authenticate_on_next_connection",
                        "device_tracking": {
                            "device_registered": bool(device),
                            "device_id": device.id if device else None,
                            "mac_address": mac_address,
                            "ip_address": ip_address,
                            "note": "Device tracked in database but MikroTik sync failed - will authenticate on next connection",
                            "device_count": user.get_active_devices().count(),
                            "max_devices": user.max_devices,
                        },
                    }
            else:
                # No MAC address provided, but user still gets access for when they connect
                device_info = {
                    "device_registered": False,
                    "message": "No device registered. User can connect with any device within device limit.",
                    "max_devices": user.max_devices,
                }
                mikrotik_integration_info = {
                    "mikrotik_auth_attempted": False,
                    "ready_for_internet": user.has_active_access(),
                    "note": "Device will be registered when user connects to WiFi",
                    "device_tracking": {
                        "device_registered": False,
                        "message": "No device registered yet - will track when user connects to WiFi",
                        "max_devices": user.max_devices,
                        "current_device_count": user.get_active_devices().count(),
                    },
                }

            # Create access log for voucher redemption
            AccessLog.objects.create(
                user=user,
                device=device,
                ip_address=ip_address or "127.0.0.1",
                mac_address=mac_address,
                access_granted=True,
                denial_reason=f"Voucher redeemed: {voucher_code} - Access granted for {voucher.duration_hours} hours",
            )

            # Send SMS confirmation
            try:
                from .nextsms import NextSMSAPI
                from .models import SMSLog

                nextsms = NextSMSAPI()
                sms_result = nextsms.send_voucher_confirmation(
                    phone_number, voucher_code, voucher.duration_hours
                )

                # Log SMS
                SMSLog.objects.create(
                    phone_number=phone_number,
                    message=f"Voucher redemption: {voucher_code}",
                    sms_type="voucher",
                    success=sms_result["success"],
                    response_data=sms_result.get("data"),
                )

                sms_sent = sms_result["success"]
            except Exception as e:
                logger.error(
                    f"SMS notification failed for voucher redemption {voucher_code}: {str(e)}"
                )
                sms_sent = False

            # Enhanced response with access and device information
            response_data = {
                "success": True,
                "message": message,
                "user": UserSerializer(user).data,
                "voucher_info": {
                    "code": voucher_code,
                    "duration_hours": voucher.duration_hours,
                    "redeemed_at": voucher.used_at.isoformat(),
                    "batch_id": voucher.batch_id,
                },
                "access_info": {
                    "has_active_access": user.has_active_access(),
                    "paid_until": (
                        user.paid_until.isoformat() if user.paid_until else None
                    ),
                    "access_method": "voucher",
                    "can_connect_to_wifi": user.has_active_access(),
                    "instructions": (
                        "Your internet access is now active!"
                        if mikrotik_integration_info.get(
                            "immediate_login_success", False
                        )
                        else "Connect to WiFi network. Your device will automatically get internet access."
                    ),
                },
                "device_info": device_info,
                "mikrotik_integration": mikrotik_integration_info,
                "sms_notification_sent": sms_sent,
                "next_steps": [
                    (
                        "1. Connect your device to the WiFi network"
                        if not immediate_login_success
                        else "1. ✅ Your device is already connected and should have internet access"
                    ),
                    (
                        "2. Open your browser - you should automatically get internet access"
                        if immediate_login_success
                        else "2. Open your browser and you should automatically get internet access"
                    ),
                    (
                        "3. If prompted, enter your phone number to authenticate"
                        if not immediate_login_success
                        else "3. ✅ Authentication completed automatically"
                    ),
                    f'4. Your access is valid until {user.paid_until.strftime("%Y-%m-%d %H:%M") if user.paid_until else "N/A"}',
                    (
                        "5. If you still cannot access internet, disconnect and reconnect to WiFi"
                        if not immediate_login_success
                        else "5. ✅ Internet access should be working now"
                    ),
                ],
            }

            return Response(response_data, status=status.HTTP_200_OK)

        else:
            # Voucher redemption failed
            logger.error(
                f"Voucher redemption failed for {voucher_code} by {phone_number}: {message}"
            )
            return Response(
                {"success": False, "message": message},
                status=status.HTTP_400_BAD_REQUEST,
            )

    except Voucher.DoesNotExist:
        logger.warning(
            f"Invalid voucher code {voucher_code} attempted by {phone_number}"
        )
        return Response(
            {"success": False, "message": "Invalid voucher code"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(
            f"Error during voucher redemption {voucher_code} by {phone_number}: {str(e)}"
        )
        return Response(
            {
                "success": False,
                "message": "Voucher redemption failed due to system error",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([SimpleAdminTokenPermission])
def list_vouchers(request):
    """
    List all vouchers from ALL tenants with optional filters (Admin only)
    Shows tenant info for each voucher and supports filtering by tenant
    """
    vouchers = Voucher.objects.all().order_by('-created_at')

    # Filter by tenant
    tenant_filter = request.query_params.get("tenant")
    if tenant_filter:
        vouchers = vouchers.filter(tenant__slug=tenant_filter)

    # Filter by status
    is_used = request.query_params.get("is_used")
    if is_used is not None:
        vouchers = vouchers.filter(is_used=is_used.lower() == "true")

    # Filter by batch
    batch_id = request.query_params.get("batch_id")
    if batch_id:
        vouchers = vouchers.filter(batch_id=batch_id)

    # Filter by duration
    duration = request.query_params.get("duration_hours")
    if duration:
        vouchers = vouchers.filter(duration_hours=int(duration))

    # Pagination
    page_size = int(request.query_params.get("page_size", 50))
    page = int(request.query_params.get("page", 1))
    start = (page - 1) * page_size
    end = start + page_size
    
    total_vouchers = vouchers.count()
    vouchers_page = vouchers[start:end]

    # Serialize with tenant info
    vouchers_data = []
    for voucher in vouchers_page:
        voucher_data = {
            'id': voucher.id,
            'code': voucher.code,
            'tenant': voucher.tenant.slug if voucher.tenant else 'platform',
            'tenant_name': voucher.tenant.business_name if voucher.tenant else 'Platform',
            'duration_hours': voucher.duration_hours,
            'bundle': voucher.bundle.name if voucher.bundle else None,
            'is_used': voucher.is_used,
            'used_by': voucher.used_by.phone_number if voucher.used_by else None,
            'used_at': voucher.used_at.isoformat() if voucher.used_at else None,
            'batch_id': voucher.batch_id,
            'created_at': voucher.created_at.isoformat() if voucher.created_at else None,
            'created_by': voucher.created_by,
            'notes': voucher.notes,
        }
        vouchers_data.append(voucher_data)

    # Get summary stats
    used_count = vouchers.filter(is_used=True).count()
    available_count = vouchers.filter(is_used=False).count()

    return Response(
        {
            "success": True,
            "vouchers": vouchers_data,
            "pagination": {
                "total": total_vouchers,
                "page": page,
                "page_size": page_size,
                "total_pages": (total_vouchers + page_size - 1) // page_size if total_vouchers > 0 else 0
            },
            "summary": {
                "total": total_vouchers,
                "used": used_count,
                "available": available_count
            }
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def user_status(request, phone_number):
    """
    Get user status and access information
    """
    try:
        from .utils import find_user_by_phone

        user = find_user_by_phone(phone_number)

        if not user:
            return Response(
                {"message": "User not found", "phone_number_searched": phone_number},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(UserSerializer(user).data)
    except Exception as e:
        return Response(
            {"message": f"Error retrieving user: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@staff_member_required
def dashboard_stats_view(request):
    """
    Dashboard statistics template view for admin
    """
    # Get statistics
    active_users = get_active_users_count()
    revenue_30d = get_revenue_statistics(days=30)
    revenue_7d = get_revenue_statistics(days=7)
    revenue_today = get_revenue_statistics(days=1)

    # Recent payments
    recent_payments = (
        Payment.objects.filter(status="completed")
        .select_related("user")
        .order_by("-completed_at")[:10]
    )

    # Recent users
    recent_users = User.objects.order_by("-created_at")[:10]

    # Payment status breakdown
    payment_stats = Payment.objects.values("status").annotate(count=Count("id"))

    voucher_stats = {
        "total": Voucher.objects.count(),
        "used": Voucher.objects.filter(is_used=True).count(),
        "available": Voucher.objects.filter(is_used=False).count(),
    }

    # Device statistics
    device_stats = {
        "total": Device.objects.count(),
        "active": Device.objects.filter(is_active=True).count(),
        "inactive": Device.objects.filter(is_active=False).count(),
    }

    context = {
        "active_users": active_users,
        "revenue_30d": revenue_30d,
        "revenue_7d": revenue_7d,
        "revenue_today": revenue_today,
        "recent_payments": recent_payments,
        "recent_users": recent_users,
        "payment_stats": payment_stats,
        "voucher_stats": voucher_stats,
        "device_stats": device_stats,
    }

    return render(request, "admin/dashboard.html", context)


@api_view(["GET"])
@permission_classes([SimpleAdminTokenPermission])
def dashboard_stats(request):
    """
    Dashboard statistics API endpoint for admin
    """
    # Get statistics
    active_users = get_active_users_count()
    revenue_30d = get_revenue_statistics(days=30)
    revenue_7d = get_revenue_statistics(days=7)
    revenue_today = get_revenue_statistics(days=1)

    # Recent payments
    recent_payments = (
        Payment.objects.filter(status="completed")
        .select_related("user")
        .order_by("-completed_at")[:10]
    )

    # Recent users
    recent_users = User.objects.order_by("-created_at")[:10]

    # Payment status breakdown
    payment_stats = list(Payment.objects.values("status").annotate(count=Count("id")))

    voucher_stats = {
        "total": Voucher.objects.count(),
        "used": Voucher.objects.filter(is_used=True).count(),
        "available": Voucher.objects.filter(is_used=False).count(),
    }

    # Device statistics
    device_stats = {
        "total": Device.objects.count(),
        "active": Device.objects.filter(is_active=True).count(),
        "inactive": Device.objects.filter(is_active=False).count(),
    }

    # Serialize recent payments
    recent_payments_data = []
    for payment in recent_payments:
        recent_payments_data.append(
            {
                "id": payment.id,
                "phone_number": payment.phone_number,
                "amount": str(payment.amount),
                "status": payment.status,
                "completed_at": (
                    payment.completed_at.isoformat() if payment.completed_at else None
                ),
                "created_at": payment.created_at.isoformat(),
            }
        )

    # Serialize recent users
    recent_users_data = []
    for user in recent_users:
        recent_users_data.append(
            {
                "id": user.id,
                "phone_number": user.phone_number,
                "created_at": user.created_at.isoformat(),
                "is_active": user.is_active,
                "has_active_access": user.has_active_access(),
            }
        )

    return Response(
        {
            "active_users": active_users,
            "revenue_30d": revenue_30d,
            "revenue_7d": revenue_7d,
            "revenue_today": revenue_today,
            "recent_payments": recent_payments_data,
            "recent_users": recent_users_data,
            "payment_stats": payment_stats,
            "voucher_stats": voucher_stats,
            "device_stats": device_stats,
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint for monitoring and load balancers
    """
    try:
        # Check database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        # Check cache if configured
        try:
            cache.set("health_check", "ok", 10)
            cache.get("health_check")
        except Exception:
            pass  # Cache might not be configured

        return Response(
            {
                "status": "healthy",
                "timestamp": timezone.now().isoformat(),
                "version": "1.0.0",
                "service": "kitonga-wifi-billing",
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return Response(
            {
                "status": "unhealthy",
                "timestamp": timezone.now().isoformat(),
                "error": str(e),
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def list_bundles(request):
    """
    List all active bundles
    """
    bundles = Bundle.objects.filter(is_active=True)
    return Response(
        {"success": True, "bundles": BundleSerializer(bundles, many=True).data}
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def list_user_devices(request, phone_number):
    """
    List all devices for a user
    """
    try:
        from .utils import find_user_by_phone

        user = find_user_by_phone(phone_number)

        if not user:
            return Response(
                {
                    "success": False,
                    "message": "User not found",
                    "phone_number_searched": phone_number,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        devices = user.devices.all()

        return Response(
            {
                "success": True,
                "max_devices": user.max_devices,
                "active_devices": user.get_active_devices().count(),
                "devices": DeviceSerializer(devices, many=True).data,
                "phone_number": user.phone_number,  # Show normalized phone number
            }
        )
    except Exception as e:
        return Response(
            {"success": False, "message": f"Error retrieving devices: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def remove_device(request):
    """
    Remove a device from user's account
    """
    phone_number = request.data.get("phone_number")
    device_id = request.data.get("device_id")

    if not phone_number or not device_id:
        return Response(
            {"success": False, "message": "Phone number and device ID are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        from .utils import find_user_by_phone

        user = find_user_by_phone(phone_number)

        if not user:
            return Response(
                {
                    "success": False,
                    "message": "User not found",
                    "phone_number_searched": phone_number,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        device = Device.objects.get(id=device_id, user=user)

        device.is_active = False
        device.save()

        return Response(
            {
                "success": True,
                "message": "Device removed successfully",
                "phone_number": user.phone_number,  # Show normalized phone number
            }
        )
    except Device.DoesNotExist:
        return Response(
            {"success": False, "message": "Device not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"success": False, "message": f"Error removing device: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([SimpleAdminTokenPermission])
def webhook_logs(request):
    """
    List webhook logs for debugging (Admin only)
    """
    logs = PaymentWebhook.objects.all()

    # Filter by processing status
    processing_status = request.query_params.get("processing_status")
    if processing_status:
        logs = logs.filter(processing_status=processing_status)

    # Filter by event type
    event_type = request.query_params.get("event_type")
    if event_type:
        logs = logs.filter(event_type=event_type)

    # Filter by order reference
    order_reference = request.query_params.get("order_reference")
    if order_reference:
        logs = logs.filter(order_reference__icontains=order_reference)

    # Limit results
    limit = int(request.query_params.get("limit", 50))
    logs = logs[:limit]

    webhook_data = []
    for log in logs:
        webhook_data.append(
            {
                "id": log.id,
                "order_reference": log.order_reference,
                "event_type": log.event_type,
                "processing_status": log.processing_status,
                "payment_status": log.payment_status,
                "amount": float(log.amount) if log.amount else None,
                "channel": log.channel,
                "received_at": log.received_at.isoformat(),
                "processed_at": (
                    log.processed_at.isoformat() if log.processed_at else None
                ),
                "processing_error": log.processing_error,
                "source_ip": log.source_ip,
                "has_payment": log.payment is not None,
                "raw_payload": log.raw_payload,
            }
        )

    return Response(
        {"success": True, "count": len(webhook_data), "webhooks": webhook_data}
    )


# Mikrotik Integration APIs
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
import json


@csrf_exempt
def mikrotik_auth(request):
    """
    Mikrotik hotspot authentication endpoint

    This endpoint is called by Mikrotik router for external authentication
    Mikrotik expects HTTP 200 for success, 403 for deny

    Works for both payment and voucher users through unified access checking
    Handles both form data and JSON data from MikroTik routers
    Enhanced to handle frontend API calls with JSON responses
    """
    # Detect if this is a frontend API call or MikroTik router call
    is_frontend_call = (
        request.content_type == "application/json"
        or "application/json" in request.META.get("HTTP_ACCEPT", "")
        or request.META.get("HTTP_USER_AGENT", "").startswith("Mozilla/")
    )

    # Get parameters from Mikrotik (can be POST or GET, form data or JSON)
    username = None
    password = ""
    mac_address = ""
    ip_address = ""

    if request.method == "POST":
        # Try to get from form data first (most common for MikroTik)
        username = request.POST.get("username")
        password = request.POST.get("password", "")
        mac_address = request.POST.get("mac", "")
        ip_address = request.POST.get("ip", "")

        # If not found in form data, try JSON
        if not username:
            try:
                json_data = json.loads(request.body.decode("utf-8"))
                username = json_data.get("username") or json_data.get("phone_number")
                password = json_data.get("password", "")
                mac_address = json_data.get("mac", "")
                ip_address = json_data.get("ip", "")
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
    else:
        # GET request
        username = request.GET.get("username")
        password = request.GET.get("password", "")
        mac_address = request.GET.get("mac", "")
        ip_address = request.GET.get("ip", "")

    logger.info(
        f"Mikrotik auth request: method={request.method}, username={username}, mac={mac_address}, ip={ip_address}, frontend={is_frontend_call}"
    )

    if not username:
        logger.warning("Mikrotik auth failed: No username provided")
        error_msg = "No username provided"
        if is_frontend_call:
            return JsonResponse(
                {"error": error_msg, "auth-state": 0, "success": False}, status=400
            )
        return HttpResponse(error_msg, status=403)

    try:
        # Check if user exists and has valid access with normalized phone number
        from .utils import find_user_by_phone

        user = find_user_by_phone(username)

        if not user:
            logger.warning(
                f"Mikrotik auth failed for {username}: User not found - no payment or voucher history"
            )
            error_msg = "User not found - please make payment or redeem voucher"

            if is_frontend_call:
                return JsonResponse(
                    {
                        "error": error_msg,
                        "auth-state": 0,
                        "success": False,
                        "phone_number_searched": username,
                    },
                    status=404,
                )
            return HttpResponse(error_msg, status=403)

        # Determine access method for better logging
        access_method = "unknown"
        if user.paid_until:
            has_payments = user.payments.filter(status="completed").exists()
            has_vouchers = user.vouchers_used.filter(is_used=True).exists()

            if has_payments and has_vouchers:
                access_method = "payment_and_voucher"
            elif has_payments:
                access_method = "payment"
            elif has_vouchers:
                access_method = "voucher"
            else:
                access_method = "manual"

        # Check if user has active access (unified logic for both payment and voucher users)
        has_access = user.has_active_access()
        denial_reason = ""
        device = None

        if not has_access:
            # Provide specific denial reasons based on user state
            if not user.is_active:
                denial_reason = "User account deactivated"
            elif not user.paid_until:
                denial_reason = (
                    "No payment or voucher found - please pay or redeem voucher"
                )
            else:
                from django.utils import timezone

                now = timezone.now()
                if user.paid_until <= now:
                    expired_hours = int((now - user.paid_until).total_seconds() / 3600)
                    denial_reason = f"Access expired {expired_hours} hours ago - please pay or redeem voucher"
                else:
                    denial_reason = "Access verification failed"

            logger.info(
                f"MikroTik access denied for {username}: {denial_reason} (method: {access_method}, paid_until: {user.paid_until})"
            )
        else:
            # User has access - handle device registration if MAC address provided
            if mac_address:
                # Enhanced device connection tracking for WiFi access
                try:
                    from .mikrotik import track_device_connection

                    # Track device connection with access method detection
                    device_tracking_result = track_device_connection(
                        phone_number=username,
                        mac_address=mac_address,
                        ip_address=ip_address,
                        connection_type="wifi",
                        access_method=access_method,
                    )

                    if device_tracking_result["success"]:
                        try:
                            device = user.devices.get(mac_address=mac_address)
                            logger.info(
                                f"Enhanced device tracking successful for {username}: {mac_address} -> {ip_address} (method: {access_method})"
                            )
                        except Device.DoesNotExist:
                            logger.warning(
                                f"Device tracking reported success but device not found for {username}: {mac_address}"
                            )
                            device = None
                    else:
                        # Check if device limit was exceeded
                        if device_tracking_result.get("device_limit_exceeded"):
                            has_access = False
                            denial_reason = device_tracking_result["message"]
                            logger.warning(
                                f'Device limit exceeded for {username}: {device_tracking_result.get("active_devices", 0)}/{device_tracking_result.get("max_devices", user.max_devices)} (method: {access_method})'
                            )
                        else:
                            logger.warning(
                                f'Device tracking failed for {username}: {device_tracking_result["message"]} (method: {access_method})'
                            )

                except Exception as tracking_error:
                    logger.error(
                        f"Enhanced device tracking error for {username}: {str(tracking_error)} (method: {access_method})"
                    )
                    # Fallback to original device tracking method
                    device, created = Device.objects.get_or_create(
                        user=user,
                        mac_address=mac_address,
                        defaults={
                            "ip_address": ip_address,
                            "is_active": True,
                            "device_name": f"Device-{mac_address[-8:]}",  # Use last 8 chars of MAC
                            "first_seen": timezone.now(),
                        },
                    )

                    if created:
                        # New device - check if limit exceeded
                        active_devices = user.get_active_devices().count()
                        if active_devices > user.max_devices:
                            has_access = False
                            denial_reason = (
                                f"Device limit reached ({user.max_devices} devices max)"
                            )
                            device.is_active = False
                            device.save()
                            logger.warning(
                                f"Device limit exceeded for {username}: {active_devices}/{user.max_devices} (method: {access_method})"
                            )
                        else:
                            logger.info(
                                f"New device registered for {username}: {mac_address} -> {ip_address} ({active_devices}/{user.max_devices}, method: {access_method})"
                            )
                    else:
                        # Update existing device with current session info
                        device.ip_address = ip_address
                        device.is_active = True
                        device.last_seen = timezone.now()
                        device.save()
                        logger.info(
                            f"Device activity tracked for {username}: {mac_address} -> {ip_address} (method: {access_method})"
                        )
            else:
                # No MAC address provided - still allow access but log it
                logger.warning(
                    f"Authentication request for {username} without MAC address - allowing access (method: {access_method})"
                )

        # Log access attempt with enhanced information
        try:
            AccessLog.objects.create(
                user=user,
                device=device,
                ip_address=ip_address or "127.0.0.1",
                mac_address=mac_address,
                access_granted=has_access,
                denial_reason=denial_reason,
            )
        except Exception as log_error:
            logger.error(f"Access log error for {username}: {str(log_error)}")

        # Update user status if expired (deactivate if no valid access)
        if (
            not has_access
            and user.is_active
            and not denial_reason.startswith("Device limit")
        ):
            user.deactivate_access()
            logger.info(
                f"User {username} deactivated due to expired access (method was: {access_method})"
            )

        # Return appropriate response based on caller type
        # Fix device count calculation - ensure we get the actual count
        try:
            device_count = user.get_active_devices().count()
            # If no devices yet, try to count all devices for this user
            if device_count == 0:
                device_count = user.devices.filter(is_active=True).count()
        except Exception as device_count_error:
            logger.warning(
                f"Error getting device count for {username}: {str(device_count_error)}"
            )
            device_count = 0

        max_devices = getattr(user, "max_devices", 3) or 3

        if has_access:
            logger.info(
                f"MikroTik auth SUCCESS for {username}: Access granted (method: {access_method}, devices: {device_count}/{max_devices})"
            )

            if is_frontend_call:
                return JsonResponse(
                    {
                        "auth-state": 1,
                        "success": True,
                        "message": "Authentication successful",
                        "user": username,
                        "device_count": device_count,
                        "max_devices": max_devices,
                        "access_type": access_method,
                        "device_info": {
                            "current_device": (
                                {
                                    "mac": mac_address,
                                    "ip": ip_address,
                                    "registered": device is not None,
                                }
                                if mac_address
                                else None
                            )
                        },
                    }
                )
            else:
                return HttpResponse("OK", status=200)
        else:
            logger.warning(
                f"Mikrotik auth DENIED for {username}: {denial_reason} (method: {access_method}, devices: {device_count}/{max_devices})"
            )

            if is_frontend_call:
                return JsonResponse(
                    {
                        "error": denial_reason,
                        "auth-state": 0,
                        "success": False,
                        "message": denial_reason,
                        "device_count": device_count,
                        "max_devices": max_devices,
                        "access_type": access_method,
                    },
                    status=403,
                )
            else:
                return HttpResponse(denial_reason, status=403)

    except User.DoesNotExist:
        logger.warning(
            f"Mikrotik auth failed for {username}: User not found - no payment or voucher history"
        )
        error_msg = "User not found - please make payment or redeem voucher"

        if is_frontend_call:
            return JsonResponse(
                {
                    "error": error_msg,
                    "auth-state": 0,
                    "success": False,
                    "message": error_msg,
                },
                status=404,
            )
        else:
            return HttpResponse(error_msg, status=403)

    except Exception as e:
        logger.error(f"Error in Mikrotik authentication for {username}: {str(e)}")
        error_msg = "Authentication error"

        if is_frontend_call:
            return JsonResponse(
                {
                    "error": error_msg,
                    "auth-state": 0,
                    "success": False,
                    "message": str(e),
                },
                status=500,
            )
        else:
            return HttpResponse(error_msg, status=500)


@csrf_exempt
def mikrotik_logout(request):
    """
    Mikrotik hotspot logout endpoint

    Handles both form data and JSON data from MikroTik routers
    Fixed to handle frontend API calls properly
    """
    # Detect if this is a frontend API call
    is_frontend_call = (
        request.content_type == "application/json"
        or "application/json" in request.META.get("HTTP_ACCEPT", "")
        or request.META.get("HTTP_USER_AGENT", "").startswith("Mozilla/")
    )

    username = None
    ip_address = ""

    if request.method == "POST":
        # Try JSON first (for frontend API calls)
        try:
            if request.content_type == "application/json":
                json_data = json.loads(request.body.decode("utf-8"))
                username = json_data.get("username") or json_data.get("phone_number")
                ip_address = json_data.get("ip") or json_data.get("ip_address", "")
            else:
                # Try form data (for MikroTik router calls)
                username = request.POST.get("username")
                ip_address = request.POST.get("ip", "")

                # If not found in form data, try JSON anyway
                if not username:
                    json_data = json.loads(request.body.decode("utf-8"))
                    username = json_data.get("username") or json_data.get(
                        "phone_number"
                    )
                    ip_address = json_data.get("ip") or json_data.get("ip_address", "")
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            # Fallback to form data
            username = request.POST.get("username")
            ip_address = request.POST.get("ip", "")
    else:
        # GET request
        username = request.GET.get("username")
        ip_address = request.GET.get("ip", "")

    logger.info(
        f"Mikrotik logout request: method={request.method}, username={username}, ip={ip_address}, frontend={is_frontend_call}"
    )

    if not username:
        error_msg = "No username provided"
        if is_frontend_call:
            return JsonResponse(
                {"error": error_msg, "success": False, "message": error_msg}, status=400
            )
        return HttpResponse(error_msg, status=400)

    try:
        # Log the logout
        user = User.objects.get(phone_number=username)

        # Create access log for logout
        try:
            AccessLog.objects.create(
                user=user,
                ip_address=ip_address or "127.0.0.1",
                mac_address="",
                access_granted=False,
                denial_reason="Mikrotik logout",
            )
        except Exception as log_error:
            logger.error(
                f"Access log error during logout for {username}: {str(log_error)}"
            )

        logger.info(f"Mikrotik logout successful for {username}")

        if is_frontend_call:
            return JsonResponse(
                {"success": True, "message": "Logout successful", "user": username}
            )
        else:
            return HttpResponse("OK", status=200)

    except User.DoesNotExist:
        # User not found but still return OK for MikroTik compatibility
        logger.info(f"Mikrotik logout for unknown user {username}")

        if is_frontend_call:
            return JsonResponse(
                {
                    "success": True,
                    "message": "Logout completed",
                    "warning": "User not found",
                }
            )
        else:
            return HttpResponse("OK", status=200)

    except Exception as e:
        logger.error(f"Error in Mikrotik logout for {username}: {str(e)}")
        error_msg = "Logout error"

        if is_frontend_call:
            return JsonResponse(
                {"error": error_msg, "success": False, "message": str(e)}, status=500
            )
        else:
            return HttpResponse(error_msg, status=500)


@api_view(["GET"])
@permission_classes([SimpleAdminTokenPermission])
def mikrotik_status_check(request):
    """
    Check MikroTik router status (Admin only)
    """
    try:
        from .mikrotik import test_mikrotik_connection

        # Get router configuration from settings (using correct variable names)
        router_ip = settings.MIKROTIK_HOST
        router_port = settings.MIKROTIK_PORT
        router_user = settings.MIKROTIK_USER

        # Get active users count
        active_users_count = User.objects.filter(
            paid_until__gt=timezone.now(), is_active=True
        ).count()

        # Test connection to router using the mikrotik module function
        connection_test = test_mikrotik_connection()
        connection_status = (
            "connected" if connection_test.get("success") else "disconnected"
        )

        return Response(
            {
                "success": True,
                "router_ip": router_ip,
                "router_port": router_port,
                "connection_status": connection_status,
                "connection_details": connection_test,
                "active_users": active_users_count,
                "admin_user": router_user,
                "timestamp": timezone.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"MikroTik status check failed: {str(e)}")
        return Response(
            {
                "success": False,
                "message": f"Failed to check router status: {str(e)}",
                "router_ip": getattr(settings, "MIKROTIK_HOST", "Not configured"),
                "error": str(e),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@csrf_exempt
def mikrotik_user_status(request):
    """
    Check the status of a specific user on MikroTik hotspot

    Can be used both for internal checking and by MikroTik router for user validation
    Accepts username via GET parameter, POST form data, or JSON
    """
    try:
        # Get username from different sources
        username = None

        if request.method == "GET":
            username = request.GET.get("username")
        elif request.method == "POST":
            # Try form data first (MikroTik format)
            username = request.POST.get("username")

            # If not found, try JSON
            if not username:
                try:
                    json_data = json.loads(request.body.decode("utf-8"))
                    username = json_data.get("username")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass

        if not username:
            return JsonResponse(
                {"success": False, "message": "Username is required"}, status=400
            )

        # Check if user exists in our database
        try:
            user = User.objects.get(phone_number=username)
        except User.DoesNotExist:
            # Check if it's a voucher
            try:
                voucher = Voucher.objects.get(code=username)
                return JsonResponse(
                    {
                        "success": True,
                        "user_type": "voucher",
                        "username": username,
                        "is_active": not voucher.is_used,
                        "status": "valid" if not voucher.is_used else "invalid",
                        "voucher_info": {
                            "code": voucher.code,
                            "duration_hours": voucher.duration_hours,
                            "is_used": voucher.is_used,
                            "used_at": (
                                voucher.used_at.isoformat() if voucher.used_at else None
                            ),
                            "created_at": voucher.created_at.isoformat(),
                            "batch_id": voucher.batch_id,
                        },
                    }
                )
            except Voucher.DoesNotExist:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "User not found",
                        "username": username,
                        "user_type": "unknown",
                    },
                    status=404,
                )

        # User found - check their status
        has_active_access = user.has_active_access()

        # Get device information
        devices = user.devices.all()
        device_info = []
        for device in devices:
            device_info.append(
                {
                    "mac_address": device.mac_address,
                    "first_seen": device.first_seen.isoformat(),
                    "last_seen": device.last_seen.isoformat(),
                    "is_active": device.is_active,
                }
            )

        # Get payment information
        latest_payment = (
            user.payments.filter(status="completed").order_by("-created_at").first()
        )
        payment_info = None
        if latest_payment:
            payment_info = {
                "bundle_name": latest_payment.bundle.name,
                "amount": str(latest_payment.amount),
                "paid_at": latest_payment.created_at.isoformat(),
                "expires_at": user.paid_until.isoformat() if user.paid_until else None,
            }

        # Try to get MikroTik active session info
        mikrotik_session = None
        try:
            from .mikrotik import get_active_hotspot_users

            active_users_result = get_active_hotspot_users()
            if active_users_result["success"]:
                for active_user in active_users_result["data"]:
                    if active_user.get("user") == username:
                        mikrotik_session = {
                            "session_id": active_user.get("id"),
                            "ip_address": active_user.get("address"),
                            "mac_address": active_user.get("mac-address"),
                            "session_time": active_user.get("session-time"),
                            "bytes_in": active_user.get("bytes-in"),
                            "bytes_out": active_user.get("bytes-out"),
                            "packets_in": active_user.get("packets-in"),
                            "packets_out": active_user.get("packets-out"),
                        }
                        break
        except Exception as e:
            logger.warning(
                f"Could not get MikroTik session info for {username}: {str(e)}"
            )

        return JsonResponse(
            {
                "success": True,
                "user_type": "payment_user",
                "username": username,
                "is_active": user.is_active,
                "has_active_access": has_active_access,
                "status": "active" if has_active_access else "inactive",
                "user_info": {
                    "user_id": user.id,
                    "phone_number": user.phone_number,
                    "is_active": user.is_active,
                    "paid_until": (
                        user.paid_until.isoformat() if user.paid_until else None
                    ),
                    "created_at": user.created_at.isoformat(),
                    "device_count": len(device_info),
                },
                "devices": device_info,
                "payment_info": payment_info,
                "mikrotik_session": mikrotik_session,
                "timestamp": timezone.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"MikroTik user status check failed for {username}: {str(e)}")
        return JsonResponse(
            {
                "success": False,
                "message": f"Failed to check user status: {str(e)}",
                "username": username if "username" in locals() else None,
                "error": str(e),
            },
            status=500,
        )


@api_view(["POST"])
@permission_classes([SimpleAdminTokenPermission])
def force_user_logout(request):
    """
    Force logout a user from all devices (Admin only)
    """
    phone_number = request.data.get("phone_number")

    if not phone_number:
        return Response(
            {"success": False, "message": "Phone number is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.get(phone_number=phone_number)

        # Logout from Mikrotik
        mikrotik_result = logout_user_from_mikrotik(phone_number)

        # Deactivate all user devices
        user.devices.update(is_active=False)

        # Log the forced logout with proper IP extraction
        request_info = get_request_info(request)
        AccessLog.objects.create(
            user=user,
            ip_address=request_info["ip_address"],
            mac_address="ADMIN_ACTION",
            access_granted=False,
            denial_reason="Admin forced logout",
        )

        return Response(
            {
                "success": True,
                "message": f"User {phone_number} forcibly logged out",
                "mikrotik_result": mikrotik_result,
            }
        )

    except User.DoesNotExist:
        return Response(
            {"success": False, "message": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Error in force logout: {str(e)}")
        return Response(
            {"success": False, "message": "Force logout error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def test_voucher_access(request):
    """
    Test endpoint specifically for voucher users to verify their access and MikroTik integration
    This helps debug voucher-related access issues
    """
    phone_number = request.data.get("phone_number")
    mac_address = request.data.get("mac_address", "")

    # Extract comprehensive request information
    request_info = get_request_info(request, request.data)
    ip_address = request_info["ip_address"]
    mac_address = request_info["mac_address"] or mac_address
    user_agent = request_info["user_agent"]

    if not phone_number:
        return Response(
            {
                "success": False,
                "message": "Phone number is required",
                "usage": {
                    "POST": '{"phone_number": "255123456789", "mac_address": "AA:BB:CC:DD:EE:FF", "ip_address": "192.168.1.100"}'
                },
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.get(phone_number=phone_number)
        now = timezone.now()

        # Check if user has voucher history
        vouchers = user.vouchers_used.filter(is_used=True).order_by("-used_at")
        if not vouchers.exists():
            return Response(
                {
                    "success": False,
                    "message": "User has no voucher history",
                    "suggestion": "User needs to redeem a voucher first",
                    "user_info": {
                        "phone_number": phone_number,
                        "has_payments": user.payments.filter(
                            status="completed"
                        ).exists(),
                        "has_vouchers": False,
                    },
                }
            )

        # Test core access
        has_access = user.has_active_access()
        last_voucher = vouchers.first()

        # Test verify_access endpoint behavior
        verify_access_simulation = {
            "would_grant_access": has_access,
            "denial_reason": (
                "None" if has_access else "Access expired or no valid voucher"
            ),
            "user_is_active": user.is_active,
            "paid_until": user.paid_until.isoformat() if user.paid_until else None,
        }

        # Test MikroTik authentication behavior
        mikrotik_auth_simulation = {
            "would_authenticate": has_access,
            "http_status_expected": 200 if has_access else 403,
            "response_expected": (
                "Authentication success"
                if has_access
                else "Access denied - payment or voucher required"
            ),
        }

        # Device management test
        device_info = {}
        if mac_address:
            try:
                device = Device.objects.get(user=user, mac_address=mac_address)
                device_info = {
                    "device_exists": True,
                    "device_active": device.is_active,
                    "device_id": device.id,
                    "last_seen": device.last_seen.isoformat(),
                }
            except Device.DoesNotExist:
                device_info = {
                    "device_exists": False,
                    "would_create_device": user.get_active_devices().count()
                    < user.max_devices,
                    "current_device_count": user.get_active_devices().count(),
                    "max_devices": user.max_devices,
                }

        # Access logs for this user
        recent_logs = AccessLog.objects.filter(user=user).order_by("-timestamp")[:3]

        return Response(
            {
                "success": True,
                "voucher_access_test": {
                    "user_info": {
                        "phone_number": phone_number,
                        "created_at": user.created_at.isoformat(),
                        "is_active": user.is_active,
                        "max_devices": user.max_devices,
                    },
                    "voucher_info": {
                        "total_vouchers_redeemed": vouchers.count(),
                        "last_voucher": (
                            {
                                "code": last_voucher.code,
                                "duration_hours": last_voucher.duration_hours,
                                "used_at": last_voucher.used_at.isoformat(),
                                "batch_id": last_voucher.batch_id,
                            }
                            if last_voucher
                            else None
                        ),
                        "all_vouchers": [
                            {
                                "code": v.code,
                                "duration_hours": v.duration_hours,
                                "used_at": v.used_at.isoformat() if v.used_at else None,
                            }
                            for v in vouchers[:5]
                        ],
                    },
                    "access_status": {
                        "has_active_access": has_access,
                        "paid_until": (
                            user.paid_until.isoformat() if user.paid_until else None
                        ),
                        "time_remaining_hours": (
                            round((user.paid_until - now).total_seconds() / 3600, 1)
                            if user.paid_until and has_access
                            else 0
                        ),
                        "access_method": "voucher",
                    },
                    "api_simulation": {
                        "verify_access_endpoint": verify_access_simulation,
                        "mikrotik_auth_endpoint": mikrotik_auth_simulation,
                    },
                    "device_management": device_info,
                    "recent_access_logs": [
                        {
                            "timestamp": log.timestamp.isoformat(),
                            "access_granted": log.access_granted,
                            "denial_reason": log.denial_reason or "Access granted",
                            "mac_address": log.mac_address,
                        }
                        for log in recent_logs
                    ],
                    "recommendations": [
                        (
                            "User has valid voucher access - should be able to connect to WiFi"
                            if has_access
                            else "Voucher access has expired - user needs to redeem a new voucher"
                        ),
                        (
                            f"Last voucher was used {(now - last_voucher.used_at).days} days ago"
                            if last_voucher and last_voucher.used_at
                            else "No recent voucher usage"
                        ),
                        (
                            f"User can connect {user.max_devices - user.get_active_devices().count()} more devices"
                            if user.get_active_devices().count() < user.max_devices
                            else "User has reached device limit"
                        ),
                    ],
                },
            }
        )

    except User.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": f"User {phone_number} not found",
                "suggestion": "User needs to redeem a voucher first to create an account",
            },
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Test voucher access error: {str(e)}")
        return Response(
            {"success": False, "message": f"Test error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def trigger_device_authentication(request):
    """
    Manually trigger MikroTik authentication for a user's device
    This can be called after payment to activate internet access
    """
    phone_number = request.data.get("phone_number")
    mac_address = request.data.get("mac_address", "")

    # Extract comprehensive request information
    request_info = get_request_info(request, request.data)
    ip_address = request_info["ip_address"]
    mac_address = request_info["mac_address"] or mac_address
    user_agent = request_info["user_agent"]

    if not phone_number:
        return Response(
            {"success": False, "message": "Phone number is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Check if user exists and has valid access
        user = User.objects.get(phone_number=phone_number)

        if not user.has_active_access():
            return Response(
                {
                    "success": False,
                    "message": "User does not have active access. Please make payment or redeem voucher first.",
                    "user_status": {
                        "has_access": False,
                        "paid_until": (
                            user.paid_until.isoformat() if user.paid_until else None
                        ),
                        "is_active": user.is_active,
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Register/update device if MAC address provided
        device = None
        if mac_address:
            device, created = Device.objects.get_or_create(
                user=user,
                mac_address=mac_address,
                defaults={"ip_address": ip_address, "is_active": True},
            )

            if not created:
                device.ip_address = ip_address
                device.is_active = True
                device.save()

        # Try MikroTik authentication
        mikrotik_result = None
        try:
            from .mikrotik import authenticate_user_with_mikrotik

            mikrotik_result = authenticate_user_with_mikrotik(
                phone_number=phone_number,
                mac_address=mac_address,
                ip_address=ip_address,
            )
        except Exception as e:
            logger.error(f"MikroTik authentication error for {phone_number}: {str(e)}")
            mikrotik_result = {"success": False, "error": str(e)}

        # Log the attempt
        AccessLog.objects.create(
            user=user,
            device=device,
            ip_address=ip_address or "127.0.0.1",
            mac_address=mac_address,
            access_granted=True,
            denial_reason=f'Manual authentication trigger - MikroTik result: {mikrotik_result.get("success", False)}',
        )

        response_data = {
            "success": True,
            "message": "Authentication triggered successfully",
            "user_status": {
                "phone_number": phone_number,
                "has_access": user.has_active_access(),
                "paid_until": user.paid_until.isoformat() if user.paid_until else None,
                "is_active": user.is_active,
            },
            "device_info": {
                "mac_address": mac_address,
                "ip_address": ip_address,
                "device_registered": device is not None,
            },
            "mikrotik_result": mikrotik_result,
            "instructions": [
                "Your device authentication has been triggered.",
                "If you still cannot access internet:",
                "1. Disconnect from WiFi and reconnect",
                "2. Open a web browser and try to visit any website",
                "3. You should automatically get internet access",
                "4. If problems persist, contact support",
            ],
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except User.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "User not found. Please make payment or redeem voucher first.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Error in manual authentication trigger: {str(e)}")
        return Response(
            {
                "success": False,
                "message": "Authentication trigger failed due to system error",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# =============================================================================
# SAAS SUBSCRIPTION API ENDPOINTS
# =============================================================================


@api_view(["GET"])
@permission_classes([AllowAny])
def list_subscription_plans(request):
    """
    List all available subscription plans
    Public endpoint for pricing page
    """
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by("display_order")
    serializer = SubscriptionPlanSerializer(plans, many=True)
    return Response(
        {
            "success": True,
            "plans": serializer.data,
            "currency": "TZS",
            "payment_methods": ["M-Pesa", "Tigo Pesa", "Airtel Money", "Bank Transfer"],
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def register_tenant(request):
    """
    Register a new tenant (hotspot business)
    Step 1: Create account and send OTP for email verification
    """
    serializer = TenantRegistrationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data

    try:
        # Create Django user for tenant owner
        from django.contrib.auth.models import User as DjangoUser
        from .models import EmailOTP
        from .email_utils import send_otp_email
        import re

        # Generate slug from business name if not provided
        slug = data.get("slug")
        if not slug:
            slug = re.sub(
                r"[^a-z0-9]", "", data["business_name"].lower().replace(" ", "-")
            )[:50]
            # Ensure unique slug
            base_slug = slug
            counter = 1
            while Tenant.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

        # Create admin user (inactive until email verified)
        admin_user = DjangoUser.objects.create_user(
            username=data["admin_email"],
            email=data["admin_email"],
            password=data["admin_password"],
            first_name=data.get("admin_first_name", ""),
            last_name=data.get("admin_last_name", ""),
            is_active=False,  # Inactive until email verified
        )

        # Get subscription plan (default to Starter if none specified)
        plan = None
        if data.get("plan_id"):
            try:
                plan = SubscriptionPlan.objects.get(id=data["plan_id"], is_active=True)
            except SubscriptionPlan.DoesNotExist:
                pass

        if not plan:
            plan = SubscriptionPlan.objects.filter(
                name="starter", is_active=True
            ).first()

        # Create tenant (email not verified yet)
        tenant = Tenant.objects.create(
            slug=slug,
            business_name=data["business_name"],
            business_email=data["business_email"],
            business_phone=data["business_phone"],
            business_address=data.get("business_address", ""),
            owner=admin_user,
            subscription_plan=plan,
            subscription_status="trial",
            email_verified=False,  # Will be set to True after OTP verification
        )

        # Create owner staff entry
        TenantStaff.objects.create(
            tenant=tenant,
            user=admin_user,
            role="owner",
            can_manage_routers=True,
            can_manage_users=True,
            can_manage_payments=True,
            can_manage_vouchers=True,
            can_view_reports=True,
            can_manage_staff=True,
            can_manage_settings=True,
            is_active=True,
            joined_at=timezone.now(),
        )

        # Create and send OTP for email verification
        otp = EmailOTP.create_for_email(
            email=data["admin_email"], purpose="registration", tenant=tenant
        )

        # Send OTP email
        email_sent = send_otp_email(
            email=data["admin_email"],
            otp_code=otp.otp_code,
            purpose="registration",
            tenant_name=tenant.business_name,
        )

        if not email_sent:
            logger.warning(
                f"Failed to send OTP email for registration: {data['admin_email']}"
            )

        return Response(
            {
                "success": True,
                "message": "Registration successful! Please check your email for the verification code.",
                "email": data["admin_email"],
                "tenant_id": str(tenant.id),
                "requires_verification": True,
                "next_step": "verify_email",
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        logger.error(f"Tenant registration failed: {e}")
        # Clean up if tenant was partially created
        try:
            if "admin_user" in locals() and admin_user.pk:
                admin_user.delete()
        except:
            pass
        return Response(
            {"success": False, "message": "Registration failed. Please try again."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_email_otp(request):
    """
    Verify email OTP after registration
    Step 2: Complete registration by verifying email
    """
    from .models import EmailOTP
    from .email_utils import send_welcome_email
    from .serializers import EmailOTPVerifySerializer

    serializer = EmailOTPVerifySerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    email = serializer.validated_data["email"]
    otp_code = serializer.validated_data["otp_code"]

    # Find the OTP
    try:
        otp = EmailOTP.objects.filter(
            email=email, purpose="registration", is_used=False
        ).latest("created_at")
    except EmailOTP.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "No pending verification found. Please register again.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # Verify OTP
    is_valid, message = otp.verify(otp_code)

    if not is_valid:
        return Response(
            {"success": False, "message": message}, status=status.HTTP_400_BAD_REQUEST
        )

    # OTP verified - activate the tenant and user
    try:
        tenant = otp.tenant
        if not tenant:
            return Response(
                {"success": False, "message": "Tenant not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Activate tenant email
        tenant.email_verified = True
        tenant.email_verified_at = timezone.now()
        tenant.save(update_fields=["email_verified", "email_verified_at"])

        # Activate Django user
        admin_user = tenant.owner
        admin_user.is_active = True
        admin_user.save(update_fields=["is_active"])

        # Send welcome SMS
        try:
            from .nextsms import NextSMSAPI

            sms_client = NextSMSAPI()
            sms_message = (
                f"Welcome to Kitonga!\n"
                f"Your business: {tenant.business_name}\n"
                f"Trial ends: {tenant.trial_ends_at.strftime('%d/%m/%Y') if tenant.trial_ends_at else '14 days'}\n"
                f"Login: https://app.kitonga.com"
            )
            sms_client.send_sms(tenant.business_phone, sms_message)
        except Exception as e:
            logger.warning(f"Failed to send welcome SMS: {e}")

        # Send welcome email
        try:
            send_welcome_email(
                email=admin_user.email,
                business_name=tenant.business_name,
                trial_ends_at=(
                    tenant.trial_ends_at.strftime("%B %d, %Y")
                    if tenant.trial_ends_at
                    else "14 days"
                ),
                api_key_preview=tenant.api_key[:16],
            )
        except Exception as e:
            logger.warning(f"Failed to send welcome email: {e}")

        return Response(
            {
                "success": True,
                "message": "Email verified successfully! Your 14-day trial has started.",
                "tenant": {
                    "id": str(tenant.id),
                    "slug": tenant.slug,
                    "business_name": tenant.business_name,
                    "api_key": tenant.api_key,
                    "trial_ends_at": (
                        tenant.trial_ends_at.isoformat()
                        if tenant.trial_ends_at
                        else None
                    ),
                },
                "admin": {
                    "email": admin_user.email,
                },
                "next_steps": [
                    "Log in to your dashboard",
                    "Add your first MikroTik router",
                    "Create WiFi bundles/packages",
                    "Generate vouchers or enable payments",
                ],
            }
        )

    except Exception as e:
        logger.error(f"Email verification failed: {e}")
        return Response(
            {"success": False, "message": "Verification failed. Please try again."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def resend_otp(request):
    """
    Resend OTP for email verification
    """
    from .models import EmailOTP
    from .email_utils import send_otp_email
    from .serializers import ResendOTPSerializer

    serializer = ResendOTPSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    email = serializer.validated_data["email"]
    purpose = serializer.validated_data.get("purpose", "registration")

    # Find tenant by email
    tenant = None
    try:
        from django.contrib.auth.models import User as DjangoUser

        user = DjangoUser.objects.get(email=email)
        tenant = Tenant.objects.filter(owner=user).first()
    except DjangoUser.DoesNotExist:
        pass

    # Rate limiting: Check if OTP was sent in the last 60 seconds
    recent_otp = EmailOTP.objects.filter(
        email=email,
        purpose=purpose,
        created_at__gte=timezone.now() - timedelta(seconds=60),
    ).exists()

    if recent_otp:
        return Response(
            {
                "success": False,
                "message": "Please wait 60 seconds before requesting a new code.",
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # Create new OTP
    otp = EmailOTP.create_for_email(email=email, purpose=purpose, tenant=tenant)

    # Send OTP email
    email_sent = send_otp_email(
        email=email,
        otp_code=otp.otp_code,
        purpose=purpose,
        tenant_name=tenant.business_name if tenant else None,
    )

    if email_sent:
        return Response(
            {"success": True, "message": "Verification code sent! Check your email."}
        )
    else:
        return Response(
            {"success": False, "message": "Failed to send email. Please try again."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def tenant_login(request):
    """
    Login endpoint for tenant owners/staff
    Returns API key and tenant info on successful login
    """
    from django.contrib.auth import authenticate
    from .serializers import TenantLoginSerializer

    serializer = TenantLoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    email = serializer.validated_data["email"]
    password = serializer.validated_data["password"]

    # Authenticate user
    user = authenticate(username=email, password=password)

    if not user:
        return Response(
            {"success": False, "message": "Invalid email or password."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        # Check if email needs verification
        tenant = Tenant.objects.filter(owner=user).first()
        if tenant and not tenant.email_verified:
            return Response(
                {
                    "success": False,
                    "message": "Please verify your email first.",
                    "requires_verification": True,
                    "email": email,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(
            {"success": False, "message": "Account is inactive. Contact support."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Find tenant for this user
    tenant = Tenant.objects.filter(owner=user).first()
    staff_entry = None

    if not tenant:
        # Check if user is staff of a tenant
        staff_entry = TenantStaff.objects.filter(user=user, is_active=True).first()
        if staff_entry:
            tenant = staff_entry.tenant

    if not tenant:
        return Response(
            {"success": False, "message": "No tenant account found for this user."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Check tenant subscription status
    if not tenant.is_subscription_valid():
        if tenant.subscription_status == "suspended":
            return Response(
                {
                    "success": False,
                    "message": "Your account is suspended. Please contact support.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        elif tenant.subscription_status == "cancelled":
            return Response(
                {"success": False, "message": "Your subscription has been cancelled."},
                status=status.HTTP_403_FORBIDDEN,
            )

    # Determine role and permissions
    role = "owner"
    permissions = {}

    if staff_entry:
        role = staff_entry.role
        permissions = {
            "can_manage_routers": staff_entry.can_manage_routers,
            "can_manage_users": staff_entry.can_manage_users,
            "can_manage_payments": staff_entry.can_manage_payments,
            "can_manage_vouchers": staff_entry.can_manage_vouchers,
            "can_view_reports": staff_entry.can_view_reports,
            "can_manage_staff": staff_entry.can_manage_staff,
            "can_manage_settings": staff_entry.can_manage_settings,
        }
    else:
        # Owner has all permissions
        permissions = {
            "can_manage_routers": True,
            "can_manage_users": True,
            "can_manage_payments": True,
            "can_manage_vouchers": True,
            "can_view_reports": True,
            "can_manage_staff": True,
            "can_manage_settings": True,
        }

    return Response(
        {
            "success": True,
            "message": "Login successful!",
            "user": {
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": role,
                "permissions": permissions,
            },
            "tenant": {
                "id": str(tenant.id),
                "slug": tenant.slug,
                "business_name": tenant.business_name,
                "api_key": tenant.api_key,
                "subscription_status": tenant.subscription_status,
                "subscription_plan": (
                    tenant.subscription_plan.display_name
                    if tenant.subscription_plan
                    else None
                ),
                "subscription_ends_at": (
                    tenant.subscription_ends_at.isoformat()
                    if tenant.subscription_ends_at
                    else None
                ),
                "trial_ends_at": (
                    tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None
                ),
            },
        }
    )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def tenant_logout(request):
    """
    Logout endpoint for tenant owners/staff
    Optionally regenerates API key to invalidate all sessions

    Request Body:
    {
        "invalidate_api_key": false  # Optional: if true, regenerates API key
    }
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    invalidate_api_key = request.data.get("invalidate_api_key", False)

    if invalidate_api_key:
        # Regenerate API key to invalidate all sessions using this key
        import secrets

        tenant.api_key = secrets.token_hex(32)
        tenant.save()

        logger.info(f"Tenant {tenant.slug} logged out and invalidated API key")

        return Response(
            {
                "success": True,
                "message": "Logged out successfully. API key has been invalidated.",
                "api_key_invalidated": True,
            }
        )

    logger.info(f"Tenant {tenant.slug} logged out")

    return Response(
        {
            "success": True,
            "message": "Logged out successfully.",
            "api_key_invalidated": False,
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def tenant_password_reset_request(request):
    """
    Request password reset - sends OTP to email
    """
    from .models import EmailOTP
    from .email_utils import send_otp_email
    from .serializers import TenantPasswordResetRequestSerializer
    from django.contrib.auth.models import User as DjangoUser

    serializer = TenantPasswordResetRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    email = serializer.validated_data["email"]

    # Check if user exists (don't reveal if they do or not for security)
    try:
        user = DjangoUser.objects.get(email=email)
        tenant = Tenant.objects.filter(owner=user).first()

        # Create OTP
        otp = EmailOTP.create_for_email(
            email=email, purpose="password_reset", tenant=tenant
        )

        # Send OTP email
        send_otp_email(email=email, otp_code=otp.otp_code, purpose="password_reset")
    except DjangoUser.DoesNotExist:
        pass  # Don't reveal if user exists

    # Always return success to prevent email enumeration
    return Response(
        {
            "success": True,
            "message": "If an account exists with this email, you will receive a password reset code.",
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def tenant_password_reset_confirm(request):
    """
    Confirm password reset with OTP and new password
    """
    from .models import EmailOTP
    from .email_utils import send_password_reset_success_email
    from .serializers import TenantPasswordResetConfirmSerializer
    from django.contrib.auth.models import User as DjangoUser

    serializer = TenantPasswordResetConfirmSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    email = serializer.validated_data["email"]
    otp_code = serializer.validated_data["otp_code"]
    new_password = serializer.validated_data["new_password"]

    # Find the OTP
    try:
        otp = EmailOTP.objects.filter(
            email=email, purpose="password_reset", is_used=False
        ).latest("created_at")
    except EmailOTP.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "No pending password reset found. Please request a new code.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # Verify OTP
    is_valid, message = otp.verify(otp_code)

    if not is_valid:
        return Response(
            {"success": False, "message": message}, status=status.HTTP_400_BAD_REQUEST
        )

    # Update password
    try:
        user = DjangoUser.objects.get(email=email)
        user.set_password(new_password)
        user.save()

        # Send confirmation email
        send_password_reset_success_email(email)

        return Response(
            {
                "success": True,
                "message": "Password reset successful! You can now log in with your new password.",
            }
        )

    except DjangoUser.DoesNotExist:
        return Response(
            {"success": False, "message": "User not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Password reset failed: {e}")
        return Response(
            {"success": False, "message": "Password reset failed. Please try again."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def tenant_dashboard(request):
    """
    Get tenant dashboard data including subscription status, usage, and stats
    Requires tenant API key or authenticated staff user
    """
    # Get tenant from request (set by middleware)
    tenant = getattr(request, "tenant", None)

    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found. Use X-API-Key header."},
            status=status.HTTP_403_FORBIDDEN,
        )

    from .subscription import SubscriptionManager, UsageMeter, RevenueCalculator

    subscription_mgr = SubscriptionManager(tenant)
    usage_meter = UsageMeter(tenant)
    revenue_calc = RevenueCalculator(tenant)

    # Get subscription status
    subscription_status = subscription_mgr.check_subscription_status()

    # Get usage summary
    usage_summary = usage_meter.get_usage_summary()

    # Get revenue for current month
    revenue_report = revenue_calc.get_monthly_revenue_report()

    # Check for renewal reminders
    renewal_reminder = subscription_mgr.get_renewal_reminder()

    return Response(
        {
            "success": True,
            "tenant": TenantSerializer(tenant).data,
            "subscription": subscription_status,
            "usage": usage_summary,
            "revenue_this_month": revenue_report,
            "renewal_reminder": renewal_reminder,
            "quick_stats": {
                "total_wifi_users": tenant.wifi_users.count(),
                "active_wifi_users": tenant.wifi_users.filter(is_active=True).count(),
                "total_payments_today": Payment.objects.filter(
                    tenant=tenant,
                    status="completed",
                    completed_at__date=timezone.now().date(),
                ).count(),
                "revenue_today": float(
                    Payment.objects.filter(
                        tenant=tenant,
                        status="completed",
                        completed_at__date=timezone.now().date(),
                    ).aggregate(total=Sum("amount"))["total"]
                    or 0
                ),
            },
        }
    )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def tenant_usage(request):
    """
    Get detailed usage stats for the tenant
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    from .subscription import UsageMeter

    meter = UsageMeter(tenant)
    usage = meter.get_usage_summary()

    return Response(
        {
            "success": True,
            "usage": usage,
            "plan": (
                tenant.subscription_plan.display_name
                if tenant.subscription_plan
                else None
            ),
        }
    )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def create_subscription_payment(request):
    """
    Create a subscription payment request for the tenant
    Returns ClickPesa checkout URL for payment
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = CreateSubscriptionPaymentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        plan = SubscriptionPlan.objects.get(
            id=serializer.validated_data["plan_id"], is_active=True
        )
    except SubscriptionPlan.DoesNotExist:
        return Response(
            {"success": False, "message": "Invalid subscription plan"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from .subscription import SubscriptionManager

    mgr = SubscriptionManager(tenant)
    result = mgr.create_subscription_payment(
        plan=plan,
        billing_cycle=serializer.validated_data.get("billing_cycle", "monthly"),
    )

    if result.get("success"):
        return Response(result)
    else:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def subscription_payment_status(request, transaction_id):
    """
    Check the status of a subscription payment
    Used by frontend to poll payment status after initiating payment
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        payment = TenantSubscriptionPayment.objects.get(
            tenant=tenant, transaction_id=transaction_id
        )

        return Response(
            {
                "success": True,
                "transaction_id": transaction_id,
                "status": payment.status,  # pending, completed, failed
                "amount": float(payment.amount),
                "currency": payment.currency,
                "plan": payment.plan.display_name if payment.plan else None,
                "billing_cycle": payment.billing_cycle,
                "created_at": payment.created_at.isoformat(),
                "completed_at": (
                    payment.completed_at.isoformat() if payment.completed_at else None
                ),
                "period_start": (
                    payment.period_start.isoformat() if payment.period_start else None
                ),
                "period_end": (
                    payment.period_end.isoformat() if payment.period_end else None
                ),
                "message": (
                    "Payment completed successfully!"
                    if payment.status == "completed"
                    else (
                        "Payment failed"
                        if payment.status == "failed"
                        else "Waiting for payment confirmation..."
                    )
                ),
            }
        )

    except TenantSubscriptionPayment.DoesNotExist:
        return Response(
            {"success": False, "message": "Payment not found"},
            status=status.HTTP_404_NOT_FOUND,
        )


@permission_classes([AllowAny])
@csrf_exempt
def subscription_payment_webhook(request):
    """
    Webhook for subscription payment callbacks from ClickPesa
    Similar to WiFi payment webhook but for subscription payments
    Creates PaymentWebhook log entries for audit trail
    """
    webhook_log = None

    try:
        data = request.data
        logger.info(f"Subscription payment webhook received: {data}")

        # Extract webhook data
        transaction_id = (
            data.get("external_reference")
            or data.get("merchant_reference")
            or data.get("order_reference")
        )
        payment_status = data.get("payment_status", "") or data.get("status", "")
        payment_reference = data.get("order_reference", "")
        channel = data.get("channel", "")
        amount = data.get("amount")

        # Convert amount to decimal if it's a string
        if amount and isinstance(amount, str):
            try:
                amount = float(amount)
            except ValueError:
                amount = None

        # Create webhook log entry for audit trail
        request_info = get_request_info(request)

        from .models import PaymentWebhook

        webhook_log = PaymentWebhook.objects.create(
            event_type=(
                "PAYMENT RECEIVED"
                if payment_status in ["PAYMENT RECEIVED", "SUCCESS", "COMPLETED"]
                else "OTHER"
            ),
            order_reference=transaction_id or "UNKNOWN",
            transaction_id=transaction_id or "",
            payment_status=payment_status or "UNKNOWN",
            channel=channel or "subscription",
            amount=amount,
            raw_payload=data,
            source_ip=request_info["ip_address"],
            user_agent=request_info["user_agent"],
        )

        if not transaction_id:
            error_msg = "Missing transaction_id in webhook data"
            logger.error(error_msg)
            webhook_log.mark_failed(error_msg)
            return Response({"error": error_msg}, status=status.HTTP_400_BAD_REQUEST)

        # Check if this is a subscription payment (starts with SUB)
        if not transaction_id.startswith("SUB"):
            logger.info(f"Not a subscription payment: {transaction_id}")
            webhook_log.mark_ignored(
                "Not a subscription payment (transaction_id does not start with SUB)"
            )
            return Response(
                {"message": "Not a subscription payment"}, status=status.HTTP_200_OK
            )

        # Find payment by transaction_id
        try:
            payment = TenantSubscriptionPayment.objects.get(
                transaction_id=transaction_id
            )
            tenant = payment.tenant
            webhook_log.tenant = tenant
            webhook_log.save()
        except TenantSubscriptionPayment.DoesNotExist:
            error_msg = f"Subscription payment not found: {transaction_id}"
            logger.error(error_msg)
            webhook_log.mark_failed(error_msg)
            return Response(
                {"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Check for duplicates
        if webhook_log.is_duplicate:
            webhook_log.mark_ignored("Duplicate webhook - already processed")
            logger.info(f"Duplicate webhook ignored: {transaction_id}")
            return Response({"success": True, "message": "Duplicate webhook ignored"})

        from .subscription import SubscriptionManager

        mgr = SubscriptionManager(tenant)
        success = mgr.process_payment_callback(
            transaction_id=transaction_id,
            status=payment_status,
            payment_reference=payment_reference,
            channel=channel,
        )

        if success:
            # Mark webhook as successfully processed
            webhook_log.mark_processed(payment=payment)
            logger.info(
                f"Subscription webhook processed successfully: {transaction_id}"
            )
            return Response(
                {"success": True, "message": "Subscription activated successfully"}
            )
        else:
            error_msg = "Payment processing failed"
            webhook_log.mark_failed(error_msg)
            return Response({"success": False, "message": error_msg})

    except Exception as e:
        logger.error(f"Subscription webhook error: {e}")
        if webhook_log:
            webhook_log.mark_failed(str(e))
        return Response(
            {"success": False, "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def tenant_subscription_history(request):
    """
    Get subscription payment history for the tenant
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    all_payments = TenantSubscriptionPayment.objects.filter(tenant=tenant)
    total_paid = float(sum(p.amount for p in all_payments.filter(status="completed")))

    payments = all_payments.order_by("-created_at")[:50]
    serializer = SubscriptionPaymentSerializer(payments, many=True)

    return Response(
        {"success": True, "payments": serializer.data, "total_paid": total_paid}
    )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def tenant_revenue_report(request):
    """
    Get WiFi payment revenue report for tenant
    Shows platform share vs tenant share
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    from .subscription import RevenueCalculator

    year = request.query_params.get("year")
    month = request.query_params.get("month")

    calc = RevenueCalculator(tenant)
    report = calc.get_monthly_revenue_report(
        year=int(year) if year else None, month=int(month) if month else None
    )

    return Response({"success": True, "report": report})


# =============================================================================
# PLATFORM ADMIN ENDPOINTS (Super Admin)
# =============================================================================


@api_view(["GET"])
@permission_classes([SimpleAdminTokenPermission])
def platform_dashboard(request):
    """
    Platform-wide dashboard for super admin
    Shows all tenants, revenue, and system status
    """
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Tenant stats
    total_tenants = Tenant.objects.count()
    active_tenants = Tenant.objects.filter(subscription_status="active").count()
    trial_tenants = Tenant.objects.filter(subscription_status="trial").count()

    # Revenue from subscription payments
    subscription_revenue = (
        TenantSubscriptionPayment.objects.filter(
            status="completed", completed_at__gte=month_start
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )

    # Revenue share from WiFi payments
    wifi_payments_total = (
        Payment.objects.filter(
            status="completed", completed_at__gte=month_start
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )

    # Calculate platform share (aggregate across all tenants)
    platform_revenue_share = 0
    for tenant in Tenant.objects.filter(subscription_plan__isnull=False):
        if tenant.subscription_plan:
            share_pct = tenant.subscription_plan.revenue_share_percentage
            tenant_payments = (
                Payment.objects.filter(
                    tenant=tenant, status="completed", completed_at__gte=month_start
                ).aggregate(total=Sum("amount"))["total"]
                or 0
            )
            platform_revenue_share += float(tenant_payments * share_pct / 100)

    # Expiring subscriptions (next 7 days)
    warning_date = now + timedelta(days=7)
    expiring_soon = Tenant.objects.filter(
        subscription_status="active",
        subscription_ends_at__lte=warning_date,
        subscription_ends_at__gt=now,
    ).count()

    return Response(
        {
            "success": True,
            "tenants": {
                "total": total_tenants,
                "active": active_tenants,
                "trial": trial_tenants,
                "expiring_soon": expiring_soon,
            },
            "revenue_this_month": {
                "subscription_payments": float(subscription_revenue),
                "wifi_payments_total": float(wifi_payments_total),
                "platform_revenue_share": round(platform_revenue_share, 2),
                "total_platform_revenue": float(subscription_revenue)
                + round(platform_revenue_share, 2),
            },
            "system": {
                "total_routers": Router.objects.filter(is_active=True).count(),
                "total_wifi_users": User.objects.count(),
                "total_payments": Payment.objects.filter(status="completed").count(),
            },
        }
    )


@api_view(["GET"])
@permission_classes([SimpleAdminTokenPermission])
def list_all_tenants(request):
    """
    List all tenants for platform admin
    """
    status_filter = request.query_params.get("status")

    queryset = Tenant.objects.select_related("subscription_plan", "owner").order_by(
        "-created_at"
    )

    if status_filter:
        queryset = queryset.filter(subscription_status=status_filter)

    # Simple pagination
    page = int(request.query_params.get("page", 1))
    per_page = int(request.query_params.get("per_page", 20))
    start = (page - 1) * per_page
    end = start + per_page

    tenants = queryset[start:end]
    total = queryset.count()

    data = []
    for tenant in tenants:
        data.append(
            {
                "id": str(tenant.id),
                "slug": tenant.slug,
                "business_name": tenant.business_name,
                "business_email": tenant.business_email,
                "subscription_plan": (
                    tenant.subscription_plan.display_name
                    if tenant.subscription_plan
                    else None
                ),
                "subscription_status": tenant.subscription_status,
                "subscription_ends_at": (
                    tenant.subscription_ends_at.isoformat()
                    if tenant.subscription_ends_at
                    else None
                ),
                "is_active": tenant.is_active,
                "created_at": tenant.created_at.isoformat(),
                "routers_count": tenant.routers.filter(is_active=True).count(),
                "wifi_users_count": tenant.wifi_users.count(),
            }
        )

    return Response(
        {
            "success": True,
            "tenants": data,
            "pagination": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": (total + per_page - 1) // per_page,
            },
        }
    )


@api_view(["GET", "PUT"])
@permission_classes([SimpleAdminTokenPermission])
def manage_tenant(request, tenant_id):
    """
    Get or update a specific tenant (platform admin)
    """
    try:
        tenant = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            {
                "success": True,
                "tenant": TenantSerializer(tenant).data,
                "subscription_payments": SubscriptionPaymentSerializer(
                    tenant.subscription_payments.order_by("-created_at")[:10], many=True
                ).data,
            }
        )

    elif request.method == "PUT":
        # Update tenant status, plan, etc.
        data = request.data

        if "subscription_status" in data:
            tenant.subscription_status = data["subscription_status"]

        if "subscription_plan_id" in data:
            try:
                plan = SubscriptionPlan.objects.get(id=data["subscription_plan_id"])
                tenant.subscription_plan = plan
            except SubscriptionPlan.DoesNotExist:
                pass

        if "subscription_ends_at" in data:
            from django.utils.dateparse import parse_datetime

            tenant.subscription_ends_at = parse_datetime(data["subscription_ends_at"])

        if "is_active" in data:
            tenant.is_active = data["is_active"]

        if "notes" in data:
            tenant.notes = data["notes"]

        tenant.save()

        return Response(
            {
                "success": True,
                "message": "Tenant updated successfully",
                "tenant": TenantSerializer(tenant).data,
            }
        )


@api_view(["GET"])
@permission_classes([SimpleAdminTokenPermission])
def platform_revenue_report(request):
    """
    Generate platform-wide revenue report
    """
    year = int(request.query_params.get("year", timezone.now().year))
    month = request.query_params.get("month")

    if month:
        month = int(month)
        month_start = timezone.datetime(
            year, month, 1, tzinfo=timezone.get_current_timezone()
        )
        if month == 12:
            month_end = timezone.datetime(
                year + 1, 1, 1, tzinfo=timezone.get_current_timezone()
            )
        else:
            month_end = timezone.datetime(
                year, month + 1, 1, tzinfo=timezone.get_current_timezone()
            )
    else:
        # Full year
        month_start = timezone.datetime(
            year, 1, 1, tzinfo=timezone.get_current_timezone()
        )
        month_end = timezone.datetime(
            year + 1, 1, 1, tzinfo=timezone.get_current_timezone()
        )

    # Subscription revenue
    subscription_revenue = TenantSubscriptionPayment.objects.filter(
        status="completed", completed_at__gte=month_start, completed_at__lt=month_end
    ).aggregate(total=Sum("amount"), count=Count("id"))

    # WiFi payment revenue share
    revenue_by_tenant = []
    total_platform_share = 0

    for tenant in Tenant.objects.filter(subscription_plan__isnull=False):
        tenant_payments = (
            Payment.objects.filter(
                tenant=tenant,
                status="completed",
                completed_at__gte=month_start,
                completed_at__lt=month_end,
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )

        if tenant_payments:
            share_pct = tenant.subscription_plan.revenue_share_percentage
            platform_share = float(tenant_payments * share_pct / 100)
            total_platform_share += platform_share

            revenue_by_tenant.append(
                {
                    "tenant": tenant.business_name,
                    "slug": tenant.slug,
                    "wifi_revenue": float(tenant_payments),
                    "share_percentage": float(share_pct),
                    "platform_share": round(platform_share, 2),
                }
            )

    # Sort by platform share
    revenue_by_tenant.sort(key=lambda x: x["platform_share"], reverse=True)

    return Response(
        {
            "success": True,
            "period": f"{year}-{month:02d}" if month else str(year),
            "subscription_revenue": {
                "total": float(subscription_revenue["total"] or 0),
                "count": subscription_revenue["count"] or 0,
            },
            "revenue_share": {
                "total_platform_share": round(total_platform_share, 2),
                "by_tenant": revenue_by_tenant[:20],  # Top 20
            },
            "total_platform_revenue": float(subscription_revenue["total"] or 0)
            + round(total_platform_share, 2),
            "currency": "TZS",
        }
    )


# =============================================================================
# TENANT ROUTER MANAGEMENT
# =============================================================================


@api_view(["GET", "POST"])
@permission_classes([TenantAPIKeyPermission])
def tenant_routers(request):
    """
    List or create routers for the tenant
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        routers = Router.objects.filter(tenant=tenant).order_by("name")
        return Response(
            {"success": True, "routers": RouterSerializer(routers, many=True).data}
        )

    elif request.method == "POST":
        # Check limit
        from .subscription import UsageMeter

        meter = UsageMeter(tenant)
        can_add, message = meter.can_add_router()

        if not can_add:
            return Response(
                {"success": False, "message": message}, status=status.HTTP_403_FORBIDDEN
            )

        serializer = RouterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        router = serializer.save(tenant=tenant)

        return Response(
            {
                "success": True,
                "message": "Router added successfully",
                "router": RouterSerializer(router).data,
            },
            status=status.HTTP_201_CREATED,
        )


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([TenantAPIKeyPermission])
def tenant_router_detail(request, router_id):
    """
    Get, update, or delete a specific router
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        router = Router.objects.get(id=router_id, tenant=tenant)
    except Router.DoesNotExist:
        return Response(
            {"success": False, "message": "Router not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response({"success": True, "router": RouterSerializer(router).data})

    elif request.method == "PUT":
        serializer = RouterSerializer(router, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "success": True,
                    "message": "Router updated",
                    "router": serializer.data,
                }
            )
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    elif request.method == "DELETE":
        router.is_active = False  # Soft delete
        router.save()
        return Response({"success": True, "message": "Router removed"})


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def test_router_connection(request, router_id):
    """
    Test connection to a router
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        router = Router.objects.get(id=router_id, tenant=tenant)
    except Router.DoesNotExist:
        return Response(
            {"success": False, "message": "Router not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        # Test connection
        import routeros_api

        connection = routeros_api.RouterOsApiPool(
            router.host,
            username=router.username,
            password=router.password,
            port=router.port,
            plaintext_login=True,
        )
        api = connection.get_api()

        # Get router identity
        identity = api.get_resource("/system/identity").get()[0]

        # Update last seen and clear errors
        router.last_seen = timezone.now()
        router.last_error = ""
        router.status = "online"
        router.save()

        connection.disconnect()

        return Response(
            {
                "success": True,
                "message": f"Connected to {identity.get('name', 'Unknown')}",
                "router_name": identity.get("name"),
            }
        )

    except Exception as e:
        router.last_error = str(e)
        router.status = "error"
        router.save()

        return Response(
            {"success": False, "message": f"Connection failed: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )
