"""
Snippe Payment API Integration (https://api.snippe.sh)
Handles Mobile Money, Card, and Dynamic QR payments for Tanzania.

Supports:
  - Mobile Money: Airtel Money, M-Pesa, Mixx by Yas, Halotel
  - Card Payments: Visa, Mastercard, local debit cards
  - Dynamic QR: QR code scanned with mobile money app
  - Disbursements: Mobile money payouts
  - Payment Sessions: Hosted checkout pages
"""

import hmac
import hashlib
import requests
import logging
import uuid

from django.conf import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SNIPPE_BASE_URL = "https://api.snippe.sh/v1"

PAYMENT_STATUS_PENDING = "pending"
PAYMENT_STATUS_COMPLETED = "completed"
PAYMENT_STATUS_FAILED = "failed"
PAYMENT_STATUS_VOIDED = "voided"
PAYMENT_STATUS_EXPIRED = "expired"

PAYOUT_STATUS_PENDING = "pending"
PAYOUT_STATUS_COMPLETED = "completed"
PAYOUT_STATUS_FAILED = "failed"
PAYOUT_STATUS_REVERSED = "reversed"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_phone_number(phone_number: str) -> str:
    """Normalize phone number to 255XXXXXXXXX format."""
    phone = str(phone_number).strip()
    if phone.startswith("+"):
        phone = phone[1:]
    if phone.startswith("0"):
        phone = "255" + phone[1:]
    elif not phone.startswith("255"):
        phone = "255" + phone
    return phone


def verify_webhook_signature(
    payload: str, signature: str, secret: str, timestamp: str = ""
) -> bool:
    """
    Verify Snippe webhook HMAC-SHA256 signature.

    Snippe signs ``{timestamp}.{payload}`` when the X-Webhook-Timestamp
    header is present.  Falls back to signing raw payload only.

    Args:
        payload:   Raw request body (string / bytes)
        signature: Value of X-Webhook-Signature header
        secret:    Your webhook signing secret
        timestamp: Value of X-Webhook-Timestamp header (optional)
    """
    import logging

    logger = logging.getLogger(__name__)

    if isinstance(payload, str):
        payload = payload.encode()

    # Strip common prefixes from signature (e.g. "v1=<hex>", "sha256=<hex>")
    clean_sig = signature
    for prefix in ("v1=", "sha256="):
        if clean_sig.startswith(prefix):
            clean_sig = clean_sig[len(prefix):]
            break

    # Try multiple signing strategies (Snippe may include timestamp)
    candidates = []

    # Strategy 1: timestamp.payload (like Stripe whsec_ pattern)
    if timestamp:
        candidates.append(f"{timestamp}.".encode() + payload)

    # Strategy 2: raw payload only
    candidates.append(payload)

    secret_bytes = secret.encode()

    for candidate in candidates:
        expected = hmac.new(secret_bytes, candidate, hashlib.sha256).hexdigest()
        if hmac.compare_digest(clean_sig, expected):
            return True

    # Debug logging for failed verification
    logger.warning(
        f"Snippe signature mismatch. "
        f"Signature header (first 16 chars): {signature[:16]}..., "
        f"Timestamp: {timestamp}, "
        f"Payload length: {len(payload)}, "
        f"Secret (first 10 chars): {secret[:10]}..."
    )
    return False


# ---------------------------------------------------------------------------
# SnippeAPI Client
# ---------------------------------------------------------------------------


class SnippeAPI:
    """
    Snippe API client.

    Can be constructed with explicit credentials (for per-tenant usage)
    or will fall back to Django settings.
    """

    def __init__(self, api_key: str | None = None, webhook_secret: str | None = None):
        self.api_key = api_key or getattr(settings, "SNIPPE_API_KEY", "")
        self.webhook_secret = webhook_secret or getattr(
            settings, "SNIPPE_WEBHOOK_SECRET", ""
        )
        self.base_url = getattr(settings, "SNIPPE_BASE_URL", SNIPPE_BASE_URL)
        self.timeout = 30  # seconds

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self, idempotency_key: str | None = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def _request(
        self,
        method: str,
        path: str,
        json_data: dict | None = None,
        params: dict | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        """
        Generic HTTP request wrapper.

        Returns a dict with at least ``success`` (bool).
        On success the Snippe ``data`` payload is included under ``data``.
        """
        url = f"{self.base_url}{path}"
        headers = self._headers(idempotency_key)

        try:
            response = requests.request(
                method,
                url,
                json=json_data,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )

            body = response.json()

            if response.status_code in (200, 201):
                return {
                    "success": True,
                    "data": body.get("data", body),
                    "raw": body,
                }

            # Error response from Snippe
            logger.error(
                "Snippe API error %s %s → %s %s: %s",
                method,
                path,
                response.status_code,
                body.get("error_code", ""),
                body.get("message", ""),
            )
            return {
                "success": False,
                "status_code": response.status_code,
                "error_code": body.get("error_code", "unknown"),
                "message": body.get("message", "Unknown error"),
                "raw": body,
            }

        except requests.exceptions.Timeout:
            logger.error("Snippe API timeout: %s %s", method, path)
            return {
                "success": False,
                "message": "Request timed out. Please try again.",
            }
        except requests.exceptions.ConnectionError:
            logger.error("Snippe API connection error: %s %s", method, path)
            return {
                "success": False,
                "message": "Could not connect to payment provider.",
            }
        except requests.exceptions.RequestException as exc:
            logger.error("Snippe API request error: %s", exc)
            return {"success": False, "message": str(exc)}
        except ValueError:
            logger.error(
                "Snippe API returned non-JSON response for %s %s", method, path
            )
            return {
                "success": False,
                "message": "Invalid response from payment provider.",
            }

    # ======================================================================
    # PAYMENTS — Collection
    # ======================================================================

    def create_mobile_payment(
        self,
        phone_number: str,
        amount: int,
        *,
        currency: str = "TZS",
        firstname: str = "WiFi",
        lastname: str = "User",
        email: str = "",
        webhook_url: str = "",
        metadata: dict | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        """
        Create a mobile money payment (USSD push).

        Args:
            phone_number: Customer phone (255XXXXXXXXX)
            amount:       Amount in smallest currency unit
            currency:     Currency code (default TZS)
            firstname:    Customer first name
            lastname:     Customer last name
            email:        Customer email
            webhook_url:  URL for webhook notifications
            metadata:     Custom key-value data
            idempotency_key: Prevent duplicate payments
        """
        phone = _format_phone_number(phone_number)

        if not idempotency_key:
            idempotency_key = f"mob-{phone}-{amount}-{uuid.uuid4().hex[:8]}"

        payload = {
            "payment_type": "mobile",
            "details": {"amount": int(amount), "currency": currency},
            "phone_number": phone,
            "customer": {
                "firstname": firstname,
                "lastname": lastname,
                "email": email or f"{phone}@wifi.local",
            },
        }
        if webhook_url:
            payload["webhook_url"] = webhook_url
        if metadata:
            payload["metadata"] = metadata

        logger.info(
            "Snippe: Creating mobile payment phone=%s amount=%s %s",
            phone,
            amount,
            currency,
        )
        result = self._request(
            "POST", "/payments", json_data=payload, idempotency_key=idempotency_key
        )

        if result["success"]:
            data = result["data"]
            return {
                "success": True,
                "message": "Payment request sent to your phone",
                "reference": data.get("reference"),
                "status": data.get("status"),
                "expires_at": data.get("expires_at"),
                "data": data,
            }
        return result

    def create_card_payment(
        self,
        amount: int,
        redirect_url: str,
        cancel_url: str,
        *,
        phone_number: str = "",
        currency: str = "TZS",
        firstname: str = "WiFi",
        lastname: str = "User",
        email: str = "",
        address: str = "",
        city: str = "",
        state: str = "DSM",
        postcode: str = "14101",
        country: str = "TZ",
        webhook_url: str = "",
        metadata: dict | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        """Create a card payment. Returns ``payment_url`` for redirect."""
        if not idempotency_key:
            idempotency_key = f"card-{amount}-{uuid.uuid4().hex[:8]}"

        payload = {
            "payment_type": "card",
            "details": {
                "amount": int(amount),
                "currency": currency,
                "redirect_url": redirect_url,
                "cancel_url": cancel_url,
            },
            "customer": {
                "firstname": firstname,
                "lastname": lastname,
                "email": email or "noreply@wifi.local",
                "address": address,
                "city": city,
                "state": state,
                "postcode": postcode,
                "country": country,
            },
        }
        if phone_number:
            payload["phone_number"] = _format_phone_number(phone_number)
        if webhook_url:
            payload["webhook_url"] = webhook_url
        if metadata:
            payload["metadata"] = metadata

        logger.info("Snippe: Creating card payment amount=%s %s", amount, currency)
        result = self._request(
            "POST", "/payments", json_data=payload, idempotency_key=idempotency_key
        )

        if result["success"]:
            data = result["data"]
            return {
                "success": True,
                "message": "Redirect customer to payment page",
                "reference": data.get("reference"),
                "payment_url": data.get("payment_url"),
                "payment_token": data.get("payment_token"),
                "payment_qr_code": data.get("payment_qr_code"),
                "status": data.get("status"),
                "expires_at": data.get("expires_at"),
                "data": data,
            }
        return result

    def create_qr_payment(
        self,
        amount: int,
        *,
        currency: str = "TZS",
        redirect_url: str = "",
        cancel_url: str = "",
        phone_number: str = "",
        firstname: str = "WiFi",
        lastname: str = "User",
        email: str = "",
        webhook_url: str = "",
        metadata: dict | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        """Create a Dynamic QR payment. Returns ``payment_qr_code``."""
        if not idempotency_key:
            idempotency_key = f"qr-{amount}-{uuid.uuid4().hex[:8]}"

        details = {"amount": int(amount), "currency": currency}
        if redirect_url:
            details["redirect_url"] = redirect_url
        if cancel_url:
            details["cancel_url"] = cancel_url

        payload = {
            "payment_type": "dynamic-qr",
            "details": details,
            "customer": {
                "firstname": firstname,
                "lastname": lastname,
                "email": email or "noreply@wifi.local",
            },
        }
        if phone_number:
            payload["phone_number"] = _format_phone_number(phone_number)
        if webhook_url:
            payload["webhook_url"] = webhook_url
        if metadata:
            payload["metadata"] = metadata

        logger.info("Snippe: Creating QR payment amount=%s %s", amount, currency)
        result = self._request(
            "POST", "/payments", json_data=payload, idempotency_key=idempotency_key
        )

        if result["success"]:
            data = result["data"]
            return {
                "success": True,
                "message": "QR code generated",
                "reference": data.get("reference"),
                "payment_qr_code": data.get("payment_qr_code"),
                "payment_url": data.get("payment_url"),
                "payment_token": data.get("payment_token"),
                "status": data.get("status"),
                "expires_at": data.get("expires_at"),
                "data": data,
            }
        return result

    # ------------------------------------------------------------------
    # Trigger / Retry USSD push
    # ------------------------------------------------------------------

    def trigger_push(self, reference: str, phone_number: str | None = None) -> dict:
        """
        Trigger or retry a USSD push for a pending payment.

        Args:
            reference:    Payment reference or payment_token
            phone_number: Optional different phone to push to
        """
        payload = {}
        if phone_number:
            payload["phone"] = _format_phone_number(phone_number)

        logger.info("Snippe: Triggering push for %s", reference)
        return self._request(
            "POST",
            f"/payments/{reference}/push",
            json_data=payload if payload else None,
        )

    # ------------------------------------------------------------------
    # Query / List / Search payments
    # ------------------------------------------------------------------

    def get_payment_status(self, reference: str) -> dict:
        """Get current status of a payment by reference."""
        logger.info("Snippe: Querying payment status for %s", reference)
        return self._request("GET", f"/payments/{reference}")

    def list_payments(self, limit: int = 20, offset: int = 0) -> dict:
        """List payments with pagination."""
        return self._request(
            "GET", "/payments", params={"limit": limit, "offset": offset}
        )

    def search_payments(self, reference: str) -> dict:
        """Search payments by reference."""
        return self._request("GET", "/payments/search", params={"reference": reference})

    def get_account_balance(self) -> dict:
        """Get account balance."""
        logger.info("Snippe: Querying account balance")
        result = self._request("GET", "/payments/balance")
        if result["success"]:
            data = result["data"]
            return {
                "success": True,
                "balance": data.get("balance", {}).get("value", 0),
                "available": data.get("available", {}).get("value", 0),
                "currency": data.get("balance", {}).get("currency", "TZS"),
                "data": data,
            }
        return result

    # ======================================================================
    # DISBURSEMENTS — Payouts
    # ======================================================================

    def create_mobile_payout(
        self,
        phone_number: str,
        amount: int,
        recipient_name: str,
        *,
        narration: str = "",
        webhook_url: str = "",
        metadata: dict | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        """
        Send money to a mobile money account.

        Args:
            phone_number:   Recipient phone (255XXXXXXXXX)
            amount:         Amount in smallest currency unit
            recipient_name: Full name of recipient
            narration:      Description / reason for payout
            webhook_url:    URL for webhook notifications
            metadata:       Custom key-value data
            idempotency_key: Prevent duplicate payouts
        """
        phone = _format_phone_number(phone_number)

        if not idempotency_key:
            idempotency_key = f"payout-{phone}-{amount}-{uuid.uuid4().hex[:8]}"

        payload = {
            "amount": int(amount),
            "channel": "mobile",
            "recipient_phone": phone,
            "recipient_name": recipient_name,
        }
        if narration:
            payload["narration"] = narration
        if webhook_url:
            payload["webhook_url"] = webhook_url
        if metadata:
            payload["metadata"] = metadata

        logger.info("Snippe: Creating mobile payout phone=%s amount=%s", phone, amount)
        result = self._request(
            "POST",
            "/payouts/send",
            json_data=payload,
            idempotency_key=idempotency_key,
        )

        if result["success"]:
            data = result["data"]
            return {
                "success": True,
                "reference": data.get("reference"),
                "external_reference": data.get("external_reference"),
                "status": data.get("status"),
                "amount": data.get("amount", {}).get("value"),
                "fees": data.get("fees", {}).get("value"),
                "total": data.get("total", {}).get("value"),
                "channel_provider": data.get("channel", {}).get("provider"),
                "data": data,
            }
        return result

    def get_payout_status(self, reference: str) -> dict:
        """Get current status of a payout by reference."""
        logger.info("Snippe: Querying payout status for %s", reference)
        return self._request("GET", f"/payouts/{reference}")

    def list_payouts(self, limit: int = 20, offset: int = 0) -> dict:
        """List payouts with pagination."""
        return self._request(
            "GET", "/payouts", params={"limit": limit, "offset": offset}
        )

    def calculate_payout_fee(self, amount: int) -> dict:
        """Calculate payout fee before creating a payout."""
        result = self._request("GET", "/payouts/fee", params={"amount": int(amount)})
        if result["success"]:
            data = result["data"]
            return {
                "success": True,
                "amount": data.get("amount"),
                "fee_amount": data.get("fee_amount"),
                "total_amount": data.get("total_amount"),
                "currency": data.get("currency", "TZS"),
                "data": data,
            }
        return result

    # ======================================================================
    # PAYMENT SESSIONS — Hosted Checkout
    # ======================================================================

    def create_session(
        self,
        amount: int,
        *,
        currency: str = "TZS",
        allowed_methods: list | None = None,
        customer: dict | None = None,
        redirect_url: str = "",
        webhook_url: str = "",
        description: str = "",
        metadata: dict | None = None,
        expires_in: int = 3600,
        line_items: list | None = None,
        profile_id: str = "",
    ) -> dict:
        """
        Create a hosted checkout session.

        Returns ``checkout_url`` and ``payment_link_url``.
        """
        payload: dict = {"amount": int(amount), "currency": currency}

        if allowed_methods:
            payload["allowed_methods"] = allowed_methods
        if customer:
            payload["customer"] = customer
        if redirect_url:
            payload["redirect_url"] = redirect_url
        if webhook_url:
            payload["webhook_url"] = webhook_url
        if description:
            payload["description"] = description
        if metadata:
            payload["metadata"] = metadata
        if expires_in:
            payload["expires_in"] = expires_in
        if line_items:
            payload["line_items"] = line_items
        if profile_id:
            payload["profile_id"] = profile_id

        logger.info("Snippe: Creating checkout session amount=%s %s", amount, currency)
        result = self._request("POST", "/sessions", json_data=payload)

        if result["success"]:
            data = result["data"]
            return {
                "success": True,
                "reference": data.get("reference"),
                "checkout_url": data.get("checkout_url"),
                "payment_link_url": data.get("payment_link_url"),
                "short_code": data.get("short_code"),
                "status": data.get("status"),
                "expires_at": data.get("expires_at"),
                "data": data,
            }
        return result

    def get_session(self, reference: str) -> dict:
        """Get session details by reference."""
        return self._request("GET", f"/sessions/{reference}")

    def list_sessions(
        self, limit: int = 20, offset: int = 0, status_filter: str = ""
    ) -> dict:
        """List sessions with optional status filter."""
        params: dict = {"limit": limit, "offset": offset}
        if status_filter:
            params["status"] = status_filter
        return self._request("GET", "/sessions", params=params)

    def cancel_session(self, reference: str) -> dict:
        """Cancel a pending/active session."""
        return self._request("POST", f"/sessions/{reference}/cancel")

    # ======================================================================
    # WEBHOOK VERIFICATION
    # ======================================================================

    def verify_signature(
        self, payload: str, signature: str, timestamp: str = ""
    ) -> bool:
        """Verify webhook signature using the instance's webhook_secret."""
        if not self.webhook_secret:
            logger.warning(
                "Snippe webhook secret not configured – skipping verification"
            )
            return True  # Allow in development
        return verify_webhook_signature(
            payload, signature, self.webhook_secret, timestamp
        )
