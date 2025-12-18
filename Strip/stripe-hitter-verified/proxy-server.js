const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');

const {
    fetchCheckoutInfo,
    parseCheckoutUrl,
    StripeCheckoutInfoError
} = require('./gateways/stripe/checkout-based/checkout-info');

const {
    generateCardFromBin,
    parseCardString,
    attemptPayment,
    formatPaymentResponse,
    createDetailedResponse,
    isPaymentApproved,
    isPaymentDeclined,
    isPaymentPending
} = require('./gateways/stripe/checkout-based/payer');

const {
    PaymentStatus
} = require('./gateways/stripe/checkout-based/response-handler');

const { AdvancedPaymentFlow } = require('./gateways/stripe/checkout-based/advanced-flow');
const { CaptchaSolver } = require('./gateways/stripe/checkout-based/captcha-solver');
const { ThreeDSHandler } = require('./gateways/stripe/checkout-based/3ds-handler');
const { SuccessDetector } = require('./gateways/stripe/checkout-based/success-detector');

class ProxyServer {
    constructor(options = {}) {
        this.port = options.port || 8080;
        this.useApiKey = options.useApiKey || false;
        this.apiKey = options.apiKey || '';
        this.maxPayloadSize = 10 * 1024 * 1024;
        this.debugMode = !!options.debugMode;
        this.maxWorkers = options.maxWorkers || 3;
        
        this.server = null;
        this.activeWorkers = 0;
        
        this.stats = {
            totalRequests: 0,
            totalBytesTransferred: 0,
            activeConnections: 0
        };
    }

    start() {
        this.server = http.createServer((req, res) => {
            this.handleRequest(req, res);
        });

        this.server.listen(this.port, () => {
            console.log('\n');
            console.log('$$\\    $$\\  $$$$$$\\  $$$$$$\\ $$$$$$$\\  $$\\ ');
            console.log('$$ |   $$ |$$  __$$\\ \\_$$  _|$$  __$$\\ $$ |');
            console.log('$$ |   $$ |$$ /  $$ |  $$ |  $$ |  $$ |$$ |');
            console.log('\\$$\\  $$  |$$ |  $$ |  $$ |  $$ |  $$ |$$ |');
            console.log(' \\$$\\$$  / $$ |  $$ |  $$ |  $$ |  $$ |\\__|');
            console.log('  \\$$$  /  $$ |  $$ |  $$ |  $$ |  $$ |    ');
            console.log('   \\$  /    $$$$$$  |$$$$$$\\ $$$$$$$  |$$\\ ');
            console.log('    \\_/     \\______/ \\______|\\_______/ \\__|');
            console.log('\n');
            console.log(`Port:        ${this.port}`);
            console.log(`Workers:     ${this.maxWorkers} concurrent`);
            console.log(`API Key:     ${this.useApiKey ? 'REQUIRED' : 'DISABLED'}`);
            console.log(`Debug Mode:  ${this.debugMode ? 'ENABLED' : 'DISABLED'}`);
        });

        process.on('SIGINT', () => {
            this.shutdown();
        });
    }

    handleRequest(req, res) {
        this.stats.totalRequests++;
        this.stats.activeConnections++;

        if (this.activeWorkers >= this.maxWorkers) {
            if (this.debugMode) {
                console.log(`[PROXY] Queue full (${this.activeWorkers}/${this.maxWorkers}) - waiting...`);
            }
            setTimeout(() => {
                this.handleRequest(req, res);
            }, 100);
            return;
        }

        this.activeWorkers++;
        
        const cleanup = () => {
            this.activeWorkers--;
            this.stats.activeConnections--;
        };

        res.on('finish', cleanup);
        res.on('close', cleanup);

        if (this.useApiKey) {
            const providedKey = req.headers['x-api-key'];
            if (!providedKey || providedKey !== this.apiKey) {
                this.sendJson(res, 401, { error: 'Unauthorized', message: 'Invalid or missing X-API-Key' });
                if (this.debugMode) {
                    console.log(`[PROXY] 401 ${req.method} ${req.url} - Invalid API key`);
                }
                return;
            }
        }

        let parsedUrl;
        try {
            const hostHeader = req.headers.host || `localhost:${this.port}`;
            parsedUrl = new URL(req.url, `http://${hostHeader}`);
        } catch (err) {
            this.sendJson(res, 400, {
                error: 'Bad Request',
                message: 'Invalid request URL'
            });
            return;
        }

        const payGenMatch = parsedUrl.pathname.match(/^\/stripe\/(checkout|cjheckout)-based\/url\/(.+?)\/pay\/gen\/([^\/\?]+)$/);
        if (payGenMatch) {
            const encodedUrl = payGenMatch[2];
            const binPart = payGenMatch[3];
            this.handleStripePayGen(req, res, encodedUrl, binPart, parsedUrl.searchParams);
            return;
        }

        const payCardMatch = parsedUrl.pathname.match(/^\/stripe\/(checkout|cjheckout)-based\/url\/(.+?)\/pay\/cc\/([^\/\?]+)$/);
        if (payCardMatch) {
            const encodedUrl = payCardMatch[2];
            const cardSpec = payCardMatch[3];
            this.handleStripePayCard(req, res, encodedUrl, cardSpec, parsedUrl.searchParams);
            return;
        }

        const directStripePath = parsedUrl.pathname.match(/^\/stripe\/(?:checkout|cjheckout)-based\/url\/(.+)\/info$/);
        if (directStripePath) {
            try {
                const encodedSegment = directStripePath[1];
                const checkoutUrl = decodeURIComponent(encodedSegment);
                const hostHeader = req.headers.host || `localhost:${this.port}`;
                const normalizedUrl = new URL('/stripe/checkout-based/url/info', `http://${hostHeader}`);
                normalizedUrl.searchParams.set('checkoutUrl', checkoutUrl);
                this.handleStripeCheckoutInfo(req, res, normalizedUrl);
            } catch (err) {
                this.sendJson(res, 400, {
                    error: 'Bad Request',
                    message: 'Checkout URL segment must be percent-encoded'
                });
            }
            return;
        }

        if (parsedUrl.pathname === '/stripe/checkout-based/url/info' || parsedUrl.pathname === '/stripe/cjheckout-based/url/info') {
            this.handleStripeCheckoutInfo(req, res, parsedUrl);
            return;
        }

        // Handle advanced payment flow endpoint
        if (req.url.includes('/pay/advanced')) {
            this.handleAdvancedPaymentFlow(req, res, parsedUrl);
            return;
        }

        // Handle payment endpoints with response formatting
        if (req.url.includes('/pay/cc') || req.url.includes('/pay/gen')) {
            this.handlePaymentRequest(req, res, parsedUrl);
            return;
        }

        let targetUrl;
        if (req.url.startsWith('/proxy/')) {
            targetUrl = req.url.substring(7); 
        } else {
            this.sendJson(res, 400, {
                error: 'Bad Request',
                message: 'URL must start with /proxy/ followed by full URL',
                example: '/proxy/https://api.stripe.com/v1/customers'
            });
            return;
        }

        this.proxyRequest(targetUrl, req, res);
    }

    proxyRequest(targetUrl, req, res) {
        console.log(`[PROXY] ${req.method} ${targetUrl}`);

        const chunks = [];
        req.on('data', chunk => chunks.push(chunk));
        req.on('end', () => {
            try {
                const body = Buffer.concat(chunks);
                this.stats.totalBytesTransferred += body.length;

                const url = new URL(targetUrl);
                const isHttps = url.protocol === 'https:';
                const httpModule = isHttps ? https : http;

                const options = {
                    hostname: url.hostname,
                    port: url.port || (isHttps ? 443 : 80),
                    path: url.pathname + url.search,
                    method: req.method,
                    headers: {
                        ...req.headers,
                        host: url.hostname
                    },
                    timeout: 30000
                };

                if (isHttps) {
                    options.rejectUnauthorized = false;
                }

                delete options.headers['x-api-key'];

                const proxyReq = httpModule.request(options, (proxyRes) => {
                    this.handleProxyResponse(proxyRes, res);
                });

                proxyReq.on('error', (err) => {
                    console.error('[PROXY] Request error:', err.message);
                    if (!res.headersSent) {
                        res.writeHead(502, { 'Content-Type': 'application/json' });
                        res.end(JSON.stringify({ 
                            error: 'Bad Gateway',
                            message: err.message,
                            target: targetUrl
                        }));
                    }
                });

                proxyReq.on('timeout', () => {
                    console.error('[PROXY] Request timeout');
                    proxyReq.destroy();
                    if (!res.headersSent) {
                        res.writeHead(504, { 'Content-Type': 'application/json' });
                        res.end(JSON.stringify({ error: 'Gateway Timeout' }));
                    }
                });

                if (body.length > 0) {
                    proxyReq.write(body);
                }

                proxyReq.end();
            } catch (err) {
                console.error('[PROXY] Error:', err.message);
                if (!res.headersSent) {
                    res.writeHead(500, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ 
                        error: 'Internal Server Error',
                        message: err.message 
                    }));
                }
            }
        });

        req.on('error', (err) => {
            console.error('[PROXY] Request error:', err.message);
            if (!res.headersSent) {
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'Request Error' }));
            }
        });
    }

    handleProxyResponse(proxyRes, res) {
        const chunks = [];

        proxyRes.on('data', (chunk) => {
            chunks.push(chunk);
        });

        proxyRes.on('end', () => {
            try {
                const responseBody = Buffer.concat(chunks);
                this.stats.totalBytesTransferred += responseBody.length;

                res.writeHead(proxyRes.statusCode, proxyRes.headers);
                res.end(responseBody);

                console.log(`[PROXY] Response: ${proxyRes.statusCode} (${responseBody.length} bytes)`);
            } catch (err) {
                console.error('[PROXY] Error processing response:', err.message);
                if (!res.headersSent) {
                    res.writeHead(500, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ error: 'Response Error' }));
                }
            }
        });

        proxyRes.on('error', (err) => {
            console.error('[PROXY] Response error:', err.message);
            if (!res.headersSent) {
                res.writeHead(502, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'Response Error' }));
            }
        });
    }

    handleStripeCheckoutInfo(req, res, parsedUrl) {
        const method = (req.method || 'GET').toUpperCase();

        if (method !== 'GET' && method !== 'POST') {
            this.sendJson(res, 405, { error: 'Method Not Allowed', allowed: ['GET', 'POST'] });
            return;
        }

        const processRequest = async (bodyBuffer) => {
            let payload = {};

            if (bodyBuffer && bodyBuffer.length) {
                try {
                    payload = this.parseRequestBody(bodyBuffer, req.headers['content-type']);
                } catch (err) {
                    this.sendJson(res, 400, { error: 'Invalid request body', message: err.message });
                    return;
                }
            }

            const query = parsedUrl.searchParams;

            const checkoutUrl = this.pickFirstValue([
                payload.checkoutUrl,
                payload.url,
                query.get('checkoutUrl'),
                query.get('url')
            ]);

            const derived = checkoutUrl ? parseCheckoutUrl(checkoutUrl) : { sessionId: null, publicKey: null, site: null };

            const sessionId = this.validateSessionId(this.pickFirstValue([
                payload.sessionId,
                payload.cs,
                query.get('sessionId'),
                query.get('cs'),
                derived.sessionId
            ]));

            if (!sessionId) {
                this.sendJson(res, 400, {
                    error: 'Invalid session id',
                    message: 'Provide a cs_live_* or cs_test_* value via "sessionId" or "cs"'
                });
                return;
            }

            const publicKey = this.validatePublicKey(this.pickFirstValue([
                payload.publicKey,
                payload.pk,
                query.get('publicKey'),
                query.get('pk'),
                derived.publicKey
            ]));

            if (!publicKey) {
                this.sendJson(res, 400, {
                    error: 'Invalid publishable key',
                    message: 'Provide a pk_live_* or pk_test_* value via "publicKey" or "pk"'
                });
                return;
            }

            const localeValue = this.pickFirstValue([
                payload.locale,
                payload.browser_locale,
                query.get('locale')
            ]);

            const timezoneValue = this.pickFirstValue([
                payload.timezone,
                payload.browser_timezone,
                query.get('timezone')
            ]);

            const locale = typeof localeValue === 'string' && localeValue.trim() ? localeValue.trim() : 'en-US';
            const timezone = typeof timezoneValue === 'string' && timezoneValue.trim() ? timezoneValue.trim() : 'UTC';

            try {
                const info = await fetchCheckoutInfo({
                    sessionId,
                    publicKey,
                    locale,
                    timezone,
                    fallbackSite: derived.site || undefined
                });

                console.log(`[STRIPE] Checkout info fetched for ${sessionId}`);
                this.sendJson(res, 200, info);
            } catch (err) {
                if (err instanceof StripeCheckoutInfoError) {
                    const statusCode = err.statusCode && err.statusCode >= 400 ? err.statusCode : 502;
                    const response = {
                        error: 'Stripe request failed',
                        message: err.message
                    };

                    if (err.details && err.details.error) {
                        if (err.details.error.code) {
                            response.code = err.details.error.code;
                        }
                        if (err.details.error.message) {
                            response.stripeMessage = err.details.error.message;
                        }
                    }

                    this.sendJson(res, statusCode, response);
                    return;
                }

                console.error('[STRIPE] Info endpoint error:', err.message || err);
                this.sendJson(res, 500, {
                    error: 'Internal Server Error',
                    message: 'Failed to retrieve Stripe checkout information'
                });
            }
        };

        if (method === 'GET') {
            processRequest(Buffer.alloc(0));
            return;
        }

        this.collectRequestBody(req)
            .then(processRequest)
            .catch((err) => {
                if (err && err.message === 'Payload too large') {
                    this.sendJson(res, 413, { error: 'Payload too large' });
                    return;
                }

                console.error('[STRIPE] Failed to read request body:', err?.message || err);
                this.sendJson(res, 400, { error: 'Invalid request body' });
            });
    }

    async handlePaymentRequest(req, res, parsedUrl) {
        const method = (req.method || 'GET').toUpperCase();
        if (method !== 'GET' && method !== 'POST') {
            this.sendJson(res, 405, { error: 'Method Not Allowed', allowed: ['GET', 'POST'] });
            return;
        }

        try {
            const urlParts = req.url.split('/');
            const payIndex = urlParts.indexOf('pay');
            
            if (payIndex === -1) {
                this.sendJson(res, 400, { error: 'Invalid payment URL' });
                return;
            }

            const payType = urlParts[payIndex + 1]; // 'cc' or 'gen'
            const checkoutUrlEncoded = urlParts[payIndex - 1];
            const checkoutUrl = decodeURIComponent(checkoutUrlEncoded);
            
            let card = null;
            let retries = 0;

            if (payType === 'cc') {
                const cardStr = urlParts[payIndex + 2];
                if (!cardStr) {
                    this.sendJson(res, 400, { error: 'Card data required for /pay/cc' });
                    return;
                }
                card = parseCardString(cardStr);
            } else if (payType === 'gen') {
                const bin = urlParts[payIndex + 2] || '424242';
                const retryParam = parsedUrl.searchParams.get('retry');
                retries = retryParam ? parseInt(retryParam) : 0;
                card = () => generateCardFromBin(bin);
            } else {
                this.sendJson(res, 400, { error: 'Invalid payment type' });
                return;
            }

            console.log(`[PAYMENT] Processing ${payType} payment for ${checkoutUrl.substring(0, 50)}...`);
            
            const result = await attemptPayment({
                checkoutUrl,
                card,
                retries
            });

            // Format response with payment status
            const formattedResponse = {
                timestamp: new Date().toISOString(),
                success: result.success,
                status: result.status || (result.success ? PaymentStatus.APPROVED : PaymentStatus.DECLINED),
                message: result.message,
                attempts: result.attempts,
                card: result.card ? {
                    last4: result.card.cardNumber?.slice(-4) || 'XXXX',
                    expiration: `${result.card.expMonth}/${result.card.expYear}`,
                    type: this.getCardType(result.card.cardNumber)
                } : null,
                details: result.details || result.error || {}
            };

            const statusCode = result.success ? 200 : 402;
            this.sendJson(res, statusCode, formattedResponse);
            console.log(`[PAYMENT] ${result.success ? 'APPROVED' : 'DECLINED'} - ${result.message}`);
        } catch (err) {
            console.error('[PAYMENT] Error:', err.message);
            this.sendJson(res, 500, {
                success: false,
                status: PaymentStatus.FAILED,
                error: 'Payment processing failed',
                message: err.message
            });
        }
    }

    async handleAdvancedPaymentFlow(req, res, parsedUrl) {
        const method = (req.method || 'GET').toUpperCase();
        if (method !== 'GET' && method !== 'POST') {
            this.sendJson(res, 405, { error: 'Method Not Allowed', allowed: ['GET', 'POST'] });
            return;
        }

        try {
            const urlParts = req.url.split('/');
            const advIndex = urlParts.indexOf('advanced');
            
            if (advIndex === -1) {
                this.sendJson(res, 400, { error: 'Invalid advanced payment URL' });
                return;
            }

            const checkoutUrlEncoded = urlParts[advIndex - 1];
            const checkoutUrl = decodeURIComponent(checkoutUrlEncoded);
            const cardStr = urlParts[advIndex + 1];

            if (!cardStr) {
                this.sendJson(res, 400, { error: 'Card data required' });
                return;
            }

            const card = parseCardString(cardStr);

            console.log(`[ADVANCED] Starting advanced payment flow for ${checkoutUrl.substring(0, 50)}...`);

            // Initialize advanced flow
            const flow = new AdvancedPaymentFlow({
                verbose: true,
                maxRetries: 2,
                timeout: 120000
            });

            // Execute complete flow
            const flowResult = await flow.executePaymentFlow(checkoutUrl, card);

            // Create response
            const response = {
                timestamp: new Date().toISOString(),
                success: flowResult.success,
                duration: flowResult.duration,
                stages: {
                    payment: flowResult.stages.payment?.success || false,
                    captcha: flowResult.stages.captcha?.success || flowResult.stages.captcha?.skipped || false,
                    threeDS: flowResult.stages.threeDS?.success || flowResult.stages.threeDS?.skipped || false,
                    verification: flowResult.stages.success?.success || false
                },
                errors: flowResult.errors,
                details: flowResult.stages.payment?.response || {}
            };

            const statusCode = flowResult.success ? 200 : 402;
            this.sendJson(res, statusCode, response);

            console.log(`[ADVANCED] Flow completed: ${flowResult.success ? '✅ SUCCESS' : '❌ FAILED'}`);
        } catch (err) {
            console.error('[ADVANCED] Error:', err.message);
            this.sendJson(res, 500, {
                success: false,
                error: 'Advanced payment flow failed',
                message: err.message
            });
        }
    }

    getCardType(cardNumber) {
        if (!cardNumber) return 'Unknown';
        const patterns = {
            'Visa': /^4[0-9]{12}(?:[0-9]{3})?$/,
            'Mastercard': /^5[1-5][0-9]{14}$/,
            'AmEx': /^3[47][0-9]{13}$/,
            'Discover': /^6(?:011|5[0-9]{2})[0-9]{12}$/
        };
        for (const [type, pattern] of Object.entries(patterns)) {
            if (pattern.test(cardNumber)) return type;
        }
        return 'Unknown';
    }

    collectRequestBody(req) {
        return new Promise((resolve, reject) => {
            const chunks = [];
            let totalLength = 0;

            const cleanup = () => {
                req.removeListener('data', onData);
                req.removeListener('end', onEnd);
                req.removeListener('error', onError);
            };

            const onData = (chunk) => {
                totalLength += chunk.length;
                if (totalLength > this.maxPayloadSize) {
                    cleanup();
                    reject(new Error('Payload too large'));
                    req.destroy();
                    return;
                }
                chunks.push(chunk);
            };

            const onEnd = () => {
                cleanup();
                resolve(Buffer.concat(chunks));
            };

            const onError = (err) => {
                cleanup();
                reject(err);
            };

            req.on('data', onData);
            req.on('end', onEnd);
            req.on('error', onError);
        });
    }

    parseRequestBody(buffer, contentType = '') {
        const body = buffer.toString('utf8');
        if (!body.trim()) {
            return {};
        }

        if (contentType.includes('application/json')) {
            return JSON.parse(body);
        }

        if (contentType.includes('application/x-www-form-urlencoded')) {
            const params = new URLSearchParams(body);
            const result = {};
            for (const [key, value] of params.entries()) {
                result[key] = value;
            }
            return result;
        }

        try {
            return JSON.parse(body);
        } catch (err) {
            throw new Error('Unsupported content type');
        }
    }

    pickFirstValue(values) {
        for (const value of values) {
            if (value !== undefined && value !== null && value !== '') {
                return value;
            }
        }
        return null;
    }

    validateSessionId(value) {
        if (typeof value !== 'string') {
            return null;
        }
        const trimmed = value.trim();
        return /^cs_(?:live|test)_[A-Za-z0-9]+$/.test(trimmed) ? trimmed : null;
    }

    validatePublicKey(value) {
        if (typeof value !== 'string') {
            return null;
        }
        const trimmed = value.trim();
        return /^pk_(?:live|test)_[A-Za-z0-9]+$/.test(trimmed) ? trimmed : null;
    }

    sendJson(res, statusCode, payload) {
        if (res.writableEnded) {
            return;
        }

        const body = JSON.stringify(payload);
        res.writeHead(statusCode, { 'Content-Type': 'application/json' });
        res.end(body);
        this.stats.totalBytesTransferred += Buffer.byteLength(body);
    }

    handleStripePayGen(req, res, encodedUrl, binPart, query) {
        let checkoutUrl;
        try {
            checkoutUrl = decodeURIComponent(encodedUrl);
        } catch (err) {
            this.sendJson(res, 400, { error: 'Invalid URL encoding' });
            return;
        }

        const retryParam = query.get('retry') || query.get('retries') || '0';
        const retries = Math.max(0, Math.min(parseInt(retryParam) || 0, 10));

        const bin = binPart.replace(/[^0-9]/g, '').slice(0, 6);
        if (!bin || bin.length < 6) {
            this.sendJson(res, 400, { error: 'BIN must be at least 6 digits' });
            return;
        }

        if (this.debugMode) {
            console.log(`[STRIPE PAY/GEN] Checkout: ${checkoutUrl.slice(0, 80)}...`);
            console.log(`[STRIPE PAY/GEN] BIN: ${bin}, Retries: ${retries}`);
        }

        attemptPayment({
            checkoutUrl,
            card: () => generateCardFromBin(bin),
            retries
        })
            .then(result => {
                if (result.success) {
                    const response = {
                        success: true,
                        attempts: result.attempts,
                        card: { last4: result.card.cardNumber.slice(-4), exp: `${result.card.expMonth}/${result.card.expYear}` }
                    };
                    
                    if (result.requires3DS) {
                        response.requires3DS = true;
                        response.paymentIntent = result.paymentIntent;
                        response.message = 'Payment method accepted (3DS challenge required)';
                    } else {
                        response.message = 'Payment completed';
                    }
                    
                    this.sendJson(res, 200, response);
                } else {
                    const errorSummary = result.error?.code || result.error?.message || 'Unknown error';
                    this.sendJson(res, 402, {
                        success: false,
                        attempts: result.attempts,
                        error: errorSummary,
                        message: 'Card declined'
                    });
                }
            })
            .catch(err => {
                console.error('[STRIPE PAY/GEN] Error:', err.message || err);
                this.sendJson(res, 500, {
                    error: 'Payment processing failed',
                    message: err.message
                });
            });
    }

    handleStripePayCard(req, res, encodedUrl, cardSpec, query) {
        let checkoutUrl;
        try {
            checkoutUrl = decodeURIComponent(encodedUrl);
        } catch (err) {
            this.sendJson(res, 400, { error: 'Invalid URL encoding' });
            return;
        }

        let card;
        try {
            card = parseCardString(decodeURIComponent(cardSpec));
        } catch (err) {
            this.sendJson(res, 400, {
                error: 'Invalid card format',
                message: 'Expected: number|month|year|cvv (e.g., 4242424242424242|12|25|123)',
                details: err.message
            });
            return;
        }

        if (this.debugMode) {
            console.log(`[STRIPE PAY/CC] Checkout: ${checkoutUrl.slice(0, 80)}...`);
            console.log(`[STRIPE PAY/CC] Card: ****${card.cardNumber.slice(-4)} (single attempt)`);
        }

        attemptPayment({ checkoutUrl, card, retries: 0 })
            .then(result => {
                if (result.success) {
                    const response = {
                        success: true,
                        attempts: result.attempts,
                        card: { last4: result.card.cardNumber.slice(-4), exp: `${result.card.expMonth}/${result.card.expYear}` }
                    };
                    
                    if (result.requires3DS) {
                        response.requires3DS = true;
                        response.paymentIntent = result.paymentIntent;
                        response.message = 'Payment method accepted (3DS challenge required)';
                    } else {
                        response.message = 'Payment completed';
                    }
                    
                    this.sendJson(res, 200, response);
                } else {
                    this.sendJson(res, 402, {
                        success: false,
                        attempts: result.attempts,
                        error: result.error,
                        message: 'Payment failed after retries'
                    });
                }
            })
            .catch(err => {
                console.error('[STRIPE PAY/CC] Error:', err.message || err);
                this.sendJson(res, 500, {
                    error: 'Payment processing failed',
                    message: err.message
                });
            });
    }

    shutdown() {
        console.log('\n[SERVER] Shutting down...');
        
        if (this.server) {
            this.server.close();
        }

        process.exit(0);
    }
}

if (require.main === module) {
        const envPath = path.join(__dirname, '.env');
        const config = {
            port: 8080,
            useApiKey: false,
            apiKey: '',
            debugMode: false,
            maxWorkers: 3
        };

    if (fs.existsSync(envPath)) {
        const envContent = fs.readFileSync(envPath, 'utf8');
        envContent.split('\n').forEach(line => {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith('#')) return;

            const [rawKey, ...valueParts] = trimmed.split('=');
            const key = rawKey.trim();
            const value = valueParts.join('=').trim();
            const normalizedKey = key.toUpperCase().replace(/-/g, '_');

            if (normalizedKey === 'PORT') {
                config.port = parseInt(value) || 8080;
            } else if (normalizedKey === 'USE_API_KEY') {
                config.useApiKey = value.toLowerCase() === 'true';
            } else if (normalizedKey === 'API_KEY') {
                config.apiKey = value;
            } else if (normalizedKey === 'DEBUG_MODE') {
                const lowered = value.toLowerCase();
                config.debugMode = ['true', '1', 'yes', 'on'].includes(lowered);
            } else if (normalizedKey === 'MAX_WORKERS') {
                config.maxWorkers = parseInt(value) || 3;
            }
        });
    }

    const server = new ProxyServer(config);
    server.start();
}

module.exports = ProxyServer;
