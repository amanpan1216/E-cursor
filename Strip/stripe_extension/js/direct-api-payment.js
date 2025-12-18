/**
 * Direct Stripe API Payment Module
 * Makes direct API calls to Stripe without DOM manipulation
 * Based on Python-style approach
 */

(function() {
    'use strict';
    
    console.log('[DIRECT API] Initializing Direct Payment Module...');
    
    // Stripe API endpoints
    const STRIPE_API_BASE = 'https://api.stripe.com/v1';
    
    /**
     * Make direct request to Stripe API
     */
    async function makeStripeRequest(url, payload, headers = {}) {
        const defaultHeaders = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'Origin': 'https://checkout.stripe.com',
            'Referer': window.location.href,
            'User-Agent': navigator.userAgent
        };
        
        const finalHeaders = { ...defaultHeaders, ...headers };
        
        // Convert payload object to URLSearchParams
        const formBody = new URLSearchParams();
        for (const key in payload) {
            if (payload[key] !== null && payload[key] !== undefined) {
                formBody.append(key, payload[key]);
            }
        }
        
        console.log('[DIRECT API] Request to:', url);
        console.log('[DIRECT API] Payload keys:', Object.keys(payload));
        
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: finalHeaders,
                body: formBody.toString(),
                credentials: 'include'
            });
            
            const data = await response.json();
            
            return {
                statusCode: response.status,
                data: data,
                headers: Object.fromEntries(response.headers.entries())
            };
        } catch (error) {
            console.error('[DIRECT API] Request failed:', error);
            return {
                statusCode: 500,
                data: { error: { message: error.message } },
                headers: {}
            };
        }
    }
    
    /**
     * Parse checkout URL to extract session ID and public key
     */
    function parseCheckoutUrl(url) {
        const match = url.match(/\/c\/pay\/(cs_[a-zA-Z0-9_]+)/);
        const sessionId = match ? match[1] : null;
        
        // Try to extract public key from page
        let publicKey = null;
        const scripts = document.querySelectorAll('script');
        for (const script of scripts) {
            const content = script.textContent || script.innerHTML;
            const pkMatch = content.match(/pk_(live|test)_[a-zA-Z0-9]+/);
            if (pkMatch) {
                publicKey = pkMatch[0];
                break;
            }
        }
        
        return { sessionId, publicKey };
    }
    
    /**
     * Fetch checkout session information
     */
    async function fetchCheckoutInfo(sessionId, publicKey) {
        const url = `${STRIPE_API_BASE}/payment_pages/${sessionId}`;
        const payload = {
            key: publicKey,
            eid: 'NA',
            guid: 'NA',
            muid: 'NA',
            sid: 'NA'
        };
        
        const response = await makeStripeRequest(url, payload);
        
        if (response.statusCode === 200 && response.data) {
            return {
                totals: response.data.totals || {},
                customerEmail: response.data.customer_email || 'test@example.com',
                initChecksum: response.data.init_checksum || '',
                configId: response.data.config_id || null,
                jsChecksum: response.data.js_checksum || null,
                merchantName: response.data.merchant_name || 'Unknown',
                currency: response.data.currency || 'usd',
                amount: response.data.amount_total || 0
            };
        }
        
        return null;
    }
    
    /**
     * Create payment method via direct API call
     */
    async function createPaymentMethod(card, sessionInfo, billingDetails = {}) {
        const payload = {
            type: 'card',
            'card[number]': card.number,
            'card[exp_month]': card.expMonth,
            'card[exp_year]': card.expYear,
            'card[cvc]': card.cvv,
            'billing_details[name]': billingDetails.name || 'Test User',
            'billing_details[email]': billingDetails.email || sessionInfo.customerEmail,
            'billing_details[address][country]': billingDetails.country || 'US',
            guid: 'NA',
            muid: 'NA',
            sid: 'NA',
            key: sessionInfo.publicKey,
            'payment_user_agent': 'stripe.js/90ba939846; stripe-js-v3/90ba939846; checkout',
            'client_attribution_metadata[client_session_id]': sessionInfo.sessionId,
            'client_attribution_metadata[merchant_integration_source]': 'checkout',
            'client_attribution_metadata[merchant_integration_version]': 'hosted_checkout',
            'client_attribution_metadata[payment_method_selection_flow]': 'automatic'
        };
        
        // Add address details if provided
        if (billingDetails.address) {
            if (billingDetails.address.line1) {
                payload['billing_details[address][line1]'] = billingDetails.address.line1;
            }
            if (billingDetails.address.city) {
                payload['billing_details[address][city]'] = billingDetails.address.city;
            }
            if (billingDetails.address.state) {
                payload['billing_details[address][state]'] = billingDetails.address.state;
            }
            if (billingDetails.address.postal_code) {
                payload['billing_details[address][postal_code]'] = billingDetails.address.postal_code;
            }
        }
        
        if (sessionInfo.configId) {
            payload['client_attribution_metadata[checkout_config_id]'] = sessionInfo.configId;
        }
        
        const response = await makeStripeRequest(`${STRIPE_API_BASE}/payment_methods`, payload);
        return response;
    }
    
    /**
     * Confirm payment via direct API call
     */
    async function confirmPayment(paymentMethodId, sessionInfo) {
        const payload = {
            eid: 'NA',
            payment_method: paymentMethodId,
            expected_amount: sessionInfo.amount,
            'consent[terms_of_service]': 'accepted',
            expected_payment_method_type: 'card',
            guid: 'NA',
            muid: 'NA',
            sid: 'NA',
            key: sessionInfo.publicKey,
            version: '90ba939846',
            init_checksum: sessionInfo.initChecksum || '',
            passive_captcha_token: '',
            'client_attribution_metadata[client_session_id]': sessionInfo.sessionId,
            'client_attribution_metadata[merchant_integration_source]': 'checkout',
            'client_attribution_metadata[merchant_integration_version]': 'hosted_checkout',
            'client_attribution_metadata[payment_method_selection_flow]': 'automatic'
        };
        
        if (sessionInfo.configId) {
            payload['client_attribution_metadata[checkout_config_id]'] = sessionInfo.configId;
        }
        
        if (sessionInfo.jsChecksum) {
            payload.js_checksum = sessionInfo.jsChecksum;
        }
        
        const response = await makeStripeRequest(
            `${STRIPE_API_BASE}/payment_pages/${sessionInfo.sessionId}/confirm`,
            payload
        );
        return response;
    }
    
    /**
     * Execute complete payment flow via direct API
     */
    async function executeDirectPayment(card, billingDetails = {}) {
        console.log('[DIRECT API] Starting direct payment flow...');
        
        try {
            // Step 1: Parse checkout URL
            const parsed = parseCheckoutUrl(window.location.href);
            if (!parsed.sessionId || !parsed.publicKey) {
                throw new Error('Unable to extract session ID or public key');
            }
            
            console.log('[DIRECT API] Session ID:', parsed.sessionId);
            console.log('[DIRECT API] Public Key:', parsed.publicKey.substring(0, 20) + '...');
            
            // Step 2: Fetch checkout info
            console.log('[DIRECT API] Fetching checkout info...');
            const sessionInfo = await fetchCheckoutInfo(parsed.sessionId, parsed.publicKey);
            if (!sessionInfo) {
                throw new Error('Failed to fetch checkout information');
            }
            
            sessionInfo.sessionId = parsed.sessionId;
            sessionInfo.publicKey = parsed.publicKey;
            
            console.log('[DIRECT API] Merchant:', sessionInfo.merchantName);
            console.log('[DIRECT API] Amount:', sessionInfo.amount / 100, sessionInfo.currency.toUpperCase());
            
            // Step 3: Create payment method
            console.log('[DIRECT API] Creating payment method...');
            const pmResponse = await createPaymentMethod(card, sessionInfo, billingDetails);
            
            if (pmResponse.statusCode !== 200 || !pmResponse.data.id) {
                const error = pmResponse.data.error || { message: 'Failed to create payment method' };
                throw new Error(error.message);
            }
            
            const paymentMethodId = pmResponse.data.id;
            console.log('[DIRECT API] Payment Method ID:', paymentMethodId);
            
            // Step 4: Confirm payment
            console.log('[DIRECT API] Confirming payment...');
            const confirmResponse = await confirmPayment(paymentMethodId, sessionInfo);
            
            const responseData = confirmResponse.data;
            
            // Analyze response
            const result = {
                success: false,
                status: 'unknown',
                card: card,
                response: responseData,
                sessionInfo: sessionInfo
            };
            
            // Check for success
            if (responseData.status === 'complete') {
                result.success = true;
                result.status = 'approved';
                console.log('[DIRECT API] ✅ Payment APPROVED!');
            }
            // Check for 3DS requirement
            else if (responseData.payment_intent?.status === 'requires_action') {
                result.status = '3ds_required';
                result.next_action = responseData.payment_intent.next_action;
                console.log('[DIRECT API] 🔐 3DS verification required');
            }
            // Check for decline
            else if (responseData.payment_intent?.status === 'requires_payment_method') {
                result.status = 'declined';
                const errorInfo = responseData.payment_intent.last_payment_error || {};
                result.error = {
                    code: errorInfo.code || 'card_declined',
                    message: errorInfo.message || 'Card was declined',
                    decline_code: errorInfo.decline_code || 'generic_decline'
                };
                console.log('[DIRECT API] ❌ Payment DECLINED:', result.error.code);
            }
            // Check for error
            else if (responseData.error) {
                result.status = 'error';
                result.error = responseData.error;
                console.log('[DIRECT API] ❌ Error:', result.error.message);
            }
            
            // Send result to content script
            window.postMessage({
                type: 'DIRECT_API_RESULT',
                result: result
            }, '*');
            
            return result;
            
        } catch (error) {
            console.error('[DIRECT API] Payment flow failed:', error);
            return {
                success: false,
                status: 'error',
                error: { message: error.message },
                card: card
            };
        }
    }
    
    // Listen for payment triggers from content script
    window.addEventListener('message', async (event) => {
        if (event.source !== window) return;
        
        if (event.data.type === 'TRIGGER_DIRECT_PAYMENT') {
            console.log('[DIRECT API] Payment triggered from content script');
            const result = await executeDirectPayment(event.data.card, event.data.billingDetails || {});
            console.log('[DIRECT API] Payment result:', result);
        }
    });
    
    // Export to window for content script access
    window.DirectAPIPayment = {
        executeDirectPayment,
        parseCheckoutUrl,
        fetchCheckoutInfo,
        createPaymentMethod,
        confirmPayment
    };
    
    console.log('[DIRECT API] Module initialized successfully');
    
})();
