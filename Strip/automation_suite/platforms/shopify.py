import re
import json
import time
import random
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse, urljoin, parse_qs
from bs4 import BeautifulSoup
from dataclasses import dataclass

from ..core.http_client import AdvancedHTTPClient, HTTPResponse
from ..core.behavior import HumanBehaviorSimulator, FormInteractionSimulator, Point


@dataclass
class ShopifyProduct:
    product_id: str
    variant_id: str
    name: str
    price: float
    url: str
    handle: str
    quantity: int = 1


@dataclass
class ShopifyCart:
    token: str
    items: List[ShopifyProduct]
    subtotal: float
    total: float
    currency: str
    item_count: int


@dataclass
class ShopifyCheckout:
    checkout_token: str
    checkout_url: str
    web_url: str
    order_id: Optional[str] = None
    payment_due: float = 0
    shipping_rates: List[Dict] = None


class ShopifyDetector:
    def __init__(self, http_client: AdvancedHTTPClient):
        self.http_client = http_client
        
    def detect(self, url: str) -> Tuple[bool, Dict[str, Any]]:
        response = self.http_client.get(url)
        
        if response.status_code != 200:
            return False, {}
        
        indicators = {
            "is_shopify": False,
            "shop_name": None,
            "currency": None,
            "payment_gateways": [],
            "features": []
        }
        
        shopify_indicators = [
            'shopify' in response.body.lower(),
            'cdn.shopify.com' in response.body,
            'myshopify.com' in response.body,
            'Shopify.theme' in response.body,
            '/cart.js' in response.body,
            'ShopifyAnalytics' in response.body
        ]
        
        if any(shopify_indicators):
            indicators["is_shopify"] = True
        
        shop_match = re.search(r'"shop"\s*:\s*"([^"]+)"', response.body)
        if shop_match:
            indicators["shop_name"] = shop_match.group(1)
        
        currency_match = re.search(r'"currency"\s*:\s*"([A-Z]{3})"', response.body)
        if currency_match:
            indicators["currency"] = currency_match.group(1)
        
        gateway_patterns = [
            (r'stripe', 'stripe'),
            (r'shopify_payments', 'shopify_payments'),
            (r'paypal', 'paypal'),
            (r'braintree', 'braintree')
        ]
        
        for pattern, gateway in gateway_patterns:
            if re.search(pattern, response.body, re.IGNORECASE):
                indicators["payment_gateways"].append(gateway)
        
        if 'checkout.shopify.com' in response.body:
            indicators["features"].append("hosted_checkout")
        
        return indicators["is_shopify"], indicators


class ShopifyHandler:
    def __init__(self, http_client: AdvancedHTTPClient):
        self.http_client = http_client
        self.behavior = HumanBehaviorSimulator()
        self.form_simulator = FormInteractionSimulator()
        self.base_url = None
        self.shop_name = None
        self.cart = None
        self.checkout = None
        self.session_data = {}
        
    def initialize(self, base_url: str) -> bool:
        self.base_url = base_url.rstrip('/')
        
        response = self.http_client.get(self.base_url)
        if response.status_code != 200:
            return False
        
        self._extract_shop_data(response.body)
        
        self.behavior.human_delay(action_type="page_load")
        
        return True
    
    def _extract_shop_data(self, html: str):
        shop_match = re.search(r'"shop"\s*:\s*"([^"]+)"', html)
        if shop_match:
            self.shop_name = shop_match.group(1)
        
        patterns = [
            (r'"accessToken"\s*:\s*"([^"]+)"', 'access_token'),
            (r'"storefrontAccessToken"\s*:\s*"([^"]+)"', 'storefront_token'),
            (r'"permanentDomain"\s*:\s*"([^"]+)"', 'permanent_domain'),
            (r'"currency"\s*:\s*"([A-Z]{3})"', 'currency'),
            (r'"countryCode"\s*:\s*"([A-Z]{2})"', 'country_code')
        ]
        
        for pattern, key in patterns:
            match = re.search(pattern, html)
            if match:
                self.session_data[key] = match.group(1)
    
    def browse_products(self, collection_url: str = None) -> List[ShopifyProduct]:
        products = []
        
        url = collection_url or f"{self.base_url}/collections/all"
        response = self.http_client.get(url)
        
        if response.status_code != 200:
            return products
        
        self.behavior.human_delay(action_type="reading")
        
        soup = BeautifulSoup(response.body, 'html.parser')
        
        product_cards = soup.find_all(['div', 'article', 'li'], class_=re.compile(r'product|card'))
        
        for card in product_cards:
            try:
                product_id = card.get('data-product-id')
                
                link = card.find('a', href=re.compile(r'/products/'))
                if link:
                    href = link.get('href', '')
                    handle_match = re.search(r'/products/([^/?]+)', href)
                    handle = handle_match.group(1) if handle_match else ''
                    product_url = urljoin(self.base_url, href)
                else:
                    handle = ''
                    product_url = ''
                
                name_elem = card.find(['h2', 'h3', 'a'], class_=re.compile(r'title|name'))
                name = name_elem.get_text(strip=True) if name_elem else "Unknown"
                
                price_elem = card.find(['span', 'div'], class_=re.compile(r'price|money'))
                price_text = price_elem.get_text(strip=True) if price_elem else "0"
                price = float(re.sub(r'[^\d.]', '', price_text) or 0)
                
                variant_id = card.get('data-variant-id', '')
                
                if handle or product_id:
                    products.append(ShopifyProduct(
                        product_id=product_id or '',
                        variant_id=variant_id,
                        name=name,
                        price=price,
                        url=product_url,
                        handle=handle
                    ))
            except Exception:
                continue
        
        return products
    
    def get_product_details(self, product_url: str) -> Optional[ShopifyProduct]:
        response = self.http_client.get(product_url)
        
        if response.status_code != 200:
            return None
        
        self.behavior.human_delay(action_type="reading")
        
        handle_match = re.search(r'/products/([^/?]+)', product_url)
        handle = handle_match.group(1) if handle_match else ''
        
        json_url = f"{self.base_url}/products/{handle}.json"
        json_response = self.http_client.get(json_url)
        
        if json_response.status_code == 200:
            try:
                product_data = json.loads(json_response.body)['product']
                
                first_variant = product_data['variants'][0] if product_data.get('variants') else {}
                
                return ShopifyProduct(
                    product_id=str(product_data.get('id', '')),
                    variant_id=str(first_variant.get('id', '')),
                    name=product_data.get('title', 'Unknown'),
                    price=float(first_variant.get('price', 0)),
                    url=product_url,
                    handle=handle
                )
            except (json.JSONDecodeError, KeyError):
                pass
        
        soup = BeautifulSoup(response.body, 'html.parser')
        
        product_json = soup.find('script', type='application/json', id=re.compile(r'ProductJson'))
        if product_json:
            try:
                product_data = json.loads(product_json.string)
                first_variant = product_data.get('variants', [{}])[0]
                
                return ShopifyProduct(
                    product_id=str(product_data.get('id', '')),
                    variant_id=str(first_variant.get('id', '')),
                    name=product_data.get('title', 'Unknown'),
                    price=float(first_variant.get('price', 0)) / 100,
                    url=product_url,
                    handle=handle
                )
            except (json.JSONDecodeError, KeyError):
                pass
        
        name_elem = soup.find('h1', class_=re.compile(r'product'))
        name = name_elem.get_text(strip=True) if name_elem else "Unknown"
        
        price_elem = soup.find(['span', 'div'], class_=re.compile(r'price|money'))
        price_text = price_elem.get_text(strip=True) if price_elem else "0"
        price = float(re.sub(r'[^\d.]', '', price_text) or 0)
        
        variant_input = soup.find('input', {'name': 'id'})
        variant_id = variant_input.get('value', '') if variant_input else ''
        
        product_id_match = re.search(r'"product_id"\s*:\s*(\d+)', response.body)
        product_id = product_id_match.group(1) if product_id_match else ''
        
        return ShopifyProduct(
            product_id=product_id,
            variant_id=variant_id,
            name=name,
            price=price,
            url=product_url,
            handle=handle
        )
    
    def add_to_cart(self, product: ShopifyProduct, quantity: int = 1) -> bool:
        self.behavior.human_delay(action_type="button_click")
        
        cart_add_url = f"{self.base_url}/cart/add.js"
        
        data = {
            'id': product.variant_id,
            'quantity': quantity
        }
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        response = self.http_client.post(cart_add_url, json_data=data, headers=headers)
        
        if response.status_code == 200:
            try:
                result = json.loads(response.body)
                if 'id' in result or 'variant_id' in result:
                    return True
            except json.JSONDecodeError:
                pass
        
        form_data = {
            'form_type': 'product',
            'utf8': '✓',
            'id': product.variant_id,
            'quantity': str(quantity)
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = self.http_client.post(f"{self.base_url}/cart/add", data=form_data, headers=headers)
        
        return response.status_code in [200, 302]
    
    def get_cart(self) -> Optional[ShopifyCart]:
        cart_url = f"{self.base_url}/cart.js"
        response = self.http_client.get(cart_url)
        
        if response.status_code != 200:
            return None
        
        try:
            cart_data = json.loads(response.body)
            
            items = []
            for item in cart_data.get('items', []):
                items.append(ShopifyProduct(
                    product_id=str(item.get('product_id', '')),
                    variant_id=str(item.get('variant_id', '')),
                    name=item.get('title', 'Unknown'),
                    price=float(item.get('price', 0)) / 100,
                    url=item.get('url', ''),
                    handle=item.get('handle', ''),
                    quantity=item.get('quantity', 1)
                ))
            
            self.cart = ShopifyCart(
                token=cart_data.get('token', ''),
                items=items,
                subtotal=float(cart_data.get('total_price', 0)) / 100,
                total=float(cart_data.get('total_price', 0)) / 100,
                currency=cart_data.get('currency', 'USD'),
                item_count=cart_data.get('item_count', 0)
            )
            
            return self.cart
            
        except json.JSONDecodeError:
            return None
    
    def proceed_to_checkout(self) -> Optional[ShopifyCheckout]:
        checkout_url = f"{self.base_url}/checkout"
        response = self.http_client.get(checkout_url, allow_redirects=True)
        
        if response.status_code != 200:
            return None
        
        self.behavior.human_delay(action_type="page_load")
        
        checkout_token = None
        
        token_match = re.search(r'/checkouts/([a-f0-9]+)', response.url)
        if token_match:
            checkout_token = token_match.group(1)
        
        if not checkout_token:
            token_match = re.search(r'"token"\s*:\s*"([a-f0-9]+)"', response.body)
            if token_match:
                checkout_token = token_match.group(1)
        
        payment_due = 0
        payment_match = re.search(r'"payment_due"\s*:\s*"?(\d+)"?', response.body)
        if payment_match:
            payment_due = float(payment_match.group(1)) / 100
        
        self.checkout = ShopifyCheckout(
            checkout_token=checkout_token or '',
            checkout_url=response.url,
            web_url=response.url,
            payment_due=payment_due
        )
        
        return self.checkout
    
    def fill_contact_info(self, email: str, phone: str = None) -> Dict[str, str]:
        return {
            'checkout[email]': email,
            'checkout[buyer_accepts_marketing]': '0',
            'checkout[buyer_accepts_sms_marketing]': '0'
        }
    
    def fill_shipping_address(self, shipping_data: Dict[str, str]) -> Dict[str, str]:
        field_mapping = {
            'first_name': 'checkout[shipping_address][first_name]',
            'last_name': 'checkout[shipping_address][last_name]',
            'address_1': 'checkout[shipping_address][address1]',
            'address_2': 'checkout[shipping_address][address2]',
            'city': 'checkout[shipping_address][city]',
            'state': 'checkout[shipping_address][province]',
            'postcode': 'checkout[shipping_address][zip]',
            'country': 'checkout[shipping_address][country]',
            'phone': 'checkout[shipping_address][phone]'
        }
        
        formatted_data = {}
        
        for key, value in shipping_data.items():
            if key in field_mapping:
                formatted_data[field_mapping[key]] = value
        
        return formatted_data
    
    def fill_billing_address(self, billing_data: Dict[str, str]) -> Dict[str, str]:
        field_mapping = {
            'first_name': 'checkout[billing_address][first_name]',
            'last_name': 'checkout[billing_address][last_name]',
            'address_1': 'checkout[billing_address][address1]',
            'address_2': 'checkout[billing_address][address2]',
            'city': 'checkout[billing_address][city]',
            'state': 'checkout[billing_address][province]',
            'postcode': 'checkout[billing_address][zip]',
            'country': 'checkout[billing_address][country]',
            'phone': 'checkout[billing_address][phone]'
        }
        
        formatted_data = {}
        
        for key, value in billing_data.items():
            if key in field_mapping:
                formatted_data[field_mapping[key]] = value
        
        return formatted_data
    
    def get_shipping_rates(self) -> List[Dict[str, Any]]:
        if not self.checkout:
            return []
        
        shipping_url = f"{self.checkout.checkout_url}?step=shipping_method"
        response = self.http_client.get(shipping_url)
        
        if response.status_code != 200:
            return []
        
        rates = []
        soup = BeautifulSoup(response.body, 'html.parser')
        
        rate_elements = soup.find_all('div', class_=re.compile(r'radio-wrapper'))
        
        for elem in rate_elements:
            try:
                input_elem = elem.find('input', {'name': 'checkout[shipping_rate][id]'})
                if input_elem:
                    rate_id = input_elem.get('value', '')
                    
                    label = elem.find('span', class_=re.compile(r'radio__label'))
                    name = label.get_text(strip=True) if label else 'Standard'
                    
                    price_elem = elem.find('span', class_=re.compile(r'content-box__emphasis'))
                    price_text = price_elem.get_text(strip=True) if price_elem else '0'
                    price = float(re.sub(r'[^\d.]', '', price_text) or 0)
                    
                    rates.append({
                        'id': rate_id,
                        'name': name,
                        'price': price
                    })
            except Exception:
                continue
        
        return rates
    
    def select_shipping_rate(self, rate_id: str) -> bool:
        if not self.checkout:
            return False
        
        data = {
            'checkout[shipping_rate][id]': rate_id,
            '_method': 'patch'
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = self.http_client.post(self.checkout.checkout_url, data=data, headers=headers)
        
        return response.status_code in [200, 302]
    
    def submit_order(self, contact_email: str, billing_data: Dict[str, str], 
                     shipping_data: Dict[str, str] = None, payment_data: Dict[str, str] = None) -> Dict[str, Any]:
        
        self.behavior.human_delay(action_type="thinking")
        
        if not self.checkout:
            self.proceed_to_checkout()
        
        result = {
            'success': False,
            'order_id': None,
            'redirect_url': None,
            'error': None,
            'requires_action': False,
            'action_type': None,
            'action_data': None
        }
        
        order_data = {}
        order_data.update(self.fill_contact_info(contact_email))
        
        if shipping_data:
            order_data.update(self.fill_shipping_address(shipping_data))
        
        order_data.update(self.fill_billing_address(billing_data))
        
        if payment_data:
            order_data.update(payment_data)
        
        order_data['_method'] = 'patch'
        order_data['previous_step'] = 'payment_method'
        order_data['step'] = ''
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': self.checkout.checkout_url
        }
        
        self.behavior.human_delay(action_type="button_click")
        
        response = self.http_client.post(self.checkout.checkout_url, data=order_data, headers=headers)
        
        if response.status_code in [200, 302]:
            if 'thank_you' in response.url or 'order' in response.url:
                result['success'] = True
                result['redirect_url'] = response.url
                
                order_match = re.search(r'/orders/([a-f0-9]+)', response.url)
                if order_match:
                    result['order_id'] = order_match.group(1)
            
            elif 'processing' in response.body.lower() or '3ds' in response.body.lower():
                result['requires_action'] = True
                result['action_type'] = '3ds'
                
                secret_match = re.search(r'"client_secret"\s*:\s*"([^"]+)"', response.body)
                if secret_match:
                    result['action_data'] = {'client_secret': secret_match.group(1)}
            
            else:
                result['error'] = 'Unknown checkout state'
        else:
            result['error'] = f'HTTP {response.status_code}'
        
        return result
    
    def get_order_confirmation(self, order_id: str) -> Dict[str, Any]:
        confirmation_url = f"{self.base_url}/orders/{order_id}"
        response = self.http_client.get(confirmation_url)
        
        if response.status_code != 200:
            return {'success': False, 'error': 'Could not retrieve order confirmation'}
        
        soup = BeautifulSoup(response.body, 'html.parser')
        
        confirmation = {
            'success': True,
            'order_id': order_id,
            'order_number': None,
            'total': None,
            'status': None
        }
        
        order_number_elem = soup.find(['span', 'div'], class_=re.compile(r'order-number'))
        if order_number_elem:
            confirmation['order_number'] = order_number_elem.get_text(strip=True)
        
        total_elem = soup.find(['span', 'div'], class_=re.compile(r'total-recap'))
        if total_elem:
            total_text = total_elem.get_text(strip=True)
            total_match = re.search(r'[\d,.]+', total_text)
            if total_match:
                confirmation['total'] = total_match.group(0)
        
        return confirmation
