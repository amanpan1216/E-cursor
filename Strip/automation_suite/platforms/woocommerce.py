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
class WooCommerceProduct:
    product_id: str
    name: str
    price: float
    url: str
    variation_id: Optional[str] = None
    quantity: int = 1


@dataclass
class WooCommerceCart:
    items: List[WooCommerceProduct]
    subtotal: float
    total: float
    cart_hash: str
    nonce: str


@dataclass
class WooCommerceCheckout:
    checkout_url: str
    nonce: str
    order_id: Optional[str] = None
    payment_method: Optional[str] = None
    billing_fields: Dict[str, str] = None
    shipping_fields: Dict[str, str] = None


class WooCommerceDetector:
    def __init__(self, http_client: AdvancedHTTPClient):
        self.http_client = http_client
        
    def detect(self, url: str) -> Tuple[bool, Dict[str, Any]]:
        response = self.http_client.get(url)
        
        if response.status_code != 200:
            return False, {}
        
        indicators = {
            "is_woocommerce": False,
            "version": None,
            "currency": None,
            "payment_gateways": [],
            "features": []
        }
        
        soup = BeautifulSoup(response.body, 'html.parser')
        
        woo_indicators = [
            'woocommerce' in response.body.lower(),
            soup.find('body', class_=re.compile(r'woocommerce')),
            soup.find('script', src=re.compile(r'woocommerce')),
            soup.find('link', href=re.compile(r'woocommerce')),
            'wc-ajax' in response.body,
            'wc_add_to_cart_params' in response.body,
            'wc_checkout_params' in response.body
        ]
        
        if any(woo_indicators):
            indicators["is_woocommerce"] = True
        
        version_match = re.search(r'woocommerce[/-](\d+\.\d+\.\d+)', response.body, re.IGNORECASE)
        if version_match:
            indicators["version"] = version_match.group(1)
        
        currency_match = re.search(r'"currency"\s*:\s*"([A-Z]{3})"', response.body)
        if currency_match:
            indicators["currency"] = currency_match.group(1)
        
        gateway_patterns = [
            (r'stripe', 'stripe'),
            (r'braintree', 'braintree'),
            (r'paypal', 'paypal'),
            (r'square', 'square'),
            (r'authorize\.net', 'authorize_net')
        ]
        
        for pattern, gateway in gateway_patterns:
            if re.search(pattern, response.body, re.IGNORECASE):
                indicators["payment_gateways"].append(gateway)
        
        if 'wc-blocks' in response.body:
            indicators["features"].append("blocks_checkout")
        if 'wc-stripe' in response.body:
            indicators["features"].append("stripe_elements")
        
        return indicators["is_woocommerce"], indicators


class WooCommerceHandler:
    def __init__(self, http_client: AdvancedHTTPClient):
        self.http_client = http_client
        self.behavior = HumanBehaviorSimulator()
        self.form_simulator = FormInteractionSimulator()
        self.base_url = None
        self.cart = None
        self.checkout = None
        self.nonces = {}
        self.session_data = {}
        
    def initialize(self, base_url: str) -> bool:
        self.base_url = base_url.rstrip('/')
        
        response = self.http_client.get(self.base_url)
        if response.status_code != 200:
            return False
        
        self._extract_nonces(response.body)
        self._extract_session_data(response.body)
        
        self.behavior.human_delay(action_type="page_load")
        
        return True
    
    def _extract_nonces(self, html: str):
        nonce_patterns = [
            (r'wc_add_to_cart_params.*?"nonce"\s*:\s*"([^"]+)"', 'add_to_cart'),
            (r'wc_checkout_params.*?"nonce"\s*:\s*"([^"]+)"', 'checkout'),
            (r'wc_cart_params.*?"nonce"\s*:\s*"([^"]+)"', 'cart'),
            (r'_wpnonce["\s:=]+([a-f0-9]{10})', 'wp'),
            (r'woocommerce-process-checkout-nonce.*?value=["\']([^"\']+)', 'process_checkout'),
            (r'security["\s:=]+([a-f0-9]{10})', 'security'),
            (r'"ajax_nonce"\s*:\s*"([^"]+)"', 'ajax'),
            (r'wc-ajax=\w+&security=([a-f0-9]+)', 'wc_ajax')
        ]
        
        for pattern, nonce_type in nonce_patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                self.nonces[nonce_type] = match.group(1)
        
        soup = BeautifulSoup(html, 'html.parser')
        
        nonce_inputs = soup.find_all('input', {'name': re.compile(r'nonce|_wpnonce|security', re.IGNORECASE)})
        for inp in nonce_inputs:
            name = inp.get('name', '')
            value = inp.get('value', '')
            if value:
                self.nonces[name] = value
    
    def _extract_session_data(self, html: str):
        patterns = [
            (r'wc_cart_hash.*?["\']([a-f0-9]{32})["\']', 'cart_hash'),
            (r'wc_fragments_params.*?"fragment_name"\s*:\s*"([^"]+)"', 'fragment_name'),
            (r'"store_api_nonce"\s*:\s*"([^"]+)"', 'store_api_nonce'),
            (r'"wcStoreApiNonce"\s*:\s*"([^"]+)"', 'store_api_nonce'),
            (r'"cartToken"\s*:\s*"([^"]+)"', 'cart_token')
        ]
        
        for pattern, key in patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                self.session_data[key] = match.group(1)
    
    def browse_products(self, shop_url: str = None) -> List[WooCommerceProduct]:
        products = []
        
        url = shop_url or f"{self.base_url}/shop/"
        response = self.http_client.get(url)
        
        if response.status_code != 200:
            return products
        
        self.behavior.human_delay(action_type="reading")
        
        soup = BeautifulSoup(response.body, 'html.parser')
        
        product_elements = soup.find_all('li', class_=re.compile(r'product'))
        
        for elem in product_elements:
            try:
                product_id = None
                product_class = elem.get('class', [])
                for cls in product_class:
                    if cls.startswith('post-'):
                        product_id = cls.replace('post-', '')
                        break
                
                name_elem = elem.find(['h2', 'h3'], class_=re.compile(r'title|name'))
                name = name_elem.get_text(strip=True) if name_elem else "Unknown"
                
                price_elem = elem.find('span', class_='woocommerce-Price-amount')
                price_text = price_elem.get_text(strip=True) if price_elem else "0"
                price = float(re.sub(r'[^\d.]', '', price_text) or 0)
                
                link_elem = elem.find('a', class_=re.compile(r'woocommerce-LoopProduct-link'))
                url = link_elem.get('href', '') if link_elem else ''
                
                if product_id:
                    products.append(WooCommerceProduct(
                        product_id=product_id,
                        name=name,
                        price=price,
                        url=url
                    ))
            except Exception:
                continue
        
        return products
    
    def get_product_details(self, product_url: str) -> Optional[WooCommerceProduct]:
        response = self.http_client.get(product_url)
        
        if response.status_code != 200:
            return None
        
        self.behavior.human_delay(action_type="reading")
        self._extract_nonces(response.body)
        
        soup = BeautifulSoup(response.body, 'html.parser')
        
        product_id = None
        body = soup.find('body')
        if body:
            for cls in body.get('class', []):
                if cls.startswith('postid-'):
                    product_id = cls.replace('postid-', '')
                    break
        
        if not product_id:
            add_to_cart = soup.find('button', class_='single_add_to_cart_button')
            if add_to_cart:
                product_id = add_to_cart.get('value')
        
        name_elem = soup.find('h1', class_=re.compile(r'product_title|entry-title'))
        name = name_elem.get_text(strip=True) if name_elem else "Unknown"
        
        price_elem = soup.find('p', class_='price')
        if price_elem:
            price_amount = price_elem.find('span', class_='woocommerce-Price-amount')
            price_text = price_amount.get_text(strip=True) if price_amount else "0"
        else:
            price_text = "0"
        price = float(re.sub(r'[^\d.]', '', price_text) or 0)
        
        variation_id = None
        variation_form = soup.find('form', class_='variations_form')
        if variation_form:
            variation_data = variation_form.get('data-product_variations')
            if variation_data:
                try:
                    variations = json.loads(variation_data)
                    if variations:
                        variation_id = str(variations[0].get('variation_id', ''))
                except json.JSONDecodeError:
                    pass
        
        return WooCommerceProduct(
            product_id=product_id,
            name=name,
            price=price,
            url=product_url,
            variation_id=variation_id
        )
    
    def add_to_cart(self, product: WooCommerceProduct, quantity: int = 1) -> bool:
        self.behavior.human_delay(action_type="button_click")
        
        ajax_url = f"{self.base_url}/?wc-ajax=add_to_cart"
        
        data = {
            'product_id': product.product_id,
            'quantity': quantity
        }
        
        if product.variation_id:
            data['variation_id'] = product.variation_id
        
        if 'add_to_cart' in self.nonces:
            data['security'] = self.nonces['add_to_cart']
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': product.url
        }
        
        response = self.http_client.post(ajax_url, data=data, headers=headers)
        
        if response.status_code == 200:
            try:
                result = json.loads(response.body)
                if 'fragments' in result or 'cart_hash' in result:
                    if 'cart_hash' in result:
                        self.session_data['cart_hash'] = result['cart_hash']
                    return True
            except json.JSONDecodeError:
                pass
        
        form_url = f"{self.base_url}/?add-to-cart={product.product_id}"
        if product.variation_id:
            form_url += f"&variation_id={product.variation_id}"
        form_url += f"&quantity={quantity}"
        
        response = self.http_client.get(form_url)
        return response.status_code in [200, 302]
    
    def get_cart(self) -> Optional[WooCommerceCart]:
        cart_url = f"{self.base_url}/cart/"
        response = self.http_client.get(cart_url)
        
        if response.status_code != 200:
            return None
        
        self.behavior.human_delay(action_type="reading")
        self._extract_nonces(response.body)
        
        soup = BeautifulSoup(response.body, 'html.parser')
        
        items = []
        cart_items = soup.find_all('tr', class_='woocommerce-cart-form__cart-item')
        
        for item in cart_items:
            try:
                product_name = item.find('td', class_='product-name')
                name = product_name.get_text(strip=True) if product_name else "Unknown"
                
                product_price = item.find('td', class_='product-price')
                price_text = product_price.get_text(strip=True) if product_price else "0"
                price = float(re.sub(r'[^\d.]', '', price_text) or 0)
                
                quantity_input = item.find('input', class_='qty')
                quantity = int(quantity_input.get('value', 1)) if quantity_input else 1
                
                remove_link = item.find('a', class_='remove')
                product_id = None
                if remove_link:
                    data_product_id = remove_link.get('data-product_id')
                    if data_product_id:
                        product_id = data_product_id
                
                if product_id:
                    items.append(WooCommerceProduct(
                        product_id=product_id,
                        name=name,
                        price=price,
                        url='',
                        quantity=quantity
                    ))
            except Exception:
                continue
        
        subtotal_elem = soup.find('td', {'data-title': 'Subtotal'})
        subtotal_text = subtotal_elem.get_text(strip=True) if subtotal_elem else "0"
        subtotal = float(re.sub(r'[^\d.]', '', subtotal_text) or 0)
        
        total_elem = soup.find('td', {'data-title': 'Total'})
        if not total_elem:
            total_elem = soup.find('strong', class_='order-total')
        total_text = total_elem.get_text(strip=True) if total_elem else "0"
        total = float(re.sub(r'[^\d.]', '', total_text) or 0)
        
        cart_hash = self.session_data.get('cart_hash', '')
        nonce = self.nonces.get('cart', '')
        
        self.cart = WooCommerceCart(
            items=items,
            subtotal=subtotal,
            total=total,
            cart_hash=cart_hash,
            nonce=nonce
        )
        
        return self.cart
    
    def proceed_to_checkout(self) -> Optional[WooCommerceCheckout]:
        checkout_url = f"{self.base_url}/checkout/"
        response = self.http_client.get(checkout_url)
        
        if response.status_code != 200:
            return None
        
        self.behavior.human_delay(action_type="page_load")
        self._extract_nonces(response.body)
        
        soup = BeautifulSoup(response.body, 'html.parser')
        
        billing_fields = {}
        billing_inputs = soup.find_all('input', {'name': re.compile(r'^billing_')})
        for inp in billing_inputs:
            name = inp.get('name', '')
            billing_fields[name] = inp.get('value', '')
        
        shipping_fields = {}
        shipping_inputs = soup.find_all('input', {'name': re.compile(r'^shipping_')})
        for inp in shipping_inputs:
            name = inp.get('name', '')
            shipping_fields[name] = inp.get('value', '')
        
        payment_methods = []
        payment_inputs = soup.find_all('input', {'name': 'payment_method'})
        for inp in payment_inputs:
            payment_methods.append(inp.get('value', ''))
        
        nonce = self.nonces.get('process_checkout', '') or self.nonces.get('checkout', '')
        
        self.checkout = WooCommerceCheckout(
            checkout_url=checkout_url,
            nonce=nonce,
            billing_fields=billing_fields,
            shipping_fields=shipping_fields,
            payment_method=payment_methods[0] if payment_methods else None
        )
        
        return self.checkout
    
    def fill_billing_info(self, billing_data: Dict[str, str]) -> Dict[str, str]:
        field_mapping = {
            'first_name': 'billing_first_name',
            'last_name': 'billing_last_name',
            'company': 'billing_company',
            'country': 'billing_country',
            'address_1': 'billing_address_1',
            'address_2': 'billing_address_2',
            'city': 'billing_city',
            'state': 'billing_state',
            'postcode': 'billing_postcode',
            'phone': 'billing_phone',
            'email': 'billing_email'
        }
        
        filled_data = {}
        
        for key, value in billing_data.items():
            if key in field_mapping:
                filled_data[field_mapping[key]] = value
            elif key.startswith('billing_'):
                filled_data[key] = value
            else:
                filled_data[f'billing_{key}'] = value
        
        return filled_data
    
    def fill_shipping_info(self, shipping_data: Dict[str, str]) -> Dict[str, str]:
        field_mapping = {
            'first_name': 'shipping_first_name',
            'last_name': 'shipping_last_name',
            'company': 'shipping_company',
            'country': 'shipping_country',
            'address_1': 'shipping_address_1',
            'address_2': 'shipping_address_2',
            'city': 'shipping_city',
            'state': 'shipping_state',
            'postcode': 'shipping_postcode'
        }
        
        filled_data = {}
        
        for key, value in shipping_data.items():
            if key in field_mapping:
                filled_data[field_mapping[key]] = value
            elif key.startswith('shipping_'):
                filled_data[key] = value
            else:
                filled_data[f'shipping_{key}'] = value
        
        return filled_data
    
    def submit_order(self, billing_data: Dict[str, str], shipping_data: Dict[str, str] = None,
                     payment_method: str = None, payment_data: Dict[str, str] = None) -> Dict[str, Any]:
        
        self.behavior.human_delay(action_type="thinking")
        
        if not self.checkout:
            self.proceed_to_checkout()
        
        order_data = {}
        
        order_data.update(self.fill_billing_info(billing_data))
        
        if shipping_data:
            order_data['ship_to_different_address'] = '1'
            order_data.update(self.fill_shipping_info(shipping_data))
        
        order_data['payment_method'] = payment_method or self.checkout.payment_method or 'stripe'
        
        if payment_data:
            order_data.update(payment_data)
        
        order_data['woocommerce-process-checkout-nonce'] = self.checkout.nonce
        order_data['_wp_http_referer'] = '/checkout/'
        
        if 'wp' in self.nonces:
            order_data['_wpnonce'] = self.nonces['wp']
        
        order_data['terms'] = 'on'
        order_data['terms-field'] = '1'
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': self.checkout.checkout_url
        }
        
        ajax_url = f"{self.base_url}/?wc-ajax=checkout"
        
        self.behavior.human_delay(action_type="button_click")
        
        response = self.http_client.post(ajax_url, data=order_data, headers=headers)
        
        result = {
            'success': False,
            'order_id': None,
            'redirect_url': None,
            'error': None,
            'requires_action': False,
            'action_type': None,
            'action_data': None
        }
        
        if response.status_code == 200:
            try:
                response_data = json.loads(response.body)
                
                if response_data.get('result') == 'success':
                    result['success'] = True
                    result['redirect_url'] = response_data.get('redirect')
                    
                    if result['redirect_url']:
                        order_match = re.search(r'order-received/(\d+)', result['redirect_url'])
                        if order_match:
                            result['order_id'] = order_match.group(1)
                
                elif response_data.get('result') == 'failure':
                    result['error'] = response_data.get('messages', 'Unknown error')
                
                if 'stripe_intent_secret' in response_data or 'client_secret' in response_data:
                    result['requires_action'] = True
                    result['action_type'] = '3ds'
                    result['action_data'] = {
                        'client_secret': response_data.get('stripe_intent_secret') or response_data.get('client_secret'),
                        'return_url': response_data.get('return_url')
                    }
                
            except json.JSONDecodeError:
                result['error'] = 'Invalid response from server'
        else:
            result['error'] = f'HTTP {response.status_code}'
        
        return result
    
    def get_order_confirmation(self, order_id: str) -> Dict[str, Any]:
        confirmation_url = f"{self.base_url}/checkout/order-received/{order_id}/"
        response = self.http_client.get(confirmation_url)
        
        if response.status_code != 200:
            return {'success': False, 'error': 'Could not retrieve order confirmation'}
        
        soup = BeautifulSoup(response.body, 'html.parser')
        
        confirmation = {
            'success': True,
            'order_id': order_id,
            'order_number': None,
            'total': None,
            'payment_method': None,
            'status': None
        }
        
        order_number_elem = soup.find('li', class_='woocommerce-order-overview__order')
        if order_number_elem:
            confirmation['order_number'] = order_number_elem.get_text(strip=True)
        
        total_elem = soup.find('li', class_='woocommerce-order-overview__total')
        if total_elem:
            total_text = total_elem.get_text(strip=True)
            total_match = re.search(r'[\d,.]+', total_text)
            if total_match:
                confirmation['total'] = total_match.group(0)
        
        payment_elem = soup.find('li', class_='woocommerce-order-overview__payment-method')
        if payment_elem:
            confirmation['payment_method'] = payment_elem.get_text(strip=True)
        
        return confirmation
