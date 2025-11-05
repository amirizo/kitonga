"""
URL routing for billing API
"""
from django.urls import path
from . import views

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
    path('devices/<str:phone_number>/', views.list_user_devices, name='list_user_devices'),
    path('devices/remove/', views.remove_device, name='remove_device'),
    
    # Voucher endpoints
    path('vouchers/generate/', views.generate_vouchers, name='generate_vouchers'),
    path('vouchers/redeem/', views.redeem_voucher, name='redeem_voucher'),
    path('vouchers/list/', views.list_vouchers, name='list_vouchers'),
    
    # Admin endpoints
    path('webhook-logs/', views.webhook_logs, name='webhook_logs'),
    path('dashboard-stats/', views.dashboard_stats, name='dashboard_stats'),
    path('force-logout/', views.force_user_logout, name='force_user_logout'),
    path('debug-user-access/', views.debug_user_access, name='debug_user_access'),
    
    # User Management endpoints (Admin only)
    path('admin/users/', views.list_users, name='list_users'),
    path('admin/users/<int:user_id>/', views.get_user_detail, name='get_user_detail'),
    path('admin/users/<int:user_id>/update/', views.update_user, name='update_user'),
    path('admin/users/<int:user_id>/delete/', views.delete_user, name='delete_user'),
    
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
    
    # Mikrotik Integration endpoints
    path('mikrotik/auth/', views.mikrotik_auth, name='mikrotik_auth'),
    path('mikrotik/logout/', views.mikrotik_logout, name='mikrotik_logout'),
    path('mikrotik/status/', views.mikrotik_status_check, name='mikrotik_status_check'),
    path('mikrotik/user-status/', views.mikrotik_user_status, name='mikrotik_user_status'),
    path('mikrotik/debug-user/', views.debug_user_access, name='debug_user_access'),
    
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
    
    # System endpoints
    path('health/', views.health_check, name='health_check'),
]
