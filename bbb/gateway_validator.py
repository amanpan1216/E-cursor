"""
Gateway Validator - Advanced Site Compatibility Checker

This tool performs deep validation of discovered sites to check:
1. Payment gateway compatibility (Braintree, NMI, etc.)
2. Nonce extraction capability
3. Registration/login functionality
4. WooCommerce version compatibility
5. Security features and anti-bot measures

Integrates with bbb_final.py for compatibility testing.
"""

import asyncio
import aiohttp
import json
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Detailed validation result for a site"""
    domain: str
    validated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Compatibility scores (0-100)
    overall_score: int = 0
    nonce_extraction_score: int = 0
    gateway_compatibility_score: int = 0
    security_score: int = 0
    
    # Gateway detection
    has_braintree: bool = False
    has_nmi: bool = False
    has_stripe: bool = False
    has_paypal: bool = False
    primary_gateway: str = ""
    
    # Nonce detection
    register_nonce_found: bool = False
    login_nonce_found: bool = False
    billing_nonce_found: bool = False
    payment_method_nonce_found: bool = False
    client_token_nonce_found: bool = False
    
    # Features
    has_registration: bool = False
    has_login: bool = False
    has_my_account: bool = False
    has_payment_methods_page: bool = False
    has_add_payment_method: bool = False
    
    # Security
    has_cloudflare: bool = False
    has_captcha: bool = False
    has_rate_limiting: bool = False
    has_ssl: bool = False
    security_headers: List[str] = field(default_factory=list)
    
    # Technical details
    woocommerce_version: str = ""
    wordpress_version: str = ""
    php_version: str = ""
    server_software: str = ""
    
    # Nonce extraction details
    nonce_patterns_matched: Dict[str, int] = field(default_factory=dict)
    
    # Compatibility notes
    compatibility_notes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    # Recommended configuration
    recommended_config: Dict = field(default_factory=dict)
    
    def to_dict(self):
        return asdict(self)
    
    def calculate_scores(self):
        """Calculate compatibility scores"""
        # Nonce extraction score
        nonce_count = sum([
            self.register_nonce_found,
            self.login_nonce_found,
            self.billing_nonce_found,
            self.payment_method_nonce_found,
            self.client_token_nonce_found
        ])
        self.nonce_extraction_score = int((nonce_count / 5) * 100)
        
        # Gateway compatibility score
        gateway_score = 0
        if self.has_braintree:
            gateway_score = 100
        elif self.has_nmi:
            gateway_score = 50  # NMI is detected but not supported
        elif self.has_stripe or self.has_paypal:
            gateway_score = 25
        self.gateway_compatibility_score = gateway_score
        
        # Security score (higher is more challenging)
        security_penalties = sum([
            self.has_cloudflare * 20,
            self.has_captcha * 30,
            self.has_rate_limiting * 20,
            len(self.security_headers) * 5
        ])
        self.security_score = min(100, security_penalties)
        
        # Overall score (weighted average)
        self.overall_score = int(
            (self.nonce_extraction_score * 0.4) +
            (self.gateway_compatibility_score * 0.5) +
            ((100 - self.security_score) * 0.1)
        )


class GatewayValidator:
    """Advanced gateway validation system"""
    
    # Enhanced regex patterns for nonce detection
    NONCE_PATTERNS = {
        'register': [
            re.compile(r'name=["\']woocommerce-register-nonce["\']\s+value=["\']([^"\']+)["\']'),
            re.compile(r'id=["\']woocommerce-register-nonce["\']\s+value=["\']([^"\']+)["\']'),
            re.compile(r'woocommerce-register-nonce["\']?\s*:\s*["\']([^"\']+)["\']'),
        ],
        'login': [
            re.compile(r'name=["\']woocommerce-login-nonce["\']\s+value=["\']([^"\']+)["\']'),
            re.compile(r'id=["\']woocommerce-login-nonce["\']\s+value=["\']([^"\']+)["\']'),
            re.compile(r'woocommerce-login-nonce["\']?\s*:\s*["\']([^"\']+)["\']'),
        ],
        'billing': [
            re.compile(r'name=["\']woocommerce-edit-address-nonce["\']\s+value=["\']([^"\']+)["\']'),
            re.compile(r'id=["\']woocommerce-edit-address-nonce["\']\s+value=["\']([^"\']+)["\']'),
        ],
        'payment_method': [
            re.compile(r'name=["\']woocommerce-add-payment-method-nonce["\']\s+value=["\']([^"\']+)["\']'),
            re.compile(r'id=["\']woocommerce-add-payment-method-nonce["\']\s+value=["\']([^"\']+)["\']'),
        ],
        'client_token': [
            re.compile(r'wc-braintree-credit-card-get-client-token-nonce["\']?\s+value=["\']([^"\']+)["\']'),
            re.compile(r'client_token_nonce["\']?\s*:\s*["\']([^"\']+)["\']'),
        ]
    }
    
    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.results: List[ValidationResult] = []
    
    async def validate_site(self, domain: str, session: Optional[aiohttp.ClientSession] = None) -> ValidationResult:
        """
        Perform comprehensive validation of a single site.
        
        Args:
            domain: Domain to validate
            session: Optional aiohttp session
            
        Returns:
            ValidationResult with detailed compatibility information
        """
        if not domain.startswith('http'):
            domain = f'https://{domain}'
        
        result = ValidationResult(domain=domain.replace('https://', '').replace('http://', ''))
        
        # Create session if not provided
        close_session = session is None
        if session is None:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            session = aiohttp.ClientSession(timeout=timeout)
        
        try:
            # Step 1: Check main page
            await self._check_main_page(session, domain, result)
            
            # Step 2: Check /my-account/ page
            await self._check_my_account_page(session, domain, result)
            
            # Step 3: Check payment methods page
            await self._check_payment_methods_page(session, domain, result)
            
            # Step 4: Analyze security
            await self._analyze_security(session, domain, result)
            
            # Calculate scores
            result.calculate_scores()
            
            # Generate recommendations
            self._generate_recommendations(result)
            
            logger.info(f"✓ Validated {result.domain}: Score={result.overall_score}/100")
            
        except Exception as e:
            result.errors.append(f"Validation error: {str(e)}")
            logger.error(f"✗ Failed to validate {result.domain}: {e}")
        
        finally:
            if close_session:
                await session.close()
        
        return result
    
    async def _check_main_page(self, session: aiohttp.ClientSession, 
                               domain: str, result: ValidationResult):
        """Check main page for basic information"""
        try:
            async with session.get(domain, allow_redirects=True, ssl=False) as response:
                result.has_ssl = domain.startswith('https://')
                result.server_software = response.headers.get('Server', '')
                
                html = await response.text()
                html_lower = html.lower()
                
                # Detect gateways
                result.has_braintree = 'braintree' in html_lower
                result.has_nmi = 'nmi' in html_lower or 'nmi-gateway' in html_lower
                result.has_stripe = 'stripe' in html_lower
                result.has_paypal = 'paypal' in html_lower
                
                # Determine primary gateway
                if result.has_braintree:
                    result.primary_gateway = 'braintree'
                elif result.has_nmi:
                    result.primary_gateway = 'nmi'
                elif result.has_stripe:
                    result.primary_gateway = 'stripe'
                elif result.has_paypal:
                    result.primary_gateway = 'paypal'
                
                # Extract versions
                wc_match = re.search(r'woocommerce[/-](\d+\.\d+\.\d+)', html_lower)
                if wc_match:
                    result.woocommerce_version = wc_match.group(1)
                
                wp_match = re.search(r'wordpress[/-](\d+\.\d+\.\d+)', html_lower)
                if wp_match:
                    result.wordpress_version = wp_match.group(1)
                
                # Check for Cloudflare
                result.has_cloudflare = 'cloudflare' in response.headers.get('Server', '').lower()
                
        except Exception as e:
            result.errors.append(f"Main page check failed: {str(e)}")
    
    async def _check_my_account_page(self, session: aiohttp.ClientSession,
                                    domain: str, result: ValidationResult):
        """Check /my-account/ page for nonces and features"""
        try:
            url = f"{domain}/my-account/"
            async with session.get(url, allow_redirects=True, ssl=False) as response:
                if response.status == 200:
                    result.has_my_account = True
                    html = await response.text()
                    
                    # Check for nonces using multiple patterns
                    result.nonce_patterns_matched = {}
                    
                    for nonce_type, patterns in self.NONCE_PATTERNS.items():
                        matches = 0
                        for pattern in patterns:
                            if pattern.search(html):
                                matches += 1
                        result.nonce_patterns_matched[nonce_type] = matches
                    
                    # Set nonce flags
                    result.register_nonce_found = result.nonce_patterns_matched.get('register', 0) > 0
                    result.login_nonce_found = result.nonce_patterns_matched.get('login', 0) > 0
                    
                    # Check for registration and login
                    result.has_registration = bool(re.search(r'register|sign up', html, re.IGNORECASE))
                    result.has_login = bool(re.search(r'login|sign in', html, re.IGNORECASE))
                    
        except Exception as e:
            result.warnings.append(f"/my-account/ check failed: {str(e)}")
    
    async def _check_payment_methods_page(self, session: aiohttp.ClientSession,
                                         domain: str, result: ValidationResult):
        """Check payment methods pages for Braintree integration"""
        try:
            # Check /my-account/payment-methods/
            url = f"{domain}/my-account/payment-methods/"
            async with session.get(url, allow_redirects=True, ssl=False) as response:
                if response.status == 200:
                    result.has_payment_methods_page = True
                    html = await response.text()
                    
                    # Check for payment method nonce
                    matches = 0
                    for pattern in self.NONCE_PATTERNS['payment_method']:
                        if pattern.search(html):
                            matches += 1
                    
                    if 'payment_method' not in result.nonce_patterns_matched:
                        result.nonce_patterns_matched['payment_method'] = matches
                    else:
                        result.nonce_patterns_matched['payment_method'] += matches
            
            # Check /my-account/add-payment-method/
            url = f"{domain}/my-account/add-payment-method/"
            async with session.get(url, allow_redirects=True, ssl=False) as response:
                if response.status == 200:
                    result.has_add_payment_method = True
                    html = await response.text()
                    
                    # Update nonce detection
                    result.payment_method_nonce_found = bool(
                        result.nonce_patterns_matched.get('payment_method', 0) > 0
                    )
                    
                    # Check for client token nonce
                    matches = 0
                    for pattern in self.NONCE_PATTERNS['client_token']:
                        if pattern.search(html):
                            matches += 1
                    result.nonce_patterns_matched['client_token'] = matches
                    result.client_token_nonce_found = matches > 0
                    
        except Exception as e:
            result.warnings.append(f"Payment methods check failed: {str(e)}")
    
    async def _analyze_security(self, session: aiohttp.ClientSession,
                               domain: str, result: ValidationResult):
        """Analyze security features and anti-bot measures"""
        try:
            async with session.get(domain, ssl=False) as response:
                headers = response.headers
                
                # Check security headers
                security_header_names = [
                    'X-Frame-Options',
                    'X-Content-Type-Options',
                    'Strict-Transport-Security',
                    'Content-Security-Policy',
                    'X-XSS-Protection'
                ]
                
                for header in security_header_names:
                    if header in headers:
                        result.security_headers.append(header)
                
                # Check for CAPTCHA in HTML
                html = await response.text()
                html_lower = html.lower()
                
                result.has_captcha = any(
                    keyword in html_lower 
                    for keyword in ['recaptcha', 'hcaptcha', 'captcha']
                )
                
                # Check for rate limiting (via headers)
                result.has_rate_limiting = any(
                    'rate-limit' in str(k).lower() or 'rate-limit' in str(v).lower()
                    for k, v in headers.items()
                )
                
        except Exception as e:
            result.warnings.append(f"Security analysis failed: {str(e)}")
    
    def _generate_recommendations(self, result: ValidationResult):
        """Generate configuration recommendations based on validation"""
        config = {
            'enabled': result.overall_score >= 50,
            'retry_strategy': 'normal',
            'max_retries': 3,
            'graphql_retries': 3,
            'payment_gateway': result.primary_gateway,
            'requires_billing': True,
            'delays': {
                'between_requests': 2.0,
                'after_registration': 3.0
            }
        }
        
        # Adjust based on security score
        if result.security_score > 50:
            config['retry_strategy'] = 'conservative'
            config['max_retries'] = 2
            config['delays']['between_requests'] = 3.0
            config['delays']['after_registration'] = 5.0
            result.compatibility_notes.append(
                "High security score - using conservative settings"
            )
        
        # Adjust based on Cloudflare
        if result.has_cloudflare:
            config['delays']['between_requests'] = 3.0
            result.compatibility_notes.append(
                "Cloudflare detected - increased delays"
            )
        
        # Add warnings
        if not result.has_braintree:
            result.warnings.append(
                f"Site uses {result.primary_gateway or 'unknown gateway'}, not Braintree"
            )
            config['enabled'] = False
        
        if not result.has_registration:
            result.warnings.append("No registration form detected")
        
        if result.has_captcha:
            result.warnings.append("CAPTCHA detected - may require manual intervention")
        
        result.recommended_config = config
    
    async def validate_multiple(self, domains: List[str]) -> List[ValidationResult]:
        """Validate multiple sites concurrently"""
        logger.info(f"Starting validation of {len(domains)} sites")
        
        connector = aiohttp.TCPConnector(limit=10, ttl_dns_cache=300)
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = [self.validate_site(domain, session) for domain in domains]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            valid_results = [r for r in results if isinstance(r, ValidationResult)]
            self.results.extend(valid_results)
            
        return valid_results
    
    def save_results(self, filename: str = "validation_report.json"):
        """Save validation results to JSON"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'total_validated': len(self.results),
            'compatible_sites': sum(1 for r in self.results if r.overall_score >= 50),
            'braintree_sites': sum(1 for r in self.results if r.has_braintree),
            'results': [r.to_dict() for r in self.results]
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✓ Saved validation results to {filename}")
    
    def get_compatible_sites(self, min_score: int = 50) -> List[ValidationResult]:
        """Get sites that meet minimum compatibility score"""
        return [r for r in self.results if r.overall_score >= min_score]
    
    def generate_config_json(self, min_score: int = 50, filename: str = "compatible_sites_config.json"):
        """Generate config.json for compatible sites"""
        compatible = self.get_compatible_sites(min_score)
        
        config = {
            'sites': {},
            'defaults': {
                'retry_strategy': 'normal',
                'max_retries': 3,
                'graphql_retries': 3,
                'timeout': 30,
                'requires_billing': True,
                'payment_gateway': 'braintree'
            }
        }
        
        for result in compatible:
            if result.has_braintree:
                config['sites'][result.domain] = result.recommended_config
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✓ Generated config for {len(config['sites'])} compatible sites")


async def main():
    """Main validation function"""
    print("=" * 80)
    print("GATEWAY VALIDATOR - SITE COMPATIBILITY CHECKER")
    print("=" * 80)
    
    # Load discovered sites
    try:
        with open('discovered_sites.json', 'r') as f:
            data = json.load(f)
            sites = [s['domain'] for s in data.get('sites', [])]
    except FileNotFoundError:
        print("\n[!] discovered_sites.json not found")
        print("[!] Run site_discovery.py first or provide domains manually")
        sites = []
    
    if not sites:
        # Example domains for testing
        sites = [
            'example-store.com',
            # Add test domains here
        ]
    
    print(f"\n[1] Validating {len(sites)} sites...")
    print("This may take several minutes...\n")
    
    validator = GatewayValidator(timeout=20)
    results = await validator.validate_multiple(sites)
    
    # Display results
    print("\n" + "=" * 80)
    print("VALIDATION RESULTS")
    print("=" * 80)
    
    compatible = validator.get_compatible_sites(min_score=50)
    print(f"\nTotal validated: {len(results)}")
    print(f"Compatible sites (score ≥ 50): {len(compatible)}")
    print(f"Braintree sites: {sum(1 for r in results if r.has_braintree)}")
    
    # Show top compatible sites
    if compatible:
        print(f"\n{'='*80}")
        print("TOP COMPATIBLE SITES")
        print("=" * 80)
        
        sorted_sites = sorted(compatible, key=lambda x: x.overall_score, reverse=True)
        for i, result in enumerate(sorted_sites[:20], 1):
            print(f"\n{i}. {result.domain} (Score: {result.overall_score}/100)")
            print(f"   Gateway: {result.primary_gateway}")
            print(f"   Nonces: Reg={result.register_nonce_found}, Login={result.login_nonce_found}, Payment={result.payment_method_nonce_found}")
            print(f"   Security: Cloudflare={result.has_cloudflare}, CAPTCHA={result.has_captcha}")
            if result.warnings:
                print(f"   Warnings: {', '.join(result.warnings[:2])}")
    
    # Save results
    print(f"\n{'='*80}")
    validator.save_results('validation_report.json')
    validator.generate_config_json(min_score=70, filename='high_quality_sites_config.json')
    print("✓ Complete!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[!] Validation interrupted by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
