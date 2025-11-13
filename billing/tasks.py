"""
Background tasks for Kitonga Wi-Fi Billing System
Handles automatic disconnection of expired users
"""
import logging
from django.utils import timezone
from .models import User, Device
from .mikrotik import revoke_user_access, logout_user_from_mikrotik

logger = logging.getLogger(__name__)


def disconnect_expired_users():
    """
    Disconnect users whose access has expired
    This should be run periodically (e.g., every 5 minutes)
    """
    try:
        now = timezone.now()
        
        # Find users whose access has expired
        expired_users = User.objects.filter(
            is_active=True,
            paid_until__lte=now
        )
        
        disconnected_count = 0
        failed_count = 0
        
        for user in expired_users:
            try:
                logger.info(f'Disconnecting expired user: {user.phone_number} (paid_until: {user.paid_until})')
                
                # Get all active devices for this user
                devices = user.devices.filter(is_active=True)
                
                for device in devices:
                    try:
                        # Revoke access from MikroTik
                        result = revoke_user_access(
                            mac_address=device.mac_address,
                            username=user.phone_number
                        )
                        
                        if result.get('success'):
                            logger.info(f'Successfully revoked access for {user.phone_number} - {device.mac_address}')
                        else:
                            logger.warning(f'Failed to revoke access for {user.phone_number} - {device.mac_address}: {result}')
                            failed_count += 1
                            
                    except Exception as device_error:
                        logger.error(f'Error revoking device {device.mac_address} for {user.phone_number}: {str(device_error)}')
                        failed_count += 1
                
                # Deactivate user
                user.deactivate_access()
                disconnected_count += 1
                logger.info(f'User {user.phone_number} deactivated after expiration')
                
            except Exception as user_error:
                logger.error(f'Error disconnecting user {user.phone_number}: {str(user_error)}')
                failed_count += 1
        
        logger.info(f'Expired user cleanup: {disconnected_count} disconnected, {failed_count} failed')
        
        return {
            'success': True,
            'disconnected': disconnected_count,
            'failed': failed_count,
            'total_checked': expired_users.count()
        }
        
    except Exception as e:
        logger.error(f'Error in disconnect_expired_users task: {str(e)}')
        return {
            'success': False,
            'error': str(e)
        }


def cleanup_inactive_devices():
    """
    Clean up devices that haven't been seen in a while
    """
    try:
        from datetime import timedelta
        threshold = timezone.now() - timedelta(days=30)
        
        old_devices = Device.objects.filter(
            last_seen__lt=threshold,
            is_active=True
        )
        
        count = 0
        for device in old_devices:
            try:
                device.is_active = False
                device.save()
                count += 1
                logger.info(f'Deactivated old device {device.mac_address} for user {device.user.phone_number}')
            except Exception as e:
                logger.error(f'Error deactivating device {device.id}: {str(e)}')
        
        logger.info(f'Inactive device cleanup: {count} devices deactivated')
        
        return {
            'success': True,
            'deactivated': count
        }
        
    except Exception as e:
        logger.error(f'Error in cleanup_inactive_devices task: {str(e)}')
        return {
            'success': False,
            'error': str(e)
        }
