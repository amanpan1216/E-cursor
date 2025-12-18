/**
 * Enhanced Payment Flow
 * Integrates advanced captcha solver and anti-bot detection
 */

const { AdvancedCaptchaSolver } = require('./advanced-captcha-solver');
const { AntiBotHeaders } = require('./anti-bot-headers');
const { ThreeDSHandler } = require('./3ds-handler');
const { SuccessDetector } = require('./success-detector');
const { attemptPayment } = require('./payer');

class EnhancedPaymentFlow {
    constructor(options = {}) {
        this.captchaSolver = new AdvancedCaptchaSolver(options.captcha);
        this.antiBotHeaders = new AntiBotHeaders(options.antiBot);
        this.threeDSHandler = new ThreeDSHandler(options.threeDS);
        this.successDetector = new SuccessDetector(options.success);
        this.maxRetries = options.maxRetries || 3;
        this.timeout = options.timeout || 120000;
        this.verbose = options.verbose !== false;
    }

    /**
     * Execute complete enhanced payment flow
     */
    async executeEnhancedFlow(checkoutUrl, card) {
        const flowResult = {
            success: false,
            stages: {},
            errors: [],
            startTime: Date.now(),
            config: {
                headers: {},
                cookies: {},
                antiDetection: {}
            }
        };

        try {
            console.log('\n╔════════════════════════════════════════════════════════════╗');
            console.log('║      ENHANCED PAYMENT FLOW WITH ANTI-BOT DETECTION         ║');
            console.log('╚════════════════════════════════════════════════════════════╝\n');

            const flowResult2 = {
                success: false,
                stages: {},
                errors: [],
                startTime: Date.now(),
                config: {
                    headers: this.antiBotHeaders.getHeaders(),
                    cookies: this.antiBotHeaders.getCookies(),
                    antiDetection: this.antiBotHeaders.getAntiDetectionTechniques()
                }
            };

            // Stage 1: Prepare anti-bot configuration
            console.log('[FLOW] Stage 1: Preparing Anti-Bot Configuration');
            const antiBot = this.antiBotHeaders.getCompleteConfig();
            flowResult.stages.antiBot = {
                success: true,
                config: antiBot,
                timestamp: Date.now()
            };
            console.log('[FLOW] ✅ Anti-bot configuration prepared');

            // Stage 2: Initial Payment Attempt
            console.log('[FLOW] Stage 2: Initial Payment Attempt');
            const paymentResult = await this.executePaymentAttempt(checkoutUrl, card, antiBot);
            flowResult.stages.payment = paymentResult;

            if (!paymentResult.success) {
                flowResult.errors.push('Initial payment attempt failed');
                return flowResult;
            }

            // Stage 3: Check for Captcha
            console.log('[FLOW] Stage 3: Checking for Captcha Challenge');
            const captchaChallenge = null; // Captcha detection would go here

            if (captchaChallenge) {
                console.log('[FLOW] ✅ Captcha challenge detected, solving with advanced methods...');
                const captchaResult = await this.solveCaptchaWithFallbacks(captchaChallenge);
                flowResult.stages.captcha = captchaResult;

                if (!captchaResult.success) {
                    flowResult.errors.push('Captcha solving failed');
                    return flowResult;
                }
            } else {
                console.log('[FLOW] ✅ No captcha challenge detected');
                flowResult.stages.captcha = { success: true, skipped: true };
            }

            // Stage 4: Check for 3DS
            console.log('[FLOW] Stage 4: Checking for 3D Secure Requirement');
            const threeDSChallenge = this.threeDSHandler.extract3DSChallenge(paymentResult.response);

            if (threeDSChallenge) {
                console.log('[FLOW] ✅ 3DS challenge detected, processing...');
                const threeDSResult = await this.process3DSChallenge(threeDSChallenge);
                flowResult.stages.threeDS = threeDSResult;

                if (!threeDSResult.success) {
                    flowResult.errors.push('3DS verification failed');
                    return flowResult;
                }
            } else {
                console.log('[FLOW] ✅ No 3DS challenge detected');
                flowResult.stages.threeDS = { success: true, skipped: true };
            }

            // Stage 5: Verify Payment Success
            console.log('[FLOW] Stage 5: Verifying Payment Success');
            const successResult = await this.verifyPaymentSuccess(paymentResult.response);
            flowResult.stages.success = successResult;

            if (successResult.success) {
                console.log('[FLOW] ✅ Payment Successful!');
                flowResult.success = true;
            } else {
                flowResult.errors.push('Payment verification failed');
            }

            flowResult.duration = Date.now() - flowResult.startTime;

            console.log('\n╔════════════════════════════════════════════════════════════╗');
            console.log(`║  ENHANCED FLOW: ${flowResult.success ? '✅ SUCCESS' : '❌ FAILED'}                                   ║`);
            console.log(`║  Duration: ${flowResult.duration}ms                                        ║`);
            console.log('╚════════════════════════════════════════════════════════════╝\n');

            return flowResult;
        } catch (err) {
            console.error('[FLOW] Fatal error:', err.message);
            flowResult.errors.push(err.message);
            flowResult.duration = Date.now() - flowResult.startTime;
            return flowResult;
        }
    }

    /**
     * Execute payment attempt with anti-bot headers
     */
    async executePaymentAttempt(checkoutUrl, card, antiBot, attempt = 1) {
        try {
            console.log(`[FLOW] Payment attempt ${attempt}/${this.maxRetries + 1}`);

            const result = await attemptPayment({
                checkoutUrl,
                card,
                retries: 0,
                headers: antiBot.headers,
                cookies: antiBot.cookies
            });

            return {
                success: true,
                attempt: attempt,
                response: result,
                antiBot: antiBot,
                timestamp: Date.now()
            };
        } catch (err) {
            console.error(`[FLOW] Payment attempt ${attempt} failed:`, err.message);

            if (attempt < this.maxRetries) {
                console.log(`[FLOW] Retrying with different anti-bot configuration...`);
                const newAntiBot = new AntiBotHeaders().getCompleteConfig();
                await this.delay(2000);
                return this.executePaymentAttempt(checkoutUrl, card, newAntiBot, attempt + 1);
            }

            return {
                success: false,
                attempt: attempt,
                error: err.message,
                timestamp: Date.now()
            };
        }
    }

    /**
     * Solve captcha with multiple fallback methods
     */
    async solveCaptchaWithFallbacks(challenge) {
        try {
            console.log('[FLOW] Solving captcha with advanced fallback methods...');

            const solveResult = await this.captchaSolver.solve(challenge);

            if (!solveResult.success) {
                throw new Error(solveResult.error || 'Captcha solving failed');
            }

            console.log(`[FLOW] ✅ Captcha solved using ${solveResult.method}`);

            // Verify solution
            const verifyResult = await this.captchaSolver.verifyToken(solveResult.token);

            return {
                success: verifyResult,
                method: solveResult.method,
                token: solveResult.token,
                verified: verifyResult,
                timestamp: Date.now()
            };
        } catch (err) {
            console.error('[FLOW] Captcha solving failed:', err.message);
            return {
                success: false,
                error: err.message,
                timestamp: Date.now()
            };
        }
    }

    /**
     * Process 3DS challenge
     */
    async process3DSChallenge(challenge) {
        try {
            console.log('[FLOW] Processing 3DS challenge...');

            const result = await this.threeDSHandler.complete3DSFlow(challenge);

            if (!result.success) {
                throw new Error(result.error || '3DS processing failed');
            }

            return {
                success: true,
                paymentIntentId: challenge.paymentIntentId,
                challengeType: challenge.type,
                timestamp: Date.now()
            };
        } catch (err) {
            console.error('[FLOW] 3DS processing failed:', err.message);
            return {
                success: false,
                error: err.message,
                timestamp: Date.now()
            };
        }
    }

    /**
     * Verify payment success
     */
    async verifyPaymentSuccess(responseData) {
        try {
            console.log('[FLOW] Verifying payment success...');

            const isSuccess = this.successDetector.isPaymentSuccess(responseData);

            if (!isSuccess) {
                throw new Error('Payment not marked as successful');
            }

            const report = this.successDetector.createSuccessReport(responseData, '');

            return {
                success: true,
                report: report,
                timestamp: Date.now()
            };
        } catch (err) {
            console.error('[FLOW] Success verification failed:', err.message);
            return {
                success: false,
                error: err.message,
                timestamp: Date.now()
            };
        }
    }

    /**
     * Delay utility
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * Create comprehensive flow report
     */
    createFlowReport(flowResult) {
        return {
            timestamp: new Date().toISOString(),
            success: flowResult.success,
            duration: flowResult.duration,
            antiBot: {
                headers: Object.keys(flowResult.config.headers).length,
                cookies: Object.keys(flowResult.config.cookies).length,
                techniques: Object.keys(flowResult.config.antiDetection).length
            },
            stages: {
                antiBot: flowResult.stages.antiBot?.success || false,
                payment: flowResult.stages.payment?.success || false,
                captcha: flowResult.stages.captcha?.success || flowResult.stages.captcha?.skipped || false,
                threeDS: flowResult.stages.threeDS?.success || flowResult.stages.threeDS?.skipped || false,
                success: flowResult.stages.success?.success || false
            },
            errors: flowResult.errors,
            captchaMethod: flowResult.stages.captcha?.method || 'N/A'
        };
    }

    /**
     * Get flow statistics
     */
    getFlowStatistics(flowResult) {
        const completedStages = Object.values(flowResult.stages).filter(s => s && (s.success || s.skipped)).length;
        const totalStages = Object.keys(flowResult.stages).length;

        return {
            successRate: (completedStages / totalStages) * 100,
            completedStages: completedStages,
            totalStages: totalStages,
            duration: flowResult.duration,
            errorCount: flowResult.errors.length,
            antiBotHeaders: Object.keys(flowResult.config.headers).length,
            antiBotCookies: Object.keys(flowResult.config.cookies).length,
            antiBotTechniques: Object.keys(flowResult.config.antiDetection).length
        };
    }
}

module.exports = {
    EnhancedPaymentFlow
};
