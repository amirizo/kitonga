"""
URL routing for billing API
"""
from django.urls import path
from . import views
from . import portal_views

urlpatterns = [
    # Authentication endpoints
    path('auth/login/', views.admin_login, name='admin_login'),
    path('auth/logout/', views.admin_logout, name='admin_logout'),
    path('auth/profile/', views.admin_profile, name='admin_profile'),
    path('auth/change-password/', views.admin_change_password, name='admin_change_password'),
    path('auth/create-admin/', views.create_admin_user, name='create_admin_user'),
    
    # Wi-Fi Access endpoints
    path('verify/', views.verify_access, name='verify_access'),
    path('bundles/', views.list_bundles, name='list_bundles'),
    path('initiate-payment/', views.initiate_payment, name='initiate_payment'),
    path('clickpesa-webhook/', views.clickpesa_webhook, name='clickpesa_webhook'),
    path('payment-status/<str:order_reference>/', views.query_payment_status, name='query_payment_status'),
    path('user-status/<str:phone_number>/', views.user_status, name='user_status'),
    path('devices/remove/', views.remove_device, name='remove_device'),  # Must be before devices/<str:phone_number>/
    path('devices/<str:phone_number>/', views.list_user_devices, name='list_user_devices'),
    path('trigger-auth/', views.trigger_device_authentication, name='trigger_device_authentication'),
    
    # Voucher endpoints
    path('vouchers/generate/', views.generate_vouchers, name='generate_vouchers'),
    path('vouchers/redeem/', views.redeem_voucher, name='redeem_voucher'),
    path('vouchers/list/', views.list_vouchers, name='list_vouchers'),
    path('vouchers/test-access/', views.test_voucher_access, name='test_voucher_access'),
    
    # Admin endpoints
    path('webhook-logs/', views.webhook_logs, name='webhook_logs'),
    path('dashboard-stats/', views.dashboard_stats, name='dashboard_stats'),
    path('force-logout/', views.force_user_logout, name='force_user_logout'),
    
    # User Management endpoints (Admin only)
    path('admin/users/', views.list_users, name='list_users'),
    path('admin/users/<int:user_id>/', views.get_user_detail, name='get_user_detail'),
    path('admin/users/<int:user_id>/update/', views.update_user, name='update_user'),
    path('admin/users/<int:user_id>/delete/', views.delete_user, name='delete_user'),
    path('admin/users/<int:user_id>/disconnect/', views.disconnect_user, name='disconnect_user'),
    
    # Alternative shorter endpoints for frontend compatibility
    path('users/', views.list_users, name='list_users_short'),
    path('users/<int:user_id>/', views.get_user_detail, name='get_user_detail_short'),
    
    # Payment Management endpoints (Admin only)
    path('admin/payments/', views.list_payments, name='list_payments'),
    path('admin/payments/<int:payment_id>/', views.get_payment_detail, name='get_payment_detail'),
    path('admin/payments/<int:payment_id>/refund/', views.refund_payment, name='refund_payment'),
    path('payments/', views.list_payments, name='list_payments_short'),
    path('payments/<int:payment_id>/', views.get_payment_detail, name='get_payment_detail_short'),
    
    # Bundle/Package Management endpoints (Admin only)
    path('admin/bundles/', views.manage_bundles, name='manage_bundles'),
    path('admin/bundles/<int:bundle_id>/', views.manage_bundle, name='manage_bundle'),
    
    # System Settings and Status endpoints (Admin only)
    path('admin/settings/', views.system_settings, name='system_settings'),
    path('admin/status/', views.system_status, name='system_status'),
    path('admin/cleanup-expired/', views.cleanup_expired_users, name='cleanup_expired_users'),
    path('admin/expiry-watcher/', views.expiry_watcher_status, name='expiry_watcher_status'),
    
    # Mikrotik Integration endpoints
    path('mikrotik/auth/', views.mikrotik_auth, name='mikrotik_auth'),
    path('mikrotik/logout/', views.mikrotik_logout, name='mikrotik_logout'),
    path('mikrotik/status/', views.mikrotik_status_check, name='mikrotik_status_check'),
    path('mikrotik/user-status/', views.mikrotik_user_status, name='mikrotik_user_status'),
    
    # MikroTik Configuration and Management endpoints (Admin only)
    path('admin/mikrotik/config/', views.mikrotik_configuration, name='mikrotik_configuration'),
    path('admin/mikrotik/test-connection/', views.test_mikrotik_connection, name='test_mikrotik_connection'),
    path('admin/mikrotik/router-info/', views.mikrotik_router_info, name='mikrotik_router_info'),
    path('admin/mikrotik/active-users/', views.mikrotik_active_users, name='mikrotik_active_users'),
    path('admin/mikrotik/disconnect-user/', views.mikrotik_disconnect_user, name='mikrotik_disconnect_user'),
    path('admin/mikrotik/disconnect-all/', views.mikrotik_disconnect_all_users, name='mikrotik_disconnect_all_users'),
    path('admin/mikrotik/reboot/', views.mikrotik_reboot_router, name='mikrotik_reboot_router'),
    path('admin/mikrotik/profiles/', views.mikrotik_hotspot_profiles, name='mikrotik_hotspot_profiles'),
    path('admin/mikrotik/profiles/create/', views.mikrotik_create_hotspot_profile, name='mikrotik_create_hotspot_profile'),
    path('admin/mikrotik/resources/', views.mikrotik_system_resources, name='mikrotik_system_resources'),
    
    # =========================================================================
    # SAAS SUBSCRIPTION ENDPOINTS
    # =========================================================================
    
    # Public endpoints (pricing page, registration)
    path('saas/plans/', views.list_subscription_plans, name='list_subscription_plans'),
    path('saas/register/', views.register_tenant, name='register_tenant'),
    
    # Tenant endpoints (requires API key)
    path('saas/dashboard/', views.tenant_dashboard, name='tenant_dashboard'),
    path('saas/usage/', views.tenant_usage, name='tenant_usage'),
    path('saas/subscribe/', views.create_subscription_payment, name='create_subscription_payment'),
    path('saas/subscription-history/', views.tenant_subscription_history, name='tenant_subscription_history'),
    path('saas/revenue/', views.tenant_revenue_report, name='tenant_revenue_report'),
    
    # Subscription webhook (ClickPesa callback)
    path('saas/webhook/', views.subscription_payment_webhook, name='subscription_payment_webhook'),
    
    # Tenant router management
    path('saas/routers/', views.tenant_routers, name='tenant_routers'),
    path('saas/routers/<int:router_id>/', views.tenant_router_detail, name='tenant_router_detail'),
    path('saas/routers/<int:router_id>/test/', views.test_router_connection, name='test_router_connection'),
    
    # Platform admin endpoints (super admin only)
    path('platform/dashboard/', views.platform_dashboard, name='platform_dashboard'),
    path('platform/tenants/', views.list_all_tenants, name='list_all_tenants'),
    path('platform/tenants/<uuid:tenant_id>/', views.manage_tenant, name='manage_tenant'),
    path('platform/revenue/', views.platform_revenue_report, name='platform_revenue_report'),
    
    # System endpoints
    path('health/', views.health_check, name='health_check'),
]
