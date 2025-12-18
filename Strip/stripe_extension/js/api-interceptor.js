// API Request Interceptor - Direct Stripe API Modification
// Intercepts and modifies Stripe API requests at network level

(function() {
    'use strict';
    
    console.log('[API INTERCEPTOR] Initializing...');
    
    // Store original fetch and XMLHttpRequest
    const originalFetch = window.fetch;
    const originalXHROpen = XMLHttpRequest.prototype.open;
    const originalXHRSend = XMLHttpRequest.prototype.send;
    
    let currentCardData = null;
    let autofillData = null;
    
    // Load card and autofill data from storage
    chrome.storage.local.get(['cards', 'currentCardIndex', 'autofillData', 'email'], (data) => {
        if (data.cards && data.cards[data.currentCardIndex || 0]) {
            currentCardData = data.cards[data.currentCardIndex || 0];
            console.log('[API INTERCEPTOR] Card data loaded:', currentCardData);
        }
        autofillData = data.autofillData || {};
        autofillData.email = data.email || autofillData.email;
    });
    
    // Listen for card updates from content script
    window.addEventListener('message', (event) => {
        if (event.source !== window) return;
        
        if (event.data.type === 'updateCurrentCard') {
            currentCardData = event.data.card;
            console.log('[API INTERCEPTOR] Card updated via window message:', currentCardData);
        } else if (event.data.type === 'updateAutofillData') {
            autofillData = event.data.data;
            console.log('[API INTERCEPTOR] Autofill updated via window message:', autofillData);
        }
    });
    
    // Also listen for chrome runtime messages (from background)
    if (typeof chrome !== 'undefined' && chrome.runtime) {
        chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
            if (message.type === 'updateCurrentCard') {
                currentCardData = message.card;
                console.log('[API INTERCEPTOR] Card updated via runtime:', currentCardData);
            } else if (message.type === 'updateAutofillData') {
                autofillData = message.data;
            }
        });
    }
    
    // Intercept Stripe API endpoints
    const STRIPE_ENDPOINTS = [
        '/v1/payment_intents',
        '/v1/payment_methods',
        '/v1/tokens',
        '/v1/sources',
        '/v1/setup_intents',
        '/v1/charges',
        '/payments/payment_intents',
        '/payments/payment_methods'
    ];
    
    function isStripeRequest(url) {
        return STRIPE_ENDPOINTS.some(endpoint => url.includes(endpoint)) ||
               url.includes('api.stripe.com') ||
               url.includes('checkout.stripe.com');
    }
    
    function modifyStripePayload(originalPayload, url) {
        if (!currentCardData) {
            console.log('[API INTERCEPTOR] No card data available');
            return originalPayload;
        }
        
        console.log('[API INTERCEPTOR] Modifying payload for:', url);
        
        let payload = originalPayload;
        
        // Parse existing payload
        let params = new URLSearchParams();
        if (typeof payload === 'string') {
            params = new URLSearchParams(payload);
        } else if (payload instanceof FormData) {
            params = new URLSearchParams();
            for (let [key, value] of payload.entries()) {
                params.append(key, value);
            }
        }
        
        // Inject card data
        if (url.includes('payment_methods') || url.includes('tokens')) {
            // Card number
            if (!params.has('card[number]') && !params.has('payment_method_data[card][number]')) {
                params.set('card[number]', currentCardData.number);
                params.set('payment_method_data[card][number]', currentCardData.number);
            }
            
            // Expiry
            if (!params.has('card[exp_month]')) {
                params.set('card[exp_month]', currentCardData.expMonth);
                params.set('payment_method_data[card][exp_month]', currentCardData.expMonth);
            }
            if (!params.has('card[exp_year]')) {
                params.set('card[exp_year]', currentCardData.expYear);
                params.set('payment_method_data[card][exp_year]', currentCardData.expYear);
            }
            
            // CVC
            if (!params.has('card[cvc]')) {
                params.set('card[cvc]', currentCardData.cvv);
                params.set('payment_method_data[card][cvc]', currentCardData.cvv);
            }
        }
        
        // Inject billing details
        if (autofillData) {
            if (autofillData.name && !params.has('billing_details[name]')) {
                params.set('billing_details[name]', autofillData.name);
                params.set('payment_method_data[billing_details][name]', autofillData.name);
            }
            
            if (autofillData.email && !params.has('billing_details[email]')) {
                params.set('billing_details[email]', autofillData.email);
                params.set('payment_method_data[billing_details][email]', autofillData.email);
            }
            
            if (autofillData.address && !params.has('billing_details[address][line1]')) {
                params.set('billing_details[address][line1]', autofillData.address);
                params.set('payment_method_data[billing_details][address][line1]', autofillData.address);
            }
            
            if (autofillData.city && !params.has('billing_details[address][city]')) {
                params.set('billing_details[address][city]', autofillData.city);
                params.set('payment_method_data[billing_details][address][city]', autofillData.city);
            }
            
            if (autofillData.zip && !params.has('billing_details[address][postal_code]')) {
                params.set('billing_details[address][postal_code]', autofillData.zip);
                params.set('payment_method_data[billing_details][address][postal_code]', autofillData.zip);
            }
            
            if (autofillData.country && !params.has('billing_details[address][country]')) {
                params.set('billing_details[address][country]', autofillData.country);
                params.set('payment_method_data[billing_details][address][country]', autofillData.country);
            }
        }
        
        console.log('[API INTERCEPTOR] Modified payload:', params.toString());
        return params.toString();
    }
    
    // Intercept fetch API
    window.fetch = async function(url, options = {}) {
        const urlString = typeof url === 'string' ? url : url.url;
        
        if (isStripeRequest(urlString)) {
            console.log('[API INTERCEPTOR] Intercepted fetch:', urlString);
            
            // Modify request body
            if (options.body && (options.method === 'POST' || options.method === 'PUT')) {
                options.body = modifyStripePayload(options.body, urlString);
                
                // Update content-type if needed
                if (!options.headers) {
                    options.headers = {};
                }
                if (typeof options.headers.set === 'function') {
                    options.headers.set('Content-Type', 'application/x-www-form-urlencoded');
                } else {
                    options.headers['Content-Type'] = 'application/x-www-form-urlencoded';
                }
            }
        }
        
        // Call original fetch
        const response = await originalFetch(url, options);
        
        // Intercept response
        if (isStripeRequest(urlString)) {
            const clonedResponse = response.clone();
            try {
                const data = await clonedResponse.json();
                console.log('[API INTERCEPTOR] Response:', data);
                
                // Send to content script for processing
                window.postMessage({
                    type: 'STRIPE_API_RESPONSE',
                    url: urlString,
                    data: data,
                    status: response.status
                }, '*');
            } catch (e) {
                console.error('[API INTERCEPTOR] Error parsing response:', e);
            }
        }
        
        return response;
    };
    
    // Intercept XMLHttpRequest
    XMLHttpRequest.prototype.open = function(method, url, ...args) {
        this._url = url;
        this._method = method;
        return originalXHROpen.apply(this, [method, url, ...args]);
    };
    
    XMLHttpRequest.prototype.send = function(body) {
        if (this._url && isStripeRequest(this._url)) {
            console.log('[API INTERCEPTOR] Intercepted XHR:', this._url);
            
            // Modify request body
            if (body && (this._method === 'POST' || this._method === 'PUT')) {
                body = modifyStripePayload(body, this._url);
            }
            
            // Intercept response
            const originalOnReadyStateChange = this.onreadystatechange;
            this.onreadystatechange = function() {
                if (this.readyState === 4 && this.status > 0) {
                    try {
                        const data = JSON.parse(this.responseText);
                        console.log('[API INTERCEPTOR] XHR Response:', data);
                        
                        // Send to content script
                        window.postMessage({
                            type: 'STRIPE_API_RESPONSE',
                            url: this._url,
                            data: data,
                            status: this.status
                        }, '*');
                    } catch (e) {
                        console.error('[API INTERCEPTOR] Error parsing XHR response:', e);
                    }
                }
                
                if (originalOnReadyStateChange) {
                    originalOnReadyStateChange.apply(this, arguments);
                }
            };
        }
        
        return originalXHRSend.apply(this, [body]);
    };
    
    console.log('[API INTERCEPTOR] Initialized successfully');
    
    // Export for content script
    window.APIInterceptor = {
        updateCard: (card) => {
            currentCardData = card;
            console.log('[API INTERCEPTOR] Card updated via API:', card);
        },
        updateAutofill: (data) => {
            autofillData = data;
            console.log('[API INTERCEPTOR] Autofill updated via API:', data);
        }
    };
})();
