"""
Kitonga WiFi Remote App — Customer-Facing API Views

These endpoints serve the WebView-based mobile app (iOS/Android).
They allow end-users to:
  1. Sign up / Log in
  2. Browse WiFi locations (tenants)
  3. Choose a KTN data plan
  4. Pay via Snippe Payment
  5. Receive their KTN config
  6. Check plan status by phone number

All responses follow the data shapes defined in the
"Kitonga WiFi Remote App — Backend Integration Guide".
"""

import logging

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User as DjangoUser
from django.db import IntegrityError
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import (
    Tenant,
    TenantVPNConfig,
    RemoteUser,
    RemoteAccessPlan,
    RemoteAccessPayment,
    RemoteAccessLog,
    AppUserProfile,
    PhoneOTP,
)
from .wireguard_utils import generate_wireguard_keypair, generate_preshared_key

logger = logging.getLogger(__name__)


# =========================================================================
# Helpers
# =========================================================================


def _normalize_phone(phone: str) -> str:
    """Normalize a Tanzanian phone number to 255XXXXXXXXX format."""
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+"):
        phone = phone[1:]
    if phone.startswith("0") and len(phone) >= 10:
        phone = "255" + phone[1:]
    if not phone.startswith("255") and len(phone) <= 10:
        phone = "255" + phone
    return phone


def _send_otp_sms(phone_number: str, otp_code: str) -> bool:
    """Send OTP code via NextSMS. Returns True on success."""
    try:
        from .nextsms import NextSMSAPI

        sms = NextSMSAPI()
        result = sms.send_sms(
            phone_number,
            f"Your Kitonga WiFi verification code is: {otp_code}. "
            f"Valid for 10 minutes. Do not share this code.",
            reference=f"OTP-{phone_number}",
        )
        return result.get("success", False)
    except Exception as e:
        logger.error(f"Failed to send OTP SMS to {phone_number}: {e}")
        return False


# =========================================================================
# Helper: resolve DjangoUser → RemoteUser (find their active VPN profile)
# =========================================================================


def _get_remote_user_for_django_user(user: DjangoUser):
    """
    Return the most recently-created active RemoteUser linked to this
    Django user (matched by email).  Returns None when no link exists.
    """
    return (
        RemoteUser.objects.filter(email=user.email, is_active=True)
        .select_related("vpn_config", "vpn_config__router", "plan", "tenant")
        .order_by("-created_at")
        .first()
    )


# =========================================================================
# §2  Authentication — Signup
# =========================================================================


@api_view(["POST"])
@permission_classes([AllowAny])
def app_signup(request):
    """
    Register a new app user using phone number.

    POST /api/app/signup/
    Body: {
        "name": "...",
        "phone_number": "0712345678",
        "password": "...",
        "password_confirm": "...",
        "email": "..."  (optional)
    }
    Returns: { "token": "...", "user": { "id", "name", "email", "phone_number" } }
    """
    name = (request.data.get("name") or "").strip()
    phone_raw = (request.data.get("phone_number") or "").strip()
    email = (request.data.get("email") or "").strip().lower()
    password = request.data.get("password") or ""
    password_confirm = request.data.get("password_confirm") or ""

    # Validation
    errors = {}
    if not name:
        errors["name"] = ["This field is required."]
    if not phone_raw:
        errors["phone_number"] = ["This field is required."]
    if not password:
        errors["password"] = ["This field is required."]
    if password and len(password) < 6:
        errors["password"] = ["Password must be at least 6 characters."]
    if password != password_confirm:
        errors["password_confirm"] = ["Passwords do not match."]

    if errors:
        return Response(
            {"detail": "Validation error.", "errors": errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    phone = _normalize_phone(phone_raw)

    # Check if phone already registered
    if AppUserProfile.objects.filter(phone_number=phone).exists():
        return Response(
            {
                "detail": "Validation error.",
                "errors": {
                    "phone_number": [
                        "An account with this phone number already exists."
                    ]
                },
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Use phone as username (unique), email is optional
    username = phone
    if DjangoUser.objects.filter(username=username).exists():
        return Response(
            {
                "detail": "Validation error.",
                "errors": {
                    "phone_number": [
                        "An account with this phone number already exists."
                    ]
                },
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    first_name = name.split(" ", 1)[0]
    last_name = name.split(" ", 1)[1] if " " in name else ""

    user = DjangoUser.objects.create_user(
        username=username,
        email=email or f"{phone}@app.kitonga.klikcell.com",
        password=password,
        first_name=first_name,
        last_name=last_name,
        is_active=False,  # Inactive until phone verified via OTP
        is_staff=False,
    )

    # Create app profile with phone
    AppUserProfile.objects.create(user=user, phone_number=phone)

    # Send verification OTP via SMS
    otp = PhoneOTP.create_for_phone(phone, purpose="phone_verify")
    sent = _send_otp_sms(phone, otp.otp_code)

    logger.info(
        "App signup: %s name=%s (id=%d) otp_sent=%s",
        phone,
        name,
        user.id,
        sent,
    )

    return Response(
        {
            "message": "Account created. A verification code has been sent to your phone.",
            "phone_number": phone,
            "requires_verification": True,
        },
        status=status.HTTP_201_CREATED,
    )


# =========================================================================
# §2b  Phone Verification — Verify OTP after signup
# =========================================================================


@api_view(["POST"])
@permission_classes([AllowAny])
def app_verify_phone(request):
    """
    Verify phone number with OTP sent during signup.

    POST /api/app/verify-phone/
    Body: { "phone_number": "0712345678", "otp": "482916" }
    Returns: { "token": "...", "user": { "id", "name", "email", "phone_number" } }
    """
    phone_raw = (request.data.get("phone_number") or "").strip()
    otp_code = (request.data.get("otp") or "").strip()

    if not phone_raw or not otp_code:
        return Response(
            {"detail": "Phone number and OTP are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    phone = _normalize_phone(phone_raw)

    # Find the latest unused phone_verify OTP for this phone
    otp_obj = (
        PhoneOTP.objects.filter(
            phone_number=phone,
            purpose="phone_verify",
            is_used=False,
        )
        .order_by("-created_at")
        .first()
    )

    if not otp_obj:
        return Response(
            {"detail": "No pending verification found. Please sign up again."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    verified, message = otp_obj.verify(otp_code)
    if not verified:
        return Response(
            {"detail": message},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Activate the user account
    profile = (
        AppUserProfile.objects.filter(phone_number=phone).select_related("user").first()
    )
    if not profile:
        return Response(
            {"detail": "Account not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    user = profile.user
    user.is_active = True
    user.save(update_fields=["is_active"])

    # Generate auth token
    token, _ = Token.objects.get_or_create(user=user)

    logger.info("App verify-phone: %s activated (user=%d)", phone, user.id)

    return Response(
        {
            "token": token.key,
            "user": {
                "id": user.id,
                "name": user.get_full_name() or user.username,
                "email": user.email,
                "phone_number": phone,
            },
        }
    )


# =========================================================================
# §2c  Resend OTP — For phone verification
# =========================================================================


@api_view(["POST"])
@permission_classes([AllowAny])
def app_resend_otp(request):
    """
    Resend phone verification OTP (rate limited to 1 per 60 seconds).

    POST /api/app/resend-otp/
    Body: { "phone_number": "0712345678" }
    Returns: { "message": "Verification code sent." }
    """
    phone_raw = (request.data.get("phone_number") or "").strip()

    if not phone_raw:
        return Response(
            {"detail": "Phone number is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    phone = _normalize_phone(phone_raw)

    # Check that an unverified account exists for this phone
    profile = (
        AppUserProfile.objects.filter(phone_number=phone).select_related("user").first()
    )
    if not profile or profile.user.is_active:
        # Don't reveal account status
        return Response(
            {"message": "If this number has a pending account, a code will be sent."}
        )

    # Rate limit: 1 OTP per 60 seconds
    from datetime import timedelta

    recent = PhoneOTP.objects.filter(
        phone_number=phone,
        purpose="phone_verify",
        is_used=False,
        created_at__gte=timezone.now() - timedelta(seconds=60),
    ).first()

    if recent:
        return Response(
            {"detail": "OTP was sent recently. Please wait 60 seconds."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    otp = PhoneOTP.create_for_phone(phone, purpose="phone_verify")
    sent = _send_otp_sms(phone, otp.otp_code)

    logger.info("App resend-otp: %s sent=%s", phone, sent)

    return Response(
        {"message": "If this number has a pending account, a code will be sent."}
    )


# =========================================================================
# §2  Authentication — Login
# =========================================================================


@api_view(["POST"])
@permission_classes([AllowAny])
def app_login(request):
    """
    Log in an existing app user with phone number + password.

    POST /api/app/login/
    Body: { "phone_number": "0712345678", "password": "..." }
    Returns: { "token": "...", "user": { "id", "name", "email", "phone_number" } }
    """
    phone_raw = (request.data.get("phone_number") or "").strip()
    password = request.data.get("password") or ""

    if not phone_raw or not password:
        return Response(
            {"detail": "Phone number and password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    phone = _normalize_phone(phone_raw)

    # Find the Django user via AppUserProfile
    profile = (
        AppUserProfile.objects.filter(phone_number=phone).select_related("user").first()
    )

    if not profile:
        return Response(
            {"detail": "Invalid phone number or password."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    user = authenticate(username=profile.user.username, password=password)

    if not user:
        return Response(
            {"detail": "Invalid phone number or password."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        return Response(
            {
                "detail": "Phone number not verified. Please verify your phone first.",
                "requires_verification": True,
                "phone_number": phone,
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    token, _ = Token.objects.get_or_create(user=user)

    logger.info(f"App login: {phone} (id={user.id})")

    return Response(
        {
            "token": token.key,
            "user": {
                "id": user.id,
                "name": user.get_full_name() or phone,
                "email": user.email,
                "phone_number": phone,
            },
        }
    )


# =========================================================================
# Forgot Password — Request OTP via SMS
# =========================================================================


@api_view(["POST"])
@permission_classes([AllowAny])
def app_forgot_password(request):
    """
    Send a 6-digit OTP to the user's phone number for password reset.

    POST /api/app/forgot-password/
    Body: { "phone_number": "0712345678" }
    Returns: { "message": "OTP sent to your phone number." }
    """
    phone_raw = (request.data.get("phone_number") or "").strip()

    if not phone_raw:
        return Response(
            {"detail": "Phone number is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    phone = _normalize_phone(phone_raw)

    # Check if the phone number exists
    profile = AppUserProfile.objects.filter(phone_number=phone).first()
    if not profile:
        # Don't reveal whether the phone exists (security best practice)
        # But still return success to prevent enumeration
        return Response(
            {
                "message": "If this phone number is registered, you will receive an OTP.",
            }
        )

    # Rate limit: don't send more than 1 OTP per 60 seconds
    from django.utils import timezone as tz
    from datetime import timedelta

    recent_otp = PhoneOTP.objects.filter(
        phone_number=phone,
        purpose="password_reset",
        is_used=False,
        created_at__gte=tz.now() - timedelta(seconds=60),
    ).first()

    if recent_otp:
        return Response(
            {"detail": "An OTP was sent recently. Please wait 60 seconds."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # Create and send OTP
    otp = PhoneOTP.create_for_phone(phone, purpose="password_reset")
    sent = _send_otp_sms(phone, otp.otp_code)

    if sent:
        logger.info(f"App forgot-password: OTP sent to {phone}")
    else:
        logger.error(f"App forgot-password: Failed to send OTP to {phone}")

    return Response(
        {
            "message": "If this phone number is registered, you will receive an OTP.",
        }
    )


# =========================================================================
# Reset Password — Verify OTP + Set New Password
# =========================================================================


@api_view(["POST"])
@permission_classes([AllowAny])
def app_reset_password(request):
    """
    Verify the OTP and set a new password.

    POST /api/app/reset-password/
    Body: {
        "phone_number": "0712345678",
        "otp": "123456",
        "new_password": "...",
        "new_password_confirm": "..."
    }
    Returns: { "message": "Password reset successful. You can now log in." }
    """
    phone_raw = (request.data.get("phone_number") or "").strip()
    otp_code = (request.data.get("otp") or "").strip()
    new_password = request.data.get("new_password") or ""
    new_password_confirm = request.data.get("new_password_confirm") or ""

    errors = {}
    if not phone_raw:
        errors["phone_number"] = ["This field is required."]
    if not otp_code:
        errors["otp"] = ["This field is required."]
    if not new_password:
        errors["new_password"] = ["This field is required."]
    if new_password and len(new_password) < 6:
        errors["new_password"] = ["Password must be at least 6 characters."]
    if new_password != new_password_confirm:
        errors["new_password_confirm"] = ["Passwords do not match."]

    if errors:
        return Response(
            {"detail": "Validation error.", "errors": errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    phone = _normalize_phone(phone_raw)

    # Find the latest unused OTP for this phone
    otp_record = (
        PhoneOTP.objects.filter(
            phone_number=phone,
            purpose="password_reset",
            is_used=False,
        )
        .order_by("-created_at")
        .first()
    )

    if not otp_record:
        return Response(
            {"detail": "No OTP found. Please request a new one."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Verify the OTP
    is_valid, message = otp_record.verify(otp_code)
    if not is_valid:
        return Response(
            {"detail": message},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Find the user and update password
    profile = (
        AppUserProfile.objects.filter(phone_number=phone).select_related("user").first()
    )
    if not profile:
        return Response(
            {"detail": "Account not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    user = profile.user
    user.set_password(new_password)
    user.save(update_fields=["password"])

    # Invalidate all existing tokens (force re-login)
    Token.objects.filter(user=user).delete()

    logger.info(f"App reset-password: password changed for {phone} (user={user.id})")

    return Response(
        {
            "message": "Password reset successful. You can now log in.",
        }
    )


# =========================================================================
# Delete Account
# =========================================================================


@api_view(["DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def app_delete_account(request):
    """
    Permanently delete the authenticated user's account and all associated data.

    DELETE /api/app/delete-account/
    Body: { "password": "..." }  (confirmation)
    Returns: { "message": "Account deleted successfully." }
    """
    user = request.user
    password = request.data.get("password") or ""

    if not password:
        return Response(
            {"detail": "Password is required to confirm account deletion."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Verify password
    if not user.check_password(password):
        return Response(
            {"detail": "Incorrect password."},
            status=status.HTTP_403_FORBIDDEN,
        )

    phone = ""
    try:
        profile = user.app_profile
        phone = profile.phone_number
    except AppUserProfile.DoesNotExist:
        pass

    # Deactivate all remote users linked to this email
    remote_users = RemoteUser.objects.filter(email=user.email, is_active=True)
    deactivated_count = 0
    for ru in remote_users:
        ru.status = "revoked"
        ru.is_active = False
        ru.save(update_fields=["status", "is_active", "updated_at"])
        deactivated_count += 1

        # Log the revocation
        try:
            RemoteAccessLog.objects.create(
                tenant=ru.tenant,
                remote_user=ru,
                event_type="revoked",
                event_details=f"Account deleted by user. Phone: {phone}",
            )
        except Exception:
            pass

    # Delete tokens, profile, and user
    Token.objects.filter(user=user).delete()

    try:
        user.app_profile.delete()
    except AppUserProfile.DoesNotExist:
        pass

    username = user.username
    user.delete()

    logger.info(
        f"App delete-account: {username} (phone={phone}) deleted. "
        f"{deactivated_count} KTN profiles revoked."
    )

    return Response(
        {
            "message": "Account deleted successfully.",
        }
    )


# =========================================================================
# §3  Tenants — Location List
# =========================================================================


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def app_tenants(request):
    """
    List active Kitonga WiFi locations (tenants) that have KTN configured.

    GET /api/app/tenants/
    Returns: [ { "id": 1, "name": "...", "location": "...", ... } ]
    """
    tenants = (
        Tenant.objects.filter(
            is_active=True,
            subscription_status__in=["active", "trial"],
        )
        .select_related("subscription_plan")
        .order_by("business_name")
    )

    # Only show tenants that have VPN configured
    tenant_ids_with_vpn = TenantVPNConfig.objects.filter(
        is_active=True,
    ).values_list("tenant_id", flat=True)

    tenants = tenants.filter(id__in=tenant_ids_with_vpn)

    results = []
    for t in tenants:
        logo_url = None
        if t.logo:
            try:
                logo_url = request.build_absolute_uri(t.logo.url)
            except Exception:
                pass

        # Build location string from business_address or fallback
        location = t.business_address or f"{t.country}"
        if not location or location == "TZ":
            location = "Tanzania"

        results.append(
            {
                "id": str(t.id),
                "name": t.business_name,
                "location": location,
                "description": t.notes or None,
                "logo": logo_url,
            }
        )

    return Response(results)


# =========================================================================
# §4  Plans — Per Location
# =========================================================================


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def app_plans(request):
    """
    List KTN plans for a given tenant (location).

    GET /api/app/plans/?tenant_id=<uuid>
    Returns: [ { "id": 101, "name": "...", "price": 1000, ... } ]
    """
    tenant_id = request.query_params.get("tenant_id", "").strip()

    if not tenant_id:
        return Response(
            {"detail": "tenant_id query parameter is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        tenant = Tenant.objects.get(id=tenant_id, is_active=True)
    except (Tenant.DoesNotExist, ValueError):
        return Response(
            {"detail": "Location not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    plans = RemoteAccessPlan.objects.filter(
        tenant=tenant,
        is_active=True,
    ).order_by("display_order", "price")

    results = []
    for p in plans:
        speed_mbps = None
        if p.download_speed:
            # Try to extract numeric value from "10 Mbps"
            try:
                speed_mbps = int("".join(c for c in p.download_speed if c.isdigit()))
            except (ValueError, TypeError):
                pass

        # Build features list
        features = list(p.features) if p.features else []
        if not features:
            # Auto-generate features from plan attributes
            if p.download_speed:
                features.append(p.download_speed)
            if p.data_limit_gb is not None:
                features.append(f"{p.data_limit_gb} GB")
            else:
                features.append("Unlimited data")
            if p.max_devices_per_user > 1:
                features.append(f"{p.max_devices_per_user} devices")

        results.append(
            {
                "id": str(p.id),
                "name": p.name,
                "price": float(p.effective_price),
                "currency": p.currency,
                "duration_days": p.billing_days,
                "description": p.description or None,
                "speed_mbps": speed_mbps,
                "features": features if features else None,
            }
        )

    return Response(results)


# =========================================================================
# §5  Payment — Initiate & Verify
# =========================================================================


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def app_initiate_payment(request):
    """
    Initiate a Snippe payment session for a KTN plan.
    This creates a checkout session URL for the app's iframe.

    POST /api/app/initiate-payment/
    Body: {
        "plan_id": "<uuid>",
        "tenant_id": "<uuid>",
        "phone_number": "+255..."  (optional)
    }
    Returns: {
        "status": "pending",
        "order_reference": "KTN-XXXXXXXX",
        "checkout_url": "https://...",      // for iframe
        "snippe_reference": "...",
        "amount": 10000,
        "plan_name": "...",
        "currency": "TZS"
    }
    """
    user = request.user
    plan_id = request.data.get("plan_id", "")
    tenant_id = request.data.get("tenant_id", "")
    phone_number = (request.data.get("phone_number") or "").strip()

    if not plan_id or not tenant_id:
        return Response(
            {"detail": "plan_id and tenant_id are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Resolve tenant
    try:
        tenant = Tenant.objects.get(id=tenant_id, is_active=True)
    except (Tenant.DoesNotExist, ValueError):
        return Response(
            {"detail": "Location not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Resolve plan
    try:
        plan = RemoteAccessPlan.objects.get(id=plan_id, tenant=tenant, is_active=True)
    except (RemoteAccessPlan.DoesNotExist, ValueError):
        return Response(
            {"detail": "Plan not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Ensure tenant has VPN configured
    try:
        vpn_config = TenantVPNConfig.objects.get(tenant=tenant, is_active=True)
    except TenantVPNConfig.DoesNotExist:
        return Response(
            {"detail": "This location does not have KTN configured yet."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Find or create RemoteUser for this Django user under this tenant
    # Match by email OR phone to handle phone-based auth users
    from django.db.models import Q

    remote_user = (
        RemoteUser.objects.filter(
            Q(email=user.email) | Q(phone=phone_number if phone_number else None),
            tenant=tenant,
            vpn_config=vpn_config,
        )
        .exclude(status="revoked")
        .first()
    )

    if not remote_user:
        # Auto-provision a new remote user with WireGuard keys
        next_ip = vpn_config.get_next_available_ip()
        if not next_ip:
            return Response(
                {"detail": "No available KTN addresses. Contact support."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        keypair = generate_wireguard_keypair()
        psk = generate_preshared_key()

        try:
            remote_user = RemoteUser.objects.create(
                tenant=tenant,
                vpn_config=vpn_config,
                name=user.get_full_name() or user.email,
                email=user.email,
                phone=phone_number,
                plan=plan,
                public_key=keypair["public_key"],
                private_key=keypair["private_key"],
                preshared_key=psk,
                assigned_ip=next_ip,
                status="disabled",  # Will be activated after payment
                is_active=False,
            )
        except IntegrityError:
            # Race condition or stale IP — retry once with a fresh IP
            logger.warning(
                "App: IP %s collision for vpn_config=%s, retrying...",
                next_ip,
                vpn_config.id,
            )
            next_ip = vpn_config.get_next_available_ip()
            if not next_ip:
                return Response(
                    {"detail": "No available KTN addresses. Contact support."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            keypair = generate_wireguard_keypair()
            psk = generate_preshared_key()
            remote_user = RemoteUser.objects.create(
                tenant=tenant,
                vpn_config=vpn_config,
                name=user.get_full_name() or user.email,
                email=user.email,
                phone=phone_number,
                plan=plan,
                public_key=keypair["public_key"],
                private_key=keypair["private_key"],
                preshared_key=psk,
                assigned_ip=next_ip,
                status="disabled",
                is_active=False,
            )

        logger.info(
            f"App: auto-provisioned RemoteUser {remote_user.name} "
            f"(ip={next_ip}) for tenant={tenant.slug}"
        )

    # Update phone if provided
    if phone_number and not remote_user.phone:
        remote_user.phone = phone_number
        remote_user.save(update_fields=["phone", "updated_at"])

    amount = int(plan.effective_price)

    # Expire old pending payments for this user
    RemoteAccessPayment.objects.filter(
        remote_user=remote_user, status="pending"
    ).update(status="expired")

    # Create payment record
    payment = RemoteAccessPayment.objects.create(
        tenant=tenant,
        remote_user=remote_user,
        plan=plan,
        amount=amount,
        currency=plan.currency,
        billing_days=plan.billing_days,
        phone_number=phone_number or remote_user.phone,
        payment_channel="snippe",
        status="pending",
    )

    # Create Snippe checkout session (for iframe)
    from .snippe import SnippeAPI

    webhook_url = getattr(settings, "SNIPPE_WEBHOOK_URL", "") or ""

    # Use tenant's own Snippe key if available, otherwise platform key
    snippe_key = tenant.snippe_api_key or None
    snippe = SnippeAPI(api_key=snippe_key)

    metadata = {
        "order_reference": payment.order_reference,
        "payment_type": "ktn",
        "remote_user_id": str(remote_user.id),
        "tenant": tenant.slug,
        "app_user_id": str(user.id),
    }

    customer = {
        "phone": phone_number or remote_user.phone or "",
        "name": user.get_full_name() or "App User",
        "email": user.email,
    }

    # Try session-based payment (iframe) first
    result = snippe.create_session(
        amount=amount,
        currency=plan.currency,
        customer=customer,
        webhook_url=webhook_url,
        description=f"{plan.name} - {tenant.business_name}",
        metadata=metadata,
    )

    if result.get("success"):
        snippe_ref = result.get("reference", "")
        checkout_url = result.get("checkout_url", "")

        if snippe_ref:
            payment.payment_reference = snippe_ref
            payment.save(update_fields=["payment_reference"])

        logger.info(
            f"App payment session created: ref={payment.order_reference} "
            f"snippe={snippe_ref} amount={amount} user={user.email}"
        )

        return Response(
            {
                "status": "pending",
                "order_reference": payment.order_reference,
                "checkout_url": checkout_url,
                "snippe_reference": snippe_ref,
                "amount": amount,
                "plan_name": plan.name,
                "currency": plan.currency,
                "duration_days": plan.billing_days,
            }
        )

    # Session creation failed — try direct mobile money push if phone provided
    if phone_number or remote_user.phone:
        phone_to_use = phone_number or remote_user.phone
        name_parts = (user.get_full_name() or "App User").split(" ", 1)
        firstname = name_parts[0]
        lastname = name_parts[1] if len(name_parts) > 1 else ""

        mobile_result = snippe.create_mobile_payment(
            phone_number=phone_to_use,
            amount=amount,
            firstname=firstname,
            lastname=lastname,
            email=user.email,
            webhook_url=webhook_url,
            metadata=metadata,
            idempotency_key=payment.order_reference,
        )

        if mobile_result.get("success"):
            snippe_ref = mobile_result.get("reference", "")
            if snippe_ref:
                payment.payment_reference = snippe_ref
                payment.save(update_fields=["payment_reference"])

            return Response(
                {
                    "status": "pending",
                    "order_reference": payment.order_reference,
                    "checkout_url": None,
                    "snippe_reference": snippe_ref,
                    "amount": amount,
                    "plan_name": plan.name,
                    "currency": plan.currency,
                    "duration_days": plan.billing_days,
                    "message": f"USSD push sent to {phone_to_use}",
                }
            )

    # All payment methods failed
    payment.mark_failed()
    error_msg = result.get("message", result.get("error", "Payment initiation failed"))
    return Response(
        {"detail": f"Payment failed: {error_msg}"},
        status=status.HTTP_502_BAD_GATEWAY,
    )


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def app_verify_payment(request):
    """
    Verify a Snippe payment and activate the user's KTN plan.

    POST /api/app/verify-payment/
    Body: {
        "plan_id": "<uuid>",
        "tenant_id": "<uuid>",
        "transaction_id": "TXN-123",
        "phone_number": "+255..."  (optional)
    }
    Returns: {
        "status": "success" | "pending" | "failed",
        "transaction_id": "TXN-123",
        "message": "...",
        "config_ready": true | false
    }
    """
    user = request.user
    transaction_id = (request.data.get("transaction_id") or "").strip()
    tenant_id = request.data.get("tenant_id", "")

    if not transaction_id:
        return Response(
            {"detail": "transaction_id is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Try to find the payment by snippe reference or order_reference
    payment = None

    # Strategy 1: find by Snippe payment_reference (transaction_id from Snippe)
    payment = (
        RemoteAccessPayment.objects.filter(payment_reference=transaction_id)
        .select_related("remote_user", "remote_user__vpn_config", "plan", "tenant")
        .first()
    )

    # Strategy 2: find by our order_reference
    if not payment:
        payment = (
            RemoteAccessPayment.objects.filter(order_reference=transaction_id)
            .select_related("remote_user", "remote_user__vpn_config", "plan", "tenant")
            .first()
        )

    # Strategy 3: find latest pending payment for this user + tenant
    if not payment and tenant_id:
        remote_user = RemoteUser.objects.filter(
            email=user.email, tenant_id=tenant_id
        ).first()
        if remote_user:
            payment = (
                RemoteAccessPayment.objects.filter(
                    remote_user=remote_user,
                    status="pending",
                )
                .order_by("-created_at")
                .first()
            )

    if not payment:
        return Response(
            {
                "status": "failed",
                "transaction_id": transaction_id,
                "message": "Payment not found. It may still be processing.",
                "config_ready": False,
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # If already completed, return success
    if payment.status == "completed":
        remote_user = payment.remote_user
        config_ready = bool(remote_user.private_key and remote_user.is_active)
        return Response(
            {
                "status": "success",
                "transaction_id": transaction_id,
                "message": "Payment confirmed.",
                "config_ready": config_ready,
            }
        )

    if payment.status == "failed":
        return Response(
            {
                "status": "failed",
                "transaction_id": transaction_id,
                "message": "Payment failed. Please try again.",
                "config_ready": False,
            }
        )

    if payment.status == "expired":
        return Response(
            {
                "status": "failed",
                "transaction_id": transaction_id,
                "message": "Payment expired. Please initiate a new payment.",
                "config_ready": False,
            }
        )

    # Status is still "pending" — check with Snippe API
    from .snippe import SnippeAPI

    snippe_key = payment.tenant.snippe_api_key or None
    snippe = SnippeAPI(api_key=snippe_key)

    ref_to_check = payment.payment_reference or payment.order_reference

    try:
        snippe_result = snippe.get_payment_status(ref_to_check)
        snippe_status = ""
        if snippe_result.get("success"):
            data = snippe_result.get("data", {})
            if isinstance(data, dict):
                snippe_status = data.get("status", "")

        if snippe_status == "completed":
            # Payment completed — activate the plan
            payment.mark_completed()

            remote_user = payment.remote_user

            # Sync peer to router
            try:
                from .mikrotik import (
                    add_wireguard_peer,
                    enable_wireguard_peer,
                    setup_wireguard_bandwidth_queue,
                )

                if not remote_user.is_configured_on_router:
                    add_result = add_wireguard_peer(remote_user)
                    if add_result.get("success"):
                        logger.info(
                            f"App: KTN peer added to router for {remote_user.name}"
                        )
                else:
                    enable_result = enable_wireguard_peer(remote_user)
                    if enable_result.get("success"):
                        logger.info(f"App: KTN peer re-enabled for {remote_user.name}")

                setup_wireguard_bandwidth_queue(remote_user)
            except Exception as e:
                logger.error(f"App: Router sync error: {e}")

            # Log event
            try:
                RemoteAccessLog.objects.create(
                    tenant=payment.tenant,
                    remote_user=remote_user,
                    event_type="payment",
                    event_details=(
                        f"App payment completed: TSh {payment.amount:,.0f} "
                        f"for {payment.billing_days} days. Ref: {payment.order_reference}"
                    ),
                )
            except Exception:
                pass

            config_ready = bool(remote_user.private_key and remote_user.is_active)
            return Response(
                {
                    "status": "success",
                    "transaction_id": transaction_id,
                    "message": "Payment confirmed.",
                    "config_ready": config_ready,
                }
            )

        elif snippe_status == "failed":
            payment.mark_failed()
            return Response(
                {
                    "status": "failed",
                    "transaction_id": transaction_id,
                    "message": "Payment failed. Please try again.",
                    "config_ready": False,
                }
            )

    except Exception as e:
        logger.error(f"App: Snippe status check error: {e}")

    # Still pending
    return Response(
        {
            "status": "pending",
            "transaction_id": transaction_id,
            "message": "Payment is still being processed. Please wait.",
            "config_ready": False,
        }
    )


# =========================================================================
# §6  KTN Config Delivery
# =========================================================================


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def app_wireguard_config(request):
    """
    Get KTN config for the authenticated user.

    GET /api/app/wireguard-config/?tenant_id=<uuid>
    Returns: {
        "download_url": "...",
        "filename": "kitonga-client.conf",
        "expires_at": "2026-03-25T23:59:59Z",
        "config_content": "[Interface]\\n..."
    }
    """
    user = request.user
    tenant_id = request.query_params.get("tenant_id", "").strip()

    # Find the user's active remote access profile
    qs = RemoteUser.objects.filter(
        email=user.email,
        is_active=True,
    ).select_related("vpn_config", "vpn_config__router", "plan", "tenant")

    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)

    remote_user = qs.order_by("-created_at").first()

    if not remote_user:
        return Response(
            {"detail": "No active KTN profile found. Please purchase a plan first."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Check expiry
    if remote_user.is_expired:
        return Response(
            {"detail": "Your KTN access has expired. Please renew your plan."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Generate config
    config_content = remote_user.generate_client_config()

    # Build a safe filename
    tenant_slug = remote_user.tenant.slug or "kitonga"
    filename = f"{tenant_slug}-ktn.conf"

    # Build download URL (the app can call this same endpoint)
    download_url = request.build_absolute_uri(request.path)
    if tenant_id:
        download_url += f"?tenant_id={tenant_id}"

    # Mark as downloaded
    if not remote_user.config_downloaded:
        remote_user.config_downloaded = True
        remote_user.save(update_fields=["config_downloaded", "updated_at"])

        # Log the download
        try:
            RemoteAccessLog.objects.create(
                tenant=remote_user.tenant,
                remote_user=remote_user,
                event_type="config_downloaded",
                event_details=f"Config downloaded via app by {user.email}",
            )
        except Exception:
            pass

    return Response(
        {
            "download_url": download_url,
            "filename": filename,
            "expires_at": (
                remote_user.expires_at.isoformat() if remote_user.expires_at else None
            ),
            "config_content": config_content,
        }
    )


# =========================================================================
# §7  User Status Lookup (Public — no auth required)
# =========================================================================


@api_view(["GET"])
@permission_classes([AllowAny])
def app_user_status(request):
    """
    Look up KTN plan status by phone number.
    No authentication required — intentional for users who lost login.

    GET /api/app/user-status/?phone=+255712345678
    Returns: {
        "phone": "+255712345678",
        "status": "active" | "expired" | "none",
        "has_active_plan": true | false,
        "message": "...",
        "plan": { ... } | null
    }
    """
    phone = (request.query_params.get("phone") or "").strip()

    if not phone:
        return Response(
            {"detail": "phone query parameter is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Normalize phone number
    from .utils import normalize_phone_number

    try:
        normalized = normalize_phone_number(phone)
    except Exception:
        normalized = phone

    # Find remote user by phone
    remote_user = (
        RemoteUser.objects.filter(phone=normalized, is_active=True)
        .select_related("plan", "tenant")
        .order_by("-created_at")
        .first()
    )

    # Also try with original phone if normalization changed it
    if not remote_user and normalized != phone:
        remote_user = (
            RemoteUser.objects.filter(phone=phone, is_active=True)
            .select_related("plan", "tenant")
            .order_by("-created_at")
            .first()
        )

    if not remote_user:
        return Response(
            {
                "phone": phone,
                "status": "none",
                "has_active_plan": False,
                "message": "No account found for this phone number.",
                "plan": None,
            }
        )

    # Check if expired
    is_expired = remote_user.is_expired
    has_active = not is_expired and remote_user.status == "active"

    if has_active:
        expires_str = (
            remote_user.expires_at.strftime("%d %b %Y %H:%M")
            if remote_user.expires_at
            else "Unlimited"
        )
        message = f"Active until {expires_str}"
        status_val = "active"
    elif is_expired:
        message = "Your plan has expired. Please renew."
        status_val = "expired"
    else:
        message = "Account found but not active."
        status_val = "expired"

    plan_data = None
    if remote_user.plan:
        speed_mbps = None
        if remote_user.plan.download_speed:
            try:
                speed_mbps = int(
                    "".join(c for c in remote_user.plan.download_speed if c.isdigit())
                )
            except (ValueError, TypeError):
                pass

        plan_data = {
            "name": remote_user.plan.name,
            "tenant_name": remote_user.tenant.business_name,
            "expires_at": (
                remote_user.expires_at.isoformat() if remote_user.expires_at else None
            ),
            "speed_mbps": speed_mbps,
            "duration_days": remote_user.plan.billing_days,
        }

    return Response(
        {
            "phone": phone,
            "status": status_val,
            "has_active_plan": has_active,
            "message": message,
            "plan": plan_data,
        }
    )


# =========================================================================
# Account — Get current user info
# =========================================================================


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def app_account(request):
    """
    Get current authenticated user's account info and active plans.

    GET /api/app/account/
    Returns: {
        "user": { "id": ..., "name": "...", "email": "..." },
        "active_plans": [ ... ]
    }
    """
    user = request.user

    # Find all active remote user profiles for this user
    remote_users = (
        RemoteUser.objects.filter(email=user.email, is_active=True)
        .select_related("plan", "tenant")
        .order_by("-created_at")
    )

    active_plans = []
    for ru in remote_users:
        if ru.is_expired:
            continue
        plan_info = {
            "tenant_id": str(ru.tenant.id),
            "tenant_name": ru.tenant.business_name,
            "plan_name": ru.plan.name if ru.plan else "Custom",
            "assigned_ip": ru.assigned_ip,
            "status": ru.status,
            "expires_at": ru.expires_at.isoformat() if ru.expires_at else None,
            "config_ready": bool(ru.private_key),
        }
        active_plans.append(plan_info)

    # Get phone from profile
    phone = ""
    try:
        phone = user.app_profile.phone_number
    except AppUserProfile.DoesNotExist:
        pass

    return Response(
        {
            "user": {
                "id": user.id,
                "name": user.get_full_name() or user.email,
                "email": user.email,
                "phone_number": phone,
            },
            "active_plans": active_plans,
        }
    )


# =========================================================================
# §8  Native Bridge Endpoints — Called by Android/iOS native VPN layer
# =========================================================================
# These endpoints are called by the native KTNBridge, NOT by the React
# WebView directly. The native app uses these to obtain WireGuard tunnel
# credentials and check plan validity before connecting.
# =========================================================================


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def vpn_session(request):
    """
    Get VPN session credentials for the native WireGuard tunnel.

    Called by the native KTNBridge.connectVPN() and KTNBridge.requestSession().
    Returns parsed WireGuard keys + endpoint — NOT the raw .conf file.
    The native layer uses these to programmatically create a VPN tunnel
    named "KTN" via Android VpnService / iOS NetworkExtension.

    GET /api/vpn/session/
    Headers: Authorization: Token <token>
    Query:   ?tenant_id=<uuid>  (optional)

    Returns 200:
    {
        "success": true,
        "tunnel_name": "KTN",
        "interface": {
            "private_key": "...",
            "address": "10.200.0.4/32",
            "dns": "1.1.1.1,8.8.8.8",
            "mtu": 1420
        },
        "peer": {
            "public_key": "...",
            "preshared_key": "...",
            "endpoint": "10.100.0.40:51820",
            "allowed_ips": "0.0.0.0/0",
            "persistent_keepalive": 25
        },
        "plan": {
            "name": "Monthly 30GB",
            "expires_at": "2026-03-26T13:03:06+00:00"
        },
        "tenant": {
            "id": "...",
            "name": "Kitonga WiFi"
        }
    }
    """
    user = request.user
    tenant_id = request.query_params.get("tenant_id", "").strip()

    # Also check native-stored tenant_id in header (set by KTNBridge)
    if not tenant_id:
        tenant_id = request.META.get("HTTP_X_TENANT_ID", "").strip()

    # Find the user's active remote access profile
    qs = RemoteUser.objects.filter(
        email=user.email,
        is_active=True,
    ).select_related("vpn_config", "vpn_config__router", "plan", "tenant")

    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)

    remote_user = qs.order_by("-created_at").first()

    # Also try matching by phone number if no match by email
    if not remote_user:
        phone = ""
        try:
            phone = user.app_profile.phone_number
        except AppUserProfile.DoesNotExist:
            pass

        if phone:
            qs2 = RemoteUser.objects.filter(
                phone=phone,
                is_active=True,
            ).select_related("vpn_config", "vpn_config__router", "plan", "tenant")

            if tenant_id:
                qs2 = qs2.filter(tenant_id=tenant_id)

            remote_user = qs2.order_by("-created_at").first()

    if not remote_user:
        return Response(
            {
                "success": False,
                "error": "no_plan",
                "message": "No active KTN plan found. Please purchase a plan first.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # Check expiry
    if remote_user.is_expired:
        return Response(
            {
                "success": False,
                "error": "expired",
                "message": "Your KTN plan has expired. Please renew your plan.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # Ensure we have the private key
    if not remote_user.private_key:
        return Response(
            {
                "success": False,
                "error": "no_config",
                "message": "VPN configuration not ready. Please contact support.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Build parsed tunnel credentials for the native layer
    vpn_config = remote_user.vpn_config

    # Parse DNS — default to Cloudflare + Google
    dns = "1.1.1.1,8.8.8.8"
    if vpn_config and vpn_config.dns_servers:
        dns = vpn_config.dns_servers

    # Parse MTU
    mtu = 1420
    if vpn_config and hasattr(vpn_config, "mtu") and vpn_config.mtu:
        mtu = vpn_config.mtu

    # Build endpoint and server public key.
    # Clients connect to the VPS relay (public IP), NOT directly to the
    # MikroTik router (which sits behind NAT). The VPS wg0 interface
    # has the client peers and forwards decrypted traffic.
    vps_public_key = getattr(
        settings, "WG_VPS_PUBLIC_KEY", ""
    )
    vps_endpoint = getattr(
        settings, "WG_VPS_ENDPOINT", ""
    )

    # Fallback: use the vpn_config/router values if VPS relay not configured
    if not vps_public_key and vpn_config:
        vps_public_key = vpn_config.server_public_key or ""
    if not vps_endpoint and vpn_config:
        server_host = ""
        if vpn_config.router:
            server_host = vpn_config.router.host or ""
        listen_port = vpn_config.listen_port or 51820
        if server_host:
            vps_endpoint = f"{server_host}:{listen_port}"

    # Log session request
    try:
        RemoteAccessLog.objects.create(
            tenant=remote_user.tenant,
            remote_user=remote_user,
            event_type="session_requested",
            event_details=f"VPN session requested via native bridge by {user.email}",
        )
    except Exception:
        pass

    logger.info(
        "VPN session issued: user=%s remote_user=%s tenant=%s ip=%s",
        user.email,
        remote_user.name,
        remote_user.tenant.slug,
        remote_user.assigned_ip,
    )

    return Response(
        {
            "success": True,
            "tunnel_name": "KTN",
            "interface": {
                "private_key": remote_user.private_key,
                "address": f"{remote_user.assigned_ip}/32",
                "dns": dns,
                "mtu": mtu,
            },
            "peer": {
                "public_key": vps_public_key,
                "preshared_key": remote_user.preshared_key or "",
                "endpoint": vps_endpoint,
                "allowed_ips": "0.0.0.0/0",
                "persistent_keepalive": 25,
            },
            "plan": {
                "name": remote_user.plan.name if remote_user.plan else "Custom",
                "expires_at": (
                    remote_user.expires_at.isoformat()
                    if remote_user.expires_at
                    else None
                ),
                "duration_days": (
                    remote_user.plan.billing_days if remote_user.plan else None
                ),
            },
            "tenant": {
                "id": str(remote_user.tenant.id),
                "name": remote_user.tenant.business_name,
            },
        }
    )


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def vpn_status(request):
    """
    Check authenticated user's VPN plan status.

    Called by the native KTNBridge.checkPlanStatus() method.
    Also used by the native app to decide whether to auto-disconnect
    when a plan expires.

    GET /api/vpn/status/
    Headers: Authorization: Token <token>
    Query:   ?tenant_id=<uuid>  (optional)

    Returns 200:
    {
        "success": true,
        "active": true | false,
        "plan_name": "Monthly 30GB",
        "expires_at": "2026-03-26T13:03:06+00:00",
        "message": "Plan is active",
        "tenant_id": "...",
        "tenant_name": "Kitonga WiFi",
        "assigned_ip": "10.200.0.4",
        "has_session": true
    }
    """
    user = request.user
    tenant_id = request.query_params.get("tenant_id", "").strip()

    if not tenant_id:
        tenant_id = request.META.get("HTTP_X_TENANT_ID", "").strip()

    # Find the user's remote access profile
    qs = RemoteUser.objects.filter(
        email=user.email,
        is_active=True,
    ).select_related("plan", "tenant")

    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)

    remote_user = qs.order_by("-created_at").first()

    # Fallback: try phone number
    if not remote_user:
        phone = ""
        try:
            phone = user.app_profile.phone_number
        except AppUserProfile.DoesNotExist:
            pass

        if phone:
            qs2 = RemoteUser.objects.filter(
                phone=phone,
                is_active=True,
            ).select_related("plan", "tenant")

            if tenant_id:
                qs2 = qs2.filter(tenant_id=tenant_id)

            remote_user = qs2.order_by("-created_at").first()

    if not remote_user:
        return Response(
            {
                "success": True,
                "active": False,
                "plan_name": None,
                "expires_at": None,
                "message": "No active plan found. Please purchase a plan.",
                "tenant_id": tenant_id or None,
                "tenant_name": None,
                "assigned_ip": None,
                "has_session": False,
            }
        )

    is_expired = remote_user.is_expired
    is_active = not is_expired and remote_user.status == "active"

    if is_active:
        expires_str = (
            remote_user.expires_at.strftime("%d %b %Y %H:%M")
            if remote_user.expires_at
            else "Unlimited"
        )
        message = f"Plan is active until {expires_str}"
    elif is_expired:
        message = "Your plan has expired. Please renew to reconnect."
    else:
        message = "Plan found but not active."

    return Response(
        {
            "success": True,
            "active": is_active,
            "plan_name": remote_user.plan.name if remote_user.plan else "Custom",
            "expires_at": (
                remote_user.expires_at.isoformat() if remote_user.expires_at else None
            ),
            "message": message,
            "tenant_id": str(remote_user.tenant.id),
            "tenant_name": remote_user.tenant.business_name,
            "assigned_ip": remote_user.assigned_ip,
            "has_session": bool(remote_user.private_key),
        }
    )


# =========================================================================
# §8b  VPN Status Check by Phone — Public (no auth)
# =========================================================================
# Called by KTNBridge.checkPlanByPhone(phone) from the native layer.
# No authentication required — mirrors app_user_status but lives at
# /api/vpn/status/check/ to match the Android Retrofit route.
# =========================================================================


@api_view(["GET"])
@permission_classes([AllowAny])
def vpn_status_check(request):
    """
    Check VPN plan status by phone number (no auth required).

    Called by the native KTNBridge.checkPlanByPhone(phone) method.
    This lets the native layer verify plan validity even before login.

    GET /api/vpn/status/check/?phone=0712345678
    Query: phone (required) — Tanzanian phone number in any format

    Returns 200:
    {
        "success": true,
        "active": true | false,
        "plan_name": "Monthly 30GB",
        "expires_at": "2026-03-26T13:03:06+00:00",
        "message": "Plan is active"
    }
    """
    phone_raw = (request.query_params.get("phone") or "").strip()

    if not phone_raw:
        return Response(
            {
                "success": False,
                "active": False,
                "plan_name": None,
                "expires_at": None,
                "message": "Phone number is required.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    phone = _normalize_phone(phone_raw)

    # Find remote user by phone (try normalized first, then raw)
    remote_user = (
        RemoteUser.objects.filter(phone=phone, is_active=True)
        .select_related("plan", "tenant")
        .order_by("-created_at")
        .first()
    )

    if not remote_user and phone != phone_raw:
        remote_user = (
            RemoteUser.objects.filter(phone=phone_raw, is_active=True)
            .select_related("plan", "tenant")
            .order_by("-created_at")
            .first()
        )

    # Also try matching via AppUserProfile → DjangoUser → email → RemoteUser
    if not remote_user:
        profile = (
            AppUserProfile.objects.filter(phone_number=phone)
            .select_related("user")
            .first()
        )
        if profile:
            remote_user = (
                RemoteUser.objects.filter(email=profile.user.email, is_active=True)
                .select_related("plan", "tenant")
                .order_by("-created_at")
                .first()
            )

    if not remote_user:
        return Response(
            {
                "success": True,
                "active": False,
                "plan_name": None,
                "expires_at": None,
                "message": "No account found for this phone number.",
            }
        )

    is_expired = remote_user.is_expired
    is_active = not is_expired and remote_user.status == "active"

    if is_active:
        expires_str = (
            remote_user.expires_at.strftime("%d %b %Y %H:%M")
            if remote_user.expires_at
            else "Unlimited"
        )
        message = f"Plan is active until {expires_str}"
    elif is_expired:
        message = "Plan expired or inactive"
    else:
        message = "Plan found but not active."

    return Response(
        {
            "success": True,
            "active": is_active,
            "plan_name": remote_user.plan.name if remote_user.plan else "Custom",
            "expires_at": (
                remote_user.expires_at.isoformat() if remote_user.expires_at else None
            ),
            "message": message,
        }
    )
