import re
import json
import time
import random
import hashlib
import base64
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse, urljoin, parse_qs
from dataclasses import dataclass

from ..core.http_client import AdvancedHTTPClient, HTTPResponse
from ..core.behavior import HumanBehaviorSimulator, TypingSimulator
from ..core.browser import SessionManager, BrowserFingerprintGenerator


@dataclass
class StripeCard:
    number: str
    exp_month: str
    exp_year: str
    cvc: str
    name: Optional[str] = None


@dataclass
class StripePaymentIntent:
    id: str
    client_secret: str
    status: str
    amount: int
    currency: str
    payment_method: Optional[str] = None
    requires_action: bool = False
    next_action: Optional[Dict] = None


@dataclass
class StripePaymentMethod:
    id: str
    type: str
    card: Dict[str, Any]
    billing_details: Dict[str, Any]


class StripeDetector:
    def __init__(self, http_client: AdvancedHTTPClient):
        self.http_client = http_client
        
    def detect(self, html: str) -> Tuple[bool, Dict[str, Any]]:
        indicators = {
            "is_stripe": False,
            "publishable_key": None,
            "account_id": None,
            "elements_version": None,
            "features": []
        }
        
        stripe_indicators = [
            'stripe.com' in html,
            'Stripe(' in html,
            'stripe.js' in html,
            'js.stripe.com' in html,
            'stripe_publishable_key' in html.lower(),
            'pk_live_' in html or 'pk_test_' in html
        ]
        
        if any(stripe_indicators):
            indicators["is_stripe"] = True
        
        pk_match = re.search(r'(pk_(?:live|test)_[a-zA-Z0-9]+)', html)
        if pk_match:
            indicators["publishable_key"] = pk_match.group(1)
        
        account_match = re.search(r'"stripeAccount"\s*:\s*"(acct_[a-zA-Z0-9]+)"', html)
        if account_match:
            indicators["account_id"] = account_match.group(1)
        
        if 'PaymentElement' in html:
            indicators["features"].append("payment_element")
        if 'CardElement' in html:
            indicators["features"].append("card_element")
        if 'stripe.confirmCardPayment' in html:
            indicators["features"].append("payment_intents")
        if 'stripe.createToken' in html:
            indicators["features"].append("tokens")
        
        return indicators["is_stripe"], indicators


class StripeElementsEmulator:
    def __init__(self, publishable_key: str, session_manager: SessionManager = None):
        self.publishable_key = publishable_key
        self.session_manager = session_manager or SessionManager()
        self.fingerprint_generator = BrowserFingerprintGenerator()
        self.api_base = "https://api.stripe.com"
        self.js_base = "https://js.stripe.com"
        self.muid = None
        self.guid = None
        self.sid = None
        
    def _generate_muid(self) -> str:
        return hashlib.md5(f"{time.time()}_{random.random()}".encode()).hexdigest()
    
    def _generate_guid(self) -> str:
        return f"{self._random_hex(8)}-{self._random_hex(4)}-{self._random_hex(4)}-{self._random_hex(4)}-{self._random_hex(12)}"
    
    def _generate_sid(self) -> str:
        return self._random_hex(24)
    
    def _random_hex(self, length: int) -> str:
        return ''.join(random.choice('0123456789abcdef') for _ in range(length))
    
    def initialize(self) -> Dict[str, str]:
        self.muid = self._generate_muid()
        self.guid = self._generate_guid()
        self.sid = self._generate_sid()
        
        return {
            "muid": self.muid,
            "guid": self.guid,
            "sid": self.sid
        }
    
    def generate_payment_user_agent(self) -> str:
        components = [
            "stripe.js/v3",
            "stripe-js-v3/v3",
            "payment-element",
            "card-element"
        ]
        return " ".join(random.sample(components, 2))


class StripeGatewayHandler:
    def __init__(self, http_client: AdvancedHTTPClient, publishable_key: str = None):
        self.http_client = http_client
        self.publishable_key = publishable_key
        self.behavior = HumanBehaviorSimulator()
        self.typing = TypingSimulator()
        self.elements_emulator = None
        self.api_base = "https://api.stripe.com/v1"
        self.session_data = {}
        
    def initialize(self, publishable_key: str = None) -> bool:
        if publishable_key:
            self.publishable_key = publishable_key
        
        if not self.publishable_key:
            return False
        
        self.elements_emulator = StripeElementsEmulator(self.publishable_key)
        ids = self.elements_emulator.initialize()
        self.session_data.update(ids)
        
        return True
    
    def _get_stripe_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.publishable_key}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Origin": "https://js.stripe.com",
            "Referer": "https://js.stripe.com/",
            "Stripe-Version": "2023-10-16"
        }
    
    def create_payment_method(self, card: StripeCard, billing_details: Dict[str, Any] = None) -> Optional[StripePaymentMethod]:
        self.behavior.human_delay(action_type="form_field")
        
        data = {
            "type": "card",
            "card[number]": card.number.replace(" ", ""),
            "card[exp_month]": card.exp_month,
            "card[exp_year]": card.exp_year,
            "card[cvc]": card.cvc,
            "guid": self.session_data.get("guid", ""),
            "muid": self.session_data.get("muid", ""),
            "sid": self.session_data.get("sid", ""),
            "payment_user_agent": self.elements_emulator.generate_payment_user_agent() if self.elements_emulator else "stripe.js/v3",
            "time_on_page": str(random.randint(30000, 120000)),
            "key": self.publishable_key
        }
        
        if card.name:
            data["billing_details[name]"] = card.name
        
        if billing_details:
            if "email" in billing_details:
                data["billing_details[email]"] = billing_details["email"]
            if "phone" in billing_details:
                data["billing_details[phone]"] = billing_details["phone"]
            if "address" in billing_details:
                addr = billing_details["address"]
                if "line1" in addr:
                    data["billing_details[address][line1]"] = addr["line1"]
                if "line2" in addr:
                    data["billing_details[address][line2]"] = addr["line2"]
                if "city" in addr:
                    data["billing_details[address][city]"] = addr["city"]
                if "state" in addr:
                    data["billing_details[address][state]"] = addr["state"]
                if "postal_code" in addr:
                    data["billing_details[address][postal_code]"] = addr["postal_code"]
                if "country" in addr:
                    data["billing_details[address][country]"] = addr["country"]
        
        headers = self._get_stripe_headers()
        
        response = self.http_client.post(f"{self.api_base}/payment_methods", data=data, headers=headers)
        
        if response.status_code == 200:
            try:
                pm_data = json.loads(response.body)
                return StripePaymentMethod(
                    id=pm_data.get("id", ""),
                    type=pm_data.get("type", "card"),
                    card=pm_data.get("card", {}),
                    billing_details=pm_data.get("billing_details", {})
                )
            except json.JSONDecodeError:
                pass
        
        return None
    
    def create_token(self, card: StripeCard) -> Optional[str]:
        self.behavior.human_delay(action_type="form_field")
        
        data = {
            "card[number]": card.number.replace(" ", ""),
            "card[exp_month]": card.exp_month,
            "card[exp_year]": card.exp_year,
            "card[cvc]": card.cvc,
            "guid": self.session_data.get("guid", ""),
            "muid": self.session_data.get("muid", ""),
            "sid": self.session_data.get("sid", ""),
            "payment_user_agent": "stripe.js/v3",
            "time_on_page": str(random.randint(30000, 120000)),
            "key": self.publishable_key
        }
        
        if card.name:
            data["card[name]"] = card.name
        
        headers = self._get_stripe_headers()
        
        response = self.http_client.post(f"{self.api_base}/tokens", data=data, headers=headers)
        
        if response.status_code == 200:
            try:
                token_data = json.loads(response.body)
                return token_data.get("id")
            except json.JSONDecodeError:
                pass
        
        return None
    
    def confirm_payment_intent(self, client_secret: str, payment_method_id: str, 
                               return_url: str = None) -> Dict[str, Any]:
        self.behavior.human_delay(action_type="button_click")
        
        intent_id = client_secret.split("_secret_")[0]
        
        data = {
            "payment_method": payment_method_id,
            "expected_payment_method_type": "card",
            "use_stripe_sdk": "true",
            "key": self.publishable_key,
            "client_secret": client_secret
        }
        
        if return_url:
            data["return_url"] = return_url
        
        headers = self._get_stripe_headers()
        
        response = self.http_client.post(
            f"{self.api_base}/payment_intents/{intent_id}/confirm",
            data=data,
            headers=headers
        )
        
        result = {
            "success": False,
            "status": None,
            "requires_action": False,
            "action_type": None,
            "action_url": None,
            "error": None
        }
        
        if response.status_code == 200:
            try:
                intent_data = json.loads(response.body)
                result["status"] = intent_data.get("status")
                
                if result["status"] == "succeeded":
                    result["success"] = True
                
                elif result["status"] == "requires_action":
                    result["requires_action"] = True
                    next_action = intent_data.get("next_action", {})
                    
                    if next_action.get("type") == "redirect_to_url":
                        result["action_type"] = "redirect"
                        result["action_url"] = next_action.get("redirect_to_url", {}).get("url")
                    
                    elif next_action.get("type") == "use_stripe_sdk":
                        result["action_type"] = "3ds"
                        result["action_data"] = next_action.get("use_stripe_sdk", {})
                
                elif result["status"] == "requires_payment_method":
                    result["error"] = "Payment method failed"
                    error_data = intent_data.get("last_payment_error", {})
                    if error_data:
                        result["error"] = error_data.get("message", result["error"])
                
            except json.JSONDecodeError:
                result["error"] = "Invalid response"
        else:
            try:
                error_data = json.loads(response.body)
                result["error"] = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
            except json.JSONDecodeError:
                result["error"] = f"HTTP {response.status_code}"
        
        return result
    
    def confirm_setup_intent(self, client_secret: str, payment_method_id: str,
                             return_url: str = None) -> Dict[str, Any]:
        self.behavior.human_delay(action_type="button_click")
        
        intent_id = client_secret.split("_secret_")[0]
        
        data = {
            "payment_method": payment_method_id,
            "expected_payment_method_type": "card",
            "use_stripe_sdk": "true",
            "key": self.publishable_key,
            "client_secret": client_secret
        }
        
        if return_url:
            data["return_url"] = return_url
        
        headers = self._get_stripe_headers()
        
        response = self.http_client.post(
            f"{self.api_base}/setup_intents/{intent_id}/confirm",
            data=data,
            headers=headers
        )
        
        result = {
            "success": False,
            "status": None,
            "requires_action": False,
            "error": None
        }
        
        if response.status_code == 200:
            try:
                intent_data = json.loads(response.body)
                result["status"] = intent_data.get("status")
                
                if result["status"] == "succeeded":
                    result["success"] = True
                elif result["status"] == "requires_action":
                    result["requires_action"] = True
                
            except json.JSONDecodeError:
                result["error"] = "Invalid response"
        else:
            result["error"] = f"HTTP {response.status_code}"
        
        return result
    
    def retrieve_payment_intent(self, client_secret: str) -> Optional[StripePaymentIntent]:
        intent_id = client_secret.split("_secret_")[0]
        
        params = {
            "key": self.publishable_key,
            "client_secret": client_secret
        }
        
        headers = self._get_stripe_headers()
        
        url = f"{self.api_base}/payment_intents/{intent_id}"
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        
        response = self.http_client.get(f"{url}?{query_string}", headers=headers)
        
        if response.status_code == 200:
            try:
                data = json.loads(response.body)
                return StripePaymentIntent(
                    id=data.get("id", ""),
                    client_secret=client_secret,
                    status=data.get("status", ""),
                    amount=data.get("amount", 0),
                    currency=data.get("currency", ""),
                    payment_method=data.get("payment_method"),
                    requires_action=data.get("status") == "requires_action",
                    next_action=data.get("next_action")
                )
            except json.JSONDecodeError:
                pass
        
        return None
    
    def process_checkout_payment(self, card: StripeCard, client_secret: str,
                                  billing_details: Dict[str, Any] = None,
                                  return_url: str = None) -> Dict[str, Any]:
        result = {
            "success": False,
            "payment_method_id": None,
            "status": None,
            "requires_action": False,
            "action_type": None,
            "action_url": None,
            "error": None
        }
        
        payment_method = self.create_payment_method(card, billing_details)
        
        if not payment_method:
            result["error"] = "Failed to create payment method"
            return result
        
        result["payment_method_id"] = payment_method.id
        
        confirm_result = self.confirm_payment_intent(
            client_secret,
            payment_method.id,
            return_url
        )
        
        result.update(confirm_result)
        
        return result
    
    def handle_3ds_challenge(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            "success": False,
            "completed": False,
            "error": None
        }
        
        if "three_d_secure_2_source" in action_data:
            source_id = action_data["three_d_secure_2_source"]
            
            self.behavior.human_delay(action_type="page_load")
            
            result["completed"] = True
            result["source_id"] = source_id
        
        return result


class StripeCheckoutHandler:
    def __init__(self, http_client: AdvancedHTTPClient):
        self.http_client = http_client
        self.behavior = HumanBehaviorSimulator()
        self.session_id = None
        self.checkout_url = None
        
    def parse_checkout_session(self, html: str) -> Dict[str, Any]:
        session_data = {
            "session_id": None,
            "publishable_key": None,
            "amount": None,
            "currency": None,
            "client_secret": None
        }
        
        session_match = re.search(r'(cs_(?:live|test)_[a-zA-Z0-9]+)', html)
        if session_match:
            session_data["session_id"] = session_match.group(1)
        
        pk_match = re.search(r'(pk_(?:live|test)_[a-zA-Z0-9]+)', html)
        if pk_match:
            session_data["publishable_key"] = pk_match.group(1)
        
        amount_match = re.search(r'"amount"\s*:\s*(\d+)', html)
        if amount_match:
            session_data["amount"] = int(amount_match.group(1))
        
        currency_match = re.search(r'"currency"\s*:\s*"([a-z]{3})"', html)
        if currency_match:
            session_data["currency"] = currency_match.group(1)
        
        secret_match = re.search(r'"client_secret"\s*:\s*"([^"]+)"', html)
        if secret_match:
            session_data["client_secret"] = secret_match.group(1)
        
        return session_data
    
    def complete_checkout_session(self, session_id: str, card: StripeCard,
                                   billing_details: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            "success": False,
            "redirect_url": None,
            "error": None
        }
        
        checkout_url = f"https://checkout.stripe.com/c/pay/{session_id}"
        
        response = self.http_client.get(checkout_url)
        
        if response.status_code != 200:
            result["error"] = "Failed to load checkout page"
            return result
        
        self.behavior.human_delay(action_type="page_load")
        
        session_data = self.parse_checkout_session(response.body)
        
        if session_data.get("publishable_key") and session_data.get("client_secret"):
            gateway = StripeGatewayHandler(self.http_client, session_data["publishable_key"])
            gateway.initialize()
            
            payment_result = gateway.process_checkout_payment(
                card,
                session_data["client_secret"],
                billing_details
            )
            
            result.update(payment_result)
        else:
            result["error"] = "Could not extract checkout session data"
        
        return result
