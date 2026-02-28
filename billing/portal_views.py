"""
Tenant Portal Views for Kitonga Wi-Fi Billing System
Phase 3: Self-service dashboard, router wizard, analytics, and white-label customization
"""

import uuid
from datetime import timedelta
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.conf import settings
from django.http import HttpResponse
from django.db.models import Sum, Count, Q
from django.db import transaction, models
from django.contrib.auth.models import User as DjangoUser
import logging

from .models import (
    Tenant,
    Router,
    Location,
    TenantStaff,
    Bundle,
    User,
    Payment,
    Voucher,
    TenantPayout,
    TenantVPNConfig,
    RemoteUser,
    RemoteAccessPlan,
    RemoteAccessLog,
    RemoteAccessPayment,
)
from .serializers import (
    RouterWizardSerializer,
    RouterConfigSerializer,
    HotspotAutoConfigSerializer,
    BrandingUpdateSerializer,
    CustomDomainSerializer,
    AnalyticsQuerySerializer,
    ExportRequestSerializer,
    TenantSettingsSerializer,
    StaffInviteSerializer,
    StaffUpdateSerializer,
    LocationSerializer,
    BundleSerializer,
    TenantStaffSerializer,
    TenantVPNConfigSerializer,
    TenantVPNConfigCreateSerializer,
    RemoteAccessPlanSerializer,
    RemoteAccessPlanCreateSerializer,
    RemoteUserSerializer,
    RemoteUserCreateSerializer,
    RemoteUserUpdateSerializer,
    RemoteAccessLogSerializer,
    RemoteAccessPaymentSerializer,
    RemoteUserPaymentInitiateSerializer,
)
from .permissions import TenantAPIKeyPermission, TenantOrAdminPermission
from .analytics import TenantAnalytics, ComparisonAnalytics, ExportManager
from .router_wizard import RouterWizard, RouterHealthChecker
from .branding import BrandingManager, ThemeGenerator, CaptivePortalGenerator

logger = logging.getLogger(__name__)


# =============================================================================
# TENANT DASHBOARD
# =============================================================================


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_dashboard(request):
    """
    Get comprehensive tenant dashboard data
    Includes overview stats, trends, and quick insights
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found. Use X-API-Key header."},
            status=status.HTTP_403_FORBIDDEN,
        )

    analytics = TenantAnalytics(tenant)

    try:
        dashboard_data = analytics.get_dashboard_summary()

        return Response(
            {
                "success": True,
                "tenant": {
                    "id": str(tenant.id),
                    "slug": tenant.slug,
                    "business_name": tenant.business_name,
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
                },
                "dashboard": dashboard_data,
            }
        )
    except Exception as e:
        logger.error(f"Dashboard error for {tenant.slug}: {e}")
        return Response(
            {"success": False, "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_realtime_stats(request):
    """
    Get real-time statistics for live dashboard updates
    Lightweight endpoint for polling
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    analytics = TenantAnalytics(tenant)

    return Response({"success": True, "data": analytics.get_real_time_stats()})


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_comparison(request):
    """
    Get period comparison analytics (week over week, month over month)
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    comparison = ComparisonAnalytics(tenant)

    return Response(
        {
            "success": True,
            "week_over_week": comparison.week_over_week(),
            "month_over_month": comparison.month_over_month(),
        }
    )


# =============================================================================
# ANALYTICS AND REPORTING
# =============================================================================


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_revenue_analytics(request):
    """
    Get detailed revenue analytics
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = AnalyticsQuerySerializer(data=request.query_params)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    analytics = TenantAnalytics(tenant)

    report = analytics.get_revenue_report(
        start_date=serializer.validated_data.get("start_date"),
        end_date=serializer.validated_data.get("end_date"),
        group_by=serializer.validated_data.get("group_by", "day"),
    )

    return Response({"success": True, "report": report})


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_user_analytics(request):
    """
    Get user analytics including retention and growth
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    analytics = TenantAnalytics(tenant)

    return Response({"success": True, "data": analytics.get_user_analytics()})


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_voucher_analytics(request):
    """
    Get voucher usage analytics
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    analytics = TenantAnalytics(tenant)

    return Response({"success": True, "data": analytics.get_voucher_analytics()})


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_generate_vouchers(request):
    """
    Generate voucher codes for tenant and optionally send via SMS (in Swahili)

    Request Body:
    {
        "quantity": 10,              # Number of vouchers (1-100)
        "duration_hours": 24,        # Duration in hours
        "batch_id": "BATCH-001",     # Optional batch identifier
        "notes": "Holiday promo",    # Optional notes
        "phone_number": "0712345678" # Optional: Send vouchers via SMS (will be formatted to 255...)
    }

    Phone number formats accepted:
    - 0712345678 → 255712345678
    - 255712345678 → 255712345678
    - 712345678 → 255712345678
    """
    import uuid
    from .nextsms import NextSMSAPI
    from .models import SMSLog

    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Validate input
    quantity = request.data.get("quantity", 1)
    duration_hours = request.data.get("duration_hours")
    batch_id = request.data.get("batch_id", f"BATCH-{uuid.uuid4().hex[:8].upper()}")
    notes = request.data.get("notes", "")
    phone_number = request.data.get("phone_number")

    # Validate quantity
    try:
        quantity = int(quantity)
        if quantity < 1 or quantity > 100:
            return Response(
                {"success": False, "message": "Quantity must be between 1 and 100"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    except (ValueError, TypeError):
        return Response(
            {"success": False, "message": "Invalid quantity"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate duration
    if not duration_hours:
        return Response(
            {"success": False, "message": "duration_hours is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        duration_hours = int(duration_hours)
        if duration_hours < 1:
            return Response(
                {"success": False, "message": "Duration must be at least 1 hour"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    except (ValueError, TypeError):
        return Response(
            {"success": False, "message": "Invalid duration_hours"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Format phone number to start with 255 (Tanzania format)
    normalized_phone = None
    if phone_number:
        # Remove spaces, dashes, and other characters
        phone_clean = "".join(filter(str.isdigit, str(phone_number)))

        # Handle different formats
        if phone_clean.startswith("0"):
            # Remove leading 0 and add 255
            phone_clean = "255" + phone_clean[1:]
        elif phone_clean.startswith("255"):
            # Already in correct format
            pass
        elif len(phone_clean) == 9:
            # Just the number without prefix, add 255
            phone_clean = "255" + phone_clean
        else:
            return Response(
                {
                    "success": False,
                    "message": "Invalid phone number format. Should start with 0 or 255",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate length (255 + 9 digits = 12 total)
        if len(phone_clean) != 12:
            return Response(
                {
                    "success": False,
                    "message": "Invalid phone number. Must have 9 digits after 255",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        normalized_phone = phone_clean

    # Generate vouchers for this tenant
    vouchers_created = []
    voucher_objects = []
    for _ in range(quantity):
        voucher = Voucher.objects.create(
            code=Voucher.generate_code(),
            duration_hours=duration_hours,
            batch_id=batch_id,
            created_by=f"tenant:{tenant.slug}",
            notes=notes,
            tenant=tenant,  # Associate with tenant
        )
        voucher_objects.append(voucher)
        vouchers_created.append(
            {
                "id": voucher.id,
                "code": voucher.code,
                "duration_hours": voucher.duration_hours,
                "is_used": voucher.is_used,
                "created_at": voucher.created_at.isoformat(),
            }
        )

    logger.info(
        f"Tenant {tenant.slug} generated {quantity} vouchers in batch {batch_id}"
    )

    # Send SMS if phone number provided (always in Swahili)
    sms_result = {"sent": False, "phone_number": None}
    if normalized_phone:
        try:
            nextsms = NextSMSAPI()

            # Build duration text in Swahili
            if duration_hours < 24:
                duration_text = f"saa {duration_hours}"
            elif duration_hours == 24:
                duration_text = "siku 1"
            elif duration_hours < 168:  # Less than a week
                days = duration_hours // 24
                duration_text = f"siku {days}"
            elif duration_hours == 168:
                duration_text = "wiki 1"
            elif duration_hours < 720:
                weeks = duration_hours // 168
                duration_text = f"wiki {weeks}"
            else:
                months = duration_hours // 720
                duration_text = f"mwezi {months}" if months == 1 else f"miezi {months}"

            # Create voucher codes list
            voucher_codes = [v.code for v in voucher_objects]

            # Always Swahili message
            if quantity == 1:
                message = (
                    f"Habari! Umepokea voucher ya Wi-Fi kutoka {tenant.business_name}.\n"
                    f"Code: {voucher_codes[0]}\n"
                    f"Muda: {duration_text}\n"
                    f"Ingia kwenye portal na utumie code hii kupata internet. Karibu!"
                )
            else:
                codes_text = "\n".join(voucher_codes[:10])  # Limit to 10 codes per SMS
                message = (
                    f"Habari! Umepokea voucher {quantity} za Wi-Fi kutoka {tenant.business_name}.\n"
                    f"Muda: {duration_text} kila moja\n"
                    f"Codes:\n{codes_text}"
                )
                if quantity > 10:
                    message += f"\n...na {quantity - 10} zaidi"

            # Send SMS
            result = nextsms.send_sms(normalized_phone, message, f"VOUCHER-{batch_id}")

            # Log SMS
            SMSLog.objects.create(
                phone_number=normalized_phone,
                message=message,
                sms_type="voucher",
                success=result.get("success", False),
                response_data=result.get("data"),
            )

            sms_result = {
                "sent": result.get("success", False),
                "phone_number": normalized_phone,
                "message": (
                    "Voucher SMS sent successfully"
                    if result.get("success")
                    else "SMS sending failed"
                ),
            }

            logger.info(
                f"Voucher SMS sent to {normalized_phone}: {result.get('success')}"
            )

        except Exception as e:
            logger.error(f"Failed to send voucher SMS to {normalized_phone}: {e}")
            sms_result = {
                "sent": False,
                "phone_number": normalized_phone,
                "error": str(e),
            }

    return Response(
        {
            "success": True,
            "message": f"Successfully generated {quantity} vouchers",
            "batch_id": batch_id,
            "vouchers": vouchers_created,
            "summary": {
                "total_generated": quantity,
                "duration_hours": duration_hours,
                "batch_id": batch_id,
            },
            "sms": sms_result,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_list_vouchers(request):
    """
    List all vouchers for tenant with filtering options

    Query Parameters:
    - batch_id: Filter by batch ID
    - is_used: Filter by usage status (true/false)
    - page: Page number (default 1)
    - page_size: Items per page (default 50, max 100)
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Get vouchers for this tenant
    vouchers = Voucher.objects.filter(tenant=tenant).order_by("-created_at")

    # Apply filters
    batch_id = request.query_params.get("batch_id")
    if batch_id:
        vouchers = vouchers.filter(batch_id=batch_id)

    is_used = request.query_params.get("is_used")
    if is_used is not None:
        is_used_bool = is_used.lower() == "true"
        vouchers = vouchers.filter(is_used=is_used_bool)

    # Pagination
    page = int(request.query_params.get("page", 1))
    page_size = min(int(request.query_params.get("page_size", 50)), 100)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size

    total_count = vouchers.count()
    vouchers_page = vouchers[start_idx:end_idx]

    voucher_list = []
    for v in vouchers_page:
        voucher_list.append(
            {
                "id": v.id,
                "code": v.code,
                "duration_hours": v.duration_hours,
                "batch_id": v.batch_id,
                "is_used": v.is_used,
                "used_by": v.used_by.phone_number if v.used_by else None,
                "used_at": v.used_at.isoformat() if v.used_at else None,
                "notes": v.notes,
                "created_at": v.created_at.isoformat(),
            }
        )

    # Get batch summary
    batches = (
        Voucher.objects.filter(tenant=tenant)
        .values("batch_id")
        .annotate(total=Count("id"), used=Count("id", filter=models.Q(is_used=True)))
        .order_by("-batch_id")[:10]
    )

    return Response(
        {
            "success": True,
            "vouchers": voucher_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": (total_count + page_size - 1) // page_size,
            },
            "recent_batches": list(batches),
        }
    )


@api_view(["DELETE"])
@permission_classes([TenantAPIKeyPermission])
def portal_delete_voucher(request, voucher_id):
    """
    Delete a single voucher (only if not used)

    URL: DELETE /api/portal/vouchers/<voucher_id>/
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        voucher = Voucher.objects.get(id=voucher_id, tenant=tenant)
    except Voucher.DoesNotExist:
        return Response(
            {"success": False, "message": "Voucher not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Don't allow deleting used vouchers
    if voucher.is_used:
        return Response(
            {
                "success": False,
                "message": "Cannot delete a voucher that has already been used",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    voucher_code = voucher.code
    voucher.delete()

    logger.info(f"Tenant {tenant.slug} deleted voucher {voucher_code}")

    return Response(
        {"success": True, "message": f"Voucher {voucher_code} deleted successfully"}
    )


@api_view(["DELETE"])
@permission_classes([TenantAPIKeyPermission])
def portal_delete_voucher_batch(request):
    """
    Delete multiple vouchers by batch_id or list of IDs (only unused vouchers)

    Request Body:
    {
        "batch_id": "BATCH-001"    # Delete all unused vouchers in this batch
    }
    OR
    {
        "voucher_ids": [1, 2, 3]   # Delete specific vouchers by ID
    }
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    batch_id = request.data.get("batch_id")
    voucher_ids = request.data.get("voucher_ids", [])

    if not batch_id and not voucher_ids:
        return Response(
            {"success": False, "message": "Please provide batch_id or voucher_ids"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Get vouchers to delete
    if batch_id:
        vouchers = Voucher.objects.filter(
            tenant=tenant, batch_id=batch_id, is_used=False
        )
    else:
        vouchers = Voucher.objects.filter(
            tenant=tenant, id__in=voucher_ids, is_used=False
        )

    count = vouchers.count()

    if count == 0:
        return Response(
            {
                "success": False,
                "message": "No vouchers available to delete (they may have been used already)",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # Delete vouchers
    vouchers.delete()

    logger.info(
        f"Tenant {tenant.slug} deleted {count} vouchers (batch: {batch_id}, ids: {voucher_ids})"
    )

    return Response(
        {
            "success": True,
            "message": f"{count} voucher(s) deleted successfully",
            "deleted_count": count,
        }
    )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_export_data(request):
    """
    Export tenant data (payments, users, vouchers) as CSV
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = ExportRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    export_mgr = ExportManager(tenant)
    export_type = serializer.validated_data["export_type"]

    try:
        if export_type == "payments":
            csv_data = export_mgr.export_payments_csv(
                start_date=serializer.validated_data.get("start_date"),
                end_date=serializer.validated_data.get("end_date"),
            )
            filename = f"{tenant.slug}_payments.csv"
        elif export_type == "users":
            csv_data = export_mgr.export_users_csv()
            filename = f"{tenant.slug}_users.csv"
        elif export_type == "vouchers":
            csv_data = export_mgr.export_vouchers_csv(
                batch_id=serializer.validated_data.get("batch_id")
            )
            filename = f"{tenant.slug}_vouchers.csv"
        else:
            return Response(
                {"success": False, "message": "Invalid export type"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response = HttpResponse(csv_data, content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        logger.error(f"Export error for {tenant.slug}: {e}")
        return Response(
            {"success": False, "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# =============================================================================
# ROUTER CONFIGURATION WIZARD
# =============================================================================


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_router_test_connection(request):
    """
    Test connection to a MikroTik router
    Step 1 of the router setup wizard
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = RouterWizardSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    wizard = RouterWizard(tenant)

    result = wizard.test_connection(
        host=serializer.validated_data["host"],
        port=serializer.validated_data.get("port", 8728),
        username=serializer.validated_data.get("username", "admin"),
        password=serializer.validated_data.get("password", ""),
        use_ssl=serializer.validated_data.get("use_ssl", False),
    )

    return Response(result)


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_router_save_config(request):
    """
    Save router configuration
    Step 2 of the router setup wizard
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = RouterConfigSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    wizard = RouterWizard(tenant)

    success, message, router = wizard.save_router_config(
        name=serializer.validated_data["name"],
        host=serializer.validated_data["host"],
        port=serializer.validated_data.get("port", 8728),
        username=serializer.validated_data.get("username", "admin"),
        password=serializer.validated_data.get("password", ""),
        use_ssl=serializer.validated_data.get("use_ssl", False),
        location_id=serializer.validated_data.get("location_id"),
        hotspot_interface=serializer.validated_data.get("hotspot_interface", "bridge"),
        hotspot_profile=serializer.validated_data.get("hotspot_profile", "default"),
    )

    if success:
        return Response(
            {
                "success": True,
                "message": message,
                "router": {
                    "id": router.id,
                    "name": router.name,
                    "host": router.host,
                    "status": router.status,
                },
            },
            status=status.HTTP_201_CREATED,
        )
    else:
        return Response(
            {"success": False, "message": message}, status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_router_auto_configure(request):
    """
    Auto-configure hotspot on a router
    Step 3 of the router setup wizard (optional)
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = HotspotAutoConfigSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        router = Router.objects.get(
            id=serializer.validated_data["router_id"], tenant=tenant
        )
    except Router.DoesNotExist:
        return Response(
            {"success": False, "message": "Router not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    wizard = RouterWizard(tenant, router)

    # First establish connection
    test_result = wizard.test_connection(
        host=router.host,
        port=router.port,
        username=router.username,
        password=router.password,
        use_ssl=router.use_ssl,
    )

    if not test_result.get("success"):
        return Response(
            {
                "success": False,
                "message": "Could not connect to router",
                "error": test_result.get("error"),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Perform auto-configuration
    result = wizard.auto_configure_hotspot(
        interface=serializer.validated_data.get("interface", "bridge"),
        server_name=serializer.validated_data.get("server_name", "kitonga-hotspot"),
        profile_name=serializer.validated_data.get("profile_name", "kitonga-profile"),
    )

    return Response(result)


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_router_generate_html(request, router_id):
    """
    Generate custom hotspot HTML pages for a router
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

    wizard = RouterWizard(tenant, router)
    result = wizard.upload_hotspot_html()

    return Response(result)


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_router_health(request):
    """
    Check health of all tenant routers
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    health_checker = RouterHealthChecker(tenant)

    return Response(
        {
            "success": True,
            "summary": health_checker.get_summary(),
            "routers": health_checker.check_all_routers(),
        }
    )


# =============================================================================
# ROUTER MONITORING (Business/Enterprise Feature)
# =============================================================================


def check_router_monitoring_permission(tenant):
    """Check if tenant has access to router monitoring features"""
    if not tenant.subscription_plan:
        return False, "No subscription plan"
    # Available for Business and Enterprise plans
    plan_name = tenant.subscription_plan.name.lower()
    if "business" in plan_name or "enterprise" in plan_name:
        return True, None
    return False, "Router monitoring requires Business or Enterprise plan"


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_router_monitoring(request, router_id):
    """
    Get real-time monitoring data for a specific router
    """
    from .models import Router
    from .router_monitoring import RouterMonitor

    tenant = request.tenant

    # Check permission
    allowed, error = check_router_monitoring_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        router = Router.objects.get(id=router_id, tenant=tenant)
    except Router.DoesNotExist:
        return Response(
            {"success": False, "error": "Router not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    monitor = RouterMonitor(router)
    status_data = monitor.get_current_status()

    return Response(
        {
            "success": True,
            "router": status_data,
        }
    )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_router_active_users(request, router_id):
    """
    Get active users connected to a specific router (Tenant Portal)
    Allows tenants to see who is currently connected to their MikroTik router
    """
    from .models import Router, User
    from .mikrotik import get_tenant_mikrotik_api

    tenant = request.tenant

    try:
        # Ensure router belongs to this tenant
        router = Router.objects.get(id=router_id, tenant=tenant)
    except Router.DoesNotExist:
        return Response(
            {"success": False, "error": "Router not found or access denied"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Connect to MikroTik
    api = get_tenant_mikrotik_api(router)
    if not api:
        return Response(
            {
                "success": False,
                "error": f"Cannot connect to router {router.name}. Please check router configuration.",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    try:
        # Get active hotspot users from MikroTik
        active = api.get_resource("/ip/hotspot/active").get()

        users_data = []
        for session in active:
            username = session.get("user", "")

            # Find user in database
            db_info = None
            try:
                db_user = User.objects.get(phone_number=username, tenant=tenant)
                db_info = {
                    "user_id": db_user.id,
                    "is_active": db_user.is_active,
                    "has_active_access": db_user.has_active_access(),
                    "access_expires_at": (
                        db_user.paid_until.isoformat() if db_user.paid_until else None
                    ),
                    "time_remaining": (
                        str(db_user.paid_until - timezone.now())
                        if db_user.paid_until and db_user.paid_until > timezone.now()
                        else None
                    ),
                }
            except User.DoesNotExist:
                # User session exists in MikroTik but not in database
                db_info = {
                    "user_id": None,
                    "is_active": False,
                    "has_active_access": False,
                    "note": "User not found in database",
                }

            users_data.append(
                {
                    "session_id": session.get(".id", ""),
                    "username": username,
                    "mac_address": session.get("mac-address", ""),
                    "ip_address": session.get("address", ""),
                    "uptime": session.get("uptime", ""),
                    "bytes_in": session.get("bytes-in", "0"),
                    "bytes_out": session.get("bytes-out", "0"),
                    "idle_time": session.get("idle-time", ""),
                    "login_time": session.get("login-by", ""),
                    "database_info": db_info,
                }
            )

        return Response(
            {
                "success": True,
                "router": {
                    "id": router.id,
                    "name": router.name,
                    "host": router.host,
                    "status": router.status,
                },
                "active_users": users_data,
                "total_count": len(users_data),
                "timestamp": timezone.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(
            f"Error getting active users for router {router_id} (tenant: {tenant.slug}): {str(e)}"
        )
        return Response(
            {
                "success": False,
                "error": f"Error retrieving active users from MikroTik: {str(e)}",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_router_disconnect_user(request, router_id):
    """
    Disconnect a specific user from a specific router (Tenant Portal)

    Request Body:
    {
        "username": "+255712345678",  # Required: phone number
        "mac_address": "AA:BB:CC:DD:EE:FF"  # Optional: specific device MAC
    }
    """
    from .models import Router, User
    from .mikrotik import get_tenant_mikrotik_api, disconnect_user_with_api

    tenant = request.tenant

    try:
        # Ensure router belongs to this tenant
        router = Router.objects.get(id=router_id, tenant=tenant)
    except Router.DoesNotExist:
        return Response(
            {"success": False, "error": "Router not found or access denied"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get request data
    username = request.data.get("username")
    mac_address = request.data.get("mac_address")  # Optional

    if not username:
        return Response(
            {"success": False, "error": "username is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Verify user belongs to this tenant
    try:
        user = User.objects.get(phone_number=username, tenant=tenant)
    except User.DoesNotExist:
        return Response(
            {
                "success": False,
                "error": "User not found or does not belong to your tenant",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # Connect to MikroTik
    api = get_tenant_mikrotik_api(router)
    if not api:
        return Response(
            {
                "success": False,
                "error": f"Cannot connect to router {router.name}. Please check router configuration.",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    try:
        # Disconnect user from this specific router
        result = disconnect_user_with_api(
            api=api, username=username, mac_address=mac_address
        )

        if result.get("success") or result.get("session_removed"):
            logger.info(
                f"Tenant {tenant.slug} disconnected user {username} from router {router.name} (ID: {router_id})"
            )

            return Response(
                {
                    "success": True,
                    "message": f"User {username} disconnected from {router.name}",
                    "router": {
                        "id": router.id,
                        "name": router.name,
                    },
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
                    "error": f"Failed to disconnect user from {router.name}",
                    "details": result.get("errors", []),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except Exception as e:
        logger.error(
            f"Error disconnecting user {username} from router {router_id} (tenant: {tenant.slug}): {str(e)}"
        )
        return Response(
            {
                "success": False,
                "error": f"Error disconnecting user: {str(e)}",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_router_collect_metrics(request, router_id):
    """
    Trigger metrics collection for a specific router and save snapshot
    """
    from .models import Router
    from .router_monitoring import RouterMonitor

    tenant = request.tenant

    # Check permission
    allowed, error = check_router_monitoring_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        router = Router.objects.get(id=router_id, tenant=tenant)
    except Router.DoesNotExist:
        return Response(
            {"success": False, "error": "Router not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    monitor = RouterMonitor(router)
    snapshot = monitor.collect_metrics()

    if snapshot and snapshot.is_reachable:
        return Response(
            {
                "success": True,
                "message": "Metrics collected successfully",
                "snapshot": {
                    "id": snapshot.id,
                    "cpu_load": snapshot.cpu_load,
                    "memory_percent": snapshot.memory_percent,
                    "disk_percent": snapshot.disk_percent,
                    "active_users": snapshot.active_hotspot_users,
                    "uptime_seconds": snapshot.uptime,
                    "created_at": snapshot.created_at.isoformat(),
                },
            }
        )
    else:
        return Response(
            {
                "success": False,
                "error": (
                    snapshot.error_message if snapshot else "Failed to collect metrics"
                ),
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_router_monitoring_history(request, router_id):
    """
    Get historical monitoring snapshots for a router
    """
    from .models import Router, RouterMonitoringSnapshot

    tenant = request.tenant

    # Check permission
    allowed, error = check_router_monitoring_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        router = Router.objects.get(id=router_id, tenant=tenant)
    except Router.DoesNotExist:
        return Response(
            {"success": False, "error": "Router not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get query params
    hours = int(request.query_params.get("hours", 24))
    limit = min(int(request.query_params.get("limit", 100)), 500)

    since = timezone.now() - timedelta(hours=hours)

    snapshots = RouterMonitoringSnapshot.objects.filter(
        router=router, created_at__gte=since
    ).order_by("-created_at")[:limit]

    data = [
        {
            "timestamp": s.created_at.isoformat(),
            "is_reachable": s.is_reachable,
            "cpu_load": s.cpu_load,
            "memory_percent": s.memory_percent,
            "disk_percent": s.disk_percent,
            "active_users": s.active_hotspot_users,
            "rx_mb": round(s.rx_bytes / (1024 * 1024), 2),
            "tx_mb": round(s.tx_bytes / (1024 * 1024), 2),
            "uptime_seconds": s.uptime,
        }
        for s in snapshots
    ]

    return Response(
        {
            "success": True,
            "router_id": router_id,
            "router_name": router.name,
            "period_hours": hours,
            "snapshots": data,
        }
    )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_router_monitoring_all(request):
    """
    Get monitoring status for all tenant routers
    """
    from .models import Router
    from .router_monitoring import RouterMonitor

    tenant = request.tenant

    # Check permission
    allowed, error = check_router_monitoring_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    routers = Router.objects.filter(tenant=tenant, is_active=True)

    router_status = []
    for router in routers:
        monitor = RouterMonitor(router)
        status_data = monitor.get_current_status()
        router_status.append(status_data)

    # Summary stats
    online_count = sum(1 for r in router_status if r.get("is_reachable"))
    total_users = sum(
        r.get("metrics", {}).get("active_users", 0) for r in router_status
    )

    return Response(
        {
            "success": True,
            "summary": {
                "total_routers": len(router_status),
                "online": online_count,
                "offline": len(router_status) - online_count,
                "total_active_users": total_users,
            },
            "routers": router_status,
        }
    )


# =============================================================================
# BANDWIDTH REPORTS (Business/Enterprise Feature)
# =============================================================================


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_router_bandwidth(request, router_id):
    """
    Get bandwidth usage report for a specific router
    """
    from .models import Router
    from .router_monitoring import BandwidthReporter

    tenant = request.tenant

    # Check permission
    allowed, error = check_router_monitoring_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        router = Router.objects.get(id=router_id, tenant=tenant)
    except Router.DoesNotExist:
        return Response(
            {"success": False, "error": "Router not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    reporter = BandwidthReporter(router)

    # Get query params
    report_type = request.query_params.get("type", "daily")  # hourly, daily
    days = int(request.query_params.get("days", 7))

    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)

    if report_type == "hourly":
        data = reporter.get_hourly_report(start_date, end_date)
    else:
        data = reporter.get_daily_report(start_date, end_date)

    summary = reporter.get_summary(days)

    return Response(
        {
            "success": True,
            "router_id": router_id,
            "router_name": router.name,
            "report_type": report_type,
            "period_days": days,
            "summary": summary,
            "data": data,
        }
    )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_bandwidth_summary(request):
    """
    Get bandwidth summary across all tenant routers
    """
    from .models import Router, RouterBandwidthLog
    from django.db.models import Sum, Max, Avg

    tenant = request.tenant

    # Check permission
    allowed, error = check_router_monitoring_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    days = int(request.query_params.get("days", 30))
    start_date = timezone.now() - timedelta(days=days)

    routers = Router.objects.filter(tenant=tenant, is_active=True)

    router_summaries = []
    total_rx = 0
    total_tx = 0
    peak_users = 0

    for router in routers:
        stats = RouterBandwidthLog.objects.filter(
            router=router, hour_start__gte=start_date
        ).aggregate(
            rx=Sum("rx_bytes"),
            tx=Sum("tx_bytes"),
            peak=Max("peak_users"),
            avg_users=Avg("avg_users"),
        )

        rx = stats["rx"] or 0
        tx = stats["tx"] or 0
        total_rx += rx
        total_tx += tx
        peak_users = max(peak_users, stats["peak"] or 0)

        router_summaries.append(
            {
                "router_id": router.id,
                "router_name": router.name,
                "location": router.location.name if router.location else None,
                "rx_gb": round(rx / (1024 * 1024 * 1024), 2),
                "tx_gb": round(tx / (1024 * 1024 * 1024), 2),
                "total_gb": round((rx + tx) / (1024 * 1024 * 1024), 2),
                "peak_users": stats["peak"] or 0,
                "avg_users": round(stats["avg_users"] or 0, 1),
            }
        )

    return Response(
        {
            "success": True,
            "period_days": days,
            "total_summary": {
                "total_rx_gb": round(total_rx / (1024 * 1024 * 1024), 2),
                "total_tx_gb": round(total_tx / (1024 * 1024 * 1024), 2),
                "total_gb": round((total_rx + total_tx) / (1024 * 1024 * 1024), 2),
                "daily_avg_gb": round(
                    (total_rx + total_tx) / (1024 * 1024 * 1024) / days, 2
                ),
                "peak_concurrent_users": peak_users,
            },
            "routers": router_summaries,
        }
    )


# =============================================================================
# HOTSPOT PAGE CUSTOMIZATION (Per Router)
# =============================================================================


@api_view(["GET", "PUT"])
@permission_classes([TenantAPIKeyPermission])
def portal_router_hotspot_customization(request, router_id):
    """
    GET: Get hotspot page customization for a router
    PUT: Update hotspot page customization
    """
    from .models import Router, RouterHotspotCustomization

    tenant = request.tenant

    # Check permission (available for all paid plans)
    if not tenant.subscription_plan:
        return Response(
            {"success": False, "error": "No subscription plan"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        router = Router.objects.get(id=router_id, tenant=tenant)
    except Router.DoesNotExist:
        return Response(
            {"success": False, "error": "Router not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get or create customization
    customization, created = RouterHotspotCustomization.objects.get_or_create(
        router=router
    )

    if request.method == "GET":
        return Response(
            {
                "success": True,
                "router_id": router_id,
                "router_name": router.name,
                "customization": {
                    # Text content
                    "page_title": customization.page_title,
                    "welcome_message": customization.welcome_message,
                    "footer_text": customization.footer_text,
                    # Branding
                    "logo_url": customization.logo_url,
                    "background_image_url": customization.background_image_url,
                    "favicon_url": customization.favicon_url,
                    # Colors
                    "primary_color": customization.primary_color,
                    "secondary_color": customization.secondary_color,
                    "background_color": customization.background_color,
                    "text_color": customization.text_color,
                    "button_color": customization.button_color,
                    "button_text_color": customization.button_text_color,
                    # Layout
                    "show_logo": customization.show_logo,
                    "show_bundles": customization.show_bundles,
                    "show_social_login": customization.show_social_login,
                    "show_terms_link": customization.show_terms_link,
                    "show_support_contact": customization.show_support_contact,
                    # Contact
                    "terms_url": customization.terms_url,
                    "support_email": customization.support_email,
                    "support_phone": customization.support_phone,
                    # Custom code
                    "custom_css": customization.custom_css,
                    "custom_js": customization.custom_js,
                    "header_html": customization.header_html,
                    "footer_html": customization.footer_html,
                    # Template
                    "use_custom_template": customization.use_custom_template,
                    "custom_login_html": customization.custom_login_html,
                    "custom_logout_html": customization.custom_logout_html,
                    "custom_status_html": customization.custom_status_html,
                    # Metadata
                    "updated_at": customization.updated_at.isoformat(),
                },
            }
        )

    elif request.method == "PUT":
        data = request.data

        # Update text fields
        if "page_title" in data:
            customization.page_title = data["page_title"]
        if "welcome_message" in data:
            customization.welcome_message = data["welcome_message"]
        if "footer_text" in data:
            customization.footer_text = data["footer_text"]

        # Update branding
        if "logo_url" in data:
            customization.logo_url = data["logo_url"]
        if "background_image_url" in data:
            customization.background_image_url = data["background_image_url"]
        if "favicon_url" in data:
            customization.favicon_url = data["favicon_url"]

        # Update colors
        color_fields = [
            "primary_color",
            "secondary_color",
            "background_color",
            "text_color",
            "button_color",
            "button_text_color",
        ]
        for field in color_fields:
            if field in data:
                setattr(customization, field, data[field])

        # Update layout options
        layout_fields = [
            "show_logo",
            "show_bundles",
            "show_social_login",
            "show_terms_link",
            "show_support_contact",
        ]
        for field in layout_fields:
            if field in data:
                setattr(customization, field, data[field])

        # Update contact
        if "terms_url" in data:
            customization.terms_url = data["terms_url"]
        if "support_email" in data:
            customization.support_email = data["support_email"]
        if "support_phone" in data:
            customization.support_phone = data["support_phone"]

        # Update custom code (check plan for advanced features)
        plan_name = tenant.subscription_plan.name.lower()
        can_use_custom_code = "business" in plan_name or "enterprise" in plan_name

        if can_use_custom_code:
            if "custom_css" in data:
                customization.custom_css = data["custom_css"]
            if "custom_js" in data:
                customization.custom_js = data["custom_js"]
            if "header_html" in data:
                customization.header_html = data["header_html"]
            if "footer_html" in data:
                customization.footer_html = data["footer_html"]
            if "use_custom_template" in data:
                customization.use_custom_template = data["use_custom_template"]
            if "custom_login_html" in data:
                customization.custom_login_html = data["custom_login_html"]
            if "custom_logout_html" in data:
                customization.custom_logout_html = data["custom_logout_html"]
            if "custom_status_html" in data:
                customization.custom_status_html = data["custom_status_html"]

        customization.save()

        logger.info(
            f"Tenant {tenant.slug} updated hotspot customization for router {router.name}"
        )

        return Response(
            {
                "success": True,
                "message": "Hotspot customization updated",
            }
        )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_router_hotspot_preview(request, router_id):
    """
    Generate a preview of the hotspot login page HTML
    """
    from .models import Router, RouterHotspotCustomization

    tenant = request.tenant

    try:
        router = Router.objects.get(id=router_id, tenant=tenant)
    except Router.DoesNotExist:
        return Response(
            {"success": False, "error": "Router not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get customization or defaults
    try:
        customization = router.hotspot_customization
    except RouterHotspotCustomization.DoesNotExist:
        customization = None

    # Build preview HTML
    html = generate_hotspot_preview_html(tenant, router, customization)

    return Response(
        {
            "success": True,
            "router_id": router_id,
            "html": html,
        }
    )


def generate_hotspot_preview_html(tenant, router, customization):
    """Generate preview HTML for hotspot page"""
    # Default values
    page_title = tenant.business_name
    welcome_message = f"Welcome to {tenant.business_name} WiFi"
    primary_color = "#3B82F6"
    background_color = "#F3F4F6"
    text_color = "#1F2937"
    button_color = "#3B82F6"
    button_text_color = "#FFFFFF"
    logo_url = ""
    custom_css = ""

    if customization:
        page_title = customization.page_title or page_title
        welcome_message = customization.welcome_message or welcome_message
        primary_color = customization.primary_color or primary_color
        background_color = customization.background_color or background_color
        text_color = customization.text_color or text_color
        button_color = customization.button_color or button_color
        button_text_color = customization.button_text_color or button_text_color
        logo_url = customization.logo_url or ""
        custom_css = customization.custom_css or ""

        # Check for custom template
        if customization.use_custom_template and customization.custom_login_html:
            return customization.custom_login_html

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: {background_color};
            color: {text_color};
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .container {{
            background: white;
            padding: 2rem;
            border-radius: 1rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            max-width: 400px;
            width: 90%;
            text-align: center;
        }}
        .logo {{ max-width: 150px; margin-bottom: 1rem; }}
        h1 {{ font-size: 1.5rem; margin-bottom: 0.5rem; color: {primary_color}; }}
        .welcome {{ margin-bottom: 1.5rem; color: #666; }}
        .form-group {{ margin-bottom: 1rem; text-align: left; }}
        label {{ display: block; margin-bottom: 0.25rem; font-weight: 500; }}
        input {{
            width: 100%;
            padding: 0.75rem;
            border: 1px solid #ddd;
            border-radius: 0.5rem;
            font-size: 1rem;
        }}
        input:focus {{ outline: none; border-color: {primary_color}; }}
        .btn {{
            width: 100%;
            padding: 0.75rem;
            background: {button_color};
            color: {button_text_color};
            border: none;
            border-radius: 0.5rem;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            margin-top: 0.5rem;
        }}
        .btn:hover {{ opacity: 0.9; }}
        .packages {{ margin-top: 1.5rem; text-align: left; }}
        .packages h3 {{ font-size: 1rem; margin-bottom: 0.75rem; }}
        .package {{
            padding: 0.75rem;
            border: 1px solid #ddd;
            border-radius: 0.5rem;
            margin-bottom: 0.5rem;
            display: flex;
            justify-content: space-between;
        }}
        {custom_css}
    </style>
</head>
<body>
    <div class="container">
        {"<img src='" + logo_url + "' alt='Logo' class='logo'>" if logo_url else ""}
        <h1>{page_title}</h1>
        <p class="welcome">{welcome_message}</p>
        
        <form>
            <div class="form-group">
                <label for="phone">Phone Number</label>
                <input type="tel" id="phone" placeholder="+255xxxxxxxxx">
            </div>
            <button type="submit" class="btn">Connect</button>
        </form>
        
        <div class="packages">
            <h3>Available Packages</h3>
            <div class="package">
                <span>1 Hour</span>
                <span>TZS 500</span>
            </div>
            <div class="package">
                <span>24 Hours</span>
                <span>TZS 2,000</span>
            </div>
            <div class="package">
                <span>7 Days</span>
                <span>TZS 10,000</span>
            </div>
        </div>
    </div>
</body>
</html>"""

    return html


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_router_deploy_hotspot(request, router_id):
    """
    Deploy customized hotspot pages to the router
    """
    from .models import Router, RouterHotspotCustomization
    from .mikrotik import get_tenant_mikrotik_api, safe_close

    tenant = request.tenant

    # Check permission (requires Business or Enterprise)
    allowed, error = check_router_monitoring_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        router = Router.objects.get(id=router_id, tenant=tenant)
    except Router.DoesNotExist:
        return Response(
            {"success": False, "error": "Router not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get customization
    try:
        customization = router.hotspot_customization
    except RouterHotspotCustomization.DoesNotExist:
        return Response(
            {"success": False, "error": "No customization configured for this router"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Generate HTML files
    login_html = generate_hotspot_preview_html(tenant, router, customization)

    # Note: In production, you would upload these files to the router
    # For now, return success with the generated HTML
    # Actual deployment would use RouterOS API to upload files to /hotspot folder

    logger.info(
        f"Tenant {tenant.slug} deployed hotspot customization to router {router.name}"
    )

    return Response(
        {
            "success": True,
            "message": "Hotspot pages generated. Manual upload to router required.",
            "files": {
                "login.html": (
                    login_html[:500] + "..." if len(login_html) > 500 else login_html
                ),
            },
            "instructions": [
                "1. Download the generated HTML files",
                "2. Connect to your router via Winbox or WebFig",
                "3. Navigate to Files > hotspot",
                "4. Upload the HTML files, replacing existing ones",
                "5. Test the hotspot login page",
            ],
        }
    )


# =============================================================================
# WHITE-LABEL CUSTOMIZATION
# =============================================================================


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_branding(request):
    """
    Get current tenant branding configuration
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    branding = BrandingManager(tenant)
    branding_data = branding.get_branding()

    # Build full URL for logo
    if branding_data.get("logo_url"):
        base_url = request.build_absolute_uri("/").rstrip("/")
        branding_data["logo_url"] = f"{base_url}{branding_data['logo_url']}"

    return Response({"success": True, "branding": branding_data})


@api_view(["PUT"])
@permission_classes([TenantAPIKeyPermission])
def portal_branding_update(request):
    """
    Update tenant branding colors and settings
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check if plan allows custom branding
    if tenant.subscription_plan and not tenant.subscription_plan.custom_branding:
        return Response(
            {
                "success": False,
                "message": "Custom branding not available in your subscription plan. Upgrade to unlock this feature.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = BrandingUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    branding = BrandingManager(tenant)

    # Update colors if provided
    if (
        "primary_color" in serializer.validated_data
        or "secondary_color" in serializer.validated_data
    ):
        success, message = branding.update_colors(
            primary_color=serializer.validated_data.get("primary_color"),
            secondary_color=serializer.validated_data.get("secondary_color"),
        )
        if not success:
            return Response(
                {"success": False, "message": message},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # Update business name if provided
    if "business_name" in serializer.validated_data:
        tenant.business_name = serializer.validated_data["business_name"]
        tenant.save()

    return Response(
        {
            "success": True,
            "message": "Branding updated successfully",
            "branding": branding.get_branding(),
        }
    )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
@parser_classes([MultiPartParser, FormParser])
def portal_logo_upload(request):
    """
    Upload tenant logo
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check if plan allows custom branding
    if tenant.subscription_plan and not tenant.subscription_plan.custom_branding:
        return Response(
            {
                "success": False,
                "message": "Custom branding not available in your subscription plan",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if "logo" not in request.FILES:
        return Response(
            {"success": False, "message": "No logo file provided"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    branding = BrandingManager(tenant)
    success, message = branding.update_logo(request.FILES["logo"])

    if success:
        # Build full URL with domain
        logo_url = None
        if tenant.logo:
            logo_path = tenant.logo.url
            # Get base URL from request
            base_url = request.build_absolute_uri("/").rstrip("/")
            logo_url = f"{base_url}{logo_path}"

        return Response(
            {
                "success": True,
                "message": message,
                "logo_url": logo_url,
                "logo_path": tenant.logo.url if tenant.logo else None,
            }
        )
    else:
        return Response(
            {"success": False, "message": message}, status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["DELETE"])
@permission_classes([TenantAPIKeyPermission])
def portal_logo_remove(request):
    """
    Remove tenant logo
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    branding = BrandingManager(tenant)
    success, message = branding.remove_logo()

    return Response({"success": success, "message": message})


@api_view(["GET", "POST", "DELETE"])
@permission_classes([TenantAPIKeyPermission])
def portal_custom_domain(request):
    """
    Manage custom domain configuration
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    branding = BrandingManager(tenant)

    if request.method == "GET":
        # Get current domain and DNS instructions
        return Response(
            {
                "success": True,
                "domain": tenant.custom_domain,
                "dns_instructions": branding.get_dns_instructions(),
                "validation": branding.validate_custom_domain(),
            }
        )

    elif request.method == "POST":
        # Set custom domain
        if tenant.subscription_plan and not tenant.subscription_plan.custom_domain:
            return Response(
                {
                    "success": False,
                    "message": "Custom domain not available in your subscription plan",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CustomDomainSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        success, message = branding.update_custom_domain(
            serializer.validated_data["domain"]
        )

        if success:
            return Response(
                {
                    "success": True,
                    "message": message,
                    "dns_instructions": branding.get_dns_instructions(),
                }
            )
        else:
            return Response(
                {"success": False, "message": message},
                status=status.HTTP_400_BAD_REQUEST,
            )

    elif request.method == "DELETE":
        # Remove custom domain
        success, message = branding.remove_custom_domain()
        return Response({"success": success, "message": message})


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_theme_css(request):
    """
    Get generated CSS theme based on tenant branding
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    theme = ThemeGenerator(tenant)

    # Return as CSS file or JSON
    output_format = request.query_params.get("format", "json")

    if output_format == "css":
        response = HttpResponse(theme.generate_full_theme(), content_type="text/css")
        response["Content-Disposition"] = (
            f'attachment; filename="{tenant.slug}_theme.css"'
        )
        return response

    return Response(
        {
            "success": True,
            "css_variables": theme.generate_css_variables(),
            "full_theme": theme.generate_full_theme(),
        }
    )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_captive_portal_pages(request):
    """
    Get generated captive portal HTML pages
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    generator = CaptivePortalGenerator(tenant)

    return Response({"success": True, "pages": generator.get_all_pages()})


# =============================================================================
# TENANT SETTINGS
# =============================================================================


@api_view(["GET", "PUT"])
@permission_classes([TenantAPIKeyPermission])
def portal_settings(request):
    """
    Get or update tenant settings
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        return Response(
            {
                "success": True,
                "settings": {
                    "business_name": tenant.business_name,
                    "business_email": tenant.business_email,
                    "business_phone": tenant.business_phone,
                    "business_address": tenant.business_address,
                    "timezone": tenant.timezone,
                    "primary_color": tenant.primary_color,
                    "secondary_color": tenant.secondary_color,
                    "has_nextsms": bool(tenant.nextsms_username),
                    "has_clickpesa": bool(tenant.clickpesa_client_id),
                    "nextsms_sender_id": tenant.nextsms_sender_id,
                },
            }
        )

    elif request.method == "PUT":
        serializer = TenantSettingsSerializer(tenant, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()

        return Response({"success": True, "message": "Settings updated successfully"})


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_api_keys(request):
    """
    Get tenant API keys
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    return Response(
        {
            "success": True,
            "api_key": tenant.api_key,
            "api_secret": (
                tenant.api_secret[:8] + "..." if tenant.api_secret else None
            ),  # Partially masked
            "usage": {
                "header_name": "X-API-Key",
                "example": f'curl -H "X-API-Key: {tenant.api_key}" https://api.kitonga.klikcell.com/api/...',
            },
        }
    )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_regenerate_api_key(request):
    """
    Regenerate tenant API key
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    import secrets

    tenant.api_key = secrets.token_hex(32)
    tenant.api_secret = secrets.token_hex(64)
    tenant.save()

    return Response(
        {
            "success": True,
            "message": "API keys regenerated successfully",
            "api_key": tenant.api_key,
            "warning": "Update your integrations with the new API key",
        }
    )


# =============================================================================
# STAFF MANAGEMENT
# =============================================================================


@api_view(["GET", "POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_staff(request):
    """
    List or invite staff members
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        staff = TenantStaff.objects.filter(tenant=tenant).select_related("user")
        return Response(
            {
                "success": True,
                "staff": TenantStaffSerializer(staff, many=True).data,
                "limit": (
                    tenant.subscription_plan.max_staff_accounts
                    if tenant.subscription_plan
                    else 2
                ),
                "used": staff.count(),
            }
        )

    elif request.method == "POST":
        # Check limit
        current_count = TenantStaff.objects.filter(
            tenant=tenant, is_active=True
        ).count()
        limit = (
            tenant.subscription_plan.max_staff_accounts
            if tenant.subscription_plan
            else 2
        )

        if current_count >= limit:
            return Response(
                {
                    "success": False,
                    "message": f"Staff limit reached ({limit}). Upgrade your plan to add more staff.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = StaffInviteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data["email"]

        # Check if user exists or create new
        user, created = DjangoUser.objects.get_or_create(
            email=email,
            defaults={
                "username": email.split("@")[0] + "_" + tenant.slug,
                "first_name": serializer.validated_data.get("first_name", ""),
                "last_name": serializer.validated_data.get("last_name", ""),
            },
        )

        # Check if already a staff member
        if TenantStaff.objects.filter(tenant=tenant, user=user).exists():
            return Response(
                {"success": False, "message": "User is already a staff member"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create staff record
        staff = TenantStaff.objects.create(
            tenant=tenant,
            user=user,
            role=serializer.validated_data.get("role", "support"),
            can_manage_routers=serializer.validated_data.get(
                "can_manage_routers", False
            ),
            can_manage_users=serializer.validated_data.get("can_manage_users", True),
            can_manage_payments=serializer.validated_data.get(
                "can_manage_payments", True
            ),
            can_manage_vouchers=serializer.validated_data.get(
                "can_manage_vouchers", True
            ),
            can_view_reports=serializer.validated_data.get("can_view_reports", True),
            can_manage_staff=serializer.validated_data.get("can_manage_staff", False),
            can_manage_settings=serializer.validated_data.get(
                "can_manage_settings", False
            ),
        )

        # TODO: Send invitation email

        return Response(
            {
                "success": True,
                "message": f"Staff member invited: {email}",
                "staff": TenantStaffSerializer(staff).data,
            },
            status=status.HTTP_201_CREATED,
        )


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([TenantAPIKeyPermission])
def portal_staff_detail(request, staff_id):
    """
    Get, update, or remove a staff member
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        staff = TenantStaff.objects.get(id=staff_id, tenant=tenant)
    except TenantStaff.DoesNotExist:
        return Response(
            {"success": False, "message": "Staff member not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response({"success": True, "staff": TenantStaffSerializer(staff).data})

    elif request.method == "PUT":
        # Cannot modify owner
        if staff.role == "owner":
            return Response(
                {"success": False, "message": "Cannot modify owner permissions"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = StaffUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for field, value in serializer.validated_data.items():
            setattr(staff, field, value)
        staff.save()

        return Response(
            {
                "success": True,
                "message": "Staff member updated",
                "staff": TenantStaffSerializer(staff).data,
            }
        )

    elif request.method == "DELETE":
        # Cannot delete owner
        if staff.role == "owner":
            return Response(
                {"success": False, "message": "Cannot remove owner"},
                status=status.HTTP_403_FORBIDDEN,
            )

        staff.is_active = False
        staff.save()

        return Response({"success": True, "message": "Staff member removed"})


# =============================================================================
# LOCATION MANAGEMENT
# =============================================================================


@api_view(["GET", "POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_locations(request):
    """
    List or create locations
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        locations = Location.objects.filter(tenant=tenant, is_active=True)
        return Response(
            {
                "success": True,
                "locations": LocationSerializer(locations, many=True).data,
                "limit": (
                    tenant.subscription_plan.max_locations
                    if tenant.subscription_plan
                    else 1
                ),
                "used": locations.count(),
            }
        )

    elif request.method == "POST":
        # Check limit
        current_count = Location.objects.filter(tenant=tenant, is_active=True).count()
        limit = (
            tenant.subscription_plan.max_locations if tenant.subscription_plan else 1
        )

        if current_count >= limit:
            return Response(
                {
                    "success": False,
                    "message": f"Location limit reached ({limit}). Upgrade your plan to add more locations.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = LocationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        location = serializer.save(tenant=tenant)

        return Response(
            {
                "success": True,
                "message": "Location created",
                "location": LocationSerializer(location).data,
            },
            status=status.HTTP_201_CREATED,
        )


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([TenantAPIKeyPermission])
def portal_location_detail(request, location_id):
    """
    Get, update, or delete a location
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        location = Location.objects.get(id=location_id, tenant=tenant)
    except Location.DoesNotExist:
        return Response(
            {"success": False, "message": "Location not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        # Include routers at this location
        routers = Router.objects.filter(location=location, is_active=True)
        return Response(
            {
                "success": True,
                "location": LocationSerializer(location).data,
                "routers": [
                    {"id": r.id, "name": r.name, "status": r.status} for r in routers
                ],
            }
        )

    elif request.method == "PUT":
        serializer = LocationSerializer(location, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()

        return Response(
            {
                "success": True,
                "message": "Location updated",
                "location": serializer.data,
            }
        )

    elif request.method == "DELETE":
        location.is_active = False
        location.save()

        return Response({"success": True, "message": "Location removed"})


# =============================================================================
# BUNDLE MANAGEMENT
# =============================================================================


@api_view(["GET", "POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_bundles(request):
    """
    List or create WiFi bundles
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        bundles = Bundle.objects.filter(tenant=tenant).order_by(
            "display_order", "duration_hours"
        )
        return Response(
            {"success": True, "bundles": BundleSerializer(bundles, many=True).data}
        )

    elif request.method == "POST":
        serializer = BundleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bundle = serializer.save(tenant=tenant)

        return Response(
            {
                "success": True,
                "message": "Bundle created",
                "bundle": BundleSerializer(bundle).data,
            },
            status=status.HTTP_201_CREATED,
        )


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([TenantAPIKeyPermission])
def portal_bundle_detail(request, bundle_id):
    """
    Get, update, or delete a bundle
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        bundle = Bundle.objects.get(id=bundle_id, tenant=tenant)
    except Bundle.DoesNotExist:
        return Response(
            {"success": False, "message": "Bundle not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        # Include sales stats
        sales = Payment.objects.filter(bundle=bundle, status="completed")
        return Response(
            {
                "success": True,
                "bundle": BundleSerializer(bundle).data,
                "stats": {
                    "total_sales": sales.count(),
                    "total_revenue": float(
                        sales.aggregate(total=Sum("amount"))["total"] or 0
                    ),
                },
            }
        )

    elif request.method == "PUT":
        serializer = BundleSerializer(bundle, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()

        return Response(
            {"success": True, "message": "Bundle updated", "bundle": serializer.data}
        )

    elif request.method == "DELETE":
        # Soft delete - just deactivate
        bundle.is_active = False
        bundle.save()

        return Response({"success": True, "message": "Bundle deactivated"})


# =============================================================================
# USER MANAGEMENT
# =============================================================================


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_users(request):
    """
    List all WiFi users for tenant with filtering and pagination

    Query Parameters:
    - search: Search by phone number or name
    - is_active: Filter by active status (true/false)
    - has_access: Filter by current access (true/false)
    - page: Page number (default 1)
    - page_size: Items per page (default 50, max 100)
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    users = (
        User.objects.filter(tenant=tenant)
        .select_related("primary_router")
        .order_by("-created_at")
    )

    # Search filter
    search = request.query_params.get("search")
    if search:
        users = users.filter(
            models.Q(phone_number__icontains=search) | models.Q(name__icontains=search)
        )

    # Active status filter
    is_active = request.query_params.get("is_active")
    if is_active is not None:
        is_active_bool = is_active.lower() == "true"
        users = users.filter(is_active=is_active_bool)

    # Current access filter
    has_access = request.query_params.get("has_access")
    if has_access is not None:
        now = timezone.now()
        if has_access.lower() == "true":
            users = users.filter(is_active=True, paid_until__gt=now)
        else:
            users = users.filter(
                models.Q(is_active=False)
                | models.Q(paid_until__lte=now)
                | models.Q(paid_until__isnull=True)
            )

    # Pagination
    page = int(request.query_params.get("page", 1))
    page_size = min(int(request.query_params.get("page_size", 50)), 100)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size

    total_count = users.count()
    users_page = users[start_idx:end_idx]

    now = timezone.now()
    user_list = []
    for u in users_page:
        # Calculate remaining time
        remaining_hours = None
        if u.paid_until and u.paid_until > now:
            remaining = u.paid_until - now
            remaining_hours = remaining.total_seconds() / 3600

        user_list.append(
            {
                "id": u.id,
                "phone_number": u.phone_number,
                "name": u.name or tenant.business_name,
                "email": u.email or "",
                "is_active": u.is_active,
                "has_access": u.has_active_access(),
                "paid_until": u.paid_until.isoformat() if u.paid_until else None,
                "remaining_hours": (
                    round(remaining_hours, 1) if remaining_hours else None
                ),
                "total_payments": u.total_payments,
                "total_amount_paid": float(u.total_amount_paid),
                "max_devices": u.max_devices,
                "primary_router": (
                    {
                        "id": u.primary_router.id,
                        "name": u.primary_router.name,
                        "host": u.primary_router.host,
                    }
                    if u.primary_router
                    else None
                ),
                "created_at": u.created_at.isoformat(),
            }
        )

    # Summary stats
    active_users = User.objects.filter(
        tenant=tenant, is_active=True, paid_until__gt=now
    ).count()
    total_users = User.objects.filter(tenant=tenant).count()

    return Response(
        {
            "success": True,
            "tenant": {
                "id": str(tenant.id),
                "name": tenant.business_name,
                "slug": tenant.slug,
            },
            "users": user_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": (total_count + page_size - 1) // page_size,
            },
            "summary": {
                "total_users": total_users,
                "active_users": active_users,
                "inactive_users": total_users - active_users,
            },
        }
    )


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([TenantAPIKeyPermission])
def portal_user_detail(request, user_id):
    """
    Get, update or delete a specific user

    GET: Get user details with payment history
    PUT: Update user (name, email, max_devices, extend access)
    DELETE: Deactivate user and revoke access
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        user = User.objects.get(id=user_id, tenant=tenant)
    except User.DoesNotExist:
        return Response(
            {"success": False, "message": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        now = timezone.now()

        # Get payment history
        payments = Payment.objects.filter(user=user).order_by("-created_at")[:20]
        payment_list = [
            {
                "id": p.id,
                "amount": float(p.amount),
                "status": p.status,
                "bundle_name": p.bundle.name if p.bundle else "Unknown",
                "created_at": p.created_at.isoformat(),
            }
            for p in payments
        ]

        # Get vouchers used
        vouchers_used = Voucher.objects.filter(used_by=user).order_by("-used_at")[:10]
        voucher_list = [
            {
                "id": v.id,
                "code": v.code,
                "duration_hours": v.duration_hours,
                "used_at": v.used_at.isoformat() if v.used_at else None,
            }
            for v in vouchers_used
        ]

        # Calculate remaining time
        remaining_hours = None
        if user.paid_until and user.paid_until > now:
            remaining = user.paid_until - now
            remaining_hours = remaining.total_seconds() / 3600

        return Response(
            {
                "success": True,
                "user": {
                    "id": user.id,
                    "phone_number": user.phone_number,
                    "name": user.name or "",
                    "email": user.email or "",
                    "is_active": user.is_active,
                    "has_access": user.has_active_access(),
                    "paid_until": (
                        user.paid_until.isoformat() if user.paid_until else None
                    ),
                    "remaining_hours": (
                        round(remaining_hours, 1) if remaining_hours else None
                    ),
                    "total_payments": user.total_payments,
                    "total_amount_paid": float(user.total_amount_paid),
                    "max_devices": user.max_devices,
                    "created_at": user.created_at.isoformat(),
                },
                "payments": payment_list,
                "vouchers_used": voucher_list,
            }
        )

    elif request.method == "PUT":
        # Update user details
        name = request.data.get("name")
        email = request.data.get("email")
        max_devices = request.data.get("max_devices")
        extend_hours = request.data.get("extend_hours")  # Manually extend access

        if name is not None:
            user.name = name
        if email is not None:
            user.email = email
        if max_devices is not None:
            try:
                max_devices = int(max_devices)
                if max_devices < 1:
                    return Response(
                        {"success": False, "message": "max_devices must be at least 1"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                user.max_devices = max_devices
            except (ValueError, TypeError):
                return Response(
                    {"success": False, "message": "Invalid max_devices value"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Extend access if requested
        if extend_hours:
            try:
                extend_hours = int(extend_hours)
                if extend_hours < 1:
                    return Response(
                        {
                            "success": False,
                            "message": "extend_hours must be at least 1",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                user.extend_access(hours=extend_hours, source="manual")
                logger.info(
                    f"Tenant {tenant.slug} extended access for user {user.phone_number} by {extend_hours} hours"
                )
            except (ValueError, TypeError):
                return Response(
                    {"success": False, "message": "Invalid extend_hours value"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        user.save()

        return Response(
            {
                "success": True,
                "message": "User updated successfully",
                "user": {
                    "id": user.id,
                    "phone_number": user.phone_number,
                    "name": user.name,
                    "email": user.email,
                    "max_devices": user.max_devices,
                    "is_active": user.is_active,
                    "paid_until": (
                        user.paid_until.isoformat() if user.paid_until else None
                    ),
                },
            }
        )

    elif request.method == "DELETE":
        # Deactivate user and revoke access
        user.is_active = False
        user.paid_until = None
        user.save()

        logger.info(f"Tenant {tenant.slug} deactivated user {user.phone_number}")

        return Response(
            {"success": True, "message": f"User {user.phone_number} deactivated"}
        )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_user_disconnect(request, user_id):
    """
    Disconnect user from MikroTik router (force logout)
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        user = User.objects.get(id=user_id, tenant=tenant)
    except User.DoesNotExist:
        return Response(
            {"success": False, "message": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get tenant's routers and disconnect user from all
    from .mikrotik import disconnect_user_from_mikrotik, get_mikrotik_api, safe_close
    import routeros_api

    routers = Router.objects.filter(tenant=tenant, is_active=True)
    disconnected_from = []
    errors = []

    # If no routers configured for tenant, try using global settings
    if not routers.exists():
        try:
            result = disconnect_user_from_mikrotik(user.phone_number)
            if (
                result.get("success")
                or result.get("session_removed")
                or result.get("user_disabled")
            ):
                return Response(
                    {
                        "success": True,
                        "message": f"User {user.phone_number} disconnected",
                        "disconnected_from": ["Default Router"],
                        "details": result,
                    }
                )
        except Exception as e:
            return Response(
                {"success": False, "message": f"Failed to disconnect user: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # Disconnect from each tenant router
    for router in routers:
        api = None
        try:
            # Connect to router using tenant-specific credentials
            connection = routeros_api.RouterOsApiPool(
                router.host,
                username=router.username,
                password=router.password,
                port=router.port or 8728,
                plaintext_login=True,
            )
            api = connection.get_api()

            # Remove active sessions
            try:
                active = api.get_resource("/ip/hotspot/active")
                all_sessions = active.get()

                for session in all_sessions:
                    if session.get("user", "") == user.phone_number:
                        session_id = session.get(".id") or session.get("id")
                        if session_id:
                            active.remove(id=session_id)
                            disconnected_from.append(router.name)
                            break
            except Exception as e:
                errors.append(f"{router.name}: {str(e)}")

        except Exception as e:
            errors.append(f"{router.name}: Connection failed - {str(e)}")
        finally:
            if api:
                try:
                    api.get_communicator().close()
                except:
                    pass

    return Response(
        {
            "success": True,
            "message": f"User {user.phone_number} disconnected",
            "disconnected_from": disconnected_from if disconnected_from else None,
            "errors": errors if errors else None,
        }
    )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_user_release_device(request, user_id):
    """
    Release (deactivate) a user's current device to allow them to use a different device.

    This is useful when a user wants to switch to a new device manually.
    With "Last Device Wins" policy, this isn't strictly necessary (the new device
    will automatically replace the old one), but this provides a manual option.

    Request Body (optional):
    {
        "mac_address": "AA:BB:CC:DD:EE:FF"  # Optional: specific device to release
    }

    If no mac_address is provided, all active devices are released.
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        user = User.objects.get(id=user_id, tenant=tenant)
    except User.DoesNotExist:
        return Response(
            {"success": False, "message": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    mac_address = request.data.get("mac_address")

    # Get devices to release
    if mac_address:
        devices_to_release = user.devices.filter(
            mac_address__iexact=mac_address, is_active=True
        )
    else:
        devices_to_release = user.devices.filter(is_active=True)

    if not devices_to_release.exists():
        return Response(
            {
                "success": True,
                "message": "No active devices to release",
                "released_count": 0,
            }
        )

    released_devices = []
    revoke_errors = []

    # Import MikroTik functions
    from .mikrotik import revoke_user_access_on_router, revoke_user_access

    # Get tenant's routers
    routers = Router.objects.filter(tenant=tenant, is_active=True)

    for device in devices_to_release:
        try:
            # Revoke from MikroTik
            if routers.exists():
                for router in routers:
                    try:
                        revoke_user_access_on_router(
                            router=router,
                            mac_address=device.mac_address,
                            username=user.phone_number,
                        )
                    except Exception as router_err:
                        revoke_errors.append(f"{router.name}: {str(router_err)}")
            else:
                # Try global router
                try:
                    revoke_user_access(
                        mac_address=device.mac_address, username=user.phone_number
                    )
                except Exception as global_err:
                    revoke_errors.append(f"global: {str(global_err)}")

            # Deactivate device in database
            device.is_active = False
            device.save()

            released_devices.append(
                {
                    "device_id": device.id,
                    "mac_address": device.mac_address,
                    "device_name": device.device_name,
                }
            )

            logger.info(
                f"Released device {device.mac_address} for user {user.phone_number} "
                f"(tenant: {tenant.slug})"
            )

        except Exception as e:
            revoke_errors.append(f"{device.mac_address}: {str(e)}")
            logger.error(f"Error releasing device {device.mac_address}: {e}")

    return Response(
        {
            "success": True,
            "message": f"Released {len(released_devices)} device(s). User can now connect from a new device.",
            "released_count": len(released_devices),
            "released_devices": released_devices,
            "errors": revoke_errors if revoke_errors else None,
            "info": "With 'Last Device Wins' policy, the user's next login will automatically use the new device.",
        }
    )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_user_device_status(request, user_id):
    """
    Get the device status for a WiFi user.

    Shows:
    - Current active device (if any)
    - Device history
    - Policy info (Last Device Wins)
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        user = User.objects.get(id=user_id, tenant=tenant)
    except User.DoesNotExist:
        return Response(
            {"success": False, "message": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get all devices
    all_devices = user.devices.all().order_by("-last_seen")
    active_devices = all_devices.filter(is_active=True)

    devices_list = []
    for device in all_devices:
        devices_list.append(
            {
                "id": device.id,
                "mac_address": device.mac_address,
                "ip_address": device.ip_address,
                "device_name": device.device_name,
                "is_active": device.is_active,
                "first_seen": (
                    device.first_seen.isoformat() if device.first_seen else None
                ),
                "last_seen": device.last_seen.isoformat() if device.last_seen else None,
            }
        )

    return Response(
        {
            "success": True,
            "user": {
                "id": user.id,
                "phone_number": user.phone_number,
                "has_access": user.has_active_access(),
                "max_devices": user.max_devices,
            },
            "device_policy": {
                "type": "last_device_wins",
                "description": "Only one device can be active at a time. When user connects from a new device, the old device is automatically disconnected.",
                "max_devices": user.max_devices,
            },
            "active_device": (
                {
                    "id": active_devices.first().id,
                    "mac_address": active_devices.first().mac_address,
                    "device_name": active_devices.first().device_name,
                    "last_seen": (
                        active_devices.first().last_seen.isoformat()
                        if active_devices.first().last_seen
                        else None
                    ),
                }
                if active_devices.exists()
                else None
            ),
            "active_count": active_devices.count(),
            "total_devices": all_devices.count(),
            "devices": devices_list,
        }
    )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_user_extend_access(request, user_id):
    """
    Extend user access by specified hours

    Request Body:
    {
        "hours": 24,
        "notify_sms": true  # Optional: send SMS notification
    }
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        user = User.objects.get(id=user_id, tenant=tenant)
    except User.DoesNotExist:
        return Response(
            {"success": False, "message": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    hours = request.data.get("hours")
    notify_sms = request.data.get("notify_sms", False)

    if not hours:
        return Response(
            {"success": False, "message": "hours is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        hours = int(hours)
        if hours < 1:
            return Response(
                {"success": False, "message": "hours must be at least 1"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    except (ValueError, TypeError):
        return Response(
            {"success": False, "message": "Invalid hours value"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Extend access
    user.extend_access(hours=hours, source="manual")
    user.save()

    logger.info(
        f"Tenant {tenant.slug} extended access for user {user.phone_number} by {hours} hours"
    )

    # Send SMS notification if requested
    sms_result = {"sent": False}
    if notify_sms:
        try:
            from .nextsms import NextSMSAPI
            from .models import SMSLog

            nextsms = NextSMSAPI()

            # Build duration text in Swahili
            if hours < 24:
                duration_text = f"saa {hours}"
            elif hours == 24:
                duration_text = "siku 1"
            else:
                days = hours // 24
                duration_text = f"siku {days}"

            message = (
                f"Habari! Muda wako wa Wi-Fi umeongezwa na {duration_text} kutoka {tenant.business_name}. "
                f"Unaweza kuendelea kutumia internet. Karibu!"
            )

            result = nextsms.send_sms(user.phone_number, message, f"EXTEND-{user.id}")

            SMSLog.objects.create(
                phone_number=user.phone_number,
                message=message,
                sms_type="access_extension",
                success=result.get("success", False),
                response_data=result.get("data"),
            )

            sms_result = {"sent": result.get("success", False)}
        except Exception as e:
            logger.error(f"Failed to send extension SMS: {e}")
            sms_result = {"sent": False, "error": str(e)}

    return Response(
        {
            "success": True,
            "message": f"Access extended by {hours} hours",
            "user": {
                "id": user.id,
                "phone_number": user.phone_number,
                "paid_until": user.paid_until.isoformat() if user.paid_until else None,
                "is_active": user.is_active,
            },
            "sms": sms_result,
        }
    )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_user_hotspot_enable(request, user_id):
    """
    Enable or disable a user's hotspot account on the tenant's MikroTik routers.

    This creates/re-enables the hotspot user on all active routers when enabling,
    or disables the hotspot user and kicks active sessions when disabling.

    POST body:
    {
        "action": "enable" | "disable",
        "router_id": 5          # Optional: target a specific router (default: all)
    }
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        user = User.objects.get(id=user_id, tenant=tenant)
    except User.DoesNotExist:
        return Response(
            {"success": False, "message": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    action = request.data.get("action", "").lower()
    target_router_id = request.data.get("router_id")

    if action not in ("enable", "disable"):
        return Response(
            {
                "success": False,
                "message": "action is required and must be 'enable' or 'disable'",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    from .mikrotik import get_tenant_mikrotik_api, safe_close

    # Get routers to operate on
    routers = Router.objects.filter(tenant=tenant, is_active=True)

    if target_router_id:
        routers = routers.filter(id=target_router_id)
        if not routers.exists():
            return Response(
                {"success": False, "message": "Router not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    if not routers.exists():
        return Response(
            {
                "success": False,
                "message": "No active routers configured for this tenant",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    results = []
    username = user.phone_number
    password = user.phone_number  # Hotspot password is the phone number

    for router in routers:
        router_result = {
            "router_id": router.id,
            "router_name": router.name,
            "success": False,
            "action": action,
            "detail": "",
        }

        api = get_tenant_mikrotik_api(router)
        if api is None:
            router_result["detail"] = f"Cannot connect to router {router.name}"
            results.append(router_result)
            continue

        try:
            hotspot_users = api.get_resource("/ip/hotspot/user")
            existing = hotspot_users.get(name=username)

            if action == "enable":
                if existing:
                    # Re-enable existing user
                    for item in existing:
                        uid = item.get(".id") or item.get("id")
                        if uid:
                            hotspot_users.set(id=uid, disabled="no", password=password)
                    router_result["success"] = True
                    router_result["detail"] = "User re-enabled on hotspot"
                else:
                    # Create new hotspot user
                    profile = getattr(router, "default_profile", None) or "default"
                    hotspot_users.add(
                        name=username,
                        password=password,
                        profile=profile,
                        disabled="no",
                    )
                    router_result["success"] = True
                    router_result["detail"] = "User created and enabled on hotspot"

            elif action == "disable":
                if existing:
                    for item in existing:
                        uid = item.get(".id") or item.get("id")
                        if uid:
                            hotspot_users.set(id=uid, disabled="yes")

                    # Also kick any active sessions
                    try:
                        active_resource = api.get_resource("/ip/hotspot/active")
                        sessions = active_resource.get()
                        for session in sessions:
                            if session.get("user", "") == username:
                                sid = session.get(".id") or session.get("id")
                                if sid:
                                    active_resource.remove(id=sid)
                    except Exception:
                        pass  # Session kick is best-effort

                    router_result["success"] = True
                    router_result["detail"] = (
                        "User disabled on hotspot and sessions kicked"
                    )
                else:
                    router_result["success"] = True
                    router_result["detail"] = (
                        "User not found on hotspot (already absent)"
                    )

        except Exception as e:
            router_result["detail"] = f"Error: {str(e)}"
            logger.error(
                f"portal_user_hotspot_enable: {action} user {username} on "
                f"router {router.name} failed: {e}"
            )
        finally:
            safe_close(api)

        results.append(router_result)

    # Update Django user active status to match
    if action == "enable":
        user.is_active = True
        user.save(update_fields=["is_active"])
    elif action == "disable":
        user.is_active = False
        user.save(update_fields=["is_active"])

    all_success = all(r["success"] for r in results)
    any_success = any(r["success"] for r in results)

    logger.info(
        f"Tenant {tenant.slug} {action}d hotspot for user {username} "
        f"({sum(1 for r in results if r['success'])}/{len(results)} routers)"
    )

    return Response(
        {
            "success": any_success,
            "message": (
                f"User {username} {action}d on hotspot"
                + ("" if all_success else " (some routers had errors)")
            ),
            "action": action,
            "user": {
                "id": user.id,
                "phone_number": user.phone_number,
                "is_active": user.is_active,
                "has_access": user.has_active_access(),
                "paid_until": (
                    user.paid_until.isoformat() if user.paid_until else None
                ),
            },
            "router_results": results,
        }
    )


# =============================================================================
# PAYMENT MANAGEMENT
# =============================================================================


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_payments(request):
    """
    List all payments for tenant with filtering and pagination
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    payments = Payment.objects.filter(tenant=tenant).order_by("-created_at")

    # Filters
    payment_status = request.query_params.get("status")
    if payment_status:
        payments = payments.filter(status=payment_status)

    search = request.query_params.get("search")
    if search:
        payments = payments.filter(
            models.Q(phone_number__icontains=search)
            | models.Q(transaction_id__icontains=search)
        )

    # Pagination
    page = int(request.query_params.get("page", 1))
    page_size = min(int(request.query_params.get("page_size", 50)), 100)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size

    total_count = payments.count()
    payments_page = payments[start_idx:end_idx]

    payment_list = [
        {
            "id": p.id,
            "phone_number": p.phone_number,
            "amount": float(p.amount),
            "status": p.status,
            "bundle_name": p.bundle.name if p.bundle else None,
            "transaction_id": p.transaction_id,
            "payment_channel": p.payment_channel,
            "created_at": p.created_at.isoformat(),
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        }
        for p in payments_page
    ]

    # Summary
    completed = Payment.objects.filter(tenant=tenant, status="completed")
    total_revenue = completed.aggregate(total=Sum("amount"))["total"] or 0

    return Response(
        {
            "success": True,
            "payments": payment_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": (total_count + page_size - 1) // page_size,
            },
            "summary": {
                "total_payments": Payment.objects.filter(tenant=tenant).count(),
                "completed_payments": completed.count(),
                "total_revenue": float(total_revenue),
            },
        }
    )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_balance(request):
    """
    Get tenant's financial balance with payout info
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Revenue from completed payments
    completed_payments = Payment.objects.filter(tenant=tenant, status="completed")
    total_revenue = completed_payments.aggregate(total=Sum("amount"))["total"] or 0

    # Platform fee (0% default)
    platform_fee_percent = 0
    if tenant.subscription_plan and hasattr(
        tenant.subscription_plan, "revenue_share_percent"
    ):
        platform_fee_percent = tenant.subscription_plan.revenue_share_percent or 0

    platform_fee = float(total_revenue) * (platform_fee_percent / 100)
    net_revenue = float(total_revenue) - platform_fee

    # Payouts
    completed_payouts = (
        TenantPayout.objects.filter(tenant=tenant, status="completed").aggregate(
            total=Sum("amount")
        )["total"]
        or 0
    )

    pending_payouts = (
        TenantPayout.objects.filter(
            tenant=tenant, status__in=["pending", "processing"]
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )

    available_balance = net_revenue - float(completed_payouts) - float(pending_payouts)

    return Response(
        {
            "success": True,
            "balance": {
                "total_revenue": float(total_revenue),
                "platform_fee_percent": platform_fee_percent,
                "platform_fee": round(platform_fee, 2),
                "net_revenue": round(net_revenue, 2),
                "total_payouts": float(completed_payouts),
                "pending_payouts": float(pending_payouts),
                "available_balance": round(available_balance, 2),
            },
            "payout_info": {
                "minimum_payout": 10000,
                "can_request_payout": available_balance >= 10000,
            },
        }
    )


@api_view(["GET", "POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_payouts(request):
    """
    GET: List payout requests
    POST: Request new payout
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        payouts = TenantPayout.objects.filter(tenant=tenant).order_by("-requested_at")

        payout_status = request.query_params.get("status")
        if payout_status:
            payouts = payouts.filter(status=payout_status)

        payout_list = [
            {
                "id": p.id,
                "reference": p.reference,
                "amount": float(p.amount),
                "payout_method": p.payout_method,
                "account_number": p.account_number,
                "account_name": p.account_name,
                "bank_name": p.bank_name,
                "bank_branch": p.bank_branch,  # BIC/SWIFT code
                "status": p.status,
                "requested_at": p.requested_at.isoformat(),
                "completed_at": p.completed_at.isoformat() if p.completed_at else None,
            }
            for p in payouts[:50]
        ]

        return Response(
            {
                "success": True,
                "payouts": payout_list,
                "summary": {
                    "total_requested": float(
                        TenantPayout.objects.filter(tenant=tenant).aggregate(
                            total=Sum("amount")
                        )["total"]
                        or 0
                    ),
                    "total_completed": float(
                        TenantPayout.objects.filter(
                            tenant=tenant, status="completed"
                        ).aggregate(total=Sum("amount"))["total"]
                        or 0
                    ),
                    "pending_count": TenantPayout.objects.filter(
                        tenant=tenant, status__in=["pending", "processing"]
                    ).count(),
                },
            }
        )

    elif request.method == "POST":
        amount = request.data.get("amount")
        payout_method = request.data.get("payout_method", "mobile_money")
        account_number = request.data.get("account_number")
        account_name = request.data.get("account_name", "")
        bank_name = request.data.get("bank_name", "")
        bank_branch = request.data.get(
            "bank_branch", ""
        )  # BIC/SWIFT code for bank transfers
        transfer_type = request.data.get("transfer_type", "ACH")  # ACH or RTGS

        if not amount or not account_number:
            return Response(
                {"success": False, "message": "amount and account_number are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Bank transfers require additional fields
        if payout_method == "bank_transfer":
            if not account_name:
                return Response(
                    {
                        "success": False,
                        "message": "account_name is required for bank transfers",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not bank_branch:
                return Response(
                    {
                        "success": False,
                        "message": "bank_branch (BIC/SWIFT code) is required for bank transfers",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            amount = float(amount)
        except (ValueError, TypeError):
            return Response(
                {"success": False, "message": "Invalid amount"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Calculate available balance
        completed_payments = Payment.objects.filter(tenant=tenant, status="completed")
        total_revenue = completed_payments.aggregate(total=Sum("amount"))["total"] or 0

        platform_fee_percent = 5
        platform_fee = float(total_revenue) * (platform_fee_percent / 100)
        net_revenue = float(total_revenue) - platform_fee

        completed_payouts = (
            TenantPayout.objects.filter(tenant=tenant, status="completed").aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )
        pending_payouts = (
            TenantPayout.objects.filter(
                tenant=tenant, status__in=["pending", "processing"]
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )

        available_balance = (
            net_revenue - float(completed_payouts) - float(pending_payouts)
        )

        if amount < 10000:
            return Response(
                {"success": False, "message": "Minimum payout is TSh 10,000"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if amount > available_balance:
            return Response(
                {
                    "success": False,
                    "message": f"Insufficient balance. Available: TSh {available_balance:,.2f}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payout = TenantPayout.objects.create(
            tenant=tenant,
            amount=amount,
            payout_method=payout_method,
            account_number=account_number,
            account_name=account_name,
            bank_name=bank_name,
            bank_branch=bank_branch,  # BIC/SWIFT code
            requested_by=f"API:{tenant.slug}",
        )

        logger.info(f"Tenant {tenant.slug} requested payout of TSh {amount}")

        # Determine which payment gateway to use for this payout
        use_snippe = (
            getattr(tenant, "preferred_payment_gateway", "clickpesa") == "snippe"
        )
        gateway_result = None
        gateway_name = "snippe" if use_snippe else "clickpesa"

        # Mobile Money payouts
        if payout_method in [
            "mobile_money",
            "mpesa",
            "tigopesa",
            "airtel_money",
            "halopesa",
        ]:
            if use_snippe:
                # ============================================================
                # SNIPPE MOBILE MONEY PAYOUT
                # ============================================================
                try:
                    from .snippe import SnippeAPI

                    snippe = SnippeAPI()

                    # Step 1: Check Snippe account balance
                    balance_result = snippe.get_account_balance()
                    if not balance_result.get("success"):
                        logger.warning(
                            f"Could not check Snippe balance: {balance_result.get('message')}"
                        )
                        gateway_result = {
                            "processed": False,
                            "reason": "balance_check_failed",
                            "message": balance_result.get(
                                "message", "Could not verify platform balance"
                            ),
                        }
                    else:
                        snippe_balance = balance_result.get("available", 0)
                        if snippe_balance < amount:
                            logger.warning(
                                f"Insufficient Snippe balance: {snippe_balance} < {amount}"
                            )
                            payout.error_message = f"Insufficient Snippe balance (TSh {snippe_balance:,.0f}). Will be processed manually."
                            payout.save()
                            gateway_result = {
                                "processed": False,
                                "reason": "insufficient_platform_balance",
                                "platform_balance": float(snippe_balance),
                                "required_amount": float(amount),
                                "message": "Platform does not have enough funds. Payout will be processed manually.",
                            }
                        else:
                            # Step 2: Calculate fee (optional preview)
                            fee_result = snippe.calculate_payout_fee(int(amount))
                            fee_info = {}
                            if fee_result.get("success"):
                                fee_info = {
                                    "fee": fee_result.get("fee_amount"),
                                    "total": fee_result.get("total_amount"),
                                }

                            # Step 3: Create mobile payout
                            webhook_url = (
                                getattr(settings, "SNIPPE_WEBHOOK_URL", "") or ""
                            )
                            payout_result = snippe.create_mobile_payout(
                                phone_number=account_number,
                                amount=int(amount),
                                recipient_name=account_name or tenant.business_name,
                                narration=f"Payout to {tenant.business_name} ({payout.reference})",
                                webhook_url=webhook_url,
                                metadata={
                                    "payout_reference": payout.reference,
                                    "tenant": tenant.slug,
                                },
                                idempotency_key=payout.reference,
                            )

                            if payout_result.get("success"):
                                payout.mark_processing()
                                payout.transaction_id = payout_result.get(
                                    "reference", ""
                                )
                                payout.save()
                                gateway_result = {
                                    "processed": True,
                                    "status": payout_result.get("status"),
                                    "channel_provider": payout_result.get(
                                        "channel_provider"
                                    ),
                                    "fee": payout_result.get("fees"),
                                    "snippe_reference": payout_result.get("reference"),
                                    **fee_info,
                                }
                                logger.info(
                                    f"Payout {payout.reference} submitted to Snippe: {payout_result.get('status')}"
                                )
                            else:
                                payout.error_message = payout_result.get(
                                    "message", "Snippe payout failed"
                                )
                                payout.save()
                                gateway_result = {
                                    "processed": False,
                                    "error": payout_result.get("message"),
                                }
                except Exception as e:
                    logger.error(f"Error processing payout via Snippe: {e}")
                    payout.error_message = f"Snippe auto-processing failed: {str(e)}"
                    payout.save()
                    gateway_result = {"processed": False, "error": str(e)}
            else:
                # ============================================================
                # CLICKPESA MOBILE MONEY PAYOUT (existing logic)
                # ============================================================
                try:
                    from .clickpesa import ClickPesaAPI

                    clickpesa = ClickPesaAPI()

                    # Step 1: Check account balance
                    balance_result = clickpesa.get_account_balance()
                    if not balance_result.get("success"):
                        logger.warning(
                            f"Could not check ClickPesa balance: {balance_result.get('message')}"
                        )
                        gateway_result = {
                            "processed": False,
                            "reason": "balance_check_failed",
                            "message": balance_result.get(
                                "message", "Could not verify platform balance"
                            ),
                        }
                    else:
                        tzs_balance = balance_result.get("balances", {}).get("TZS", 0)
                        if tzs_balance < amount:
                            logger.warning(
                                f"Insufficient ClickPesa balance: {tzs_balance} < {amount}"
                            )
                            payout.error_message = f"Insufficient platform balance (TSh {tzs_balance:,.0f}). Will be processed manually."
                            payout.save()
                            gateway_result = {
                                "processed": False,
                                "reason": "insufficient_platform_balance",
                                "platform_balance": float(tzs_balance),
                                "required_amount": float(amount),
                                "message": "Platform does not have enough funds. Payout will be processed manually.",
                            }
                        else:
                            # Step 2: Preview payout
                            preview_result = clickpesa.preview_mobile_money_payout(
                                phone_number=account_number,
                                amount=amount,
                                order_reference=payout.reference,
                            )

                            if preview_result.get("success"):
                                # Step 3: Create payout
                                payout_result = clickpesa.create_mobile_money_payout(
                                    phone_number=account_number,
                                    amount=amount,
                                    order_reference=payout.reference,
                                )

                                if payout_result.get("success"):
                                    payout.mark_processing()
                                    payout.transaction_id = payout_result.get(
                                        "payout_id"
                                    )
                                    payout.save()
                                    gateway_result = {
                                        "processed": True,
                                        "status": payout_result.get("status"),
                                        "channel_provider": payout_result.get(
                                            "channel_provider"
                                        ),
                                        "fee": payout_result.get("fee"),
                                    }
                                    logger.info(
                                        f"Payout {payout.reference} submitted to ClickPesa: {payout_result.get('status')}"
                                    )
                                else:
                                    payout.error_message = payout_result.get(
                                        "message", "ClickPesa payout failed"
                                    )
                                    payout.save()
                                    gateway_result = {
                                        "processed": False,
                                        "error": payout_result.get("message"),
                                    }
                            else:
                                payout.error_message = preview_result.get(
                                    "message", "Payout preview failed"
                                )
                                payout.save()
                                gateway_result = {
                                    "processed": False,
                                    "error": preview_result.get("message"),
                                }
                except Exception as e:
                    logger.error(f"Error processing payout via ClickPesa: {e}")
                    payout.error_message = f"Auto-processing failed: {str(e)}"
                    payout.save()
                    gateway_result = {"processed": False, "error": str(e)}

        # Bank Transfer payouts (ClickPesa only — Snippe does not support bank transfers)
        elif payout_method == "bank_transfer":
            try:
                from .clickpesa import ClickPesaAPI

                clickpesa = ClickPesaAPI()

                # Step 1: Check account balance
                balance_result = clickpesa.get_account_balance()
                if not balance_result.get("success"):
                    logger.warning(
                        f"Could not check ClickPesa balance: {balance_result.get('message')}"
                    )
                    gateway_result = {
                        "processed": False,
                        "reason": "balance_check_failed",
                        "message": balance_result.get(
                            "message", "Could not verify platform balance"
                        ),
                    }
                else:
                    tzs_balance = balance_result.get("balances", {}).get("TZS", 0)
                    if tzs_balance < amount:
                        logger.warning(
                            f"Insufficient ClickPesa balance for bank transfer: {tzs_balance} < {amount}"
                        )
                        payout.error_message = f"Insufficient platform balance (TSh {tzs_balance:,.0f}). Will be processed manually."
                        payout.save()
                        gateway_result = {
                            "processed": False,
                            "reason": "insufficient_platform_balance",
                            "platform_balance": float(tzs_balance),
                            "required_amount": float(amount),
                            "message": "Platform does not have enough funds. Payout will be processed manually.",
                        }
                    else:
                        # Step 2: Preview bank payout
                        preview_result = clickpesa.preview_bank_payout(
                            account_number=account_number,
                            amount=amount,
                            order_reference=payout.reference,
                            bic=bank_branch,  # BIC/SWIFT code
                            transfer_type=transfer_type,
                        )

                        if preview_result.get("success"):
                            # Step 3: Create bank payout
                            payout_result = clickpesa.create_bank_payout(
                                account_number=account_number,
                                account_name=account_name,
                                amount=amount,
                                order_reference=payout.reference,
                                bic=bank_branch,
                                transfer_type=transfer_type,
                            )

                            if payout_result.get("success"):
                                payout.mark_processing()
                                payout.transaction_id = payout_result.get("payout_id")
                                payout.save()
                                gateway_result = {
                                    "processed": True,
                                    "status": payout_result.get("status"),
                                    "channel_provider": payout_result.get(
                                        "channel_provider"
                                    ),
                                    "transfer_type": payout_result.get("transfer_type"),
                                    "fee": payout_result.get("fee"),
                                    "beneficiary": payout_result.get("beneficiary"),
                                }
                                logger.info(
                                    f"Bank payout {payout.reference} submitted to ClickPesa: {payout_result.get('status')}"
                                )
                            else:
                                payout.error_message = payout_result.get(
                                    "message", "ClickPesa bank payout failed"
                                )
                                payout.save()
                                gateway_result = {
                                    "processed": False,
                                    "error": payout_result.get("message"),
                                }
                        else:
                            payout.error_message = preview_result.get(
                                "message", "Bank payout preview failed"
                            )
                            payout.save()
                            gateway_result = {
                                "processed": False,
                                "error": preview_result.get("message"),
                            }
            except Exception as e:
                logger.error(f"Error processing bank payout via ClickPesa: {e}")
                payout.error_message = f"Auto-processing failed: {str(e)}"
                payout.save()
                gateway_result = {"processed": False, "error": str(e)}

        return Response(
            {
                "success": True,
                "message": "Payout request submitted",
                "payout": {
                    "id": payout.id,
                    "reference": payout.reference,
                    "amount": float(payout.amount),
                    "status": payout.status,
                },
                "new_available_balance": round(available_balance - amount, 2),
                "gateway": gateway_name,
                "gateway_result": gateway_result,
            },
            status=status.HTTP_201_CREATED,
        )


@api_view(["GET", "DELETE"])
@permission_classes([TenantAPIKeyPermission])
def portal_payout_detail(request, payout_id):
    """
    GET: Get payout details
    DELETE: Cancel pending payout
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        payout = TenantPayout.objects.get(id=payout_id, tenant=tenant)
    except TenantPayout.DoesNotExist:
        return Response(
            {"success": False, "message": "Payout not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            {
                "success": True,
                "payout": {
                    "id": payout.id,
                    "reference": payout.reference,
                    "amount": float(payout.amount),
                    "payout_method": payout.payout_method,
                    "account_number": payout.account_number,
                    "account_name": payout.account_name,
                    "bank_name": payout.bank_name,
                    "bank_branch": payout.bank_branch,  # BIC/SWIFT code
                    "status": payout.status,
                    "transaction_id": payout.transaction_id,
                    "error_message": payout.error_message,
                    "requested_at": payout.requested_at.isoformat(),
                    "completed_at": (
                        payout.completed_at.isoformat() if payout.completed_at else None
                    ),
                },
            }
        )

    elif request.method == "DELETE":
        if payout.status != "pending":
            return Response(
                {
                    "success": False,
                    "message": f"Cannot cancel payout with status: {payout.status}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payout.cancel("Cancelled by tenant")
        logger.info(f"Tenant {tenant.slug} cancelled payout {payout.reference}")

        return Response({"success": True, "message": "Payout cancelled"})


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_payout_refresh_status(request, payout_id):
    """
    Refresh payout status from payment provider (ClickPesa or Snippe)
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        payout = TenantPayout.objects.get(id=payout_id, tenant=tenant)
    except TenantPayout.DoesNotExist:
        return Response(
            {"success": False, "message": "Payout not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if payout.status in ["completed", "failed", "cancelled"]:
        return Response(
            {
                "success": True,
                "message": f"Payout already in final state: {payout.status}",
                "payout": {
                    "id": payout.id,
                    "reference": payout.reference,
                    "status": payout.status,
                },
            }
        )

    # Check if this payout was ever submitted to a payment provider
    if not payout.transaction_id:
        return Response(
            {
                "success": True,
                "message": "Payout was not submitted to payment provider - needs manual processing",
                "payout": {
                    "id": payout.id,
                    "reference": payout.reference,
                    "status": payout.status,
                    "needs_resubmit": True,
                    "error_message": payout.error_message
                    or "Not submitted to payment provider",
                },
            }
        )

    # Determine which gateway to query based on tenant preference
    use_snippe = getattr(tenant, "preferred_payment_gateway", "clickpesa") == "snippe"

    try:
        if use_snippe:
            # ---- Snippe payout status refresh ----
            from .snippe import SnippeAPI

            snippe = SnippeAPI()
            result = snippe.get_payout_status(payout.transaction_id)

            if result.get("success"):
                snippe_data = result.get("data", {})
                snippe_status = snippe_data.get("status", "").lower()
                old_status = payout.status

                if snippe_status == "completed":
                    ext_ref = snippe_data.get(
                        "external_reference", payout.transaction_id
                    )
                    payout.mark_completed(ext_ref)
                elif snippe_status in ["failed", "reversed"]:
                    failure_reason = snippe_data.get(
                        "failure_reason", f"Snippe status: {snippe_status}"
                    )
                    payout.mark_failed(failure_reason)
                elif snippe_status in ["processing", "pending"]:
                    payout.status = "processing"
                    payout.save()

                logger.info(
                    f"Payout {payout.reference} status updated via Snippe: {old_status} -> {payout.status}"
                )

                return Response(
                    {
                        "success": True,
                        "message": "Payout status refreshed",
                        "gateway": "snippe",
                        "payout": {
                            "id": payout.id,
                            "reference": payout.reference,
                            "status": payout.status,
                            "old_status": old_status,
                            "provider_status": snippe_status,
                        },
                        "provider_data": snippe_data,
                    }
                )
            else:
                return Response(
                    {
                        "success": False,
                        "message": result.get(
                            "message", "Failed to query payout status from Snippe"
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            # ---- ClickPesa payout status refresh ----
            from .clickpesa import ClickPesaAPI

            clickpesa = ClickPesaAPI()
            result = clickpesa.query_payout_status(payout.reference)

            if result.get("success"):
                clickpesa_status = result.get("status", "").upper()
                old_status = payout.status

                # Map ClickPesa status to our status
                if clickpesa_status == "SUCCESS":
                    payout.mark_completed(result.get("payout_id"))
                elif clickpesa_status in ["FAILED", "REVERSED", "REFUNDED"]:
                    payout.mark_failed(f"ClickPesa status: {clickpesa_status}")
                elif clickpesa_status in ["PROCESSING", "PENDING", "AUTHORIZED"]:
                    payout.status = "processing"
                    payout.save()

                logger.info(
                    f"Payout {payout.reference} status updated: {old_status} -> {payout.status}"
                )

                return Response(
                    {
                        "success": True,
                        "message": "Payout status refreshed",
                        "gateway": "clickpesa",
                        "payout": {
                            "id": payout.id,
                            "reference": payout.reference,
                            "status": payout.status,
                            "old_status": old_status,
                            "provider_status": clickpesa_status,
                        },
                        "provider_data": result.get("data"),
                    }
                )
            else:
                return Response(
                    {
                        "success": False,
                        "message": result.get(
                            "message", "Failed to query payout status"
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

    except Exception as e:
        logger.error(f"Error refreshing payout status: {e}")
        return Response(
            {"success": False, "message": f"Error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([TenantOrAdminPermission])
def portal_clickpesa_balance(request):
    """
    Get payment gateway account balance (platform balance for payouts).
    Automatically returns Snippe or ClickPesa balance based on tenant preference.
    Accessible by: Tenant (via API key) or Platform Admin
    """
    tenant = getattr(request, "tenant", None)

    # For admin users without tenant context, use platform credentials
    is_admin = (
        request.user
        and request.user.is_authenticated
        and (request.user.is_staff or request.user.is_superuser)
    )

    if not tenant and not is_admin:
        return Response(
            {"success": False, "message": "Tenant not found or unauthorized"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Determine preferred gateway
    preferred_gateway = (
        getattr(tenant, "preferred_payment_gateway", "clickpesa")
        if tenant
        else "clickpesa"
    )

    try:
        if preferred_gateway == "snippe":
            from .snippe import SnippeAPI

            snippe = SnippeAPI()
            result = snippe.get_account_balance()

            if result.get("success"):
                balance_data = result.get("data", {})
                # Extract TZS balance — Snippe returns {available: {currency, value}, balance: {currency, value}}
                available = balance_data.get("available", {})
                if isinstance(available, dict) and "value" in available:
                    tzs_balance = available.get("value", 0)
                elif isinstance(available, dict) and "TZS" in available:
                    tzs_balance = available.get("TZS", 0)
                else:
                    tzs_balance = (
                        balance_data.get("balance", {}).get("value", 0)
                        if isinstance(balance_data.get("balance"), dict)
                        else 0
                    )
                return Response(
                    {
                        "success": True,
                        "gateway": "snippe",
                        "balances": balance_data,
                        "tzs_balance": tzs_balance,
                    }
                )
            else:
                return Response(
                    {
                        "success": False,
                        "gateway": "snippe",
                        "message": result.get(
                            "message", "Failed to get Snippe balance"
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            from .clickpesa import ClickPesaAPI

            clickpesa = ClickPesaAPI()
            result = clickpesa.get_account_balance()

            if result.get("success"):
                return Response(
                    {
                        "success": True,
                        "gateway": "clickpesa",
                        "balances": result.get("balances", {}),
                        "tzs_balance": result.get("balances", {}).get("TZS", 0),
                    }
                )
            else:
                return Response(
                    {
                        "success": False,
                        "gateway": "clickpesa",
                        "message": result.get("message", "Failed to get balance"),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

    except Exception as e:
        logger.error(f"Error getting {preferred_gateway} balance: {e}")
        return Response(
            {
                "success": False,
                "gateway": preferred_gateway,
                "message": f"Error: {str(e)}",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_financial_summary(request):
    """
    Comprehensive financial summary for dashboard
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    from datetime import timedelta
    from django.db.models.functions import TruncDate

    now = timezone.now()
    today = now.date()

    # Revenue
    completed = Payment.objects.filter(tenant=tenant, status="completed")
    total_revenue = completed.aggregate(total=Sum("amount"))["total"] or 0

    # Platform fee
    platform_fee_percent = 5
    platform_fee = float(total_revenue) * (platform_fee_percent / 100)
    net_revenue = float(total_revenue) - platform_fee

    # Payouts
    completed_payouts = (
        TenantPayout.objects.filter(tenant=tenant, status="completed").aggregate(
            total=Sum("amount")
        )["total"]
        or 0
    )
    pending_payouts = (
        TenantPayout.objects.filter(
            tenant=tenant, status__in=["pending", "processing"]
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )

    available_balance = net_revenue - float(completed_payouts) - float(pending_payouts)

    # Period revenue
    today_revenue = (
        completed.filter(completed_at__date=today).aggregate(total=Sum("amount"))[
            "total"
        ]
        or 0
    )
    week_start = today - timedelta(days=today.weekday())
    week_revenue = (
        completed.filter(completed_at__date__gte=week_start).aggregate(
            total=Sum("amount")
        )["total"]
        or 0
    )
    month_start = today.replace(day=1)
    month_revenue = (
        completed.filter(completed_at__date__gte=month_start).aggregate(
            total=Sum("amount")
        )["total"]
        or 0
    )

    # Daily trend (last 30 days)
    thirty_days_ago = today - timedelta(days=30)
    daily_revenue = (
        completed.filter(completed_at__date__gte=thirty_days_ago)
        .annotate(date=TruncDate("completed_at"))
        .values("date")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("date")
    )

    return Response(
        {
            "success": True,
            "financial": {
                "total_revenue": float(total_revenue),
                "platform_fee": round(platform_fee, 2),
                "net_revenue": round(net_revenue, 2),
                "total_payouts": float(completed_payouts),
                "pending_payouts": float(pending_payouts),
                "available_balance": round(available_balance, 2),
                "can_request_payout": available_balance >= 10000,
            },
            "period_revenue": {
                "today": float(today_revenue),
                "this_week": float(week_revenue),
                "this_month": float(month_revenue),
            },
            "daily_trend": [
                {
                    "date": d["date"].strftime("%Y-%m-%d") if d["date"] else None,
                    "revenue": float(d["total"] or 0),
                    "payments": d["count"],
                }
                for d in daily_revenue
            ],
        }
    )


# =============================================================================
# TENANT SMS CONFIGURATION AND BROADCAST
# =============================================================================


def check_sms_broadcast_permission(tenant):
    """
    Check if tenant has permission to use SMS broadcast feature
    Only Business and Enterprise plans can use this feature
    """
    if not tenant.subscription_plan:
        return False, "No subscription plan active"

    # Check if plan allows SMS broadcast
    if (
        hasattr(tenant.subscription_plan, "sms_broadcast")
        and tenant.subscription_plan.sms_broadcast
    ):
        return True, None

    # Also allow if plan name is business or enterprise
    if tenant.subscription_plan.name in ["business", "enterprise"]:
        return True, None

    return (
        False,
        "SMS broadcast is only available for Business and Enterprise plans. Please upgrade to unlock this feature.",
    )


@api_view(["GET", "PUT"])
@permission_classes([TenantAPIKeyPermission])
def portal_sms_config(request):
    """
    Get or update tenant SMS (NextSMS) configuration

    GET: Returns current SMS configuration status
    PUT: Update SMS credentials
    """
    from .serializers import TenantSMSConfigSerializer
    from .nextsms import TenantNextSMSAPI

    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check permission
    has_permission, error_message = check_sms_broadcast_permission(tenant)
    if not has_permission:
        return Response(
            {"success": False, "message": error_message, "upgrade_required": True},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        # Return current config status (masked password)
        is_configured = bool(tenant.nextsms_username and tenant.nextsms_password)

        response_data = {
            "success": True,
            "is_configured": is_configured,
            "config": {
                "nextsms_username": tenant.nextsms_username or "",
                "nextsms_sender_id": (
                    tenant.nextsms_sender_id or tenant.business_name[:11]
                    if tenant.business_name
                    else ""
                ),
                "nextsms_base_url": tenant.nextsms_base_url
                or "https://messaging-service.co.tz",
                "has_password": bool(tenant.nextsms_password),
            },
        }

        # If configured, try to get balance
        if is_configured:
            try:
                sms_api = TenantNextSMSAPI(tenant)
                balance_result = sms_api.get_balance()
                response_data["balance"] = balance_result
            except Exception as e:
                response_data["balance"] = {"success": False, "message": str(e)}

        return Response(response_data)

    elif request.method == "PUT":
        serializer = TenantSMSConfigSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update tenant SMS credentials
        tenant.nextsms_username = serializer.validated_data["nextsms_username"]
        tenant.nextsms_password = serializer.validated_data["nextsms_password"]

        if "nextsms_sender_id" in serializer.validated_data:
            tenant.nextsms_sender_id = serializer.validated_data["nextsms_sender_id"]

        if (
            "nextsms_base_url" in serializer.validated_data
            and serializer.validated_data["nextsms_base_url"]
        ):
            tenant.nextsms_base_url = serializer.validated_data["nextsms_base_url"]

        tenant.save()

        logger.info(f"Tenant {tenant.slug} updated SMS configuration")

        return Response(
            {"success": True, "message": "SMS configuration updated successfully"}
        )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_sms_test_credentials(request):
    """
    Test tenant's NextSMS credentials
    """
    from .nextsms import TenantNextSMSAPI

    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check permission
    has_permission, error_message = check_sms_broadcast_permission(tenant)
    if not has_permission:
        return Response(
            {"success": False, "message": error_message, "upgrade_required": True},
            status=status.HTTP_403_FORBIDDEN,
        )

    if not tenant.nextsms_username or not tenant.nextsms_password:
        return Response(
            {
                "success": False,
                "message": "SMS credentials not configured. Please configure your NextSMS credentials first.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        sms_api = TenantNextSMSAPI(tenant)
        result = sms_api.test_credentials()

        return Response(
            {
                "success": result.get("success", False),
                "message": result.get("message", "Unknown error"),
                "balance": result.get("balance"),
            }
        )
    except Exception as e:
        logger.error(f"Error testing SMS credentials for {tenant.slug}: {e}")
        return Response(
            {"success": False, "message": f"Error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_sms_balance(request):
    """
    Get tenant's NextSMS balance
    """
    from .nextsms import TenantNextSMSAPI

    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check permission
    has_permission, error_message = check_sms_broadcast_permission(tenant)
    if not has_permission:
        return Response(
            {"success": False, "message": error_message, "upgrade_required": True},
            status=status.HTTP_403_FORBIDDEN,
        )

    if not tenant.nextsms_username or not tenant.nextsms_password:
        return Response(
            {"success": False, "message": "SMS credentials not configured"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        sms_api = TenantNextSMSAPI(tenant)
        result = sms_api.get_balance()

        return Response(result)
    except Exception as e:
        return Response(
            {"success": False, "message": f"Error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET", "POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_sms_broadcasts(request):
    """
    List or create SMS broadcasts for tenant

    GET: List all broadcasts with pagination
    POST: Create a new broadcast (draft or send immediately)
    """
    from .models import TenantSMSBroadcast
    from .serializers import (
        TenantSMSBroadcastCreateSerializer,
        TenantSMSBroadcastSerializer,
    )

    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check permission
    has_permission, error_message = check_sms_broadcast_permission(tenant)
    if not has_permission:
        return Response(
            {"success": False, "message": error_message, "upgrade_required": True},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        broadcasts = TenantSMSBroadcast.objects.filter(tenant=tenant).order_by(
            "-created_at"
        )

        # Pagination
        page = int(request.query_params.get("page", 1))
        page_size = min(int(request.query_params.get("page_size", 20)), 50)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        total_count = broadcasts.count()
        broadcasts_page = broadcasts[start_idx:end_idx]

        broadcast_list = []
        for b in broadcasts_page:
            broadcast_list.append(
                {
                    "id": str(b.id),
                    "title": b.title,
                    "message": (
                        b.message[:50] + "..." if len(b.message) > 50 else b.message
                    ),
                    "target_type": b.target_type,
                    "status": b.status,
                    "total_recipients": b.total_recipients,
                    "sent_count": b.sent_count,
                    "failed_count": b.failed_count,
                    "created_at": b.created_at.isoformat(),
                    "completed_at": (
                        b.completed_at.isoformat() if b.completed_at else None
                    ),
                }
            )

        return Response(
            {
                "success": True,
                "broadcasts": broadcast_list,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": (total_count + page_size - 1) // page_size,
                },
            }
        )

    elif request.method == "POST":
        # Check if SMS is configured
        if not tenant.nextsms_username or not tenant.nextsms_password:
            return Response(
                {
                    "success": False,
                    "message": "SMS credentials not configured. Please configure your NextSMS credentials first.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = TenantSMSBroadcastCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create broadcast
        broadcast = TenantSMSBroadcast.objects.create(
            tenant=tenant,
            title=serializer.validated_data["title"],
            message=serializer.validated_data["message"],
            target_type=serializer.validated_data["target_type"],
            custom_recipients=serializer.validated_data.get("custom_recipients"),
            scheduled_at=serializer.validated_data.get("scheduled_at"),
            status="draft",
        )

        # Get recipient count
        recipients = broadcast.get_recipients()
        broadcast.total_recipients = len(recipients)
        broadcast.save()

        logger.info(f"Tenant {tenant.slug} created SMS broadcast: {broadcast.title}")

        return Response(
            {
                "success": True,
                "message": "Broadcast created successfully",
                "broadcast": {
                    "id": str(broadcast.id),
                    "title": broadcast.title,
                    "target_type": broadcast.target_type,
                    "total_recipients": broadcast.total_recipients,
                    "status": broadcast.status,
                },
            },
            status=status.HTTP_201_CREATED,
        )


@api_view(["GET", "DELETE"])
@permission_classes([TenantAPIKeyPermission])
def portal_sms_broadcast_detail(request, broadcast_id):
    """
    Get or delete a specific SMS broadcast
    """
    from .models import TenantSMSBroadcast, SMSLog

    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        broadcast = TenantSMSBroadcast.objects.get(id=broadcast_id, tenant=tenant)
    except (TenantSMSBroadcast.DoesNotExist, ValueError):
        return Response(
            {"success": False, "message": "Broadcast not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        # Get SMS logs for this broadcast
        logs = SMSLog.objects.filter(
            tenant=tenant, message=broadcast.message, sent_at__gte=broadcast.created_at
        ).order_by("-sent_at")[:100]

        log_list = [
            {
                "phone_number": log.phone_number,
                "success": log.success,
                "sent_at": log.sent_at.isoformat(),
            }
            for log in logs
        ]

        return Response(
            {
                "success": True,
                "broadcast": {
                    "id": str(broadcast.id),
                    "title": broadcast.title,
                    "message": broadcast.message,
                    "target_type": broadcast.target_type,
                    "target_type_display": broadcast.get_target_type_display(),
                    "status": broadcast.status,
                    "status_display": broadcast.get_status_display(),
                    "total_recipients": broadcast.total_recipients,
                    "sent_count": broadcast.sent_count,
                    "failed_count": broadcast.failed_count,
                    "created_at": broadcast.created_at.isoformat(),
                    "scheduled_at": (
                        broadcast.scheduled_at.isoformat()
                        if broadcast.scheduled_at
                        else None
                    ),
                    "started_at": (
                        broadcast.started_at.isoformat()
                        if broadcast.started_at
                        else None
                    ),
                    "completed_at": (
                        broadcast.completed_at.isoformat()
                        if broadcast.completed_at
                        else None
                    ),
                    "error_message": broadcast.error_message,
                },
                "recent_logs": log_list,
            }
        )

    elif request.method == "DELETE":
        if broadcast.status in ["sending"]:
            return Response(
                {
                    "success": False,
                    "message": "Cannot delete a broadcast that is currently sending",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        broadcast_title = broadcast.title
        broadcast.delete()

        logger.info(f"Tenant {tenant.slug} deleted SMS broadcast: {broadcast_title}")

        return Response({"success": True, "message": "Broadcast deleted successfully"})


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_sms_broadcast_send(request, broadcast_id):
    """
    Send a pending SMS broadcast
    """
    from .models import TenantSMSBroadcast

    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        broadcast = TenantSMSBroadcast.objects.get(id=broadcast_id, tenant=tenant)
    except (TenantSMSBroadcast.DoesNotExist, ValueError):
        return Response(
            {"success": False, "message": "Broadcast not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if broadcast.status not in ["draft", "pending"]:
        return Response(
            {
                "success": False,
                "message": f'Cannot send broadcast in "{broadcast.get_status_display()}" status',
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Send the broadcast
    success, message = broadcast.send_broadcast()

    logger.info(
        f"Tenant {tenant.slug} sent SMS broadcast: {broadcast.title} - {message}"
    )

    return Response(
        {
            "success": success,
            "message": message,
            "broadcast": {
                "id": str(broadcast.id),
                "status": broadcast.status,
                "sent_count": broadcast.sent_count,
                "failed_count": broadcast.failed_count,
                "total_recipients": broadcast.total_recipients,
            },
        }
    )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_sms_broadcast_preview(request):
    """
    Preview recipients count for a broadcast without creating it
    """
    from .models import TenantSMSBroadcast
    from .serializers import TenantSMSBroadcastCreateSerializer

    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check permission
    has_permission, error_message = check_sms_broadcast_permission(tenant)
    if not has_permission:
        return Response(
            {"success": False, "message": error_message, "upgrade_required": True},
            status=status.HTTP_403_FORBIDDEN,
        )

    target_type = request.data.get("target_type", "all_users")
    custom_recipients = request.data.get("custom_recipients", [])

    # Create a temporary broadcast object to use get_recipients
    temp_broadcast = TenantSMSBroadcast(
        tenant=tenant, target_type=target_type, custom_recipients=custom_recipients
    )

    recipients = temp_broadcast.get_recipients()

    # Sample some recipients
    sample_recipients = recipients[:10] if len(recipients) > 10 else recipients

    return Response(
        {
            "success": True,
            "total_recipients": len(recipients),
            "sample_recipients": [
                {"phone": r.get("phone_number", ""), "name": r.get("name", "")}
                for r in sample_recipients
            ],
            "estimated_cost": len(recipients) * 25,  # Approximate cost per SMS in TZS
        }
    )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_sms_send_single(request):
    """
    Send a single SMS to a phone number
    """
    from .models import SMSLog
    from .nextsms import TenantNextSMSAPI
    from .serializers import TenantSendSingleSMSSerializer

    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check permission
    has_permission, error_message = check_sms_broadcast_permission(tenant)
    if not has_permission:
        return Response(
            {"success": False, "message": error_message, "upgrade_required": True},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check if SMS is configured
    if not tenant.nextsms_username or not tenant.nextsms_password:
        return Response(
            {
                "success": False,
                "message": "SMS credentials not configured. Please configure your NextSMS credentials first.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = TenantSendSingleSMSSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    phone_number = serializer.validated_data["phone_number"]
    message = serializer.validated_data["message"]

    try:
        sms_api = TenantNextSMSAPI(tenant)
        result = sms_api.send_sms(phone_number, message, f"SINGLE-{tenant.slug}")

        # Log the SMS
        SMSLog.objects.create(
            tenant=tenant,
            phone_number=phone_number,
            message=message,
            sms_type="broadcast",
            success=result.get("success", False),
            response_data=result.get("data"),
        )

        logger.info(f"Tenant {tenant.slug} sent single SMS to {phone_number}")

        return Response(
            {
                "success": result.get("success", False),
                "message": (
                    "SMS sent successfully"
                    if result.get("success")
                    else result.get("message", "Failed to send SMS")
                ),
            }
        )
    except Exception as e:
        logger.error(f"Error sending single SMS for {tenant.slug}: {e}")
        return Response(
            {"success": False, "message": f"Error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_sms_logs(request):
    """
    Get SMS logs for tenant
    """
    from .models import SMSLog

    tenant = getattr(request, "tenant", None)
    if not tenant:
        return Response(
            {"success": False, "message": "Tenant not found"},
            status=status.HTTP_403_FORBIDDEN,
        )

    logs = SMSLog.objects.filter(tenant=tenant).order_by("-sent_at")

    # Filters
    sms_type = request.query_params.get("sms_type")
    if sms_type:
        logs = logs.filter(sms_type=sms_type)

    success_filter = request.query_params.get("success")
    if success_filter is not None:
        logs = logs.filter(success=success_filter.lower() == "true")

    # Pagination
    page = int(request.query_params.get("page", 1))
    page_size = min(int(request.query_params.get("page_size", 50)), 100)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size

    total_count = logs.count()
    logs_page = logs[start_idx:end_idx]

    log_list = [
        {
            "id": log.id,
            "phone_number": log.phone_number,
            "message": (
                log.message[:100] + "..." if len(log.message) > 100 else log.message
            ),
            "sms_type": log.sms_type,
            "success": log.success,
            "sent_at": log.sent_at.isoformat(),
        }
        for log in logs_page
    ]

    # Summary stats
    total_sent = SMSLog.objects.filter(tenant=tenant, success=True).count()
    total_failed = SMSLog.objects.filter(tenant=tenant, success=False).count()

    return Response(
        {
            "success": True,
            "logs": log_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": (total_count + page_size - 1) // page_size,
            },
            "summary": {"total_sent": total_sent, "total_failed": total_failed},
        }
    )


# =============================================================================
# AUTO SMS CAMPAIGNS (Business/Enterprise Feature)
# =============================================================================


def check_auto_sms_permission(tenant):
    """Check if tenant has access to auto SMS campaigns"""
    if not tenant.subscription_plan:
        return False, "No subscription plan"
    if not tenant.subscription_plan.auto_sms_campaigns:
        return False, "Auto SMS campaigns require Business or Enterprise plan"
    return True, None


@api_view(["GET", "POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_auto_sms_campaigns(request):
    """
    GET: List auto SMS campaigns
    POST: Create new auto SMS campaign
    """
    from .models import AutoSMSCampaign
    from .serializers import AutoSMSCampaignSerializer, AutoSMSCampaignCreateSerializer

    tenant = request.tenant

    # Check permission
    allowed, error = check_auto_sms_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        campaigns = AutoSMSCampaign.objects.filter(tenant=tenant)

        # Filter by status if provided
        status_filter = request.query_params.get("status")
        if status_filter:
            campaigns = campaigns.filter(status=status_filter)

        campaign_list = [
            {
                "id": str(c.id),
                "name": c.name,
                "trigger_type": c.trigger_type,
                "trigger_type_display": c.get_trigger_type_display(),
                "status": c.status,
                "total_sent": c.total_sent,
                "total_failed": c.total_failed,
                "last_triggered_at": (
                    c.last_triggered_at.isoformat() if c.last_triggered_at else None
                ),
                "next_run_at": c.next_run_at.isoformat() if c.next_run_at else None,
                "created_at": c.created_at.isoformat(),
            }
            for c in campaigns
        ]

        return Response(
            {
                "success": True,
                "campaigns": campaign_list,
                "total_count": campaigns.count(),
            }
        )

    elif request.method == "POST":
        serializer = AutoSMSCampaignCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data

        campaign = AutoSMSCampaign.objects.create(
            tenant=tenant,
            name=data["name"],
            description=data.get("description", ""),
            trigger_type=data["trigger_type"],
            hours_before_expiry=data.get("hours_before_expiry", 24),
            scheduled_time=data.get("scheduled_time"),
            scheduled_date=data.get("scheduled_date"),
            day_of_week=data.get("day_of_week"),
            day_of_month=data.get("day_of_month"),
            message_template=data["message_template"],
            target_all_users=data.get("target_all_users", True),
            target_active_only=data.get("target_active_only", False),
            target_expired_only=data.get("target_expired_only", False),
            status="draft",
        )

        # Calculate next run for scheduled campaigns
        if campaign.trigger_type in [
            "scheduled",
            "recurring_daily",
            "recurring_weekly",
            "recurring_monthly",
        ]:
            campaign.calculate_next_run()

        logger.info(f"Tenant {tenant.slug} created auto SMS campaign: {campaign.name}")

        return Response(
            {
                "success": True,
                "message": "Auto SMS campaign created",
                "campaign": {
                    "id": str(campaign.id),
                    "name": campaign.name,
                    "trigger_type": campaign.trigger_type,
                    "status": campaign.status,
                },
            },
            status=status.HTTP_201_CREATED,
        )


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([TenantAPIKeyPermission])
def portal_auto_sms_campaign_detail(request, campaign_id):
    """
    GET: Get campaign details
    PUT: Update campaign
    DELETE: Delete campaign
    """
    from .models import AutoSMSCampaign

    tenant = request.tenant

    # Check permission
    allowed, error = check_auto_sms_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        campaign = AutoSMSCampaign.objects.get(id=campaign_id, tenant=tenant)
    except AutoSMSCampaign.DoesNotExist:
        return Response(
            {"success": False, "error": "Campaign not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            {
                "success": True,
                "campaign": {
                    "id": str(campaign.id),
                    "name": campaign.name,
                    "description": campaign.description,
                    "trigger_type": campaign.trigger_type,
                    "trigger_type_display": campaign.get_trigger_type_display(),
                    "hours_before_expiry": campaign.hours_before_expiry,
                    "scheduled_time": (
                        str(campaign.scheduled_time)
                        if campaign.scheduled_time
                        else None
                    ),
                    "scheduled_date": (
                        campaign.scheduled_date.isoformat()
                        if campaign.scheduled_date
                        else None
                    ),
                    "day_of_week": campaign.day_of_week,
                    "day_of_month": campaign.day_of_month,
                    "message_template": campaign.message_template,
                    "target_all_users": campaign.target_all_users,
                    "target_active_only": campaign.target_active_only,
                    "target_expired_only": campaign.target_expired_only,
                    "status": campaign.status,
                    "total_sent": campaign.total_sent,
                    "total_failed": campaign.total_failed,
                    "last_triggered_at": (
                        campaign.last_triggered_at.isoformat()
                        if campaign.last_triggered_at
                        else None
                    ),
                    "next_run_at": (
                        campaign.next_run_at.isoformat()
                        if campaign.next_run_at
                        else None
                    ),
                    "created_at": campaign.created_at.isoformat(),
                },
            }
        )

    elif request.method == "PUT":
        data = request.data

        # Update fields
        if "name" in data:
            campaign.name = data["name"]
        if "description" in data:
            campaign.description = data["description"]
        if "message_template" in data:
            campaign.message_template = data["message_template"]
        if "status" in data and data["status"] in ["active", "paused", "draft"]:
            campaign.status = data["status"]
        if "hours_before_expiry" in data:
            campaign.hours_before_expiry = data["hours_before_expiry"]
        if "scheduled_time" in data:
            campaign.scheduled_time = data["scheduled_time"]
        if "target_all_users" in data:
            campaign.target_all_users = data["target_all_users"]
        if "target_active_only" in data:
            campaign.target_active_only = data["target_active_only"]
        if "target_expired_only" in data:
            campaign.target_expired_only = data["target_expired_only"]

        campaign.save()

        # Recalculate next run if needed
        if campaign.trigger_type in [
            "scheduled",
            "recurring_daily",
            "recurring_weekly",
            "recurring_monthly",
        ]:
            campaign.calculate_next_run()

        logger.info(f"Tenant {tenant.slug} updated auto SMS campaign: {campaign.name}")

        return Response(
            {
                "success": True,
                "message": "Campaign updated",
            }
        )

    elif request.method == "DELETE":
        campaign_name = campaign.name
        campaign.delete()
        logger.info(f"Tenant {tenant.slug} deleted auto SMS campaign: {campaign_name}")
        return Response({"success": True, "message": "Campaign deleted"})


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_auto_sms_campaign_logs(request, campaign_id):
    """Get execution logs for a campaign"""
    from .models import AutoSMSCampaign, AutoSMSLog

    tenant = request.tenant

    # Check permission
    allowed, error = check_auto_sms_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        campaign = AutoSMSCampaign.objects.get(id=campaign_id, tenant=tenant)
    except AutoSMSCampaign.DoesNotExist:
        return Response(
            {"success": False, "error": "Campaign not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Pagination
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 50))

    logs = AutoSMSLog.objects.filter(campaign=campaign).order_by("-triggered_at")
    total_count = logs.count()

    start = (page - 1) * page_size
    end = start + page_size
    logs_page = logs[start:end]

    log_list = [
        {
            "id": log.id,
            "trigger_event": log.trigger_event,
            "recipient_phone": log.recipient_phone,
            "message_sent": (
                log.message_sent[:100] + "..."
                if len(log.message_sent) > 100
                else log.message_sent
            ),
            "success": log.success,
            "error_message": log.error_message,
            "triggered_at": log.triggered_at.isoformat(),
        }
        for log in logs_page
    ]

    return Response(
        {
            "success": True,
            "logs": log_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": (total_count + page_size - 1) // page_size,
            },
            "summary": {
                "total_sent": campaign.total_sent,
                "total_failed": campaign.total_failed,
                "last_triggered": (
                    campaign.last_triggered_at.isoformat()
                    if campaign.last_triggered_at
                    else None
                ),
            },
        }
    )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_auto_sms_campaign_toggle(request, campaign_id):
    """Toggle campaign status between active and paused"""
    from .models import AutoSMSCampaign

    tenant = request.tenant

    # Check permission
    allowed, error = check_auto_sms_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        campaign = AutoSMSCampaign.objects.get(id=campaign_id, tenant=tenant)
    except AutoSMSCampaign.DoesNotExist:
        return Response(
            {"success": False, "error": "Campaign not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Toggle status
    if campaign.status == "active":
        campaign.status = "paused"
        new_status = "paused"
    elif campaign.status in ["paused", "draft"]:
        campaign.status = "active"
        new_status = "active"
        # Calculate next run for time-based triggers
        if campaign.trigger_type in [
            "scheduled",
            "recurring_daily",
            "recurring_weekly",
            "recurring_monthly",
        ]:
            campaign.calculate_next_run()
    else:
        return Response(
            {
                "success": False,
                "error": f"Cannot toggle campaign with status: {campaign.status}",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    campaign.save()

    logger.info(
        f"Tenant {tenant.slug} toggled campaign {campaign.name} to {new_status}"
    )

    return Response(
        {
            "success": True,
            "message": f"Campaign {new_status}",
            "campaign": {
                "id": str(campaign.id),
                "name": campaign.name,
                "status": campaign.status,
                "next_run_at": (
                    campaign.next_run_at.isoformat() if campaign.next_run_at else None
                ),
            },
        }
    )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_auto_sms_campaign_preview(request, campaign_id):
    """Preview how many users would receive SMS from this campaign"""
    from .models import AutoSMSCampaign, User

    tenant = request.tenant

    # Check permission
    allowed, error = check_auto_sms_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        campaign = AutoSMSCampaign.objects.get(id=campaign_id, tenant=tenant)
    except AutoSMSCampaign.DoesNotExist:
        return Response(
            {"success": False, "error": "Campaign not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Build recipient query based on targeting
    users = User.objects.filter(tenant=tenant, phone_number__isnull=False)

    if campaign.target_active_only:
        users = users.filter(paid_until__gt=timezone.now())
    elif campaign.target_expired_only:
        users = users.filter(paid_until__lt=timezone.now())

    recipient_count = users.count()

    # Sample message preview
    sample_message = campaign.message_template
    sample_user = users.first()
    if sample_user:
        # Replace template variables
        sample_message = sample_message.replace(
            "{name}", sample_user.name or "Customer"
        )
        sample_message = sample_message.replace(
            "{phone}", sample_user.phone_number or ""
        )
        sample_message = sample_message.replace(
            "{business}", tenant.business_name or ""
        )

    return Response(
        {
            "success": True,
            "preview": {
                "recipient_count": recipient_count,
                "sample_message": sample_message,
                "targeting": {
                    "all_users": campaign.target_all_users,
                    "active_only": campaign.target_active_only,
                    "expired_only": campaign.target_expired_only,
                },
                "trigger_info": {
                    "type": campaign.trigger_type,
                    "display": campaign.get_trigger_type_display(),
                },
            },
        }
    )


# =============================================================================
# WEBHOOK NOTIFICATIONS (Business/Enterprise Feature)
# =============================================================================


def check_webhook_permission(tenant):
    """Check if tenant has access to webhook notifications"""
    if not tenant.subscription_plan:
        return False, "No subscription plan"
    if not tenant.subscription_plan.webhook_notifications:
        return False, "Webhooks require Business or Enterprise plan"
    return True, None


@api_view(["GET", "POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_webhooks(request):
    """
    GET: List webhooks
    POST: Create new webhook
    """
    from .models import TenantWebhook

    tenant = request.tenant

    # Check permission
    allowed, error = check_webhook_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        webhooks = TenantWebhook.objects.filter(tenant=tenant)

        webhook_list = [
            {
                "id": str(w.id),
                "name": w.name,
                "url": w.url,
                "events": w.events,
                "is_active": w.is_active,
                "last_success_at": (
                    w.last_success_at.isoformat() if w.last_success_at else None
                ),
                "created_at": w.created_at.isoformat(),
            }
            for w in webhooks
        ]

        return Response(
            {"success": True, "webhooks": webhook_list, "total_count": webhooks.count()}
        )

    elif request.method == "POST":
        data = request.data

        # Validate required fields
        if not data.get("name"):
            return Response(
                {"success": False, "error": "Name is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not data.get("url"):
            return Response(
                {"success": False, "error": "URL is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not data.get("events") or not isinstance(data["events"], list):
            return Response(
                {"success": False, "error": "Events list is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        import secrets

        webhook = TenantWebhook.objects.create(
            tenant=tenant,
            name=data["name"],
            url=data["url"],
            events=data["events"],
            is_active=data.get("is_active", True),
        )

        logger.info(f"Tenant {tenant.slug} created webhook: {webhook.name}")

        return Response(
            {
                "success": True,
                "message": "Webhook created",
                "webhook": {
                    "id": str(webhook.id),
                    "name": webhook.name,
                    "url": webhook.url,
                    "secret": webhook.secret_key,
                    "events": webhook.events,
                },
            },
            status=status.HTTP_201_CREATED,
        )


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([TenantAPIKeyPermission])
def portal_webhook_detail(request, webhook_id):
    """
    GET: Get webhook details
    PUT: Update webhook
    DELETE: Delete webhook
    """
    from .models import TenantWebhook

    tenant = request.tenant

    # Check permission
    allowed, error = check_webhook_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        webhook = TenantWebhook.objects.get(id=webhook_id, tenant=tenant)
    except TenantWebhook.DoesNotExist:
        return Response(
            {"success": False, "error": "Webhook not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            {
                "success": True,
                "webhook": {
                    "id": str(webhook.id),
                    "name": webhook.name,
                    "url": webhook.url,
                    "secret": webhook.secret_key,
                    "events": webhook.events,
                    "is_active": webhook.is_active,
                    "last_success_at": (
                        webhook.last_success_at.isoformat()
                        if webhook.last_success_at
                        else None
                    ),
                    "created_at": webhook.created_at.isoformat(),
                },
            }
        )

    elif request.method == "PUT":
        data = request.data

        if "name" in data:
            webhook.name = data["name"]
        if "url" in data:
            webhook.url = data["url"]
        if "events" in data:
            webhook.events = data["events"]
        if "is_active" in data:
            webhook.is_active = data["is_active"]

        webhook.save()

        logger.info(f"Tenant {tenant.slug} updated webhook: {webhook.name}")

        return Response(
            {
                "success": True,
                "message": "Webhook updated",
            }
        )

    elif request.method == "DELETE":
        webhook_name = webhook.name
        webhook.delete()
        logger.info(f"Tenant {tenant.slug} deleted webhook: {webhook_name}")
        return Response({"success": True, "message": "Webhook deleted"})


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_webhook_test(request, webhook_id):
    """Send a test webhook to verify endpoint"""
    from .models import TenantWebhook
    from .webhook_service import WebhookService

    tenant = request.tenant

    # Check permission
    allowed, error = check_webhook_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        webhook = TenantWebhook.objects.get(id=webhook_id, tenant=tenant)
    except TenantWebhook.DoesNotExist:
        return Response(
            {"success": False, "error": "Webhook not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Send test webhook directly
    import requests
    import time
    import json

    test_payload = {
        "event": "test",
        "test": True,
        "message": "This is a test webhook from Kitonga",
        "tenant": tenant.business_name,
        "timestamp": timezone.now().isoformat(),
    }

    payload_json = json.dumps(test_payload, default=str)

    # Generate signature
    signature = WebhookService.generate_signature(payload_json, webhook.secret_key)

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
        "X-Webhook-Event": "test",
        "User-Agent": "Kitonga-Webhook/1.0",
    }

    try:
        response = requests.post(
            webhook.url,
            data=payload_json,
            headers=headers,
            timeout=10,
        )
        success = response.status_code in [200, 201, 202, 204]
        response_code = response.status_code
        error_msg = None if success else response.text[:500]
    except requests.exceptions.Timeout:
        success = False
        response_code = None
        error_msg = "Request timed out"
    except Exception as e:
        success = False
        response_code = None
        error_msg = str(e)

    if success:
        return Response(
            {
                "success": True,
                "message": "Test webhook sent successfully",
                "response_code": response_code,
            }
        )
    else:
        return Response(
            {
                "success": False,
                "error": f"Webhook failed: {error_msg}",
                "response_code": response_code,
            }
        )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_webhook_deliveries(request, webhook_id):
    """Get delivery history for a webhook"""
    from .models import TenantWebhook, WebhookDelivery

    tenant = request.tenant

    # Check permission
    allowed, error = check_webhook_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        webhook = TenantWebhook.objects.get(id=webhook_id, tenant=tenant)
    except TenantWebhook.DoesNotExist:
        return Response(
            {"success": False, "error": "Webhook not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Pagination
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 50))

    deliveries = WebhookDelivery.objects.filter(webhook=webhook).order_by("-created_at")
    total_count = deliveries.count()

    start = (page - 1) * page_size
    end = start + page_size
    deliveries_page = deliveries[start:end]

    delivery_list = [
        {
            "id": str(d.id),
            "event_type": d.event_type,
            "event_id": str(d.event_id),
            "status": d.status,
            "response_status_code": d.response_status_code,
            "response_time_ms": d.response_time_ms,
            "error_message": d.error_message,
            "attempts": d.attempts,
            "max_attempts": d.max_attempts,
            "created_at": d.created_at.isoformat(),
            "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
        }
        for d in deliveries_page
    ]

    # Success rate
    total = deliveries.count()
    successful = deliveries.filter(status="success").count()
    success_rate = (successful / total * 100) if total > 0 else 0

    return Response(
        {
            "success": True,
            "deliveries": delivery_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": (total_count + page_size - 1) // page_size,
            },
            "summary": {
                "total_deliveries": total,
                "successful": successful,
                "failed": total - successful,
                "success_rate": round(success_rate, 1),
            },
        }
    )


# =============================================================================
# ADVANCED ANALYTICS (Business/Enterprise Feature)
# =============================================================================


def check_analytics_permission(tenant):
    """Check if tenant has access to advanced analytics"""
    if not tenant.subscription_plan:
        return False, "No subscription plan"
    if not tenant.subscription_plan.advanced_analytics:
        return False, "Advanced analytics require Business or Enterprise plan"
    return True, None


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_advanced_analytics(request):
    """Get comprehensive analytics dashboard data"""
    from django.db.models import Sum, Count, Avg
    from django.db.models.functions import TruncDate, TruncHour
    from .models import User, Payment, Voucher, Router

    tenant = request.tenant

    # Check permission
    allowed, error = check_analytics_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Date range
    days = int(request.query_params.get("days", 30))
    start_date = timezone.now() - timedelta(days=days)

    # User stats
    total_users = User.objects.filter(tenant=tenant).count()
    active_users = User.objects.filter(
        tenant=tenant, paid_until__gt=timezone.now()
    ).count()
    new_users = User.objects.filter(tenant=tenant, created_at__gte=start_date).count()

    # Revenue stats
    payments = Payment.objects.filter(
        tenant=tenant, status="completed", created_at__gte=start_date
    )
    total_revenue = payments.aggregate(total=Sum("amount"))["total"] or 0
    payment_count = payments.count()
    avg_payment = payments.aggregate(avg=Avg("amount"))["avg"] or 0

    # Voucher stats
    vouchers_created = Voucher.objects.filter(
        tenant=tenant, created_at__gte=start_date
    ).count()
    vouchers_used = Voucher.objects.filter(
        tenant=tenant, is_used=True, used_at__gte=start_date
    ).count()

    # Router stats
    routers = Router.objects.filter(tenant=tenant, is_active=True)
    router_count = routers.count()
    online_routers = routers.filter(status="online").count()

    # Daily trends
    daily_revenue = (
        payments.annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("date")
    )

    daily_users = (
        User.objects.filter(tenant=tenant, created_at__gte=start_date)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )

    return Response(
        {
            "success": True,
            "period": {
                "days": days,
                "start_date": start_date.isoformat(),
                "end_date": timezone.now().isoformat(),
            },
            "users": {
                "total": total_users,
                "active": active_users,
                "new": new_users,
                "expired": total_users - active_users,
            },
            "revenue": {
                "total": float(total_revenue),
                "payment_count": payment_count,
                "average_payment": float(avg_payment),
            },
            "vouchers": {
                "created": vouchers_created,
                "used": vouchers_used,
                "usage_rate": round(
                    (
                        (vouchers_used / vouchers_created * 100)
                        if vouchers_created > 0
                        else 0
                    ),
                    1,
                ),
            },
            "routers": {
                "total": router_count,
                "online": online_routers,
                "offline": router_count - online_routers,
            },
            "trends": {
                "daily_revenue": [
                    {
                        "date": r["date"].isoformat(),
                        "revenue": float(r["total"]),
                        "count": r["count"],
                    }
                    for r in daily_revenue
                ],
                "daily_users": [
                    {"date": r["date"].isoformat(), "count": r["count"]}
                    for r in daily_users
                ],
            },
        }
    )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_analytics_trends(request):
    """Get detailed trend data for charts"""
    from django.db.models import Sum, Count
    from django.db.models.functions import TruncDate, TruncHour
    from .models import User, Payment

    tenant = request.tenant

    # Check permission
    allowed, error = check_analytics_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Parameters
    days = int(request.query_params.get("days", 30))
    metric = request.query_params.get("metric", "revenue")  # revenue, users, payments
    granularity = request.query_params.get("granularity", "daily")  # hourly, daily

    start_date = timezone.now() - timedelta(days=days)
    trunc_func = TruncHour if granularity == "hourly" else TruncDate

    if metric == "revenue":
        data = (
            Payment.objects.filter(
                tenant=tenant, status="completed", created_at__gte=start_date
            )
            .annotate(period=trunc_func("created_at"))
            .values("period")
            .annotate(value=Sum("amount"))
            .order_by("period")
        )
        data_list = [
            {"period": r["period"].isoformat(), "value": float(r["value"])}
            for r in data
        ]

    elif metric == "users":
        data = (
            User.objects.filter(tenant=tenant, created_at__gte=start_date)
            .annotate(period=trunc_func("created_at"))
            .values("period")
            .annotate(value=Count("id"))
            .order_by("period")
        )
        data_list = [
            {"period": r["period"].isoformat(), "value": r["value"]} for r in data
        ]

    elif metric == "payments":
        data = (
            Payment.objects.filter(
                tenant=tenant, status="completed", created_at__gte=start_date
            )
            .annotate(period=trunc_func("created_at"))
            .values("period")
            .annotate(value=Count("id"))
            .order_by("period")
        )
        data_list = [
            {"period": r["period"].isoformat(), "value": r["value"]} for r in data
        ]

    else:
        return Response(
            {"success": False, "error": "Invalid metric"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {
            "success": True,
            "metric": metric,
            "granularity": granularity,
            "period": {"days": days, "start_date": start_date.isoformat()},
            "data": data_list,
        }
    )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_analytics_export(request):
    """Export analytics data"""
    from django.db.models import Sum
    from .models import User, Payment, Voucher
    import csv
    from io import StringIO

    tenant = request.tenant

    # Check permission
    allowed, error = check_analytics_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check data export permission
    if not tenant.subscription_plan.data_export:
        return Response(
            {"success": False, "error": "Data export requires Enterprise plan"},
            status=status.HTTP_403_FORBIDDEN,
        )

    data_type = request.data.get(
        "type", "summary"
    )  # summary, users, payments, vouchers
    format_type = request.data.get("format", "json")  # json, csv
    days = int(request.data.get("days", 30))

    start_date = timezone.now() - timedelta(days=days)

    if data_type == "users":
        users = User.objects.filter(tenant=tenant, created_at__gte=start_date)
        records = [
            {
                "phone": u.phone_number,
                "created_at": u.created_at.isoformat(),
                "paid_until": (u.paid_until.isoformat() if u.paid_until else None),
                "total_payments": u.total_payments,
                "is_active": (u.paid_until > timezone.now() if u.paid_until else False),
            }
            for u in users
        ]
    elif data_type == "payments":
        payments = Payment.objects.filter(tenant=tenant, created_at__gte=start_date)
        records = [
            {
                "id": p.id,
                "user_phone": p.user.phone_number if p.user else None,
                "amount": float(p.amount),
                "status": p.status,
                "payment_channel": p.payment_channel,
                "created_at": p.created_at.isoformat(),
            }
            for p in payments
        ]
    elif data_type == "vouchers":
        vouchers = Voucher.objects.filter(tenant=tenant, created_at__gte=start_date)
        records = [
            {
                "code": v.code,
                "bundle": v.bundle.name if v.bundle else None,
                "is_used": v.is_used,
                "used_by": v.used_by.phone_number if v.used_by else None,
                "used_at": v.used_at.isoformat() if v.used_at else None,
                "created_at": v.created_at.isoformat(),
            }
            for v in vouchers
        ]
    else:
        # Summary
        records = {
            "period": {"days": days, "start_date": start_date.isoformat()},
            "total_users": User.objects.filter(tenant=tenant).count(),
            "new_users": User.objects.filter(
                tenant=tenant, created_at__gte=start_date
            ).count(),
            "total_revenue": float(
                Payment.objects.filter(
                    tenant=tenant, status="completed", created_at__gte=start_date
                ).aggregate(total=Sum("amount"))["total"]
                or 0
            ),
            "total_payments": Payment.objects.filter(
                tenant=tenant, status="completed", created_at__gte=start_date
            ).count(),
            "vouchers_created": Voucher.objects.filter(
                tenant=tenant, created_at__gte=start_date
            ).count(),
        }

    if format_type == "csv" and isinstance(records, list) and len(records) > 0:
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)
        csv_content = output.getvalue()

        return Response(
            {
                "success": True,
                "format": "csv",
                "data_type": data_type,
                "content": csv_content,
                "record_count": len(records),
            }
        )

    return Response(
        {
            "success": True,
            "format": "json",
            "data_type": data_type,
            "data": records,
            "record_count": len(records) if isinstance(records, list) else 1,
        }
    )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_analytics_revenue_breakdown(request):
    """Get revenue breakdown by bundle, router, time"""
    from django.db.models import Sum, Count
    from .models import Payment, Bundle

    tenant = request.tenant

    # Check permission
    allowed, error = check_analytics_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    days = int(request.query_params.get("days", 30))
    start_date = timezone.now() - timedelta(days=days)

    # By bundle
    by_bundle = (
        Payment.objects.filter(
            tenant=tenant,
            status="completed",
            created_at__gte=start_date,
            bundle__isnull=False,
        )
        .values("bundle__name")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )

    # By payment method (payment_channel in this model)
    by_method = (
        Payment.objects.filter(
            tenant=tenant, status="completed", created_at__gte=start_date
        )
        .values("payment_channel")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )

    # By hour of day
    from django.db.models.functions import ExtractHour

    by_hour = (
        Payment.objects.filter(
            tenant=tenant, status="completed", created_at__gte=start_date
        )
        .annotate(hour=ExtractHour("created_at"))
        .values("hour")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("hour")
    )

    return Response(
        {
            "success": True,
            "period": {"days": days},
            "by_bundle": [
                {
                    "bundle": r["bundle__name"],
                    "revenue": float(r["total"]),
                    "count": r["count"],
                }
                for r in by_bundle
            ],
            "by_payment_method": [
                {
                    "method": r["payment_channel"] or "unknown",
                    "revenue": float(r["total"]),
                    "count": r["count"],
                }
                for r in by_method
            ],
            "by_hour": [
                {"hour": r["hour"], "revenue": float(r["total"]), "count": r["count"]}
                for r in by_hour
            ],
        }
    )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_analytics_user_segments(request):
    """Get user segmentation analytics"""
    from django.db.models import Sum, Count, F
    from .models import User, Payment

    tenant = request.tenant

    # Check permission
    allowed, error = check_analytics_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    total_users = User.objects.filter(tenant=tenant).count()

    # Active vs Expired
    active = User.objects.filter(tenant=tenant, paid_until__gt=timezone.now()).count()
    expired = total_users - active

    # By payment frequency
    high_value = User.objects.filter(tenant=tenant, total_payments__gte=5).count()
    medium_value = User.objects.filter(
        tenant=tenant, total_payments__gte=2, total_payments__lt=5
    ).count()
    low_value = User.objects.filter(tenant=tenant, total_payments=1).count()
    no_payments = User.objects.filter(tenant=tenant, total_payments=0).count()

    # Recently active (based on access logs in last 7 days)
    week_ago = timezone.now() - timedelta(days=7)
    from billing.models import AccessLog

    recently_active = (
        User.objects.filter(tenant=tenant, access_logs__timestamp__gte=week_ago)
        .distinct()
        .count()
    )

    # Expiring soon (next 24 hours)
    tomorrow = timezone.now() + timedelta(hours=24)
    expiring_soon = User.objects.filter(
        tenant=tenant, paid_until__gt=timezone.now(), paid_until__lt=tomorrow
    ).count()

    return Response(
        {
            "success": True,
            "total_users": total_users,
            "status_segments": {
                "active": active,
                "expired": expired,
            },
            "value_segments": {
                "high_value": {"count": high_value, "description": "5+ payments"},
                "medium_value": {"count": medium_value, "description": "2-4 payments"},
                "low_value": {"count": low_value, "description": "1 payment"},
                "no_payments": {"count": no_payments, "description": "No payments"},
            },
            "activity_segments": {
                "recently_active": recently_active,
                "expiring_soon": expiring_soon,
            },
        }
    )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_analytics_router_performance(request):
    """Get router performance analytics"""
    from django.db.models import Sum, Count
    from .models import Router, User, Payment

    tenant = request.tenant

    # Check permission
    allowed, error = check_analytics_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    days = int(request.query_params.get("days", 30))
    start_date = timezone.now() - timedelta(days=days)

    routers = Router.objects.filter(tenant=tenant, is_active=True)

    router_stats = []
    for router in routers:
        # Users associated with this router
        user_count = User.objects.filter(tenant=tenant, primary_router=router).count()

        # Revenue from users on this router
        revenue = (
            Payment.objects.filter(
                tenant=tenant,
                status="completed",
                created_at__gte=start_date,
                user__primary_router=router,
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )

        router_stats.append(
            {
                "id": router.id,
                "name": router.name,
                "location": router.location.name if router.location else None,
                "status": router.status,
                "last_seen": (
                    router.last_seen.isoformat() if router.last_seen else None
                ),
                "user_count": user_count,
                "revenue": float(revenue),
            }
        )

    # Sort by revenue
    router_stats.sort(key=lambda x: x["revenue"], reverse=True)

    return Response(
        {
            "success": True,
            "period": {"days": days},
            "routers": router_stats,
            "summary": {
                "total_routers": routers.count(),
                "online": routers.filter(status="online").count(),
                "offline": routers.filter(status="offline").count(),
            },
        }
    )


# =============================================================================
# PPP (Point-to-Point Protocol) MANAGEMENT — Enterprise Plan
# =============================================================================


def check_ppp_permission(tenant):
    """Check if tenant has access to PPP management features (Enterprise only)"""
    if not tenant.subscription_plan:
        return False, "No subscription plan"
    plan_name = tenant.subscription_plan.name.lower()
    if "enterprise" in plan_name:
        return True, None
    return False, "PPP management requires Enterprise plan"


def _create_ppp_customer_bill(customer):
    """
    Create a ClickPesa BillPay control number for a PPP customer.
    This gives them a permanent control number they can use to pay
    via M-Pesa, bank, USSD, etc.

    Returns:
        dict with success, control_number, data
    """
    try:
        from .clickpesa import ClickPesaAPI

        clickpesa = ClickPesaAPI()

        price = int(customer.effective_price)
        business_name = customer.tenant.business_name or "Kitonga WiFi"
        plan_name = customer.plan.name if customer.plan else customer.profile.name

        description = (
            f"{business_name} - {plan_name} - {customer.full_name or customer.username}"
        )

        # Don't pass bill_reference so ClickPesa auto-generates a numeric control number
        result = clickpesa.create_customer_control_number(
            amount=price,
            bill_reference="",
            customer_name=customer.full_name or customer.username,
            customer_phone=customer.phone_number,
            customer_email=customer.email,
            description=description,
            payment_mode="EXACT",
        )

        if result.get("success"):
            control_number = result.get("bill_pay_number", "")
            if control_number:
                customer.control_number = control_number
                customer.save(update_fields=["control_number", "updated_at"])
                logger.info(
                    f"ClickPesa control number {control_number} created for "
                    f"PPP customer {customer.username}"
                )
            return {
                "success": True,
                "control_number": control_number,
                "data": result,
            }
        else:
            logger.error(
                f"Failed to create ClickPesa control number for {customer.username}: "
                f"{result.get('message')}"
            )
            return result

    except Exception as e:
        logger.error(f"Error creating PPP bill for {customer.username}: {e}")
        return {"success": False, "message": str(e)}


def _send_ppp_welcome_sms(customer):
    """
    Send welcome SMS to a new PPP customer with their credentials
    and control number for payment.
    """
    try:
        from .nextsms import TenantNextSMSAPI

        tenant = customer.tenant
        sms_api = TenantNextSMSAPI(tenant)

        if not sms_api.is_configured():
            logger.warning(
                f"Tenant {tenant.slug} has no SMS credentials, skipping PPP welcome SMS"
            )
            return {"success": False, "message": "SMS not configured for tenant"}

        price = customer.effective_price
        business_name = tenant.business_name or "WiFi"

        # Build payment instruction based on whether control number exists
        if customer.control_number:
            pay_line = (
                f"Control No: {customer.control_number}\n"
                f"Pay TSh {price:,.0f} via M-Pesa/Bank using this control number."
            )
        else:
            pay_line = (
                f"Pay TSh {price:,.0f} via M-Pesa/Airtel to activate.\n"
                f"Payment code: PPP-{customer.id}"
            )

        message = (
            f"{business_name} PPPoE Account Created!\n"
            f"Username: {customer.username}\n"
            f"Password: {customer.password}\n"
            f"Plan: {customer.profile.name} ({customer.profile.rate_limit})\n"
            f"{pay_line}"
        )

        result = sms_api.send_sms(
            customer.phone_number,
            message,
            reference=f"PPP-WELCOME-{customer.id}",
        )

        if result.get("success"):
            logger.info(
                f"PPP welcome SMS sent to {customer.phone_number} for {customer.username}"
            )
        else:
            logger.warning(
                f"Failed to send PPP welcome SMS to {customer.phone_number}: {result}"
            )

        return result

    except Exception as e:
        logger.error(f"Error sending PPP welcome SMS: {e}")
        return {"success": False, "message": str(e)}


def _send_ppp_payment_confirmation_sms(customer, payment):
    """Send payment confirmation + activation SMS to PPP customer."""
    try:
        from .nextsms import TenantNextSMSAPI

        tenant = customer.tenant
        sms_api = TenantNextSMSAPI(tenant)

        if not sms_api.is_configured():
            return {"success": False, "message": "SMS not configured"}

        business_name = tenant.business_name or "WiFi"
        paid_until_str = (
            customer.paid_until.strftime("%d %b %Y %H:%M")
            if customer.paid_until
            else "N/A"
        )

        message = (
            f"{business_name}: Payment of TSh {payment.amount:,.0f} received!\n"
            f"Your PPPoE internet is now ACTIVE.\n"
            f"Username: {customer.username}\n"
            f"Valid until: {paid_until_str}\n"
            f"Thank you!"
        )

        return sms_api.send_sms(
            customer.phone_number,
            message,
            reference=f"PPP-PAID-{payment.id}",
        )

    except Exception as e:
        logger.error(f"Error sending PPP payment confirmation SMS: {e}")
        return {"success": False, "message": str(e)}


def _send_ppp_expiry_warning_sms(customer, hours_remaining):
    """Send expiry warning SMS to PPP customer."""
    try:
        from .nextsms import TenantNextSMSAPI

        tenant = customer.tenant
        sms_api = TenantNextSMSAPI(tenant)

        if not sms_api.is_configured():
            return {"success": False, "message": "SMS not configured"}

        business_name = tenant.business_name or "WiFi"
        price = customer.effective_price

        if hours_remaining > 24:
            time_str = f"{hours_remaining // 24} day(s)"
        else:
            time_str = f"{hours_remaining} hour(s)"

        message = (
            f"{business_name}: Your PPPoE internet expires in {time_str}.\n"
            f"Pay TSh {price:,.0f} to continue.\n"
            f"Payment code: PPP-{customer.id}\n"
            f"Username: {customer.username}"
        )

        return sms_api.send_sms(
            customer.phone_number,
            message,
            reference=f"PPP-EXPIRY-{customer.id}",
        )

    except Exception as e:
        logger.error(f"Error sending PPP expiry warning SMS: {e}")
        return {"success": False, "message": str(e)}


def _send_ppp_disabled_sms(customer):
    """Send SMS notifying customer their internet has been disabled."""
    try:
        from .nextsms import TenantNextSMSAPI

        tenant = customer.tenant
        sms_api = TenantNextSMSAPI(tenant)

        if not sms_api.is_configured():
            return {"success": False, "message": "SMS not configured"}

        business_name = tenant.business_name or "WiFi"
        price = customer.effective_price

        message = (
            f"{business_name}: Your PPPoE internet has expired and been disconnected.\n"
            f"Pay TSh {price:,.0f} to reconnect.\n"
            f"Payment code: PPP-{customer.id}"
        )

        return sms_api.send_sms(
            customer.phone_number,
            message,
            reference=f"PPP-DISABLED-{customer.id}",
        )

    except Exception as e:
        logger.error(f"Error sending PPP disabled SMS: {e}")
        return {"success": False, "message": str(e)}


@api_view(["GET", "POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_ppp_profiles(request):
    """
    GET: List PPP profiles for tenant
    POST: Create a new PPP profile
    """
    from .models import PPPProfile, Router
    from .serializers import PPPProfileSerializer, PPPProfileCreateSerializer

    tenant = request.tenant

    allowed, error = check_ppp_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        profiles = PPPProfile.objects.filter(tenant=tenant).select_related("router")

        # Optional filters
        router_id = request.query_params.get("router_id")
        if router_id:
            profiles = profiles.filter(router_id=router_id)
        active_only = request.query_params.get("active")
        if active_only and active_only.lower() == "true":
            profiles = profiles.filter(is_active=True)

        serializer = PPPProfileSerializer(profiles, many=True)

        # Build router summary so frontend knows which routers exist and profile counts
        tenant_routers = Router.objects.filter(tenant=tenant, is_active=True)
        all_profiles = PPPProfile.objects.filter(tenant=tenant)
        router_summary = []
        for r in tenant_routers:
            router_summary.append(
                {
                    "router_id": r.id,
                    "router_name": r.name,
                    "router_host": r.host,
                    "is_active": r.is_active,
                    "profile_count": all_profiles.filter(router=r).count(),
                    "active_profile_count": all_profiles.filter(
                        router=r, is_active=True
                    ).count(),
                }
            )

        return Response(
            {
                "success": True,
                "profiles": serializer.data,
                "total_count": profiles.count(),
                "router_summary": router_summary,
                "available_routers": [
                    {"id": r.id, "name": r.name, "host": r.host} for r in tenant_routers
                ],
            }
        )

    elif request.method == "POST":
        serializer = PPPProfileCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data

        # Validate router belongs to tenant
        try:
            router = Router.objects.get(id=data["router_id"], tenant=tenant)
        except Router.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "Router not found or does not belong to your tenant",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check uniqueness
        if PPPProfile.objects.filter(
            tenant=tenant, router=router, name=data["name"]
        ).exists():
            return Response(
                {
                    "success": False,
                    "error": f"Profile '{data['name']}' already exists on this router",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile = PPPProfile.objects.create(
            tenant=tenant,
            router=router,
            name=data["name"],
            rate_limit=data.get("rate_limit", ""),
            local_address=data.get("local_address"),
            remote_address=data.get("remote_address", ""),
            dns_server=data.get("dns_server", ""),
            service_type=data.get("service_type", "pppoe"),
            session_timeout=data.get("session_timeout", ""),
            idle_timeout=data.get("idle_timeout", ""),
            address_pool=data.get("address_pool", ""),
            monthly_price=data.get("monthly_price", 0),
            is_active=data.get("is_active", True),
        )

        # Optionally sync to router
        sync_result = None
        if data.get("sync_to_router"):
            from .mikrotik import sync_ppp_profile_to_router

            sync_result = sync_ppp_profile_to_router(profile)

        logger.info(f"Tenant {tenant.slug} created PPP profile: {profile.name}")

        return Response(
            {
                "success": True,
                "message": "PPP profile created",
                "profile": PPPProfileSerializer(profile).data,
                "sync_result": sync_result,
            },
            status=status.HTTP_201_CREATED,
        )


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([TenantAPIKeyPermission])
def portal_ppp_profile_detail(request, profile_id):
    """
    GET: Get PPP profile details
    PUT: Update PPP profile
    DELETE: Delete PPP profile
    """
    from .models import PPPProfile
    from .serializers import PPPProfileSerializer

    tenant = request.tenant

    allowed, error = check_ppp_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        profile = PPPProfile.objects.get(id=profile_id, tenant=tenant)
    except PPPProfile.DoesNotExist:
        return Response(
            {"success": False, "error": "PPP profile not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        serializer = PPPProfileSerializer(profile)
        return Response({"success": True, "profile": serializer.data})

    elif request.method == "PUT":
        data = request.data

        if "name" in data:
            profile.name = data["name"]
        if "rate_limit" in data:
            profile.rate_limit = data["rate_limit"]
        if "local_address" in data:
            profile.local_address = data["local_address"] or None
        if "remote_address" in data:
            profile.remote_address = data["remote_address"]
        if "dns_server" in data:
            profile.dns_server = data["dns_server"]
        if "service_type" in data:
            profile.service_type = data["service_type"]
        if "session_timeout" in data:
            profile.session_timeout = data["session_timeout"]
        if "idle_timeout" in data:
            profile.idle_timeout = data["idle_timeout"]
        if "address_pool" in data:
            profile.address_pool = data["address_pool"]
        if "monthly_price" in data:
            profile.monthly_price = data["monthly_price"]
        if "is_active" in data:
            profile.is_active = data["is_active"]

        profile.save()

        # Optionally re-sync to router
        sync_result = None
        if data.get("sync_to_router"):
            from .mikrotik import sync_ppp_profile_to_router

            sync_result = sync_ppp_profile_to_router(profile)

        logger.info(f"Tenant {tenant.slug} updated PPP profile: {profile.name}")

        return Response(
            {
                "success": True,
                "message": "PPP profile updated",
                "profile": PPPProfileSerializer(profile).data,
                "sync_result": sync_result,
            }
        )

    elif request.method == "DELETE":
        # Check for dependent customers
        if profile.customers.exists():
            return Response(
                {
                    "success": False,
                    "error": f"Cannot delete profile '{profile.name}': {profile.customers.count()} customer(s) are using it. Reassign or remove them first.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile_name = profile.name

        # Remove from router if synced
        if profile.synced_to_router:
            from .mikrotik import remove_ppp_profile_from_router

            remove_ppp_profile_from_router(profile)

        profile.delete()
        logger.info(f"Tenant {tenant.slug} deleted PPP profile: {profile_name}")
        return Response(
            {"success": True, "message": f"PPP profile '{profile_name}' deleted"}
        )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_ppp_profile_sync(request, profile_id):
    """Sync a PPP profile to the MikroTik router"""
    from .models import PPPProfile
    from .mikrotik import sync_ppp_profile_to_router

    tenant = request.tenant

    allowed, error = check_ppp_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        profile = PPPProfile.objects.get(id=profile_id, tenant=tenant)
    except PPPProfile.DoesNotExist:
        return Response(
            {"success": False, "error": "PPP profile not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    sync_result = sync_ppp_profile_to_router(profile)

    return Response(
        {
            "success": sync_result["success"],
            "message": sync_result["message"],
            "mikrotik_id": sync_result.get("mikrotik_id", ""),
            "errors": sync_result.get("errors", []),
        },
        status=(
            status.HTTP_200_OK
            if sync_result["success"]
            else status.HTTP_502_BAD_GATEWAY
        ),
    )


# ----- PPP Plans -----


@api_view(["GET", "POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_ppp_plans(request):
    """
    GET: List PPP plans for tenant (optionally filter by profile_id, is_active)
    POST: Create a new PPP plan
    """
    from .models import PPPPlan, PPPProfile
    from .serializers import PPPPlanSerializer, PPPPlanCreateSerializer

    tenant = request.tenant

    allowed, error = check_ppp_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        plans = PPPPlan.objects.filter(tenant=tenant).select_related(
            "profile", "profile__router"
        )

        # Filters
        profile_id = request.GET.get("profile_id")
        if profile_id:
            plans = plans.filter(profile_id=profile_id)

        is_active = request.GET.get("is_active")
        if is_active is not None:
            plans = plans.filter(is_active=is_active.lower() in ("true", "1"))

        billing_cycle = request.GET.get("billing_cycle")
        if billing_cycle:
            plans = plans.filter(billing_cycle=billing_cycle)

        serializer = PPPPlanSerializer(plans, many=True)

        # Build router summary for plans — show per-router plan breakdown
        tenant_routers = Router.objects.filter(tenant=tenant, is_active=True)
        all_plans = PPPPlan.objects.filter(tenant=tenant)
        router_summary = []
        for r in tenant_routers:
            router_plans = all_plans.filter(profile__router=r)
            router_summary.append(
                {
                    "router_id": r.id,
                    "router_name": r.name,
                    "plan_count": router_plans.count(),
                    "active_plan_count": router_plans.filter(is_active=True).count(),
                }
            )

        return Response(
            {
                "success": True,
                "plans": serializer.data,
                "total": plans.count(),
                "router_summary": router_summary,
                "available_routers": [
                    {"id": r.id, "name": r.name, "host": r.host} for r in tenant_routers
                ],
            }
        )

    # POST — Create
    serializer = PPPPlanCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data

    # Validate profile belongs to tenant
    try:
        profile = PPPProfile.objects.get(
            id=data["profile_id"], tenant=tenant, is_active=True
        )
    except PPPProfile.DoesNotExist:
        return Response(
            {"success": False, "error": "PPP Profile not found or inactive"},
            status=status.HTTP_404_NOT_FOUND,
        )

    plan = PPPPlan.objects.create(
        tenant=tenant,
        profile=profile,
        name=data["name"],
        description=data.get("description", ""),
        price=data["price"],
        currency=data.get("currency", "TZS"),
        billing_cycle=data.get("billing_cycle", "monthly"),
        billing_days=data.get("billing_days", 30),
        data_limit_gb=data.get("data_limit_gb"),
        download_speed=data.get("download_speed", ""),
        upload_speed=data.get("upload_speed", ""),
        features=data.get("features", []),
        display_order=data.get("display_order", 0),
        is_popular=data.get("is_popular", False),
        is_active=data.get("is_active", True),
        promo_price=data.get("promo_price"),
        promo_label=data.get("promo_label", ""),
    )

    return Response(
        {
            "success": True,
            "message": f"PPP Plan '{plan.name}' created",
            "plan": PPPPlanSerializer(plan).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([TenantAPIKeyPermission])
def portal_ppp_plan_detail(request, plan_id):
    """
    GET: Retrieve single PPP plan
    PUT: Update PPP plan
    DELETE: Soft-delete (deactivate) PPP plan
    """
    from .models import PPPPlan, PPPProfile
    from .serializers import PPPPlanSerializer, PPPPlanCreateSerializer

    tenant = request.tenant

    allowed, error = check_ppp_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        plan = PPPPlan.objects.select_related("profile", "profile__router").get(
            id=plan_id, tenant=tenant
        )
    except PPPPlan.DoesNotExist:
        return Response(
            {"success": False, "error": "PPP Plan not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        serializer = PPPPlanSerializer(plan)
        return Response({"success": True, "plan": serializer.data})

    if request.method == "DELETE":
        if plan.customers.exists():
            # Don't hard-delete — deactivate
            plan.is_active = False
            plan.save(update_fields=["is_active", "updated_at"])
            return Response(
                {
                    "success": True,
                    "message": f"Plan '{plan.name}' deactivated (has {plan.customer_count} customers)",
                }
            )
        plan.delete()
        return Response({"success": True, "message": f"Plan '{plan.name}' deleted"})

    # PUT — Update
    serializer = PPPPlanCreateSerializer(data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data

    if "profile_id" in data:
        try:
            profile = PPPProfile.objects.get(
                id=data["profile_id"], tenant=tenant, is_active=True
            )
            plan.profile = profile
        except PPPProfile.DoesNotExist:
            return Response(
                {"success": False, "error": "PPP Profile not found or inactive"},
                status=status.HTTP_404_NOT_FOUND,
            )

    # Update fields
    updatable = [
        "name",
        "description",
        "price",
        "currency",
        "billing_cycle",
        "billing_days",
        "data_limit_gb",
        "download_speed",
        "upload_speed",
        "features",
        "display_order",
        "is_popular",
        "is_active",
        "promo_price",
        "promo_label",
    ]
    for field in updatable:
        if field in data:
            setattr(plan, field, data[field])

    plan.save()

    return Response(
        {
            "success": True,
            "message": f"Plan '{plan.name}' updated",
            "plan": PPPPlanSerializer(plan).data,
        }
    )


# ----- PPP Customers -----


@api_view(["GET", "POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_ppp_customers(request):
    """
    GET: List PPP customers for tenant
    POST: Create a new PPP customer
    """
    from .models import PPPCustomer, PPPProfile, Router
    from .serializers import PPPCustomerSerializer, PPPCustomerCreateSerializer

    tenant = request.tenant

    allowed, error = check_ppp_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        customers = PPPCustomer.objects.filter(tenant=tenant).select_related(
            "router", "profile"
        )

        # Optional filters
        router_id = request.query_params.get("router_id")
        if router_id:
            customers = customers.filter(router_id=router_id)
        profile_id = request.query_params.get("profile_id")
        if profile_id:
            customers = customers.filter(profile_id=profile_id)
        status_filter = request.query_params.get("status")
        if status_filter:
            customers = customers.filter(status=status_filter)
        search = request.query_params.get("search")
        if search:
            customers = customers.filter(
                Q(username__icontains=search)
                | Q(full_name__icontains=search)
                | Q(phone_number__icontains=search)
            )

        # Pagination
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 50))
        total_count = customers.count()
        start = (page - 1) * page_size
        customers_page = customers[start : start + page_size]

        serializer = PPPCustomerSerializer(customers_page, many=True)

        # Build per-router breakdown for customers
        tenant_routers = Router.objects.filter(tenant=tenant, is_active=True)
        all_customers = PPPCustomer.objects.filter(tenant=tenant)
        router_summary = []
        for r in tenant_routers:
            rc = all_customers.filter(router=r)
            router_summary.append(
                {
                    "router_id": r.id,
                    "router_name": r.name,
                    "router_host": r.host,
                    "total": rc.count(),
                    "active": rc.filter(status="active").count(),
                    "suspended": rc.filter(status="suspended").count(),
                    "expired": rc.filter(status="expired").count(),
                }
            )

        return Response(
            {
                "success": True,
                "customers": serializer.data,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": (total_count + page_size - 1) // page_size,
                },
                "summary": {
                    "total": total_count,
                    "active": all_customers.filter(status="active").count(),
                    "suspended": all_customers.filter(status="suspended").count(),
                    "expired": all_customers.filter(status="expired").count(),
                },
                "router_summary": router_summary,
                "available_routers": [
                    {"id": r.id, "name": r.name, "host": r.host} for r in tenant_routers
                ],
            }
        )

    elif request.method == "POST":
        serializer = PPPCustomerCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data

        # Validate router belongs to tenant
        try:
            router = Router.objects.get(id=data["router_id"], tenant=tenant)
        except Router.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "Router not found or does not belong to your tenant",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Validate profile belongs to tenant and same router
        try:
            profile = PPPProfile.objects.get(
                id=data["profile_id"], tenant=tenant, router=router
            )
        except PPPProfile.DoesNotExist:
            return Response(
                {"success": False, "error": "PPP profile not found on this router"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check username uniqueness on router
        if PPPCustomer.objects.filter(
            tenant=tenant, router=router, username=data["username"]
        ).exists():
            return Response(
                {
                    "success": False,
                    "error": f"Username '{data['username']}' already exists on this router",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate plan if provided
        plan = None
        if data.get("plan_id"):
            from .models import PPPPlan

            try:
                plan = PPPPlan.objects.get(
                    id=data["plan_id"], tenant=tenant, is_active=True
                )
                # Ensure plan's profile matches the selected profile
                if plan.profile_id != profile.id:
                    return Response(
                        {
                            "success": False,
                            "error": "Plan's profile does not match the selected profile",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except PPPPlan.DoesNotExist:
                return Response(
                    {"success": False, "error": "PPP Plan not found or inactive"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        customer = PPPCustomer.objects.create(
            tenant=tenant,
            router=router,
            profile=profile,
            plan=plan,
            username=data["username"],
            password=data["password"],
            service=data.get("service", ""),
            full_name=data.get("full_name", ""),
            phone_number=data.get("phone_number", ""),
            email=data.get("email", ""),
            address=data.get("address", ""),
            static_ip=data.get("static_ip"),
            mac_address=data.get("mac_address", ""),
            caller_id=data.get("caller_id", ""),
            billing_type=data.get("billing_type", "monthly"),
            monthly_price=data.get("monthly_price"),
            paid_until=data.get("paid_until"),
            comment=data.get("comment", ""),
        )

        # Optionally sync to router
        sync_result = None
        if data.get("sync_to_router"):
            from .mikrotik import sync_ppp_secret_to_router

            sync_result = sync_ppp_secret_to_router(customer)

        # --- Create ClickPesa BillPay control number ---
        bill_result = None
        if customer.phone_number:
            bill_result = _create_ppp_customer_bill(customer)

        # --- Send SMS with credentials & control number ---
        sms_result = None
        if customer.phone_number:
            sms_result = _send_ppp_welcome_sms(customer)

        logger.info(f"Tenant {tenant.slug} created PPP customer: {customer.username}")

        return Response(
            {
                "success": True,
                "message": "PPP customer created",
                "customer": PPPCustomerSerializer(customer).data,
                "sync_result": sync_result,
                "bill_result": bill_result,
                "sms_result": sms_result,
            },
            status=status.HTTP_201_CREATED,
        )


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([TenantAPIKeyPermission])
def portal_ppp_customer_detail(request, customer_id):
    """
    GET: Get PPP customer details
    PUT: Update PPP customer
    DELETE: Delete PPP customer
    """
    from .models import PPPCustomer, PPPProfile
    from .serializers import PPPCustomerSerializer

    tenant = request.tenant

    allowed, error = check_ppp_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        customer = PPPCustomer.objects.select_related("router", "profile").get(
            id=customer_id, tenant=tenant
        )
    except PPPCustomer.DoesNotExist:
        return Response(
            {"success": False, "error": "PPP customer not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        serializer = PPPCustomerSerializer(customer)
        return Response({"success": True, "customer": serializer.data})

    elif request.method == "PUT":
        data = request.data

        if "profile_id" in data:
            try:
                profile = PPPProfile.objects.get(
                    id=data["profile_id"], tenant=tenant, router=customer.router
                )
                customer.profile = profile
            except PPPProfile.DoesNotExist:
                return Response(
                    {"success": False, "error": "PPP profile not found on this router"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        if "plan_id" in data:
            if data["plan_id"] is None:
                customer.plan = None
            else:
                from .models import PPPPlan

                try:
                    plan = PPPPlan.objects.get(
                        id=data["plan_id"], tenant=tenant, is_active=True
                    )
                    customer.plan = plan
                except PPPPlan.DoesNotExist:
                    return Response(
                        {"success": False, "error": "PPP Plan not found or inactive"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

        if "password" in data:
            customer.password = data["password"]
        if "service" in data:
            customer.service = data["service"]
        if "full_name" in data:
            customer.full_name = data["full_name"]
        if "phone_number" in data:
            customer.phone_number = data["phone_number"]
        if "email" in data:
            customer.email = data["email"]
        if "address" in data:
            customer.address = data["address"]
        if "static_ip" in data:
            customer.static_ip = data["static_ip"] or None
        if "mac_address" in data:
            customer.mac_address = data["mac_address"]
        if "caller_id" in data:
            customer.caller_id = data["caller_id"]
        if "billing_type" in data:
            customer.billing_type = data["billing_type"]
        if "monthly_price" in data:
            customer.monthly_price = data["monthly_price"]
        if "paid_until" in data:
            customer.paid_until = data["paid_until"]
        if "comment" in data:
            customer.comment = data["comment"]

        customer.save()

        # Optionally re-sync to router
        sync_result = None
        if data.get("sync_to_router"):
            from .mikrotik import sync_ppp_secret_to_router

            sync_result = sync_ppp_secret_to_router(customer)

        logger.info(f"Tenant {tenant.slug} updated PPP customer: {customer.username}")

        return Response(
            {
                "success": True,
                "message": "PPP customer updated",
                "customer": PPPCustomerSerializer(customer).data,
                "sync_result": sync_result,
            }
        )

    elif request.method == "DELETE":
        username = customer.username

        # Remove from router if synced
        if customer.synced_to_router:
            from .mikrotik import remove_ppp_secret_from_router

            remove_ppp_secret_from_router(customer)

        customer.delete()
        logger.info(f"Tenant {tenant.slug} deleted PPP customer: {username}")
        return Response(
            {"success": True, "message": f"PPP customer '{username}' deleted"}
        )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_ppp_customer_sync(request, customer_id):
    """Sync a PPP customer to the MikroTik router"""
    from .models import PPPCustomer
    from .mikrotik import sync_ppp_secret_to_router

    tenant = request.tenant

    allowed, error = check_ppp_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        customer = PPPCustomer.objects.get(id=customer_id, tenant=tenant)
    except PPPCustomer.DoesNotExist:
        return Response(
            {"success": False, "error": "PPP customer not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    sync_result = sync_ppp_secret_to_router(customer)

    return Response(
        {
            "success": sync_result["success"],
            "message": sync_result["message"],
            "mikrotik_id": sync_result.get("mikrotik_id", ""),
            "errors": sync_result.get("errors", []),
        },
        status=(
            status.HTTP_200_OK
            if sync_result["success"]
            else status.HTTP_502_BAD_GATEWAY
        ),
    )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_ppp_customer_suspend(request, customer_id):
    """Suspend a PPP customer (disable on router + kick session)"""
    from .models import PPPCustomer
    from .mikrotik import suspend_ppp_customer_on_router

    tenant = request.tenant

    allowed, error = check_ppp_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        customer = PPPCustomer.objects.get(id=customer_id, tenant=tenant)
    except PPPCustomer.DoesNotExist:
        return Response(
            {"success": False, "error": "PPP customer not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    reason = request.data.get("reason", "")
    customer.suspend(reason=reason)

    # Sync suspension to router
    router_result = suspend_ppp_customer_on_router(customer)

    logger.info(f"Tenant {tenant.slug} suspended PPP customer: {customer.username}")

    return Response(
        {
            "success": True,
            "message": f"PPP customer '{customer.username}' suspended",
            "router_sync": router_result,
        }
    )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_ppp_customer_activate(request, customer_id):
    """Re-activate a suspended PPP customer"""
    from .models import PPPCustomer
    from .mikrotik import activate_ppp_customer_on_router

    tenant = request.tenant

    allowed, error = check_ppp_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        customer = PPPCustomer.objects.get(id=customer_id, tenant=tenant)
    except PPPCustomer.DoesNotExist:
        return Response(
            {"success": False, "error": "PPP customer not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    customer.activate()

    # Re-enable on router
    router_result = activate_ppp_customer_on_router(customer)

    logger.info(f"Tenant {tenant.slug} activated PPP customer: {customer.username}")

    return Response(
        {
            "success": True,
            "message": f"PPP customer '{customer.username}' activated",
            "router_sync": router_result,
        }
    )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_ppp_active_sessions(request, router_id):
    """Get active PPP sessions on a specific router"""
    from .models import Router
    from .mikrotik import get_ppp_active_sessions

    tenant = request.tenant

    allowed, error = check_ppp_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        router = Router.objects.get(id=router_id, tenant=tenant)
    except Router.DoesNotExist:
        return Response(
            {"success": False, "error": "Router not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    sessions_result = get_ppp_active_sessions(router)

    return Response(
        {
            "success": sessions_result["success"],
            "router": {"id": router.id, "name": router.name},
            "sessions": sessions_result.get("sessions", []),
            "total_sessions": len(sessions_result.get("sessions", [])),
            "errors": sessions_result.get("errors", []),
        }
    )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_ppp_kick_session(request, router_id):
    """Kick a specific PPP active session"""
    from .models import Router
    from .mikrotik import kick_ppp_session

    tenant = request.tenant

    allowed, error = check_ppp_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        router = Router.objects.get(id=router_id, tenant=tenant)
    except Router.DoesNotExist:
        return Response(
            {"success": False, "error": "Router not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    username = request.data.get("username")
    if not username:
        return Response(
            {"success": False, "error": "Username is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    kick_result = kick_ppp_session(router, username)

    return Response(
        {
            "success": kick_result["success"],
            "message": kick_result.get("message", ""),
            "errors": kick_result.get("errors", []),
        }
    )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_ppp_bulk_sync(request):
    """Bulk sync all PPP profiles and customers to router(s)"""
    from .models import PPPProfile, PPPCustomer
    from .mikrotik import sync_ppp_profile_to_router, sync_ppp_secret_to_router

    tenant = request.tenant

    allowed, error = check_ppp_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    router_id = request.data.get("router_id")
    sync_profiles = request.data.get("sync_profiles", True)
    sync_customers = request.data.get("sync_customers", True)

    results = {
        "profiles_synced": 0,
        "profiles_failed": 0,
        "customers_synced": 0,
        "customers_failed": 0,
        "errors": [],
    }

    # Build querysets
    profiles_qs = PPPProfile.objects.filter(tenant=tenant, is_active=True)
    customers_qs = PPPCustomer.objects.filter(tenant=tenant)

    if router_id:
        profiles_qs = profiles_qs.filter(router_id=router_id)
        customers_qs = customers_qs.filter(router_id=router_id)

    # Sync profiles first (customers depend on profiles existing on the router)
    if sync_profiles:
        for profile in profiles_qs:
            try:
                r = sync_ppp_profile_to_router(profile)
                if r["success"]:
                    results["profiles_synced"] += 1
                else:
                    results["profiles_failed"] += 1
                    results["errors"].append(
                        f"Profile '{profile.name}': {r['message']}"
                    )
            except Exception as e:
                results["profiles_failed"] += 1
                results["errors"].append(f"Profile '{profile.name}': {e}")

    # Then sync customers
    if sync_customers:
        for customer in customers_qs:
            try:
                r = sync_ppp_secret_to_router(customer)
                if r["success"]:
                    results["customers_synced"] += 1
                else:
                    results["customers_failed"] += 1
                    results["errors"].append(
                        f"Customer '{customer.username}': {r['message']}"
                    )
            except Exception as e:
                results["customers_failed"] += 1
                results["errors"].append(f"Customer '{customer.username}': {e}")

    overall_success = (results["profiles_failed"] + results["customers_failed"]) == 0

    logger.info(
        f"Tenant {tenant.slug} bulk PPP sync: "
        f"{results['profiles_synced']} profiles, {results['customers_synced']} customers synced"
    )

    return Response(
        {
            "success": overall_success,
            "message": (
                f"Synced {results['profiles_synced']} profiles and {results['customers_synced']} customers"
            ),
            "results": results,
        }
    )


# ==================== PPP BILLPAY (ClickPesa) ENDPOINTS ====================


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_ppp_create_bill(request, customer_id):
    """
    Create or refresh a ClickPesa BillPay control number for a PPP customer.
    If the customer already has one, updates the amount; otherwise creates new.

    POST /api/portal/ppp/customers/<id>/create-bill/
    Body: { "amount": 30000 }  (optional — defaults to effective_price)
    """
    from .models import PPPCustomer

    tenant = request.tenant

    allowed, error = check_ppp_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        customer = PPPCustomer.objects.get(id=customer_id, tenant=tenant)
    except PPPCustomer.DoesNotExist:
        return Response(
            {"success": False, "error": "PPP customer not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    custom_amount = request.data.get("amount")

    if customer.control_number and not custom_amount:
        # Already has a control number and no amount change — update amount
        from .clickpesa import ClickPesaAPI

        clickpesa = ClickPesaAPI()
        update_result = clickpesa.update_bill(
            customer.control_number,
            amount=int(customer.effective_price),
        )
        if update_result.get("success"):
            return Response(
                {
                    "success": True,
                    "message": "Control number amount updated",
                    "control_number": customer.control_number,
                    "amount": int(customer.effective_price),
                    "data": update_result,
                }
            )
        else:
            # Update failed — create a new one
            logger.warning(
                f"Failed to update bill {customer.control_number}, creating new one"
            )

    # Create new control number (or custom amount bill)
    if custom_amount:
        # One-time bill with custom amount
        from .clickpesa import ClickPesaAPI

        clickpesa = ClickPesaAPI()
        business_name = tenant.business_name or "Kitonga WiFi"
        plan_name = customer.plan.name if customer.plan else customer.profile.name

        bill_reference = ""  # Let ClickPesa auto-generate a numeric control number
        description = (
            f"{business_name} - {plan_name} - {customer.full_name or customer.username}"
        )

        result = clickpesa.create_customer_control_number(
            amount=int(custom_amount),
            bill_reference=bill_reference,
            customer_name=customer.full_name or customer.username,
            customer_phone=customer.phone_number,
            customer_email=customer.email,
            description=description,
            payment_mode="EXACT",
        )

        if result.get("success"):
            control_number = result.get("bill_pay_number", "")
            customer.control_number = control_number
            customer.save(update_fields=["control_number", "updated_at"])

            return Response(
                {
                    "success": True,
                    "message": f"Control number created: {control_number}",
                    "control_number": control_number,
                    "amount": int(custom_amount),
                    "data": result,
                },
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(
                {
                    "success": False,
                    "error": result.get("message", "Failed to create control number"),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
    else:
        result = _create_ppp_customer_bill(customer)
        if result.get("success"):
            return Response(
                {
                    "success": True,
                    "message": f"Control number created: {result.get('control_number')}",
                    "control_number": result.get("control_number"),
                    "amount": int(customer.effective_price),
                    "data": result,
                },
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(
                {
                    "success": False,
                    "error": result.get("message", "Failed to create control number"),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_ppp_query_bill(request, customer_id):
    """
    Query the ClickPesa BillPay status for a PPP customer.

    GET /api/portal/ppp/customers/<id>/bill-status/
    """
    from .models import PPPCustomer
    from .clickpesa import ClickPesaAPI

    tenant = request.tenant

    allowed, error = check_ppp_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        customer = PPPCustomer.objects.get(id=customer_id, tenant=tenant)
    except PPPCustomer.DoesNotExist:
        return Response(
            {"success": False, "error": "PPP customer not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not customer.control_number:
        return Response(
            {
                "success": False,
                "error": "No control number for this customer. Use create-bill first.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    clickpesa = ClickPesaAPI()
    result = clickpesa.query_bill_status(customer.control_number)

    if result.get("success"):
        return Response(
            {
                "success": True,
                "customer": customer.username,
                "control_number": customer.control_number,
                "bill": result,
            }
        )
    else:
        return Response(
            {"success": False, "error": result.get("message", "Query failed")},
            status=status.HTTP_502_BAD_GATEWAY,
        )


# ==================== PPP PAYMENT ENDPOINTS ====================


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_ppp_initiate_payment(request, customer_id):
    """
    Initiate a payment for a PPPoE customer via Snippe mobile money USSD push.
    This creates a PPPPayment record and triggers USSD on the customer's phone.

    POST /api/portal/ppp/customers/<id>/pay/
    Body: { "billing_days": 30 }  (optional, defaults to 30)
    """
    from .models import PPPCustomer, PPPPayment
    from .snippe import SnippeAPI

    tenant = request.tenant

    allowed, error = check_ppp_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        customer = PPPCustomer.objects.get(id=customer_id, tenant=tenant)
    except PPPCustomer.DoesNotExist:
        return Response(
            {"success": False, "error": "PPP customer not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    billing_days = int(request.data.get("billing_days", 0))

    # If customer has a plan, use plan's billing cycle and price by default
    if customer.plan and billing_days == 0:
        billing_days = customer.plan.billing_days
    elif billing_days == 0:
        billing_days = 30  # Default fallback

    if billing_days < 1 or billing_days > 365:
        return Response(
            {"success": False, "error": "billing_days must be between 1 and 365"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Calculate amount: plan price > customer override > profile default
    import math

    if customer.plan and billing_days == customer.plan.billing_days:
        # Exact plan cycle — use plan's effective (promo) price
        amount = int(customer.plan.effective_price)
    else:
        # Pro-rate from the effective monthly/cycle price
        base_price = customer.effective_price
        daily_rate = base_price / 30
        amount = math.ceil(daily_rate * billing_days)
        if billing_days == 30:
            amount = int(base_price)

    # Check for existing pending payment for this customer
    pending = PPPPayment.objects.filter(customer=customer, status="pending").first()
    if pending:
        # Expire old pending payment to avoid duplicates
        pending.status = "expired"
        pending.save(update_fields=["status"])

    # Create order reference with PPP prefix
    order_reference = f"PPP{customer.id}{uuid.uuid4().hex[:8].upper()}"

    # Create PPP payment record
    ppp_payment = PPPPayment.objects.create(
        tenant=tenant,
        customer=customer,
        amount=amount,
        phone_number=customer.phone_number,
        order_reference=order_reference,
        payment_channel="snippe",
        status="pending",
        billing_days=billing_days,
    )

    logger.info(
        f"PPP payment initiated: ref={order_reference} customer={customer.username} "
        f"amount={amount} days={billing_days} tenant={tenant.slug}"
    )

    # Build webhook URL
    from django.conf import settings as django_settings

    webhook_url = getattr(django_settings, "SNIPPE_WEBHOOK_URL", "") or ""

    # Initiate Snippe mobile money payment
    snippe = SnippeAPI()
    metadata = {
        "order_reference": order_reference,
        "payment_type": "ppp",
        "customer_id": str(customer.id),
        "tenant": tenant.slug,
    }

    name_parts = (customer.full_name or customer.username).split(" ", 1)
    firstname = name_parts[0]
    lastname = name_parts[1] if len(name_parts) > 1 else ""
    customer_email = customer.email or f"{customer.phone_number}@kitonga.klikcell.com"

    result = snippe.create_mobile_payment(
        phone_number=customer.phone_number,
        amount=int(amount),
        firstname=firstname,
        lastname=lastname,
        email=customer_email,
        webhook_url=webhook_url,
        metadata=metadata,
        idempotency_key=order_reference,
    )

    if result.get("success"):
        # Store Snippe reference
        snippe_reference = result.get("reference", "")
        if snippe_reference:
            ppp_payment.payment_reference = snippe_reference
            ppp_payment.save(update_fields=["payment_reference"])

        return Response(
            {
                "success": True,
                "message": f"Payment request of TSh {amount:,} sent to {customer.phone_number}",
                "payment": {
                    "id": ppp_payment.id,
                    "order_reference": order_reference,
                    "snippe_reference": snippe_reference,
                    "amount": str(amount),
                    "billing_days": billing_days,
                    "status": "pending",
                    "customer": customer.username,
                    "phone_number": customer.phone_number,
                },
            },
            status=status.HTTP_201_CREATED,
        )
    else:
        ppp_payment.mark_failed()
        error_msg = result.get("message", result.get("error", "Snippe payment failed"))
        logger.error(f"PPP Snippe payment failed: {error_msg}")

        return Response(
            {
                "success": False,
                "error": f"Payment initiation failed: {error_msg}",
                "order_reference": order_reference,
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_ppp_payment_history(request, customer_id):
    """
    Get payment history for a PPPoE customer.
    GET /api/portal/ppp/customers/<id>/payments/
    """
    from .models import PPPCustomer, PPPPayment

    tenant = request.tenant

    allowed, error = check_ppp_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        customer = PPPCustomer.objects.get(id=customer_id, tenant=tenant)
    except PPPCustomer.DoesNotExist:
        return Response(
            {"success": False, "error": "PPP customer not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    payments = PPPPayment.objects.filter(customer=customer).order_by("-created_at")

    payment_data = [
        {
            "id": p.id,
            "amount": str(p.amount),
            "billing_days": p.billing_days,
            "order_reference": p.order_reference,
            "payment_reference": p.payment_reference,
            "payment_channel": p.payment_channel,
            "control_number": p.control_number,
            "status": p.status,
            "phone_number": p.phone_number,
            "created_at": p.created_at.isoformat(),
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        }
        for p in payments
    ]

    return Response(
        {
            "success": True,
            "customer": customer.username,
            "total_payments": len(payment_data),
            "payments": payment_data,
        }
    )


# =============================================================================
# REMOTE ACCESS (VPN / WIREGUARD) PORTAL ENDPOINTS — Enterprise Plan
# =============================================================================


def check_remote_access_permission(tenant):
    """
    Check that the tenant's subscription plan allows remote user access.
    Returns (allowed: bool, error: str).
    """
    if not tenant:
        return False, "Tenant not found"
    if not tenant.is_subscription_valid():
        return False, "Subscription expired or invalid"
    plan = tenant.subscription_plan
    if not plan:
        return False, "No subscription plan"
    if not plan.remote_user_access:
        return (
            False,
            "Remote access is not available on your current plan. Upgrade to Enterprise.",
        )
    return True, ""


# ---- VPN Configuration ----


@api_view(["GET", "POST", "PUT"])
@permission_classes([TenantAPIKeyPermission])
def portal_vpn_config(request):
    """
    GET  — Retrieve current VPN configuration for the tenant.
    POST — Create a new VPN configuration.
    PUT  — Update existing VPN configuration.

    Endpoint: /api/portal/vpn/config/
    """
    tenant = request.tenant

    allowed, error = check_remote_access_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        try:
            vpn_config = TenantVPNConfig.objects.get(tenant=tenant)
            serializer = TenantVPNConfigSerializer(vpn_config)
            return Response({"success": True, "vpn_config": serializer.data})
        except TenantVPNConfig.DoesNotExist:
            return Response(
                {
                    "success": True,
                    "vpn_config": None,
                    "message": "No VPN configuration found. Create one to get started.",
                }
            )

    # POST or PUT
    serializer = TenantVPNConfigCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data
    router_id = data.pop("router_id")
    sync_to_router = data.pop("sync_to_router", False)

    try:
        router = Router.objects.get(id=router_id, tenant=tenant, is_active=True)
    except Router.DoesNotExist:
        return Response(
            {"success": False, "error": "Router not found or not active"},
            status=status.HTTP_404_NOT_FOUND,
        )

    from .wireguard_utils import generate_wireguard_keypair

    if request.method == "POST":
        # Check if config already exists
        if TenantVPNConfig.objects.filter(tenant=tenant).exists():
            return Response(
                {
                    "success": False,
                    "error": "VPN configuration already exists. Use PUT to update.",
                },
                status=status.HTTP_409_CONFLICT,
            )

        keypair = generate_wireguard_keypair()
        vpn_config = TenantVPNConfig.objects.create(
            tenant=tenant,
            router=router,
            server_private_key=keypair["private_key"],
            server_public_key=keypair["public_key"],
            **data,
        )
        message = "VPN configuration created"
    else:
        # PUT — update
        try:
            vpn_config = TenantVPNConfig.objects.get(tenant=tenant)
        except TenantVPNConfig.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "No VPN configuration to update. Use POST to create.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        vpn_config.router = router
        for key, value in data.items():
            setattr(vpn_config, key, value)
        vpn_config.save()
        message = "VPN configuration updated"

    # Optionally sync to router
    sync_result = None
    if sync_to_router:
        from .mikrotik import sync_vpn_config_to_router

        sync_result = sync_vpn_config_to_router(vpn_config)
        if sync_result["success"]:
            message += " and synced to router"
        else:
            message += f" but router sync failed: {sync_result['message']}"

    resp_serializer = TenantVPNConfigSerializer(vpn_config)
    return Response(
        {
            "success": True,
            "message": message,
            "vpn_config": resp_serializer.data,
            "sync_result": sync_result,
        },
        status=(
            status.HTTP_201_CREATED if request.method == "POST" else status.HTTP_200_OK
        ),
    )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_vpn_sync(request):
    """
    Full sync of VPN configuration + all active peers to the router.

    Endpoint: POST /api/portal/vpn/sync/
    """
    tenant = request.tenant

    allowed, error = check_remote_access_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        vpn_config = TenantVPNConfig.objects.get(tenant=tenant)
    except TenantVPNConfig.DoesNotExist:
        return Response(
            {
                "success": False,
                "error": "No VPN configuration found. Create one first.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    from .mikrotik import sync_vpn_config_to_router

    result = sync_vpn_config_to_router(vpn_config)

    return Response(
        {
            "success": result["success"],
            "message": result["message"],
            "interface_result": result.get("interface_result"),
            "peer_results": result.get("peer_results"),
            "firewall_result": result.get("firewall_result"),
            "errors": result.get("errors", []),
        },
        status=status.HTTP_200_OK if result["success"] else status.HTTP_502_BAD_GATEWAY,
    )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_vpn_teardown(request):
    """
    Full teardown — remove WireGuard interface, all peers, firewall rules,
    and bandwidth queues from the router.

    Endpoint: POST /api/portal/vpn/teardown/
    """
    tenant = request.tenant

    allowed, error = check_remote_access_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        vpn_config = TenantVPNConfig.objects.get(tenant=tenant)
    except TenantVPNConfig.DoesNotExist:
        return Response(
            {"success": False, "error": "No VPN configuration found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    from .mikrotik import full_teardown_vpn

    result = full_teardown_vpn(vpn_config)

    return Response(
        {
            "success": result["success"],
            "message": (
                "VPN fully removed from router"
                if result["success"]
                else "Teardown encountered errors"
            ),
            "details": result.get("details"),
            "errors": result.get("errors", []),
        }
    )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_vpn_status(request):
    """
    Get live WireGuard peer status from the router (handshake, traffic, endpoint).

    Endpoint: GET /api/portal/vpn/status/
    """
    tenant = request.tenant

    allowed, error = check_remote_access_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        vpn_config = TenantVPNConfig.objects.get(tenant=tenant)
    except TenantVPNConfig.DoesNotExist:
        return Response(
            {"success": False, "error": "No VPN configuration found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    from .mikrotik import get_wireguard_peer_status

    result = get_wireguard_peer_status(vpn_config)

    # Enrich with local DB data
    peer_map = {}
    for peer in result.get("peers", []):
        peer_map[peer["public_key"]] = peer

    remote_users = RemoteUser.objects.filter(vpn_config=vpn_config)
    enriched = []
    for ru in remote_users:
        live_data = peer_map.get(ru.public_key, {})
        enriched.append(
            {
                "id": str(ru.id),
                "name": ru.name,
                "assigned_ip": ru.assigned_ip,
                "status": ru.status,
                "is_active": ru.is_active,
                "expires_at": ru.expires_at.isoformat() if ru.expires_at else None,
                "is_expired": ru.is_expired,
                "last_handshake_db": (
                    ru.last_handshake.isoformat() if ru.last_handshake else None
                ),
                "last_handshake_live": live_data.get("last_handshake", ""),
                "endpoint": live_data.get("endpoint", ""),
                "endpoint_port": live_data.get("endpoint_port", ""),
                "rx": live_data.get("rx", "0"),
                "tx": live_data.get("tx", "0"),
                "disabled_on_router": live_data.get("disabled", "false"),
                "is_configured_on_router": ru.is_configured_on_router,
            }
        )

    return Response(
        {
            "success": result["success"],
            "vpn_interface": vpn_config.interface_name,
            "is_configured_on_router": vpn_config.is_configured_on_router,
            "total_peers": len(enriched),
            "peers": enriched,
            "errors": result.get("errors", []),
        }
    )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_vps_peer_status(request):
    """
    Get live WireGuard peer status from the VPS wg0 hub (handshake, traffic, endpoint).

    Endpoint: GET /api/portal/vpn/vps-status/
    """
    tenant = request.tenant

    allowed, error = check_remote_access_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        vpn_config = TenantVPNConfig.objects.get(tenant=tenant)
    except TenantVPNConfig.DoesNotExist:
        return Response(
            {"success": False, "error": "No VPN configuration found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    from .vps_wireguard import vps_get_peer_status

    result = vps_get_peer_status()

    # Enrich with local DB data
    peer_map = {}
    for peer in result.get("peers", []):
        peer_map[peer["public_key"]] = peer

    remote_users = RemoteUser.objects.filter(vpn_config=vpn_config)
    enriched = []
    for ru in remote_users:
        live_data = peer_map.get(ru.public_key, {})
        enriched.append(
            {
                "id": str(ru.id),
                "name": ru.name,
                "assigned_ip": ru.assigned_ip,
                "status": ru.status,
                "is_active": ru.is_active,
                "expires_at": ru.expires_at.isoformat() if ru.expires_at else None,
                "is_expired": ru.is_expired,
                "last_handshake_db": (
                    ru.last_handshake.isoformat() if ru.last_handshake else None
                ),
                "last_handshake_live": live_data.get("last_handshake", ""),
                "endpoint": live_data.get("endpoint", ""),
                "endpoint_port": live_data.get("endpoint_port", ""),
                "rx": live_data.get("rx", 0),
                "tx": live_data.get("tx", 0),
                "is_configured_on_router": ru.is_configured_on_router,
            }
        )

    return Response(
        {
            "success": result["success"],
            "source": "vps_wg0",
            "vpn_interface": vpn_config.interface_name,
            "total_peers": len(enriched),
            "peers": enriched,
            "errors": result.get("errors", []),
        }
    )


# ---- Remote Access Plans ----


@api_view(["GET", "POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_remote_plans(request):
    """
    GET  — List all remote access plans for this tenant.
    POST — Create a new remote access plan.

    Endpoint: /api/portal/vpn/plans/
    """
    tenant = request.tenant

    allowed, error = check_remote_access_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        plans = RemoteAccessPlan.objects.filter(tenant=tenant).order_by(
            "display_order", "price"
        )
        active_only = request.query_params.get("active_only", "false").lower() == "true"
        if active_only:
            plans = plans.filter(is_active=True)
        serializer = RemoteAccessPlanSerializer(plans, many=True)

        # Include VPN config/router context
        vpn_config_info = None
        try:
            vpn_config = TenantVPNConfig.objects.select_related("router").get(
                tenant=tenant
            )
            vpn_config_info = {
                "vpn_config_id": str(vpn_config.id),
                "router_id": vpn_config.router.id,
                "router_name": vpn_config.router.name,
                "router_host": vpn_config.router.host,
            }
        except TenantVPNConfig.DoesNotExist:
            vpn_config_info = None

        return Response(
            {
                "success": True,
                "total": plans.count(),
                "plans": serializer.data,
                "vpn_config": vpn_config_info,
            }
        )

    # POST
    serializer = RemoteAccessPlanCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    plan = RemoteAccessPlan.objects.create(tenant=tenant, **serializer.validated_data)
    resp = RemoteAccessPlanSerializer(plan)
    return Response(
        {"success": True, "message": "Plan created", "plan": resp.data},
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([TenantAPIKeyPermission])
def portal_remote_plan_detail(request, plan_id):
    """
    GET    — Get plan details.
    PUT    — Update a plan.
    DELETE — Deactivate (soft-delete) a plan.

    Endpoint: /api/portal/vpn/plans/<plan_id>/
    """
    tenant = request.tenant

    allowed, error = check_remote_access_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        plan = RemoteAccessPlan.objects.get(id=plan_id, tenant=tenant)
    except RemoteAccessPlan.DoesNotExist:
        return Response(
            {"success": False, "error": "Plan not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        serializer = RemoteAccessPlanSerializer(plan)
        return Response({"success": True, "plan": serializer.data})

    if request.method == "DELETE":
        plan.is_active = False
        plan.save(update_fields=["is_active", "updated_at"])
        return Response({"success": True, "message": f"Plan '{plan.name}' deactivated"})

    # PUT
    serializer = RemoteAccessPlanCreateSerializer(data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    for key, value in serializer.validated_data.items():
        setattr(plan, key, value)
    plan.save()
    resp = RemoteAccessPlanSerializer(plan)
    return Response({"success": True, "message": "Plan updated", "plan": resp.data})


# ---- Remote Users (CRUD + Provisioning) ----


@api_view(["GET", "POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_remote_users(request):
    """
    GET  — List all remote users for this tenant.
    POST — Create (provision) a new remote user with WireGuard keys.

    Endpoint: /api/portal/vpn/users/
    """
    tenant = request.tenant

    allowed, error = check_remote_access_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        users = RemoteUser.objects.filter(tenant=tenant).select_related(
            "plan", "vpn_config"
        )

        # Filters
        status_filter = request.query_params.get("status")
        if status_filter:
            users = users.filter(status=status_filter)

        search = request.query_params.get("search")
        if search:
            users = users.filter(
                Q(name__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
                | Q(assigned_ip__icontains=search)
            )

        serializer = RemoteUserSerializer(users, many=True)

        # Include VPN config/router context so frontend knows which router is being managed
        vpn_config_info = None
        try:
            vpn_config = TenantVPNConfig.objects.select_related("router").get(
                tenant=tenant
            )
            vpn_config_info = {
                "vpn_config_id": str(vpn_config.id),
                "router_id": vpn_config.router.id,
                "router_name": vpn_config.router.name,
                "router_host": vpn_config.router.host,
                "interface_name": vpn_config.interface_name,
                "address_pool": vpn_config.address_pool,
                "server_address": str(vpn_config.server_address),
            }
        except TenantVPNConfig.DoesNotExist:
            vpn_config_info = None

        # Summary by status
        all_remote = RemoteUser.objects.filter(tenant=tenant)
        summary = {
            "total": all_remote.count(),
            "active": all_remote.filter(status="active").count(),
            "suspended": all_remote.filter(status="suspended").count(),
            "expired": all_remote.filter(status="expired").count(),
            "revoked": all_remote.filter(status="revoked").count(),
        }

        return Response(
            {
                "success": True,
                "total": users.count(),
                "users": serializer.data,
                "vpn_config": vpn_config_info,
                "summary": summary,
            }
        )

    # POST — provision new remote user
    serializer = RemoteUserCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data

    # Ensure VPN config exists
    try:
        vpn_config = TenantVPNConfig.objects.get(tenant=tenant)
    except TenantVPNConfig.DoesNotExist:
        return Response(
            {
                "success": False,
                "error": "No VPN configuration found. Set up VPN config first.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Check tenant limit
    if not tenant.can_add_remote_user():
        return Response(
            {"success": False, "error": "Remote user limit reached for your plan."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Resolve plan
    plan = None
    plan_id = data.pop("plan_id", None)
    if plan_id:
        try:
            plan = RemoteAccessPlan.objects.get(
                id=plan_id, tenant=tenant, is_active=True
            )
        except RemoteAccessPlan.DoesNotExist:
            return Response(
                {"success": False, "error": "Remote access plan not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

    sync_to_router = data.pop("sync_to_router", False)
    use_psk = data.pop("use_preshared_key", True)

    # Get created_by from token auth
    created_by = (
        request.user if request.user and request.user.is_authenticated else None
    )

    from .wireguard_utils import provision_remote_user_keys

    prov_result = provision_remote_user_keys(
        vpn_config=vpn_config,
        name=data["name"],
        email=data.get("email", ""),
        phone=data.get("phone", ""),
        notes=data.get("notes", ""),
        plan=plan,
        created_by=created_by,
        use_preshared_key=use_psk,
    )

    if not prov_result["success"]:
        return Response(
            {"success": False, "error": prov_result["error"]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    remote_user = prov_result["remote_user"]

    # Optionally sync peer to router + bandwidth queue
    sync_peer_result = None
    if sync_to_router:
        from .mikrotik import add_wireguard_peer, setup_wireguard_bandwidth_queue

        sync_peer_result = add_wireguard_peer(remote_user)
        if sync_peer_result["success"]:
            setup_wireguard_bandwidth_queue(remote_user)

    resp = RemoteUserSerializer(remote_user)
    return Response(
        {
            "success": True,
            "message": f"Remote user '{remote_user.name}' provisioned ({remote_user.assigned_ip})",
            "user": resp.data,
            "private_key": prov_result["private_key"],
            "config_text": prov_result["config_text"],
            "sync_result": sync_peer_result,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([TenantAPIKeyPermission])
def portal_remote_user_detail(request, user_id):
    """
    GET    — Get remote user details.
    PUT    — Update remote user fields.
    DELETE — Revoke / remove remote user.

    Endpoint: /api/portal/vpn/users/<user_id>/
    """
    tenant = request.tenant

    allowed, error = check_remote_access_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        remote_user = RemoteUser.objects.select_related("plan", "vpn_config").get(
            id=user_id, tenant=tenant
        )
    except RemoteUser.DoesNotExist:
        return Response(
            {"success": False, "error": "Remote user not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        serializer = RemoteUserSerializer(remote_user)
        return Response({"success": True, "user": serializer.data})

    if request.method == "DELETE":
        # Remove peer from router
        from .mikrotik import remove_wireguard_peer, remove_wireguard_bandwidth_queue

        remove_wireguard_peer(remote_user)
        remove_wireguard_bandwidth_queue(remote_user)

        # Log the revocation
        RemoteAccessLog.objects.create(
            tenant=tenant,
            remote_user=remote_user,
            event_type="revoked",
            event_details=f"User '{remote_user.name}' revoked and removed from router",
        )

        remote_user.status = "revoked"
        remote_user.is_active = False
        remote_user.save(update_fields=["status", "is_active", "updated_at"])

        return Response(
            {
                "success": True,
                "message": f"Remote user '{remote_user.name}' revoked and removed from router",
            }
        )

    # PUT — update
    serializer = RemoteUserUpdateSerializer(data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data

    # Handle plan change
    plan_id = data.pop("plan_id", None)
    if plan_id is not None:
        if plan_id:
            try:
                plan = RemoteAccessPlan.objects.get(
                    id=plan_id, tenant=tenant, is_active=True
                )
                remote_user.plan = plan
            except RemoteAccessPlan.DoesNotExist:
                return Response(
                    {"success": False, "error": "Plan not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            remote_user.plan = None

    # Handle status change (enable/disable on router)
    new_status = data.pop("status", None)
    if new_status and new_status != remote_user.status:
        from .mikrotik import disable_wireguard_peer, enable_wireguard_peer

        if new_status == "disabled":
            disable_wireguard_peer(remote_user)
            remote_user.status = "disabled"
            remote_user.is_active = False
            RemoteAccessLog.objects.create(
                tenant=tenant,
                remote_user=remote_user,
                event_type="revoked",
                event_details="User disabled via portal",
            )
        elif new_status == "active":
            enable_wireguard_peer(remote_user)
            remote_user.status = "active"
            remote_user.is_active = True
            RemoteAccessLog.objects.create(
                tenant=tenant,
                remote_user=remote_user,
                event_type="reactivated",
                event_details="User re-enabled via portal",
            )
        elif new_status == "revoked":
            from .mikrotik import (
                remove_wireguard_peer,
                remove_wireguard_bandwidth_queue,
            )

            remove_wireguard_peer(remote_user)
            remove_wireguard_bandwidth_queue(remote_user)
            remote_user.status = "revoked"
            remote_user.is_active = False

    # Apply remaining fields
    for key, value in data.items():
        setattr(remote_user, key, value)
    remote_user.save()

    # If bandwidth changed, update queue on router
    if (
        "bandwidth_limit_up" in serializer.validated_data
        or "bandwidth_limit_down" in serializer.validated_data
    ):
        from .mikrotik import setup_wireguard_bandwidth_queue

        setup_wireguard_bandwidth_queue(remote_user)

    resp = RemoteUserSerializer(remote_user)
    return Response(
        {"success": True, "message": "Remote user updated", "user": resp.data}
    )


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_remote_user_sync(request, user_id):
    """
    Sync a single remote user's peer to the router.

    Endpoint: POST /api/portal/vpn/users/<user_id>/sync/
    """
    tenant = request.tenant

    allowed, error = check_remote_access_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        remote_user = RemoteUser.objects.get(id=user_id, tenant=tenant)
    except RemoteUser.DoesNotExist:
        return Response(
            {"success": False, "error": "Remote user not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    from .mikrotik import add_wireguard_peer, setup_wireguard_bandwidth_queue

    peer_result = add_wireguard_peer(remote_user)
    queue_result = None
    if peer_result["success"]:
        queue_result = setup_wireguard_bandwidth_queue(remote_user)

    RemoteAccessLog.objects.create(
        tenant=tenant,
        remote_user=remote_user,
        event_type="peer_added" if peer_result["success"] else "peer_removed",
        event_details=peer_result["message"],
    )

    return Response(
        {
            "success": peer_result["success"],
            "message": peer_result["message"],
            "peer_result": peer_result,
            "queue_result": queue_result,
        }
    )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_remote_user_config(request, user_id):
    """
    Download the WireGuard client config for a remote user.
    Returns the .conf file content and optionally a QR code data string.

    Endpoint: GET /api/portal/vpn/users/<user_id>/config/
    """
    tenant = request.tenant

    allowed, error = check_remote_access_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        remote_user = RemoteUser.objects.select_related("vpn_config").get(
            id=user_id, tenant=tenant
        )
    except RemoteUser.DoesNotExist:
        return Response(
            {"success": False, "error": "Remote user not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    config_text = remote_user.generate_client_config()

    # Mark as downloaded
    if not remote_user.config_downloaded:
        remote_user.config_downloaded = True
        remote_user.save(update_fields=["config_downloaded", "updated_at"])

        RemoteAccessLog.objects.create(
            tenant=tenant,
            remote_user=remote_user,
            event_type="config_downloaded",
            event_details="Config file downloaded via portal",
        )

    # Return as .conf file or JSON
    fmt = request.query_params.get("format", "json")
    if fmt == "file":
        response = HttpResponse(config_text, content_type="text/plain")
        response["Content-Disposition"] = (
            f'attachment; filename="wg-{remote_user.name.replace(" ", "_")}.conf"'
        )
        return response

    from .wireguard_utils import generate_qr_code_data

    return Response(
        {
            "success": True,
            "user": {
                "id": str(remote_user.id),
                "name": remote_user.name,
                "assigned_ip": remote_user.assigned_ip,
            },
            "config_text": config_text,
            "qr_code_data": generate_qr_code_data(config_text),
            "has_private_key": bool(remote_user.private_key),
        }
    )


# ---- Remote User Payments ----


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_remote_user_pay(request, user_id):
    """
    Initiate a mobile money payment for a remote user's VPN access.

    Endpoint: POST /api/portal/vpn/users/<user_id>/pay/
    """
    tenant = request.tenant

    allowed, error = check_remote_access_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        remote_user = RemoteUser.objects.select_related("plan").get(
            id=user_id, tenant=tenant
        )
    except RemoteUser.DoesNotExist:
        return Response(
            {"success": False, "error": "Remote user not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = RemoteUserPaymentInitiateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data

    # Resolve plan
    plan_id = data.get("plan_id")
    plan = None
    if plan_id:
        try:
            plan = RemoteAccessPlan.objects.get(
                id=plan_id, tenant=tenant, is_active=True
            )
        except RemoteAccessPlan.DoesNotExist:
            return Response(
                {"success": False, "error": "Plan not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
    else:
        plan = remote_user.plan

    if not plan:
        return Response(
            {
                "success": False,
                "error": "No plan specified and user has no current plan.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    billing_days = data.get("billing_days") or plan.billing_days
    if billing_days < 1:
        billing_days = plan.billing_days or 30

    import math

    if billing_days == plan.billing_days:
        amount = int(plan.effective_price)
    else:
        daily_rate = plan.effective_price / max(plan.billing_days, 1)
        amount = math.ceil(daily_rate * billing_days)

    phone = data.get("phone_number") or remote_user.phone
    if not phone:
        return Response(
            {"success": False, "error": "Phone number required for payment."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Expire old pending payments
    RemoteAccessPayment.objects.filter(
        remote_user=remote_user, status="pending"
    ).update(status="expired")

    # Create payment record
    payment = RemoteAccessPayment.objects.create(
        tenant=tenant,
        remote_user=remote_user,
        plan=plan,
        amount=amount,
        billing_days=billing_days,
        phone_number=phone,
        payment_channel="snippe",
        status="pending",
    )

    logger.info(
        f"VPN payment initiated: ref={payment.order_reference} user={remote_user.name} "
        f"amount={amount} days={billing_days} tenant={tenant.slug}"
    )

    # Initiate Snippe payment
    from .snippe import SnippeAPI
    from django.conf import settings as django_settings

    webhook_url = getattr(django_settings, "SNIPPE_WEBHOOK_URL", "") or ""

    snippe = SnippeAPI()
    metadata = {
        "order_reference": payment.order_reference,
        "payment_type": "vpn",
        "remote_user_id": str(remote_user.id),
        "tenant": tenant.slug,
    }

    name_parts = (remote_user.name or "VPN User").split(" ", 1)
    firstname = name_parts[0]
    lastname = name_parts[1] if len(name_parts) > 1 else ""
    email = remote_user.email or f"{phone}@kitonga.klikcell.com"

    result = snippe.create_mobile_payment(
        phone_number=phone,
        amount=int(amount),
        firstname=firstname,
        lastname=lastname,
        email=email,
        webhook_url=webhook_url,
        metadata=metadata,
        idempotency_key=payment.order_reference,
    )

    if result.get("success"):
        snippe_ref = result.get("reference", "")
        if snippe_ref:
            payment.payment_reference = snippe_ref
            payment.save(update_fields=["payment_reference"])

        return Response(
            {
                "success": True,
                "message": f"Payment request of TSh {amount:,} sent to {phone}",
                "payment": {
                    "id": str(payment.id),
                    "order_reference": payment.order_reference,
                    "snippe_reference": snippe_ref,
                    "amount": str(amount),
                    "billing_days": billing_days,
                    "plan_name": plan.name,
                    "status": "pending",
                    "phone_number": phone,
                },
            },
            status=status.HTTP_201_CREATED,
        )
    else:
        payment.mark_failed()
        error_msg = result.get("message", result.get("error", "Payment failed"))
        return Response(
            {"success": False, "error": f"Payment initiation failed: {error_msg}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_remote_user_payments(request, user_id):
    """
    Get payment history for a remote user.

    Endpoint: GET /api/portal/vpn/users/<user_id>/payments/
    """
    tenant = request.tenant

    allowed, error = check_remote_access_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        remote_user = RemoteUser.objects.get(id=user_id, tenant=tenant)
    except RemoteUser.DoesNotExist:
        return Response(
            {"success": False, "error": "Remote user not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    payments = RemoteAccessPayment.objects.filter(remote_user=remote_user).order_by(
        "-created_at"
    )
    serializer = RemoteAccessPaymentSerializer(payments, many=True)

    return Response(
        {
            "success": True,
            "remote_user": remote_user.name,
            "total_payments": payments.count(),
            "payments": serializer.data,
        }
    )


# ---- Remote Access Logs ----


@api_view(["GET"])
@permission_classes([TenantAPIKeyPermission])
def portal_remote_access_logs(request):
    """
    Get remote access logs for the tenant. Supports filtering by user and event type.

    Endpoint: GET /api/portal/vpn/logs/
    """
    tenant = request.tenant

    allowed, error = check_remote_access_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    logs = RemoteAccessLog.objects.filter(tenant=tenant).select_related("remote_user")

    # Filters
    user_id = request.query_params.get("user_id")
    if user_id:
        logs = logs.filter(remote_user_id=user_id)

    event_type = request.query_params.get("event_type")
    if event_type:
        logs = logs.filter(event_type=event_type)

    limit = min(int(request.query_params.get("limit", 100)), 500)
    logs = logs[:limit]

    serializer = RemoteAccessLogSerializer(logs, many=True)
    return Response(
        {
            "success": True,
            "total": len(serializer.data),
            "logs": serializer.data,
        }
    )


# ---- Expiry Management ----


@api_view(["POST"])
@permission_classes([TenantAPIKeyPermission])
def portal_remote_user_extend(request, user_id):
    """
    Manually extend a remote user's access by a number of days.

    Endpoint: POST /api/portal/vpn/users/<user_id>/extend/
    Body: { "days": 30 }
    """
    tenant = request.tenant

    allowed, error = check_remote_access_permission(tenant)
    if not allowed:
        return Response(
            {"success": False, "error": error},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        remote_user = RemoteUser.objects.get(id=user_id, tenant=tenant)
    except RemoteUser.DoesNotExist:
        return Response(
            {"success": False, "error": "Remote user not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    days = int(request.data.get("days", 0))
    if days < 1 or days > 365:
        return Response(
            {"success": False, "error": "days must be between 1 and 365"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    now = timezone.now()
    if remote_user.expires_at and remote_user.expires_at > now:
        remote_user.expires_at = remote_user.expires_at + timedelta(days=days)
    else:
        remote_user.expires_at = now + timedelta(days=days)

    # Reactivate if expired
    if remote_user.status in ("expired", "disabled"):
        remote_user.status = "active"
        remote_user.is_active = True

        from .mikrotik import enable_wireguard_peer

        enable_wireguard_peer(remote_user)

    remote_user.save()

    RemoteAccessLog.objects.create(
        tenant=tenant,
        remote_user=remote_user,
        event_type="reactivated",
        event_details=f"Access extended by {days} days. New expiry: {remote_user.expires_at}",
    )

    serializer = RemoteUserSerializer(remote_user)
    return Response(
        {
            "success": True,
            "message": f"Access extended by {days} days",
            "user": serializer.data,
        }
    )
