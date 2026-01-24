"""
URL routing for billing API
"""

from django.urls import path
from . import views
from . import portal_views

urlpatterns = [
    # Authentication endpoints
    path("auth/login/", views.admin_login, name="admin_login"),
    path("auth/logout/", views.admin_logout, name="admin_logout"),
    path("auth/profile/", views.admin_profile, name="admin_profile"),
    path(
        "auth/change-password/",
        views.admin_change_password,
        name="admin_change_password",
    ),
    path("auth/create-admin/", views.create_admin_user, name="create_admin_user"),
    # Wi-Fi Access endpoints
    path("verify/", views.verify_access, name="verify_access"),
    path("bundles/", views.list_bundles, name="list_bundles"),
    path("initiate-payment/", views.initiate_payment, name="initiate_payment"),
    path("clickpesa-webhook/", views.clickpesa_webhook, name="clickpesa_webhook"),
    path(
        "clickpesa-payout-webhook/",
        views.clickpesa_payout_webhook,
        name="clickpesa_payout_webhook",
    ),
    path(
        "payment-status/<str:order_reference>/",
        views.query_payment_status,
        name="query_payment_status",
    ),
    path("user-status/<str:phone_number>/", views.user_status, name="user_status"),
    path(
        "devices/remove/", views.remove_device, name="remove_device"
    ),  # Must be before devices/<str:phone_number>/
    path(
        "devices/<str:phone_number>/", views.list_user_devices, name="list_user_devices"
    ),
    path(
        "trigger-auth/",
        views.trigger_device_authentication,
        name="trigger_device_authentication",
    ),
    # Voucher endpoints
    path("vouchers/generate/", views.generate_vouchers, name="generate_vouchers"),
    path("vouchers/redeem/", views.redeem_voucher, name="redeem_voucher"),
    path("vouchers/list/", views.list_vouchers, name="list_vouchers"),
    path(
        "vouchers/test-access/", views.test_voucher_access, name="test_voucher_access"
    ),
    # Admin endpoints
    path("webhook-logs/", views.webhook_logs, name="webhook_logs"),
    path("dashboard-stats/", views.dashboard_stats, name="dashboard_stats"),
    path("force-logout/", views.force_user_logout, name="force_user_logout"),
    # User Management endpoints (Admin only)
    path("admin/users/", views.list_users, name="list_users"),
    path("admin/users/<int:user_id>/", views.get_user_detail, name="get_user_detail"),
    path("admin/users/<int:user_id>/update/", views.update_user, name="update_user"),
    path("admin/users/<int:user_id>/delete/", views.delete_user, name="delete_user"),
    path(
        "admin/users/<int:user_id>/disconnect/",
        views.disconnect_user,
        name="disconnect_user",
    ),
    # Alternative shorter endpoints for frontend compatibility
    path("users/", views.list_users, name="list_users_short"),
    path("users/<int:user_id>/", views.get_user_detail, name="get_user_detail_short"),
    # Payment Management endpoints (Admin only)
    path("admin/payments/", views.list_payments, name="list_payments"),
    path(
        "admin/payments/<int:payment_id>/",
        views.get_payment_detail,
        name="get_payment_detail",
    ),
    path(
        "admin/payments/<int:payment_id>/refund/",
        views.refund_payment,
        name="refund_payment",
    ),
    path("payments/", views.list_payments, name="list_payments_short"),
    path(
        "payments/<int:payment_id>/",
        views.get_payment_detail,
        name="get_payment_detail_short",
    ),
    # Bundle/Package Management endpoints (Admin only)
    path("admin/bundles/", views.manage_bundles, name="manage_bundles"),
    path("admin/bundles/<int:bundle_id>/", views.manage_bundle, name="manage_bundle"),
    # System Settings and Status endpoints (Admin only)
    path("admin/settings/", views.system_settings, name="system_settings"),
    path("admin/status/", views.system_status, name="system_status"),
    path(
        "admin/cleanup-expired/",
        views.cleanup_expired_users,
        name="cleanup_expired_users",
    ),
    path(
        "admin/expiry-watcher/",
        views.expiry_watcher_status,
        name="expiry_watcher_status",
    ),
    # Mikrotik Integration endpoints
    path("mikrotik/auth/", views.mikrotik_auth, name="mikrotik_auth"),
    path("mikrotik/logout/", views.mikrotik_logout, name="mikrotik_logout"),
    path("mikrotik/status/", views.mikrotik_status_check, name="mikrotik_status_check"),
    path(
        "mikrotik/user-status/", views.mikrotik_user_status, name="mikrotik_user_status"
    ),
    # MikroTik Configuration and Management endpoints (Admin only)
    # NEW: Multi-tenant router management for platform admin
    path(
        "admin/routers/",
        views.admin_list_all_routers,
        name="admin_list_all_routers",
    ),
    path(
        "admin/routers/<int:router_id>/",
        views.admin_router_detail,
        name="admin_router_detail",
    ),
    path(
        "admin/routers/<int:router_id>/active-users/",
        views.admin_router_active_users,
        name="admin_router_active_users",
    ),
    path(
        "admin/routers/<int:router_id>/disconnect-user/",
        views.admin_router_disconnect_user,
        name="admin_router_disconnect_user",
    ),
    path(
        "admin/routers/<int:router_id>/test-connection/",
        views.admin_router_test_connection,
        name="admin_router_test_connection",
    ),
    # Legacy MikroTik endpoints (use default router from settings)
    path(
        "admin/mikrotik/config/",
        views.mikrotik_configuration,
        name="mikrotik_configuration",
    ),
    path(
        "admin/mikrotik/test-connection/",
        views.test_mikrotik_connection,
        name="test_mikrotik_connection",
    ),
    path(
        "admin/mikrotik/router-info/",
        views.mikrotik_router_info,
        name="mikrotik_router_info",
    ),
    path(
        "admin/mikrotik/active-users/",
        views.mikrotik_active_users,
        name="mikrotik_active_users",
    ),
    path(
        "admin/mikrotik/disconnect-user/",
        views.mikrotik_disconnect_user,
        name="mikrotik_disconnect_user",
    ),
    path(
        "admin/mikrotik/disconnect-all/",
        views.mikrotik_disconnect_all_users,
        name="mikrotik_disconnect_all_users",
    ),
    path(
        "admin/mikrotik/reboot/",
        views.mikrotik_reboot_router,
        name="mikrotik_reboot_router",
    ),
    path(
        "admin/mikrotik/profiles/",
        views.mikrotik_hotspot_profiles,
        name="mikrotik_hotspot_profiles",
    ),
    path(
        "admin/mikrotik/profiles/create/",
        views.mikrotik_create_hotspot_profile,
        name="mikrotik_create_hotspot_profile",
    ),
    path(
        "admin/mikrotik/resources/",
        views.mikrotik_system_resources,
        name="mikrotik_system_resources",
    ),
    # =========================================================================
    # SAAS SUBSCRIPTION ENDPOINTS
    # =========================================================================
    # Public endpoints (pricing page, registration)
    path("saas/plans/", views.list_subscription_plans, name="list_subscription_plans"),
    path("saas/register/", views.register_tenant, name="register_tenant"),
    # Email verification and authentication
    path("saas/verify-email/", views.verify_email_otp, name="verify_email_otp"),
    path("saas/resend-otp/", views.resend_otp, name="resend_otp"),
    path("saas/login/", views.tenant_login, name="tenant_login"),
    path("saas/logout/", views.tenant_logout, name="tenant_logout"),
    path(
        "saas/password-reset/",
        views.tenant_password_reset_request,
        name="tenant_password_reset_request",
    ),
    path(
        "saas/password-reset/confirm/",
        views.tenant_password_reset_confirm,
        name="tenant_password_reset_confirm",
    ),
    # Tenant endpoints (requires API key)
    path("saas/dashboard/", views.tenant_dashboard, name="tenant_dashboard"),
    path("saas/usage/", views.tenant_usage, name="tenant_usage"),
    path(
        "saas/subscribe/",
        views.create_subscription_payment,
        name="create_subscription_payment",
    ),
    path(
        "saas/subscription-history/",
        views.tenant_subscription_history,
        name="tenant_subscription_history",
    ),
    path("saas/revenue/", views.tenant_revenue_report, name="tenant_revenue_report"),
    # Subscription webhook (ClickPesa callback)
    path(
        "saas/webhook/",
        views.subscription_payment_webhook,
        name="subscription_payment_webhook",
    ),
    path(
        "saas/payment-status/<str:transaction_id>/",
        views.subscription_payment_status,
        name="subscription_payment_status",
    ),
    # Tenant router management
    path("saas/routers/", views.tenant_routers, name="tenant_routers"),
    path(
        "saas/routers/<int:router_id>/",
        views.tenant_router_detail,
        name="tenant_router_detail",
    ),
    path(
        "saas/routers/<int:router_id>/test/",
        views.test_router_connection,
        name="test_router_connection",
    ),
    # Platform admin endpoints (super admin only)
    path("platform/dashboard/", views.platform_dashboard, name="platform_dashboard"),
    path("platform/tenants/", views.list_all_tenants, name="list_all_tenants"),
    path(
        "platform/tenants/<uuid:tenant_id>/", views.manage_tenant, name="manage_tenant"
    ),
    path(
        "platform/revenue/",
        views.platform_revenue_report,
        name="platform_revenue_report",
    ),
    # System endpoints
    path("health/", views.health_check, name="health_check"),
    path("contact/", views.contact_submit, name="contact_submit"),
    # =========================================================================
    # TENANT PORTAL ENDPOINTS (Phase 3)
    # =========================================================================
    # Portal Dashboard
    path("portal/dashboard/", portal_views.portal_dashboard, name="portal_dashboard"),
    path(
        "portal/realtime/",
        portal_views.portal_realtime_stats,
        name="portal_realtime_stats",
    ),
    path(
        "portal/comparison/", portal_views.portal_comparison, name="portal_comparison"
    ),
    # Analytics & Reporting
    path(
        "portal/analytics/revenue/",
        portal_views.portal_revenue_analytics,
        name="portal_revenue_analytics",
    ),
    path(
        "portal/analytics/users/",
        portal_views.portal_user_analytics,
        name="portal_user_analytics",
    ),
    path(
        "portal/analytics/vouchers/",
        portal_views.portal_voucher_analytics,
        name="portal_voucher_analytics",
    ),
    path("portal/export/", portal_views.portal_export_data, name="portal_export_data"),
    # Router Configuration Wizard
    path(
        "portal/router/test/",
        portal_views.portal_router_test_connection,
        name="portal_router_test_connection",
    ),
    path(
        "portal/router/save/",
        portal_views.portal_router_save_config,
        name="portal_router_save_config",
    ),
    path(
        "portal/router/auto-configure/",
        portal_views.portal_router_auto_configure,
        name="portal_router_auto_configure",
    ),
    path(
        "portal/router/<int:router_id>/html/",
        portal_views.portal_router_generate_html,
        name="portal_router_generate_html",
    ),
    path(
        "portal/router/health/",
        portal_views.portal_router_health,
        name="portal_router_health",
    ),
    # ==========================================================================
    # ROUTER MONITORING & BANDWIDTH REPORTS (Business/Enterprise)
    # ==========================================================================
    path(
        "portal/router/<int:router_id>/monitoring/",
        portal_views.portal_router_monitoring,
        name="portal_router_monitoring",
    ),
    path(
        "portal/router/<int:router_id>/collect-metrics/",
        portal_views.portal_router_collect_metrics,
        name="portal_router_collect_metrics",
    ),
    path(
        "portal/router/<int:router_id>/monitoring/history/",
        portal_views.portal_router_monitoring_history,
        name="portal_router_monitoring_history",
    ),
    path(
        "portal/router/monitoring/all/",
        portal_views.portal_router_monitoring_all,
        name="portal_router_monitoring_all",
    ),
    path(
        "portal/router/<int:router_id>/bandwidth/",
        portal_views.portal_router_bandwidth,
        name="portal_router_bandwidth",
    ),
    path(
        "portal/bandwidth/summary/",
        portal_views.portal_bandwidth_summary,
        name="portal_bandwidth_summary",
    ),
    # ==========================================================================
    # HOTSPOT PAGE CUSTOMIZATION (Per Router)
    # ==========================================================================
    path(
        "portal/router/<int:router_id>/hotspot/",
        portal_views.portal_router_hotspot_customization,
        name="portal_router_hotspot_customization",
    ),
    path(
        "portal/router/<int:router_id>/hotspot/preview/",
        portal_views.portal_router_hotspot_preview,
        name="portal_router_hotspot_preview",
    ),
    path(
        "portal/router/<int:router_id>/hotspot/deploy/",
        portal_views.portal_router_deploy_hotspot,
        name="portal_router_deploy_hotspot",
    ),
    # White-Label Customization
    path("portal/branding/", portal_views.portal_branding, name="portal_branding"),
    path(
        "portal/branding/update/",
        portal_views.portal_branding_update,
        name="portal_branding_update",
    ),
    path(
        "portal/branding/logo/",
        portal_views.portal_logo_upload,
        name="portal_logo_upload",
    ),
    path(
        "portal/branding/logo/remove/",
        portal_views.portal_logo_remove,
        name="portal_logo_remove",
    ),
    path(
        "portal/branding/domain/",
        portal_views.portal_custom_domain,
        name="portal_custom_domain",
    ),
    path(
        "portal/branding/theme/", portal_views.portal_theme_css, name="portal_theme_css"
    ),
    path(
        "portal/branding/captive-portal/",
        portal_views.portal_captive_portal_pages,
        name="portal_captive_portal_pages",
    ),
    # Tenant Settings
    path("portal/settings/", portal_views.portal_settings, name="portal_settings"),
    path("portal/api-keys/", portal_views.portal_api_keys, name="portal_api_keys"),
    path(
        "portal/api-keys/regenerate/",
        portal_views.portal_regenerate_api_key,
        name="portal_regenerate_api_key",
    ),
    # Staff Management
    path("portal/staff/", portal_views.portal_staff, name="portal_staff"),
    path(
        "portal/staff/<int:staff_id>/",
        portal_views.portal_staff_detail,
        name="portal_staff_detail",
    ),
    # Location Management
    path("portal/locations/", portal_views.portal_locations, name="portal_locations"),
    path(
        "portal/locations/<int:location_id>/",
        portal_views.portal_location_detail,
        name="portal_location_detail",
    ),
    # Bundle Management
    path("portal/bundles/", portal_views.portal_bundles, name="portal_bundles"),
    path(
        "portal/bundles/<int:bundle_id>/",
        portal_views.portal_bundle_detail,
        name="portal_bundle_detail",
    ),
    # Voucher Management
    path(
        "portal/vouchers/",
        portal_views.portal_list_vouchers,
        name="portal_list_vouchers",
    ),
    path(
        "portal/vouchers/generate/",
        portal_views.portal_generate_vouchers,
        name="portal_generate_vouchers",
    ),
    path(
        "portal/vouchers/delete/",
        portal_views.portal_delete_voucher_batch,
        name="portal_delete_voucher_batch",
    ),
    path(
        "portal/vouchers/<int:voucher_id>/",
        portal_views.portal_delete_voucher,
        name="portal_delete_voucher",
    ),
    # User Management
    path("portal/users/", portal_views.portal_users, name="portal_users"),
    path(
        "portal/users/<int:user_id>/",
        portal_views.portal_user_detail,
        name="portal_user_detail",
    ),
    path(
        "portal/users/<int:user_id>/disconnect/",
        portal_views.portal_user_disconnect,
        name="portal_user_disconnect",
    ),
    path(
        "portal/users/<int:user_id>/release-device/",
        portal_views.portal_user_release_device,
        name="portal_user_release_device",
    ),
    path(
        "portal/users/<int:user_id>/device-status/",
        portal_views.portal_user_device_status,
        name="portal_user_device_status",
    ),
    path(
        "portal/users/<int:user_id>/extend/",
        portal_views.portal_user_extend_access,
        name="portal_user_extend_access",
    ),
    # Payment Management
    path("portal/payments/", portal_views.portal_payments, name="portal_payments"),
    path("portal/balance/", portal_views.portal_balance, name="portal_balance"),
    path("portal/payouts/", portal_views.portal_payouts, name="portal_payouts"),
    path(
        "portal/payouts/<int:payout_id>/",
        portal_views.portal_payout_detail,
        name="portal_payout_detail",
    ),
    path(
        "portal/payouts/<int:payout_id>/refresh/",
        portal_views.portal_payout_refresh_status,
        name="portal_payout_refresh_status",
    ),
    path(
        "portal/financial-summary/",
        portal_views.portal_financial_summary,
        name="portal_financial_summary",
    ),
    path(
        "portal/clickpesa-balance/",
        portal_views.portal_clickpesa_balance,
        name="portal_clickpesa_balance",
    ),
    # SMS Configuration and Broadcast (Business/Enterprise only)
    path(
        "portal/sms/config/",
        portal_views.portal_sms_config,
        name="portal_sms_config",
    ),
    path(
        "portal/sms/test-credentials/",
        portal_views.portal_sms_test_credentials,
        name="portal_sms_test_credentials",
    ),
    path(
        "portal/sms/balance/",
        portal_views.portal_sms_balance,
        name="portal_sms_balance",
    ),
    path(
        "portal/sms/broadcasts/",
        portal_views.portal_sms_broadcasts,
        name="portal_sms_broadcasts",
    ),
    path(
        "portal/sms/broadcasts/preview/",
        portal_views.portal_sms_broadcast_preview,
        name="portal_sms_broadcast_preview",
    ),
    path(
        "portal/sms/broadcasts/<uuid:broadcast_id>/",
        portal_views.portal_sms_broadcast_detail,
        name="portal_sms_broadcast_detail",
    ),
    path(
        "portal/sms/broadcasts/<uuid:broadcast_id>/send/",
        portal_views.portal_sms_broadcast_send,
        name="portal_sms_broadcast_send",
    ),
    path(
        "portal/sms/send-single/",
        portal_views.portal_sms_send_single,
        name="portal_sms_send_single",
    ),
    path(
        "portal/sms/logs/",
        portal_views.portal_sms_logs,
        name="portal_sms_logs",
    ),
    # ==========================================================================
    # SMS BROADCAST ENDPOINTS (Admin only)
    # ==========================================================================
    path("sms-broadcasts/", views.list_sms_broadcasts, name="list_sms_broadcasts"),
    path(
        "sms-broadcasts/create/",
        views.create_sms_broadcast,
        name="create_sms_broadcast",
    ),
    path(
        "sms-broadcasts/preview/",
        views.preview_sms_broadcast,
        name="preview_sms_broadcast",
    ),
    path("sms-broadcasts/send-single/", views.send_single_sms, name="send_single_sms"),
    path(
        "sms-broadcasts/<str:broadcast_id>/",
        views.get_sms_broadcast,
        name="get_sms_broadcast",
    ),
    path(
        "sms-broadcasts/<str:broadcast_id>/send/",
        views.send_sms_broadcast,
        name="send_sms_broadcast",
    ),
    path(
        "sms-broadcasts/<str:broadcast_id>/delete/",
        views.delete_sms_broadcast,
        name="delete_sms_broadcast",
    ),
    # ==========================================================================
    # PREMIUM FEATURES (Business/Enterprise only)
    # ==========================================================================
    # Webhook Notifications
    path(
        "portal/webhooks/",
        portal_views.portal_webhooks,
        name="portal_webhooks",
    ),
    path(
        "portal/webhooks/<uuid:webhook_id>/",
        portal_views.portal_webhook_detail,
        name="portal_webhook_detail",
    ),
    path(
        "portal/webhooks/<uuid:webhook_id>/test/",
        portal_views.portal_webhook_test,
        name="portal_webhook_test",
    ),
    path(
        "portal/webhooks/<uuid:webhook_id>/deliveries/",
        portal_views.portal_webhook_deliveries,
        name="portal_webhook_deliveries",
    ),
    # Auto SMS Campaigns
    path(
        "portal/auto-sms/campaigns/",
        portal_views.portal_auto_sms_campaigns,
        name="portal_auto_sms_campaigns",
    ),
    path(
        "portal/auto-sms/campaigns/<uuid:campaign_id>/",
        portal_views.portal_auto_sms_campaign_detail,
        name="portal_auto_sms_campaign_detail",
    ),
    path(
        "portal/auto-sms/campaigns/<uuid:campaign_id>/toggle/",
        portal_views.portal_auto_sms_campaign_toggle,
        name="portal_auto_sms_campaign_toggle",
    ),
    path(
        "portal/auto-sms/campaigns/<uuid:campaign_id>/preview/",
        portal_views.portal_auto_sms_campaign_preview,
        name="portal_auto_sms_campaign_preview",
    ),
    path(
        "portal/auto-sms/campaigns/<uuid:campaign_id>/logs/",
        portal_views.portal_auto_sms_campaign_logs,
        name="portal_auto_sms_logs",
    ),
    # Advanced Analytics
    path(
        "portal/analytics/advanced/",
        portal_views.portal_advanced_analytics,
        name="portal_advanced_analytics",
    ),
    path(
        "portal/analytics/trends/",
        portal_views.portal_analytics_trends,
        name="portal_analytics_trends",
    ),
    path(
        "portal/analytics/export/",
        portal_views.portal_analytics_export,
        name="portal_analytics_export",
    ),
    path(
        "portal/analytics/revenue-breakdown/",
        portal_views.portal_analytics_revenue_breakdown,
        name="portal_analytics_revenue_breakdown",
    ),
    path(
        "portal/analytics/user-segments/",
        portal_views.portal_analytics_user_segments,
        name="portal_analytics_user_segments",
    ),
    path(
        "portal/analytics/router-performance/",
        portal_views.portal_analytics_router_performance,
        name="portal_analytics_router_performance",
    ),
    
    # ==========================================================================
    # TENANT ROUTER VPN MANAGEMENT (Self-Service)
    # ==========================================================================
    path(
        "tenant/vpn-status/",
        views.get_vpn_ip_status,
        name="tenant_vpn_status",
    ),
    path(
        "tenant/routers/",
        views.list_tenant_routers,
        name="tenant_routers_list",
    ),
    path(
        "tenant/routers/create/",
        views.create_router_with_vpn,
        name="tenant_router_create",
    ),
    path(
        "tenant/routers/<int:router_id>/vpn-config/",
        views.get_router_vpn_config,
        name="tenant_router_vpn_config",
    ),
    path(
        "tenant/routers/<int:router_id>/test-vpn/",
        views.test_router_vpn_connection,
        name="tenant_router_test_vpn",
    ),
    path(
        "tenant/routers/<int:router_id>/regenerate-vpn/",
        views.regenerate_router_vpn,
        name="tenant_router_regenerate_vpn",
    ),
    path(
        "tenant/routers/<int:router_id>/",
        views.delete_router,
        name="tenant_router_delete",
    ),
]
