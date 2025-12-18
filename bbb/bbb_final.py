import requests
import re
import json
import base64
import time
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TokenCache:
    """Token caching system with TTL (Time To Live)"""
    
    def __init__(self, ttl_minutes: int = 5):
        self.cache: Dict[str, Tuple[str, datetime]] = {}
        self.ttl = timedelta(minutes=ttl_minutes)
    
    def get(self, site_url: str) -> Optional[str]:
        """Retrieve cached token if still valid"""
        if site_url in self.cache:
            token, timestamp = self.cache[site_url]
            if datetime.now() - timestamp < self.ttl:
                logger.info(f"✓ Cache hit for {site_url}")
                return token
            else:
                logger.info(f"✗ Cache expired for {site_url}")
                del self.cache[site_url]
        return None
    
    def set(self, site_url: str, token: str):
        """Store token with timestamp"""
        self.cache[site_url] = (token, datetime.now())
        logger.info(f"✓ Token cached for {site_url}")
    
    def clear(self):
        """Clear all cached tokens"""
        self.cache.clear()


class PerformanceMetrics:
    """Track performance of extraction strategies"""
    
    def __init__(self):
        self.metrics: Dict[str, Dict[str, any]] = {}
    
    def record_attempt(self, strategy: str, success: bool, duration: float):
        """Record strategy attempt with timing"""
        if strategy not in self.metrics:
            self.metrics[strategy] = {
                'attempts': 0,
                'successes': 0,
                'failures': 0,
                'total_time': 0.0,
                'avg_time': 0.0
            }
        
        self.metrics[strategy]['attempts'] += 1
        if success:
            self.metrics[strategy]['successes'] += 1
        else:
            self.metrics[strategy]['failures'] += 1
        
        self.metrics[strategy]['total_time'] += duration
        self.metrics[strategy]['avg_time'] = (
            self.metrics[strategy]['total_time'] / self.metrics[strategy]['attempts']
        )
    
    def get_success_rate(self, strategy: str) -> float:
        """Calculate success rate for a strategy"""
        if strategy not in self.metrics or self.metrics[strategy]['attempts'] == 0:
            return 0.0
        return (self.metrics[strategy]['successes'] / self.metrics[strategy]['attempts']) * 100
    
    def get_report(self) -> str:
        """Generate performance report"""
        report = "\n=== Performance Metrics ===\n"
        for strategy, data in self.metrics.items():
            success_rate = self.get_success_rate(strategy)
            report += f"\n{strategy}:\n"
            report += f"  Attempts: {data['attempts']}\n"
            report += f"  Successes: {data['successes']}\n"
            report += f"  Failures: {data['failures']}\n"
            report += f"  Success Rate: {success_rate:.2f}%\n"
            report += f"  Avg Time: {data['avg_time']:.4f}s\n"
        return report


class EnhancedTokenExtractor:
    """Enhanced token extraction system with multiple strategies"""
    
    # Enhanced regex patterns for token detection
    BRAINTREE_CLIENT_TOKEN_PATTERNS = [
        r'braintree_client_token["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'clientToken["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'client_token["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'data-client-token\s*=\s*["\']([^"\']+)["\']',
        r'client-token["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'authorization["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'braintreeToken["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'bt_client_token["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'token["\']?\s*[:=]\s*["\']([A-Za-z0-9+/=]{100,})["\']',
        r'clientAuthorization["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'paymentToken["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'btClientToken["\']?\s*[:=]\s*["\']([^"\']+)["\']',
    ]
    
    AUTH_FINGERPRINT_PATTERNS = [
        r'"authorizationFingerprint"\s*:\s*"([^"]+)"',
        r'"authorization_fingerprint"\s*:\s*"([^"]+)"',
        r'authorizationFingerprint["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'auth_fingerprint["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'"fingerprint"\s*:\s*"([^"]+)"',
        r'fingerprint["\']?\s*[:=]\s*["\']([^"\']+)["\']',
    ]
    
    GRAPHQL_ENDPOINT_PATTERNS = [
        r'graphql["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'endpoint["\']?\s*[:=]\s*["\']([^"\']*graphql[^"\']*)["\']',
        r'url["\']?\s*[:=]\s*["\']([^"\']*graphql[^"\']*)["\']',
        r'(https?://[^"\']*graphql[^"\']*)',
    ]
    
    JAVASCRIPT_VARIABLE_PATTERNS = [
        r'var\s+(\w+)\s*=\s*\{[^}]*braintree[^}]*\}',
        r'const\s+(\w+)\s*=\s*\{[^}]*braintree[^}]*\}',
        r'let\s+(\w+)\s*=\s*\{[^}]*braintree[^}]*\}',
        r'window\.(\w+)\s*=\s*\{[^}]*braintree[^}]*\}',
    ]
    
    def __init__(self, session: requests.Session = None):
        self.session = session or requests.Session()
        self.cache = TokenCache(ttl_minutes=5)
        self.metrics = PerformanceMetrics()
        
        # Default headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
    
    def safe_base64_decode(self, encoded_str: str) -> Optional[Dict]:
        """
        Safely decode base64 string with validation
        
        Args:
            encoded_str: Base64 encoded string
            
        Returns:
            Decoded JSON object or None
        """
        try:
            # Remove whitespace
            encoded_str = encoded_str.strip()
            
            # Validate base64 format (basic check)
            if not re.match(r'^[A-Za-z0-9+/]*={0,2}$', encoded_str):
                logger.warning("Invalid base64 format")
                return None
            
            # Auto-add padding if needed
            padding = len(encoded_str) % 4
            if padding:
                encoded_str += '=' * (4 - padding)
            
            # Decode
            decoded_bytes = base64.b64decode(encoded_str)
            decoded_str = decoded_bytes.decode('utf-8')
            
            # Validate JSON
            try:
                json_obj = json.loads(decoded_str)
                logger.info("✓ Successfully decoded and validated JSON")
                return json_obj
            except json.JSONDecodeError:
                logger.warning("Decoded string is not valid JSON")
                return None
                
        except Exception as e:
            logger.error(f"Base64 decode error: {str(e)}")
            return None
    
    def extract_embedded_token_from_payment_methods(self, site_url: str) -> Optional[str]:
        """Extract token from payment methods page"""
        strategy_name = "extract_embedded_token_from_payment_methods"
        start_time = time.time()
        
        try:
            logger.info(f"[{strategy_name}] Attempting extraction from {site_url}")
            
            payment_urls = [
                f"{site_url}/checkout/",
                f"{site_url}/cart/",
                f"{site_url}/payment-methods/",
                f"{site_url}/my-account/payment-methods/",
                f"{site_url}/wc-api/braintree_payment_method/",
            ]
            
            for url in payment_urls:
                try:
                    response = self.session.get(url, timeout=10)
                    if response.status_code == 200:
                        # Try all patterns
                        for pattern in self.BRAINTREE_CLIENT_TOKEN_PATTERNS:
                            match = re.search(pattern, response.text, re.IGNORECASE)
                            if match:
                                token = match.group(1)
                                logger.info(f"✓ Token found at {url}")
                                self.metrics.record_attempt(strategy_name, True, time.time() - start_time)
                                return token
                except Exception as e:
                    logger.debug(f"Error checking {url}: {str(e)}")
                    continue
            
            self.metrics.record_attempt(strategy_name, False, time.time() - start_time)
            return None
            
        except Exception as e:
            logger.error(f"[{strategy_name}] Error: {str(e)}")
            self.metrics.record_attempt(strategy_name, False, time.time() - start_time)
            return None
    
    def extract_embedded_token_from_add_payment(self, site_url: str) -> Optional[str]:
        """Extract token from add payment method page"""
        strategy_name = "extract_embedded_token_from_add_payment"
        start_time = time.time()
        
        try:
            logger.info(f"[{strategy_name}] Attempting extraction from {site_url}")
            
            add_payment_urls = [
                f"{site_url}/my-account/add-payment-method/",
                f"{site_url}/account/add-payment-method/",
                f"{site_url}/customer/payment-methods/add/",
            ]
            
            for url in add_payment_urls:
                try:
                    response = self.session.get(url, timeout=10)
                    if response.status_code == 200:
                        for pattern in self.BRAINTREE_CLIENT_TOKEN_PATTERNS:
                            match = re.search(pattern, response.text, re.IGNORECASE)
                            if match:
                                token = match.group(1)
                                logger.info(f"✓ Token found at {url}")
                                self.metrics.record_attempt(strategy_name, True, time.time() - start_time)
                                return token
                except Exception as e:
                    logger.debug(f"Error checking {url}: {str(e)}")
                    continue
            
            self.metrics.record_attempt(strategy_name, False, time.time() - start_time)
            return None
            
        except Exception as e:
            logger.error(f"[{strategy_name}] Error: {str(e)}")
            self.metrics.record_attempt(strategy_name, False, time.time() - start_time)
            return None
    
    def extract_via_ajax_client_token(self, site_url: str) -> Optional[str]:
        """Extract token via AJAX endpoint"""
        strategy_name = "extract_via_ajax_client_token"
        start_time = time.time()
        
        try:
            logger.info(f"[{strategy_name}] Attempting extraction from {site_url}")
            
            ajax_endpoints = [
                f"{site_url}/wp-admin/admin-ajax.php?action=get_client_token",
                f"{site_url}/wp-admin/admin-ajax.php?action=braintree_get_client_token",
                f"{site_url}/wp-admin/admin-ajax.php?action=wc_braintree_get_client_token",
                f"{site_url}/api/braintree/token",
                f"{site_url}/api/payment/token",
            ]
            
            for endpoint in ajax_endpoints:
                try:
                    response = self.session.post(endpoint, timeout=10)
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            if 'token' in data:
                                logger.info(f"✓ Token found via AJAX at {endpoint}")
                                self.metrics.record_attempt(strategy_name, True, time.time() - start_time)
                                return data['token']
                            elif 'client_token' in data:
                                logger.info(f"✓ Token found via AJAX at {endpoint}")
                                self.metrics.record_attempt(strategy_name, True, time.time() - start_time)
                                return data['client_token']
                        except:
                            # Try regex on response text
                            for pattern in self.BRAINTREE_CLIENT_TOKEN_PATTERNS:
                                match = re.search(pattern, response.text, re.IGNORECASE)
                                if match:
                                    token = match.group(1)
                                    logger.info(f"✓ Token found via AJAX at {endpoint}")
                                    self.metrics.record_attempt(strategy_name, True, time.time() - start_time)
                                    return token
                except Exception as e:
                    logger.debug(f"Error checking {endpoint}: {str(e)}")
                    continue
            
            self.metrics.record_attempt(strategy_name, False, time.time() - start_time)
            return None
            
        except Exception as e:
            logger.error(f"[{strategy_name}] Error: {str(e)}")
            self.metrics.record_attempt(strategy_name, False, time.time() - start_time)
            return None
    
    def extract_from_javascript_variables(self, site_url: str) -> Optional[str]:
        """Extract token from JavaScript variables in page source"""
        strategy_name = "extract_from_javascript_variables"
        start_time = time.time()
        
        try:
            logger.info(f"[{strategy_name}] Attempting extraction from {site_url}")
            
            urls_to_check = [
                site_url,
                f"{site_url}/checkout/",
                f"{site_url}/cart/",
            ]
            
            for url in urls_to_check:
                try:
                    response = self.session.get(url, timeout=10)
                    if response.status_code == 200:
                        # Look for braintree config objects
                        config_patterns = [
                            r'braintreeConfig\s*=\s*(\{[^;]+\})',
                            r'braintree\s*=\s*(\{[^;]+\})',
                            r'paymentConfig\s*=\s*(\{[^;]+\})',
                        ]
                        
                        for pattern in config_patterns:
                            match = re.search(pattern, response.text, re.IGNORECASE | re.DOTALL)
                            if match:
                                config_str = match.group(1)
                                # Look for token within config
                                for token_pattern in self.BRAINTREE_CLIENT_TOKEN_PATTERNS:
                                    token_match = re.search(token_pattern, config_str, re.IGNORECASE)
                                    if token_match:
                                        token = token_match.group(1)
                                        logger.info(f"✓ Token found in JS variable at {url}")
                                        self.metrics.record_attempt(strategy_name, True, time.time() - start_time)
                                        return token
                except Exception as e:
                    logger.debug(f"Error checking {url}: {str(e)}")
                    continue
            
            self.metrics.record_attempt(strategy_name, False, time.time() - start_time)
            return None
            
        except Exception as e:
            logger.error(f"[{strategy_name}] Error: {str(e)}")
            self.metrics.record_attempt(strategy_name, False, time.time() - start_time)
            return None
    
    def extract_from_inline_scripts(self, site_url: str) -> Optional[str]:
        """Extract token from inline script tags"""
        strategy_name = "extract_from_inline_scripts"
        start_time = time.time()
        
        try:
            logger.info(f"[{strategy_name}] Attempting extraction from {site_url}")
            
            urls_to_check = [
                site_url,
                f"{site_url}/checkout/",
                f"{site_url}/my-account/",
            ]
            
            for url in urls_to_check:
                try:
                    response = self.session.get(url, timeout=10)
                    if response.status_code == 200:
                        # Extract all script tags
                        script_pattern = r'<script[^>]*>(.*?)</script>'
                        scripts = re.findall(script_pattern, response.text, re.IGNORECASE | re.DOTALL)
                        
                        for script in scripts:
                            # Skip external scripts
                            if 'src=' in script[:100]:
                                continue
                            
                            # Look for tokens in inline scripts
                            for pattern in self.BRAINTREE_CLIENT_TOKEN_PATTERNS:
                                match = re.search(pattern, script, re.IGNORECASE)
                                if match:
                                    token = match.group(1)
                                    # Validate it looks like a token (base64-ish)
                                    if len(token) > 50:
                                        logger.info(f"✓ Token found in inline script at {url}")
                                        self.metrics.record_attempt(strategy_name, True, time.time() - start_time)
                                        return token
                except Exception as e:
                    logger.debug(f"Error checking {url}: {str(e)}")
                    continue
            
            self.metrics.record_attempt(strategy_name, False, time.time() - start_time)
            return None
            
        except Exception as e:
            logger.error(f"[{strategy_name}] Error: {str(e)}")
            self.metrics.record_attempt(strategy_name, False, time.time() - start_time)
            return None
    
    def extract_from_wp_config(self, site_url: str) -> Optional[str]:
        """Extract token from WordPress config endpoints"""
        strategy_name = "extract_from_wp_config"
        start_time = time.time()
        
        try:
            logger.info(f"[{strategy_name}] Attempting extraction from {site_url}")
            
            wp_endpoints = [
                f"{site_url}/wp-json/wc/v3/payment_gateways/braintree",
                f"{site_url}/wp-json/wc/v2/payment_gateways/braintree",
                f"{site_url}/wp-json/wc/store/payment-methods",
                f"{site_url}/wp-json/braintree/v1/token",
            ]
            
            for endpoint in wp_endpoints:
                try:
                    response = self.session.get(endpoint, timeout=10)
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            # Search recursively for token
                            token = self._search_dict_for_token(data)
                            if token:
                                logger.info(f"✓ Token found in WP config at {endpoint}")
                                self.metrics.record_attempt(strategy_name, True, time.time() - start_time)
                                return token
                        except:
                            pass
                except Exception as e:
                    logger.debug(f"Error checking {endpoint}: {str(e)}")
                    continue
            
            self.metrics.record_attempt(strategy_name, False, time.time() - start_time)
            return None
            
        except Exception as e:
            logger.error(f"[{strategy_name}] Error: {str(e)}")
            self.metrics.record_attempt(strategy_name, False, time.time() - start_time)
            return None
    
    def extract_via_graphql_endpoint_probe(self, site_url: str) -> Optional[str]:
        """Probe for GraphQL endpoints and extract tokens"""
        strategy_name = "extract_via_graphql_endpoint_probe"
        start_time = time.time()
        
        try:
            logger.info(f"[{strategy_name}] Attempting extraction from {site_url}")
            
            # Common GraphQL endpoints
            graphql_endpoints = [
                f"{site_url}/graphql",
                f"{site_url}/api/graphql",
                f"{site_url}/v1/graphql",
                f"{site_url}/wp-json/graphql",
                f"{site_url}/index.php?graphql",
            ]
            
            # GraphQL introspection query for payment tokens
            introspection_query = {
                "query": """
                {
                    __type(name: "PaymentMethod") {
                        fields {
                            name
                            type {
                                name
                            }
                        }
                    }
                }
                """
            }
            
            # Simple query to trigger token generation
            simple_query = {
                "query": "{ clientToken }"
            }
            
            for endpoint in graphql_endpoints:
                try:
                    # Try simple query first
                    response = self.session.post(
                        endpoint,
                        json=simple_query,
                        headers={'Content-Type': 'application/json'},
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            token = self._search_dict_for_token(data)
                            if token:
                                logger.info(f"✓ Token found via GraphQL at {endpoint}")
                                self.metrics.record_attempt(strategy_name, True, time.time() - start_time)
                                return token
                        except:
                            pass
                    
                    # Try introspection
                    response = self.session.post(
                        endpoint,
                        json=introspection_query,
                        headers={'Content-Type': 'application/json'},
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        # Look for token in response
                        for pattern in self.BRAINTREE_CLIENT_TOKEN_PATTERNS:
                            match = re.search(pattern, response.text, re.IGNORECASE)
                            if match:
                                token = match.group(1)
                                logger.info(f"✓ Token found via GraphQL introspection at {endpoint}")
                                self.metrics.record_attempt(strategy_name, True, time.time() - start_time)
                                return token
                                
                except Exception as e:
                    logger.debug(f"Error checking {endpoint}: {str(e)}")
                    continue
            
            self.metrics.record_attempt(strategy_name, False, time.time() - start_time)
            return None
            
        except Exception as e:
            logger.error(f"[{strategy_name}] Error: {str(e)}")
            self.metrics.record_attempt(strategy_name, False, time.time() - start_time)
            return None
    
    def _search_dict_for_token(self, data: any, depth: int = 0, max_depth: int = 10) -> Optional[str]:
        """Recursively search dictionary for token-like values"""
        if depth > max_depth:
            return None
        
        if isinstance(data, dict):
            # Check for common token keys
            token_keys = ['token', 'client_token', 'clientToken', 'authorization', 
                          'authorizationFingerprint', 'braintree_client_token']
            
            for key in token_keys:
                if key in data and isinstance(data[key], str) and len(data[key]) > 50:
                    return data[key]
            
            # Recurse into nested dicts
            for value in data.values():
                result = self._search_dict_for_token(value, depth + 1, max_depth)
                if result:
                    return result
        
        elif isinstance(data, list):
            for item in data:
                result = self._search_dict_for_token(item, depth + 1, max_depth)
                if result:
                    return result
        
        return None
    
    def extract_token(self, site_url: str, use_cache: bool = True) -> Optional[str]:
        """
        Main method to extract token using all available strategies
        
        Args:
            site_url: Target website URL
            use_cache: Whether to use cached tokens
            
        Returns:
            Extracted token or None
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Starting token extraction for: {site_url}")
        logger.info(f"{'='*60}\n")
        
        # Check cache first
        if use_cache:
            cached_token = self.cache.get(site_url)
            if cached_token:
                return cached_token
        
        # Define extraction strategies in order of preference
        strategies = [
            self.extract_via_ajax_client_token,
            self.extract_embedded_token_from_payment_methods,
            self.extract_embedded_token_from_add_payment,
            self.extract_from_javascript_variables,
            self.extract_from_inline_scripts,
            self.extract_from_wp_config,
            self.extract_via_graphql_endpoint_probe,
        ]
        
        # Try each strategy
        for i, strategy in enumerate(strategies, 1):
            logger.info(f"\n[Strategy {i}/{len(strategies)}] Trying: {strategy.__name__}")
            token = strategy(site_url)
            
            if token:
                logger.info(f"\n{'='*60}")
                logger.info(f"✓ SUCCESS! Token extracted using: {strategy.__name__}")
                logger.info(f"{'='*60}\n")
                
                # Cache the successful token
                self.cache.set(site_url, token)
                
                # Validate token by attempting to decode (if it's base64)
                decoded = self.safe_base64_decode(token)
                if decoded:
                    logger.info(f"Token successfully decoded and validated")
                    if 'authorizationFingerprint' in decoded:
                        logger.info(f"✓ Authorization fingerprint found in token")
                
                return token
        
        logger.warning(f"\n{'='*60}")
        logger.warning(f"✗ FAILED - No token found using any strategy")
        logger.warning(f"{'='*60}\n")
        
        return None


# Global instances
_token_extractor = None
_performance_metrics = None


def get_enhanced_token_extractor() -> EnhancedTokenExtractor:
    """Get or create global token extractor instance"""
    global _token_extractor
    if _token_extractor is None:
        _token_extractor = EnhancedTokenExtractor()
    return _token_extractor


def get_braintree_authorization_token(site_url: str, use_cache: bool = True) -> Optional[str]:
    """
    Enhanced function to extract Braintree authorization token
    
    This function replaces the old implementation with a comprehensive
    multi-strategy approach that includes:
    - Token caching with TTL
    - Multiple extraction strategies
    - Performance metrics tracking
    - Comprehensive logging
    - Base64 validation
    - GraphQL endpoint probing
    
    Args:
        site_url: Target website URL
        use_cache: Whether to use cached tokens (default: True)
        
    Returns:
        Braintree client token or None if not found
        
    Examples:
        >>> token = get_braintree_authorization_token("https://example.com")
        >>> if token:
        ...     print(f"Token: {token[:50]}...")
    """
    extractor = get_enhanced_token_extractor()
    token = extractor.extract_token(site_url, use_cache=use_cache)
    
    # Log performance metrics
    logger.info(extractor.metrics.get_report())
    
    return token


def clear_token_cache():
    """Clear the token cache"""
    extractor = get_enhanced_token_extractor()
    extractor.cache.clear()
    logger.info("Token cache cleared")


def get_performance_report() -> str:
    """Get performance metrics report"""
    extractor = get_enhanced_token_extractor()
    return extractor.metrics.get_report()


# Backward compatibility - keep any existing function signatures
def extract_authorization_fingerprint(token: str) -> Optional[str]:
    """
    Extract authorization fingerprint from token
    
    Args:
        token: Braintree client token
        
    Returns:
        Authorization fingerprint or None
    """
    extractor = get_enhanced_token_extractor()
    decoded = extractor.safe_base64_decode(token)
    
    if decoded and 'authorizationFingerprint' in decoded:
        return decoded['authorizationFingerprint']
    
    # Try regex patterns as fallback
    for pattern in EnhancedTokenExtractor.AUTH_FINGERPRINT_PATTERNS:
        match = re.search(pattern, token, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


if __name__ == "__main__":
    # Example usage and testing
    import sys
    
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
    else:
        test_url = "https://example.com"
    
    print(f"\nTesting Enhanced Token Extractor")
    print(f"{'='*60}\n")
    
    # Extract token
    token = get_braintree_authorization_token(test_url, use_cache=False)
    
    if token:
        print(f"\n✓ Token extracted successfully!")
        print(f"Token (first 100 chars): {token[:100]}...")
        print(f"Token length: {len(token)} characters")
        
        # Try to extract fingerprint
        fingerprint = extract_authorization_fingerprint(token)
        if fingerprint:
            print(f"\n✓ Authorization Fingerprint: {fingerprint[:50]}...")
    else:
        print(f"\n✗ Failed to extract token")
    
    # Show performance report
    print(f"\n{get_performance_report()}")
    
    # Test caching
    print(f"\n\nTesting cache system...")
    token2 = get_braintree_authorization_token(test_url, use_cache=True)
    if token2:
        print(f"✓ Token retrieved (from cache if available)")
    
    print(f"\n{'='*60}")
    print(f"Testing complete!")
    print(f"{'='*60}\n")
