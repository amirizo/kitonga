"""
Auto SMS Campaign Service
Business/Enterprise Feature

Handles automatic SMS triggers based on events and schedules.
"""

import logging
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class AutoSMSService:
    """
    Service to handle automatic SMS campaign execution.
    Triggers SMS based on events or scheduled times.
    """

    @classmethod
    def trigger_event_campaigns(cls, tenant, event_type: str, context: dict, user=None, payment=None):
        """
        Trigger all active campaigns for a specific event.
        
        Args:
            tenant: Tenant model instance
            event_type: Event type matching AutoSMSCampaign.TRIGGER_TYPE_CHOICES
            context: Dict with variables for message template
            user: Optional User model instance
            payment: Optional Payment model instance
        """
        from .models import AutoSMSCampaign, AutoSMSLog
        from .nextsms import TenantNextSMSAPI
        
        # Check if tenant has auto SMS feature enabled
        if not tenant.subscription_plan or not tenant.subscription_plan.auto_sms_campaigns:
            return
        
        # Check if tenant has SMS credentials
        if not tenant.nextsms_username or not tenant.nextsms_password:
            return
        
        # Get active campaigns for this event type
        campaigns = AutoSMSCampaign.objects.filter(
            tenant=tenant,
            trigger_type=event_type,
            status="active",
            is_active=True
        )
        
        if not campaigns.exists():
            return
        
        sms_api = TenantNextSMSAPI(tenant)
        
        for campaign in campaigns:
            try:
                # Render message with context
                message = campaign.render_message(context)
                
                # Get recipient phone
                phone = context.get("phone") or context.get("phone_number")
                if not phone and user:
                    phone = user.phone_number
                
                if not phone:
                    continue
                
                # Send SMS
                result = sms_api.send_sms(
                    phone, message,
                    reference=f"AUTO-{campaign.id}"
                )
                
                success = result.get("success", False)
                
                # Log the execution
                AutoSMSLog.objects.create(
                    campaign=campaign,
                    trigger_event=event_type,
                    recipient_phone=phone,
                    message_sent=message,
                    success=success,
                    error_message="" if success else result.get("error", "Unknown error"),
                    related_user=user,
                    related_payment=payment
                )
                
                # Update campaign stats
                if success:
                    campaign.total_sent += 1
                else:
                    campaign.total_failed += 1
                campaign.last_triggered_at = timezone.now()
                campaign.save(update_fields=["total_sent", "total_failed", "last_triggered_at"])
                
            except Exception as e:
                logger.error("Auto SMS campaign error: %s - %s", campaign.name, str(e))
                AutoSMSLog.objects.create(
                    campaign=campaign,
                    trigger_event=event_type,
                    recipient_phone=phone if 'phone' in dir() else "",
                    message_sent="",
                    success=False,
                    error_message=str(e),
                    related_user=user,
                    related_payment=payment
                )

    @classmethod
    def process_scheduled_campaigns(cls):
        """
        Process all scheduled/recurring campaigns that are due.
        Called by a periodic task (e.g., every minute via cron).
        """
        from .models import AutoSMSCampaign, AutoSMSLog
        from .nextsms import TenantNextSMSAPI
        
        now = timezone.now()
        
        # Get campaigns that are due
        due_campaigns = AutoSMSCampaign.objects.filter(
            trigger_type__in=["scheduled", "recurring_daily", "recurring_weekly", "recurring_monthly"],
            status="active",
            is_active=True,
            next_run_at__lte=now
        ).select_related("tenant", "tenant__subscription_plan")
        
        results = {"processed": 0, "sent": 0, "failed": 0}
        
        for campaign in due_campaigns:
            tenant = campaign.tenant
            
            # Check feature availability
            if not tenant.subscription_plan or not tenant.subscription_plan.auto_sms_campaigns:
                continue
            
            # Check SMS credentials
            if not tenant.nextsms_username or not tenant.nextsms_password:
                continue
            
            results["processed"] += 1
            
            # Get recipients
            recipients = campaign.get_recipients_for_scheduled()
            
            if not recipients.exists():
                # Still calculate next run
                campaign.calculate_next_run()
                continue
            
            sms_api = TenantNextSMSAPI(tenant)
            
            for user in recipients:
                try:
                    context = {
                        "name": user.name or "Customer",
                        "phone": user.phone_number,
                        "expiry_date": user.paid_until.strftime("%Y-%m-%d %H:%M") if user.paid_until else "",
                    }
                    
                    message = campaign.render_message(context)
                    
                    result = sms_api.send_sms(
                        user.phone_number, message,
                        reference=f"SCHEDULED-{campaign.id}"
                    )
                    
                    success = result.get("success", False)
                    
                    AutoSMSLog.objects.create(
                        campaign=campaign,
                        trigger_event=campaign.trigger_type,
                        recipient_phone=user.phone_number,
                        message_sent=message,
                        success=success,
                        error_message="" if success else result.get("error", ""),
                        related_user=user
                    )
                    
                    if success:
                        campaign.total_sent += 1
                        results["sent"] += 1
                    else:
                        campaign.total_failed += 1
                        results["failed"] += 1
                
                except Exception as e:
                    logger.error("Scheduled SMS error: %s", str(e))
                    campaign.total_failed += 1
                    results["failed"] += 1
            
            # Update campaign and calculate next run
            campaign.last_triggered_at = now
            campaign.save(update_fields=["total_sent", "total_failed", "last_triggered_at"])
            campaign.calculate_next_run()
        
        return results

    @classmethod
    def check_expiring_users(cls):
        """
        Check for users whose access is expiring soon and trigger auto SMS.
        Called periodically (e.g., every hour).
        """
        from .models import AutoSMSCampaign, User
        
        now = timezone.now()
        
        # Get tenants with active expiring campaigns
        expiring_campaigns = AutoSMSCampaign.objects.filter(
            trigger_type="access_expiring",
            status="active",
            is_active=True
        ).select_related("tenant", "tenant__subscription_plan")
        
        results = {"users_notified": 0, "campaigns_processed": 0}
        
        for campaign in expiring_campaigns:
            tenant = campaign.tenant
            
            # Check feature availability
            if not tenant.subscription_plan or not tenant.subscription_plan.auto_sms_campaigns:
                continue
            
            results["campaigns_processed"] += 1
            
            # Calculate expiry window
            hours = campaign.hours_before_expiry or 24
            expiry_start = now
            expiry_end = now + timedelta(hours=hours)
            
            # Find users expiring within the window who haven't been notified
            users = User.objects.filter(
                tenant=tenant,
                is_active=True,
                paid_until__gte=expiry_start,
                paid_until__lte=expiry_end,
                expiry_notification_sent=False
            )
            
            for user in users:
                context = {
                    "name": user.name or "Customer",
                    "phone": user.phone_number,
                    "expiry_date": user.paid_until.strftime("%Y-%m-%d %H:%M") if user.paid_until else "",
                }
                
                cls.trigger_event_campaigns(
                    tenant, "access_expiring", context, user=user
                )
                
                # Mark as notified
                user.expiry_notification_sent = True
                user.save(update_fields=["expiry_notification_sent"])
                results["users_notified"] += 1
        
        return results


# =============================================================================
# EVENT TRIGGER FUNCTIONS (call these from payment/voucher flows)
# =============================================================================

def trigger_new_user_sms(user):
    """Trigger auto SMS for new user registration"""
    if not user.tenant:
        return
    
    context = {
        "name": user.name or "Customer",
        "phone": user.phone_number,
    }
    
    AutoSMSService.trigger_event_campaigns(
        user.tenant, "new_user", context, user=user
    )


def trigger_payment_success_sms(payment):
    """Trigger auto SMS for successful payment"""
    if not payment.tenant or not payment.user:
        return
    
    context = {
        "name": payment.user.name or "Customer",
        "phone": payment.phone_number,
        "amount": f"{payment.amount:,.0f}",
        "bundle": payment.bundle.name if payment.bundle else "WiFi Access",
        "expiry_date": payment.user.paid_until.strftime("%Y-%m-%d %H:%M") if payment.user.paid_until else "",
    }
    
    AutoSMSService.trigger_event_campaigns(
        payment.tenant, "payment_success", context, user=payment.user, payment=payment
    )


def trigger_payment_failed_sms(payment, reason: str = ""):
    """Trigger auto SMS for failed payment"""
    if not payment.tenant or not payment.user:
        return
    
    context = {
        "name": payment.user.name or "Customer",
        "phone": payment.phone_number,
        "amount": f"{payment.amount:,.0f}",
    }
    
    AutoSMSService.trigger_event_campaigns(
        payment.tenant, "payment_failed", context, user=payment.user, payment=payment
    )


def trigger_access_expired_sms(user):
    """Trigger auto SMS when user access expires"""
    if not user.tenant:
        return
    
    context = {
        "name": user.name or "Customer",
        "phone": user.phone_number,
        "expiry_date": user.paid_until.strftime("%Y-%m-%d %H:%M") if user.paid_until else "",
    }
    
    AutoSMSService.trigger_event_campaigns(
        user.tenant, "access_expired", context, user=user
    )


def trigger_voucher_redeemed_sms(voucher, user):
    """Trigger auto SMS when voucher is redeemed"""
    if not voucher.tenant or not user:
        return
    
    context = {
        "name": user.name or "Customer",
        "phone": user.phone_number,
        "bundle": f"{voucher.duration_hours} hours",
        "expiry_date": user.paid_until.strftime("%Y-%m-%d %H:%M") if user.paid_until else "",
    }
    
    AutoSMSService.trigger_event_campaigns(
        voucher.tenant, "voucher_redeemed", context, user=user
    )
