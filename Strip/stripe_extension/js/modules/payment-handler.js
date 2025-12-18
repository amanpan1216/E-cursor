/**
 * Payment Handler Module
 * Handles Stripe payment processing, card validation, and checkout flow
 */

class PaymentHandler {
    constructor(options = {}) {
        this.publicKey = null;
        this.sessionId = null;
        this.checkoutUrl = null;
        this.verbose = options.verbose !== false;
        this.fingerprint = null;
        this.antiBot = null;
        this.session = null;
    }

    /**
     * Initialize payment handler with checkout URL
     */
    async initialize(checkoutUrl) {
        this.checkoutUrl = checkoutUrl;
        this.log('Initializing payment handler...');

        try {
            // Extract session ID from URL
            this.sessionId = this.extractSessionId(checkoutUrl);
            
            // Get checkout page data
            const pageData = await this.getCheckoutPageData(checkoutUrl);
            
            if (pageData) {
                this.publicKey = pageData.publicKey;
                this.log('Public key:', this.publicKey);
            }

            return {
                success: true,
                sessionId: this.sessionId,
                publicKey: this.publicKey
            };
        } catch (err) {
            return { success: false, error: err.message };
        }
    }

    /**
     * Extract session ID from checkout URL
     */
    extractSessionId(url) {
        const match = url.match(/cs_[a-zA-Z0-9_]+/);
        return match ? match[0] : null;
    }

    /**
     * Get checkout page data
     */
    async getCheckoutPageData(url) {
        try {
            const response = await fetch(url, {
                headers: this.getHeaders()
            });

            const html = await response.text();

            // Extract public key
            const pkMatch = html.match(/pk_live_[a-zA-Z0-9]+/);
            const publicKey = pkMatch ? pkMatch[0] : null;

            // Extract other data
            const configMatch = html.match(/__CHECKOUT_CONFIG__\s*=\s*({[\s\S]*?});/);
            let config = null;
            if (configMatch) {
                try {
                    config = JSON.parse(configMatch[1]);
                } catch (e) {}
            }

            return {
                publicKey: publicKey,
                config: config,
                html: html
            };
        } catch (err) {
            this.log('Error getting page data:', err.message);
            return null;
        }
    }

    /**
     * Parse card string (various formats)
     */
    parseCard(cardString) {
        // Remove spaces and common separators
        const cleaned = cardString.replace(/[\s\-]/g, '');
        
        // Format: number|mm|yy|cvv or number|mm|yyyy|cvv
        const parts = cleaned.split('|');
        
        if (parts.length >= 4) {
            let expMonth = parts[1];
            let expYear = parts[2];
            
            // Handle 2-digit year
            if (expYear.length === 2) {
                expYear = '20' + expYear;
            }
            
            // Handle 4-digit year as MMYY
            if (parts[1].length === 4) {
                expMonth = parts[1].substring(0, 2);
                expYear = '20' + parts[1].substring(2, 4);
            }

            return {
                number: parts[0],
                expMonth: expMonth.padStart(2, '0'),
                expYear: expYear,
                cvv: parts[3],
                valid: this.validateCard(parts[0])
            };
        }

        return null;
    }

    /**
     * Validate card number using Luhn algorithm
     */
    validateCard(number) {
        const cleaned = number.replace(/\D/g, '');
        
        if (cleaned.length < 13 || cleaned.length > 19) {
            return false;
        }

        let sum = 0;
        let isEven = false;

        for (let i = cleaned.length - 1; i >= 0; i--) {
            let digit = parseInt(cleaned[i], 10);

            if (isEven) {
                digit *= 2;
                if (digit > 9) {
                    digit -= 9;
                }
            }

            sum += digit;
            isEven = !isEven;
        }

        return sum % 10 === 0;
    }

    /**
     * Get card brand from number
     */
    getCardBrand(number) {
        const cleaned = number.replace(/\D/g, '');
        
        const brands = [
            { name: 'visa', pattern: /^4/ },
            { name: 'mastercard', pattern: /^5[1-5]|^2[2-7]/ },
            { name: 'amex', pattern: /^3[47]/ },
            { name: 'discover', pattern: /^6(?:011|5)/ },
            { name: 'diners', pattern: /^3(?:0[0-5]|[68])/ },
            { name: 'jcb', pattern: /^(?:2131|1800|35)/ },
            { name: 'unionpay', pattern: /^62/ }
        ];

        for (const brand of brands) {
            if (brand.pattern.test(cleaned)) {
                return brand.name;
            }
        }

        return 'unknown';
    }

    /**
     * Create payment method with Stripe
     */
    async createPaymentMethod(card, billingDetails = {}) {
        this.log('Creating payment method...');

        try {
            const response = await fetch('https://api.stripe.com/v1/payment_methods', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Authorization': `Bearer ${this.publicKey}`,
                    ...this.getHeaders()
                },
                body: new URLSearchParams({
                    'type': 'card',
                    'card[number]': card.number,
                    'card[exp_month]': card.expMonth,
                    'card[exp_year]': card.expYear,
                    'card[cvc]': card.cvv,
                    'billing_details[name]': billingDetails.name || this.generateName(),
                    'billing_details[email]': billingDetails.email || this.generateEmail(),
                    'billing_details[address][line1]': billingDetails.address?.line1 || this.generateAddress(),
                    'billing_details[address][city]': billingDetails.address?.city || 'New York',
                    'billing_details[address][state]': billingDetails.address?.state || 'NY',
                    'billing_details[address][postal_code]': billingDetails.address?.postalCode || this.generateZip(),
                    'billing_details[address][country]': billingDetails.address?.country || 'US'
                })
            });

            const data = await response.json();

            if (data.error) {
                return { success: false, error: data.error.message, code: data.error.code };
            }

            return {
                success: true,
                paymentMethodId: data.id,
                card: data.card,
                brand: data.card?.brand
            };
        } catch (err) {
            return { success: false, error: err.message };
        }
    }

    /**
     * Confirm checkout session
     */
    async confirmCheckout(paymentMethodId, options = {}) {
        this.log('Confirming checkout...');

        if (!this.sessionId) {
            return { success: false, error: 'No session ID' };
        }

        try {
            const response = await fetch(`https://api.stripe.com/v1/checkout/sessions/${this.sessionId}/confirm`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Authorization': `Bearer ${this.publicKey}`,
                    ...this.getHeaders()
                },
                body: new URLSearchParams({
                    'payment_method': paymentMethodId,
                    'expected_amount': options.amount || '',
                    'expected_currency': options.currency || ''
                })
            });

            const data = await response.json();

            if (data.error) {
                return { 
                    success: false, 
                    error: data.error.message, 
                    code: data.error.code,
                    declineCode: data.error.decline_code
                };
            }

            // Check if requires 3DS
            if (data.payment_intent?.status === 'requires_action') {
                return {
                    success: false,
                    requires3DS: true,
                    paymentIntent: data.payment_intent
                };
            }

            // Check if succeeded
            if (data.payment_intent?.status === 'succeeded' || data.status === 'complete') {
                return {
                    success: true,
                    status: 'succeeded',
                    paymentIntent: data.payment_intent
                };
            }

            return {
                success: false,
                status: data.status || data.payment_intent?.status,
                data: data
            };
        } catch (err) {
            return { success: false, error: err.message };
        }
    }

    /**
     * Process full checkout flow
     */
    async processCheckout(card, billingDetails = {}) {
        this.log('Processing checkout...');

        // Step 1: Parse card
        const parsedCard = typeof card === 'string' ? this.parseCard(card) : card;
        if (!parsedCard) {
            return { success: false, error: 'Invalid card format' };
        }

        if (!parsedCard.valid) {
            return { success: false, error: 'Invalid card number (Luhn check failed)' };
        }

        this.log('Card brand:', this.getCardBrand(parsedCard.number));

        // Step 2: Create payment method
        const pmResult = await this.createPaymentMethod(parsedCard, billingDetails);
        if (!pmResult.success) {
            return pmResult;
        }

        this.log('Payment method created:', pmResult.paymentMethodId);

        // Step 3: Confirm checkout
        const confirmResult = await this.confirmCheckout(pmResult.paymentMethodId);
        
        return {
            ...confirmResult,
            paymentMethodId: pmResult.paymentMethodId,
            cardBrand: pmResult.brand
        };
    }

    /**
     * Get request headers
     */
    getHeaders() {
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site'
        };
    }

    /**
     * Generate random name
     */
    generateName() {
        const firstNames = ['John', 'Jane', 'Michael', 'Sarah', 'David', 'Emily', 'James', 'Emma', 'Robert', 'Olivia'];
        const lastNames = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez'];
        return `${firstNames[Math.floor(Math.random() * firstNames.length)]} ${lastNames[Math.floor(Math.random() * lastNames.length)]}`;
    }

    /**
     * Generate random email
     */
    generateEmail() {
        const domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com'];
        const name = this.generateRandomString(8, 'abcdefghijklmnopqrstuvwxyz');
        const num = Math.floor(Math.random() * 999);
        return `${name}${num}@${domains[Math.floor(Math.random() * domains.length)]}`;
    }

    /**
     * Generate random address
     */
    generateAddress() {
        const num = Math.floor(Math.random() * 9999) + 1;
        const streets = ['Main St', 'Oak Ave', 'Park Blvd', 'Maple Dr', 'Cedar Ln', 'Pine St', 'Elm Ave', 'Washington Blvd'];
        return `${num} ${streets[Math.floor(Math.random() * streets.length)]}`;
    }

    /**
     * Generate random ZIP code
     */
    generateZip() {
        return String(Math.floor(Math.random() * 89999) + 10000);
    }

    /**
     * Generate random string
     */
    generateRandomString(length, chars) {
        let result = '';
        for (let i = 0; i < length; i++) {
            result += chars[Math.floor(Math.random() * chars.length)];
        }
        return result;
    }

    /**
     * Log message
     */
    log(...args) {
        if (this.verbose) {
            console.log('[PAYMENT]', ...args);
        }
    }

    /**
     * Set fingerprint module
     */
    setFingerprint(fingerprint) {
        this.fingerprint = fingerprint;
    }

    /**
     * Set anti-bot module
     */
    setAntiBot(antiBot) {
        this.antiBot = antiBot;
    }

    /**
     * Set session manager
     */
    setSession(session) {
        this.session = session;
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.PaymentHandler = PaymentHandler;
}
