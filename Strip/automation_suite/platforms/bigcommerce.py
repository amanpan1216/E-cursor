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
class BigCommerceProduct:
    product_id: str
    name: str
    price: float
    url: str
    sku: Optional[str] = None
    variant_id: Optional[str] = None
    quantity: int = 1


@dataclass
class BigCommerceCart:
    cart_id: str
    items: List[BigCommerceProduct]
    subtotal: float
    total: float
    currency: str


@dataclass
class BigCommerceCheckout:
    checkout_id: str
    checkout_url: str
    order_id: Optional[str] = None
    payment_methods: List[str] = None
    billing_address: Dict[str, str] = None
    shipping_address: Dict[str, str] = None


class BigCommerceDetector:
    def __init__(self, http_client: AdvancedHTTPClient):
        self.http_client = http_client
        
    def detect(self, url: str) -> Tuple[bool, Dict[str, Any]]:
        response = self.http_client.get(url)
        
        if response.status_code != 200:
            return False, {}
        
        indicators = {
            "is_bigcommerce": False,
            "store_hash": None,
            "currency": None,
            "payment_gateways": [],
            "features": []
        }
        
        soup = BeautifulSoup(response.body, 'html.parser')
        
        bc_indicators = [
            'bigcommerce' in response.body.lower(),
            'stencil' in response.body.lower(),
            soup.find('script', src=re.compile(r'bigcommerce')),
            soup.find('link', href=re.compile(r'bigcommerce')),
            'BCData' in response.body,
            'jsContext' in response.body,
            re.search(r'cdn\d+\.bigcommerce\.com', response.body)
        ]
        
        if any(bc_indicators):
            indicators["is_bigcommerce"] = True
        
        store_hash_match = re.search(r'store-([a-z0-9]+)\.mybigcommerce\.com', response.body)
        if store_hash_match:
            indicators["store_hash"] = store_hash_match.group(1)
        
        currency_match = re.search(r'"currency_code"\s*:\s*"([A-Z]{3})"', response.body)
        if currency_match:
            indicators["currency"] = currency_match.group(1)
        
        gateway_patterns = [
            (r'stripe', 'stripe'),
            (r'braintree', 'braintree'),
            (r'paypal', 'paypal'),
            (r'square', 'square'),
            (r'authorize', 'authorize_net')
        ]
        
        for pattern, gateway in gateway_patterns:
            if re.search(pattern, response.body, re.IGNORECASE):
                indicators["payment_gateways"].append(gateway)
        
        if 'optimized-checkout' in response.body:
            indicators["features"].append("optimized_checkout")
        
        return indicators["is_bigcommerce"], indicators


class BigCommerceHandler:
    def __init__(self, http_client: AdvancedHTTPClient):
        self.http_client = http_client
        self.behavior = HumanBehaviorSimulator()
        self.form_simulator = FormInteractionSimulator()
        self.base_url = None
        self.store_hash = None
        self.cart = None
        self.checkout = None
        self.csrf_token = None
        self.session_data = {}
        
    def initialize(self, base_url: str) -> bool:
        self.base_url = base_url.rstrip('/')
        
        response = self.http_client.get(self.base_url)
        if response.status_code != 200:
            return False
        
        self._extract_store_data(response.body)
        self._extract_csrf_token(response.body)
        
        self.behavior.human_delay(action_type="page_load")
        
        return True
    
    def _extract_store_data(self, html: str):
        store_hash_match = re.search(r'store-([a-z0-9]+)\.mybigcommerce\.com', html)
        if store_hash_match:
            self.store_hash = store_hash_match.group(1)
        
        bc_data_match = re.search(r'BCData\s*=\s*({[^;]+});', html, re.DOTALL)
        if bc_data_match:
            try:
                bc_data = json.loads(bc_data_match.group(1))
                self.session_data['bc_data'] = bc_data
            except json.JSONDecodeError:
                pass
        
        js_context_match = re.search(r'jsContext\s*=\s*({[^;]+});', html, re.DOTALL)
        if js_context_match:
            try:
                js_context = json.loads(js_context_match.group(1))
                self.session_data['js_context'] = js_context
            except json.JSONDecodeError:
                pass
    
    def _extract_csrf_token(self, html: str):
        csrf_patterns = [
            r'csrf_token["\s:=]+([a-f0-9]{32,})',
            r'CSRFToken["\s:=]+([a-f0-9]{32,})',
            r'name="csrf_token"\s+value="([^"]+)"',
            r'"token"\s*:\s*"([a-f0-9]{32,})"'
        ]
        
        for pattern in csrf_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                self.csrf_token = match.group(1)
                break
        
        soup = BeautifulSoup(html, 'html.parser')
        csrf_input = soup.find('input', {'name': re.compile(r'csrf|token', re.IGNORECASE)})
        if csrf_input and not self.csrf_token:
            self.csrf_token = csrf_input.get('value', '')
    
    def browse_products(self, category_url: str = None) -> List[BigCommerceProduct]:
        products = []
        
        url = category_url or f"{self.base_url}/products/"
        response = self.http_client.get(url)
        
        if response.status_code != 200:
            return products
        
        self.behavior.human_delay(action_type="reading")
        
        soup = BeautifulSoup(response.body, 'html.parser')
        
        product_cards = soup.find_all(['article', 'li', 'div'], class_=re.compile(r'product|card'))
        
        for card in product_cards:
            try:
                product_id = card.get('data-product-id') or card.get('data-entity-id')
                
                if not product_id:
                    link = card.find('a', href=re.compile(r'/products/'))
                    if link:
                        href = link.get('href', '')
                        id_match = re.search(r'/products/[^/]+/(\d+)', href)
                        if id_match:
                            product_id = id_match.group(1)
                
                name_elem = card.find(['h3', 'h4', 'a'], class_=re.compile(r'title|name|link'))
                name = name_elem.get_text(strip=True) if name_elem else "Unknown"
                
                price_elem = card.find(['span', 'div'], class_=re.compile(r'price'))
                price_text = price_elem.get_text(strip=True) if price_elem else "0"
                price = float(re.sub(r'[^\d.]', '', price_text) or 0)
                
                link_elem = card.find('a', href=True)
                url = link_elem.get('href', '') if link_elem else ''
                if url and not url.startswith('http'):
                    url = urljoin(self.base_url, url)
                
                sku_elem = card.find(['span', 'div'], class_=re.compile(r'sku'))
                sku = sku_elem.get_text(strip=True) if sku_elem else None
                
                if product_id:
                    products.append(BigCommerceProduct(
                        product_id=product_id,
                        name=name,
                        price=price,
                        url=url,
                        sku=sku
                    ))
            except Exception:
                continue
        
        return products
    
    def get_product_details(self, product_url: str) -> Optional[BigCommerceProduct]:
        response = self.http_client.get(product_url)
        
        if response.status_code != 200:
            return None
        
        self.behavior.human_delay(action_type="reading")
        self._extract_csrf_token(response.body)
        
        soup = BeautifulSoup(response.body, 'html.parser')
        
        product_id = None
        
        product_view = soup.find(['div', 'section'], class_=re.compile(r'productView'))
        if product_view:
            product_id = product_view.get('data-product-id')
        
        if not product_id:
            add_to_cart = soup.find('input', {'name': 'product_id'})
            if add_to_cart:
                product_id = add_to_cart.get('value')
        
        if not product_id:
            id_match = re.search(r'"product_id"\s*:\s*(\d+)', response.body)
            if id_match:
                product_id = id_match.group(1)
        
        name_elem = soup.find('h1', class_=re.compile(r'productView-title|product-title'))
        name = name_elem.get_text(strip=True) if name_elem else "Unknown"
        
        price_elem = soup.find(['span', 'div'], class_=re.compile(r'productView-price|price--main'))
        price_text = price_elem.get_text(strip=True) if price_elem else "0"
        price = float(re.sub(r'[^\d.]', '', price_text) or 0)
        
        sku_elem = soup.find(['span', 'div'], class_=re.compile(r'productView-info-value|sku'))
        sku = sku_elem.get_text(strip=True) if sku_elem else None
        
        variant_id = None
        variant_select = soup.find('select', {'name': re.compile(r'attribute')})
        if variant_select:
            first_option = variant_select.find('option', selected=True)
            if first_option:
                variant_id = first_option.get('value')
        
        return BigCommerceProduct(
            product_id=product_id,
            name=name,
            price=price,
            url=product_url,
            sku=sku,
            variant_id=variant_id
        )
    
    def add_to_cart(self, product: BigCommerceProduct, quantity: int = 1) -> bool:
        self.behavior.human_delay(action_type="button_click")
        
        cart_url = f"{self.base_url}/cart.php"
        
        data = {
            'action': 'add',
            'product_id': product.product_id,
            'qty[]': str(quantity)
        }
        
        if product.variant_id:
            data['attribute[0]'] = product.variant_id
        
        if self.csrf_token:
            data['csrf_token'] = self.csrf_token
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': product.url
        }
        
        response = self.http_client.post(cart_url, data=data, headers=headers)
        
        if response.status_code in [200, 302]:
            return True
        
        api_url = f"{self.base_url}/api/storefront/carts"
        
        api_data = {
            'lineItems': [{
                'productId': int(product.product_id),
                'quantity': quantity
            }]
        }
        
        if product.variant_id:
            api_data['lineItems'][0]['variantId'] = int(product.variant_id)
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        response = self.http_client.post(api_url, json_data=api_data, headers=headers)
        
        if response.status_code in [200, 201]:
            try:
                result = json.loads(response.body)
                if 'id' in result:
                    self.session_data['cart_id'] = result['id']
                    return True
            except json.JSONDecodeError:
                pass
        
        return False
    
    def get_cart(self) -> Optional[BigCommerceCart]:
        cart_url = f"{self.base_url}/cart.php"
        response = self.http_client.get(cart_url)
        
        if response.status_code != 200:
            return None
        
        self.behavior.human_delay(action_type="reading")
        self._extract_csrf_token(response.body)
        
        soup = BeautifulSoup(response.body, 'html.parser')
        
        items = []
        cart_items = soup.find_all(['tr', 'div'], class_=re.compile(r'cart-item'))
        
        for item in cart_items:
            try:
                product_id = item.get('data-item-id') or item.get('data-product-id')
                
                name_elem = item.find(['a', 'span'], class_=re.compile(r'cart-item-name|product-title'))
                name = name_elem.get_text(strip=True) if name_elem else "Unknown"
                
                price_elem = item.find(['span', 'td'], class_=re.compile(r'cart-item-value|price'))
                price_text = price_elem.get_text(strip=True) if price_elem else "0"
                price = float(re.sub(r'[^\d.]', '', price_text) or 0)
                
                qty_input = item.find('input', {'name': re.compile(r'qty')})
                quantity = int(qty_input.get('value', 1)) if qty_input else 1
                
                if product_id:
                    items.append(BigCommerceProduct(
                        product_id=product_id,
                        name=name,
                        price=price,
                        url='',
                        quantity=quantity
                    ))
            except Exception:
                continue
        
        subtotal_elem = soup.find(['span', 'td'], class_=re.compile(r'cart-subtotal|subtotal'))
        subtotal_text = subtotal_elem.get_text(strip=True) if subtotal_elem else "0"
        subtotal = float(re.sub(r'[^\d.]', '', subtotal_text) or 0)
        
        total_elem = soup.find(['span', 'td'], class_=re.compile(r'cart-total|grand-total'))
        total_text = total_elem.get_text(strip=True) if total_elem else "0"
        total = float(re.sub(r'[^\d.]', '', total_text) or 0)
        
        cart_id = self.session_data.get('cart_id', '')
        if not cart_id:
            cart_id_match = re.search(r'"cart_id"\s*:\s*"([^"]+)"', response.body)
            if cart_id_match:
                cart_id = cart_id_match.group(1)
        
        self.cart = BigCommerceCart(
            cart_id=cart_id,
            items=items,
            subtotal=subtotal,
            total=total,
            currency='USD'
        )
        
        return self.cart
    
    def proceed_to_checkout(self) -> Optional[BigCommerceCheckout]:
        checkout_url = f"{self.base_url}/checkout"
        response = self.http_client.get(checkout_url)
        
        if response.status_code != 200:
            return None
        
        self.behavior.human_delay(action_type="page_load")
        self._extract_csrf_token(response.body)
        
        checkout_id = None
        checkout_id_match = re.search(r'"checkoutId"\s*:\s*"([^"]+)"', response.body)
        if checkout_id_match:
            checkout_id = checkout_id_match.group(1)
        
        if not checkout_id and self.cart:
            checkout_id = self.cart.cart_id
        
        payment_methods = []
        payment_match = re.findall(r'"methodId"\s*:\s*"([^"]+)"', response.body)
        if payment_match:
            payment_methods = list(set(payment_match))
        
        self.checkout = BigCommerceCheckout(
            checkout_id=checkout_id,
            checkout_url=checkout_url,
            payment_methods=payment_methods
        )
        
        return self.checkout
    
    def fill_billing_address(self, billing_data: Dict[str, str]) -> Dict[str, str]:
        field_mapping = {
            'first_name': 'firstName',
            'last_name': 'lastName',
            'email': 'email',
            'company': 'company',
            'address_1': 'address1',
            'address_2': 'address2',
            'city': 'city',
            'state': 'stateOrProvince',
            'postcode': 'postalCode',
            'country': 'countryCode',
            'phone': 'phone'
        }
        
        formatted_data = {}
        
        for key, value in billing_data.items():
            if key in field_mapping:
                formatted_data[field_mapping[key]] = value
            else:
                formatted_data[key] = value
        
        return formatted_data
    
    def fill_shipping_address(self, shipping_data: Dict[str, str]) -> Dict[str, str]:
        return self.fill_billing_address(shipping_data)
    
    def submit_order(self, billing_data: Dict[str, str], shipping_data: Dict[str, str] = None,
                     payment_method: str = None, payment_data: Dict[str, str] = None) -> Dict[str, Any]:
        
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
        
        billing_address = self.fill_billing_address(billing_data)
        
        billing_url = f"{self.base_url}/api/storefront/checkouts/{self.checkout.checkout_id}/billing-address"
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        response = self.http_client.post(billing_url, json_data=billing_address, headers=headers)
        
        if response.status_code not in [200, 201]:
            result['error'] = 'Failed to set billing address'
            return result
        
        if shipping_data:
            shipping_address = self.fill_shipping_address(shipping_data)
            shipping_url = f"{self.base_url}/api/storefront/checkouts/{self.checkout.checkout_id}/consignments"
            
            consignment_data = {
                'address': shipping_address,
                'lineItems': [{'itemId': item.product_id, 'quantity': item.quantity} 
                             for item in self.cart.items] if self.cart else []
            }
            
            response = self.http_client.post(shipping_url, json_data=[consignment_data], headers=headers)
        
        order_url = f"{self.base_url}/api/storefront/checkouts/{self.checkout.checkout_id}/orders"
        
        self.behavior.human_delay(action_type="button_click")
        
        response = self.http_client.post(order_url, json_data={}, headers=headers)
        
        if response.status_code in [200, 201]:
            try:
                order_data = json.loads(response.body)
                result['success'] = True
                result['order_id'] = str(order_data.get('orderId', ''))
                
                if 'redirectUrl' in order_data:
                    result['redirect_url'] = order_data['redirectUrl']
                
            except json.JSONDecodeError:
                result['error'] = 'Invalid response from server'
        else:
            result['error'] = f'HTTP {response.status_code}'
        
        return result
    
    def get_order_confirmation(self, order_id: str) -> Dict[str, Any]:
        confirmation_url = f"{self.base_url}/checkout/order-confirmation/{order_id}"
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
        
        total_elem = soup.find(['span', 'div'], class_=re.compile(r'order-total'))
        if total_elem:
            total_text = total_elem.get_text(strip=True)
            total_match = re.search(r'[\d,.]+', total_text)
            if total_match:
                confirmation['total'] = total_match.group(0)
        
        return confirmation
