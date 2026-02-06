"""
Snippe Payment API Integration
Handles Mobile Money, Card, and QR Code payments for Tanzania

API Docs: https://api.snippe.sh
Base URL: https://api.snippe.sh/v1
Auth: Bearer token via API key
"""

import hmac
import hashlib
import uuid
import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class SnippeAPI:
    """
    Snippe Payment API client
    Supports mobile money (USSD push), card, and dynamic QR payments
    """

    def __init__(self):
        self.api_key = getattr(settings, "SNIPPE_API_KEY", "")
        self.webhook_signing_key = getattr(settings, "SNIPPE_WEBHOOK_SIGNING_KEY", "")
        self.base_url = getattr(
            settings, "SNIPPE_BASE_URL", "https://api.snippe.sh"
        ).rstrip("/")
        self.webhook_url = getattr(settings, "SNIPPE_WEBHOOK_URL", "")

    def _headers(self, idempotency_key=None):
        """Build request headers with auth and optional idempotency key"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    # =========================================================================
    # PAYMENT CREATION
    # =========================================================================

    def initiate_payment(
        self,
        phone_number,
        amount,
        order_reference,
        customer_name="WiFi Customer",
        customer_email="customer@kitonga.co.tz",
        metadata=None,
    ):
        """
        Initiate a mobile money USSD push payment.
        Customer receives a USSD prompt on their phone.

        Args:
            phone_number: Mobile phone number (format: 255XXXXXXXXX)
            amount: Payment amount in TZS (integer)
            order_reference: Unique order reference for this payment
            customer_name: Customer display name
            customer_email: Customer email
            metadata: Optional dict of key-value pairs

        Returns:
            dict: {success, message, reference, status, data}
        """
        if not self.api_key:
            return {
                "success": False,
                "message": "Snippe API key not configured",
            }

        # Format phone number (ensure it starts with 255)
        phone_number = self._normalize_phone(phone_number)

        # Split customer name
        name_parts = customer_name.split(" ", 1)
        firstname = name_parts[0]
        lastname = name_parts[1] if len(name_parts) > 1 else firstname

        # Use order_reference as idempotency key to prevent duplicates
        idempotency_key = order_reference or str(uuid.uuid4())

        payload = {
            "payment_type": "mobile",
            "details": {
                "amount": int(amount),
                "currency": "TZS",
            },
            "phone_number": phone_number,
            "customer": {
                "firstname": firstname,
                "lastname": lastname,
                "email": customer_email,
            },
            "webhook_url": self.webhook_url,
            "metadata": {
                "order_reference": order_reference,
                **(metadata or {}),
            },
        }

        try:
            url = f"{self.base_url}/v1/payments"
            response = requests.post(
                url,
                json=payload,
                headers=self._headers(idempotency_key=idempotency_key),
                timeout=30,
            )

            result = response.json()

            if response.status_code in (200, 201) and result.get("status") == "success":
                data = result.get("data", {})
                return {
                    "success": True,
                    "message": "Payment request sent to your phone",
                    "reference": data.get("reference", ""),
                    "order_reference": order_reference,
                    "status": data.get("status", "pending"),
                    "channel": "snippe_mobile",
                    "data": data,
                }
            else:
                error_msg = result.get("message", "Payment initiation failed")
                logger.error(
                    f"Snippe payment failed: {response.status_code} - {error_msg}"
                )
                return {"success": False, "message": error_msg}

        except requests.exceptions.RequestException as e:
            logger.error(f"Snippe payment request failed: {e}")
            return {
                "success": False,
                "message": "Failed to initiate payment. Please try again.",
            }

    def create_card_payment(
        self,
        amount,
        order_reference,
        phone_number,
        customer_name="WiFi Customer",
        customer_email="customer@kitonga.co.tz",
        redirect_url="",
        cancel_url="",
        metadata=None,
    ):
        """
        Create a card payment. Returns a payment_url to redirect the customer.

        Returns:
            dict: {success, payment_url, reference, status, data}
        """
        if not self.api_key:
            return {"success": False, "message": "Snippe API key not configured"}

        phone_number = self._normalize_phone(phone_number)
        name_parts = customer_name.split(" ", 1)
        firstname = name_parts[0]
        lastname = name_parts[1] if len(name_parts) > 1 else firstname

        idempotency_key = order_reference or str(uuid.uuid4())

        payload = {
            "payment_type": "card",
            "details": {
                "amount": int(amount),
                "currency": "TZS",
                "redirect_url": redirect_url,
                "cancel_url": cancel_url,
            },
            "phone_number": phone_number,
            "customer": {
                "firstname": firstname,
                "lastname": lastname,
                "email": customer_email,
                "address": "Tanzania",
                "city": "Dar es Salaam",
                "state": "DSM",
                "postcode": "14101",
                "country": "TZ",
            },
            "webhook_url": self.webhook_url,
            "metadata": {
                "order_reference": order_reference,
                **(metadata or {}),
            },
        }

        try:
            url = f"{self.base_url}/v1/payments"
            response = requests.post(
                url,
                json=payload,
                headers=self._headers(idempotency_key=idempotency_key),
                timeout=30,
            )

            result = response.json()

            if response.status_code in (200, 201) and result.get("status") == "success":
                data = result.get("data", {})
                return {
                    "success": True,
                    "message": "Redirect customer to payment page",
                    "payment_url": data.get("payment_url", ""),
                    "reference": data.get("reference", ""),
                    "order_reference": order_reference,
                    "status": data.get("status", "pending"),
                    "channel": "snippe_card",
                    "data": data,
                }
            else:
                error_msg = result.get("message", "Card payment creation failed")
                logger.error(f"Snippe card payment failed: {error_msg}")
                return {"success": False, "message": error_msg}

        except requests.exceptions.RequestException as e:
            logger.error(f"Snippe card payment request failed: {e}")
            return {"success": False, "message": "Failed to create card payment."}

    # =========================================================================
    # PAYMENT QUERIES
    # =========================================================================

    def query_payment_status(self, reference):
        """
        Get payment status by Snippe reference ID.

        Args:
            reference: Snippe payment reference (UUID)

        Returns:
            dict: {success, status, data}
        """
        if not self.api_key:
            return {"success": False, "message": "Snippe API key not configured"}

        try:
            url = f"{self.base_url}/v1/payments/{reference}"
            response = requests.get(url, headers=self._headers(), timeout=15)

            result = response.json()

            if response.status_code == 200 and result.get("status") == "success":
                data = result.get("data", {})
                return {
                    "success": True,
                    "status": data.get("status", "unknown"),
                    "data": data,
                }
            else:
                return {
                    "success": False,
                    "message": result.get("message", "Payment not found"),
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Snippe status query failed: {e}")
            return {"success": False, "message": "Failed to query payment status"}

    def list_payments(self, limit=20, offset=0):
        """List all payments for the account"""
        if not self.api_key:
            return {"success": False, "message": "Snippe API key not configured"}

        try:
            url = f"{self.base_url}/v1/payments?limit={limit}&offset={offset}"
            response = requests.get(url, headers=self._headers(), timeout=15)
            result = response.json()

            if response.status_code == 200 and result.get("status") == "success":
                return {"success": True, "data": result.get("data", {})}
            else:
                return {
                    "success": False,
                    "message": result.get("message", "Failed to list payments"),
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Snippe list payments failed: {e}")
            return {"success": False, "message": "Failed to list payments"}

    def get_balance(self):
        """Get Snippe account balance"""
        if not self.api_key:
            return {"success": False, "message": "Snippe API key not configured"}

        try:
            url = f"{self.base_url}/v1/payments/balance"
            response = requests.get(url, headers=self._headers(), timeout=15)
            result = response.json()

            if response.status_code == 200 and result.get("status") == "success":
                data = result.get("data", {})
                return {
                    "success": True,
                    "balance": data.get("balance", {}).get("value", 0),
                    "available": data.get("available", {}).get("value", 0),
                    "currency": data.get("balance", {}).get("currency", "TZS"),
                    "data": data,
                }
            else:
                return {
                    "success": False,
                    "message": result.get("message", "Failed to get balance"),
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Snippe balance query failed: {e}")
            return {"success": False, "message": "Failed to get balance"}

    # =========================================================================
    # WEBHOOK VERIFICATION
    # =========================================================================

    def verify_webhook_signature(self, payload_body, signature, timestamp):
        """
        Verify Snippe webhook HMAC-SHA256 signature.

        Args:
            payload_body: Raw request body (bytes)
            signature: Value from X-Webhook-Signature header
            timestamp: Value from X-Webhook-Timestamp header

        Returns:
            bool: True if signature is valid
        """
        if not self.webhook_signing_key:
            logger.warning("Snippe webhook signing key not configured, skipping verification")
            return True  # Skip verification if no key configured

        try:
            # Reconstruct the signed message: timestamp.body
            message = f"{timestamp}.{payload_body}".encode("utf-8")
            expected_signature = hmac.new(
                self.webhook_signing_key.encode("utf-8"),
                message,
                hashlib.sha256,
            ).hexdigest()

            return hmac.compare_digest(expected_signature, signature)
        except Exception as e:
            logger.error(f"Snippe webhook signature verification failed: {e}")
            return False

    @staticmethod
    def parse_webhook_data(data):
        """
        Parse Snippe webhook payload into a normalized dict.

        Snippe webhook format:
        {
            "id": "evt_...",
            "type": "payment.completed" | "payment.failed",
            "data": {
                "reference": "uuid",
                "external_reference": "...",
                "status": "completed" | "failed",
                "amount": {"value": 500, "currency": "TZS"},
                "channel": {"type": "mobile_money", "provider": "airtel"},
                "customer": {"phone": "+255...", "name": "...", "email": "..."},
                "metadata": {"order_reference": "KITONGA-...", ...},
                "failure_reason": "..." (only for failed)
            }
        }

        Returns:
            dict with normalized fields
        """
        event_type = data.get("type", "")
        event_data = data.get("data", {})

        amount_obj = event_data.get("amount", {})
        channel_obj = event_data.get("channel", {})
        customer_obj = event_data.get("customer", {})
        metadata = event_data.get("metadata", {})

        # Get the order_reference from metadata (what we set when creating payment)
        order_reference = (
            metadata.get("order_reference")
            or event_data.get("external_reference")
            or event_data.get("reference")
            or ""
        )

        return {
            "event_id": data.get("id", ""),
            "event_type": event_type,
            "reference": event_data.get("reference", ""),
            "external_reference": event_data.get("external_reference", ""),
            "order_reference": order_reference,
            "status": event_data.get("status", ""),
            "amount": amount_obj.get("value"),
            "currency": amount_obj.get("currency", "TZS"),
            "channel_type": channel_obj.get("type", ""),
            "channel_provider": channel_obj.get("provider", ""),
            "customer_phone": customer_obj.get("phone", ""),
            "customer_name": customer_obj.get("name", ""),
            "customer_email": customer_obj.get("email", ""),
            "metadata": metadata,
            "failure_reason": event_data.get("failure_reason", ""),
            "completed_at": event_data.get("completed_at", ""),
            "settlement": event_data.get("settlement", {}),
        }

    # =========================================================================
    # HELPERS
    # =========================================================================

    @staticmethod
    def _normalize_phone(phone_number):
        """Ensure phone number is in 255XXXXXXXXX format"""
        phone_number = str(phone_number).strip()
        if phone_number.startswith("+"):
            phone_number = phone_number[1:]
        if phone_number.startswith("0"):
            phone_number = "255" + phone_number[1:]
        elif not phone_number.startswith("255"):
            phone_number = "255" + phone_number
        return phone_number
