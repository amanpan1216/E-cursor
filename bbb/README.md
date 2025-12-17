# Braintree Payment Processor (Enhanced)

An improved, robust Braintree payment processor with multi-site support, enhanced error handling, and comprehensive configuration management.

## Features

- ✅ **Enhanced Error Handling**: Comprehensive exception handling with retry logic
- ✅ **Multi-Site Support**: Site-specific configurations via JSON
- ✅ **Smart Retry Logic**: Exponential backoff with circuit breaker pattern
- ✅ **Improved Nonce Extraction**: Multiple fallback patterns for reliability
- ✅ **Structured Logging**: Detailed logs with performance metrics
- ✅ **Session Management**: Improved cookie handling and state management
- ✅ **Progress Tracking**: Real-time progress for batch operations
- ✅ **Site Compatibility**: Auto-detection of payment gateway types

## Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Sites** (Optional):
   Edit `config.json` to customize site-specific settings.

3. **Set Environment Variables** (Optional):
   ```bash
   export BRAINTREE_DEFAULT_PASSWORD="YourSecurePassword"
   ```

## Usage

### Basic Usage

Run the processor with default settings (tests all 12 configured sites):

```bash
python bbb_final.py
```

### Configuration

#### Site Configuration (`config.json`)

Each site can have custom settings:

```json
{
  "sites": {
    "example.com": {
      "enabled": true,
      "retry_strategy": "aggressive",
      "max_retries": 5,
      "requires_billing": true,
      "payment_gateway": "braintree",
      "delays": {
        "between_requests": 2.0,
        "after_registration": 3.0
      }
    }
  }
}
```

#### Retry Strategies

- **aggressive**: 5 retries, faster backoff (for reliable sites)
- **normal**: 3 retries, standard backoff (default)
- **conservative**: 2 retries, slower backoff (for rate-limited sites)

## Architecture

### Core Components

1. **Configuration Manager**: Loads and manages site-specific settings
2. **Session Manager**: Handles HTTP sessions with cookie persistence
3. **Nonce Extractor**: Multiple fallback patterns for token extraction
4. **Retry Manager**: Smart retry with exponential backoff
5. **Payment Processor**: Orchestrates the payment flow

### Processing Flow

```
1. Registration → 2. Login → 3. Billing → 4. Payment Method
```

Each step includes:
- Error handling with specific exceptions
- Retry logic for transient failures
- Skip on permanent failures (403, 401, 404)
- Progress tracking and logging

## Site Compatibility

### Supported Payment Gateways

- ✅ Braintree (primary)
- ⚠️ NMI Gateway (detected but skipped)

### Adding New Sites

1. Add site entry to `config.json`:
   ```json
   {
     "sites": {
       "newsite.com": {
         "enabled": true,
         "retry_strategy": "normal"
       }
     }
   }
   ```

2. Test the site:
   ```bash
   python bbb_final.py
   ```

3. Adjust settings based on results

## Error Handling

### Exception Types

- `AuthenticationError`: Login/registration failures, 401/403 errors
- `TokenError`: Nonce/token extraction failures
- `NetworkError`: Connection issues, timeouts
- `ValidationError`: Invalid card or configuration data

### Retry Behavior

- **Network errors**: Retry with exponential backoff
- **Rate limits (429)**: Special handling with longer delays
- **Permanent errors (401, 403, 404)**: No retry
- **Validation errors**: No retry

## Logging

Logs are written to:
- **Console**: Color-coded output with progress
- **File**: `braintree_processor.log` (detailed logs)

### Log Levels

- `DEBUG`: Detailed diagnostic information
- `INFO`: General progress and success messages
- `WARNING`: Non-critical issues (skipped steps)
- `ERROR`: Failures and exceptions

## Performance

### Optimizations

- Connection pooling (100 connections, 20 per host)
- Smart request delays to avoid rate limits
- Session reuse across requests
- Parallel-safe design

### Metrics

The processor tracks:
- Success/failure rates per site
- Processing time per step
- Error categories and frequencies

## Troubleshooting

### Common Issues

1. **"Registration nonce not found"**
   - Site may have disabled registration
   - Check if site structure has changed
   - Try accessing the site manually to verify

2. **"Site uses NMI Gateway"**
   - Site doesn't use Braintree
   - Mark site as `"enabled": false` in config

3. **"Session expired"**
   - Cookie handling issue
   - Check if site has special anti-bot measures
   - Increase delays in config

4. **"Access Forbidden (403)"**
   - Site is blocking requests
   - May need different User-Agent
   - Check if IP is blocked

### Debug Mode

For detailed diagnostics, check the log file:
```bash
tail -f braintree_processor.log
```

## Configuration Reference

### Site Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | true | Enable/disable site |
| `retry_strategy` | string | "normal" | Retry strategy name |
| `max_retries` | integer | 3 | Maximum retry attempts |
| `timeout` | integer | 30 | Request timeout (seconds) |
| `requires_billing` | boolean | true | Update billing address |
| `payment_gateway` | string | "braintree" | Expected gateway type |
| `delays.between_requests` | float | 2.0 | Delay between requests |
| `delays.after_registration` | float | 3.0 | Delay after registration |

### Default Settings

Global defaults are applied when site-specific settings are not provided:

```json
{
  "defaults": {
    "retry_strategy": "normal",
    "max_retries": 3,
    "timeout": 30,
    "requires_billing": true,
    "payment_gateway": "braintree"
  }
}
```

## Security Considerations

- Never commit passwords or sensitive data to config files
- Use environment variables for credentials
- Logs mask sensitive data (card numbers, emails)
- Follow responsible disclosure for any vulnerabilities found

## Testing

The processor includes comprehensive validation:
- Card number validation (Luhn algorithm)
- Expiry date checking
- CVV format validation
- Site compatibility pre-check

## Current Test Sites (12)

1. ads.premierguitar.com
2. dicksondata.com
3. djcity.com.au
4. kolarivision.com
5. lindywell.com
6. naturalacneclinic.com
7. perennialsfabrics.com
8. shop.bullfrogspas.com
9. store.puritywoods.com
10. strymon.net
11. truedark.com
12. winixamerica.com

## License

This tool is for educational and testing purposes only. Use responsibly and only on sites you have permission to test.

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review log files for detailed errors
3. Verify site configuration in config.json
4. Test individual components if needed
