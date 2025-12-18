# Advanced Site Discovery & Testing System

Complete automated system for discovering, validating, and testing WooCommerce sites with Braintree payment gateway.

## 🎯 Overview

This system provides:
- **Automated Site Discovery**: Finds 100-150+ WooCommerce sites with payment gateways
- **Gateway Validation**: Checks compatibility, extracts nonces, analyzes security
- **Batch Testing**: Automated testing with bbb_final.py integration
- **Comprehensive Reporting**: JSON, CSV, and text reports with detailed analytics

## 📁 Files

| File | Description |
|------|-------------|
| `site_discovery.py` | Discovers WooCommerce + Braintree sites |
| `gateway_validator.py` | Validates site compatibility and generates configs |
| `batch_checker.py` | Batch testing with bbb_final.py integration |
| `run_complete_pipeline.py` | Master orchestrator - runs all phases |
| `SITE_DISCOVERY_README.md` | This file |

## 🚀 Quick Start

### Option 1: Complete Pipeline (Recommended)

Run everything in one command:

```bash
python run_complete_pipeline.py
```

This will:
1. Discover 150 WooCommerce sites
2. Validate all discovered sites
3. Test high-quality sites (score ≥ 70)
4. Generate comprehensive reports

### Option 2: Step-by-Step

Run each phase separately:

```bash
# Phase 1: Discovery
python site_discovery.py

# Phase 2: Validation
python gateway_validator.py

# Phase 3: Testing
python batch_checker.py
```

## 📊 Output Files

### Discovery Phase
- `discovered_sites.json` - All discovered WooCommerce sites with metadata

### Validation Phase
- `validation_report.json` - Detailed validation results with scores
- `high_quality_sites_config.json` - Config.json for sites with score ≥ 70
- `compatible_sites_config.json` - Config.json for sites with score ≥ 50

### Testing Phase
- `batch_test_results.json` - Complete test results
- `batch_test_results.csv` - Test results in spreadsheet format
- `final_report.txt` - Human-readable summary

## 🔍 Discovery Methods

### 1. Seed Domain Generation
Generates domains based on common patterns:
- Industry-specific: `shopfashion.com`, `storeelectronics.com`
- Pattern-based: `myshop.com`, `quickshop.store`
- Real-world patterns

### 2. Technology Detection
Identifies:
- WooCommerce presence and version
- WordPress version
- Payment gateways (Braintree, NMI, Stripe, PayPal)
- Server software and security features

### 3. Path Checking
Validates WooCommerce paths:
- `/my-account/`
- `/checkout/`
- `/my-account/payment-methods/`
- `/my-account/add-payment-method/`

## ✅ Validation Features

### Compatibility Scoring

Each site receives scores (0-100):

**Nonce Extraction Score (40%):**
- Register nonce detection
- Login nonce detection
- Billing nonce detection
- Payment method nonce detection
- Client token nonce detection

**Gateway Compatibility Score (50%):**
- Braintree: 100 points
- NMI: 50 points (detected but not supported)
- Other: 25 points

**Security Score (10%):**
- Cloudflare detection
- CAPTCHA detection
- Rate limiting
- Security headers

### Site Classification

- **High Quality (≥70)**: Ready for immediate testing
- **Compatible (≥50)**: May work with adjustments
- **Low Score (<50)**: Not recommended

## 🧪 Testing Integration

### bbb_final.py Integration

Batch checker integrates with bbb_final.py:
- Uses circuit breaker pattern
- Respects site-specific configuration
- Tracks per-site results
- Generates detailed analytics

### Test Steps

Each site is tested through 4 steps:
1. Registration
2. Login verification
3. Billing address update
4. Payment method addition

### Results Categories

- **SUCCESS**: All 4 steps passed
- **PARTIAL**: Some steps passed
- **FAIL**: No steps passed
- **SKIP**: Circuit breaker open
- **ERROR**: Unexpected error

## 📈 Statistics & Analytics

### Discovery Statistics
- Total sites discovered
- Braintree percentage
- NMI percentage
- Average response time

### Validation Statistics
- Compatible site count
- High-quality site count
- Average scores
- Security distribution

### Testing Statistics
- Success rate
- Step-by-step success
- Error type distribution
- Average test duration

## ⚙️ Configuration

### Site Discovery Configuration

```python
# In run_complete_pipeline.py
SEED_COUNT = 150          # Domains to check
ENABLE_VALIDATION = True   # Run validation
ENABLE_TESTING = True      # Run testing
MIN_TEST_SCORE = 70        # Minimum score for testing
```

### Concurrency Settings

```python
# site_discovery.py
max_concurrent=20          # Concurrent discovery requests

# gateway_validator.py  
timeout=20                 # Validation timeout

# batch_checker.py
max_concurrent=3           # Concurrent tests (avoid overwhelming)
```

## 🔒 Responsible Usage

### Important Guidelines

1. **Rate Limiting**: Built-in delays prevent server overload
2. **Respect robots.txt**: Check site policies
3. **Testing Permission**: Only test sites you have permission for
4. **No Abuse**: Don't use for malicious purposes
5. **Privacy**: Don't share discovered site lists publicly

### Legal Considerations

- Site discovery uses public information
- Actual payment testing requires authorization
- Respect site terms of service
- Follow responsible disclosure for vulnerabilities

## 🛠️ Advanced Features

### Custom Seed Lists

Add your own domains to check:

```python
# In site_discovery.py
custom_domains = [
    'yourstore.com',
    'another-shop.com'
]
await discovery.discover_from_seed_list(custom_domains)
```

### Filtering Results

Filter by criteria:

```python
# Get only Braintree sites with registration
braintree_sites = [
    s for s in discovered_sites 
    if s.has_braintree and s.has_registration
]
```

### Custom Validation Rules

Modify scoring in `gateway_validator.py`:

```python
def calculate_scores(self):
    # Adjust weights here
    self.overall_score = int(
        (self.nonce_extraction_score * 0.4) +
        (self.gateway_compatibility_score * 0.5) +
        ((100 - self.security_score) * 0.1)
    )
```

## 📝 Example Workflow

### Discover and Test 100 Sites

```bash
# 1. Run complete pipeline
python run_complete_pipeline.py

# Wait for completion...

# 2. Check results
cat final_report.txt

# 3. View successful sites
python -c "
import json
with open('batch_test_results.json') as f:
    data = json.load(f)
    successful = [r for r in data['results'] if r['overall_status'] == 'SUCCESS']
    print(f'Successful sites: {len(successful)}')
    for site in successful:
        print(f\"  ✓ {site['domain']}\")
"

# 4. Use high-quality config
cp high_quality_sites_config.json config.json
python bbb_final.py
```

## 🐛 Troubleshooting

### No sites discovered

- Check internet connection
- Verify seed domain generation
- Increase `seed_count` parameter
- Check for timeout issues

### Validation fails

- Increase timeout settings
- Reduce `max_concurrent`
- Check for network issues

### Testing fails

- Ensure bbb_final.py is present
- Check test card format
- Verify site compatibility scores
- Review circuit breaker states

### Low success rate

- Filter for higher quality sites (score ≥ 80)
- Check site-specific errors
- Adjust retry strategies
- Review security features (Cloudflare, CAPTCHA)

## 📊 Performance Tips

### Optimize Discovery

```python
# Faster discovery (less accuracy)
discovery = SiteDiscovery(max_concurrent=30, timeout=10)

# Slower discovery (more accuracy)
discovery = SiteDiscovery(max_concurrent=10, timeout=30)
```

### Optimize Validation

```python
# Quick validation
validator = GatewayValidator(timeout=15)

# Thorough validation
validator = GatewayValidator(timeout=30)
```

### Optimize Testing

```python
# Faster testing (more load)
checker.test_sites(domains, max_concurrent=5)

# Slower testing (safer)
checker.test_sites(domains, max_concurrent=2)
```

## 🔄 Integration with Existing Code

### Use discovered sites with bbb_final.py

```python
# Load high-quality sites
with open('high_quality_sites_config.json') as f:
    config = json.load(f)

# Merge with existing config.json
with open('config.json') as f:
    existing = json.load(f)

existing['sites'].update(config['sites'])

# Save merged config
with open('config.json', 'w') as f:
    json.dump(existing, f, indent=2)
```

## 📞 Support

For issues or questions:
1. Check troubleshooting section
2. Review log files
3. Verify configuration settings
4. Check site compatibility scores

## 🎉 Success Metrics

Target outcomes:
- **Discovery**: 30-50% of seeds become WooCommerce sites
- **Validation**: 20-40% compatible (score ≥ 50)
- **Testing**: 40-60% success rate on high-quality sites

## 📜 License

Educational and testing purposes only. Use responsibly and ethically.
