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
    
    # System endpoints
    path('health/', views.health_check, name='health_check'),
]
