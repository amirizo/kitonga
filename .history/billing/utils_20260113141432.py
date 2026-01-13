"""
Utility functions for billing system
"""

from django.utils import timezone
from django.db import models
from datetime import timedelta
from .models import User, Payment
import logging

logger = logging.getLogger(__name__)


def normalize_phone_number(phone_number):
    """
    Normalize phone number to standard Tanzania format (255XXXXXXXXX)

    Handles formats like:
    - +255712345678 -> 255712345678
    - 255712345678 -> 255712345678
    - 0712345678 -> 255712345678
    - 712345678 -> 255712345678

    Returns:
        str: Normalized phone number in format 255XXXXXXXXX

    Raises:
        ValueError: If phone number is invalid
    """
    if not phone_number:
        raise ValueError("Phone number cannot be empty")

    # Remove all non-numeric characters except +
    phone = "".join(c for c in str(phone_number) if c.isdigit() or c == "+")

    # Remove + sign if present
    phone = phone.replace("+", "")

    # Validate and normalize Tanzania phone numbers
    if phone.startswith("255"):
        # Already in correct format 255XXXXXXXXX
        if len(phone) == 12:
            return phone
        else:
            raise ValueError(f"Invalid Tanzania phone number format: {phone_number}")

    elif phone.startswith("0"):
        # Convert local format 07XXXXXXXX to 255XXXXXXXXX
        if len(phone) == 10:
            return "255" + phone[1:]
        else:
            raise ValueError(f"Invalid local phone number format: {phone_number}")

    elif len(phone) == 9:
        # Local number without 0 prefix (7XXXXXXXX)
        return "255" + phone

    elif len(phone) == 10 and phone.startswith("7"):
        # Local number 7XXXXXXXXX
        return "255" + phone

    else:
        raise ValueError(f"Unrecognized phone number format: {phone_number}")


def format_phone_number(phone_number):
    """
    Legacy function - use normalize_phone_number instead
    Format phone number to standard Tanzania format (255XXXXXXXXX)
    """
    try:
        return normalize_phone_number(phone_number)
    except ValueError:
        # Fallback to old logic for backward compatibility
        phone = phone_number.replace(" ", "").replace("-", "").replace("+", "")

        if phone.startswith("0"):
            phone = "255" + phone[1:]
        elif phone.startswith("255"):
            pass
        elif phone.startswith("254"):
            phone = "255" + phone[3:]
        else:
            phone = "255" + phone

        return phone


def validate_tanzania_phone_number(phone_number):
    """
    Validate if a phone number is a valid Tanzania mobile number

    Tanzania mobile networks:
    - Vodacom: 255752, 255753, 255754, 255755, 255756, 255758, 255759, 255763, 255764, 255765, 255766, 255767
    - Airtel: 255743, 255744, 255745, 255746, 255747, 255748, 255749, 255732, 255733, 255734, 255735
    - Tigo: 255714, 255715, 255716, 255717, 255718, 255719, 255712, 255713, 255682, 255683, 255684, 255685, 255686, 255687, 255688, 255689
    - Zantel: 255777, 255778, 255776
    - TTCL: 255622, 255623, 255624, 255625, 255626, 255627, 255628, 255629
    - Halotel: 255729, 255621, 255620

    Args:
        phone_number (str): Phone number to validate

    Returns:
        tuple: (is_valid, network_name, normalized_number)
    """
    try:
        normalized = normalize_phone_number(phone_number)

        # Extract the prefix (first 6 digits: 255 + 3 digit network code)
        if len(normalized) >= 6:
            prefix = normalized[:6]

            # Define network prefixes
            vodacom_prefixes = [
                "255752",
                "255753",
                "255754",
                "255755",
                "255756",
                "255758",
                "255759",
                "255763",
                "255764",
                "255765",
                "255766",
                "255767",
            ]
            airtel_prefixes = [
                "255743",
                "255744",
                "255745",
                "255746",
                "255747",
                "255748",
                "255749",
                "255732",
                "255733",
                "255734",
                "255735",
            ]
            tigo_prefixes = [
                "255714",
                "255715",
                "255716",
                "255717",
                "255718",
                "255719",
                "255712",
                "255713",
                "255682",
                "255683",
                "255684",
                "255685",
                "255686",
                "255687",
                "255688",
                "255689",
            ]
            zantel_prefixes = ["255777", "255778", "255776"]
            ttcl_prefixes = [
                "255622",
                "255623",
                "255624",
                "255625",
                "255626",
                "255627",
                "255628",
                "255629",
            ]
            halotel_prefixes = ["255729", "255621", "255620"]

            # Check which network
            if prefix in vodacom_prefixes:
                return True, "Vodacom", normalized
            elif prefix in airtel_prefixes:
                return True, "Airtel", normalized
            elif prefix in tigo_prefixes:
                return True, "Tigo", normalized
            elif prefix in zantel_prefixes:
                return True, "Zantel", normalized
            elif prefix in ttcl_prefixes:
                return True, "TTCL", normalized
            elif prefix in halotel_prefixes:
                return True, "Halotel", normalized
            else:
                # Unknown network but valid Tanzania format
                return True, "Unknown", normalized

        return False, None, normalized

    except ValueError as e:
        return False, None, str(e)


def get_user_statistics(user):
    """
    Get statistics for a user
    """
    # Calculate actual total spent from payments
    total_spent = (
        Payment.objects.filter(user=user, status="completed").aggregate(
            total=models.Sum("amount")
        )["total"]
        or 0
    )

    successful_payments = Payment.objects.filter(user=user, status="completed").count()

    failed_payments = Payment.objects.filter(user=user, status="failed").count()

    last_payment = (
        Payment.objects.filter(user=user, status="completed")
        .order_by("-completed_at")
        .first()
    )

    return {
        "total_spent": float(total_spent),
        "successful_payments": successful_payments,
        "failed_payments": failed_payments,
        "last_payment_date": last_payment.completed_at if last_payment else None,
        "member_since": user.created_at,
    }


def check_and_deactivate_expired_users():
    """
    Check and deactivate users with expired access
    Can be called from a scheduled task
    """
    now = timezone.now()
    expired_users = User.objects.filter(is_active=True, paid_until__lt=now)

    count = 0
    for user in expired_users:
        user.deactivate_access()
        count += 1
        logger.info(f"Deactivated expired user: {user.phone_number}")

    return count


def get_active_users_count():
    """
    Get count of currently active users
    """
    now = timezone.now()
    return User.objects.filter(is_active=True, paid_until__gt=now).count()


def get_revenue_statistics(days=30):
    """
    Get revenue statistics for the specified period
    """
    from datetime import timedelta

    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)

    total_revenue = (
        Payment.objects.filter(
            status="completed", completed_at__gte=start_date, completed_at__lte=end_date
        ).aggregate(total=models.Sum("amount"))["total"]
        or 0
    )

    return float(total_revenue)


def get_or_create_user(phone_number, tenant=None, **kwargs):
    """
    Get or create a user with normalized phone number (TENANT-AWARE)

    This function ensures that users are found/created using normalized
    phone numbers to prevent duplicates like:
    - +255772236727
    - 255772236727
    - 0772236727

    MULTI-TENANT: Users are scoped to tenants. The same phone number can
    exist across different tenants (e.g., a person using WiFi at two different hotels).

    Args:
        phone_number (str): Phone number in any format
        tenant: Tenant instance (required for multi-tenant mode)
        **kwargs: Additional fields for user creation

    Returns:
        tuple: (user, created) - User instance and boolean indicating if created

    Raises:
        ValueError: If phone number is invalid
    """
    # Import here to avoid circular imports
    from .models import User

    try:
        # Normalize the phone number
        normalized_phone = normalize_phone_number(phone_number)

        # Validate it's a Tanzania number
        is_valid, network, normalized_phone = validate_tanzania_phone_number(
            normalized_phone
        )
        if not is_valid:
            raise ValueError(f"Invalid Tanzania phone number: {phone_number}")

        # Try to get existing user with normalized number (scoped to tenant)
        try:
            if tenant:
                # Multi-tenant mode: find user within this tenant
                user = User.objects.get(phone_number=normalized_phone, tenant=tenant)
            else:
                # Legacy mode: find user without tenant (backwards compatibility)
                user = User.objects.get(
                    phone_number=normalized_phone, tenant__isnull=True
                )
            return user, False
        except User.DoesNotExist:
            # Create new user with normalized phone number
            user_data = {
                "phone_number": normalized_phone,
                "max_devices": 1,
                "tenant": tenant,  # Associate with tenant
                **kwargs,
            }
            user = User.objects.create(**user_data)
            return user, True

    except ValueError as e:
        raise ValueError(f"Cannot process phone number {phone_number}: {e}")


def find_user_by_phone(phone_number, tenant=None):
    """
    Find user by phone number with normalization (TENANT-AWARE)

    Args:
        phone_number (str): Phone number in any format
        tenant: Tenant instance (optional, for multi-tenant mode)

    Returns:
        User or None: User instance if found, None otherwise
    """
    from .models import User

    try:
        normalized_phone = normalize_phone_number(phone_number)
        if tenant:
            return User.objects.get(phone_number=normalized_phone, tenant=tenant)
        else:
            # Legacy: try without tenant filter first, then with null tenant
            try:
                return User.objects.get(
                    phone_number=normalized_phone, tenant__isnull=True
                )
            except User.DoesNotExist:
                # Fallback: return first match (for backwards compatibility)
                return User.objects.filter(phone_number=normalized_phone).first()
    except (User.DoesNotExist, ValueError):
        return None
