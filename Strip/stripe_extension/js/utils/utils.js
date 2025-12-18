/**
 * Utility Functions Module
 * Common helper functions used across the extension
 */

const Utils = {
    /**
     * Generate random string
     */
    randomString(length, chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789') {
        let result = '';
        for (let i = 0; i < length; i++) {
            result += chars[Math.floor(Math.random() * chars.length)];
        }
        return result;
    },

    /**
     * Generate random hex string
     */
    randomHex(length) {
        return this.randomString(length, '0123456789abcdef');
    },

    /**
     * Generate UUID v4
     */
    uuid() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    },

    /**
     * Hash string (simple)
     */
    hashString(str) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return Math.abs(hash).toString(16).padStart(8, '0');
    },

    /**
     * Luhn algorithm for card validation
     */
    luhnCheck(number) {
        const cleaned = number.replace(/\D/g, '');
        if (cleaned.length < 13 || cleaned.length > 19) return false;

        let sum = 0;
        let isEven = false;

        for (let i = cleaned.length - 1; i >= 0; i--) {
            let digit = parseInt(cleaned[i], 10);
            if (isEven) {
                digit *= 2;
                if (digit > 9) digit -= 9;
            }
            sum += digit;
            isEven = !isEven;
        }

        return sum % 10 === 0;
    },

    /**
     * Get card brand from number
     */
    getCardBrand(number) {
        const cleaned = number.replace(/\D/g, '');
        
        const brands = [
            { name: 'visa', pattern: /^4/, lengths: [13, 16, 19] },
            { name: 'mastercard', pattern: /^5[1-5]|^2[2-7]/, lengths: [16] },
            { name: 'amex', pattern: /^3[47]/, lengths: [15] },
            { name: 'discover', pattern: /^6(?:011|5)/, lengths: [16, 19] },
            { name: 'diners', pattern: /^3(?:0[0-5]|[68])/, lengths: [14, 16, 19] },
            { name: 'jcb', pattern: /^(?:2131|1800|35)/, lengths: [16, 17, 18, 19] },
            { name: 'unionpay', pattern: /^62/, lengths: [16, 17, 18, 19] }
        ];

        for (const brand of brands) {
            if (brand.pattern.test(cleaned)) {
                return brand.name;
            }
        }

        return 'unknown';
    },

    /**
     * Format card number with spaces
     */
    formatCardNumber(number) {
        const cleaned = number.replace(/\D/g, '');
        const brand = this.getCardBrand(cleaned);
        
        if (brand === 'amex') {
            return cleaned.replace(/(\d{4})(\d{6})(\d{5})/, '$1 $2 $3');
        }
        
        return cleaned.replace(/(\d{4})/g, '$1 ').trim();
    },

    /**
     * Parse card string (various formats)
     */
    parseCard(cardString) {
        const cleaned = cardString.replace(/[\s\-]/g, '');
        const parts = cleaned.split('|');
        
        if (parts.length >= 4) {
            let expMonth = parts[1];
            let expYear = parts[2];
            
            if (expYear.length === 2) {
                expYear = '20' + expYear;
            }

            return {
                number: parts[0],
                expMonth: expMonth.padStart(2, '0'),
                expYear: expYear,
                cvv: parts[3],
                brand: this.getCardBrand(parts[0]),
                valid: this.luhnCheck(parts[0])
            };
        }

        return null;
    },

    /**
     * Generate random name
     */
    randomName() {
        const firstNames = ['John', 'Jane', 'Michael', 'Sarah', 'David', 'Emily', 'James', 'Emma', 'Robert', 'Olivia', 'William', 'Sophia', 'Richard', 'Isabella', 'Joseph', 'Mia', 'Thomas', 'Charlotte', 'Charles', 'Amelia'];
        const lastNames = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin'];
        
        return `${firstNames[Math.floor(Math.random() * firstNames.length)]} ${lastNames[Math.floor(Math.random() * lastNames.length)]}`;
    },

    /**
     * Generate random email
     */
    randomEmail() {
        const domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com', 'protonmail.com'];
        const name = this.randomString(8, 'abcdefghijklmnopqrstuvwxyz');
        const num = Math.floor(Math.random() * 999);
        return `${name}${num}@${domains[Math.floor(Math.random() * domains.length)]}`;
    },

    /**
     * Generate random US address
     */
    randomUSAddress() {
        const streets = ['Main St', 'Oak Ave', 'Park Blvd', 'Maple Dr', 'Cedar Ln', 'Pine St', 'Elm Ave', 'Washington Blvd', 'Broadway', 'Market St'];
        const cities = [
            { city: 'New York', state: 'NY', zip: '10001' },
            { city: 'Los Angeles', state: 'CA', zip: '90001' },
            { city: 'Chicago', state: 'IL', zip: '60601' },
            { city: 'Houston', state: 'TX', zip: '77001' },
            { city: 'Phoenix', state: 'AZ', zip: '85001' },
            { city: 'Philadelphia', state: 'PA', zip: '19101' },
            { city: 'San Antonio', state: 'TX', zip: '78201' },
            { city: 'San Diego', state: 'CA', zip: '92101' },
            { city: 'Dallas', state: 'TX', zip: '75201' },
            { city: 'San Jose', state: 'CA', zip: '95101' }
        ];

        const num = Math.floor(Math.random() * 9999) + 1;
        const street = streets[Math.floor(Math.random() * streets.length)];
        const location = cities[Math.floor(Math.random() * cities.length)];

        return {
            line1: `${num} ${street}`,
            line2: '',
            city: location.city,
            state: location.state,
            postalCode: location.zip,
            country: 'US'
        };
    },

    /**
     * Generate random phone number
     */
    randomPhone(country = 'US') {
        if (country === 'US') {
            const areaCode = Math.floor(Math.random() * 800) + 200;
            const prefix = Math.floor(Math.random() * 900) + 100;
            const line = Math.floor(Math.random() * 9000) + 1000;
            return `+1${areaCode}${prefix}${line}`;
        }
        return `+1${Math.floor(Math.random() * 9000000000) + 1000000000}`;
    },

    /**
     * Sleep/delay function
     */
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    },

    /**
     * Random delay between min and max
     */
    randomDelay(min, max) {
        const delay = Math.floor(Math.random() * (max - min + 1)) + min;
        return this.sleep(delay);
    },

    /**
     * Retry function with exponential backoff
     */
    async retry(fn, maxRetries = 3, baseDelay = 1000) {
        let lastError;
        
        for (let i = 0; i < maxRetries; i++) {
            try {
                return await fn();
            } catch (err) {
                lastError = err;
                if (i < maxRetries - 1) {
                    const delay = baseDelay * Math.pow(2, i);
                    await this.sleep(delay);
                }
            }
        }
        
        throw lastError;
    },

    /**
     * Format currency
     */
    formatCurrency(amount, currency = 'USD') {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency
        }).format(amount / 100);
    },

    /**
     * Parse URL parameters
     */
    parseUrlParams(url) {
        const params = {};
        const urlObj = new URL(url);
        
        for (const [key, value] of urlObj.searchParams) {
            params[key] = value;
        }
        
        // Also parse hash fragment
        if (urlObj.hash) {
            const hashParams = new URLSearchParams(urlObj.hash.slice(1));
            for (const [key, value] of hashParams) {
                params[key] = value;
            }
        }
        
        return params;
    },

    /**
     * Extract Stripe session ID from URL
     */
    extractStripeSessionId(url) {
        const match = url.match(/cs_[a-zA-Z0-9_]+/);
        return match ? match[0] : null;
    },

    /**
     * Extract Stripe public key from HTML
     */
    extractStripePublicKey(html) {
        const match = html.match(/pk_live_[a-zA-Z0-9]+/);
        return match ? match[0] : null;
    },

    /**
     * Deep clone object
     */
    deepClone(obj) {
        return JSON.parse(JSON.stringify(obj));
    },

    /**
     * Deep merge objects
     */
    deepMerge(target, source) {
        const result = { ...target };
        
        for (const key in source) {
            if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
                result[key] = this.deepMerge(result[key] || {}, source[key]);
            } else {
                result[key] = source[key];
            }
        }
        
        return result;
    },

    /**
     * Debounce function
     */
    debounce(fn, delay) {
        let timeoutId;
        return function(...args) {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => fn.apply(this, args), delay);
        };
    },

    /**
     * Throttle function
     */
    throttle(fn, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                fn.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },

    /**
     * Format date
     */
    formatDate(date, format = 'YYYY-MM-DD HH:mm:ss') {
        const d = new Date(date);
        
        const replacements = {
            'YYYY': d.getFullYear(),
            'MM': String(d.getMonth() + 1).padStart(2, '0'),
            'DD': String(d.getDate()).padStart(2, '0'),
            'HH': String(d.getHours()).padStart(2, '0'),
            'mm': String(d.getMinutes()).padStart(2, '0'),
            'ss': String(d.getSeconds()).padStart(2, '0')
        };
        
        let result = format;
        for (const [key, value] of Object.entries(replacements)) {
            result = result.replace(key, value);
        }
        
        return result;
    },

    /**
     * Log with timestamp
     */
    log(prefix, ...args) {
        const timestamp = this.formatDate(new Date(), 'HH:mm:ss');
        console.log(`[${timestamp}] [${prefix}]`, ...args);
    },

    /**
     * Safe JSON parse
     */
    safeJsonParse(str, defaultValue = null) {
        try {
            return JSON.parse(str);
        } catch (e) {
            return defaultValue;
        }
    },

    /**
     * Check if object is empty
     */
    isEmpty(obj) {
        if (!obj) return true;
        if (Array.isArray(obj)) return obj.length === 0;
        if (typeof obj === 'object') return Object.keys(obj).length === 0;
        return false;
    },

    /**
     * Generate BIN from card number
     */
    getBIN(cardNumber) {
        return cardNumber.replace(/\D/g, '').substring(0, 6);
    },

    /**
     * Mask card number
     */
    maskCardNumber(cardNumber) {
        const cleaned = cardNumber.replace(/\D/g, '');
        const first = cleaned.substring(0, 4);
        const last = cleaned.substring(cleaned.length - 4);
        const masked = '*'.repeat(cleaned.length - 8);
        return `${first}${masked}${last}`;
    }
};

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.Utils = Utils;
}
