import json
import time
import hashlib
import os
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin
from enum import Enum

from .session_persistence import (
    SessionPersistenceManager,
    CheckoutSessionData,
    StoredCookie,
    StoredHeader,
    StoredFingerprint
)
from .http_client import PersistentHTTPClient, HTTPResponse
from .browser import BrowserFingerprintGenerator
from .behavior import HumanBehaviorSimulator


class CheckoutStatus(Enum):
    INITIALIZED = "initialized"
    BROWSING = "browsing"
    PRODUCT_PAGE = "product_page"
    CART = "cart"
    CHECKOUT_STARTED = "checkout_started"
    BILLING_INFO = "billing_info"
    SHIPPING_INFO = "shipping_info"
    PAYMENT_INFO = "payment_info"
    PROCESSING = "processing"
    THREE_DS_REQUIRED = "3ds_required"
    CAPTCHA_REQUIRED = "captcha_required"
    COMPLETED = "completed"
    FAILED = "failed"
    DECLINED = "declined"


class CheckoutStep(Enum):
    VISIT_SITE = "visit_site"
    BROWSE_PRODUCTS = "browse_products"
    VIEW_PRODUCT = "view_product"
    ADD_TO_CART = "add_to_cart"
    VIEW_CART = "view_cart"
    INITIATE_CHECKOUT = "initiate_checkout"
    ENTER_EMAIL = "enter_email"
    ENTER_SHIPPING = "enter_shipping"
    SELECT_SHIPPING_METHOD = "select_shipping_method"
    ENTER_BILLING = "enter_billing"
    ENTER_PAYMENT = "enter_payment"
    SUBMIT_ORDER = "submit_order"
    HANDLE_3DS = "handle_3ds"
    HANDLE_CAPTCHA = "handle_captcha"
    CONFIRM_ORDER = "confirm_order"


@dataclass
class CheckoutStepResult:
    step: CheckoutStep
    success: bool
    status_code: int
    response_url: str
    data_extracted: Dict[str, Any]
    error_message: Optional[str] = None
    requires_action: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class CardInfo:
    number: str
    exp_month: str
    exp_year: str
    cvv: str
    holder_name: str = ""
    
    def get_formatted_expiry(self, format: str = "MM/YY") -> str:
        if format == "MM/YY":
            return f"{self.exp_month}/{self.exp_year[-2:]}"
        elif format == "MM/YYYY":
            return f"{self.exp_month}/{self.exp_year}"
        elif format == "MMYY":
            return f"{self.exp_month}{self.exp_year[-2:]}"
        elif format == "YYYY-MM":
            return f"{self.exp_year}-{self.exp_month}"
        return f"{self.exp_month}/{self.exp_year[-2:]}"
    
    def get_bin(self) -> str:
        return self.number[:6]
    
    def get_last_four(self) -> str:
        return self.number[-4:]
    
    def is_valid_luhn(self) -> bool:
        digits = [int(d) for d in self.number if d.isdigit()]
        checksum = 0
        for i, digit in enumerate(reversed(digits)):
            if i % 2 == 1:
                digit *= 2
                if digit > 9:
                    digit -= 9
            checksum += digit
        return checksum % 10 == 0


@dataclass
class BillingInfo:
    first_name: str
    last_name: str
    email: str
    phone: str
    address1: str
    address2: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    country: str = "US"
    
    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "address1": self.address1,
            "address2": self.address2,
            "city": self.city,
            "state": self.state,
            "zip_code": self.zip_code,
            "country": self.country
        }


@dataclass
class ShippingInfo:
    first_name: str
    last_name: str
    address1: str
    address2: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    country: str = "US"
    phone: str = ""
    
    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "address1": self.address1,
            "address2": self.address2,
            "city": self.city,
            "state": self.state,
            "zip_code": self.zip_code,
            "country": self.country,
            "phone": self.phone
        }


class CheckoutSessionManager:
    def __init__(self, session_storage_dir: str = "sessions", session_ttl: int = 3600):
        self.http_client = PersistentHTTPClient(session_storage_dir, session_ttl)
        self.behavior = HumanBehaviorSimulator()
        
        self.current_status = CheckoutStatus.INITIALIZED
        self.step_history: List[CheckoutStepResult] = []
        self.extracted_data: Dict[str, Any] = {}
        
        self.card_info: Optional[CardInfo] = None
        self.billing_info: Optional[BillingInfo] = None
        self.shipping_info: Optional[ShippingInfo] = None
        
        self.detected_platform: Optional[str] = None
        self.detected_gateway: Optional[str] = None
        
        self.tokens: Dict[str, str] = {}
        self.nonces: Dict[str, str] = {}
        
    def start_session(self, checkout_url: str, proxy: str = None) -> CheckoutSessionData:
        session = self.http_client.start_checkout_session(
            checkout_url,
            platform=self.detected_platform or "unknown",
            gateway=self.detected_gateway or "unknown",
            proxy=proxy
        )
        
        self.current_status = CheckoutStatus.INITIALIZED
        
        return session
    
    def set_card(self, card: CardInfo):
        self.card_info = card
        if self.http_client.current_checkout_session:
            self.http_client.set_payment_data({
                "card_bin": card.get_bin(),
                "card_last_four": card.get_last_four()
            })
    
    def set_billing(self, billing: BillingInfo):
        self.billing_info = billing
        if self.http_client.current_checkout_session:
            self.http_client.set_billing_data(billing.to_dict())
    
    def set_shipping(self, shipping: ShippingInfo):
        self.shipping_info = shipping
        if self.http_client.current_checkout_session:
            self.http_client.set_shipping_data(shipping.to_dict())
    
    def detect_platform(self, response: HTTPResponse) -> Optional[str]:
        body_lower = response.body.lower()
        headers_str = str(response.headers).lower()
        
        platform_signatures = {
            "shopify": [
                "cdn.shopify.com",
                "shopify.com/checkouts",
                "shopify-payment",
                "data-shopify",
                "shopify.section"
            ],
            "woocommerce": [
                "woocommerce",
                "wc-checkout",
                "wc_checkout",
                "wc-ajax",
                "wc-cart"
            ],
            "bigcommerce": [
                "bigcommerce",
                "bc-checkout",
                "stencil-utils",
                "checkout-sdk"
            ],
            "magento": [
                "magento",
                "mage-",
                "checkout/onepage",
                "firecheckout"
            ],
            "prestashop": [
                "prestashop",
                "presta",
                "ps_checkout"
            ],
            "opencart": [
                "opencart",
                "route=checkout"
            ],
            "squarespace": [
                "squarespace",
                "sqsp"
            ],
            "wix": [
                "wix.com",
                "wixstatic"
            ]
        }
        
        for platform, signatures in platform_signatures.items():
            for sig in signatures:
                if sig in body_lower or sig in headers_str:
                    self.detected_platform = platform
                    return platform
        
        return None
    
    def detect_gateway(self, response: HTTPResponse) -> Optional[str]:
        body_lower = response.body.lower()
        
        gateway_signatures = {
            "stripe": [
                "stripe.com",
                "stripe.js",
                "stripe-js",
                "pk_live_",
                "pk_test_",
                "stripe.createToken",
                "stripe.confirmCardPayment"
            ],
            "braintree": [
                "braintree",
                "braintreegateway",
                "braintree-web",
                "client-token",
                "braintree.setup"
            ],
            "paypal": [
                "paypal.com",
                "paypalobjects",
                "paypal-checkout"
            ],
            "square": [
                "squareup.com",
                "square.js",
                "sq-payment"
            ],
            "authorize_net": [
                "authorize.net",
                "acceptjs",
                "accept.js"
            ],
            "adyen": [
                "adyen.com",
                "adyen-checkout",
                "adyencheckout"
            ],
            "worldpay": [
                "worldpay",
                "wp-hosted"
            ],
            "cybersource": [
                "cybersource",
                "flex-microform"
            ]
        }
        
        for gateway, signatures in gateway_signatures.items():
            for sig in signatures:
                if sig in body_lower:
                    self.detected_gateway = gateway
                    return gateway
        
        return None
    
    def extract_tokens(self, response: HTTPResponse) -> Dict[str, str]:
        tokens = {}
        body = response.body
        
        csrf_patterns = [
            r'name=["\']csrf[_-]?token["\'][^>]*value=["\']([^"\']+)["\']',
            r'name=["\']_csrf["\'][^>]*value=["\']([^"\']+)["\']',
            r'name=["\']csrfmiddlewaretoken["\'][^>]*value=["\']([^"\']+)["\']',
            r'name=["\']authenticity_token["\'][^>]*value=["\']([^"\']+)["\']',
            r'"csrf[_-]?token":\s*["\']([^"\']+)["\']',
            r'csrf[_-]?token["\']?\s*[:=]\s*["\']([^"\']+)["\']'
        ]
        
        for pattern in csrf_patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                tokens["csrf_token"] = match.group(1)
                self.http_client.set_csrf_token("csrf_token", match.group(1))
                break
        
        nonce_patterns = [
            r'name=["\']woocommerce[_-]?nonce["\'][^>]*value=["\']([^"\']+)["\']',
            r'name=["\']_wpnonce["\'][^>]*value=["\']([^"\']+)["\']',
            r'"nonce":\s*["\']([^"\']+)["\']',
            r'nonce["\']?\s*[:=]\s*["\']([^"\']+)["\']'
        ]
        
        for pattern in nonce_patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                tokens["nonce"] = match.group(1)
                self.http_client.set_nonce("nonce", match.group(1))
                break
        
        stripe_patterns = [
            r'pk_(?:live|test)_[a-zA-Z0-9]+',
            r'"publishableKey":\s*["\']([^"\']+)["\']',
            r'data-key=["\']([^"\']+)["\']'
        ]
        
        for pattern in stripe_patterns:
            match = re.search(pattern, body)
            if match:
                key = match.group(1) if match.lastindex else match.group(0)
                tokens["stripe_publishable_key"] = key
                break
        
        braintree_patterns = [
            r'"clientToken":\s*["\']([^"\']+)["\']',
            r'braintree\.setup\(["\']([^"\']+)["\']',
            r'data-braintree-token=["\']([^"\']+)["\']'
        ]
        
        for pattern in braintree_patterns:
            match = re.search(pattern, body)
            if match:
                tokens["braintree_client_token"] = match.group(1)
                break
        
        checkout_token_patterns = [
            r'"checkoutToken":\s*["\']([^"\']+)["\']',
            r'"checkout_token":\s*["\']([^"\']+)["\']',
            r'checkout/([a-f0-9]{32})',
            r'/checkouts/([^/\?"]+)'
        ]
        
        for pattern in checkout_token_patterns:
            match = re.search(pattern, body)
            if match:
                tokens["checkout_token"] = match.group(1)
                self.http_client.set_checkout_token(match.group(1))
                break
        
        cart_patterns = [
            r'"cart_token":\s*["\']([^"\']+)["\']',
            r'"cartToken":\s*["\']([^"\']+)["\']',
            r'cart/([a-f0-9]+)'
        ]
        
        for pattern in cart_patterns:
            match = re.search(pattern, body)
            if match:
                tokens["cart_token"] = match.group(1)
                self.http_client.set_cart_data(cart_token=match.group(1))
                break
        
        self.tokens.update(tokens)
        return tokens
    
    def extract_form_data(self, response: HTTPResponse) -> Dict[str, Any]:
        forms = {}
        body = response.body
        
        form_pattern = r'<form[^>]*>(.*?)</form>'
        form_matches = re.findall(form_pattern, body, re.DOTALL | re.IGNORECASE)
        
        for i, form_content in enumerate(form_matches):
            form_data = {}
            
            input_pattern = r'<input[^>]*name=["\']([^"\']+)["\'][^>]*(?:value=["\']([^"\']*)["\'])?[^>]*>'
            inputs = re.findall(input_pattern, form_content, re.IGNORECASE)
            
            for name, value in inputs:
                form_data[name] = value
            
            select_pattern = r'<select[^>]*name=["\']([^"\']+)["\'][^>]*>.*?<option[^>]*selected[^>]*value=["\']([^"\']*)["\']'
            selects = re.findall(select_pattern, form_content, re.DOTALL | re.IGNORECASE)
            
            for name, value in selects:
                form_data[name] = value
            
            if form_data:
                forms[f"form_{i}"] = form_data
        
        self.extracted_data["forms"] = forms
        return forms
    
    def extract_product_info(self, response: HTTPResponse) -> Dict[str, Any]:
        product = {}
        body = response.body
        
        price_patterns = [
            r'"price":\s*["\']?(\d+\.?\d*)["\']?',
            r'class=["\'][^"\']*price[^"\']*["\'][^>]*>\s*\$?(\d+\.?\d*)',
            r'\$(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*USD'
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, body)
            if match:
                product["price"] = float(match.group(1))
                break
        
        title_patterns = [
            r'"name":\s*["\']([^"\']+)["\']',
            r'"product_title":\s*["\']([^"\']+)["\']',
            r'<h1[^>]*class=["\'][^"\']*product[^"\']*["\'][^>]*>([^<]+)</h1>',
            r'<title>([^<]+)</title>'
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, body)
            if match:
                product["title"] = match.group(1).strip()
                break
        
        sku_patterns = [
            r'"sku":\s*["\']([^"\']+)["\']',
            r'"product_id":\s*["\']?(\d+)["\']?',
            r'data-product-id=["\'](\d+)["\']'
        ]
        
        for pattern in sku_patterns:
            match = re.search(pattern, body)
            if match:
                product["sku"] = match.group(1)
                break
        
        self.extracted_data["product"] = product
        return product
    
    def execute_step(self, step: CheckoutStep, url: str = None, 
                     data: Dict[str, Any] = None, method: str = "GET") -> CheckoutStepResult:
        
        self.behavior.random_delay(0.5, 2.0)
        
        try:
            if method == "GET":
                response = self.http_client.get(url, request_type="navigate")
            elif method == "POST":
                if data and any(key in str(data) for key in ["card", "payment", "stripe"]):
                    response = self.http_client.post(url, json_data=data, request_type="json")
                else:
                    response = self.http_client.post(url, data=data, request_type="form")
            else:
                response = self.http_client.get(url, request_type="navigate")
            
            self.detect_platform(response)
            self.detect_gateway(response)
            self.extract_tokens(response)
            
            success = 200 <= response.status_code < 400
            error_message = None
            requires_action = None
            
            if self._check_captcha_required(response):
                requires_action = "captcha"
                self.current_status = CheckoutStatus.CAPTCHA_REQUIRED
            elif self._check_3ds_required(response):
                requires_action = "3ds"
                self.current_status = CheckoutStatus.THREE_DS_REQUIRED
            elif self._check_declined(response):
                success = False
                error_message = self._extract_decline_reason(response)
                self.current_status = CheckoutStatus.DECLINED
            elif success:
                self._update_status_for_step(step)
            
            result = CheckoutStepResult(
                step=step,
                success=success,
                status_code=response.status_code,
                response_url=response.url,
                data_extracted=self.extracted_data.copy(),
                error_message=error_message,
                requires_action=requires_action
            )
            
            self.step_history.append(result)
            
            return result
            
        except Exception as e:
            result = CheckoutStepResult(
                step=step,
                success=False,
                status_code=0,
                response_url=url or "",
                data_extracted={},
                error_message=str(e)
            )
            
            self.step_history.append(result)
            self.current_status = CheckoutStatus.FAILED
            
            return result
    
    def _check_captcha_required(self, response: HTTPResponse) -> bool:
        captcha_indicators = [
            "hcaptcha",
            "recaptcha",
            "captcha",
            "g-recaptcha",
            "h-captcha",
            "cf-turnstile",
            "challenge-form"
        ]
        
        body_lower = response.body.lower()
        return any(indicator in body_lower for indicator in captcha_indicators)
    
    def _check_3ds_required(self, response: HTTPResponse) -> bool:
        three_ds_indicators = [
            "3d-secure",
            "3ds",
            "three_d_secure",
            "threeDSecure",
            "acs_url",
            "acsUrl",
            "pareq",
            "creq",
            "challenge_url"
        ]
        
        body_lower = response.body.lower()
        return any(indicator.lower() in body_lower for indicator in three_ds_indicators)
    
    def _check_declined(self, response: HTTPResponse) -> bool:
        decline_indicators = [
            "declined",
            "card_declined",
            "insufficient_funds",
            "do_not_honor",
            "invalid_card",
            "expired_card",
            "incorrect_cvc",
            "payment failed",
            "transaction failed",
            "unable to process"
        ]
        
        body_lower = response.body.lower()
        return any(indicator in body_lower for indicator in decline_indicators)
    
    def _extract_decline_reason(self, response: HTTPResponse) -> str:
        decline_patterns = [
            r'"error":\s*["\']([^"\']+)["\']',
            r'"message":\s*["\']([^"\']+)["\']',
            r'"decline_code":\s*["\']([^"\']+)["\']',
            r'class=["\'][^"\']*error[^"\']*["\'][^>]*>([^<]+)<'
        ]
        
        for pattern in decline_patterns:
            match = re.search(pattern, response.body, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return "Payment declined"
    
    def _update_status_for_step(self, step: CheckoutStep):
        status_map = {
            CheckoutStep.VISIT_SITE: CheckoutStatus.BROWSING,
            CheckoutStep.BROWSE_PRODUCTS: CheckoutStatus.BROWSING,
            CheckoutStep.VIEW_PRODUCT: CheckoutStatus.PRODUCT_PAGE,
            CheckoutStep.ADD_TO_CART: CheckoutStatus.CART,
            CheckoutStep.VIEW_CART: CheckoutStatus.CART,
            CheckoutStep.INITIATE_CHECKOUT: CheckoutStatus.CHECKOUT_STARTED,
            CheckoutStep.ENTER_EMAIL: CheckoutStatus.CHECKOUT_STARTED,
            CheckoutStep.ENTER_SHIPPING: CheckoutStatus.SHIPPING_INFO,
            CheckoutStep.SELECT_SHIPPING_METHOD: CheckoutStatus.SHIPPING_INFO,
            CheckoutStep.ENTER_BILLING: CheckoutStatus.BILLING_INFO,
            CheckoutStep.ENTER_PAYMENT: CheckoutStatus.PAYMENT_INFO,
            CheckoutStep.SUBMIT_ORDER: CheckoutStatus.PROCESSING,
            CheckoutStep.HANDLE_3DS: CheckoutStatus.THREE_DS_REQUIRED,
            CheckoutStep.HANDLE_CAPTCHA: CheckoutStatus.CAPTCHA_REQUIRED,
            CheckoutStep.CONFIRM_ORDER: CheckoutStatus.COMPLETED
        }
        
        if step in status_map:
            self.current_status = status_map[step]
    
    def get_session_summary(self) -> Dict[str, Any]:
        return {
            "status": self.current_status.value,
            "platform": self.detected_platform,
            "gateway": self.detected_gateway,
            "steps_completed": len(self.step_history),
            "tokens_found": list(self.tokens.keys()),
            "last_step": self.step_history[-1].step.value if self.step_history else None,
            "errors": [s.error_message for s in self.step_history if s.error_message]
        }
    
    def end_session(self, status: str = None):
        final_status = status or self.current_status.value
        self.http_client.end_checkout_session(final_status)
    
    def export_session_data(self, filepath: str = None) -> str:
        return self.http_client.export_session(filepath)


class CheckoutFlowExecutor:
    def __init__(self, session_manager: CheckoutSessionManager):
        self.session = session_manager
        self.flow_steps: List[Tuple[CheckoutStep, str, Dict]] = []
        
    def add_step(self, step: CheckoutStep, url: str, data: Dict = None, method: str = "GET"):
        self.flow_steps.append((step, url, data or {}, method))
    
    def execute_flow(self) -> List[CheckoutStepResult]:
        results = []
        
        for step, url, data, method in self.flow_steps:
            result = self.session.execute_step(step, url, data, method)
            results.append(result)
            
            if not result.success:
                break
            
            if result.requires_action:
                break
        
        return results
    
    def create_shopify_flow(self, checkout_url: str, product_url: str = None):
        self.flow_steps = []
        
        if product_url:
            self.add_step(CheckoutStep.VIEW_PRODUCT, product_url)
        
        self.add_step(CheckoutStep.INITIATE_CHECKOUT, checkout_url)
    
    def create_woocommerce_flow(self, site_url: str, product_id: str = None):
        self.flow_steps = []
        
        self.add_step(CheckoutStep.VISIT_SITE, site_url)
        
        if product_id:
            self.add_step(
                CheckoutStep.ADD_TO_CART,
                f"{site_url}/?add-to-cart={product_id}",
                method="POST"
            )
        
        self.add_step(CheckoutStep.VIEW_CART, f"{site_url}/cart/")
        self.add_step(CheckoutStep.INITIATE_CHECKOUT, f"{site_url}/checkout/")
