"""
ClickPesa API Integration
Handles Mobile Money USSD-PUSH payments for Tanzania
"""

import requests
from datetime import datetime, timedelta
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class ClickPesaAPI:
    """
    ClickPesa API client for Mobile Money payments
    Supports M-PESA, TIGO-PESA, AIRTEL-MONEY, and HALOPESA
    """

    def __init__(self):
        self.client_id = settings.CLICKPESA_CLIENT_ID
        self.api_key = settings.CLICKPESA_API_KEY
        self.base_url = settings.CLICKPESA_BASE_URL
        self.token = None
        self.token_expires_at = None

    def get_access_token(self):
        """
        Generate JWT Authorization token
        Token is valid for 1 hour from issuance
        """
        # Validate credentials are configured
        if not self.client_id or not self.api_key:
            logger.error(
                "ClickPesa credentials not configured. "
                "Set CLICKPESA_CLIENT_ID and CLICKPESA_API_KEY in environment."
            )
            return None

        # Check if we have a valid cached token
        if self.token and self.token_expires_at:
            if datetime.now() < self.token_expires_at:
                return self.token

        url = f"{self.base_url}/third-parties/generate-token"

        headers = {"client-id": self.client_id, "api-key": self.api_key}

        try:
            response = requests.post(url, headers=headers, timeout=15)
            response.raise_for_status()

            result = response.json()

            if result.get("success"):
                self.token = result.get("token")
                # Token expires in 1 hour, cache it for 55 minutes to be safe
                self.token_expires_at = datetime.now() + timedelta(minutes=55)
                return self.token
            else:
                logger.error(f"Failed to get ClickPesa token: {result}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get ClickPesa access token: {str(e)}")
            if e.response is not None:
                try:
                    logger.error(f"ClickPesa token response: {e.response.text}")
                except Exception:
                    pass
            return None

    def preview_payment(self, phone_number, amount, order_reference):
        """
        Preview USSD-PUSH request
        Validates phone number, amount, and checks payment channel availability

        Args:
            phone_number: Mobile phone number (format: 255XXXXXXXXX)
            amount: Payment amount
            order_reference: Unique order reference

        Returns:
            dict: Preview response with active payment methods
        """
        token = self.get_access_token()
        if not token:
            return {
                "success": False,
                "message": "Failed to authenticate with ClickPesa",
            }

        url = f"{self.base_url}/third-parties/payments/preview-ussd-push-request"

        phone_number = str(phone_number).strip()

        # Format phone number (ensure it starts with 255)
        if phone_number.startswith("+"):
            phone_number = phone_number[1:]
        if phone_number.startswith("0"):
            phone_number = "255" + phone_number[1:]
        elif not phone_number.startswith("255"):
            phone_number = "255" + phone_number

        headers = {"Authorization": token, "Content-Type": "application/json"}

        payload = {
            "amount": str(amount),
            "currency": "TZS",
            "orderReference": order_reference,
            "phoneNumber": phone_number,
            "fetchSenderDetails": False,
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()

            result = response.json()
            return {"success": True, "data": result}

        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try:
                    logger.error(f"Response: {e.response.text}")
                except Exception:
                    pass
            logger.error(f"ClickPesa preview request failed: {error_detail}")
            return {"success": False, "message": f"Failed to preview payment: {error_detail}"}

    def initiate_payment(self, phone_number, amount, order_reference):
        """
        Initiate USSD-PUSH payment request
        Sends payment request to customer's mobile device

        Args:
            phone_number: Mobile phone number (format: 255XXXXXXXXX)
            amount: Payment amount
            order_reference: Unique order reference

        Returns:
            dict: Payment initiation response
        """
        # Validate phone number before proceeding
        if not phone_number or not str(phone_number).strip():
            logger.error("ClickPesa payment initiation failed: phone_number is empty or None")
            return {
                "success": False,
                "message": "Phone number is required to initiate payment.",
            }

        phone_number = str(phone_number).strip()

        token = self.get_access_token()
        if not token:
            logger.error(
                "ClickPesa authentication failed. Check CLICKPESA_CLIENT_ID and CLICKPESA_API_KEY."
            )
            return {
                "success": False,
                "message": "Failed to authenticate with payment provider. Please contact support.",
            }

        url = f"{self.base_url}/third-parties/payments/initiate-ussd-push-request"

        # Format phone number (ensure it starts with 255)
        if phone_number.startswith("+"):
            phone_number = phone_number[1:]
        if phone_number.startswith("0"):
            phone_number = "255" + phone_number[1:]
        elif not phone_number.startswith("255"):
            phone_number = "255" + phone_number

        headers = {"Authorization": token, "Content-Type": "application/json"}

        payload = {
            "amount": str(int(amount)) if float(amount) == int(amount) else str(amount),
            "currency": "TZS",
            "orderReference": order_reference,
            "phoneNumber": phone_number,
        }

        logger.info(
            f"ClickPesa initiating payment: phone={phone_number}, amount={amount}, ref={order_reference}"
        )

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()

            result = response.json()

            # ClickPesa returns transaction details directly
            return {
                "success": True,
                "message": "Payment request sent to your phone",
                "transaction_id": result.get("id"),
                "order_reference": result.get("orderReference"),
                "status": result.get("status"),
                "channel": result.get("channel"),
                "data": result,
            }

        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            response_body = None
            if e.response is not None:
                try:
                    response_body = e.response.text
                except Exception:
                    pass
            logger.error(
                f"ClickPesa payment initiation failed: {error_detail} | "
                f"Response body: {response_body}"
            )
            return {
                "success": False,
                "message": f"Failed to initiate payment: {error_detail}",
            }

    def query_payment_status(self, order_reference):
        """
        Query payment status by order reference

        Args:
            order_reference: Unique order reference

        Returns:
            dict: Payment status information
        """
        token = self.get_access_token()
        if not token:
            return {
                "success": False,
                "message": "Failed to authenticate with ClickPesa",
            }

        url = f"{self.base_url}/third-parties/payments/{order_reference}"

        headers = {"Authorization": token}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            result = response.json()
            logger.info(f"ClickPesa query response for {order_reference}: {result}")
            return {"success": True, "data": result}

        except requests.exceptions.RequestException as e:
            logger.error(f"ClickPesa status query failed: {str(e)}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response text: {e.response.text}")
            return {"success": False, "message": "Failed to query payment status"}

    # =========================================================================
    # PAYOUT API METHODS
    # =========================================================================

    def get_account_balance(self):
        """
        Retrieve account balance
        Check if merchant has enough funds to perform a payout

        Returns:
            dict: Account balance information
        """
        token = self.get_access_token()
        if not token:
            return {
                "success": False,
                "message": "Failed to authenticate with ClickPesa",
            }

        url = f"{self.base_url}/third-parties/account/balance"

        headers = {"Authorization": token}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            result = response.json()
            logger.info(f"ClickPesa account balance: {result}")

            # Response can be an array OR an object with 'balances' array
            balances = {}
            balance_list = (
                result if isinstance(result, list) else result.get("balances", [])
            )

            if isinstance(balance_list, list):
                for bal in balance_list:
                    currency = bal.get("currency", "TZS")
                    balances[currency] = bal.get("balance", 0)

            return {"success": True, "balances": balances, "data": result}

        except requests.exceptions.RequestException as e:
            logger.error(f"ClickPesa balance query failed: {str(e)}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response text: {e.response.text}")
            return {"success": False, "message": "Failed to retrieve account balance"}

    def preview_mobile_money_payout(
        self, phone_number, amount, order_reference, currency="TZS"
    ):
        """
        Preview/validate mobile money payout details
        Step 2: Validates phone number, amount, order-reference, fee

        Args:
            phone_number: Mobile phone number (format: 255XXXXXXXXX)
            amount: Payout amount
            order_reference: Unique order reference
            currency: Currency (TZS or USD)

        Returns:
            dict: Preview response with fee, channel provider, receiver details
        """
        token = self.get_access_token()
        if not token:
            return {
                "success": False,
                "message": "Failed to authenticate with ClickPesa",
            }

        url = f"{self.base_url}/third-parties/payouts/preview-mobile-money-payout"

        # Format phone number (ensure it starts with 255)
        if phone_number.startswith("0"):
            phone_number = "255" + phone_number[1:]
        elif phone_number.startswith("+"):
            phone_number = phone_number[1:]
        elif not phone_number.startswith("255"):
            phone_number = "255" + phone_number

        headers = {"Authorization": token, "Content-Type": "application/json"}

        payload = {
            "amount": float(amount),
            "phoneNumber": phone_number,
            "currency": currency,
            "orderReference": order_reference,
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()

            result = response.json()
            logger.info(f"ClickPesa payout preview for {order_reference}: {result}")

            return {
                "success": True,
                "total_amount": result.get("amount"),  # Amount including fee
                "fee": result.get("fee"),
                "balance": result.get("balance"),
                "channel_provider": result.get("channelProvider"),
                "receiver": result.get("receiver"),
                "data": result,
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"ClickPesa payout preview failed: {str(e)}")
            error_message = "Failed to preview payout"
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response text: {e.response.text}")
                try:
                    error_data = e.response.json()
                    error_message = error_data.get("message", error_message)
                except:
                    pass
            return {"success": False, "message": error_message}

    def create_mobile_money_payout(
        self, phone_number, amount, order_reference, currency="TZS"
    ):
        """
        Initiate a mobile money payout
        Step 3: The specified amount will be transferred to recipient's mobile wallet

        Args:
            phone_number: Mobile phone number (format: 255XXXXXXXXX)
            amount: Payout amount
            order_reference: Unique order reference
            currency: Currency (TZS or USD)

        Returns:
            dict: Payout response with transaction details
        """
        token = self.get_access_token()
        if not token:
            return {
                "success": False,
                "message": "Failed to authenticate with ClickPesa",
            }

        url = f"{self.base_url}/third-parties/payouts/create-mobile-money-payout"

        # Format phone number (ensure it starts with 255)
        if phone_number.startswith("0"):
            phone_number = "255" + phone_number[1:]
        elif phone_number.startswith("+"):
            phone_number = phone_number[1:]
        elif not phone_number.startswith("255"):
            phone_number = "255" + phone_number

        headers = {"Authorization": token, "Content-Type": "application/json"}

        payload = {
            "amount": float(amount),
            "phoneNumber": phone_number,
            "currency": currency,
            "orderReference": order_reference,
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()

            result = response.json()
            logger.info(f"ClickPesa payout created for {order_reference}: {result}")

            return {
                "success": True,
                "payout_id": result.get("id"),
                "order_reference": result.get("orderReference"),
                "amount": result.get("amount"),
                "fee": result.get("fee"),
                "status": result.get("status"),  # AUTHORIZED, SUCCESS, REVERSED
                "channel": result.get("channel"),
                "channel_provider": result.get("channelProvider"),
                "beneficiary": result.get("beneficiary"),
                "data": result,
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"ClickPesa payout creation failed: {str(e)}")
            error_message = "Failed to create payout"
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response text: {e.response.text}")
                try:
                    error_data = e.response.json()
                    error_message = error_data.get("message", error_message)
                except:
                    pass
            return {"success": False, "message": error_message}

    def query_payout_status(self, order_reference):
        """
        Query payout status by order reference
        Step 4: Check payout status

        Args:
            order_reference: Unique order reference

        Returns:
            dict: Payout status information
            Statuses: SUCCESS, PROCESSING, PENDING, FAILED, REFUNDED, REVERSED
        """
        token = self.get_access_token()
        if not token:
            return {
                "success": False,
                "message": "Failed to authenticate with ClickPesa",
            }

        url = f"{self.base_url}/third-parties/payouts/{order_reference}"

        headers = {"Authorization": token}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            result = response.json()
            logger.info(f"ClickPesa payout status for {order_reference}: {result}")

            # Response is an array
            if isinstance(result, list) and len(result) > 0:
                payout = result[0]
                return {
                    "success": True,
                    "payout_id": payout.get("id"),
                    "order_reference": payout.get("orderReference"),
                    "amount": payout.get("amount"),
                    "fee": payout.get("fee"),
                    "status": payout.get(
                        "status"
                    ),  # SUCCESS, PROCESSING, PENDING, FAILED, REFUNDED, REVERSED
                    "channel": payout.get("channel"),
                    "channel_provider": payout.get("channelProvider"),
                    "beneficiary": payout.get("beneficiary"),
                    "data": payout,
                }

            return {
                "success": False,
                "message": f"Payout not found in ClickPesa for reference: {order_reference}",
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"ClickPesa payout status query failed: {str(e)}")
            error_message = "Failed to query payout status"
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response text: {e.response.text}")
                try:
                    error_data = e.response.json()
                    error_message = error_data.get("message", error_message)
                except:
                    pass
            return {"success": False, "message": error_message}

    # =========================================================================
    # BANK PAYOUT API METHODS
    # =========================================================================

    def preview_bank_payout(
        self,
        account_number,
        amount,
        order_reference,
        bic,
        transfer_type="ACH",
        currency="TZS",
        account_currency="TZS",
    ):
        """
        Preview/validate bank payout details
        Validates account number, amount, order-reference, fee, and bank details

        Args:
            account_number: Bank account number
            amount: Payout amount
            order_reference: Unique order reference
            bic: Bank Identifier Code (BIC/SWIFT code)
            transfer_type: ACH or RTGS (default: ACH)
            currency: Source currency (TZS or USD)
            account_currency: Destination account currency (TZS or USD)

        Returns:
            dict: Preview response with fee, channel provider, receiver details
        """
        token = self.get_access_token()
        if not token:
            return {
                "success": False,
                "message": "Failed to authenticate with ClickPesa",
            }

        url = f"{self.base_url}/third-parties/payouts/preview-bank-payout"

        headers = {"Authorization": token, "Content-Type": "application/json"}

        payload = {
            "amount": float(amount),
            "accountNumber": account_number,
            "currency": currency,
            "orderReference": order_reference,
            "bic": bic,
            "transferType": transfer_type,
            "accountCurrency": account_currency,
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()

            result = response.json()
            logger.info(
                f"ClickPesa bank payout preview for {order_reference}: {result}"
            )

            return {
                "success": True,
                "total_amount": result.get("amount"),  # Amount including fee
                "fee": result.get("fee"),
                "balance": result.get("balance"),
                "channel_provider": result.get("channelProvider"),
                "receiver": result.get("receiver"),
                "transfer_type": result.get("transferType"),
                "exchange": result.get("exchange"),
                "exchanged": result.get("exchanged", False),
                "data": result,
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"ClickPesa bank payout preview failed: {str(e)}")
            error_message = "Failed to preview bank payout"
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response text: {e.response.text}")
                try:
                    error_data = e.response.json()
                    error_message = error_data.get("message", error_message)
                except:
                    pass
            return {"success": False, "message": error_message}

    def create_bank_payout(
        self,
        account_number,
        account_name,
        amount,
        order_reference,
        bic,
        transfer_type="ACH",
        currency="TZS",
        account_currency="TZS",
    ):
        """
        Initiate a bank transfer payout
        The specified amount will be transferred to recipient's bank account

        Args:
            account_number: Bank account number
            account_name: Account holder name (required for bank transfers)
            amount: Payout amount
            order_reference: Unique order reference
            bic: Bank Identifier Code (BIC/SWIFT code)
            transfer_type: ACH or RTGS (default: ACH)
            currency: Source currency (TZS or USD)
            account_currency: Destination account currency (TZS or USD)

        Returns:
            dict: Payout response with transaction details
        """
        token = self.get_access_token()
        if not token:
            return {
                "success": False,
                "message": "Failed to authenticate with ClickPesa",
            }

        url = f"{self.base_url}/third-parties/payouts/create-bank-payout"

        headers = {"Authorization": token, "Content-Type": "application/json"}

        payload = {
            "amount": float(amount),
            "accountNumber": account_number,
            "accountName": account_name,
            "currency": currency,
            "orderReference": order_reference,
            "bic": bic,
            "transferType": transfer_type,
            "accountCurrency": account_currency,
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()

            result = response.json()
            logger.info(
                f"ClickPesa bank payout created for {order_reference}: {result}"
            )

            return {
                "success": True,
                "payout_id": result.get("id"),
                "order_reference": result.get("orderReference"),
                "amount": result.get("amount"),
                "fee": result.get("fee"),
                "status": result.get("status"),  # AUTHORIZED, SUCCESS, REVERSED
                "channel": result.get("channel"),
                "channel_provider": result.get("channelProvider"),
                "transfer_type": result.get("transferType"),
                "beneficiary": result.get("beneficiary"),
                "exchange": result.get("exchange"),
                "exchanged": result.get("exchanged", False),
                "data": result,
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"ClickPesa bank payout creation failed: {str(e)}")
            error_message = "Failed to create bank payout"
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response text: {e.response.text}")
                try:
                    error_data = e.response.json()
                    error_message = error_data.get("message", error_message)
                except:
                    pass
            return {"success": False, "message": error_message}
