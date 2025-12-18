(function() {
    'use strict';

    let fingerprint = null;
    let antiBot = null;
    let sessionManager = null;
    let captchaSolver = null;
    let threeDSHandler = null;
    let paymentHandler = null;
    let currentSession = null;
    let isCheckoutPage = false;
    let cardFieldsDetected = false;

    const config = {
        autoApplyFingerprint: true,
        autoApplyAntiBot: true,
        verbose: true
    };

    const CARD_SELECTORS = {
        number: [
            'input[name="cardNumber"]',
            'input[data-elements-stable-field-name="cardNumber"]',
            'input[autocomplete="cc-number"]',
            'input[placeholder*="card number" i]',
            'input[placeholder*="1234" i]',
            'input[id*="cardNumber" i]',
            'input[id*="card-number" i]',
            'input[name="card_number"]',
            'input[name="ccnumber"]',
            'input[data-testid="card-number-input"]',
            '#card-number',
            '.card-number input',
            '[data-stripe="number"]'
        ],
        expiry: [
            'input[name="cardExpiry"]',
            'input[data-elements-stable-field-name="cardExpiry"]',
            'input[autocomplete="cc-exp"]',
            'input[placeholder*="MM" i]',
            'input[placeholder*="expir" i]',
            'input[id*="expiry" i]',
            'input[id*="exp-date" i]',
            'input[name="exp_date"]',
            'input[name="ccexp"]',
            '[data-stripe="exp"]'
        ],
        expMonth: [
            'input[name="cardExpiryMonth"]',
            'input[autocomplete="cc-exp-month"]',
            'select[name="exp_month"]',
            'select[id*="month" i]',
            'input[placeholder*="MM" i]:not([placeholder*="YY" i])'
        ],
        expYear: [
            'input[name="cardExpiryYear"]',
            'input[autocomplete="cc-exp-year"]',
            'select[name="exp_year"]',
            'select[id*="year" i]',
            'input[placeholder*="YY" i]:not([placeholder*="MM" i])'
        ],
        cvv: [
            'input[name="cardCvc"]',
            'input[data-elements-stable-field-name="cardCvc"]',
            'input[autocomplete="cc-csc"]',
            'input[placeholder*="CVC" i]',
            'input[placeholder*="CVV" i]',
            'input[placeholder*="security" i]',
            'input[id*="cvc" i]',
            'input[id*="cvv" i]',
            'input[name="cvc"]',
            'input[name="cvv"]',
            '[data-stripe="cvc"]'
        ],
        email: [
            'input[type="email"]',
            'input[name="email"]',
            'input[autocomplete="email"]',
            'input[placeholder*="email" i]'
        ],
        name: [
            'input[name="cardholderName"]',
            'input[name="name"]',
            'input[autocomplete="cc-name"]',
            'input[placeholder*="name on card" i]',
            'input[placeholder*="cardholder" i]'
        ]
    };

    function log(...args) {
        if (config.verbose) {
            console.log('[STRIPE-TOOLKIT]', ...args);
        }
    }

    function detectCheckoutPage() {
        const url = window.location.href;
        const html = document.documentElement.innerHTML;
        
        const isStripeCheckout = url.includes('checkout.stripe.com') || 
                                 url.includes('stripe.com/pay') ||
                                 url.includes('/checkout');
        
        const hasStripeElements = html.includes('stripe.com') ||
                                  html.includes('pk_live_') ||
                                  html.includes('pk_test_') ||
                                  document.querySelector('[data-stripe]') !== null;
        
        const hasCardFields = findCardFields().number !== null;
        
        isCheckoutPage = isStripeCheckout || hasStripeElements || hasCardFields;
        cardFieldsDetected = hasCardFields;
        
        log('Checkout detection:', { isCheckoutPage, cardFieldsDetected, url });
        
        return isCheckoutPage;
    }

    function findCardFields() {
        const fields = {
            number: null,
            expiry: null,
            expMonth: null,
            expYear: null,
            cvv: null,
            email: null,
            name: null
        };

        for (const [fieldType, selectors] of Object.entries(CARD_SELECTORS)) {
            for (const selector of selectors) {
                try {
                    const element = document.querySelector(selector);
                    if (element && isVisible(element)) {
                        fields[fieldType] = element;
                        break;
                    }
                } catch (e) {}
            }
        }

        const iframes = document.querySelectorAll('iframe');
        iframes.forEach(iframe => {
            try {
                if (iframe.src?.includes('stripe.com') || iframe.name?.includes('stripe')) {
                    log('Found Stripe iframe:', iframe.name || iframe.src);
                }
            } catch (e) {}
        });

        return fields;
    }

    function isVisible(element) {
        if (!element) return false;
        const style = window.getComputedStyle(element);
        return style.display !== 'none' && 
               style.visibility !== 'hidden' && 
               style.opacity !== '0' &&
               element.offsetParent !== null;
    }

    function fillCardDetails(card) {
        log('Filling card details...', card);
        
        const fields = findCardFields();
        let filled = false;

        if (fields.number) {
            simulateInput(fields.number, card.number);
            filled = true;
            log('Filled card number');
        }

        if (fields.expiry) {
            const expValue = `${card.expMonth}/${card.expYear.slice(-2)}`;
            simulateInput(fields.expiry, expValue);
            log('Filled expiry (combined)');
        } else {
            if (fields.expMonth) {
                if (fields.expMonth.tagName === 'SELECT') {
                    selectOption(fields.expMonth, card.expMonth);
                } else {
                    simulateInput(fields.expMonth, card.expMonth);
                }
                log('Filled exp month');
            }
            if (fields.expYear) {
                const year = card.expYear.length === 4 ? card.expYear : '20' + card.expYear;
                if (fields.expYear.tagName === 'SELECT') {
                    selectOption(fields.expYear, year);
                } else {
                    simulateInput(fields.expYear, year.slice(-2));
                }
                log('Filled exp year');
            }
        }

        if (fields.cvv) {
            simulateInput(fields.cvv, card.cvv);
            filled = true;
            log('Filled CVV');
        }

        tryFillStripeIframe(card);

        return filled;
    }

    function tryFillStripeIframe(card) {
        const iframes = document.querySelectorAll('iframe[name*="stripe"], iframe[src*="stripe"]');
        
        iframes.forEach(iframe => {
            try {
                const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
                if (iframeDoc) {
                    const inputs = iframeDoc.querySelectorAll('input');
                    inputs.forEach(input => {
                        const name = input.name?.toLowerCase() || '';
                        const placeholder = input.placeholder?.toLowerCase() || '';
                        
                        if (name.includes('cardnumber') || placeholder.includes('card number')) {
                            simulateInput(input, card.number);
                        } else if (name.includes('exp') || placeholder.includes('mm')) {
                            simulateInput(input, `${card.expMonth}/${card.expYear.slice(-2)}`);
                        } else if (name.includes('cvc') || placeholder.includes('cvc')) {
                            simulateInput(input, card.cvv);
                        }
                    });
                }
            } catch (e) {
                log('Cannot access iframe (cross-origin)');
            }
        });
    }

    function simulateInput(element, value) {
        if (!element) return;
        
        element.focus();
        
        element.dispatchEvent(new Event('focus', { bubbles: true }));
        
        element.value = '';
        element.dispatchEvent(new Event('input', { bubbles: true }));
        
        for (let i = 0; i < value.length; i++) {
            const char = value[i];
            
            element.value += char;
            
            element.dispatchEvent(new KeyboardEvent('keydown', { 
                key: char, 
                code: `Key${char.toUpperCase()}`,
                bubbles: true 
            }));
            element.dispatchEvent(new KeyboardEvent('keypress', { 
                key: char,
                bubbles: true 
            }));
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new KeyboardEvent('keyup', { 
                key: char,
                bubbles: true 
            }));
        }
        
        element.dispatchEvent(new Event('change', { bubbles: true }));
        element.dispatchEvent(new Event('blur', { bubbles: true }));
    }

    function selectOption(selectElement, value) {
        const options = selectElement.options;
        for (let i = 0; i < options.length; i++) {
            if (options[i].value === value || 
                options[i].text === value ||
                options[i].value.includes(value) ||
                options[i].text.includes(value)) {
                selectElement.selectedIndex = i;
                selectElement.dispatchEvent(new Event('change', { bubbles: true }));
                return true;
            }
        }
        return false;
    }

    function clickSubmit() {
        const submitSelectors = [
            'button[type="submit"]',
            '.SubmitButton',
            '[data-testid="hosted-payment-submit-button"]',
            'button[class*="submit" i]',
            'button[class*="pay" i]',
            'input[type="submit"]',
            'button:contains("Pay")',
            'button:contains("Subscribe")',
            'button:contains("Complete")',
            '.btn-primary[type="submit"]'
        ];

        for (const selector of submitSelectors) {
            try {
                const button = document.querySelector(selector);
                if (button && isVisible(button) && !button.disabled) {
                    log('Clicking submit button:', selector);
                    button.click();
                    return true;
                }
            } catch (e) {}
        }

        const buttons = document.querySelectorAll('button');
        for (const button of buttons) {
            const text = button.textContent?.toLowerCase() || '';
            if ((text.includes('pay') || text.includes('submit') || text.includes('subscribe') || text.includes('complete')) &&
                isVisible(button) && !button.disabled) {
                log('Clicking button by text:', text);
                button.click();
                return true;
            }
        }

        log('Submit button not found');
        return false;
    }

    function extractCheckoutInfo() {
        const info = {
            url: window.location.href,
            sessionId: null,
            publicKey: null,
            amount: null,
            currency: null,
            merchantName: null,
            productName: null,
            customerEmail: null
        };

        const sessionMatch = window.location.href.match(/cs_[a-zA-Z0-9_]+/);
        if (sessionMatch) {
            info.sessionId = sessionMatch[0];
        }

        const html = document.documentElement.innerHTML;

        const pkMatch = html.match(/pk_live_[a-zA-Z0-9]+/) || html.match(/pk_test_[a-zA-Z0-9]+/);
        if (pkMatch) {
            info.publicKey = pkMatch[0];
        }

        const amountSelectors = [
            '[data-testid="total-amount"]',
            '.CheckoutPaymentForm-total',
            '.total-amount',
            '.amount',
            '[class*="total" i]',
            '[class*="price" i]'
        ];
        
        for (const selector of amountSelectors) {
            const el = document.querySelector(selector);
            if (el) {
                info.amount = el.textContent?.trim();
                break;
            }
        }

        const merchantSelectors = [
            '[data-testid="merchant-name"]',
            '.merchant-name',
            '.Header-businessName',
            '[class*="merchant" i]',
            '[class*="business" i]'
        ];
        
        for (const selector of merchantSelectors) {
            const el = document.querySelector(selector);
            if (el) {
                info.merchantName = el.textContent?.trim();
                break;
            }
        }

        const emailInput = document.querySelector('input[type="email"]');
        if (emailInput) {
            info.customerEmail = emailInput.value;
        }

        return info;
    }

    function setupResponseMonitor() {
        const originalFetch = window.fetch;
        window.fetch = async function(...args) {
            const response = await originalFetch.apply(this, args);
            const clone = response.clone();
            
            try {
                const url = args[0]?.url || args[0];
                if (typeof url === 'string' && url.includes('stripe.com')) {
                    const data = await clone.json();
                    handleStripeResponse(url, data, response.status);
                }
            } catch (e) {}

            return response;
        };

        const originalXHR = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function(method, url) {
            this._url = url;
            this._method = method;
            return originalXHR.apply(this, arguments);
        };

        const originalSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.send = function(body) {
            this.addEventListener('load', function() {
                if (this._url?.includes('stripe.com')) {
                    try {
                        const data = JSON.parse(this.responseText);
                        handleStripeResponse(this._url, data, this.status);
                    } catch (e) {}
                }
            });
            return originalSend.apply(this, arguments);
        };

        log('Response monitor setup complete');
    }

    function handleStripeResponse(url, data, status) {
        log('Stripe response:', url, status);

        const result = {
            url: url,
            status: status,
            success: false,
            error: null,
            declineCode: null,
            requires3DS: false
        };

        if (data.error) {
            result.error = data.error.message || data.error.code;
            result.declineCode = data.error.decline_code;
            log('Error response:', result.error, result.declineCode);
        }

        if (data.payment_intent?.status === 'succeeded' || 
            data.status === 'complete' ||
            data.status === 'succeeded') {
            result.success = true;
            result.status = 'live';
            log('Payment succeeded!');
            showNotification('Payment Successful!', 'success');
        }

        if (data.error?.code === 'card_declined' || 
            data.error?.type === 'card_error') {
            result.status = 'dead';
            log('Card declined:', result.declineCode);
            showNotification(`Declined: ${result.declineCode || result.error}`, 'error');
        }

        if (data.payment_intent?.status === 'requires_action' ||
            data.next_action?.type === 'use_stripe_sdk' ||
            data.next_action?.type === 'redirect_to_url') {
            result.requires3DS = true;
            log('3DS required');
            showNotification('3DS Verification Required', 'warning');
        }

        notifyPopup('cardResult', { result });
    }

    function showNotification(message, type = 'info') {
        const existing = document.querySelector('.stripe-toolkit-notification');
        if (existing) existing.remove();

        const notification = document.createElement('div');
        notification.className = `stripe-toolkit-notification ${type}`;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 25px;
            border-radius: 8px;
            color: white;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 14px;
            z-index: 999999;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            animation: slideIn 0.3s ease;
            background: ${type === 'success' ? '#22c55e' : type === 'error' ? '#ef4444' : type === 'warning' ? '#f59e0b' : '#3b82f6'};
        `;
        notification.textContent = message;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateX(100%)';
            setTimeout(() => notification.remove(), 300);
        }, 4000);
    }

    function notifyPopup(type, data) {
        try {
            chrome.runtime.sendMessage({
                type: type,
                ...data,
                url: window.location.href,
                timestamp: Date.now()
            });
        } catch (e) {}
    }

    function initializeModules() {
        log('Initializing Stripe Toolkit...');

        if (typeof BrowserFingerprint !== 'undefined') {
            fingerprint = new BrowserFingerprint();
            fingerprint.generateFingerprint();
            if (config.autoApplyFingerprint) {
                fingerprint.applyFingerprint();
            }
            log('Fingerprint module initialized');
        }

        if (typeof AntiBotHeaders !== 'undefined') {
            antiBot = new AntiBotHeaders({ verbose: config.verbose });
            if (config.autoApplyAntiBot) {
                antiBot.applyAntiBotMeasures();
            }
            log('Anti-bot module initialized');
        }

        if (typeof SessionManager !== 'undefined') {
            sessionManager = new SessionManager();
            currentSession = sessionManager.getOrCreateSession(window.location.href);
            log('Session manager initialized');
        }

        if (typeof CaptchaSolver !== 'undefined') {
            captchaSolver = new CaptchaSolver({ verbose: config.verbose });
            log('Captcha solver initialized');
        }

        if (typeof ThreeDSHandler !== 'undefined') {
            threeDSHandler = new ThreeDSHandler({ verbose: config.verbose });
            log('3DS handler initialized');
        }

        if (typeof PaymentHandler !== 'undefined') {
            paymentHandler = new PaymentHandler({ verbose: config.verbose });
            log('Payment handler initialized');
        }

        log('All modules initialized');
    }

    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        log('Received message:', message.action);

        switch (message.action) {
            case 'getInfo':
                sendResponse(extractCheckoutInfo());
                break;

            case 'fillCard':
                const filled = fillCardDetails(message.card);
                sendResponse({ success: filled });
                break;

            case 'submit':
                const submitted = clickSubmit();
                sendResponse({ success: submitted });
                break;

            case 'getSession':
                sendResponse(currentSession);
                break;

            case 'getFingerprint':
                sendResponse(fingerprint?.getFingerprint?.() || null);
                break;

            case 'getHeaders':
                sendResponse(antiBot?.getHeaders?.() || null);
                break;

            case 'getCookies':
                sendResponse(antiBot?.getCookies?.() || null);
                break;

            case 'isCheckoutPage':
                sendResponse({ isCheckout: detectCheckoutPage() });
                break;

            case 'getCardFields':
                const fields = findCardFields();
                sendResponse({
                    hasFields: fields.number !== null || fields.cvv !== null,
                    fields: Object.keys(fields).filter(k => fields[k] !== null)
                });
                break;

            default:
                sendResponse({ error: 'Unknown action' });
        }

        return true;
    });

    function init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', onReady);
        } else {
            onReady();
        }
    }

    function onReady() {
        initializeModules();
        setupResponseMonitor();
        
        if (detectCheckoutPage()) {
            log('Checkout page detected!');
            notifyPopup('checkoutDetected', { 
                info: extractCheckoutInfo(),
                hasCardFields: cardFieldsDetected
            });
        }

        const observer = new MutationObserver(() => {
            if (!cardFieldsDetected && detectCheckoutPage()) {
                log('Card fields appeared');
                notifyPopup('checkoutDetected', { 
                    info: extractCheckoutInfo(),
                    hasCardFields: cardFieldsDetected
                });
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    init();

    window.StripeToolkit = {
        fillCard: fillCardDetails,
        submit: clickSubmit,
        getInfo: extractCheckoutInfo,
        findFields: findCardFields,
        isCheckout: () => isCheckoutPage
    };

})();
