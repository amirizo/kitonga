"""
NEXTSMS API Integration
Handles SMS notifications for Kitonga Wi-Fi system
"""
import requests
import base64
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class NextSMSAPI:
    """
    NEXTSMS API client for sending SMS notifications
    Accepts optional credentials to support tenant-specific SMS accounts.
    """

    def __init__(self, username=None, password=None, sender_id=None, base_url=None):
        # Use provided credentials or fall back to global settings
        self.username = username or settings.NEXTSMS_USERNAME
        self.password = password or settings.NEXTSMS_PASSWORD
        self.sender_id = sender_id or settings.NEXTSMS_SENDER_ID
        self.base_url = base_url or settings.NEXTSMS_BASE_URL

        # Create Basic Auth token
        credentials = f"{self.username}:{self.password}"
        self.auth_token = base64.b64encode(credentials.encode()).decode()

    def send_sms(self, phone_number, message, reference=None):
        """
        Send SMS to a single recipient

        Args:
            phone_number: Recipient phone number (format: 255XXXXXXXXX)
            message: SMS message text
            reference: Optional reference ID for tracking

        Returns:
            dict: Response with success status and message
        """
        url = f'{self.base_url}/api/sms/v1/text/single'

        # Format phone number (ensure it starts with 255)
        if phone_number.startswith('0'):
            phone_number = '255' + phone_number[1:]
        elif not phone_number.startswith('255'):
            phone_number = '255' + phone_number

        headers = {
            'Authorization': f'Basic {self.auth_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        payload = {
            'from': self.sender_id,
            'to': phone_number,
            'text': message,
            'reference': reference or f'KITONGA-{phone_number}'
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()

            result = response.json()

            logger.info(f'SMS sent successfully to {phone_number}')
            return {
                'success': True,
                'message': 'SMS sent successfully',
                'data': result
            }

        except requests.exceptions.RequestException as e:
            logger.error(f'Failed to send SMS to {phone_number}: {str(e)}')
            if hasattr(e, 'response') and getattr(e, 'response') is not None and hasattr(e.response, 'text'):
                logger.error(f'Response: {e.response.text}')
            return {
                'success': False,
                'message': 'Failed to send SMS',
            }

    def send_payment_confirmation(self, phone_number, amount, duration_hours):
        """Send payment confirmation SMS"""
        duration_days = duration_hours // 24
        duration_text = f"{duration_days} day{'s' if duration_days > 1 else ''}"

        message = (
            f"Payment confirmed! TSh {amount} received. "
            f"Your Kitonga Wi-Fi access is now active for {duration_text}. "
            f"Thank you!"
        )

        return self.send_sms(phone_number, message, f'PAYMENT-{phone_number}')

    def send_payment_failed_notification(self, phone_number, amount):
        """Send payment failed notification SMS"""
        message = (
            f"Kitonga Wi-Fi: Payment of TSh {amount} failed. "
            f"Please try again or contact support. "
        )
        return self.send_sms(phone_number, message, f'PAYMENT-FAILED-{phone_number}')

    def send_expiry_warning(self, phone_number, hours_remaining):
        """Send access expiry warning SMS"""
        message = (
            f"Kitonga Wi-Fi: Your access will expire in {hours_remaining} hours. "
            f"Renew now to stay connected. Reply RENEW or visit the portal."
        )

        return self.send_sms(phone_number, message, f'EXPIRY-{phone_number}')

    def send_voucher_confirmation(self, phone_number, voucher_code, duration_hours):
        """Send voucher redemption confirmation SMS"""
        duration_days = duration_hours // 24
        duration_text = f"{duration_days} day{'s' if duration_days > 1 else ''}"

        message = (
            f"Voucher {voucher_code} redeemed successfully! "
            f"Your Kitonga Wi-Fi access is now active for {duration_text}. "
            f"Enjoy!"
        )

        return self.send_sms(phone_number, message, f'VOUCHER-{phone_number}')

    def send_access_expired(self, phone_number):
        """Send access expired notification SMS"""
        message = (
            f"Kitonga Wi-Fi: Your access has expired. "
            f"Purchase a new package to continue enjoying our service. "
            f"Visit the portal or dial *150*00#"
        )

        return self.send_sms(phone_number, message, f'EXPIRED-{phone_number}')

    def send_voucher_generation_notification(self, admin_phone_number, vouchers, language='en'):
        """
        Send voucher generation notification to admin with bilingual support

        Args:
            admin_phone_number: Admin's phone number
            vouchers: List of generated voucher objects
            language: Language preference ('en' for English, 'sw' for Swahili)

        Returns:
            dict: Response with success status
        """
        quantity = len(vouchers)
        duration_hours = vouchers[0].duration_hours if vouchers else 24
        duration_days = duration_hours // 24

        # Get first few voucher codes to include in SMS
        voucher_codes = [voucher.code for voucher in vouchers[:3]]
        batch_id = vouchers[0].batch_id if vouchers else 'UNKNOWN'

        if language == 'sw':  # Swahili
            if duration_days == 1:
                duration_text = "siku 1"
            else:
                duration_text = f"siku {duration_days}"

            message = (
                f"KITONGA ADMIN: Vouchers {quantity} vimeundwa kikamilifu! "
                f"Kila voucher ina muongo wa {duration_text}. "
                f"Batch: {batch_id}. "
            )

            if len(voucher_codes) <= 3:
                message += f"Codes: {', '.join(voucher_codes)}"
            else:
                message += f"Codes za kwanza: {', '.join(voucher_codes[:2])}, n.k."

        else:  # English (default)
            duration_text = f"{duration_days} day{'s' if duration_days > 1 else ''}"

            message = (
                f"KITONGA ADMIN: {quantity} vouchers generated successfully! "
                f"Each voucher grants {duration_text} access. "
                f"Batch: {batch_id}. "
            )

            if len(voucher_codes) <= 3:
                message += f"Codes: {', '.join(voucher_codes)}"
            else:
                message += f"First codes: {', '.join(voucher_codes[:2])}, etc."

        return self.send_sms(admin_phone_number, message, f'ADMIN-VOUCHERS-{batch_id}')

    def send_voucher_summary_sms(self, admin_phone_number, vouchers, language='en'):
        """
        Send detailed voucher summary via SMS (split into multiple messages if needed)

        Args:
            admin_phone_number: Admin's phone number
            vouchers: List of generated voucher objects
            language: Language preference ('en' for English, 'sw' for Swahili)

        Returns:
            dict: Response with success status
        """
        quantity = len(vouchers)
        batch_id = vouchers[0].batch_id if vouchers else 'UNKNOWN'

        # Split vouchers into chunks for multiple SMS
        chunk_size = 3  # 3 voucher codes per SMS
        voucher_chunks = [vouchers[i:i + chunk_size] for i in range(0, len(vouchers), chunk_size)]

        results = []

        for i, chunk in enumerate(voucher_chunks):
            voucher_codes = [voucher.code for voucher in chunk]

            if language == 'sw':  # Swahili
                if i == 0:
                    # First message with summary
                    message = (
                        f"KITONGA VOUCHERS ({i+1}/{len(voucher_chunks)}): "
                        f"Batch {batch_id} - Jumla: {quantity}. "
                        f"Codes: {', '.join(voucher_codes)}"
                    )
                else:
                    # Subsequent messages
                    message = (
                        f"KITONGA VOUCHERS ({i+1}/{len(voucher_chunks)}): "
                        f"Codes: {', '.join(voucher_codes)}"
                    )
            else:  # English
                if i == 0:
                    # First message with summary
                    message = (
                        f"KITONGA VOUCHERS ({i+1}/{len(voucher_chunks)}): "
                        f"Batch {batch_id} - Total: {quantity}. "
                        f"Codes: {', '.join(voucher_codes)}"
                    )
                else:
                    # Subsequent messages
                    message = (
                        f"KITONGA VOUCHERS ({i+1}/{len(voucher_chunks)}): "
                        f"Codes: {', '.join(voucher_codes)}"
                    )

            result = self.send_sms(
                admin_phone_number,
                message,
                f'VOUCHER-BATCH-{batch_id}-{i+1}'
            )
            results.append(result)

        # Return success if all messages were sent successfully
        all_success = all(result['success'] for result in results)
        return {
            'success': all_success,
            'message': f'Sent {len(results)} SMS messages',
            'details': results
        }

    def send_payment_confirmation_with_auth_success(self, phone_number, amount, duration_hours):
        """
        Send payment confirmation with successful MikroTik authentication
        """
        message = (
            f"✅ KITONGA WiFi: Payment successful! TSh {amount:,.0f} received. "
            f"You're now connected with {duration_hours}h internet access. "
            f"Your device is automatically authenticated. Enjoy browsing!"
        )

        return self.send_sms(
            phone_number=phone_number,
            message=message,
            reference=f'payment_auth_success_{phone_number}'
        )

    def send_payment_confirmation_with_reconnect_instructions(self, phone_number, amount, duration_hours):
        """
        Send payment confirmation with instructions to reconnect for authentication
        """
        message = (
            f"✅ KITONGA WiFi: Payment successful! TSh {amount:,.0f} received. "
            f"Access granted for {duration_hours}h. "
            f"Please DISCONNECT and RECONNECT to WiFi to activate internet access. "
            f"Or restart your WiFi connection."
        )

        return self.send_sms(
            phone_number=phone_number,
            message=message,
            reference=f'payment_reconnect_{phone_number}'
        )
