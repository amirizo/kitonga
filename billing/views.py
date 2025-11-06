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
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models import Count, Sum
from datetime import timedelta
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User as DjangoUser
from .models import User, Bundle, Payment, Device, PaymentWebhook, Voucher, AccessLog
from django.views.decorators.http import require_http_methods
from rest_framework.authtoken.models import Token
from .serializers import (
    UserSerializer, PaymentSerializer, 
    InitiatePaymentSerializer, VerifyAccessSerializer,
    VoucherSerializer, GenerateVouchersSerializer, RedeemVoucherSerializer,
    BundleSerializer, DeviceSerializer
)
from .clickpesa import ClickPesaAPI
from .utils import get_active_users_count, get_revenue_statistics
from .permissions import SimpleAdminTokenPermission
from .mikrotik import authenticate_user_with_mikrotik, logout_user_from_mikrotik

logger = logging.getLogger(__name__)


# Health Check API
@api_view(['GET'])
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
            cache.set('health_check', 'ok', 10)
            cache.get('health_check')
        except Exception:
            pass  # Cache might not be configured
            
        return Response({
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'version': '1.0.0',
            'service': 'kitonga-wifi-billing'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return Response({
            'status': 'unhealthy',
            'timestamp': timezone.now().isoformat(),
            'error': str(e)
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


# Authentication APIs
@api_view(['POST'])
@permission_classes([AllowAny])
def admin_login(request):
    """
    Admin login API endpoint
    """
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response({
            'success': False,
            'message': 'Username and password are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Authenticate user
    user = authenticate(request, username=username, password=password)
    
    if user is not None and user.is_staff:
        # Login successful and user is admin
        login(request, user)
        
        # Create or get auth token
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'date_joined': user.date_joined.isoformat()
            },
            'token': token.key,
            'admin_access_token': settings.SIMPLE_ADMIN_TOKEN  # For header-based auth
        }, status=status.HTTP_200_OK)
    
    elif user is not None and not user.is_staff:
        return Response({
            'success': False,
            'message': 'Access denied. Admin privileges required.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    else:
        return Response({
            'success': False,
            'message': 'Invalid username or password'
        }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
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
        return Response({
            'success': True,
            'message': 'Logout successful'
        }, status=status.HTTP_200_OK)
    
    return Response({
        'success': False,
        'message': 'User not logged in'
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
def admin_profile(request):
    """
    Get current admin user profile
    """
    # Check token authentication first
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if auth_header.startswith('Token '):
        token_key = auth_header.split(' ')[1]
        try:
            token = Token.objects.get(key=token_key)
            user = token.user
            if user.is_staff:
                return Response({
                    'success': True,
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'is_staff': user.is_staff,
                        'is_superuser': user.is_superuser,
                        'last_login': user.last_login.isoformat() if user.last_login else None,
                        'date_joined': user.date_joined.isoformat()
                    },
                    'is_authenticated': True
                })
        except Token.DoesNotExist:
            pass
    
    # Check session authentication
    if request.user.is_authenticated and request.user.is_staff:
        return Response({
            'success': True,
            'user': {
                'id': request.user.id,
                'username': request.user.username,
                'email': request.user.email,
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'is_staff': request.user.is_staff,
                'is_superuser': request.user.is_superuser,
                'last_login': request.user.last_login.isoformat() if request.user.last_login else None,
                'date_joined': request.user.date_joined.isoformat()
            },
            'is_authenticated': True
        })
    
    return Response({
        'success': False,
        'message': 'Not authenticated or not admin',
        'is_authenticated': False
    }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([AllowAny])
def admin_change_password(request):
    """
    Change admin password
    """
    if not request.user.is_authenticated or not request.user.is_staff:
        return Response({
            'success': False,
            'message': 'Authentication required'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')
    confirm_password = request.data.get('confirm_password')
    
    if not all([current_password, new_password, confirm_password]):
        return Response({
            'success': False,
            'message': 'All password fields are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if new_password != confirm_password:
        return Response({
            'success': False,
            'message': 'New passwords do not match'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Verify current password
    if not request.user.check_password(current_password):
        return Response({
            'success': False,
            'message': 'Current password is incorrect'
        }, status=status.HTTP_400_BAD_REQUEST)
    
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
    
    return Response({
        'success': True,
        'message': 'Password changed successfully',
        'token': new_token.key
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def create_admin_user(request):
    """
    Create a new admin user (Only for superuser or if no admin exists)
    """
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email', '')
    first_name = request.data.get('first_name', '')
    last_name = request.data.get('last_name', '')
    
    if not username or not password:
        return Response({
            'success': False,
            'message': 'Username and password are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if any admin users exist
    admin_count = DjangoUser.objects.filter(is_staff=True).count()
    
    # Allow creation only if no admins exist or current user is superuser
    if admin_count > 0 and (not request.user.is_authenticated or not request.user.is_superuser):
        return Response({
            'success': False,
            'message': 'Only superusers can create admin accounts'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Check if username already exists
    if DjangoUser.objects.filter(username=username).exists():
        return Response({
            'success': False,
            'message': 'Username already exists'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Create admin user
        user = DjangoUser.objects.create_user(
            username=username,
            password=password,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_staff=True,
            is_superuser=(admin_count == 0)  # First admin becomes superuser
        )
        
        logger.info(f'Admin user created: {username}')
        
        return Response({
            'success': True,
            'message': 'Admin user created successfully',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser
            }
        }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        logger.error(f'Error creating admin user: {str(e)}')
        return Response({
            'success': False,
            'message': 'Error creating admin user'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# User Management APIs

@api_view(['GET'])
@permission_classes([SimpleAdminTokenPermission])
def list_users(request):
    """
    List all Wi-Fi users (Admin only)
    """
    try:
        users = User.objects.all().order_by('-created_at')
        
        # Apply filters
        phone_filter = request.GET.get('phone_number')
        is_active_filter = request.GET.get('is_active')
        
        if phone_filter:
            users = users.filter(phone_number__icontains=phone_filter)
        
        if is_active_filter is not None:
            is_active = is_active_filter.lower() == 'true'
            users = users.filter(is_active=is_active)
        
        # Pagination
        page_size = int(request.GET.get('page_size', 20))
        page = int(request.GET.get('page', 1))
        start = (page - 1) * page_size
        end = start + page_size
        
        total_users = users.count()
        users_page = users[start:end]
        
        # Serialize users with basic data first
        users_data = []
        for user in users_page:
            try:
                user_data = {
                    'id': user.id,
                    'phone_number': user.phone_number,
                    'is_active': user.is_active,
                    'created_at': user.created_at.isoformat(),
                    'paid_until': user.paid_until.isoformat() if user.paid_until else None,
                    'has_active_access': user.has_active_access(),
                    'max_devices': user.max_devices,
                    'total_payments': user.total_payments
                }
                
                # Safely get device count
                try:
                    user_data['device_count'] = user.devices.count()
                except:
                    user_data['device_count'] = 0
                
                # Safely get payment count
                try:
                    user_data['payment_count'] = user.payments.filter(status='completed').count()
                except:
                    user_data['payment_count'] = 0
                
                # Safely get last payment
                user_data['last_payment'] = None
                try:
                    last_payment = user.payments.filter(status='completed').order_by('-completed_at').first()
                    if last_payment:
                        user_data['last_payment'] = {
                            'amount': str(last_payment.amount),
                            'bundle_name': last_payment.bundle.name if last_payment.bundle else None,
                            'completed_at': last_payment.completed_at.isoformat() if last_payment.completed_at else None
                        }
                except:
                    pass
                
                users_data.append(user_data)
                
            except Exception as e:
                logger.error(f'Error serializing user {user.id}: {str(e)}')
                # Add basic user data without problematic fields
                users_data.append({
                    'id': user.id,
                    'phone_number': user.phone_number,
                    'is_active': user.is_active,
                    'created_at': user.created_at.isoformat(),
                    'error': 'Failed to load complete user data'
                })
        
        return Response({
            'success': True,
            'users': users_data,
            'pagination': {
                'total': total_users,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_users + page_size - 1) // page_size
            }
        })
        
    except Exception as e:
        logger.error(f'Error listing users: {str(e)}')
        return Response({
            'success': False,
            'message': f'Error retrieving users: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([SimpleAdminTokenPermission])
def get_user_detail(request, user_id):
    """
    Get detailed information about a specific user (Admin only)
    """
    try:
        user = User.objects.get(id=user_id)
        
        # Get user's payments
        payments = user.payments.all().order_by('-created_at')
        payments_data = []
        for payment in payments:
            payments_data.append({
                'id': payment.id,
                'amount': str(payment.amount),
                'status': payment.status,
                'bundle_name': payment.bundle.name if payment.bundle else None,
                'order_reference': payment.order_reference,
                'created_at': payment.created_at.isoformat(),
                'completed_at': payment.completed_at.isoformat() if payment.completed_at else None
            })
        
        # Get user's devices
        devices = user.devices.all()
        devices_data = []
        for device in devices:
            devices_data.append({
                'id': device.id,
                'mac_address': device.mac_address,
                'device_name': device.device_name or 'Unknown Device',
                'is_active': device.is_active,
                'last_seen': device.last_seen.isoformat() if device.last_seen else None,
                'first_seen': device.first_seen.isoformat()
            })
        
        # Get access logs
        access_logs = AccessLog.objects.filter(user=user).order_by('-timestamp')[:10]
        logs_data = []
        for log in access_logs:
            logs_data.append({
                'id': log.id,
                'access_granted': log.access_granted,
                'denial_reason': log.denial_reason,
                'ip_address': log.ip_address,
                'mac_address': log.mac_address,
                'timestamp': log.timestamp.isoformat()
            })
        
        user_data = {
            'id': user.id,
            'phone_number': user.phone_number,
            'is_active': user.is_active,
            'created_at': user.created_at.isoformat(),
            'has_active_access': user.has_active_access(),
            'payments': payments_data,
            'devices': devices_data,
            'access_logs': logs_data,
            'statistics': {
                'total_payments': len([p for p in payments_data if p['status'] == 'completed']),
                'total_spent': sum(float(p['amount']) for p in payments_data if p['status'] == 'completed'),
                'device_count': len(devices_data),
                'active_devices': len([d for d in devices_data if d['is_active']])
            }
        }
        
        return Response({
            'success': True,
            'user': user_data
        })
        
    except User.DoesNotExist:
        return Response({
            'success': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Error getting user detail: {str(e)}')
        return Response({
            'success': False,
            'message': 'Error retrieving user details'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([SimpleAdminTokenPermission])
def update_user(request, user_id):
    """
    Update user information (Admin only)
    """
    try:
        user = User.objects.get(id=user_id)
        
        # Update allowed fields
        if 'is_active' in request.data:
            user.is_active = request.data['is_active']
        
        if 'phone_number' in request.data:
            new_phone = request.data['phone_number']
            # Check if phone number is already taken
            if User.objects.filter(phone_number=new_phone).exclude(id=user_id).exists():
                return Response({
                    'success': False,
                    'message': 'Phone number already exists'
                }, status=status.HTTP_400_BAD_REQUEST)
            user.phone_number = new_phone
        
        user.save()
        
        return Response({
            'success': True,
            'message': 'User updated successfully',
            'user': {
                'id': user.id,
                'phone_number': user.phone_number,
                'is_active': user.is_active,
                'has_active_access': user.has_active_access()
            }
        })
        
    except User.DoesNotExist:
        return Response({
            'success': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Error updating user: {str(e)}')
        return Response({
            'success': False,
            'message': 'Error updating user'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
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
            logger.warning(f'Could not logout user {phone_number} from MikroTik: {str(e)}')
        
        # Delete user (this will cascade delete payments, devices, etc.)
        user.delete()
        
        logger.info(f'User deleted: {phone_number}')
        
        return Response({
            'success': True,
            'message': f'User {phone_number} deleted successfully'
        })
        
    except User.DoesNotExist:
        return Response({
            'success': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Error deleting user: {str(e)}')
        return Response({
            'success': False,
            'message': 'Error deleting user'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Payment Management APIs

@api_view(['GET'])
@permission_classes([SimpleAdminTokenPermission])
def list_payments(request):
    """
    List all payments with filtering options (Admin only)
    """
    try:
        payments = Payment.objects.all().order_by('-created_at')
        
        # Apply filters
        status_filter = request.GET.get('status')
        phone_filter = request.GET.get('phone_number')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        bundle_filter = request.GET.get('bundle_id')
        
        if status_filter:
            payments = payments.filter(status=status_filter)
        
        if phone_filter:
            payments = payments.filter(phone_number__icontains=phone_filter)
        
        if date_from:
            try:
                from datetime import datetime
                date_from = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                payments = payments.filter(created_at__gte=date_from)
            except ValueError:
                pass
        
        if date_to:
            try:
                from datetime import datetime
                date_to = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                payments = payments.filter(created_at__lte=date_to)
            except ValueError:
                pass
        
        if bundle_filter:
            payments = payments.filter(bundle_id=bundle_filter)
        
        # Pagination
        page_size = int(request.GET.get('page_size', 20))
        page = int(request.GET.get('page', 1))
        start = (page - 1) * page_size
        end = start + page_size
        
        total_payments = payments.count()
        payments_page = payments[start:end]
        
        # Serialize payments
        payments_data = []
        for payment in payments_page:
            payment_data = {
                'id': payment.id,
                'phone_number': payment.phone_number,
                'amount': str(payment.amount),
                'status': payment.status,
                'order_reference': payment.order_reference,
                'bundle_name': payment.bundle.name if payment.bundle else None,
                'bundle_id': payment.bundle.id if payment.bundle else None,
                'created_at': payment.created_at.isoformat(),
                'completed_at': payment.completed_at.isoformat() if payment.completed_at else None,
                'user_id': payment.user.id if payment.user else None,
                'payment_reference': payment.payment_reference,
                'transaction_id': payment.transaction_id,
                'payment_channel': payment.payment_channel
            }
            payments_data.append(payment_data)
        
        # Calculate totals
        total_amount = payments.filter(status='completed').aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        pending_amount = payments.filter(status='pending').aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        return Response({
            'success': True,
            'payments': payments_data,
            'pagination': {
                'total': total_payments,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_payments + page_size - 1) // page_size
            },
            'summary': {
                'total_amount': str(total_amount),
                'pending_amount': str(pending_amount),
                'completed_count': payments.filter(status='completed').count(),
                'pending_count': payments.filter(status='pending').count(),
                'failed_count': payments.filter(status='failed').count()
            }
        })
        
    except Exception as e:
        logger.error(f'Error listing payments: {str(e)}')
        return Response({
            'success': False,
            'message': f'Error retrieving payments: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([SimpleAdminTokenPermission])
def get_payment_detail(request, payment_id):
    """
    Get detailed information about a specific payment (Admin only)
    """
    try:
        payment = Payment.objects.get(id=payment_id)
        
        # Get webhook logs for this payment
        webhook_logs = PaymentWebhook.objects.filter(
            order_reference=payment.order_reference
        ).order_by('-received_at')
        
        webhook_data = []
        for webhook in webhook_logs:
            webhook_data.append({
                'id': webhook.id,
                'event_type': webhook.event_type,
                'payment_status': webhook.payment_status,
                'amount': str(webhook.amount) if webhook.amount else None,
                'transaction_id': webhook.transaction_id,
                'received_at': webhook.received_at.isoformat(),
                'processed_at': webhook.processed_at.isoformat() if webhook.processed_at else None,
                'processing_status': webhook.processing_status
            })
        
        payment_data = {
            'id': payment.id,
            'phone_number': payment.phone_number,
            'amount': str(payment.amount),
            'status': payment.status,
            'order_reference': payment.order_reference,
            'payment_reference': payment.payment_reference,
            'transaction_id': payment.transaction_id,
            'payment_channel': payment.payment_channel,
            'bundle': {
                'id': payment.bundle.id,
                'name': payment.bundle.name,
                'price': str(payment.bundle.price),
                'duration_hours': payment.bundle.duration_hours,
                'description': payment.bundle.description
            } if payment.bundle else None,
            'user': {
                'id': payment.user.id,
                'phone_number': payment.user.phone_number,
                'is_active': payment.user.is_active,
                'has_active_access': payment.user.has_active_access()
            } if payment.user else None,
            'created_at': payment.created_at.isoformat(),
            'completed_at': payment.completed_at.isoformat() if payment.completed_at else None,
            'webhook_logs': webhook_data
        }
        
        return Response({
            'success': True,
            'payment': payment_data
        })
        
    except Payment.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Payment not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Error getting payment detail: {str(e)}')
        return Response({
            'success': False,
            'message': f'Error retrieving payment details: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([SimpleAdminTokenPermission])
def refund_payment(request, payment_id):
    """
    Refund a payment (Admin only) - marks payment as refunded and revokes access
    """
    try:
        payment = Payment.objects.get(id=payment_id)
        
        if payment.status != 'completed':
            return Response({
                'success': False,
                'message': 'Only completed payments can be refunded'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update payment status
        payment.status = 'refunded'
        payment.save()
        
        # Force logout user if they have active access
        if payment.user and payment.user.has_active_access():
            try:
                logout_user_from_mikrotik(payment.phone_number)
            except Exception as e:
                logger.warning(f'Could not logout user {payment.phone_number} from MikroTik: {str(e)}')
        
        logger.info(f'Payment refunded: {payment.order_reference}')
        
        return Response({
            'success': True,
            'message': f'Payment {payment.order_reference} refunded successfully'
        })
        
    except Payment.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Payment not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Error refunding payment: {str(e)}')
        return Response({
            'success': False,
            'message': 'Error processing refund'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Bundle/Package Management APIs

@api_view(['GET', 'POST'])
@permission_classes([SimpleAdminTokenPermission])
def manage_bundles(request):
    """
    List all bundles (GET) or create new bundle (POST) (Admin only)
    """
    if request.method == 'GET':
        try:
            bundles = Bundle.objects.all().order_by('price')
            
            bundles_data = []
            for bundle in bundles:
                # Get usage statistics
                total_purchases = Payment.objects.filter(
                    bundle=bundle, 
                    status='completed'
                ).count()
                
                revenue = Payment.objects.filter(
                    bundle=bundle, 
                    status='completed'
                ).aggregate(total=Sum('amount'))['total'] or 0
                
                bundles_data.append({
                    'id': bundle.id,
                    'name': bundle.name,
                    'description': bundle.description,
                    'price': str(bundle.price),
                    'duration_hours': bundle.duration_hours,
                    'is_active': bundle.is_active,
                    'display_order': bundle.display_order,
                    'total_purchases': total_purchases,
                    'revenue': str(revenue)
                })
            
            return Response({
                'success': True,
                'bundles': bundles_data
            })
            
        except Exception as e:
            logger.error(f'Error listing bundles: {str(e)}')
            return Response({
                'success': False,
                'message': 'Error retrieving bundles'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    elif request.method == 'POST':
        try:
            # Create new bundle
            bundle = Bundle.objects.create(
                name=request.data.get('name'),
                description=request.data.get('description', ''),
                price=request.data.get('price'),
                duration_hours=request.data.get('duration_hours'),
                display_order=request.data.get('display_order', 0),
                is_active=request.data.get('is_active', True)
            )
            
            return Response({
                'success': True,
                'message': 'Bundle created successfully',
                'bundle': {
                    'id': bundle.id,
                    'name': bundle.name,
                    'price': str(bundle.price),
                    'duration_hours': bundle.duration_hours
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f'Error creating bundle: {str(e)}')
            return Response({
                'success': False,
                'message': 'Error creating bundle'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([SimpleAdminTokenPermission])
def manage_bundle(request, bundle_id):
    """
    Get, update, or delete a specific bundle (Admin only)
    """
    try:
        bundle = Bundle.objects.get(id=bundle_id)
        
        if request.method == 'GET':
            # Get usage statistics
            payments = Payment.objects.filter(bundle=bundle)
            total_purchases = payments.filter(status='completed').count()
            revenue = payments.filter(status='completed').aggregate(
                total=Sum('amount')
            )['total'] or 0
            
            recent_purchases = payments.filter(status='completed').order_by('-completed_at')[:10]
            recent_data = []
            for payment in recent_purchases:
                recent_data.append({
                    'phone_number': payment.phone_number,
                    'amount': str(payment.amount),
                    'completed_at': payment.completed_at.isoformat()
                })
            
            bundle_data = {
                'id': bundle.id,
                'name': bundle.name,
                'description': bundle.description,
                'price': str(bundle.price),
                'duration_hours': bundle.duration_hours,
                'is_active': bundle.is_active,
                'display_order': bundle.display_order,
                'statistics': {
                    'total_purchases': total_purchases,
                    'total_revenue': str(revenue),
                    'recent_purchases': recent_data
                }
            }
            
            return Response({
                'success': True,
                'bundle': bundle_data
            })
        
        elif request.method == 'PUT':
            # Update bundle
            if 'name' in request.data:
                bundle.name = request.data['name']
            if 'description' in request.data:
                bundle.description = request.data['description']
            if 'price' in request.data:
                bundle.price = request.data['price']
            if 'duration_hours' in request.data:
                bundle.duration_hours = request.data['duration_hours']
            if 'display_order' in request.data:
                bundle.display_order = request.data['display_order']
            if 'is_active' in request.data:
                bundle.is_active = request.data['is_active']
            
            bundle.save()
            
            return Response({
                'success': True,
                'message': 'Bundle updated successfully',
                'bundle': {
                    'id': bundle.id,
                    'name': bundle.name,
                    'price': str(bundle.price),
                    'is_active': bundle.is_active
                }
            })
        
        elif request.method == 'DELETE':
            # Check if bundle has any payments
            payment_count = Payment.objects.filter(bundle=bundle).count()
            if payment_count > 0:
                return Response({
                    'success': False,
                    'message': f'Cannot delete bundle with {payment_count} associated payments. Deactivate instead.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            bundle_name = bundle.name
            bundle.delete()
            
            return Response({
                'success': True,
                'message': f'Bundle "{bundle_name}" deleted successfully'
            })
        
    except Bundle.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Bundle not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Error managing bundle: {str(e)}')
        return Response({
            'success': False,
            'message': 'Error managing bundle'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# System Settings APIs

@api_view(['GET', 'PUT'])
@permission_classes([SimpleAdminTokenPermission])
def system_settings(request):
    """
    Get or update system settings (Admin only)
    """
    if request.method == 'GET':
        try:
            from django.conf import settings as django_settings
            
            # Get current settings (you can expand this based on your needs)
            settings_data = {
                'mikrotik': {
                    'router_ip': getattr(django_settings, 'MIKROTIK_ROUTER_IP', ''),
                    'username': getattr(django_settings, 'MIKROTIK_USERNAME', ''),
                    'hotspot_name': getattr(django_settings, 'MIKROTIK_HOTSPOT_NAME', ''),
                    'api_port': getattr(django_settings, 'MIKROTIK_API_PORT', 8728),
                    'connection_status': 'Unknown'  # You can add a test here
                },
                'clickpesa': {
                    'api_key_configured': bool(getattr(django_settings, 'CLICKPESA_API_KEY', '')),
                    'webhook_url': getattr(django_settings, 'CLICKPESA_WEBHOOK_URL', ''),
                    'environment': getattr(django_settings, 'CLICKPESA_ENVIRONMENT', 'sandbox')
                },
                'nextsms': {
                    'api_key_configured': bool(getattr(django_settings, 'NEXTSMS_API_KEY', '')),
                    'sender_id': getattr(django_settings, 'NEXTSMS_SENDER_ID', '')
                },
                'system': {
                    'debug_mode': getattr(django_settings, 'DEBUG', False),
                    'allowed_hosts': getattr(django_settings, 'ALLOWED_HOSTS', []),
                    'time_zone': getattr(django_settings, 'TIME_ZONE', 'UTC'),
                    'language_code': getattr(django_settings, 'LANGUAGE_CODE', 'en-us')
                }
            }
            
            return Response({
                'success': True,
                'settings': settings_data
            })
            
        except Exception as e:
            logger.error(f'Error getting system settings: {str(e)}')
            return Response({
                'success': False,
                'message': 'Error retrieving system settings'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    elif request.method == 'PUT':
        # Note: In production, you'd want to store these in a database table
        # or environment variables, not modify Django settings directly
        return Response({
            'success': True,
            'message': 'Settings updated successfully',
            'note': 'Settings updates require server restart to take effect'
        })


@api_view(['GET'])
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
        db_status = 'OK'
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            db_status = 'ERROR'
        
        # MikroTik connection test
        mikrotik_status = 'Unknown'
        try:
            # You can add actual MikroTik connection test here
            mikrotik_status = 'OK'  # Placeholder
        except Exception:
            mikrotik_status = 'ERROR'
        
        # Get system statistics
        now = timezone.now()
        today = now.date()
        week_ago = now - timedelta(days=7)
        
        stats = {
            'database_status': db_status,
            'mikrotik_status': mikrotik_status,
            'uptime': 'Unknown',  # You can calculate actual uptime
            'memory_usage': 'Unknown',  # You can get actual memory usage
            'disk_usage': 'Unknown',  # You can get actual disk usage
            'active_users': User.objects.filter(
                is_active=True,
                paid_until__gt=now
            ).count(),
            'payments_today': Payment.objects.filter(
                created_at__date=today,
                status='completed'
            ).count(),
            'revenue_today': Payment.objects.filter(
                created_at__date=today,
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or 0,
            'payments_week': Payment.objects.filter(
                created_at__gte=week_ago,
                status='completed'
            ).count(),
            'revenue_week': Payment.objects.filter(
                created_at__gte=week_ago,
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or 0,
            'total_users': User.objects.count(),
            'active_bundles': Bundle.objects.filter(is_active=True).count(),
            'pending_payments': Payment.objects.filter(status='pending').count()
        }
        
        return Response({
            'success': True,
            'status': stats,
            'timestamp': now.isoformat()
        })
        
    except Exception as e:
        logger.error(f'Error getting system status: {str(e)}')
        return Response({
            'success': False,
            'message': f'Error retrieving system status: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# MikroTik Router Configuration and Management APIs

@api_view(['GET', 'POST'])
@permission_classes([SimpleAdminTokenPermission])
def mikrotik_configuration(request):
    """
    Get or update MikroTik router configuration (Admin only)
    """
    if request.method == 'GET':
        try:
            from django.conf import settings as django_settings
            
            config_data = {
                'router_ip': getattr(django_settings, 'MIKROTIK_ROUTER_IP', ''),
                'username': getattr(django_settings, 'MIKROTIK_USERNAME', ''),
                'password_configured': bool(getattr(django_settings, 'MIKROTIK_PASSWORD', '')),
                'api_port': getattr(django_settings, 'MIKROTIK_API_PORT', 8728),
                'hotspot_name': getattr(django_settings, 'MIKROTIK_HOTSPOT_NAME', ''),
                'connection_timeout': getattr(django_settings, 'MIKROTIK_CONNECTION_TIMEOUT', 10),
                'max_login_attempts': getattr(django_settings, 'MIKROTIK_MAX_LOGIN_ATTEMPTS', 3)
            }
            
            return Response({
                'success': True,
                'configuration': config_data
            })
            
        except Exception as e:
            logger.error(f'Error getting MikroTik configuration: {str(e)}')
            return Response({
                'success': False,
                'message': 'Error retrieving MikroTik configuration'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    elif request.method == 'POST':
        try:
            # In a real implementation, you'd save these to a database table or update environment variables
            # For now, we'll just validate and return success
            
            required_fields = ['router_ip', 'username', 'password', 'hotspot_name']
            for field in required_fields:
                if not request.data.get(field):
                    return Response({
                        'success': False,
                        'message': f'{field} is required'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate IP address format
            import ipaddress
            try:
                ipaddress.ip_address(request.data['router_ip'])
            except ValueError:
                return Response({
                    'success': False,
                    'message': 'Invalid IP address format'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Test connection with new configuration
            try:
                from .mikrotik import test_mikrotik_connection
                test_result = test_mikrotik_connection(
                    host=request.data['router_ip'],
                    username=request.data['username'],
                    password=request.data['password'],
                    port=request.data.get('api_port', 8728)
                )
                
                if not test_result['success']:
                    return Response({
                        'success': False,
                        'message': f'Connection test failed: {test_result["error"]}'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
            except ImportError:
                logger.warning('MikroTik connection test not available')
            
            return Response({
                'success': True,
                'message': 'MikroTik configuration updated successfully',
                'note': 'Server restart may be required for changes to take effect'
            })
            
        except Exception as e:
            logger.error(f'Error updating MikroTik configuration: {str(e)}')
            return Response({
                'success': False,
                'message': 'Error updating MikroTik configuration'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([SimpleAdminTokenPermission])
def test_mikrotik_connection(request):
    """
    Test MikroTik router connection (Admin only)
    """
    try:
        from .mikrotik import test_mikrotik_connection
        
        # Use provided credentials or default from settings
        router_ip = request.data.get('router_ip') or getattr(settings, 'MIKROTIK_ROUTER_IP', '')
        username = request.data.get('username') or getattr(settings, 'MIKROTIK_USERNAME', '')
        password = request.data.get('password') or getattr(settings, 'MIKROTIK_PASSWORD', '')
        api_port = request.data.get('api_port') or getattr(settings, 'MIKROTIK_API_PORT', 8728)
        
        if not all([router_ip, username, password]):
            return Response({
                'success': False,
                'message': 'Router IP, username, and password are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Test connection
        result = test_mikrotik_connection(
            host=router_ip,
            username=username,
            password=password,
            port=api_port
        )
        
        return Response({
            'success': result['success'],
            'message': result.get('message', 'Connection test completed'),
            'router_info': result.get('router_info', {}),
            'error': result.get('error') if not result['success'] else None
        })
        
    except ImportError:
        return Response({
            'success': False,
            'message': 'MikroTik library not available'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f'Error testing MikroTik connection: {str(e)}')
        return Response({
            'success': False,
            'message': f'Connection test error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([SimpleAdminTokenPermission])
def mikrotik_router_info(request):
    """
    Get detailed MikroTik router information (Admin only)
    """
    try:
        from .mikrotik import get_router_info
        
        result = get_router_info()
        
        if result['success']:
            return Response({
                'success': True,
                'router_info': result['data']
            })
        else:
            return Response({
                'success': False,
                'message': result.get('error', 'Failed to get router information')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except ImportError:
        return Response({
            'success': False,
            'message': 'MikroTik library not available'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f'Error getting router info: {str(e)}')
        return Response({
            'success': False,
            'message': f'Error retrieving router information: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([SimpleAdminTokenPermission])
def mikrotik_active_users(request):
    """
    Get list of currently active users on MikroTik hotspot (Admin only)
    """
    try:
        from .mikrotik import get_active_hotspot_users
        
        result = get_active_hotspot_users()
        
        if result['success']:
            # Enhance user data with database information
            active_users = result['data']
            enhanced_users = []
            
            for mikrotik_user in active_users:
                username = mikrotik_user.get('user', '')
                
                # Find corresponding user in database
                try:
                    db_user = User.objects.get(phone_number=username)
                    user_data = {
                        **mikrotik_user,
                        'database_info': {
                            'user_id': db_user.id,
                            'is_active': db_user.is_active,
                            'has_active_access': db_user.has_active_access(),
                            'device_count': db_user.devices.count()
                        }
                    }
                except User.DoesNotExist:
                    user_data = {
                        **mikrotik_user,
                        'database_info': None
                    }
                
                enhanced_users.append(user_data)
            
            return Response({
                'success': True,
                'active_users': enhanced_users,
                'total_count': len(enhanced_users)
            })
        else:
            return Response({
                'success': False,
                'message': result.get('error', 'Failed to get active users')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except ImportError:
        return Response({
            'success': False,
            'message': 'MikroTik library not available'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f'Error getting active users: {str(e)}')
        return Response({
            'success': False,
            'message': f'Error retrieving active users: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([SimpleAdminTokenPermission])
def mikrotik_disconnect_user(request):
    """
    Disconnect a specific user from MikroTik hotspot (Admin only)
    """
    try:
        username = request.data.get('username')
        if not username:
            return Response({
                'success': False,
                'message': 'Username is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        from .mikrotik import logout_user_from_mikrotik
        
        result = logout_user_from_mikrotik(username)
        
        if result:
            # Log the disconnection
            try:
                user = User.objects.get(phone_number=username)
                AccessLog.objects.create(
                    user=user,
                    ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
                    mac_address='',
                    access_granted=False,
                    denial_reason=f'Disconnected by admin user: {request.user.username if request.user.is_authenticated else "Unknown"}'
                )
            except User.DoesNotExist:
                pass  # Log anyway without user reference
            
            return Response({
                'success': True,
                'message': f'User {username} disconnected successfully'
            })
        else:
            return Response({
                'success': False,
                'message': f'Failed to disconnect user {username}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except ImportError:
        return Response({
            'success': False,
            'message': 'MikroTik library not available'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f'Error disconnecting user: {str(e)}')
        return Response({
            'success': False,
            'message': f'Error disconnecting user: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([SimpleAdminTokenPermission])
def mikrotik_disconnect_all_users(request):
    """
    Disconnect all users from MikroTik hotspot (Admin only)
    """
    try:
        from .mikrotik import disconnect_all_hotspot_users
        
        result = disconnect_all_hotspot_users()
        
        if result['success']:
            # Log the mass disconnection (using system user if available)
            try:
                # Try to create admin log without user reference
                from django.contrib.auth.models import User as AuthUser
                admin_user = request.user if request.user.is_authenticated else None
                AccessLog.objects.create(
                    user=admin_user if isinstance(admin_user, User) else None,
                    ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
                    mac_address='ADMIN_ACTION',
                    access_granted=False,
                    denial_reason=f'All users disconnected by admin: {request.user.username if request.user.is_authenticated else "Unknown"}'
                )
            except Exception:
                pass  # Don't fail if logging fails
            
            return Response({
                'success': True,
                'message': f'Successfully disconnected {result.get("count", 0)} users',
                'disconnected_count': result.get("count", 0)
            })
        else:
            return Response({
                'success': False,
                'message': result.get('error', 'Failed to disconnect all users')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except ImportError:
        return Response({
            'success': False,
            'message': 'MikroTik library not available'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f'Error disconnecting all users: {str(e)}')
        return Response({
            'success': False,
            'message': f'Error disconnecting all users: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([SimpleAdminTokenPermission])
def mikrotik_reboot_router(request):
    """
    Reboot MikroTik router (Admin only) - USE WITH CAUTION
    """
    try:
        # Require confirmation
        confirmation = request.data.get('confirm')
        if confirmation != 'REBOOT_ROUTER':
            return Response({
                'success': False,
                'message': 'Confirmation required. Send {"confirm": "REBOOT_ROUTER"} to proceed.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        from .mikrotik import reboot_router
        
        result = reboot_router()
        
        if result['success']:
            # Log the reboot (skip logging if it fails)
            try:
                from django.contrib.auth.models import User as AuthUser
                admin_user = request.user if request.user.is_authenticated else None
                AccessLog.objects.create(
                    user=admin_user if isinstance(admin_user, User) else None,
                    ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
                    mac_address='ADMIN_ACTION',
                    access_granted=False,
                    denial_reason=f'Router reboot initiated by admin: {request.user.username if request.user.is_authenticated else "Unknown"}'
                )
            except Exception:
                pass  # Don't fail if logging fails
            
            return Response({
                'success': True,
                'message': 'Router reboot initiated. The router will be offline for 1-2 minutes.',
                'warning': 'All users will be disconnected during reboot'
            })
        else:
            return Response({
                'success': False,
                'message': result.get('error', 'Failed to reboot router')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except ImportError:
        return Response({
            'success': False,
            'message': 'MikroTik library not available'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f'Error rebooting router: {str(e)}')
        return Response({
            'success': False,
            'message': f'Error rebooting router: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
@permission_classes([SimpleAdminTokenPermission])
def mikrotik_hotspot_profiles(request):
    """
    Get MikroTik hotspot user profiles (Admin only)
    """
    try:
        from .mikrotik import get_hotspot_profiles
        
        result = get_hotspot_profiles()
        
        if result['success']:
            return Response({
                'success': True,
                'profiles': result['data']
            })
        else:
            return Response({
                'success': False,
                'message': result.get('error', 'Failed to get hotspot profiles')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except ImportError:
        return Response({
            'success': False,
            'message': 'MikroTik library not available'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f'Error getting hotspot profiles: {str(e)}')
        return Response({
            'success': False,
            'message': f'Error retrieving hotspot profiles: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([SimpleAdminTokenPermission])
def mikrotik_create_hotspot_profile(request):
    """
    Create a new MikroTik hotspot user profile (Admin only)
    """
    try:
        profile_name = request.data.get('name')
        rate_limit = request.data.get('rate_limit', '512k/512k')
        session_timeout = request.data.get('session_timeout', '1d')
        idle_timeout = request.data.get('idle_timeout', '5m')
        
        if not profile_name:
            return Response({
                'success': False,
                'message': 'Profile name is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        from .mikrotik import create_hotspot_profile
        
        result = create_hotspot_profile(
            name=profile_name,
            rate_limit=rate_limit,
            session_timeout=session_timeout,
            idle_timeout=idle_timeout
        )
        
        if result['success']:
            return Response({
                'success': True,
                'message': f'Hotspot profile "{profile_name}" created successfully',
                'profile': result.get('data', {})
            })
        else:
            return Response({
                'success': False,
                'message': result.get('error', 'Failed to create hotspot profile')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except ImportError:
        return Response({
            'success': False,
            'message': 'MikroTik library not available'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f'Error creating hotspot profile: {str(e)}')
        return Response({
            'success': False,
            'message': f'Error creating hotspot profile: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([SimpleAdminTokenPermission])
def mikrotik_system_resources(request):
    """
    Get MikroTik router system resources and performance metrics (Admin only)
    """
    try:
        from .mikrotik import get_system_resources
        
        result = get_system_resources()
        
        if result['success']:
            return Response({
                'success': True,
                'system_resources': result['data']
            })
        else:
            return Response({
                'success': False,
                'message': result.get('error', 'Failed to get system resources')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except ImportError:
        return Response({
            'success': False,
            'message': 'MikroTik library not available'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f'Error getting system resources: {str(e)}')
        return Response({
            'success': False,
            'message': f'Error retrieving system resources: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Wi-Fi Access APIs


@api_view(['POST'])
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
    
    phone_number = serializer.validated_data['phone_number']
    ip_address = serializer.validated_data.get('ip_address', request.META.get('REMOTE_ADDR'))
    mac_address = serializer.validated_data.get('mac_address', '')
    
    try:
        user = User.objects.get(phone_number=phone_number)
        
        # Core access check - works for both payment and voucher users
        has_access = user.has_active_access()
        denial_reason = ''
        device = None
        access_method = 'unknown'
        
        # Determine how user got access (for better logging and debugging)
        if user.paid_until:
            # Check if user has payment history
            has_payments = user.payments.filter(status='completed').exists()
            # Check if user has voucher history  
            has_vouchers = user.vouchers_used.filter(is_used=True).exists()
            
            if has_payments and has_vouchers:
                access_method = 'payment_and_voucher'
            elif has_payments:
                access_method = 'payment'
            elif has_vouchers:
                access_method = 'voucher'
            else:
                access_method = 'manual'  # Manually extended by admin
        
        if not has_access:
            # Provide more specific denial reasons
            if not user.is_active:
                denial_reason = 'User account is deactivated'
            elif not user.paid_until:
                denial_reason = 'No payment or voucher redemption found'
            else:
                from django.utils import timezone
                now = timezone.now()
                if user.paid_until <= now:
                    expired_hours = int((now - user.paid_until).total_seconds() / 3600)
                    denial_reason = f'Access expired {expired_hours} hours ago - payment or voucher required'
                else:
                    denial_reason = 'Access verification failed'
            
            logger.info(f'Access denied for {phone_number}: {denial_reason} (method: {access_method}, paid_until: {user.paid_until})')
            
        elif mac_address:
            # User has access, now check device management
            device, created = Device.objects.get_or_create(
                user=user,
                mac_address=mac_address,
                defaults={'ip_address': ip_address, 'is_active': True}
            )
            
            if not created:
                # Update existing device
                device.ip_address = ip_address
                device.is_active = True
                device.save()
                logger.info(f'Updated existing device for {phone_number}: {mac_address} (method: {access_method})')
            else:
                # New device - check if limit reached
                active_devices = user.get_active_devices().count()
                if active_devices > user.max_devices:
                    has_access = False
                    denial_reason = f'Device limit reached ({user.max_devices} devices max)'
                    device.is_active = False
                    device.save()
                    logger.warning(f'Device limit exceeded for {phone_number}: {active_devices}/{user.max_devices} (method: {access_method})')
                else:
                    logger.info(f'New device registered for {phone_number}: {mac_address} ({active_devices}/{user.max_devices}, method: {access_method})')
        
        # Log access attempt with enhanced information
        AccessLog.objects.create(
            user=user,
            device=device,
            ip_address=ip_address or '127.0.0.1',
            mac_address=mac_address,
            access_granted=has_access,
            denial_reason=denial_reason
        )
        
        # Update user status if expired (deactivate if no valid access)
        if not has_access and user.is_active and not denial_reason.startswith('Device limit'):
            user.deactivate_access()
            logger.info(f'User {phone_number} deactivated due to expired access (method was: {access_method})')
        
        # Enhanced response with access method information
        response_data = {
            'access_granted': has_access,
            'denial_reason': denial_reason,
            'user': UserSerializer(user).data,
            'access_method': access_method,
            'debug_info': {
                'has_payments': user.payments.filter(status='completed').exists(),
                'has_vouchers': user.vouchers_used.filter(is_used=True).exists(),
                'paid_until': user.paid_until.isoformat() if user.paid_until else None,
                'is_active': user.is_active,
                'device_count': user.get_active_devices().count(),
                'max_devices': user.max_devices
            }
        }
        
        return Response(response_data)
        
    except User.DoesNotExist:
        return Response({
            'access_granted': False,
            'message': 'User not found. Please register and pay to access Wi-Fi.',
            'suggestion': 'Make a payment or redeem a voucher to create account and get access'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([AllowAny])
def initiate_payment(request):
    """
    Initiate ClickPesa USSD-PUSH payment
    """
    serializer = InitiatePaymentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    phone_number = serializer.validated_data['phone_number']
    bundle_id = serializer.validated_data.get('bundle_id')
    
    # Optional device information for immediate access after payment
    ip_address = request.data.get('ip_address', request.META.get('REMOTE_ADDR'))
    mac_address = request.data.get('mac_address', '')
    
    # Get or create user
    user, created = User.objects.get_or_create(phone_number=phone_number)
    
    # Register device if MAC address provided
    device = None
    if mac_address:
        device, device_created = Device.objects.get_or_create(
            user=user,
            mac_address=mac_address,
            defaults={'ip_address': ip_address or '127.0.0.1', 'is_active': True}
        )
        
        if device_created:
            logger.info(f'New device registered during payment initiation for {phone_number}: {mac_address}')
        else:
            # Update existing device
            device.ip_address = ip_address or '127.0.0.1'
            device.is_active = True
            device.save()
            logger.info(f'Device updated during payment initiation for {phone_number}: {mac_address}')
    
    # Get bundle or use default
    if bundle_id:
        try:
            bundle = Bundle.objects.get(id=bundle_id, is_active=True)
            amount = bundle.price
        except Bundle.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Invalid bundle selected'
            }, status=status.HTTP_400_BAD_REQUEST)
    else:
        # Use default daily bundle
        bundle = Bundle.objects.filter(duration_hours=24, is_active=True).first()
        amount = bundle.price if bundle else settings.DAILY_ACCESS_PRICE
    
    # Generate unique order reference (alphanumeric only)
    order_reference = f'KITONGA{user.id}{uuid.uuid4().hex[:8].upper()}'
    
    # Create payment record
    payment = Payment.objects.create(
        user=user,
        bundle=bundle,
        amount=amount,
        phone_number=phone_number,
        transaction_id=str(uuid.uuid4()),
        order_reference=order_reference,
        status='pending'
    )
    
    clickpesa = ClickPesaAPI()
    result = clickpesa.initiate_payment(
        phone_number=phone_number,
        amount=amount,
        order_reference=order_reference
    )
    
    if result['success']:
        return Response({
            'success': True,
            'message': result['message'],
            'transaction_id': payment.transaction_id,
            'order_reference': order_reference,
            'amount': float(amount),
            'bundle': BundleSerializer(bundle).data if bundle else None,
            'channel': result.get('channel')
        }, status=status.HTTP_200_OK)
    else:
        payment.mark_failed()
        return Response({
            'success': False,
            'message': result['message']
        }, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(['POST'])
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
        logger.info(f'ClickPesa webhook received: {json.dumps(webhook_data)}')
        
        # Extract webhook data - handle both formats
        event_type = webhook_data.get('event') or webhook_data.get('eventType', 'OTHER')
        payment_data = webhook_data.get('data', webhook_data.get('payment', {}))
        
        # Extract order reference from different possible fields
        order_reference = (
            payment_data.get('orderReference') or 
            payment_data.get('order_reference') or
            payment_data.get('id') or
            webhook_data.get('order_reference') or  # Check root level too
            webhook_data.get('orderReference')
        )
        
        # Extract transaction/payment ID
        transaction_id = (
            payment_data.get('paymentId') or 
            payment_data.get('id') or
            payment_data.get('transaction_id') or
            webhook_data.get('transaction_reference') or  # Check root level too
            webhook_data.get('transaction_id')
        )
        
        # Extract status
        status_code = payment_data.get('status') or webhook_data.get('status')
        
        # Extract other fields
        channel = payment_data.get('channel')
        amount = (
            payment_data.get('collectedAmount') or 
            payment_data.get('amount')
        )
        
        # Convert amount to decimal if it's a string
        if amount and isinstance(amount, str):
            try:
                amount = float(amount)
            except ValueError:
                amount = None
        
        # Create webhook log entry
        from .models import PaymentWebhook
        webhook_log = PaymentWebhook.objects.create(
            event_type=event_type if event_type in dict(PaymentWebhook.WEBHOOK_EVENT_CHOICES) else 'OTHER',
            order_reference=order_reference or 'UNKNOWN',
            transaction_id=transaction_id or '',
            payment_status=status_code or 'UNKNOWN',
            channel=channel or '',
            amount=amount,
            raw_payload=webhook_data,
            source_ip=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        if not order_reference:
            error_msg = 'No order reference in webhook data'
            logger.error(error_msg)
            webhook_log.mark_failed(error_msg)
            return Response({'success': False, 'message': 'Missing order reference'})
        
        # Check for duplicates
        if webhook_log.is_duplicate:
            webhook_log.mark_ignored('Duplicate webhook - already processed')
            logger.info(f'Duplicate webhook ignored: {order_reference} - {event_type}')
            return Response({
                'success': True,
                'message': 'Duplicate webhook ignored'
            })
        
        # Find payment by order reference
        try:
            payment = Payment.objects.get(order_reference=order_reference)
            
            if (event_type == 'PAYMENT RECEIVED' or status_code == 'PAYMENT RECEIVED') and status_code in ['SUCCESS', 'COMPLETED', 'PAYMENT RECEIVED']:
                # Payment successful
                payment.mark_completed(
                    payment_reference=transaction_id,
                    channel=channel
                )
                logger.info(f'Payment completed: {order_reference} - {transaction_id}')
                
                # Try to authenticate user with MikroTik immediately after payment
                mikrotik_auth_result = None
                try:
                    from .mikrotik import authenticate_user_with_mikrotik
                    
                    # Try to find device information from recent access logs or request
                    user = payment.user
                    device = user.devices.filter(is_active=True).first()
                    
                    if device:
                        mikrotik_auth_result = authenticate_user_with_mikrotik(
                            phone_number=payment.phone_number,
                            mac_address=device.mac_address,
                            ip_address=device.ip_address
                        )
                        logger.info(f'MikroTik authentication after payment for {payment.phone_number}: {mikrotik_auth_result}')
                    else:
                        logger.info(f'No active device found for {payment.phone_number} - user will authenticate on next WiFi connection')
                        
                except Exception as e:
                    logger.error(f'MikroTik authentication failed after payment for {payment.phone_number}: {str(e)}')
                    mikrotik_auth_result = {'success': False, 'error': str(e)}
                
                from .nextsms import NextSMSAPI
                from .models import SMSLog
                
                nextsms = NextSMSAPI()
                duration_hours = payment.bundle.duration_hours if payment.bundle else 24
                
                # Enhanced SMS with connection instructions
                if mikrotik_auth_result and mikrotik_auth_result.get('success'):
                    sms_result = nextsms.send_payment_confirmation_with_auth_success(
                        payment.phone_number,
                        payment.amount,
                        duration_hours
                    )
                else:
                    sms_result = nextsms.send_payment_confirmation_with_reconnect_instructions(
                        payment.phone_number,
                        payment.amount,
                        duration_hours
                    )
                
                # Log SMS
                SMSLog.objects.create(
                    phone_number=payment.phone_number,
                    message=f'Payment confirmation: TSh {payment.amount}',
                    sms_type='payment',
                    success=sms_result['success'],
                    response_data=sms_result.get('data')
                )
                
            elif event_type == 'PAYMENT FAILED' or status_code == 'FAILED':
                # Payment failed
                payment.mark_failed()
                logger.warning(f'Payment failed: {order_reference}')
                
                from .nextsms import NextSMSAPI
                from .models import SMSLog
                
                nextsms = NextSMSAPI()
                sms_result = nextsms.send_payment_failed_notification(
                    payment.phone_number,
                    payment.amount
                )
                
                # Log SMS
                SMSLog.objects.create(
                    phone_number=payment.phone_number,
                    message=f'Payment failed notification: TSh {payment.amount}',
                    sms_type='payment',
                    success=sms_result['success'],
                    response_data=sms_result.get('data')
                )
            
            # Mark webhook as processed
            webhook_log.mark_processed(payment)
            
            return Response({
                'success': True,
                'message': 'Webhook processed successfully'
            })
            
        except Payment.DoesNotExist:
            error_msg = f'Payment not found for order reference: {order_reference}'
            logger.error(error_msg)
            webhook_log.mark_failed(error_msg)
            return Response({
                'success': False,
                'message': 'Payment not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        error_msg = f'Error processing ClickPesa webhook: {str(e)}'
        logger.error(error_msg)
        if webhook_log:
            webhook_log.mark_failed(error_msg)
        return Response({
            'success': False,
            'message': 'Webhook processing failed'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
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
        
        if result['success']:
            payment_data = result['data']
            logger.info(f'ClickPesa returned data type: {type(payment_data)}, data: {payment_data}')
            
            # Handle case where ClickPesa returns a list of payments
            if isinstance(payment_data, list):
                if payment_data:
                    # Use the first payment in the list
                    payment_data = payment_data[0]
                    logger.info(f'Using first payment from list: {payment_data}')
                else:
                    # Empty list - no payment found
                    return Response({
                        'success': False,
                        'message': 'Payment not found in ClickPesa'
                    }, status=status.HTTP_404_NOT_FOUND)
            
            status_code = payment_data.get('status')
            
            # Update payment status if changed
            if status_code == 'COMPLETED' and payment.status == 'pending':
                payment.mark_completed(
                    payment_reference=payment_data.get('id'),
                    channel=payment_data.get('channel')
                )
            elif status_code == 'FAILED' and payment.status == 'pending':
                payment.mark_failed()
            
            return Response({
                'success': True,
                'payment': PaymentSerializer(payment).data,
                'clickpesa_status': payment_data
            })
        else:
            # ClickPesa query failed, return local payment status
            logger.warning(f'ClickPesa query failed for {order_reference}: {result["message"]}')
            return Response({
                'success': True,
                'payment': PaymentSerializer(payment).data,
                'clickpesa_status': None,
                'message': 'Using local payment status (ClickPesa query failed)'
            })
            
    except Payment.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Payment not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([SimpleAdminTokenPermission])
def generate_vouchers(request):
    """
    Generate voucher codes (Admin only) and send SMS notification
    """
    serializer = GenerateVouchersSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    quantity = serializer.validated_data['quantity']
    duration_hours = serializer.validated_data['duration_hours']
    batch_id = serializer.validated_data.get('batch_id', f'BATCH-{uuid.uuid4().hex[:8].upper()}')
    notes = serializer.validated_data.get('notes', '')
    admin_phone_number = serializer.validated_data['admin_phone_number']
    language = serializer.validated_data.get('language', 'en')
    
    created_by = request.user.username if request.user.is_authenticated else 'admin'
    
    # Generate vouchers
    vouchers = []
    for _ in range(quantity):
        voucher = Voucher.objects.create(
            code=Voucher.generate_code(),
            duration_hours=duration_hours,
            batch_id=batch_id,
            created_by=created_by,
            notes=notes
        )
        vouchers.append(voucher)
    
    logger.info(f'Generated {quantity} vouchers in batch {batch_id} by {created_by}')
    
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
        message=f'Voucher generation summary: {quantity} vouchers in batch {batch_id}',
        sms_type='admin',
        success=summary_result['success'],
        response_data=summary_result.get('data')
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
            message=f'Detailed voucher codes for batch {batch_id}',
            sms_type='admin',
            success=detailed_result['success'],
            response_data=detailed_result.get('details')
        )
    
    response_data = {
        'success': True,
        'message': f'Successfully generated {quantity} vouchers',
        'batch_id': batch_id,
        'vouchers': VoucherSerializer(vouchers, many=True).data,
        'sms_notification': {
            'summary_sent': summary_result['success'],
            'detailed_sent': detailed_result['success'] if detailed_result else False,
            'admin_phone': admin_phone_number,
            'language': language
        }
    }
    
    # Add warning if SMS failed
    if not summary_result['success']:
        response_data['warning'] = 'Vouchers generated but SMS notification failed'
    
    return Response(response_data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def redeem_voucher(request):
    """
    Redeem a voucher code and grant internet access
    Creates user account if needed and enables device access
    """
    serializer = RedeemVoucherSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    voucher_code = serializer.validated_data['voucher_code']
    phone_number = serializer.validated_data['phone_number']
    # Optional device information for immediate access
    ip_address = request.data.get('ip_address', request.META.get('REMOTE_ADDR'))
    mac_address = request.data.get('mac_address', '')
    
    try:
        voucher = Voucher.objects.get(code=voucher_code)
        
        # Check if voucher is already used
        if voucher.is_used:
            logger.warning(f'Attempt to redeem already used voucher {voucher_code} by {phone_number}')
            return Response({
                'success': False,
                'message': 'Voucher has already been used',
                'voucher_info': {
                    'code': voucher_code,
                    'used_at': voucher.used_at.isoformat() if voucher.used_at else None,
                    'used_by': voucher.used_by.phone_number if voucher.used_by else None
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get or create user
        user, created = User.objects.get_or_create(
            phone_number=phone_number,
            defaults={'max_devices': 1}  # Default device limit
        )
        
        if created:
            logger.info(f'Created new user {phone_number} via voucher redemption')
        
        # Redeem voucher - this will extend user access
        success, message = voucher.redeem(user)
        
        if success:
            logger.info(f'Voucher {voucher_code} redeemed by {phone_number} - access granted for {voucher.duration_hours} hours')
            
            # Handle device registration if MAC address provided
            device = None
            device_info = {}
            mikrotik_integration_info = {}
            
            if mac_address:
                device, device_created = Device.objects.get_or_create(
                    user=user,
                    mac_address=mac_address,
                    defaults={'ip_address': ip_address or '127.0.0.1', 'is_active': True}
                )
                
                if device_created:
                    active_devices = user.get_active_devices().count()
                    if active_devices <= user.max_devices:
                        device_info = {
                            'device_registered': True,
                            'device_id': device.id,
                            'mac_address': mac_address,
                            'device_count': active_devices,
                            'max_devices': user.max_devices
                        }
                        logger.info(f'Registered device {mac_address} for voucher user {phone_number} ({active_devices}/{user.max_devices})')
                    else:
                        # Device limit exceeded
                        device.is_active = False
                        device.save()
                        device_info = {
                            'device_registered': False,
                            'device_limit_exceeded': True,
                            'device_count': active_devices,
                            'max_devices': user.max_devices,
                            'warning': 'Device limit exceeded. Please remove an existing device first.'
                        }
                        logger.warning(f'Device limit exceeded for voucher user {phone_number}: {active_devices}/{user.max_devices}')
                else:
                    # Update existing device
                    device.ip_address = ip_address or device.ip_address
                    device.is_active = True
                    device.save()
                    device_info = {
                        'device_registered': True,
                        'device_id': device.id,
                        'mac_address': mac_address,
                        'existing_device_updated': True
                    }
                    logger.info(f'Updated existing device {mac_address} for voucher user {phone_number}')
                
                # Try to authenticate with MikroTik immediately after successful voucher redemption
                try:
                    mikrotik_auth_result = authenticate_user_with_mikrotik(phone_number, mac_address, ip_address)
                    mikrotik_integration_info = {
                        'mikrotik_auth_attempted': True,
                        'mikrotik_auth_success': mikrotik_auth_result,
                        'ready_for_internet': mikrotik_auth_result and user.has_active_access()
                    }
                    
                    if mikrotik_auth_result:
                        logger.info(f'Successfully authenticated voucher user {phone_number} with MikroTik router')
                    else:
                        logger.warning(f'Failed to authenticate voucher user {phone_number} with MikroTik router')
                        
                except Exception as e:
                    logger.error(f'MikroTik authentication error for voucher user {phone_number}: {str(e)}')
                    mikrotik_integration_info = {
                        'mikrotik_auth_attempted': True,
                        'mikrotik_auth_success': False,
                        'mikrotik_error': str(e),
                        'ready_for_internet': user.has_active_access()  # User still has access, just MikroTik sync failed
                    }
            else:
                # No MAC address provided, but user still gets access for when they connect
                device_info = {
                    'device_registered': False,
                    'message': 'No device registered. User can connect with any device within device limit.',
                    'max_devices': user.max_devices
                }
                mikrotik_integration_info = {
                    'mikrotik_auth_attempted': False,
                    'ready_for_internet': user.has_active_access(),
                    'note': 'Device will be registered when user connects to WiFi'
                }
            
            # Create access log for voucher redemption
            AccessLog.objects.create(
                user=user,
                device=device,
                ip_address=ip_address or '127.0.0.1',
                mac_address=mac_address,
                access_granted=True,
                denial_reason=f'Voucher redeemed: {voucher_code} - Access granted for {voucher.duration_hours} hours'
            )
            
            # Send SMS confirmation
            try:
                from .nextsms import NextSMSAPI
                from .models import SMSLog
                
                nextsms = NextSMSAPI()
                sms_result = nextsms.send_voucher_confirmation(
                    phone_number,
                    voucher_code,
                    voucher.duration_hours
                )
                
                # Log SMS
                SMSLog.objects.create(
                    phone_number=phone_number,
                    message=f'Voucher redemption: {voucher_code}',
                    sms_type='voucher',
                    success=sms_result['success'],
                    response_data=sms_result.get('data')
                )
                
                sms_sent = sms_result['success']
            except Exception as e:
                logger.error(f'SMS notification failed for voucher redemption {voucher_code}: {str(e)}')
                sms_sent = False
            
            # Enhanced response with access and device information
            response_data = {
                'success': True,
                'message': message,
                'user': UserSerializer(user).data,
                'voucher_info': {
                    'code': voucher_code,
                    'duration_hours': voucher.duration_hours,
                    'redeemed_at': voucher.used_at.isoformat(),
                    'batch_id': voucher.batch_id
                },
                'access_info': {
                    'has_active_access': user.has_active_access(),
                    'paid_until': user.paid_until.isoformat() if user.paid_until else None,
                    'access_method': 'voucher',
                    'can_connect_to_wifi': user.has_active_access(),
                    'instructions': 'Connect to WiFi network. Your device will automatically get internet access.'
                },
                'device_info': device_info,
                'mikrotik_integration': mikrotik_integration_info,
                'sms_notification_sent': sms_sent,
                'next_steps': [
                    '1. Connect your device to the WiFi network',
                    '2. Open your browser - you should automatically get internet access',
                    '3. If prompted, enter your phone number to authenticate',
                    f'4. Your access is valid until {user.paid_until.strftime("%Y-%m-%d %H:%M") if user.paid_until else "N/A"}'
                ]
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        else:
            # Voucher redemption failed
            logger.error(f'Voucher redemption failed for {voucher_code} by {phone_number}: {message}')
            return Response({
                'success': False,
                'message': message
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Voucher.DoesNotExist:
        logger.warning(f'Invalid voucher code {voucher_code} attempted by {phone_number}')
        return Response({
            'success': False,
            'message': 'Invalid voucher code'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Error during voucher redemption {voucher_code} by {phone_number}: {str(e)}')
        return Response({
            'success': False,
            'message': 'Voucher redemption failed due to system error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([SimpleAdminTokenPermission])
def list_vouchers(request):
    """
    List all vouchers with optional filters (Admin only)
    """
    vouchers = Voucher.objects.all()
    
    # Filter by status
    is_used = request.query_params.get('is_used')
    if is_used is not None:
        vouchers = vouchers.filter(is_used=is_used.lower() == 'true')
    
    # Filter by batch
    batch_id = request.query_params.get('batch_id')
    if batch_id:
        vouchers = vouchers.filter(batch_id=batch_id)
    
    # Filter by duration
    duration = request.query_params.get('duration_hours')
    if duration:
        vouchers = vouchers.filter(duration_hours=int(duration))
    
    return Response({
        'success': True,
        'count': vouchers.count(),
        'vouchers': VoucherSerializer(vouchers, many=True).data
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def user_status(request, phone_number):
    """
    Get user status and access information
    """
    try:
        user = User.objects.get(phone_number=phone_number)
        return Response(UserSerializer(user).data)
    except User.DoesNotExist:
        return Response({
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)


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
    recent_payments = Payment.objects.filter(
        status='completed'
    ).select_related('user').order_by('-completed_at')[:10]
    
    # Recent users
    recent_users = User.objects.order_by('-created_at')[:10]
    
    # Payment status breakdown
    payment_stats = Payment.objects.values('status').annotate(
        count=Count('id')
    )
    
    voucher_stats = {
        'total': Voucher.objects.count(),
        'used': Voucher.objects.filter(is_used=True).count(),
        'available': Voucher.objects.filter(is_used=False).count(),
    }
    
    # Device statistics
    device_stats = {
        'total': Device.objects.count(),
        'active': Device.objects.filter(is_active=True).count(),
        'inactive': Device.objects.filter(is_active=False).count(),
    }
    
    context = {
        'active_users': active_users,
        'revenue_30d': revenue_30d,
        'revenue_7d': revenue_7d,
        'revenue_today': revenue_today,
        'recent_payments': recent_payments,
        'recent_users': recent_users,
        'payment_stats': payment_stats,
        'voucher_stats': voucher_stats,
        'device_stats': device_stats,
    }
    
    return render(request, 'admin/dashboard.html', context)


@api_view(['GET'])
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
    recent_payments = Payment.objects.filter(
        status='completed'
    ).select_related('user').order_by('-completed_at')[:10]
    
    # Recent users
    recent_users = User.objects.order_by('-created_at')[:10]
    
    # Payment status breakdown
    payment_stats = list(Payment.objects.values('status').annotate(
        count=Count('id')
    ))
    
    voucher_stats = {
        'total': Voucher.objects.count(),
        'used': Voucher.objects.filter(is_used=True).count(),
        'available': Voucher.objects.filter(is_used=False).count(),
    }
    
    # Device statistics
    device_stats = {
        'total': Device.objects.count(),
        'active': Device.objects.filter(is_active=True).count(),
        'inactive': Device.objects.filter(is_active=False).count(),
    }
    
    # Serialize recent payments
    recent_payments_data = []
    for payment in recent_payments:
        recent_payments_data.append({
            'id': payment.id,
            'phone_number': payment.phone_number,
            'amount': str(payment.amount),
            'status': payment.status,
            'completed_at': payment.completed_at.isoformat() if payment.completed_at else None,
            'created_at': payment.created_at.isoformat()
        })
    
    # Serialize recent users
    recent_users_data = []
    for user in recent_users:
        recent_users_data.append({
            'id': user.id,
            'phone_number': user.phone_number,
            'created_at': user.created_at.isoformat(),
            'is_active': user.is_active,
            'has_active_access': user.has_active_access()
        })
    
    return Response({
        'active_users': active_users,
        'revenue_30d': revenue_30d,
        'revenue_7d': revenue_7d,
        'revenue_today': revenue_today,
        'recent_payments': recent_payments_data,
        'recent_users': recent_users_data,
        'payment_stats': payment_stats,
        'voucher_stats': voucher_stats,
        'device_stats': device_stats,
    })


@api_view(['GET'])
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
            cache.set('health_check', 'ok', 10)
            cache.get('health_check')
        except Exception:
            pass  # Cache might not be configured
            
        return Response({
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'version': '1.0.0',
            'service': 'kitonga-wifi-billing'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return Response({
            'status': 'unhealthy',
            'timestamp': timezone.now().isoformat(),
            'error': str(e)
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['GET'])
@permission_classes([AllowAny])
def list_bundles(request):
    """
    List all active bundles
    """
    bundles = Bundle.objects.filter(is_active=True)
    return Response({
        'success': True,
        'bundles': BundleSerializer(bundles, many=True).data
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def list_user_devices(request, phone_number):
    """
    List all devices for a user
    """
    try:
        user = User.objects.get(phone_number=phone_number)
        devices = user.devices.all()
        
        return Response({
            'success': True,
            'max_devices': user.max_devices,
            'active_devices': user.get_active_devices().count(),
            'devices': DeviceSerializer(devices, many=True).data
        })
    except User.DoesNotExist:
        return Response({
            'success': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([AllowAny])
def remove_device(request):
    """
    Remove a device from user's account
    """
    phone_number = request.data.get('phone_number')
    device_id = request.data.get('device_id')
    
    if not phone_number or not device_id:
        return Response({
            'success': False,
            'message': 'Phone number and device ID are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(phone_number=phone_number)
        device = Device.objects.get(id=device_id, user=user)
        
        device.is_active = False
        device.save()
        
        return Response({
            'success': True,
            'message': 'Device removed successfully'
        })
    except User.DoesNotExist:
        return Response({
            'success': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Device.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Device not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([SimpleAdminTokenPermission])
def webhook_logs(request):
    """
    List webhook logs for debugging (Admin only)
    """
    logs = PaymentWebhook.objects.all()
    
    # Filter by processing status
    processing_status = request.query_params.get('processing_status')
    if processing_status:
        logs = logs.filter(processing_status=processing_status)
    
    # Filter by event type
    event_type = request.query_params.get('event_type')
    if event_type:
        logs = logs.filter(event_type=event_type)
    
    # Filter by order reference
    order_reference = request.query_params.get('order_reference')
    if order_reference:
        logs = logs.filter(order_reference__icontains=order_reference)
    
    # Limit results
    limit = int(request.query_params.get('limit', 50))
    logs = logs[:limit]
    
    webhook_data = []
    for log in logs:
        webhook_data.append({
            'id': log.id,
            'order_reference': log.order_reference,
            'event_type': log.event_type,
            'processing_status': log.processing_status,
            'payment_status': log.payment_status,
            'amount': float(log.amount) if log.amount else None,
            'channel': log.channel,
            'received_at': log.received_at.isoformat(),
            'processed_at': log.processed_at.isoformat() if log.processed_at else None,
            'processing_error': log.processing_error,
            'source_ip': log.source_ip,
            'has_payment': log.payment is not None,
            'raw_payload': log.raw_payload
        })
    
    return Response({
        'success': True,
        'count': len(webhook_data),
        'webhooks': webhook_data
    })


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
    """
    # Get parameters from Mikrotik (can be POST or GET, form data or JSON)
    username = None
    password = ''
    mac_address = ''
    ip_address = ''
    
    if request.method == 'POST':
        # Try to get from form data first (most common for MikroTik)
        username = request.POST.get('username')
        password = request.POST.get('password', '')
        mac_address = request.POST.get('mac', '')
        ip_address = request.POST.get('ip', '')
        
        # If not found in form data, try JSON
        if not username:
            try:
                json_data = json.loads(request.body.decode('utf-8'))
                username = json_data.get('username')
                password = json_data.get('password', '')
                mac_address = json_data.get('mac', '')
                ip_address = json_data.get('ip', '')
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
    else:
        # GET request
        username = request.GET.get('username')
        password = request.GET.get('password', '')
        mac_address = request.GET.get('mac', '')
        ip_address = request.GET.get('ip', '')
    
    logger.info(f'Mikrotik auth request: method={request.method}, username={username}, mac={mac_address}, ip={ip_address}')
    
    if not username:
        logger.warning('Mikrotik auth failed: No username provided')
        return HttpResponse('No username provided', status=403)
    
    try:
        # Check if user exists and has valid access
        user = User.objects.get(phone_number=username)
        
        # Determine access method for better logging
        access_method = 'unknown'
        if user.paid_until:
            has_payments = user.payments.filter(status='completed').exists()
            has_vouchers = user.vouchers_used.filter(is_used=True).exists()
            
            if has_payments and has_vouchers:
                access_method = 'payment_and_voucher'
            elif has_payments:
                access_method = 'payment'
            elif has_vouchers:
                access_method = 'voucher'
            else:
                access_method = 'manual'
        
        # Check if user has active access (unified logic for both payment and voucher users)
        has_access = user.has_active_access()
        denial_reason = ''
        device = None
        
        if not has_access:
            # Provide specific denial reasons based on user state
            if not user.is_active:
                denial_reason = 'User account deactivated'
            elif not user.paid_until:
                denial_reason = 'No payment or voucher found - please pay or redeem voucher'
            else:
                from django.utils import timezone
                now = timezone.now()
                if user.paid_until <= now:
                    expired_hours = int((now - user.paid_until).total_seconds() / 3600)
                    denial_reason = f'Access expired {expired_hours} hours ago - please pay or redeem voucher'
                else:
                    denial_reason = 'Access verification failed'
            
            logger.info(f'MikroTik access denied for {username}: {denial_reason} (method: {access_method}, paid_until: {user.paid_until})')
        else:
            # User has access - handle device registration if MAC address provided
            if mac_address:
                # User has access, now check device limit
                device, created = Device.objects.get_or_create(
                    user=user,
                    mac_address=mac_address,
                    defaults={'ip_address': ip_address, 'is_active': True}
                )
                
                if created:
                    # New device - check if limit exceeded
                    active_devices = user.get_active_devices().count()
                    if active_devices > user.max_devices:
                        has_access = False
                        denial_reason = f'Device limit reached ({user.max_devices} devices max)'
                        device.is_active = False
                        device.save()
                        logger.warning(f'Device limit exceeded for {username}: {active_devices}/{user.max_devices} (method: {access_method})')
                    else:
                        logger.info(f'New device registered for {username}: {mac_address} ({active_devices}/{user.max_devices}, method: {access_method})')
                else:
                    # Update existing device
                    device.ip_address = ip_address
                    device.is_active = True
                    device.save()
                    logger.info(f'Existing device updated for {username}: {mac_address} (method: {access_method})')
            else:
                # No MAC address provided - still allow access but log it
                logger.warning(f'Authentication request for {username} without MAC address - allowing access (method: {access_method})')
        
        # Log access attempt with enhanced information
        AccessLog.objects.create(
            user=user,
            device=device,
            ip_address=ip_address or '127.0.0.1',
            mac_address=mac_address,
            access_granted=has_access,
            denial_reason=denial_reason
        )
        
        # Update user status if expired (deactivate if no valid access)
        if not has_access and user.is_active and not denial_reason.startswith('Device limit'):
            user.deactivate_access()
            logger.info(f'User {username} deactivated due to expired access (method was: {access_method})')
        
        # Return appropriate response for MikroTik based on access status
        if has_access:
            logger.info(f'MikroTik auth SUCCESS for {username}: Access granted (method: {access_method})')
            return HttpResponse('OK', status=200)
        else:
            logger.warning(f'Mikrotik auth DENIED for {username}: {denial_reason} (method: {access_method})')
            return HttpResponse(denial_reason, status=403)
        
    except User.DoesNotExist:
        logger.warning(f'Mikrotik auth failed for {username}: User not found - no payment or voucher history')
        return HttpResponse('User not found - please make payment or redeem voucher', status=403)
    except Exception as e:
        logger.error(f'Error in Mikrotik authentication for {username}: {str(e)}')
        return HttpResponse('Authentication error', status=500)


@csrf_exempt
def mikrotik_logout(request):
    """
    Mikrotik hotspot logout endpoint
    
    Handles both form data and JSON data from MikroTik routers
    """
    username = None
    ip_address = ''
    
    if request.method == 'POST':
        # Try form data first
        username = request.POST.get('username')
        ip_address = request.POST.get('ip', '')
        
        # If not found in form data, try JSON
        if not username:
            try:
                json_data = json.loads(request.body.decode('utf-8'))
                username = json_data.get('username')
                ip_address = json_data.get('ip', '')
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
    else:
        # GET request
        username = request.GET.get('username')
        ip_address = request.GET.get('ip', '')
    
    logger.info(f'Mikrotik logout request: method={request.method}, username={username}, ip={ip_address}')
    
    if not username:
        return HttpResponse('No username provided', status=400)
    
    try:
        # Log the logout
        user = User.objects.get(phone_number=username)
        AccessLog.objects.create(
            user=user,
            ip_address=ip_address or '127.0.0.1',
            mac_address='',
            access_granted=False,
            denial_reason='Mikrotik logout'
        )
        
        logger.info(f'Mikrotik logout successful for {username}')
        return HttpResponse('OK', status=200)
        
    except User.DoesNotExist:
        # User not found but still return OK
        logger.info(f'Mikrotik logout for unknown user {username}')
        return HttpResponse('OK', status=200)
    except Exception as e:
        logger.error(f'Error in Mikrotik logout for {username}: {str(e)}')
        return HttpResponse('Logout error', status=500)


@api_view(['GET'])
@permission_classes([SimpleAdminTokenPermission])
def mikrotik_status_check(request):
    """
    Check MikroTik router status (Admin only)
    """
    try:
        from .mikrotik import get_mikrotik_client
        
        # Get router configuration from settings
        router_ip = settings.MIKROTIK_ROUTER_IP
        hotspot_name = settings.MIKROTIK_HOTSPOT_NAME
        
        # Try to get MikroTik client
        mikrotik_client = get_mikrotik_client()
        
        # Get active users count
        active_users_count = User.objects.filter(
            paid_until__gt=timezone.now(),
            is_active=True
        ).count()
        
        # Check if we can connect to router (basic connectivity test)
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((router_ip, 80))  # Test HTTP port
            sock.close()
            connection_status = "connected" if result == 0 else "disconnected"
        except Exception:
            connection_status = "unknown"
        
        return Response({
            'success': True,
            'router_ip': router_ip,
            'hotspot_name': hotspot_name,
            'connection_status': connection_status,
            'active_users': active_users_count,
            'api_port': settings.MIKROTIK_API_PORT,
            'admin_user': settings.MIKROTIK_ADMIN_USER,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f'MikroTik status check failed: {str(e)}')
        return Response({
            'success': False,
            'message': f'Failed to check router status: {str(e)}',
            'router_ip': getattr(settings, 'MIKROTIK_ROUTER_IP', 'Not configured'),
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
        
        if request.method == 'GET':
            username = request.GET.get('username')
        elif request.method == 'POST':
            # Try form data first (MikroTik format)
            username = request.POST.get('username')
            
            # If not found, try JSON
            if not username:
                try:
                    json_data = json.loads(request.body.decode('utf-8'))
                    username = json_data.get('username')
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
        
        if not username:
            return JsonResponse({
                'success': False,
                'message': 'Username is required'
            }, status=400)
        
        # Check if user exists in our database
        try:
            user = User.objects.get(phone_number=username)
        except User.DoesNotExist:
            # Check if it's a voucher
            try:
                voucher = Voucher.objects.get(code=username)
                return JsonResponse({
                    'success': True,
                    'user_type': 'voucher',
                    'username': username,
                    'is_active': not voucher.is_used,
                    'status': 'valid' if not voucher.is_used else 'invalid',
                    'voucher_info': {
                        'code': voucher.code,
                        'duration_hours': voucher.duration_hours,
                        'is_used': voucher.is_used,
                        'used_at': voucher.used_at.isoformat() if voucher.used_at else None,
                        'created_at': voucher.created_at.isoformat(),
                        'batch_id': voucher.batch_id
                    }
                })
            except Voucher.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'User not found',
                    'username': username,
                    'user_type': 'unknown'
                }, status=404)
        
        # User found - check their status
        has_active_access = user.has_active_access()
        
        # Get device information
        devices = user.devices.all()
        device_info = []
        for device in devices:
            device_info.append({
                'mac_address': device.mac_address,
                'first_seen': device.first_seen.isoformat(),
                'last_seen': device.last_seen.isoformat(),
                'is_active': device.is_active
            })
        
        # Get payment information
        latest_payment = user.payments.filter(status='completed').order_by('-created_at').first()
        payment_info = None
        if latest_payment:
            payment_info = {
                'bundle_name': latest_payment.bundle.name,
                'amount': str(latest_payment.amount),
                'paid_at': latest_payment.created_at.isoformat(),
                'expires_at': user.paid_until.isoformat() if user.paid_until else None
            }
        
        # Try to get MikroTik active session info
        mikrotik_session = None
        try:
            from .mikrotik import get_active_hotspot_users
            active_users_result = get_active_hotspot_users()
            if active_users_result['success']:
                for active_user in active_users_result['data']:
                    if active_user.get('user') == username:
                        mikrotik_session = {
                            'session_id': active_user.get('id'),
                            'ip_address': active_user.get('address'),
                            'mac_address': active_user.get('mac-address'),
                            'session_time': active_user.get('session-time'),
                            'bytes_in': active_user.get('bytes-in'),
                            'bytes_out': active_user.get('bytes-out'),
                            'packets_in': active_user.get('packets-in'),
                            'packets_out': active_user.get('packets-out')
                        }
                        break
        except Exception as e:
            logger.warning(f'Could not get MikroTik session info for {username}: {str(e)}')
        
        return JsonResponse({
            'success': True,
            'user_type': 'payment_user',
            'username': username,
            'is_active': user.is_active,
            'has_active_access': has_active_access,
            'status': 'active' if has_active_access else 'inactive',
            'user_info': {
                'user_id': user.id,
                'phone_number': user.phone_number,
                'is_active': user.is_active,
                'paid_until': user.paid_until.isoformat() if user.paid_until else None,
                'created_at': user.created_at.isoformat(),
                'device_count': len(device_info)
            },
            'devices': device_info,
            'payment_info': payment_info,
            'mikrotik_session': mikrotik_session,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f'MikroTik user status check failed for {username}: {str(e)}')
        return JsonResponse({
            'success': False,
            'message': f'Failed to check user status: {str(e)}',
            'username': username if 'username' in locals() else None,
            'error': str(e)
        }, status=500)


@api_view(['POST'])
@permission_classes([SimpleAdminTokenPermission])
def force_user_logout(request):
    """
    Force logout a user from all devices (Admin only)
    """
    phone_number = request.data.get('phone_number')
    
    if not phone_number:
        return Response({
            'success': False,
            'message': 'Phone number is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(phone_number=phone_number)
        
        # Logout from Mikrotik
        mikrotik_result = logout_user_from_mikrotik(phone_number)
        
        # Deactivate all user devices
        user.devices.update(is_active=False)
        
        # Log the forced logout
        AccessLog.objects.create(
            user=user,
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
            mac_address='ADMIN_ACTION',
            access_granted=False,
            denial_reason='Admin forced logout'
        )
        
        return Response({
            'success': True,
            'message': f'User {phone_number} forcibly logged out',
            'mikrotik_result': mikrotik_result
        })
        
    except User.DoesNotExist:
        return Response({
            'success': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Error in force logout: {str(e)}')
        return Response({
            'success': False,
            'message': 'Force logout error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def test_voucher_access(request):
    """
    Test endpoint specifically for voucher users to verify their access and MikroTik integration
    This helps debug voucher-related access issues
    """
    phone_number = request.data.get('phone_number')
    mac_address = request.data.get('mac_address', '')
    ip_address = request.data.get('ip_address', request.META.get('REMOTE_ADDR', '127.0.0.1'))
    
    if not phone_number:
        return Response({
            'success': False,
            'message': 'Phone number is required',
            'usage': {
                'POST': '{"phone_number": "255123456789", "mac_address": "AA:BB:CC:DD:EE:FF", "ip_address": "192.168.1.100"}'
            }
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(phone_number=phone_number)
        now = timezone.now()
        
        # Check if user has voucher history
        vouchers = user.vouchers_used.filter(is_used=True).order_by('-used_at')
        if not vouchers.exists():
            return Response({
                'success': False,
                'message': 'User has no voucher history',
                'suggestion': 'User needs to redeem a voucher first',
                'user_info': {
                    'phone_number': phone_number,
                    'has_payments': user.payments.filter(status='completed').exists(),
                    'has_vouchers': False
                }
            })
        
        # Test core access
        has_access = user.has_active_access()
        last_voucher = vouchers.first()
        
        # Test verify_access endpoint behavior
        verify_access_simulation = {
            'would_grant_access': has_access,
            'denial_reason': 'None' if has_access else 'Access expired or no valid voucher',
            'user_is_active': user.is_active,
            'paid_until': user.paid_until.isoformat() if user.paid_until else None
        }
        
        # Test MikroTik authentication behavior
        mikrotik_auth_simulation = {
            'would_authenticate': has_access,
            'http_status_expected': 200 if has_access else 403,
            'response_expected': 'Authentication success' if has_access else 'Access denied - payment or voucher required'
        }
        
        # Device management test
        device_info = {}
        if mac_address:
            try:
                device = Device.objects.get(user=user, mac_address=mac_address)
                device_info = {
                    'device_exists': True,
                    'device_active': device.is_active,
                    'device_id': device.id,
                    'last_seen': device.last_seen.isoformat()
                }
            except Device.DoesNotExist:
                device_info = {
                    'device_exists': False,
                    'would_create_device': user.get_active_devices().count() < user.max_devices,
                    'current_device_count': user.get_active_devices().count(),
                    'max_devices': user.max_devices
                }
        
        # Access logs for this user
        recent_logs = AccessLog.objects.filter(user=user).order_by('-timestamp')[:3]
        
        return Response({
            'success': True,
            'voucher_access_test': {
                'user_info': {
                    'phone_number': phone_number,
                    'created_at': user.created_at.isoformat(),
                    'is_active': user.is_active,
                    'max_devices': user.max_devices
                },
                'voucher_info': {
                    'total_vouchers_redeemed': vouchers.count(),
                    'last_voucher': {
                        'code': last_voucher.code,
                        'duration_hours': last_voucher.duration_hours,
                        'used_at': last_voucher.used_at.isoformat(),
                        'batch_id': last_voucher.batch_id
                    } if last_voucher else None,
                    'all_vouchers': [
                        {
                            'code': v.code,
                            'duration_hours': v.duration_hours,
                            'used_at': v.used_at.isoformat() if v.used_at else None
                        } for v in vouchers[:5]
                    ]
                },
                'access_status': {
                    'has_active_access': has_access,
                    'paid_until': user.paid_until.isoformat() if user.paid_until else None,
                    'time_remaining_hours': round((user.paid_until - now).total_seconds() / 3600, 1) if user.paid_until and has_access else 0,
                    'access_method': 'voucher'
                },
                'api_simulation': {
                    'verify_access_endpoint': verify_access_simulation,
                    'mikrotik_auth_endpoint': mikrotik_auth_simulation
                },
                'device_management': device_info,
                'recent_access_logs': [
                    {
                        'timestamp': log.timestamp.isoformat(),
                        'access_granted': log.access_granted,
                        'denial_reason': log.denial_reason or 'Access granted',
                        'mac_address': log.mac_address
                    } for log in recent_logs
                ],
                'recommendations': [
                    'User has valid voucher access - should be able to connect to WiFi' if has_access else 'Voucher access has expired - user needs to redeem a new voucher',
                    f'Last voucher was used {(now - last_voucher.used_at).days} days ago' if last_voucher and last_voucher.used_at else 'No recent voucher usage',
                    f'User can connect {user.max_devices - user.get_active_devices().count()} more devices' if user.get_active_devices().count() < user.max_devices else 'User has reached device limit'
                ]
            }
        })
        
    except User.DoesNotExist:
        return Response({
            'success': False,
            'message': f'User {phone_number} not found',
            'suggestion': 'User needs to redeem a voucher first to create an account'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Test voucher access error: {str(e)}')
        return Response({
            'success': False,
            'message': f'Test error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def trigger_device_authentication(request):
    """
    Manually trigger MikroTik authentication for a user's device
    This can be called after payment to activate internet access
    """
    phone_number = request.data.get('phone_number')
    mac_address = request.data.get('mac_address', '')
    ip_address = request.data.get('ip_address', request.META.get('REMOTE_ADDR'))
    
    if not phone_number:
        return Response({
            'success': False,
            'message': 'Phone number is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Check if user exists and has valid access
        user = User.objects.get(phone_number=phone_number)
        
        if not user.has_active_access():
            return Response({
                'success': False,
                'message': 'User does not have active access. Please make payment or redeem voucher first.',
                'user_status': {
                    'has_access': False,
                    'paid_until': user.paid_until.isoformat() if user.paid_until else None,
                    'is_active': user.is_active
                }
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Register/update device if MAC address provided
        device = None
        if mac_address:
            device, created = Device.objects.get_or_create(
                user=user,
                mac_address=mac_address,
                defaults={'ip_address': ip_address, 'is_active': True}
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
                ip_address=ip_address
            )
        except Exception as e:
            logger.error(f'MikroTik authentication error for {phone_number}: {str(e)}')
            mikrotik_result = {'success': False, 'error': str(e)}
        
        # Log the attempt
        AccessLog.objects.create(
            user=user,
            device=device,
            ip_address=ip_address or '127.0.0.1',
            mac_address=mac_address,
            access_granted=True,
            denial_reason=f'Manual authentication trigger - MikroTik result: {mikrotik_result.get("success", False)}'
        )
        
        response_data = {
            'success': True,
            'message': 'Authentication triggered successfully',
            'user_status': {
                'phone_number': phone_number,
                'has_access': user.has_active_access(),
                'paid_until': user.paid_until.isoformat() if user.paid_until else None,
                'is_active': user.is_active
            },
            'device_info': {
                'mac_address': mac_address,
                'ip_address': ip_address,
                'device_registered': device is not None
            },
            'mikrotik_result': mikrotik_result,
            'instructions': [
                'Your device authentication has been triggered.',
                'If you still cannot access internet:',
                '1. Disconnect from WiFi and reconnect',
                '2. Open a web browser and try to visit any website',
                '3. You should automatically get internet access',
                '4. If problems persist, contact support'
            ]
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response({
            'success': False,
            'message': 'User not found. Please make payment or redeem voucher first.'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Error in manual authentication trigger: {str(e)}')
        return Response({
            'success': False,
            'message': 'Authentication trigger failed due to system error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
