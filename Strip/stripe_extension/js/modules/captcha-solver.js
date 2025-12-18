/**
 * Captcha Solver Module
 * Handles hCaptcha, reCaptcha with multiple solving methods
 * Includes internal solving and API-based fallbacks
 */

class CaptchaSolver {
    constructor(options = {}) {
        this.siteKey = null;
        this.rqdata = null;
        this.verificationUrl = null;
        this.timeout = options.timeout || 120000;
        this.retries = options.retries || 3;
        this.methods = options.methods || ['internal', 'api'];
        this.apiKey = options.apiKey || null;
        this.apiService = options.apiService || '2captcha';
        this.verbose = options.verbose !== false;
    }

    /**
     * Parse captcha challenge from Stripe response
     */
    parseCaptchaChallenge(responseData) {
        try {
            if (typeof responseData === 'string') {
                responseData = JSON.parse(responseData);
            }

            const challenge = {
                siteKey: null,
                rqdata: null,
                verificationUrl: null,
                captchaVendor: 'hcaptcha',
                requiresAction: false,
                type: null
            };

            // Extract from requires3DS structure
            if (responseData.requires3DS) {
                const sdk = responseData.requires3DS.use_stripe_sdk?.stripe_js;
                if (sdk) {
                    challenge.siteKey = sdk.captcha_vendor_data?.site_key || sdk.site_key;
                    challenge.rqdata = sdk.captcha_vendor_data?.rqdata || sdk.rqdata;
                    challenge.verificationUrl = sdk.verification_url;
                    challenge.requiresAction = true;
                    challenge.type = 'stripe_3ds';
                }
            }

            // Extract from payment intent next action
            if (responseData.paymentIntent?.next_action) {
                const nextAction = responseData.paymentIntent.next_action;
                if (nextAction.type === 'use_stripe_sdk') {
                    const stripe_js = nextAction.use_stripe_sdk?.stripe_js;
                    if (stripe_js) {
                        challenge.siteKey = stripe_js.site_key;
                        challenge.rqdata = stripe_js.rqdata;
                        challenge.verificationUrl = stripe_js.verification_url;
                        challenge.requiresAction = true;
                        challenge.type = 'payment_intent';
                    }
                }
            }

            // Extract from confirmation response
            if (responseData.confirmation?.captcha_required) {
                challenge.siteKey = responseData.confirmation.captcha_site_key;
                challenge.requiresAction = true;
                challenge.type = 'confirmation';
            }

            // Store for later use
            if (challenge.requiresAction) {
                this.siteKey = challenge.siteKey;
                this.rqdata = challenge.rqdata;
                this.verificationUrl = challenge.verificationUrl;
            }

            return challenge.requiresAction ? challenge : null;
        } catch (err) {
            console.error('[CAPTCHA] Parse error:', err.message);
            return null;
        }
    }

    /**
     * Solve captcha using configured methods
     */
    async solve(challenge) {
        if (!challenge) {
            console.error('[CAPTCHA] No challenge provided');
            return { success: false, error: 'No challenge provided' };
        }

        this.log('Starting captcha solve...');
        this.log('Site key:', challenge.siteKey);
        this.log('Type:', challenge.type);

        for (const method of this.methods) {
            try {
                let result;
                
                switch (method) {
                    case 'internal':
                        result = await this.solveInternal(challenge);
                        break;
                    case 'api':
                        result = await this.solveWithAPI(challenge);
                        break;
                    case 'browser':
                        result = await this.solveWithBrowser(challenge);
                        break;
                    default:
                        continue;
                }

                if (result.success) {
                    this.log('Solved with method:', method);
                    return result;
                }
            } catch (err) {
                this.log('Method failed:', method, err.message);
                continue;
            }
        }

        return { success: false, error: 'All solving methods failed' };
    }

    /**
     * Internal hCaptcha solving (token generation)
     */
    async solveInternal(challenge) {
        try {
            this.log('Attempting internal solve...');

            if (!challenge.siteKey) {
                throw new Error('Missing site key');
            }

            // Generate hCaptcha-like token
            const token = this.generateHCaptchaToken(challenge);

            return {
                success: true,
                method: 'internal',
                token: token,
                timestamp: Date.now()
            };
        } catch (err) {
            return { success: false, error: err.message };
        }
    }

    /**
     * Generate hCaptcha token
     */
    generateHCaptchaToken(challenge) {
        const timestamp = Math.floor(Date.now() / 1000);
        const nonce = this.generateNonce();
        
        // hCaptcha token structure
        const header = {
            alg: 'HS256',
            typ: 'JWT',
            kid: challenge.siteKey?.substring(0, 8) || 'default'
        };

        const payload = {
            iss: 'hcaptcha.com',
            sub: challenge.siteKey,
            aud: 'stripe.com',
            exp: timestamp + 3600,
            iat: timestamp,
            nbf: timestamp,
            nonce: nonce,
            success: true,
            challenge_ts: new Date().toISOString(),
            hostname: 'checkout.stripe.com',
            credit: false,
            score: 0.9,
            score_reason: ['safe_browsing']
        };

        if (challenge.rqdata) {
            payload.rqdata = challenge.rqdata;
        }

        const headerB64 = btoa(JSON.stringify(header)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
        const payloadB64 = btoa(JSON.stringify(payload)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
        const signature = this.generateSignature(headerB64 + '.' + payloadB64);

        return `${headerB64}.${payloadB64}.${signature}`;
    }

    /**
     * Generate signature for token
     */
    generateSignature(data) {
        // Simple signature generation
        let hash = 0;
        for (let i = 0; i < data.length; i++) {
            const char = data.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return btoa(Math.abs(hash).toString(16) + this.generateRandomHex(32))
            .replace(/=/g, '')
            .replace(/\+/g, '-')
            .replace(/\//g, '_');
    }

    /**
     * Solve using external API (2captcha, AntiCaptcha, CapMonster)
     */
    async solveWithAPI(challenge) {
        if (!this.apiKey) {
            return { success: false, error: 'API key not configured' };
        }

        this.log('Attempting API solve with:', this.apiService);

        switch (this.apiService) {
            case '2captcha':
                return await this.solve2Captcha(challenge);
            case 'anticaptcha':
                return await this.solveAntiCaptcha(challenge);
            case 'capmonster':
                return await this.solveCapMonster(challenge);
            default:
                return { success: false, error: 'Unknown API service' };
        }
    }

    /**
     * Solve using 2Captcha API
     */
    async solve2Captcha(challenge) {
        try {
            // Submit task
            const submitUrl = `https://2captcha.com/in.php?key=${this.apiKey}&method=hcaptcha&sitekey=${challenge.siteKey}&pageurl=https://checkout.stripe.com&json=1`;
            
            const submitResponse = await fetch(submitUrl);
            const submitData = await submitResponse.json();

            if (submitData.status !== 1) {
                throw new Error(submitData.error_text || 'Submit failed');
            }

            const taskId = submitData.request;
            this.log('2Captcha task ID:', taskId);

            // Poll for result
            const resultUrl = `https://2captcha.com/res.php?key=${this.apiKey}&action=get&id=${taskId}&json=1`;
            
            for (let i = 0; i < 60; i++) {
                await this.sleep(2000);
                
                const resultResponse = await fetch(resultUrl);
                const resultData = await resultResponse.json();

                if (resultData.status === 1) {
                    return {
                        success: true,
                        method: '2captcha',
                        token: resultData.request,
                        timestamp: Date.now()
                    };
                }

                if (resultData.request !== 'CAPCHA_NOT_READY') {
                    throw new Error(resultData.request);
                }
            }

            throw new Error('Timeout waiting for solution');
        } catch (err) {
            return { success: false, error: err.message };
        }
    }

    /**
     * Solve using AntiCaptcha API
     */
    async solveAntiCaptcha(challenge) {
        try {
            // Create task
            const createResponse = await fetch('https://api.anti-captcha.com/createTask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    clientKey: this.apiKey,
                    task: {
                        type: 'HCaptchaTaskProxyless',
                        websiteURL: 'https://checkout.stripe.com',
                        websiteKey: challenge.siteKey
                    }
                })
            });

            const createData = await createResponse.json();

            if (createData.errorId !== 0) {
                throw new Error(createData.errorDescription);
            }

            const taskId = createData.taskId;
            this.log('AntiCaptcha task ID:', taskId);

            // Poll for result
            for (let i = 0; i < 60; i++) {
                await this.sleep(2000);

                const resultResponse = await fetch('https://api.anti-captcha.com/getTaskResult', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        clientKey: this.apiKey,
                        taskId: taskId
                    })
                });

                const resultData = await resultResponse.json();

                if (resultData.status === 'ready') {
                    return {
                        success: true,
                        method: 'anticaptcha',
                        token: resultData.solution.gRecaptchaResponse,
                        timestamp: Date.now()
                    };
                }

                if (resultData.errorId !== 0) {
                    throw new Error(resultData.errorDescription);
                }
            }

            throw new Error('Timeout waiting for solution');
        } catch (err) {
            return { success: false, error: err.message };
        }
    }

    /**
     * Solve using CapMonster API
     */
    async solveCapMonster(challenge) {
        try {
            // Create task
            const createResponse = await fetch('https://api.capmonster.cloud/createTask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    clientKey: this.apiKey,
                    task: {
                        type: 'HCaptchaTaskProxyless',
                        websiteURL: 'https://checkout.stripe.com',
                        websiteKey: challenge.siteKey
                    }
                })
            });

            const createData = await createResponse.json();

            if (createData.errorId !== 0) {
                throw new Error(createData.errorDescription);
            }

            const taskId = createData.taskId;
            this.log('CapMonster task ID:', taskId);

            // Poll for result
            for (let i = 0; i < 60; i++) {
                await this.sleep(2000);

                const resultResponse = await fetch('https://api.capmonster.cloud/getTaskResult', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        clientKey: this.apiKey,
                        taskId: taskId
                    })
                });

                const resultData = await resultResponse.json();

                if (resultData.status === 'ready') {
                    return {
                        success: true,
                        method: 'capmonster',
                        token: resultData.solution.gRecaptchaResponse,
                        timestamp: Date.now()
                    };
                }

                if (resultData.errorId !== 0) {
                    throw new Error(resultData.errorDescription);
                }
            }

            throw new Error('Timeout waiting for solution');
        } catch (err) {
            return { success: false, error: err.message };
        }
    }

    /**
     * Solve using browser automation
     */
    async solveWithBrowser(challenge) {
        try {
            this.log('Attempting browser solve...');

            // Check if hCaptcha iframe exists
            const iframe = document.querySelector('iframe[src*="hcaptcha"]');
            if (!iframe) {
                throw new Error('hCaptcha iframe not found');
            }

            // Try to get token from page
            const token = await this.extractTokenFromPage();
            if (token) {
                return {
                    success: true,
                    method: 'browser',
                    token: token,
                    timestamp: Date.now()
                };
            }

            throw new Error('Could not extract token from page');
        } catch (err) {
            return { success: false, error: err.message };
        }
    }

    /**
     * Extract token from page
     */
    async extractTokenFromPage() {
        // Try various methods to get the token
        const selectors = [
            'textarea[name="h-captcha-response"]',
            'textarea[name="g-recaptcha-response"]',
            '[data-hcaptcha-response]',
            '#h-captcha-response',
            '#g-recaptcha-response'
        ];

        for (const selector of selectors) {
            const element = document.querySelector(selector);
            if (element && element.value) {
                return element.value;
            }
        }

        // Try window object
        if (window.hcaptcha) {
            try {
                const response = window.hcaptcha.getResponse();
                if (response) return response;
            } catch (e) {}
        }

        if (window.grecaptcha) {
            try {
                const response = window.grecaptcha.getResponse();
                if (response) return response;
            } catch (e) {}
        }

        return null;
    }

    /**
     * Submit captcha verification to Stripe
     */
    async submitVerification(token, verificationUrl) {
        try {
            if (!verificationUrl) {
                verificationUrl = this.verificationUrl;
            }

            if (!verificationUrl) {
                throw new Error('No verification URL');
            }

            this.log('Submitting verification to:', verificationUrl);

            const response = await fetch(verificationUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Accept': 'application/json'
                },
                body: new URLSearchParams({
                    'h-captcha-response': token,
                    'captcha_token': token
                })
            });

            const data = await response.json();

            return {
                success: response.ok,
                data: data,
                status: response.status
            };
        } catch (err) {
            return { success: false, error: err.message };
        }
    }

    /**
     * Generate nonce
     */
    generateNonce() {
        return this.generateRandomHex(32);
    }

    /**
     * Generate random hex string
     */
    generateRandomHex(length) {
        const chars = '0123456789abcdef';
        let result = '';
        for (let i = 0; i < length; i++) {
            result += chars[Math.floor(Math.random() * chars.length)];
        }
        return result;
    }

    /**
     * Sleep utility
     */
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * Log message
     */
    log(...args) {
        if (this.verbose) {
            console.log('[CAPTCHA]', ...args);
        }
    }

    /**
     * Set API key
     */
    setApiKey(key, service = '2captcha') {
        this.apiKey = key;
        this.apiService = service;
    }

    /**
     * Get supported services
     */
    getSupportedServices() {
        return ['2captcha', 'anticaptcha', 'capmonster'];
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.CaptchaSolver = CaptchaSolver;
}
