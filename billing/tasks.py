"""
Background tasks for Kitonga Wi-Fi Billing System
Handles automatic disconnection of expired users from MikroTik
"""
import logging
from django.utils import timezone
from .models import User, Device
from .mikrotik import revoke_user_access, logout_user_from_mikrotik, disconnect_user_from_mikrotik

logger = logging.getLogger(__name__)


def disconnect_expired_users():
    """
    Disconnect users whose access has expired.
    This should be run periodically (e.g., every 5 minutes via cron or celery beat).
    
    This function:
    1. Finds users whose paid_until has passed
    2. Disconnects them from MikroTik (removes active sessions, IP bindings, disables user)
    3. Deactivates their access in the database
    4. Marks their devices as inactive
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
        devices_deactivated = 0
        
        for user in expired_users:
            try:
                logger.info(f'Processing expired user: {user.phone_number} (paid_until: {user.paid_until})')
                
                # Get all active devices for this user
                devices = user.devices.filter(is_active=True)
                
                # Disconnect each device from MikroTik
                for device in devices:
                    try:
                        # Use the comprehensive disconnect function
                        result = disconnect_user_from_mikrotik(
                            username=user.phone_number,
                            mac_address=device.mac_address
                        )
                        
                        if result.get('success'):
                            logger.info(f'Successfully disconnected {user.phone_number} - {device.mac_address} from MikroTik')
                            logger.debug(f'  - Session removed: {result.get("session_removed")}')
                            logger.debug(f'  - Binding removed: {result.get("binding_removed")}')
                            logger.debug(f'  - User disabled: {result.get("user_disabled")}')
                        else:
                            logger.warning(f'Disconnect result for {user.phone_number} - {device.mac_address}: {result}')
                            if result.get('errors'):
                                logger.warning(f'  Errors: {result.get("errors")}')
                        
                        # Mark device as inactive in database
                        device.is_active = False
                        device.save()
                        devices_deactivated += 1
                        logger.info(f'Deactivated device {device.mac_address} for {user.phone_number}')
                        
                    except Exception as device_error:
                        logger.error(f'Error disconnecting device {device.mac_address} for {user.phone_number}: {str(device_error)}')
                        failed_count += 1
                
                # Also try to disconnect by username only (in case there are orphaned sessions)
                try:
                    result = disconnect_user_from_mikrotik(
                        username=user.phone_number,
                        mac_address=None
                    )
                    if result.get('success'):
                        logger.info(f'Additional cleanup for {user.phone_number}: {result.get("message")}')
                except Exception as cleanup_error:
                    logger.debug(f'Additional cleanup attempt for {user.phone_number}: {cleanup_error}')
                
                # Deactivate user in database
                user.deactivate_access()
                disconnected_count += 1
                logger.info(f'User {user.phone_number} deactivated after expiration')
                
            except Exception as user_error:
                logger.error(f'Error processing expired user {user.phone_number}: {str(user_error)}')
                failed_count += 1
        
        logger.info(f'Expired user cleanup complete: {disconnected_count} users disconnected, {devices_deactivated} devices deactivated, {failed_count} failures')
        
        return {
            'success': True,
            'disconnected': disconnected_count,
            'devices_deactivated': devices_deactivated,
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
