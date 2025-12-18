/**
 * Advanced Payment Automation Flow
 * Orchestrates the complete payment process including captcha solving, 3DS verification, and success detection
 */

const { CaptchaSolver } = require('./captcha-solver');
const { ThreeDSHandler } = require('./3ds-handler');
const { SuccessDetector } = require('./success-detector');
const { attemptPayment } = require('./payer');

class AdvancedPaymentFlow {
    constructor(options = {}) {
        this.captchaSolver = new CaptchaSolver(options.captcha);
        this.threeDSHandler = new ThreeDSHandler(options.threeDS);
        this.successDetector = new SuccessDetector(options.success);
        this.maxRetries = options.maxRetries || 3;
        this.timeout = options.timeout || 120000; // 2 minutes
        this.verbose = options.verbose !== false;
    }

    /**
     * Execute complete payment flow
     */
    async executePaymentFlow(checkoutUrl, card) {
        try {
            console.log('\n╔════════════════════════════════════════════════════════════╗');
            console.log('║         ADVANCED PAYMENT AUTOMATION FLOW STARTED             ║');
            console.log('╚════════════════════════════════════════════════════════════╝\n');

            const flowResult = {
                success: false,
                stages: {},
                errors: [],
                startTime: Date.now()
            };

            // Stage 1: Initial Payment Attempt
            console.log('[FLOW] Stage 1: Initial Payment Attempt');
            const paymentResult = await this.executePaymentAttempt(checkoutUrl, card);
            flowResult.stages.payment = paymentResult;

            if (!paymentResult.success) {
                flowResult.errors.push('Initial payment attempt failed');
                return flowResult;
            }

            // Stage 2: Check for Captcha
            console.log('[FLOW] Stage 2: Checking for Captcha Challenge');
            const captchaChallenge = this.captchaSolver.parseCaptchaChallenge(paymentResult.response);

            if (captchaChallenge) {
                console.log('[FLOW] Captcha challenge detected, solving...');
                const captchaResult = await this.solveCaptchaChallenge(captchaChallenge);
                flowResult.stages.captcha = captchaResult;

                if (!captchaResult.success) {
                    flowResult.errors.push('Captcha solving failed');
                    return flowResult;
                }
            } else {
                console.log('[FLOW] No captcha challenge detected');
                flowResult.stages.captcha = { success: true, skipped: true };
            }

            // Stage 3: Check for 3DS
            console.log('[FLOW] Stage 3: Checking for 3D Secure Requirement');
            const threeDSChallenge = this.threeDSHandler.extract3DSChallenge(paymentResult.response);

            if (threeDSChallenge) {
                console.log('[FLOW] 3DS challenge detected, processing...');
                const threeDSResult = await this.process3DSChallenge(threeDSChallenge);
                flowResult.stages.threeDS = threeDSResult;

                if (!threeDSResult.success) {
                    flowResult.errors.push('3DS verification failed');
                    return flowResult;
                }
            } else {
                console.log('[FLOW] No 3DS challenge detected');
                flowResult.stages.threeDS = { success: true, skipped: true };
            }

            // Stage 4: Verify Payment Success
            console.log('[FLOW] Stage 4: Verifying Payment Success');
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
            console.log(`║  FLOW COMPLETED: ${flowResult.success ? '✅ SUCCESS' : '❌ FAILED'}                                   ║`);
            console.log(`║  Duration: ${flowResult.duration}ms                                        ║`);
            console.log('╚════════════════════════════════════════════════════════════╝\n');

            return flowResult;
        } catch (err) {
            console.error('[FLOW] Fatal error:', err.message);
            return {
                success: false,
                error: err.message,
                duration: Date.now() - flowResult.startTime
            };
        }
    }

    /**
     * Execute payment attempt with retries
     */
    async executePaymentAttempt(checkoutUrl, card, attempt = 1) {
        try {
            console.log(`[FLOW] Payment attempt ${attempt}/${this.maxRetries + 1}`);

            const result = await attemptPayment({
                checkoutUrl,
                card,
                retries: 0
            });

            return {
                success: true,
                attempt: attempt,
                response: result,
                timestamp: Date.now()
            };
        } catch (err) {
            console.error(`[FLOW] Payment attempt ${attempt} failed:`, err.message);

            if (attempt < this.maxRetries) {
                console.log(`[FLOW] Retrying in 2 seconds...`);
                await this.delay(2000);
                return this.executePaymentAttempt(checkoutUrl, card, attempt + 1);
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
     * Solve captcha challenge
     */
    async solveCaptchaChallenge(challenge) {
        try {
            console.log('[FLOW] Solving captcha with fallback methods...');

            const solveResult = await this.captchaSolver.solve(challenge);

            if (!solveResult.success) {
                throw new Error(solveResult.error || 'Captcha solving failed');
            }

            // Verify solution
            const verifyResult = await this.captchaSolver.verifySolution(
                solveResult.token,
                challenge
            );

            return {
                success: verifyResult.success,
                method: solveResult.method,
                token: solveResult.token,
                verified: verifyResult.success,
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

            // Create success report
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
     * Create flow report
     */
    createFlowReport(flowResult) {
        return {
            timestamp: new Date().toISOString(),
            success: flowResult.success,
            duration: flowResult.duration,
            stages: {
                payment: flowResult.stages.payment?.success || false,
                captcha: flowResult.stages.captcha?.success || flowResult.stages.captcha?.skipped || false,
                threeDS: flowResult.stages.threeDS?.success || flowResult.stages.threeDS?.skipped || false,
                success: flowResult.stages.success?.success || false
            },
            errors: flowResult.errors,
            details: flowResult.stages
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
            errorCount: flowResult.errors.length
        };
    }
}

module.exports = {
    AdvancedPaymentFlow
};
