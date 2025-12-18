# btc.py Performance Analysis

## Current Performance Issues

### **Test Results:**
- bigbrandwholesale.com: 250.68s (~4 minutes)
- kolarivision.com: Failed at checkout
- Average: 60-120s per site

### **Bottlenecks Identified:**

1. **Timeouts Too Long**
   - REQUEST_TIMEOUT = 45s (too high)
   - Playwright page.wait_for_timeout(2000) everywhere
   - wait_for_selector timeout=10000ms
   - Modal wait timeout=15000ms

2. **Sequential Operations**
   - Product fetching one by one
   - No parallel requests
   - Each retry waits full timeout

3. **Redundant Operations**
   - Multiple selector attempts with full timeouts
   - Unnecessary waits between steps
   - Repeated HTML parsing

4. **Playwright Specific**
   - wait_for_timeout(2000) after every action
   - Long iframe waits
   - Slow typing (delay=50ms per character)

## Optimization Plan

### **1. Reduce Timeouts**
```python
REQUEST_TIMEOUT = 30  # was 45
PLAYWRIGHT_TIMEOUT = 15000  # was 30000
SELECTOR_TIMEOUT = 3000  # was 5000-10000
MODAL_TIMEOUT = 10000  # was 15000
```

### **2. Remove Unnecessary Waits**
```python
# Remove: await self.page.wait_for_timeout(2000)
# Use: wait_for_load_state('networkidle') only when needed
```

### **3. Faster Typing**
```python
# Change: delay=50 → delay=10
await frame.type('#card-number', card_number, delay=10)
```

### **4. Parallel Product Fetching**
```python
# Instead of sequential:
for url in product_urls:
    product = await fetch_product(url)

# Use parallel:
products = await asyncio.gather(*[fetch_product(url) for url in product_urls[:10]])
```

### **5. Selector Optimization**
```python
# Try most common selectors first
# Use CSS selectors (faster than XPath)
# Reduce number of fallback attempts
```

### **6. Caching**
```python
# Cache client tokens
# Cache nonce patterns
# Reuse session cookies
```

## Expected Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Total Time | 250s | 60-90s | 60-65% faster |
| Product Selection | 30-60s | 10-15s | 70% faster |
| Checkout | 60-90s | 20-30s | 65% faster |
| Payment | 90-120s | 30-40s | 70% faster |

## Implementation Priority

1. **High Priority** (biggest impact):
   - Reduce timeouts
   - Remove wait_for_timeout calls
   - Faster typing speed

2. **Medium Priority**:
   - Parallel product fetching
   - Selector optimization
   - Better error handling

3. **Low Priority**:
   - Caching
   - Code refactoring
   - Additional optimizations
