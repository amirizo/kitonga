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
        # Check if we have a valid cached token
        if self.token and self.token_expires_at:
            if datetime.now() < self.token_expires_at:
                return self.token
        
        url = f'{self.base_url}/third-parties/generate-token'
        
        headers = {
            'client-id': self.client_id,
            'api-key': self.api_key
        }
        
        try:
            response = requests.post(url, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('success'):
                self.token = result.get('token')
                # Token expires in 1 hour, cache it for 55 minutes to be safe
                self.token_expires_at = datetime.now() + timedelta(minutes=55)
                return self.token
            else:
                logger.error(f'Failed to get ClickPesa token: {result}')
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f'Failed to get ClickPesa access token: {str(e)}')
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
                'success': False,
                'message': 'Failed to authenticate with ClickPesa'
            }
        
        url = f'{self.base_url}/third-parties/payments/preview-ussd-push-request'
        
        # Format phone number (ensure it starts with 255)
        if phone_number.startswith('0'):
            phone_number = '255' + phone_number[1:]
        elif not phone_number.startswith('255'):
            phone_number = '255' + phone_number
        
        headers = {
            'Authorization': token,
            'Content-Type': 'application/json'
        }
        
        payload = {
            'amount': str(amount),
            'currency': 'TZS',
            'orderReference': order_reference,
            'phoneNumber': phone_number,
            'fetchSenderDetails': False
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            return {
                'success': True,
                'data': result
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f'ClickPesa preview request failed: {str(e)}')
            if hasattr(e.response, 'text'):
                logger.error(f'Response: {e.response.text}')
            return {
                'success': False,
                'message': 'Failed to preview payment'
            }
    
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
        token = self.get_access_token()
        if not token:
            return {
                'success': False,
                'message': 'Failed to authenticate with ClickPesa'
            }
        
        url = f'{self.base_url}/third-parties/payments/initiate-ussd-push-request'
        
        # Format phone number (ensure it starts with 255)
        if phone_number.startswith('0'):
            phone_number = '255' + phone_number[1:]
        elif not phone_number.startswith('255'):
            phone_number = '255' + phone_number
        
        headers = {
            'Authorization': token,
            'Content-Type': 'application/json'
        }
        
        payload = {
            'amount': str(amount),
            'currency': 'TZS',
            'orderReference': order_reference,
            'phoneNumber': phone_number
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            # ClickPesa returns transaction details directly
            return {
                'success': True,
                'message': 'Payment request sent to your phone',
                'transaction_id': result.get('id'),
                'order_reference': result.get('orderReference'),
                'status': result.get('status'),
                'channel': result.get('channel'),
                'data': result
            }
                
        except requests.exceptions.RequestException as e:
            logger.error(f'ClickPesa payment initiation failed: {str(e)}')
            if hasattr(e.response, 'text'):
                logger.error(f'Response: {e.response.text}')
            return {
                'success': False,
                'message': 'Failed to initiate payment. Please try again.'
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
                'success': False,
                'message': 'Failed to authenticate with ClickPesa'
            }
        
        url = f'{self.base_url}/third-parties/payments/{order_reference}'
        
        headers = {
            'Authorization': token
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f'ClickPesa query response for {order_reference}: {result}')
            return {
                'success': True,
                'data': result
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f'ClickPesa status query failed: {str(e)}')
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f'Response text: {e.response.text}')
            return {
                'success': False,
                'message': 'Failed to query payment status'
            }
