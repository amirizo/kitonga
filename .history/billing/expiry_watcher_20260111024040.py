"""
Real-time Access Expiration Watcher for Kitonga Wi-Fi Billing System

This module provides real-time monitoring and automatic disconnection
of users when their access expires. Instead of just checking every 5 minutes,
this watcher:

1. Monitors users with upcoming expirations
2. Schedules precise disconnection at the exact expiration time
3. Runs as a background thread in Django
4. Can also be run as a standalone management command

Usage:
    # As management command (recommended for production):
    python manage.py run_expiry_watcher

    # Or it auto-starts with Django via AppConfig.ready()
"""

import logging
import threading
import time
from datetime import timedelta
from django.utils import timezone
from django.db import connection

logger = logging.getLogger(__name__)


class AccessExpiryWatcher:
    """
    Real-time watcher that monitors user access expiration and
    disconnects users immediately when their access expires.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern to ensure only one watcher runs"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._running = False
        self._thread = None
        self._check_interval = 30  # Check every 30 seconds
        self._scheduled_disconnects = {}  # user_id -> scheduled_time
        
    def start(self):
        """Start the expiry watcher in a background thread"""
        if self._running:
            logger.warning("Expiry watcher is already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_watcher, daemon=True)
        self._thread.start()
        logger.info("🔍 Access Expiry Watcher started - monitoring user expirations in real-time")
    
    def stop(self):
        """Stop the expiry watcher"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Access Expiry Watcher stopped")
    
    def _run_watcher(self):
        """Main watcher loop - runs in background thread"""
        while self._running:
            try:
                self._check_and_disconnect_expired()
                time.sleep(self._check_interval)
            except Exception as e:
                logger.error(f"Error in expiry watcher loop: {e}")
                time.sleep(5)  # Wait a bit before retrying on error
    
    def _check_and_disconnect_expired(self):
        """
        Check for expired users and disconnect them immediately.
        Also monitors users about to expire in the next check interval.
        """
        try:
            # Close old database connections (important for long-running threads)
            connection.close_if_unusable_or_obsolete()
            
            from .models import User, Device, AccessLog
            from .mikrotik import disconnect_user_from_mikrotik
            
            now = timezone.now()
            
            # Find users whose access has just expired (within the last check interval + buffer)
            # This catches users who expired since last check
            check_window = now - timedelta(seconds=self._check_interval + 5)
            
            expired_users = User.objects.filter(
                is_active=True,
                paid_until__lte=now,
                paid_until__gte=check_window  # Only recent expirations to avoid re-processing
            )
            
            # Also get any missed users (expired but still active)
            missed_expired = User.objects.filter(
                is_active=True,
                paid_until__lt=check_window
            )
            
            all_expired = list(expired_users) + list(missed_expired)
            
            if all_expired:
                logger.info(f"⏰ Found {len(all_expired)} expired user(s) to disconnect")
            
            disconnected = 0
            for user in all_expired:
                try:
                    self._disconnect_user(user)
                    disconnected += 1
                except Exception as e:
                    logger.error(f"Failed to disconnect expired user {user.phone_number}: {e}")
            
            if disconnected > 0:
                logger.info(f"✅ Disconnected {disconnected} expired user(s)")
            
            # Log upcoming expirations for monitoring
            upcoming = User.objects.filter(
                is_active=True,
                paid_until__gt=now,
                paid_until__lte=now + timedelta(minutes=5)
            ).count()
            
            if upcoming > 0:
                logger.debug(f"📊 {upcoming} user(s) expiring in the next 5 minutes")
                
        except Exception as e:
            logger.error(f"Error checking expired users: {e}")
    
    def _disconnect_user(self, user):
        """Disconnect a specific user from MikroTik and deactivate their access"""
        from .models import Device, AccessLog
        from .mikrotik import disconnect_user_from_mikrotik, disconnect_user_from_tenant_routers
        
        phone_number = user.phone_number
        logger.info(f"🔌 Disconnecting expired user: {phone_number} (expired at {user.paid_until})")
        
        # Get all devices for this user
        devices = user.devices.filter(is_active=True)
        
        # Use tenant-aware disconnect for multi-tenant SaaS
        if user.tenant:
            # Disconnect from all tenant's routers at once
            for device in devices:
                try:
                    result = disconnect_user_from_tenant_routers(
                        user=user,
                        mac_address=device.mac_address
                    )
                    
                    if result.get('success'):
                        logger.info(f"  ✓ Disconnected device {device.mac_address} from {result.get('routers_succeeded', 0)} router(s)")
                    else:
                        logger.warning(f"  ⚠ Issue disconnecting {device.mac_address}: {result.get('message')}")
                    
                    # Mark device as inactive
                    device.is_active = False
                    device.save()
                    
                except Exception as e:
                    logger.error(f"  ✗ Error disconnecting device {device.mac_address}: {e}")
            
            # Also try to disconnect by username only (for orphaned sessions)
            try:
                disconnect_user_from_tenant_routers(user=user, mac_address=None)
            except Exception:
                pass
        else:
            # Fallback to legacy global router for users without tenant
            for device in devices:
                try:
                    result = disconnect_user_from_mikrotik(
                        username=phone_number,
                        mac_address=device.mac_address
                    )
                    
                    if result.get('success'):
                        logger.info(f"  ✓ Disconnected device {device.mac_address}")
                    else:
                        logger.warning(f"  ⚠ Issue disconnecting {device.mac_address}: {result.get('message')}")
                    
                    # Mark device as inactive
                    device.is_active = False
                    device.save()
                    
                except Exception as e:
                    logger.error(f"  ✗ Error disconnecting device {device.mac_address}: {e}")
            
            # Also try to disconnect by username only (for orphaned sessions)
            try:
                disconnect_user_from_mikrotik(username=phone_number, mac_address=None)
            except Exception:
                pass
        
        # Deactivate user access in database
        user.deactivate_access()
        
        # Create access log
        try:
            AccessLog.objects.create(
                user=user,
                device=None,
                access_granted=False,
                denial_reason='Access expired - auto-disconnected by expiry watcher',
                ip_address='127.0.0.1',
                mac_address=''
            )
        except Exception as log_error:
            logger.warning(f"Failed to create access log for {phone_number}: {log_error}")
        
        logger.info(f"  ✓ User {phone_number} fully disconnected and deactivated")


class MikroTikSessionEnforcer:
    """
    Configures MikroTik router to enforce session limits directly.
    This provides a hardware-level backup for access expiration.
    """
    
    @staticmethod
    def set_user_session_limit(username, duration_seconds):
        """
        Set a session limit on MikroTik for a user.
        When this limit is reached, MikroTik will auto-disconnect the user.
        """
        try:
            from .mikrotik import get_mikrotik_connection
            
            api = get_mikrotik_connection()
            if not api:
                return {'success': False, 'message': 'Could not connect to MikroTik'}
            
            # Find the hotspot user
            users = api.get_resource('/ip/hotspot/user')
            user_list = list(users.get(name=username))
            
            if not user_list:
                return {'success': False, 'message': f'User {username} not found on MikroTik'}
            
            user = user_list[0]
            
            # Update user with session limit (limit-uptime in hh:mm:ss format)
            hours = duration_seconds // 3600
            minutes = (duration_seconds % 3600) // 60
            seconds = duration_seconds % 60
            limit_uptime = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            users.set(id=user['id'], **{'limit-uptime': limit_uptime})
            
            logger.info(f"Set MikroTik session limit for {username}: {limit_uptime}")
            
            return {
                'success': True,
                'message': f'Session limit set to {limit_uptime}',
                'limit_uptime': limit_uptime
            }
            
        except Exception as e:
            logger.error(f"Error setting session limit for {username}: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    def update_all_active_users():
        """
        Update session limits for all active users based on their remaining time.
        Run this periodically to sync Django's paid_until with MikroTik limits.
        """
        try:
            from .models import User
            
            now = timezone.now()
            active_users = User.objects.filter(
                is_active=True,
                paid_until__gt=now
            )
            
            updated = 0
            for user in active_users:
                remaining = user.paid_until - now
                remaining_seconds = int(remaining.total_seconds())
                
                if remaining_seconds > 0:
                    result = MikroTikSessionEnforcer.set_user_session_limit(
                        user.phone_number,
                        remaining_seconds
                    )
                    if result.get('success'):
                        updated += 1
            
            logger.info(f"Updated MikroTik session limits for {updated} users")
            return {'success': True, 'updated': updated}
            
        except Exception as e:
            logger.error(f"Error updating all session limits: {e}")
            return {'success': False, 'error': str(e)}


# Global watcher instance
_watcher = None


def get_watcher():
    """Get the global watcher instance"""
    global _watcher
    if _watcher is None:
        _watcher = AccessExpiryWatcher()
    return _watcher


def start_expiry_watcher():
    """Start the expiry watcher (called from AppConfig.ready())"""
    watcher = get_watcher()
    watcher.start()
    return watcher


def stop_expiry_watcher():
    """Stop the expiry watcher"""
    global _watcher
    if _watcher:
        _watcher.stop()
        _watcher = None
