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
class BraintreeCard:
    number: str
    exp_month: str
    exp_year: str
    cvv: str
    cardholder_name: Optional[str] = None
    postal_code: Optional[str] = None


@dataclass
class BraintreeNonce:
    nonce: str
    type: str
    details: Dict[str, Any]
    bin_data: Dict[str, Any]


@dataclass
class BraintreeClientToken:
    token: str
    authorization_fingerprint: str
    merchant_id: str
    environment: str


class BraintreeDetector:
    def __init__(self, http_client: AdvancedHTTPClient):
        self.http_client = http_client
        
    def detect(self, html: str) -> Tuple[bool, Dict[str, Any]]:
        indicators = {
            "is_braintree": False,
            "client_token": None,
            "merchant_id": None,
            "environment": None,
            "features": []
        }
        
        braintree_indicators = [
            'braintree' in html.lower(),
            'braintreegateway.com' in html,
            'braintree-api.com' in html,
            'client.braintreegateway.com' in html,
            'braintree.setup' in html,
            'braintree-web' in html
        ]
        
        if any(braintree_indicators):
            indicators["is_braintree"] = True
        
        token_match = re.search(r'"clientToken"\s*:\s*"([^"]+)"', html)
        if token_match:
            indicators["client_token"] = token_match.group(1)
        
        if not indicators["client_token"]:
            token_match = re.search(r'braintree\.client\.create\s*\(\s*\{\s*authorization\s*:\s*["\']([^"\']+)', html)
            if token_match:
                indicators["client_token"] = token_match.group(1)
        
        merchant_match = re.search(r'"merchantId"\s*:\s*"([^"]+)"', html)
        if merchant_match:
            indicators["merchant_id"] = merchant_match.group(1)
        
        if 'sandbox' in html.lower():
            indicators["environment"] = "sandbox"
        elif 'production' in html.lower():
            indicators["environment"] = "production"
        
        if 'hostedFields' in html:
            indicators["features"].append("hosted_fields")
        if 'dropin' in html.lower():
            indicators["features"].append("drop_in")
        if 'threeDSecure' in html:
            indicators["features"].append("3ds")
        if 'paypal' in html.lower():
            indicators["features"].append("paypal")
        
        return indicators["is_braintree"], indicators


class BraintreeClientTokenParser:
    def __init__(self):
        pass
        
    def parse(self, client_token: str) -> Optional[BraintreeClientToken]:
        try:
            decoded = base64.b64decode(client_token).decode('utf-8')
            token_data = json.loads(decoded)
            
            return BraintreeClientToken(
                token=client_token,
                authorization_fingerprint=token_data.get("authorizationFingerprint", ""),
                merchant_id=token_data.get("merchantId", ""),
                environment=token_data.get("environment", "production")
            )
        except Exception:
            pass
        
        return None


class BraintreeGatewayHandler:
    def __init__(self, http_client: AdvancedHTTPClient, client_token: str = None):
        self.http_client = http_client
        self.client_token = client_token
        self.parsed_token = None
        self.behavior = HumanBehaviorSimulator()
        self.typing = TypingSimulator()
        self.api_base = None
        self.session_data = {}
        
    def initialize(self, client_token: str = None) -> bool:
        if client_token:
            self.client_token = client_token
        
        if not self.client_token:
            return False
        
        parser = BraintreeClientTokenParser()
        self.parsed_token = parser.parse(self.client_token)
        
        if not self.parsed_token:
            return False
        
        if self.parsed_token.environment == "sandbox":
            self.api_base = "https://payments.sandbox.braintree-api.com"
        else:
            self.api_base = "https://payments.braintree-api.com"
        
        self.session_data["fingerprint"] = self.parsed_token.authorization_fingerprint
        self.session_data["merchant_id"] = self.parsed_token.merchant_id
        
        return True
    
    def _get_braintree_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.parsed_token.authorization_fingerprint}",
            "Braintree-Version": "2018-05-10",
            "Origin": "https://assets.braintreegateway.com",
            "Referer": "https://assets.braintreegateway.com/"
        }
    
    def _generate_device_data(self) -> str:
        fingerprint_generator = BrowserFingerprintGenerator()
        fp = fingerprint_generator.generate_fingerprint()
        
        device_data = {
            "device_session_id": hashlib.md5(f"{time.time()}_{random.random()}".encode()).hexdigest(),
            "fraud_merchant_id": self.session_data.get("merchant_id", ""),
            "correlation_id": hashlib.sha256(f"{time.time()}".encode()).hexdigest()[:32]
        }
        
        return json.dumps(device_data)
    
    def tokenize_card(self, card: BraintreeCard) -> Optional[BraintreeNonce]:
        self.behavior.human_delay(action_type="form_field")
        
        graphql_url = f"{self.api_base}/graphql"
        
        query = """
        mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) {
            tokenizeCreditCard(input: $input) {
                token
                creditCard {
                    bin
                    brandCode
                    last4
                    cardholderName
                    expirationMonth
                    expirationYear
                    binData {
                        prepaid
                        healthcare
                        debit
                        durbinRegulated
                        commercial
                        payroll
                        issuingBank
                        countryOfIssuance
                        productId
                    }
                }
            }
        }
        """
        
        variables = {
            "input": {
                "creditCard": {
                    "number": card.number.replace(" ", ""),
                    "expirationMonth": card.exp_month,
                    "expirationYear": card.exp_year,
                    "cvv": card.cvv
                },
                "options": {
                    "validate": False
                }
            }
        }
        
        if card.cardholder_name:
            variables["input"]["creditCard"]["cardholderName"] = card.cardholder_name
        
        if card.postal_code:
            variables["input"]["creditCard"]["billingAddress"] = {
                "postalCode": card.postal_code
            }
        
        payload = {
            "clientSdkMetadata": {
                "source": "client",
                "integration": "custom",
                "sessionId": hashlib.md5(f"{time.time()}".encode()).hexdigest()
            },
            "query": query,
            "variables": variables,
            "operationName": "TokenizeCreditCard"
        }
        
        headers = self._get_braintree_headers()
        
        response = self.http_client.post(graphql_url, json_data=payload, headers=headers)
        
        if response.status_code == 200:
            try:
                result = json.loads(response.body)
                
                if "data" in result and "tokenizeCreditCard" in result["data"]:
                    token_data = result["data"]["tokenizeCreditCard"]
                    card_data = token_data.get("creditCard", {})
                    
                    return BraintreeNonce(
                        nonce=token_data.get("token", ""),
                        type="CreditCard",
                        details={
                            "bin": card_data.get("bin", ""),
                            "brand": card_data.get("brandCode", ""),
                            "last4": card_data.get("last4", ""),
                            "cardholder_name": card_data.get("cardholderName", ""),
                            "expiration_month": card_data.get("expirationMonth", ""),
                            "expiration_year": card_data.get("expirationYear", "")
                        },
                        bin_data=card_data.get("binData", {})
                    )
            except json.JSONDecodeError:
                pass
        
        return self._tokenize_card_rest(card)
    
    def _tokenize_card_rest(self, card: BraintreeCard) -> Optional[BraintreeNonce]:
        tokenize_url = f"https://client.braintreegateway.com/v1/payment_methods/credit_cards"
        
        data = {
            "credit_card": {
                "number": card.number.replace(" ", ""),
                "expiration_month": card.exp_month,
                "expiration_year": card.exp_year,
                "cvv": card.cvv,
                "options": {
                    "validate": False
                }
            },
            "authorization_fingerprint": self.parsed_token.authorization_fingerprint,
            "braintree_library_version": "braintree/web/3.94.0",
            "_meta": {
                "merchantAppId": "unknown",
                "platform": "web",
                "sdkVersion": "3.94.0",
                "source": "client",
                "integration": "custom",
                "integrationType": "custom",
                "sessionId": hashlib.md5(f"{time.time()}".encode()).hexdigest()
            }
        }
        
        if card.cardholder_name:
            data["credit_card"]["cardholder_name"] = card.cardholder_name
        
        if card.postal_code:
            data["credit_card"]["billing_address"] = {
                "postal_code": card.postal_code
            }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        response = self.http_client.post(tokenize_url, json_data=data, headers=headers)
        
        if response.status_code in [200, 201]:
            try:
                result = json.loads(response.body)
                
                if "creditCards" in result and len(result["creditCards"]) > 0:
                    card_data = result["creditCards"][0]
                    
                    return BraintreeNonce(
                        nonce=card_data.get("nonce", ""),
                        type="CreditCard",
                        details={
                            "bin": card_data.get("details", {}).get("bin", ""),
                            "brand": card_data.get("details", {}).get("cardType", ""),
                            "last4": card_data.get("details", {}).get("lastFour", ""),
                            "cardholder_name": card_data.get("details", {}).get("cardholderName", "")
                        },
                        bin_data=card_data.get("binData", {})
                    )
            except json.JSONDecodeError:
                pass
        
        return None
    
    def verify_3ds(self, nonce: str, amount: float, billing_info: Dict[str, Any] = None) -> Dict[str, Any]:
        self.behavior.human_delay(action_type="page_load")
        
        result = {
            "success": False,
            "nonce": None,
            "liability_shifted": False,
            "liability_shift_possible": False,
            "requires_challenge": False,
            "challenge_url": None,
            "error": None
        }
        
        graphql_url = f"{self.api_base}/graphql"
        
        query = """
        mutation PerformThreeDSecureLookup($input: PerformThreeDSecureLookupInput!) {
            performThreeDSecureLookup(input: $input) {
                threeDSecureLookupData {
                    acsUrl
                    md
                    paReq
                    termUrl
                    threeDSecureVersion
                }
                paymentMethod {
                    id
                }
                lookup {
                    transStatus
                    transStatusReason
                }
            }
        }
        """
        
        variables = {
            "input": {
                "paymentMethodId": nonce,
                "amount": str(amount),
                "requestedExemptionType": "LOW_VALUE"
            }
        }
        
        if billing_info:
            variables["input"]["billingAddress"] = {
                "givenName": billing_info.get("first_name", ""),
                "surname": billing_info.get("last_name", ""),
                "streetAddress": billing_info.get("address_1", ""),
                "extendedAddress": billing_info.get("address_2", ""),
                "locality": billing_info.get("city", ""),
                "region": billing_info.get("state", ""),
                "postalCode": billing_info.get("postcode", ""),
                "countryCodeAlpha2": billing_info.get("country", "US")
            }
        
        payload = {
            "clientSdkMetadata": {
                "source": "client",
                "integration": "custom",
                "sessionId": hashlib.md5(f"{time.time()}".encode()).hexdigest()
            },
            "query": query,
            "variables": variables,
            "operationName": "PerformThreeDSecureLookup"
        }
        
        headers = self._get_braintree_headers()
        
        response = self.http_client.post(graphql_url, json_data=payload, headers=headers)
        
        if response.status_code == 200:
            try:
                response_data = json.loads(response.body)
                
                if "data" in response_data and "performThreeDSecureLookup" in response_data["data"]:
                    lookup_data = response_data["data"]["performThreeDSecureLookup"]
                    
                    three_ds_data = lookup_data.get("threeDSecureLookupData", {})
                    
                    if three_ds_data.get("acsUrl"):
                        result["requires_challenge"] = True
                        result["challenge_url"] = three_ds_data["acsUrl"]
                        result["challenge_data"] = {
                            "md": three_ds_data.get("md", ""),
                            "pareq": three_ds_data.get("paReq", ""),
                            "term_url": three_ds_data.get("termUrl", "")
                        }
                    else:
                        result["success"] = True
                        result["nonce"] = lookup_data.get("paymentMethod", {}).get("id", nonce)
                        
                        lookup_info = lookup_data.get("lookup", {})
                        trans_status = lookup_info.get("transStatus", "")
                        
                        if trans_status in ["Y", "A"]:
                            result["liability_shifted"] = True
                            result["liability_shift_possible"] = True
                
            except json.JSONDecodeError:
                result["error"] = "Invalid response"
        else:
            result["error"] = f"HTTP {response.status_code}"
        
        return result
    
    def process_checkout_payment(self, card: BraintreeCard, amount: float = None,
                                  billing_info: Dict[str, Any] = None,
                                  use_3ds: bool = False) -> Dict[str, Any]:
        result = {
            "success": False,
            "nonce": None,
            "device_data": None,
            "liability_shifted": False,
            "error": None
        }
        
        nonce_result = self.tokenize_card(card)
        
        if not nonce_result:
            result["error"] = "Failed to tokenize card"
            return result
        
        result["nonce"] = nonce_result.nonce
        result["device_data"] = self._generate_device_data()
        
        if use_3ds and amount:
            three_ds_result = self.verify_3ds(nonce_result.nonce, amount, billing_info)
            
            if three_ds_result.get("requires_challenge"):
                result["requires_action"] = True
                result["action_type"] = "3ds"
                result["action_data"] = three_ds_result.get("challenge_data")
                return result
            
            if three_ds_result.get("success"):
                result["nonce"] = three_ds_result.get("nonce", result["nonce"])
                result["liability_shifted"] = three_ds_result.get("liability_shifted", False)
        
        result["success"] = True
        return result
    
    def get_device_data(self) -> str:
        return self._generate_device_data()


class BraintreeDropInHandler:
    def __init__(self, http_client: AdvancedHTTPClient):
        self.http_client = http_client
        self.behavior = HumanBehaviorSimulator()
        
    def parse_drop_in_config(self, html: str) -> Dict[str, Any]:
        config = {
            "client_token": None,
            "container_id": None,
            "payment_methods": []
        }
        
        token_match = re.search(r'braintree\.dropin\.create\s*\(\s*\{\s*authorization\s*:\s*["\']([^"\']+)', html)
        if token_match:
            config["client_token"] = token_match.group(1)
        
        container_match = re.search(r'container\s*:\s*["\']#?([^"\']+)', html)
        if container_match:
            config["container_id"] = container_match.group(1)
        
        if 'card' in html.lower():
            config["payment_methods"].append("card")
        if 'paypal' in html.lower():
            config["payment_methods"].append("paypal")
        if 'venmo' in html.lower():
            config["payment_methods"].append("venmo")
        
        return config
    
    def complete_drop_in_payment(self, client_token: str, card: BraintreeCard,
                                  billing_info: Dict[str, Any] = None) -> Dict[str, Any]:
        gateway = BraintreeGatewayHandler(self.http_client, client_token)
        
        if not gateway.initialize():
            return {"success": False, "error": "Failed to initialize gateway"}
        
        return gateway.process_checkout_payment(card, billing_info=billing_info)
