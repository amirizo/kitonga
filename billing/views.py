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
import uuid
import json
import logging
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models import Count, Sum
from datetime import timedelta
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User as DjangoUser
from django.views.decorators.http import require_http_methods
from rest_framework.authtoken.models import Token

from .models import User, Payment, AccessLog, Voucher, Bundle, Device, PaymentWebhook
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


# Wi-Fi Access APIs


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_access(request):
    """
    Verify if a user has valid access
    Called by captive portal to check access status
    """
    serializer = VerifyAccessSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    phone_number = serializer.validated_data['phone_number']
    ip_address = serializer.validated_data.get('ip_address', request.META.get('REMOTE_ADDR'))
    mac_address = serializer.validated_data.get('mac_address', '')
    
    try:
        user = User.objects.get(phone_number=phone_number)
        has_access = user.has_active_access()
        denial_reason = ''
        device = None
        
        if has_access and mac_address:
            # Check device limit
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
            else:
                # New device - check if limit reached
                if not user.can_add_device():
                    has_access = False
                    denial_reason = f'Device limit reached ({user.max_devices} devices max)'
                    device.is_active = False
                    device.save()
        
        # Log access attempt
        AccessLog.objects.create(
            user=user,
            device=device,
            ip_address=ip_address,
            mac_address=mac_address,
            access_granted=has_access,
            denial_reason=denial_reason
        )
        
        # Update user status if expired
        if not has_access and user.is_active and not denial_reason:
            user.deactivate_access()
        
        return Response({
            'access_granted': has_access,
            'denial_reason': denial_reason,
            'user': UserSerializer(user).data
        })
        
    except User.DoesNotExist:
        return Response({
            'access_granted': False,
            'message': 'User not found. Please register and pay to access Wi-Fi.'
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
    
    # Get or create user
    user, created = User.objects.get_or_create(phone_number=phone_number)
    
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
            payment_data.get('id')
        )
        
        # Extract transaction/payment ID
        transaction_id = (
            payment_data.get('paymentId') or 
            payment_data.get('id') or
            payment_data.get('transaction_id')
        )
        
        # Extract status
        status_code = payment_data.get('status')
        
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
            
            if event_type == 'PAYMENT RECEIVED' and status_code in ['SUCCESS', 'COMPLETED']:
                # Payment successful
                payment.mark_completed(
                    payment_reference=transaction_id,
                    channel=channel
                )
                logger.info(f'Payment completed: {order_reference} - {transaction_id}')
                
                from .nextsms import NextSMSAPI
                from .models import SMSLog
                
                nextsms = NextSMSAPI()
                duration_hours = payment.bundle.duration_hours if payment.bundle else 24
                sms_result = nextsms.send_payment_confirmation(
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
    Redeem a voucher code
    """
    serializer = RedeemVoucherSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    voucher_code = serializer.validated_data['voucher_code']
    phone_number = serializer.validated_data['phone_number']
    
    try:
        voucher = Voucher.objects.get(code=voucher_code)
        
        # Get or create user
        user, created = User.objects.get_or_create(phone_number=phone_number)
        
        # Redeem voucher
        success, message = voucher.redeem(user)
        
        if success:
            logger.info(f'Voucher {voucher_code} redeemed by {phone_number}')
            
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
            
            return Response({
                'success': True,
                'message': message,
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'message': message
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Voucher.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Invalid voucher code'
        }, status=status.HTTP_404_NOT_FOUND)


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
    Health check endpoint for monitoring
    """
    return Response({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'service': 'Kitonga Wi-Fi Billing System'
    })


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
@api_view(['POST', 'GET'])
@permission_classes([AllowAny])
def mikrotik_auth(request):
    """
    Mikrotik hotspot authentication endpoint
    
    This endpoint is called by Mikrotik router for external authentication
    Mikrotik expects HTTP 200 for success, 403 for deny
    """
    # Get parameters from Mikrotik (can be POST or GET)
    if request.method == 'POST':
        username = request.data.get('username') or request.POST.get('username')
        password = request.data.get('password') or request.POST.get('password', '')
        mac_address = request.data.get('mac') or request.POST.get('mac', '')
        ip_address = request.data.get('ip') or request.POST.get('ip', '')
    else:
        username = request.GET.get('username')
        password = request.GET.get('password', '')
        mac_address = request.GET.get('mac', '')
        ip_address = request.GET.get('ip', '')
    
    logger.info(f'Mikrotik auth request: username={username}, mac={mac_address}, ip={ip_address}')
    
    if not username:
        logger.warning('Mikrotik auth failed: No username provided')
        return Response('No username provided', status=403)
    
    try:
        # Check if user exists and has valid access
        user = User.objects.get(phone_number=username)
        
        # Check if user has active access (paid until date)
        if not user.has_active_access():
            logger.warning(f'Mikrotik auth denied for {username}: No active access')
            return Response('Payment required', status=403)
        
        # Check and manage device limit
        if mac_address:
            device, created = Device.objects.get_or_create(
                user=user,
                mac_address=mac_address,
                defaults={'ip_address': ip_address, 'is_active': True}
            )
            
            if created:
                # New device - check if limit exceeded
                active_devices = user.get_active_devices().count()
                if active_devices > user.max_devices:
                    device.delete()
                    logger.warning(f'Mikrotik auth denied for {username}: Device limit exceeded')
                    return Response(f'Device limit exceeded ({user.max_devices} max)', status=403)
            else:
                # Update existing device
                device.ip_address = ip_address
                device.is_active = True
                device.save()
        
        # Log successful access
        AccessLog.objects.create(
            user=user,
            mac_address=mac_address,
            ip_address=ip_address,
            authenticated=True,
            notes='Mikrotik authentication successful'
        )
        
        logger.info(f'Mikrotik auth successful for {username}')
        
        # Return simple success response for Mikrotik
        return Response('OK', status=200)
        
    except User.DoesNotExist:
        logger.warning(f'Mikrotik auth failed for {username}: User not found')
        return Response('User not found', status=403)
    except Exception as e:
        logger.error(f'Error in Mikrotik authentication for {username}: {str(e)}')
        return Response('Authentication error', status=500)


@api_view(['POST', 'GET'])
@permission_classes([AllowAny])
def mikrotik_logout(request):
    """
    Mikrotik hotspot logout endpoint
    """
    if request.method == 'POST':
        username = request.data.get('username') or request.POST.get('username')
        ip_address = request.data.get('ip') or request.POST.get('ip', '')
    else:
        username = request.GET.get('username')
        ip_address = request.GET.get('ip', '')
    
    logger.info(f'Mikrotik logout request: username={username}, ip={ip_address}')
    
    if not username:
        return Response('No username provided', status=400)
    
    try:
        # Log the logout
        user = User.objects.get(phone_number=username)
        AccessLog.objects.create(
            user=user,
            ip_address=ip_address,
            authenticated=False,
            notes='Mikrotik logout'
        )
        
        logger.info(f'Mikrotik logout successful for {username}')
        return Response('OK', status=200)
        
    except User.DoesNotExist:
        # User not found but still return OK
        logger.info(f'Mikrotik logout for unknown user {username}')
        return Response('OK', status=200)
    except Exception as e:
        logger.error(f'Error in Mikrotik logout for {username}: {str(e)}')
        return Response('Logout error', status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def mikrotik_status_check(request):
    """
    Check user status for Mikrotik
    """
    username = request.GET.get('username')
    
    if not username:
        return Response({
            'success': False,
            'message': 'Username is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(phone_number=username)
        
        # Get recent access logs
        recent_logs = AccessLog.objects.filter(user=user).order_by('-timestamp')[:5]
        
        return Response({
            'success': True,
            'user': {
                'phone_number': user.phone_number,
                'paid_until': user.paid_until.isoformat() if user.paid_until else None,
                'is_active': user.is_active,
                'has_active_access': user.has_active_access(),
                'device_count': user.get_active_devices().count(),
                'max_devices': user.max_devices
            },
            'recent_activity': [
                {
                    'timestamp': log.timestamp.isoformat(),
                    'authenticated': log.authenticated,
                    'ip_address': log.ip_address,
                    'mac_address': log.mac_address,
                    'notes': log.notes or ''
                } for log in recent_logs
            ]
        })
        
    except User.DoesNotExist:
        return Response({
            'success': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)


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
            authenticated=False,
            notes='Admin forced logout'
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
@permission_classes([SimpleAdminTokenPermission])
def test_user_access(request):
    """
    Test endpoint to verify user access logic (Admin only)
    """
    phone_number = request.data.get('phone_number')
    
    if not phone_number:
        return Response({
            'success': False,
            'message': 'Phone number is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(phone_number=phone_number)
        
        # Test authentication logic
        has_access = user.has_active_access()
        
        # Get device count
        active_devices = user.get_active_devices().count()
        
        # Recent access logs
        recent_logs = AccessLog.objects.filter(user=user).order_by('-timestamp')[:5]
        
        return Response({
            'success': True,
            'user_info': {
                'phone_number': user.phone_number,
                'is_active': user.is_active,
                'has_active_access': has_access,
                'paid_until': user.paid_until.isoformat() if user.paid_until else None,
                'total_payments': user.total_payments,
                'max_devices': user.max_devices,
                'active_devices': active_devices,
                'can_add_device': user.can_add_device()
            },
            'recent_activity': [
                {
                    'timestamp': log.timestamp.isoformat(),
                    'authenticated': log.authenticated,
                    'ip_address': log.ip_address or '',
                    'mac_address': log.mac_address or '',
                    'notes': log.notes or ''
                } for log in recent_logs
            ],
            'auth_test': {
                'would_allow_mikrotik': has_access,
                'reason': 'Access granted' if has_access else 'Payment required'
            }
        })
        
    except User.DoesNotExist:
        return Response({
            'success': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
