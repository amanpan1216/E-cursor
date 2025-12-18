/**
 * Content Script - Main entry point for Stripe Checkout pages
 * Coordinates all modules and handles page interaction
 */

(function() {
    'use strict';

    // Initialize modules
    let fingerprint = null;
    let antiBot = null;
    let sessionManager = null;
    let captchaSolver = null;
    let threeDSHandler = null;
    let paymentHandler = null;

    // Current session
    let currentSession = null;

    // Configuration
    const config = {
        autoApplyFingerprint: true,
        autoApplyAntiBot: true,
        verbose: true
    };

    /**
     * Initialize all modules
     */
    function initializeModules() {
        log('Initializing Stripe Toolkit...');

        // Initialize fingerprint module
        if (typeof BrowserFingerprint !== 'undefined') {
            fingerprint = new BrowserFingerprint();
            fingerprint.generateFingerprint();
            
            if (config.autoApplyFingerprint) {
                fingerprint.applyFingerprint();
            }
            log('Fingerprint module initialized');
        }

        // Initialize anti-bot module
        if (typeof AntiBotHeaders !== 'undefined') {
            antiBot = new AntiBotHeaders({
                verbose: config.verbose
            });
            
            if (config.autoApplyAntiBot) {
                antiBot.applyAntiBotMeasures();
            }
            log('Anti-bot module initialized');
        }

        // Initialize session manager
        if (typeof SessionManager !== 'undefined') {
            sessionManager = new SessionManager();
            log('Session manager initialized');
        }

        // Initialize captcha solver
        if (typeof CaptchaSolver !== 'undefined') {
            captchaSolver = new CaptchaSolver({
                verbose: config.verbose
            });
            log('Captcha solver initialized');
        }

        // Initialize 3DS handler
        if (typeof ThreeDSHandler !== 'undefined') {
            threeDSHandler = new ThreeDSHandler({
                verbose: config.verbose
            });
            log('3DS handler initialized');
        }

        // Initialize payment handler
        if (typeof PaymentHandler !== 'undefined') {
            paymentHandler = new PaymentHandler({
                verbose: config.verbose
            });
            log('Payment handler initialized');
        }

        // Create or get session for current URL
        if (sessionManager) {
            currentSession = sessionManager.getOrCreateSession(window.location.href);
            
            // Store fingerprint in session
            if (fingerprint && currentSession) {
                sessionManager.setFingerprint(
                    currentSession.id,
                    fingerprint.getFingerprint(),
                    fingerprint.getHash()
                );
            }

            // Store headers in session
            if (antiBot && currentSession) {
                sessionManager.setHeaders(
                    currentSession.id,
                    antiBot.getHeaders()
                );
                sessionManager.setCookies(
                    currentSession.id,
                    antiBot.getCookies()
                );
            }
        }

        log('All modules initialized');
        
        // Notify background script
        notifyBackground('initialized', {
            url: window.location.href,
            sessionId: currentSession?.id
        });
    }

    /**
     * Extract checkout information from page
     */
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

        // Extract session ID from URL
        const sessionMatch = window.location.href.match(/cs_[a-zA-Z0-9_]+/);
        if (sessionMatch) {
            info.sessionId = sessionMatch[0];
        }

        // Extract from page content
        const html = document.documentElement.innerHTML;

        // Public key
        const pkMatch = html.match(/pk_live_[a-zA-Z0-9]+/);
        if (pkMatch) {
            info.publicKey = pkMatch[0];
        }

        // Amount
        const amountElement = document.querySelector('[data-testid="total-amount"], .CheckoutPaymentForm-total, .total-amount');
        if (amountElement) {
            info.amount = amountElement.textContent;
        }

        // Merchant name
        const merchantElement = document.querySelector('[data-testid="merchant-name"], .merchant-name, .Header-businessName');
        if (merchantElement) {
            info.merchantName = merchantElement.textContent;
        }

        // Product name
        const productElement = document.querySelector('[data-testid="product-name"], .product-name, .LineItem-name');
        if (productElement) {
            info.productName = productElement.textContent;
        }

        // Email
        const emailInput = document.querySelector('input[type="email"], input[name="email"]');
        if (emailInput) {
            info.customerEmail = emailInput.value;
        }

        log('Extracted checkout info:', info);
        return info;
    }

    /**
     * Fill card details into form
     */
    function fillCardDetails(card) {
        log('Filling card details...');

        const parsedCard = typeof card === 'string' ? parseCardString(card) : card;
        if (!parsedCard) {
            log('Invalid card format');
            return false;
        }

        // Find and fill card number
        const cardNumberInput = document.querySelector(
            'input[name="cardNumber"], input[data-elements-stable-field-name="cardNumber"], input[autocomplete="cc-number"]'
        );
        if (cardNumberInput) {
            simulateInput(cardNumberInput, parsedCard.number);
        }

        // Find and fill expiry
        const expiryInput = document.querySelector(
            'input[name="cardExpiry"], input[data-elements-stable-field-name="cardExpiry"], input[autocomplete="cc-exp"]'
        );
        if (expiryInput) {
            simulateInput(expiryInput, `${parsedCard.expMonth}/${parsedCard.expYear.slice(-2)}`);
        }

        // Find and fill CVV
        const cvvInput = document.querySelector(
            'input[name="cardCvc"], input[data-elements-stable-field-name="cardCvc"], input[autocomplete="cc-csc"]'
        );
        if (cvvInput) {
            simulateInput(cvvInput, parsedCard.cvv);
        }

        log('Card details filled');
        return true;
    }

    /**
     * Parse card string
     */
    function parseCardString(cardString) {
        const parts = cardString.replace(/[\s\-]/g, '').split('|');
        
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
                cvv: parts[3]
            };
        }

        return null;
    }

    /**
     * Simulate human-like input
     */
    function simulateInput(element, value) {
        element.focus();
        
        // Clear existing value
        element.value = '';
        element.dispatchEvent(new Event('input', { bubbles: true }));

        // Type each character with delay
        let index = 0;
        const typeChar = () => {
            if (index < value.length) {
                element.value += value[index];
                element.dispatchEvent(new Event('input', { bubbles: true }));
                element.dispatchEvent(new KeyboardEvent('keydown', { key: value[index] }));
                element.dispatchEvent(new KeyboardEvent('keyup', { key: value[index] }));
                index++;
                setTimeout(typeChar, Math.random() * 50 + 30);
            } else {
                element.dispatchEvent(new Event('change', { bubbles: true }));
                element.blur();
            }
        };

        typeChar();
    }

    /**
     * Click submit button
     */
    function clickSubmit() {
        const submitButton = document.querySelector(
            'button[type="submit"], .SubmitButton, [data-testid="hosted-payment-submit-button"]'
        );
        
        if (submitButton) {
            log('Clicking submit button...');
            submitButton.click();
            return true;
        }

        log('Submit button not found');
        return false;
    }

    /**
     * Monitor for responses
     */
    function setupResponseMonitor() {
        // Intercept fetch
        const originalFetch = window.fetch;
        window.fetch = async function(...args) {
            const response = await originalFetch.apply(this, args);
            
            // Clone response to read body
            const clone = response.clone();
            
            try {
                const url = args[0]?.url || args[0];
                
                if (url.includes('stripe.com')) {
                    const data = await clone.json();
                    handleStripeResponse(url, data);
                }
            } catch (e) {}

            return response;
        };

        // Intercept XMLHttpRequest
        const originalXHR = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function(method, url) {
            this._url = url;
            return originalXHR.apply(this, arguments);
        };

        const originalSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.send = function(body) {
            this.addEventListener('load', function() {
                if (this._url?.includes('stripe.com')) {
                    try {
                        const data = JSON.parse(this.responseText);
                        handleStripeResponse(this._url, data);
                    } catch (e) {}
                }
            });
            return originalSend.apply(this, arguments);
        };

        log('Response monitor setup complete');
    }

    /**
     * Handle Stripe API responses
     */
    function handleStripeResponse(url, data) {
        log('Stripe response:', url);

        // Log to session
        if (sessionManager && currentSession) {
            sessionManager.logResponse(currentSession.id, {
                url: url,
                status: 200,
                body: data
            });
        }

        // Check for captcha requirement
        if (captchaSolver) {
            const challenge = captchaSolver.parseCaptchaChallenge(data);
            if (challenge) {
                log('Captcha required!');
                handleCaptcha(challenge);
            }
        }

        // Check for 3DS requirement
        if (threeDSHandler) {
            if (threeDSHandler.requires3DS(data)) {
                log('3DS required!');
                const challenge = threeDSHandler.extract3DSChallenge(data);
                if (challenge) {
                    handle3DS(challenge);
                }
            }
        }

        // Check for success
        if (data.payment_intent?.status === 'succeeded' || data.status === 'complete') {
            log('Payment succeeded!');
            handleSuccess(data);
        }

        // Check for decline
        if (data.error?.code === 'card_declined') {
            log('Card declined:', data.error.decline_code);
            handleDecline(data);
        }

        // Notify background
        notifyBackground('response', {
            url: url,
            data: data
        });
    }

    /**
     * Handle captcha challenge
     */
    async function handleCaptcha(challenge) {
        log('Handling captcha...');

        if (sessionManager && currentSession) {
            sessionManager.updateState(currentSession.id, {
                requiresCaptcha: true,
                step: 'captcha'
            });
        }

        const result = await captchaSolver.solve(challenge);
        
        if (result.success) {
            log('Captcha solved!');
            
            // Submit verification
            const verifyResult = await captchaSolver.submitVerification(
                result.token,
                challenge.verificationUrl
            );

            if (verifyResult.success) {
                log('Captcha verification successful');
            }
        } else {
            log('Captcha solve failed:', result.error);
        }

        notifyBackground('captcha', {
            challenge: challenge,
            result: result
        });
    }

    /**
     * Handle 3DS challenge
     */
    async function handle3DS(challenge) {
        log('Handling 3DS...');

        if (sessionManager && currentSession) {
            sessionManager.updateState(currentSession.id, {
                requires3DS: true,
                step: '3ds'
            });
        }

        const result = await threeDSHandler.handle3DS(challenge);
        
        if (result.success) {
            log('3DS completed successfully');
            
            // Complete payment
            if (challenge.paymentIntentClientSecret) {
                await threeDSHandler.complete3DS(
                    challenge.paymentIntentId,
                    challenge.paymentIntentClientSecret
                );
            }
        } else {
            log('3DS failed:', result.error);
        }

        notifyBackground('3ds', {
            challenge: challenge,
            result: result
        });
    }

    /**
     * Handle payment success
     */
    function handleSuccess(data) {
        log('Payment successful!');

        if (sessionManager && currentSession) {
            sessionManager.updateState(currentSession.id, {
                step: 'completed'
            });
            sessionManager.endSession(currentSession.id, 'completed');
        }

        notifyBackground('success', {
            paymentIntent: data.payment_intent,
            status: data.status
        });

        // Show success notification
        showNotification('Payment Successful!', 'success');
    }

    /**
     * Handle payment decline
     */
    function handleDecline(data) {
        log('Payment declined:', data.error);

        if (sessionManager && currentSession) {
            sessionManager.updateState(currentSession.id, {
                step: 'declined',
                lastError: data.error
            });
        }

        notifyBackground('decline', {
            error: data.error
        });

        // Show decline notification
        showNotification(`Declined: ${data.error.decline_code || data.error.message}`, 'error');
    }

    /**
     * Show notification
     */
    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
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
            background: ${type === 'success' ? '#22c55e' : type === 'error' ? '#ef4444' : '#3b82f6'};
        `;
        notification.textContent = message;

        // Add animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
        `;
        document.head.appendChild(style);

        document.body.appendChild(notification);

        // Remove after 5 seconds
        setTimeout(() => {
            notification.style.animation = 'slideIn 0.3s ease reverse';
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    }

    /**
     * Notify background script
     */
    function notifyBackground(type, data) {
        try {
            chrome.runtime.sendMessage({
                type: type,
                data: data,
                url: window.location.href,
                timestamp: Date.now()
            });
        } catch (e) {
            // Extension context may not be available
        }
    }

    /**
     * Listen for messages from popup/background
     */
    function setupMessageListener() {
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
                    sendResponse(fingerprint?.getFingerprint());
                    break;

                case 'getHeaders':
                    sendResponse(antiBot?.getHeaders());
                    break;

                case 'getCookies':
                    sendResponse(antiBot?.getCookies());
                    break;

                case 'processCheckout':
                    processFullCheckout(message.card, message.billing)
                        .then(result => sendResponse(result));
                    return true; // Keep channel open for async response

                default:
                    sendResponse({ error: 'Unknown action' });
            }
        });
    }

    /**
     * Process full checkout
     */
    async function processFullCheckout(card, billing = {}) {
        log('Processing full checkout...');

        if (!paymentHandler) {
            return { success: false, error: 'Payment handler not initialized' };
        }

        // Initialize payment handler
        await paymentHandler.initialize(window.location.href);

        // Process checkout
        const result = await paymentHandler.processCheckout(card, billing);

        // Handle 3DS if required
        if (result.requires3DS && threeDSHandler) {
            const challenge = threeDSHandler.extract3DSChallenge(result);
            if (challenge) {
                const threeDSResult = await threeDSHandler.handle3DS(challenge);
                return threeDSResult;
            }
        }

        return result;
    }

    /**
     * Log message
     */
    function log(...args) {
        if (config.verbose) {
            console.log('[STRIPE-TOOLKIT]', ...args);
        }
    }

    /**
     * Initialize on page load
     */
    function init() {
        // Wait for page to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                initializeModules();
                setupResponseMonitor();
                setupMessageListener();
            });
        } else {
            initializeModules();
            setupResponseMonitor();
            setupMessageListener();
        }
    }

    // Start initialization
    init();

    // Expose API for debugging
    window.StripeToolkit = {
        fingerprint: () => fingerprint,
        antiBot: () => antiBot,
        session: () => sessionManager,
        captcha: () => captchaSolver,
        threeds: () => threeDSHandler,
        payment: () => paymentHandler,
        currentSession: () => currentSession,
        extractInfo: extractCheckoutInfo,
        fillCard: fillCardDetails,
        submit: clickSubmit,
        processCheckout: processFullCheckout
    };

})();
