# Hyper-Realistic Multi-Platform Checkout Automation Suite

A comprehensive Python-based checkout automation framework with advanced browser fingerprinting, anti-bot evasion, and human-like behavior simulation.

## Features

### Core Capabilities

- **Browser Fingerprinting**: Realistic browser profile generation including WebGL, Canvas, and AudioContext fingerprints
- **Human-Like Behavior**: Natural typing patterns, mouse movements, scrolling, and form interactions with Gaussian-distributed delays
- **TLS/HTTP2 Fingerprinting**: Proper cipher suite ordering and HTTP/2 settings to match real browsers
- **Session Management**: Persistent sessions with cookie handling and state management

### Supported Platforms

| Platform | Detection | Cart | Checkout | Order Submission |
|----------|-----------|------|----------|------------------|
| WooCommerce | ✅ | ✅ | ✅ | ✅ |
| BigCommerce | ✅ | ✅ | ✅ | ✅ |
| Shopify | ✅ | ✅ | ✅ | ✅ |

### Supported Payment Gateways

| Gateway | Detection | Tokenization | Payment Intents | 3DS |
|---------|-----------|--------------|-----------------|-----|
| Stripe | ✅ | ✅ | ✅ | ✅ |
| Braintree | ✅ | ✅ | ✅ | ✅ |

### Captcha Solving Integration

| Service | reCAPTCHA v2 | reCAPTCHA v3 | hCaptcha | Turnstile |
|---------|--------------|--------------|----------|-----------|
| 2Captcha | ✅ | ✅ | ✅ | ✅ |
| Anti-Captcha | ✅ | ✅ | ✅ | ✅ |
| CapMonster | ✅ | ✅ | ✅ | ✅ |

### 3D Secure Support

- 3DS 1.0 (PAReq/PARes flow)
- 3DS 2.0 (CReq/CRes flow)
- Stripe 3DS integration
- Braintree 3DS integration

## Project Structure

```
automation_suite/
├── __init__.py
├── main.py
├── README.md
├── requirements.txt
├── core/
│   ├── __init__.py
│   ├── browser.py          # Browser fingerprinting & session management
│   ├── behavior.py         # Human-like behavior simulation
│   └── http_client.py      # Advanced HTTP client with TLS fingerprinting
├── platforms/
│   ├── __init__.py
│   ├── woocommerce.py      # WooCommerce platform handler
│   ├── bigcommerce.py      # BigCommerce platform handler
│   └── shopify.py          # Shopify platform handler
├── gateways/
│   ├── __init__.py
│   ├── stripe.py           # Stripe payment gateway handler
│   └── braintree.py        # Braintree payment gateway handler
├── solvers/
│   ├── __init__.py
│   ├── captcha.py          # Captcha detection & solving
│   └── three_ds.py         # 3D Secure handling
└── utils/
    ├── __init__.py
    └── utils.py            # Utility functions & helpers
```

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Install Dependencies

```bash
pip install -r requirements.txt
```

## Usage

### Command Line Interface

```bash
python main.py --url "https://example.com/shop" --cards cards.txt
```

### Full Options

```bash
python main.py \
    --url "https://example.com/shop" \
    --cards cards.txt \
    --proxies proxies.txt \
    --captcha-key "YOUR_API_KEY" \
    --captcha-service "2captcha" \
    --country "US" \
    --retries 3 \
    --delay 2.0 \
    --log-dir logs
```

### Arguments

| Argument | Short | Required | Default | Description |
|----------|-------|----------|---------|-------------|
| `--url` | `-u` | Yes | - | Target checkout URL |
| `--cards` | `-c` | Yes | - | Path to card file |
| `--proxies` | `-p` | No | None | Path to proxy file |
| `--captcha-key` | - | No | None | Captcha solving API key |
| `--captcha-service` | - | No | 2captcha | Captcha service (2captcha/anticaptcha/capmonster) |
| `--no-3ds` | - | No | False | Disable 3DS handling |
| `--no-billing` | - | No | False | Don't generate random billing info |
| `--country` | - | No | US | Billing country code |
| `--retries` | - | No | 3 | Max retries per card |
| `--delay` | - | No | 2.0 | Delay between cards (seconds) |
| `--log-dir` | - | No | logs | Log directory |
| `--quiet` | `-q` | No | False | Quiet mode |

### Card File Format

Cards should be in one of the following formats:

```
4111111111111111|12|2025|123
4111111111111111:12:2025:123
4111111111111111 12 2025 123
4111111111111111/12/2025/123
4111111111111111,12,2025,123
```

### Proxy File Format

```
http://user:pass@host:port
socks5://user:pass@host:port
host:port:user:pass
```

## Programmatic Usage

### Basic Example

```python
from automation_suite import (
    CheckoutConfig,
    CheckoutAutomation
)

config = CheckoutConfig(
    target_url="https://example.com/shop",
    card_file="cards.txt",
    generate_billing=True,
    billing_country="US"
)

automation = CheckoutAutomation(config)
results = automation.run()

for result in results:
    if result.success:
        print(f"Success! Order ID: {result.order_id}")
    else:
        print(f"Failed: {result.error}")
```

### Using Individual Components

```python
from automation_suite import (
    SessionManager,
    AdvancedHTTPClient,
    WooCommerceHandler,
    StripeGatewayHandler,
    StripeCard,
    AddressGenerator
)

session_manager = SessionManager()
http_client = AdvancedHTTPClient(session_manager)
http_client.create_session()

woo_handler = WooCommerceHandler(http_client)
woo_handler.initialize("https://example.com")

products = woo_handler.browse_products()
product = products[0]

woo_handler.add_to_cart(product)
cart = woo_handler.get_cart()
checkout = woo_handler.proceed_to_checkout()

stripe_handler = StripeGatewayHandler(http_client, "pk_live_xxx")
stripe_handler.initialize()

card = StripeCard(
    number="4111111111111111",
    exp_month="12",
    exp_year="25",
    cvc="123"
)

payment_method = stripe_handler.create_payment_method(card)

address_gen = AddressGenerator()
billing = address_gen.generate_billing("US")
billing_dict = address_gen.billing_to_dict(billing)

result = woo_handler.submit_order(
    billing_dict,
    payment_method="stripe",
    payment_data={"stripe_source": payment_method.id}
)
```

### Browser Fingerprinting

```python
from automation_suite import (
    BrowserFingerprintGenerator,
    SessionManager
)

fp_generator = BrowserFingerprintGenerator()
fingerprint = fp_generator.generate_fingerprint()

print(f"User Agent: {fingerprint.user_agent}")
print(f"Screen: {fingerprint.screen_width}x{fingerprint.screen_height}")
print(f"Timezone: {fingerprint.timezone}")
print(f"Languages: {fingerprint.languages}")

session_manager = SessionManager()
session = session_manager.create_session()
headers = session_manager.get_session_headers(session["id"], "example.com")
```

### Human-Like Behavior

```python
from automation_suite import (
    HumanBehaviorSimulator,
    TypingSimulator,
    MouseMovementSimulator
)

behavior = HumanBehaviorSimulator()

behavior.human_delay(action_type="page_load")
behavior.human_delay(action_type="reading")
behavior.human_delay(action_type="button_click")

typing = TypingSimulator()
intervals = typing.type_text("Hello World")

mouse = MouseMovementSimulator()
path = mouse.generate_path((100, 100), (500, 300))
```

### Captcha Solving

```python
from automation_suite import (
    CaptchaSolverManager,
    TwoCaptchaSolver,
    CaptchaDetector
)

solver_manager = CaptchaSolverManager(http_client)
solver_manager.add_solver("2captcha", TwoCaptchaSolver("YOUR_API_KEY"))

detector = CaptchaDetector()
challenges = detector.detect(html_content, page_url)

for challenge in challenges:
    solution = solver_manager.solve_captcha(challenge)
    if solution:
        print(f"Solved {challenge.type}: {solution.token[:50]}...")
```

### 3D Secure Handling

```python
from automation_suite import (
    ThreeDSManager,
    ThreeDSDetector
)

three_ds_manager = ThreeDSManager(http_client)

challenge = three_ds_manager.detect_challenge(payment_response)

if challenge:
    result = three_ds_manager.handle_challenge(challenge)
    
    if result.success:
        print("3DS authentication successful")
    elif result.error:
        print(f"3DS failed: {result.error}")
```

## Output Files

### Success Log (logs/success.txt)

```
[2024-01-15T10:30:45.123Z] 4111111111111111|12|2025|123 | https://example.com | Order ID: 12345
```

### Failure Log (logs/failure.txt)

```
[2024-01-15T10:31:22.456Z] 4222222222222222|01|2024|456 | https://example.com | Card declined
```

### Error Log (logs/errors.txt)

```
[2024-01-15T10:32:00.789Z] 4333333333333333|06|2025|789 | https://example.com | ERROR: Connection timeout
```

## Anti-Detection Features

### Browser Fingerprinting

- Realistic User-Agent strings for Chrome, Firefox, Safari, Edge
- Proper screen resolution and color depth
- WebGL vendor and renderer strings
- Canvas fingerprint generation
- AudioContext fingerprint
- Timezone and language settings
- Hardware concurrency and device memory
- Touch support detection

### HTTP Fingerprinting

- TLS cipher suite ordering matching real browsers
- HTTP/2 settings (SETTINGS frame values)
- Header ordering (pseudo-headers and regular headers)
- Accept-Language and Accept-Encoding patterns

### Behavioral Patterns

- Gaussian-distributed delays between actions
- Natural typing speed with variable intervals
- Bezier curve mouse movements
- Realistic scroll patterns
- Form field focus/blur simulation

## Error Handling

The framework includes comprehensive error handling:

- Automatic retry on transient failures
- Graceful degradation when optional features fail
- Detailed error logging for debugging
- Session recovery after connection issues

## Security Considerations

- All sensitive data (cards, credentials) should be stored securely
- Use proxies to avoid IP-based blocking
- Rotate user agents and fingerprints
- Implement rate limiting to avoid detection
- Never store API keys in code

## Limitations

- Some sites may have additional anti-bot measures not covered
- Manual intervention may be required for complex captchas
- 3DS challenges requiring OTP/password need manual completion
- Rate limiting may affect high-volume operations

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Submit a pull request

## License

This project is for educational purposes only. Use responsibly and in compliance with applicable laws and terms of service.

## Disclaimer

This software is provided for educational and research purposes only. The authors are not responsible for any misuse or damage caused by this software. Always obtain proper authorization before testing on any website.
