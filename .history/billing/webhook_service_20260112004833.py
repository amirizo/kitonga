"""
Webhook Service for Tenant Event Notifications
Business/Enterprise Feature
"""

import json
import hmac
import hashlib
import time
import logging
import requests
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class WebhookService:
    """
    Service to send webhook notifications to tenants.
    Handles event dispatching, signature generation, and retry logic.
    """

    TIMEOUT_SECONDS = 10
    
    @staticmethod
    def generate_signature(payload: str, secret: str) -> str:
        """Generate HMAC-SHA256 signature for webhook payload"""
        return hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    @classmethod
    def dispatch_event(cls, tenant, event_type: str, data: dict):
        """
        Dispatch an event to all subscribed webhooks for a tenant.
        
        Args:
            tenant: Tenant model instance
            event_type: Event type (e.g., 'payment.success')
            data: Event payload data
        """
        from .models import TenantWebhook, WebhookDelivery
        
        # Check if tenant has webhook feature enabled
        if not tenant.subscription_plan or not tenant.subscription_plan.webhook_notifications:
            logger.debug(f"Webhook notifications not enabled for tenant {tenant.slug}")
            return
        
        # Get all active webhooks subscribed to this event
        webhooks = TenantWebhook.objects.filter(
            tenant=tenant,
            is_active=True,
            status__in=["active", "failing"]
        )
        
        for webhook in webhooks:
            # Check if webhook is subscribed to this event
            if event_type not in webhook.events:
                continue
            
            # Create delivery record
            import uuid
            event_id = uuid.uuid4()
            
            payload = {
                "event_id": str(event_id),
                "event_type": event_type,
                "timestamp": timezone.now().isoformat(),
                "tenant_id": str(tenant.id),
                "data": data
            }
            
            delivery = WebhookDelivery.objects.create(
                webhook=webhook,
                event_type=event_type,
                event_id=event_id,
                payload=payload,
                status="pending"
            )
            
            # Attempt delivery
            cls.deliver_webhook(delivery)

    @classmethod
    def deliver_webhook(cls, delivery):
        """
        Attempt to deliver a webhook.
        
        Args:
            delivery: WebhookDelivery model instance
        """
        webhook = delivery.webhook
        
        # Prepare payload
        payload_json = json.dumps(delivery.payload, default=str)
        
        # Generate signature
        signature = cls.generate_signature(payload_json, webhook.secret_key)
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Event": delivery.event_type,
            "X-Webhook-ID": str(delivery.event_id),
            "X-Webhook-Timestamp": str(int(time.time())),
            "User-Agent": "Kitonga-Webhook/1.0"
        }
        
        # Add custom auth header if configured
        if webhook.auth_header:
            headers["Authorization"] = webhook.auth_header
        
        # Attempt delivery
        delivery.attempts += 1
        start_time = time.time()
        
        try:
            response = requests.post(
                webhook.url,
                data=payload_json,
                headers=headers,
                timeout=cls.TIMEOUT_SECONDS
            )
            
            response_time = int((time.time() - start_time) * 1000)
            delivery.response_time_ms = response_time
            delivery.response_status_code = response.status_code
            delivery.response_body = response.text[:1000]  # Limit response body size
            
            # Check if successful (2xx status code)
            if 200 <= response.status_code < 300:
                delivery.status = "success"
                delivery.delivered_at = timezone.now()
                delivery.save()
                webhook.record_success()
                logger.info(f"Webhook delivered: {webhook.name} - {delivery.event_type}")
            else:
                delivery.error_message = f"HTTP {response.status_code}: {response.text[:200]}"
                delivery.schedule_retry()
                webhook.record_failure(delivery.error_message)
                logger.warning(f"Webhook failed: {webhook.name} - HTTP {response.status_code}")
        
        except requests.exceptions.Timeout:
            delivery.error_message = "Request timed out"
            delivery.schedule_retry()
            webhook.record_failure(delivery.error_message)
            logger.warning(f"Webhook timeout: {webhook.name}")
        
        except requests.exceptions.ConnectionError as e:
            delivery.error_message = f"Connection error: {str(e)[:200]}"
            delivery.schedule_retry()
            webhook.record_failure(delivery.error_message)
            logger.warning(f"Webhook connection error: {webhook.name}")
        
        except Exception as e:
            delivery.error_message = f"Unexpected error: {str(e)[:200]}"
            delivery.schedule_retry()
            webhook.record_failure(delivery.error_message)
            logger.error(f"Webhook error: {webhook.name} - {str(e)}")
        
        delivery.save()

    @classmethod
    def process_pending_retries(cls):
        """Process all pending webhook retries that are due"""
        from .models import WebhookDelivery
        
        now = timezone.now()
        pending = WebhookDelivery.objects.filter(
            status="retrying",
            next_retry_at__lte=now
        ).select_related("webhook")
        
        count = 0
        for delivery in pending:
            if delivery.webhook.is_active:
                cls.deliver_webhook(delivery)
                count += 1
        
        return count


# =============================================================================
# EVENT DISPATCHER FUNCTIONS
# =============================================================================

def trigger_payment_success_webhook(payment):
    """Trigger webhook for successful payment"""
    if not payment.tenant:
        return
    
    data = {
        "payment_id": payment.transaction_id,
        "amount": float(payment.amount),
        "phone_number": payment.phone_number,
        "bundle_name": payment.bundle.name if payment.bundle else None,
        "duration_hours": payment.bundle.duration_hours if payment.bundle else None,
        "payment_channel": payment.payment_channel,
        "completed_at": payment.completed_at.isoformat() if payment.completed_at else None,
        "user": {
            "phone": payment.user.phone_number,
            "name": payment.user.name,
            "is_active": payment.user.is_active,
            "paid_until": payment.user.paid_until.isoformat() if payment.user.paid_until else None
        }
    }
    
    WebhookService.dispatch_event(payment.tenant, "payment.success", data)


def trigger_payment_failed_webhook(payment, reason: str = ""):
    """Trigger webhook for failed payment"""
    if not payment.tenant:
        return
    
    data = {
        "payment_id": payment.transaction_id,
        "amount": float(payment.amount),
        "phone_number": payment.phone_number,
        "reason": reason,
        "created_at": payment.created_at.isoformat()
    }
    
    WebhookService.dispatch_event(payment.tenant, "payment.failed", data)


def trigger_user_created_webhook(user):
    """Trigger webhook for new user creation"""
    if not user.tenant:
        return
    
    data = {
        "user_id": user.id,
        "phone_number": user.phone_number,
        "name": user.name,
        "created_at": user.created_at.isoformat()
    }
    
    WebhookService.dispatch_event(user.tenant, "user.created", data)


def trigger_user_expired_webhook(user):
    """Trigger webhook when user access expires"""
    if not user.tenant:
        return
    
    data = {
        "user_id": user.id,
        "phone_number": user.phone_number,
        "name": user.name,
        "expired_at": user.paid_until.isoformat() if user.paid_until else None
    }
    
    WebhookService.dispatch_event(user.tenant, "user.expired", data)


def trigger_voucher_redeemed_webhook(voucher, user):
    """Trigger webhook when voucher is redeemed"""
    if not voucher.tenant:
        return
    
    data = {
        "voucher_code": voucher.code,
        "duration_hours": voucher.duration_hours,
        "redeemed_at": voucher.used_at.isoformat() if voucher.used_at else None,
        "user": {
            "phone": user.phone_number,
            "name": user.name,
            "paid_until": user.paid_until.isoformat() if user.paid_until else None
        }
    }
    
    WebhookService.dispatch_event(voucher.tenant, "voucher.redeemed", data)


def trigger_router_status_webhook(router, new_status: str):
    """Trigger webhook when router status changes"""
    if not router.tenant:
        return
    
    event_type = "router.online" if new_status == "online" else "router.offline"
    
    data = {
        "router_id": router.id,
        "router_name": router.name,
        "status": new_status,
        "host": router.host,
        "last_seen": router.last_seen.isoformat() if router.last_seen else None
    }
    
    WebhookService.dispatch_event(router.tenant, event_type, data)
