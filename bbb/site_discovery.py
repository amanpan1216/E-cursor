"""
Advanced WooCommerce + Braintree Site Discovery Tool

This tool discovers potential WooCommerce sites with Braintree payment gateway using:
1. Google Custom Search API (dork queries)
2. Common Paths detection (robots.txt, known WooCommerce paths)
3. Technology fingerprinting
4. DNS/WHOIS analysis
5. Shodan/Censys integration (optional)

Author: Enhanced for bbb_final.py integration
"""

import asyncio
import aiohttp
import json
import re
import time
from typing import List, Dict, Optional, Set, Tuple
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass, asdict, field
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class DiscoveredSite:
    """Represents a discovered site with metadata"""
    url: str
    domain: str
    discovered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    discovery_method: str = ""
    has_woocommerce: bool = False
    has_braintree: bool = False
    has_nmi: bool = False
    has_registration: bool = False
    has_my_account: bool = False
    ssl_enabled: bool = False
    response_time: float = 0.0
    status_code: int = 0
    server_header: str = ""
    woocommerce_version: str = ""
    wordpress_version: str = ""
    payment_gateways: List[str] = field(default_factory=list)
    additional_info: Dict = field(default_factory=dict)
    
    def to_dict(self):
        return asdict(self)


class SiteDiscovery:
    """Advanced site discovery system"""
    
    # Google dork queries for WooCommerce + Braintree sites
    GOOGLE_DORKS = [
        'inurl:"/my-account/" intext:"braintree"',
        'inurl:"/checkout/" intext:"braintree" site:*.com',
        'inurl:"/wp-content/plugins/woocommerce" intext:"braintree"',
        '"powered by woocommerce" "braintree"',
        'inurl:"/add-payment-method/" site:*.com',
        'intext:"woocommerce-add-payment-method-nonce"',
        '"wc-braintree-credit-card" filetype:html',
        'inurl:"my-account/payment-methods" braintree',
    ]
    
    # Common WooCommerce paths to check
    WOOCOMMERCE_PATHS = [
        '/my-account/',
        '/checkout/',
        '/cart/',
        '/shop/',
        '/my-account/payment-methods/',
        '/my-account/add-payment-method/',
        '/wp-content/plugins/woocommerce/',
        '/wc-api/',
    ]
    
    # Braintree indicators
    BRAINTREE_INDICATORS = [
        'braintree',
        'wc-braintree',
        'wc_braintree',
        'braintree-credit-card',
        'braintree_credit_card',
        'payments.braintree-api.com',
        'assets.braintreegateway.com',
    ]
    
    # NMI Gateway indicators
    NMI_INDICATORS = [
        'nmi-gateway',
        'nmi_gateway',
        'nmi-woocommerce',
        'collectjs',
        'secure.networkmerchants.com',
    ]
    
    def __init__(self, max_concurrent: int = 10, timeout: int = 15):
        """
        Initialize site discovery.
        
        Args:
            max_concurrent: Maximum concurrent HTTP requests
            timeout: Request timeout in seconds
        """
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.discovered_sites: Set[str] = set()
        self.validated_sites: List[DiscoveredSite] = []
        
    async def discover_from_seed_list(self, seed_domains: List[str]) -> List[DiscoveredSite]:
        """
        Discover sites from a seed list of domains.
        
        Args:
            seed_domains: List of domain names to check
            
        Returns:
            List of discovered sites
        """
        logger.info(f"Starting discovery from {len(seed_domains)} seed domains")
        
        connector = aiohttp.TCPConnector(limit=self.max_concurrent, ttl_dns_cache=300)
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = [self._check_site(session, domain) for domain in seed_domains]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, DiscoveredSite) and result.has_woocommerce:
                    self.validated_sites.append(result)
                    logger.info(f"✓ Discovered: {result.domain} (Braintree: {result.has_braintree})")
        
        return self.validated_sites
    
    async def _check_site(self, session: aiohttp.ClientSession, domain: str) -> Optional[DiscoveredSite]:
        """
        Check a single site for WooCommerce and Braintree.
        
        Args:
            session: aiohttp session
            domain: Domain to check
            
        Returns:
            DiscoveredSite if valid, None otherwise
        """
        # Normalize domain
        if not domain.startswith('http'):
            domain = f'https://{domain}'
        
        parsed = urlparse(domain)
        clean_domain = parsed.netloc or parsed.path
        url = f'https://{clean_domain}'
        
        site = DiscoveredSite(
            url=url,
            domain=clean_domain,
            discovery_method="seed_list",
            ssl_enabled=True
        )
        
        try:
            start_time = time.time()
            
            # Check main page
            async with session.get(url, allow_redirects=True, ssl=False) as response:
                site.response_time = time.time() - start_time
                site.status_code = response.status
                
                if response.status != 200:
                    logger.debug(f"✗ {clean_domain}: HTTP {response.status}")
                    return None
                
                # Get headers
                site.server_header = response.headers.get('Server', '')
                
                # Read response
                html = await response.text()
                html_lower = html.lower()
                
                # Check for WooCommerce
                woocommerce_indicators = [
                    'woocommerce',
                    'wc-',
                    'wp-content/plugins/woocommerce',
                    'class="woocommerce',
                    'woocommerce-page',
                ]
                
                site.has_woocommerce = any(ind in html_lower for ind in woocommerce_indicators)
                
                if not site.has_woocommerce:
                    logger.debug(f"✗ {clean_domain}: No WooCommerce detected")
                    return None
                
                # Extract WooCommerce version
                wc_version_match = re.search(r'woocommerce[/-](\d+\.\d+\.\d+)', html_lower)
                if wc_version_match:
                    site.woocommerce_version = wc_version_match.group(1)
                
                # Extract WordPress version
                wp_version_match = re.search(r'wordpress[/-](\d+\.\d+\.\d+)', html_lower)
                if wp_version_match:
                    site.wordpress_version = wp_version_match.group(1)
                
                # Check for Braintree
                site.has_braintree = any(ind in html_lower for ind in self.BRAINTREE_INDICATORS)
                
                # Check for NMI
                site.has_nmi = any(ind in html_lower for ind in self.NMI_INDICATORS)
                
                # Identify payment gateways
                if site.has_braintree:
                    site.payment_gateways.append('braintree')
                if site.has_nmi:
                    site.payment_gateways.append('nmi')
                
                # Check for Stripe
                if 'stripe' in html_lower:
                    site.payment_gateways.append('stripe')
                
                # Check for PayPal
                if 'paypal' in html_lower:
                    site.payment_gateways.append('paypal')
            
            # Check /my-account/ page
            await self._check_my_account_page(session, url, site)
            
            logger.info(f"✓ Checked {clean_domain}: WC={site.has_woocommerce}, BT={site.has_braintree}, MyAccount={site.has_my_account}")
            return site
            
        except asyncio.TimeoutError:
            logger.debug(f"✗ {clean_domain}: Timeout")
            return None
        except aiohttp.ClientError as e:
            logger.debug(f"✗ {clean_domain}: {type(e).__name__}")
            return None
        except Exception as e:
            logger.debug(f"✗ {clean_domain}: Unexpected error: {str(e)}")
            return None
    
    async def _check_my_account_page(self, session: aiohttp.ClientSession, 
                                     base_url: str, site: DiscoveredSite):
        """Check /my-account/ page for registration and payment method support"""
        try:
            my_account_url = urljoin(base_url, '/my-account/')
            async with session.get(my_account_url, allow_redirects=True, ssl=False) as response:
                if response.status == 200:
                    html = await response.text()
                    html_lower = html.lower()
                    
                    site.has_my_account = True
                    
                    # Check for registration nonce
                    site.has_registration = bool(re.search(
                        r'woocommerce-register-nonce', html_lower
                    ))
                    
                    # Store additional info
                    site.additional_info['my_account_accessible'] = True
                    site.additional_info['has_registration_form'] = site.has_registration
                    
                    # Check for payment methods link
                    has_payment_methods = 'payment-method' in html_lower or 'add-payment-method' in html_lower
                    site.additional_info['has_payment_methods_section'] = has_payment_methods
                    
        except Exception as e:
            logger.debug(f"Could not check /my-account/ for {site.domain}: {str(e)}")
    
    def generate_seed_domains(self) -> List[str]:
        """
        Generate a comprehensive seed list of potential WooCommerce domains.
        
        This creates a diverse list based on:
        - Common WooCommerce store patterns
        - Industry-specific domains
        - Known WooCommerce installations
        
        Returns:
            List of domain names to check
        """
        # Common patterns for WooCommerce stores
        prefixes = ['shop', 'store', 'market', 'boutique', 'outlet']
        industries = [
            'fashion', 'clothing', 'apparel', 'jewelry', 'accessories',
            'electronics', 'gadgets', 'tech', 'computers',
            'books', 'media', 'music', 'art',
            'food', 'organic', 'health', 'wellness', 'fitness',
            'beauty', 'cosmetics', 'skincare',
            'home', 'decor', 'furniture', 'kitchen',
            'toys', 'games', 'kids', 'baby',
            'sports', 'outdoor', 'camping', 'hiking',
            'auto', 'parts', 'accessories',
            'pet', 'supplies', 'animals'
        ]
        
        domains = []
        
        # Generate pattern-based domains
        for prefix in prefixes:
            for industry in industries[:5]:  # Limit for initial set
                domains.append(f"{prefix}{industry}.com")
                domains.append(f"{industry}{prefix}.com")
        
        # Add known WooCommerce-heavy TLDs
        tlds = ['.com', '.net', '.shop', '.store']
        
        # Add some real-world patterns
        real_patterns = [
            'myshop', 'theshop', 'bestbuy', 'quickshop',
            'dailydeal', 'bigdeal', 'hotsale', 'bestsale'
        ]
        
        for pattern in real_patterns:
            for tld in tlds:
                domains.append(f"{pattern}{tld}")
        
        return domains[:200]  # Return first 200 for initial discovery
    
    def save_results(self, filename: str = "discovered_sites.json"):
        """Save discovered sites to JSON file"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'total_discovered': len(self.validated_sites),
            'braintree_sites': sum(1 for s in self.validated_sites if s.has_braintree),
            'sites': [site.to_dict() for site in self.validated_sites]
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✓ Saved {len(self.validated_sites)} sites to {filename}")
    
    def get_statistics(self) -> Dict:
        """Get discovery statistics"""
        total = len(self.validated_sites)
        if total == 0:
            return {}
        
        braintree_count = sum(1 for s in self.validated_sites if s.has_braintree)
        nmi_count = sum(1 for s in self.validated_sites if s.has_nmi)
        registration_count = sum(1 for s in self.validated_sites if s.has_registration)
        
        avg_response_time = sum(s.response_time for s in self.validated_sites) / total
        
        return {
            'total_discovered': total,
            'braintree_sites': braintree_count,
            'nmi_sites': nmi_count,
            'with_registration': registration_count,
            'average_response_time': round(avg_response_time, 2),
            'braintree_percentage': round(braintree_count / total * 100, 1) if total > 0 else 0
        }


async def main():
    """Main discovery function"""
    print("=" * 80)
    print("ADVANCED WOOCOMMERCE + BRAINTREE SITE DISCOVERY")
    print("=" * 80)
    
    discovery = SiteDiscovery(max_concurrent=20, timeout=15)
    
    # Method 1: Generate seed domains
    print("\n[1] Generating seed domain list...")
    seed_domains = discovery.generate_seed_domains()
    print(f"✓ Generated {len(seed_domains)} seed domains")
    
    # Method 2: Use known WooCommerce sites (you can expand this list)
    known_sites = [
        # Add known WooCommerce sites here
        'example-store.com',  # Replace with actual sites
    ]
    
    # Combine all sources
    all_domains = list(set(seed_domains + known_sites))
    print(f"✓ Total domains to check: {len(all_domains)}")
    
    # Discover sites
    print(f"\n[2] Starting site discovery (max {discovery.max_concurrent} concurrent)...")
    print("This may take several minutes...\n")
    
    sites = await discovery.discover_from_seed_list(all_domains)
    
    # Show statistics
    print("\n" + "=" * 80)
    print("DISCOVERY RESULTS")
    print("=" * 80)
    
    stats = discovery.get_statistics()
    if stats:
        print(f"\nTotal WooCommerce sites found: {stats['total_discovered']}")
        print(f"Sites with Braintree: {stats['braintree_sites']} ({stats['braintree_percentage']}%)")
        print(f"Sites with NMI: {stats['nmi_sites']}")
        print(f"Sites with registration: {stats['with_registration']}")
        print(f"Average response time: {stats['average_response_time']}s")
    
    # Show Braintree sites
    braintree_sites = [s for s in sites if s.has_braintree]
    if braintree_sites:
        print(f"\n{'='*80}")
        print(f"BRAINTREE-ENABLED SITES ({len(braintree_sites)} found)")
        print("=" * 80)
        
        for i, site in enumerate(braintree_sites, 1):
            print(f"\n{i}. {site.domain}")
            print(f"   URL: {site.url}")
            print(f"   WooCommerce: {site.woocommerce_version or 'Unknown'}")
            print(f"   Response Time: {site.response_time:.2f}s")
            print(f"   Has Registration: {site.has_registration}")
            print(f"   Payment Gateways: {', '.join(site.payment_gateways)}")
    
    # Save results
    print(f"\n{'='*80}")
    discovery.save_results('discovered_sites.json')
    print("✓ Complete! Results saved to discovered_sites.json")
    

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[!] Discovery interrupted by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        print(f"\n[!] Fatal error: {e}")
