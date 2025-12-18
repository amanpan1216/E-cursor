import re
import json
import time
import random
import argparse
import sys
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse

from core.browser import (
    BrowserProfile,
    BrowserFingerprintGenerator,
    SessionManager
)

from core.behavior import (
    HumanBehaviorSimulator,
    TypingSimulator,
    MouseMovementSimulator,
    FormInteractionSimulator,
    PageInteractionSimulator
)

from core.http_client import (
    AdvancedHTTPClient,
    ProxyManager,
    RedirectHandler
)

from platforms.woocommerce import (
    WooCommerceDetector,
    WooCommerceHandler
)

from platforms.bigcommerce import (
    BigCommerceDetector,
    BigCommerceHandler
)

from platforms.shopify import (
    ShopifyDetector,
    ShopifyHandler
)

from gateways.stripe import (
    StripeCard,
    StripeDetector,
    StripeGatewayHandler,
    StripeCheckoutHandler
)

from gateways.braintree import (
    BraintreeCard,
    BraintreeDetector,
    BraintreeGatewayHandler,
    BraintreeDropInHandler
)

from solvers.captcha import (
    CaptchaDetector,
    CaptchaSolverManager,
    TwoCaptchaSolver,
    AntiCaptchaSolver,
    CapMonsterSolver
)

from solvers.three_ds import (
    ThreeDSManager,
    ThreeDSDetector
)

from utils.utils import (
    CardInfo,
    BillingInfo,
    ShippingInfo,
    CardValidator,
    CardParser,
    AddressGenerator,
    URLUtils,
    HashUtils,
    TimeUtils,
    JSONUtils,
    FileUtils,
    ResultLogger
)


@dataclass
class CheckoutConfig:
    target_url: str
    card_file: str
    proxy_file: Optional[str] = None
    captcha_api_key: Optional[str] = None
    captcha_service: str = "2captcha"
    use_3ds: bool = True
    generate_billing: bool = True
    billing_country: str = "US"
    max_retries: int = 3
    delay_between_cards: float = 2.0
    log_dir: str = "logs"
    verbose: bool = True


@dataclass
class CheckoutResult:
    success: bool
    card: str
    platform: str
    gateway: str
    order_id: Optional[str] = None
    error: Optional[str] = None
    requires_action: bool = False
    action_type: Optional[str] = None
    elapsed_time: float = 0


class PlatformDetector:
    def __init__(self, http_client: AdvancedHTTPClient):
        self.http_client = http_client
        self.woo_detector = WooCommerceDetector(http_client)
        self.bc_detector = BigCommerceDetector(http_client)
        self.shopify_detector = ShopifyDetector(http_client)
        
    def detect(self, url: str) -> Tuple[str, Dict[str, Any]]:
        response = self.http_client.get(url)
        
        if response.status_code != 200:
            return "unknown", {}
        
        is_woo, woo_info = self.woo_detector.detect(url)
        if is_woo:
            return "woocommerce", woo_info
        
        is_bc, bc_info = self.bc_detector.detect(url)
        if is_bc:
            return "bigcommerce", bc_info
        
        is_shopify, shopify_info = self.shopify_detector.detect(url)
        if is_shopify:
            return "shopify", shopify_info
        
        return "unknown", {}


class GatewayDetector:
    def __init__(self, http_client: AdvancedHTTPClient):
        self.http_client = http_client
        self.stripe_detector = StripeDetector(http_client)
        self.braintree_detector = BraintreeDetector(http_client)
        
    def detect(self, html: str) -> Tuple[str, Dict[str, Any]]:
        is_stripe, stripe_info = self.stripe_detector.detect(html)
        if is_stripe:
            return "stripe", stripe_info
        
        is_braintree, braintree_info = self.braintree_detector.detect(html)
        if is_braintree:
            return "braintree", braintree_info
        
        return "unknown", {}


class CheckoutAutomation:
    def __init__(self, config: CheckoutConfig):
        self.config = config
        self.session_manager = SessionManager()
        self.http_client = AdvancedHTTPClient(self.session_manager)
        self.behavior = HumanBehaviorSimulator()
        self.platform_detector = PlatformDetector(self.http_client)
        self.gateway_detector = GatewayDetector(self.http_client)
        self.card_parser = CardParser()
        self.address_generator = AddressGenerator()
        self.logger = ResultLogger(config.log_dir)
        
        self.proxy_manager = None
        if config.proxy_file:
            self.proxy_manager = ProxyManager()
            proxies = FileUtils.read_lines(config.proxy_file)
            for proxy in proxies:
                self.proxy_manager.add_proxy(proxy)
        
        self.captcha_manager = None
        if config.captcha_api_key:
            self.captcha_manager = CaptchaSolverManager(self.http_client)
            
            if config.captcha_service == "2captcha":
                solver = TwoCaptchaSolver(config.captcha_api_key)
                self.captcha_manager.add_solver("2captcha", solver)
            elif config.captcha_service == "anticaptcha":
                solver = AntiCaptchaSolver(config.captcha_api_key)
                self.captcha_manager.add_solver("anticaptcha", solver)
            elif config.captcha_service == "capmonster":
                solver = CapMonsterSolver(config.captcha_api_key)
                self.captcha_manager.add_solver("capmonster", solver)
        
        self.three_ds_manager = ThreeDSManager(self.http_client)
        
        self.platform_handler = None
        self.gateway_handler = None
        self.platform_type = None
        self.gateway_type = None
        self.gateway_info = {}
        
    def log(self, message: str, level: str = "INFO"):
        if self.config.verbose:
            timestamp = TimeUtils.iso_format()
            print(f"[{timestamp}] [{level}] {message}")
    
    def initialize(self) -> bool:
        self.log(f"Initializing checkout automation for: {self.config.target_url}")
        
        self.http_client.create_session()
        
        self.platform_type, platform_info = self.platform_detector.detect(self.config.target_url)
        self.log(f"Detected platform: {self.platform_type}")
        
        if self.platform_type == "woocommerce":
            self.platform_handler = WooCommerceHandler(self.http_client)
        elif self.platform_type == "bigcommerce":
            self.platform_handler = BigCommerceHandler(self.http_client)
        elif self.platform_type == "shopify":
            self.platform_handler = ShopifyHandler(self.http_client)
        else:
            self.log(f"Unsupported platform: {self.platform_type}", "ERROR")
            return False
        
        if not self.platform_handler.initialize(self.config.target_url):
            self.log("Failed to initialize platform handler", "ERROR")
            return False
        
        return True
    
    def detect_gateway(self, html: str) -> bool:
        self.gateway_type, self.gateway_info = self.gateway_detector.detect(html)
        self.log(f"Detected gateway: {self.gateway_type}")
        
        if self.gateway_type == "stripe":
            publishable_key = self.gateway_info.get("publishable_key")
            if publishable_key:
                self.gateway_handler = StripeGatewayHandler(self.http_client, publishable_key)
                self.gateway_handler.initialize()
                return True
        
        elif self.gateway_type == "braintree":
            client_token = self.gateway_info.get("client_token")
            if client_token:
                self.gateway_handler = BraintreeGatewayHandler(self.http_client, client_token)
                self.gateway_handler.initialize()
                return True
        
        return False
    
    def load_cards(self) -> List[CardInfo]:
        cards = self.card_parser.parse_file(self.config.card_file)
        self.log(f"Loaded {len(cards)} cards from file")
        return cards
    
    def generate_billing_info(self) -> BillingInfo:
        return self.address_generator.generate_billing(self.config.billing_country)
    
    def generate_shipping_info(self) -> ShippingInfo:
        return self.address_generator.generate_shipping(self.config.billing_country)
    
    def process_card_woocommerce(self, card: CardInfo, billing: BillingInfo, 
                                  shipping: ShippingInfo = None) -> CheckoutResult:
        start_time = time.time()
        result = CheckoutResult(
            success=False,
            card=f"{card.bin}...{card.last4}",
            platform="woocommerce",
            gateway=self.gateway_type
        )
        
        try:
            products = self.platform_handler.browse_products()
            
            if not products:
                result.error = "No products found"
                return result
            
            product = random.choice(products)
            self.log(f"Selected product: {product.name}")
            
            self.behavior.human_delay(action_type="reading")
            
            product_details = self.platform_handler.get_product_details(product.url)
            if not product_details:
                result.error = "Could not get product details"
                return result
            
            if not self.platform_handler.add_to_cart(product_details):
                result.error = "Failed to add product to cart"
                return result
            
            self.log("Product added to cart")
            self.behavior.human_delay(action_type="navigation")
            
            cart = self.platform_handler.get_cart()
            if not cart or not cart.items:
                result.error = "Cart is empty"
                return result
            
            checkout = self.platform_handler.proceed_to_checkout()
            if not checkout:
                result.error = "Failed to proceed to checkout"
                return result
            
            self.log("Proceeding to checkout")
            
            checkout_response = self.http_client.get(checkout.checkout_url)
            self.detect_gateway(checkout_response.body)
            
            if self.captcha_manager:
                captcha_challenges = self.captcha_manager.detect_captcha(
                    checkout_response.body, 
                    checkout.checkout_url
                )
                if captcha_challenges:
                    self.log(f"Detected {len(captcha_challenges)} captcha(s)")
                    solutions = self.captcha_manager.solve_all(captcha_challenges)
                    if not solutions:
                        result.error = "Failed to solve captcha"
                        return result
            
            billing_dict = self.address_generator.billing_to_dict(billing)
            shipping_dict = self.address_generator.shipping_to_dict(shipping) if shipping else None
            
            payment_data = {}
            
            if self.gateway_type == "stripe" and self.gateway_handler:
                stripe_card = StripeCard(
                    number=card.number,
                    exp_month=card.exp_month,
                    exp_year=card.exp_year[-2:],
                    cvc=card.cvv,
                    name=f"{billing.first_name} {billing.last_name}"
                )
                
                billing_details = {
                    "name": f"{billing.first_name} {billing.last_name}",
                    "email": billing.email,
                    "phone": billing.phone,
                    "address": {
                        "line1": billing.address_1,
                        "line2": billing.address_2,
                        "city": billing.city,
                        "state": billing.state,
                        "postal_code": billing.postcode,
                        "country": billing.country
                    }
                }
                
                payment_method = self.gateway_handler.create_payment_method(stripe_card, billing_details)
                
                if payment_method:
                    payment_data["stripe_source"] = payment_method.id
                    payment_data["payment_method"] = "stripe"
                else:
                    stripe_token = self.gateway_handler.create_token(stripe_card)
                    if stripe_token:
                        payment_data["stripe_token"] = stripe_token
                        payment_data["payment_method"] = "stripe"
                    else:
                        result.error = "Failed to create Stripe payment method"
                        return result
            
            elif self.gateway_type == "braintree" and self.gateway_handler:
                braintree_card = BraintreeCard(
                    number=card.number,
                    exp_month=card.exp_month,
                    exp_year=card.exp_year,
                    cvv=card.cvv,
                    cardholder_name=f"{billing.first_name} {billing.last_name}",
                    postal_code=billing.postcode
                )
                
                nonce_result = self.gateway_handler.tokenize_card(braintree_card)
                
                if nonce_result:
                    payment_data["payment_method_nonce"] = nonce_result.nonce
                    payment_data["device_data"] = self.gateway_handler.get_device_data()
                    payment_data["payment_method"] = "braintree_credit_card"
                else:
                    result.error = "Failed to tokenize Braintree card"
                    return result
            
            self.behavior.human_delay(action_type="form_submission")
            
            order_result = self.platform_handler.submit_order(
                billing_dict,
                shipping_dict,
                payment_data.get("payment_method"),
                payment_data
            )
            
            if order_result.get("success"):
                result.success = True
                result.order_id = order_result.get("order_id")
                self.log(f"Order successful! Order ID: {result.order_id}")
            
            elif order_result.get("requires_action"):
                result.requires_action = True
                result.action_type = order_result.get("action_type")
                
                if result.action_type == "3ds" and self.config.use_3ds:
                    self.log("3DS authentication required")
                    
                    action_data = order_result.get("action_data", {})
                    client_secret = action_data.get("client_secret")
                    
                    if client_secret and self.gateway_type == "stripe":
                        three_ds_result = self.gateway_handler.confirm_payment_intent(
                            client_secret,
                            payment_data.get("stripe_source"),
                            action_data.get("return_url")
                        )
                        
                        if three_ds_result.get("success"):
                            result.success = True
                            self.log("3DS authentication successful")
                        elif three_ds_result.get("requires_action"):
                            result.error = "Manual 3DS challenge required"
                        else:
                            result.error = three_ds_result.get("error", "3DS failed")
                    else:
                        result.error = "3DS handling not implemented for this gateway"
                else:
                    result.error = f"Action required: {result.action_type}"
            
            else:
                result.error = order_result.get("error", "Order failed")
        
        except Exception as e:
            result.error = str(e)
            self.log(f"Exception: {e}", "ERROR")
        
        result.elapsed_time = time.time() - start_time
        return result
    
    def process_card_shopify(self, card: CardInfo, billing: BillingInfo,
                              shipping: ShippingInfo = None) -> CheckoutResult:
        start_time = time.time()
        result = CheckoutResult(
            success=False,
            card=f"{card.bin}...{card.last4}",
            platform="shopify",
            gateway=self.gateway_type
        )
        
        try:
            products = self.platform_handler.browse_products()
            
            if not products:
                result.error = "No products found"
                return result
            
            product = random.choice(products)
            self.log(f"Selected product: {product.name}")
            
            self.behavior.human_delay(action_type="reading")
            
            product_details = self.platform_handler.get_product_details(product.url)
            if not product_details:
                result.error = "Could not get product details"
                return result
            
            if not self.platform_handler.add_to_cart(product_details):
                result.error = "Failed to add product to cart"
                return result
            
            self.log("Product added to cart")
            self.behavior.human_delay(action_type="navigation")
            
            cart = self.platform_handler.get_cart()
            if not cart or not cart.items:
                result.error = "Cart is empty"
                return result
            
            checkout = self.platform_handler.proceed_to_checkout()
            if not checkout:
                result.error = "Failed to proceed to checkout"
                return result
            
            self.log("Proceeding to checkout")
            
            checkout_response = self.http_client.get(checkout.checkout_url)
            self.detect_gateway(checkout_response.body)
            
            billing_dict = self.address_generator.billing_to_dict(billing)
            shipping_dict = self.address_generator.shipping_to_dict(shipping) if shipping else billing_dict
            
            payment_data = {}
            
            if self.gateway_type == "stripe" and self.gateway_handler:
                stripe_card = StripeCard(
                    number=card.number,
                    exp_month=card.exp_month,
                    exp_year=card.exp_year[-2:],
                    cvc=card.cvv,
                    name=f"{billing.first_name} {billing.last_name}"
                )
                
                stripe_token = self.gateway_handler.create_token(stripe_card)
                if stripe_token:
                    payment_data["s"] = stripe_token
                else:
                    result.error = "Failed to create Stripe token"
                    return result
            
            self.behavior.human_delay(action_type="form_submission")
            
            order_result = self.platform_handler.submit_order(
                billing.email,
                billing_dict,
                shipping_dict,
                payment_data
            )
            
            if order_result.get("success"):
                result.success = True
                result.order_id = order_result.get("order_id")
                self.log(f"Order successful! Order ID: {result.order_id}")
            
            elif order_result.get("requires_action"):
                result.requires_action = True
                result.action_type = order_result.get("action_type")
                result.error = f"Action required: {result.action_type}"
            
            else:
                result.error = order_result.get("error", "Order failed")
        
        except Exception as e:
            result.error = str(e)
            self.log(f"Exception: {e}", "ERROR")
        
        result.elapsed_time = time.time() - start_time
        return result
    
    def process_card_bigcommerce(self, card: CardInfo, billing: BillingInfo,
                                   shipping: ShippingInfo = None) -> CheckoutResult:
        start_time = time.time()
        result = CheckoutResult(
            success=False,
            card=f"{card.bin}...{card.last4}",
            platform="bigcommerce",
            gateway=self.gateway_type
        )
        
        try:
            products = self.platform_handler.browse_products()
            
            if not products:
                result.error = "No products found"
                return result
            
            product = random.choice(products)
            self.log(f"Selected product: {product.name}")
            
            self.behavior.human_delay(action_type="reading")
            
            product_details = self.platform_handler.get_product_details(product.url)
            if not product_details:
                result.error = "Could not get product details"
                return result
            
            if not self.platform_handler.add_to_cart(product_details):
                result.error = "Failed to add product to cart"
                return result
            
            self.log("Product added to cart")
            self.behavior.human_delay(action_type="navigation")
            
            cart = self.platform_handler.get_cart()
            if not cart or not cart.items:
                result.error = "Cart is empty"
                return result
            
            checkout = self.platform_handler.proceed_to_checkout()
            if not checkout:
                result.error = "Failed to proceed to checkout"
                return result
            
            self.log("Proceeding to checkout")
            
            checkout_response = self.http_client.get(checkout.checkout_url)
            self.detect_gateway(checkout_response.body)
            
            billing_dict = self.address_generator.billing_to_dict(billing)
            shipping_dict = self.address_generator.shipping_to_dict(shipping) if shipping else None
            
            payment_data = {}
            
            if self.gateway_type == "stripe" and self.gateway_handler:
                stripe_card = StripeCard(
                    number=card.number,
                    exp_month=card.exp_month,
                    exp_year=card.exp_year[-2:],
                    cvc=card.cvv,
                    name=f"{billing.first_name} {billing.last_name}"
                )
                
                stripe_token = self.gateway_handler.create_token(stripe_card)
                if stripe_token:
                    payment_data["stripe_token"] = stripe_token
                else:
                    result.error = "Failed to create Stripe token"
                    return result
            
            self.behavior.human_delay(action_type="form_submission")
            
            order_result = self.platform_handler.submit_order(
                billing_dict,
                shipping_dict,
                None,
                payment_data
            )
            
            if order_result.get("success"):
                result.success = True
                result.order_id = order_result.get("order_id")
                self.log(f"Order successful! Order ID: {result.order_id}")
            
            elif order_result.get("requires_action"):
                result.requires_action = True
                result.action_type = order_result.get("action_type")
                result.error = f"Action required: {result.action_type}"
            
            else:
                result.error = order_result.get("error", "Order failed")
        
        except Exception as e:
            result.error = str(e)
            self.log(f"Exception: {e}", "ERROR")
        
        result.elapsed_time = time.time() - start_time
        return result
    
    def process_card(self, card: CardInfo) -> CheckoutResult:
        billing = self.generate_billing_info() if self.config.generate_billing else None
        shipping = self.generate_shipping_info() if self.config.generate_billing else None
        
        self.log(f"Processing card: {card.bin}...{card.last4}")
        
        if self.platform_type == "woocommerce":
            return self.process_card_woocommerce(card, billing, shipping)
        elif self.platform_type == "shopify":
            return self.process_card_shopify(card, billing, shipping)
        elif self.platform_type == "bigcommerce":
            return self.process_card_bigcommerce(card, billing, shipping)
        else:
            return CheckoutResult(
                success=False,
                card=f"{card.bin}...{card.last4}",
                platform=self.platform_type,
                gateway="unknown",
                error=f"Unsupported platform: {self.platform_type}"
            )
    
    def run(self) -> List[CheckoutResult]:
        results = []
        
        if not self.initialize():
            self.log("Initialization failed", "ERROR")
            return results
        
        cards = self.load_cards()
        
        if not cards:
            self.log("No cards to process", "ERROR")
            return results
        
        total_cards = len(cards)
        
        for index, card in enumerate(cards, 1):
            self.log(f"Processing card {index}/{total_cards}")
            
            for attempt in range(self.config.max_retries):
                result = self.process_card(card)
                
                if result.success:
                    self.logger.log_success(
                        f"{card.number}|{card.exp_month}|{card.exp_year}|{card.cvv}",
                        self.config.target_url,
                        f"Order ID: {result.order_id}"
                    )
                    break
                
                elif result.requires_action:
                    self.logger.log_failure(
                        f"{card.number}|{card.exp_month}|{card.exp_year}|{card.cvv}",
                        self.config.target_url,
                        f"Requires action: {result.action_type}"
                    )
                    break
                
                else:
                    if attempt < self.config.max_retries - 1:
                        self.log(f"Attempt {attempt + 1} failed, retrying...")
                        time.sleep(2)
                    else:
                        self.logger.log_failure(
                            f"{card.number}|{card.exp_month}|{card.exp_year}|{card.cvv}",
                            self.config.target_url,
                            result.error
                        )
            
            results.append(result)
            
            if index < total_cards:
                delay = self.config.delay_between_cards + random.uniform(-0.5, 0.5)
                self.log(f"Waiting {delay:.1f}s before next card...")
                time.sleep(delay)
        
        stats = self.logger.get_stats()
        self.log(f"Completed! Success: {stats['success']}, Failure: {stats['failure']}, Errors: {stats['errors']}")
        
        return results


def main():
    parser = argparse.ArgumentParser(description="Hyper-Realistic Multi-Platform Checkout Automation")
    
    parser.add_argument("--url", "-u", required=True, help="Target checkout URL")
    parser.add_argument("--cards", "-c", required=True, help="Path to card file")
    parser.add_argument("--proxies", "-p", help="Path to proxy file")
    parser.add_argument("--captcha-key", help="Captcha solving API key")
    parser.add_argument("--captcha-service", default="2captcha", 
                        choices=["2captcha", "anticaptcha", "capmonster"],
                        help="Captcha solving service")
    parser.add_argument("--no-3ds", action="store_true", help="Disable 3DS handling")
    parser.add_argument("--no-billing", action="store_true", help="Don't generate random billing info")
    parser.add_argument("--country", default="US", help="Billing country code")
    parser.add_argument("--retries", type=int, default=3, help="Max retries per card")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between cards (seconds)")
    parser.add_argument("--log-dir", default="logs", help="Log directory")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet mode")
    
    args = parser.parse_args()
    
    config = CheckoutConfig(
        target_url=args.url,
        card_file=args.cards,
        proxy_file=args.proxies,
        captcha_api_key=args.captcha_key,
        captcha_service=args.captcha_service,
        use_3ds=not args.no_3ds,
        generate_billing=not args.no_billing,
        billing_country=args.country,
        max_retries=args.retries,
        delay_between_cards=args.delay,
        log_dir=args.log_dir,
        verbose=not args.quiet
    )
    
    automation = CheckoutAutomation(config)
    results = automation.run()
    
    success_count = sum(1 for r in results if r.success)
    failure_count = len(results) - success_count
    
    print(f"\n{'='*50}")
    print(f"RESULTS SUMMARY")
    print(f"{'='*50}")
    print(f"Total Cards: {len(results)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {failure_count}")
    print(f"Success Rate: {(success_count/len(results)*100):.1f}%" if results else "N/A")
    print(f"{'='*50}")
    
    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
