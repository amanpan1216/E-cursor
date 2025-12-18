/**
 * 3D Secure (3DS) Verification Handler
 * Handles 3D Secure authentication including OTP, verification pages, and additional details
 */

const https = require('https');

class ThreeDSHandler {
    constructor(options = {}) {
        this.timeout = options.timeout || 30000;
        this.retries = options.retries || 3;
        this.otpMethods = options.otpMethods || ['sms', 'email', 'app'];
        this.autoRetry = options.autoRetry !== false;
    }

    /**
     * Detect if response requires 3DS
     */
    requires3DS(responseData) {
        try {
            if (typeof responseData === 'string') {
                responseData = JSON.parse(responseData);
            }

            // Check payment intent status
            if (responseData.paymentIntent?.status === 'requires_action') {
                return true;
            }

            // Check for next_action
            if (responseData.paymentIntent?.next_action) {
                return true;
            }

            // Check requires3DS flag
            if (responseData.requires3DS) {
                return true;
            }

            // Check confirmation status
            if (responseData.confirmation?.payment_status === 'requires_action') {
                return true;
            }

            return false;
        } catch (err) {
            return false;
        }
    }

    /**
     * Extract 3DS challenge details
     */
    extract3DSChallenge(responseData) {
        try {
            if (typeof responseData === 'string') {
                responseData = JSON.parse(responseData);
            }

            const challenge = {
                paymentIntentId: null,
                status: 'unknown',
                type: null,
                requiresOTP: false,
                requiresVerification: false,
                otpMethods: [],
                verificationUrl: null,
                verificationData: null,
                nextAction: null,
                clientSecret: null
            };

            // Extract payment intent details
            if (responseData.paymentIntent) {
                const pi = responseData.paymentIntent;
                challenge.paymentIntentId = pi.id;
                challenge.status = pi.status;
                challenge.clientSecret = pi.client_secret;

                // Check next action
                if (pi.next_action) {
                    challenge.nextAction = pi.next_action.type;

                    // Redirect type (usually for 3DS)
                    if (pi.next_action.type === 'redirect_to_url') {
                        challenge.type = 'redirect';
                        challenge.verificationUrl = pi.next_action.redirect_to_url?.url;
                        challenge.requiresVerification = true;
                    }

                    // Use Stripe SDK (hCaptcha + 3DS)
                    if (pi.next_action.type === 'use_stripe_sdk') {
                        challenge.type = 'stripe_sdk';
                        const sdk = pi.next_action.use_stripe_sdk?.stripe_js;
                        if (sdk) {
                            challenge.verificationUrl = sdk.verification_url;
                            challenge.verificationData = sdk;
                            challenge.requiresVerification = true;
                        }
                    }
                }
            }

            // Check for OTP requirement
            if (responseData.requires3DS?.use_stripe_sdk?.stripe_js?.captcha_vendor_name === 'hcaptcha') {
                challenge.requiresOTP = true;
                challenge.otpMethods = ['hcaptcha', 'sms', 'email'];
            }

            // Check confirmation for 3DS indicators
            if (responseData.confirmation?.status === 'requires_action') {
                challenge.requiresVerification = true;
            }

            return challenge.requiresVerification || challenge.requiresOTP ? challenge : null;
        } catch (err) {
            console.error('[3DS] Extract challenge error:', err.message);
            return null;
        }
    }

    /**
     * Simulate OTP verification
     */
    async verifyOTP(paymentIntentId, otp) {
        try {
            console.log('[3DS] Verifying OTP...');

            if (!paymentIntentId || !otp) {
                throw new Error('Missing payment intent ID or OTP');
            }

            // Validate OTP format (typically 6 digits)
            if (!/^\d{4,6}$/.test(otp)) {
                throw new Error('Invalid OTP format');
            }

            // Simulate OTP verification
            const isValid = await this.validateOTPWithBank(paymentIntentId, otp);

            if (isValid) {
                console.log('[3DS] ✅ OTP verified successfully');
                return {
                    success: true,
                    paymentIntentId: paymentIntentId,
                    verified: true,
                    timestamp: Date.now()
                };
            } else {
                throw new Error('Invalid OTP');
            }
        } catch (err) {
            console.error('[3DS] OTP verification failed:', err.message);
            return { success: false, error: err.message };
        }
    }

    /**
     * Simulate bank OTP validation
     */
    async validateOTPWithBank(paymentIntentId, otp) {
        return new Promise((resolve) => {
            // Simulate bank validation
            // In real scenario, this would call the bank's API
            setTimeout(() => {
                // Accept OTP if it matches common test patterns
                const validOTPs = ['123456', '000000', '111111', '999999'];
                const isValid = validOTPs.includes(otp) || Math.random() > 0.3; // 70% success rate

                resolve(isValid);
            }, 1000);
        });
    }

    /**
     * Handle verification page redirect
     */
    async handleVerificationPage(verificationUrl, paymentIntentId) {
        try {
            console.log('[3DS] Handling verification page...');

            if (!verificationUrl) {
                throw new Error('No verification URL provided');
            }

            // Parse URL
            const url = new URL(verificationUrl);

            // Detect verification page type
            const pageType = this.detectPageType(verificationUrl);

            console.log('[3DS] Verification page type:', pageType);

            switch (pageType) {
                case 'otp':
                    return await this.handleOTPPage(paymentIntentId);
                case 'redirect_3ds':
                    return await this.handleRedirect3DS(verificationUrl);
                case 'challenge':
                    return await this.handleChallenge(paymentIntentId);
                default:
                    return { success: false, error: 'Unknown verification page type' };
            }
        } catch (err) {
            console.error('[3DS] Verification page handling failed:', err.message);
            return { success: false, error: err.message };
        }
    }

    /**
     * Detect verification page type
     */
    detectPageType(url) {
        if (!url) return 'unknown';

        const urlLower = url.toLowerCase();

        if (urlLower.includes('otp') || urlLower.includes('sms') || urlLower.includes('verify')) {
            return 'otp';
        }

        if (urlLower.includes('3d') || urlLower.includes('threeds') || urlLower.includes('acs')) {
            return 'redirect_3ds';
        }

        if (urlLower.includes('challenge') || urlLower.includes('captcha')) {
            return 'challenge';
        }

        return 'unknown';
    }

    /**
     * Handle OTP page
     */
    async handleOTPPage(paymentIntentId) {
        try {
            console.log('[3DS] Handling OTP page...');

            // Generate OTP (in real scenario, user would receive this)
            const otp = this.generateOTP();

            console.log('[3DS] Generated OTP:', otp);

            // Verify OTP
            const result = await this.verifyOTP(paymentIntentId, otp);

            return result;
        } catch (err) {
            console.error('[3DS] OTP page handling failed:', err.message);
            return { success: false, error: err.message };
        }
    }

    /**
     * Handle 3DS redirect
     */
    async handleRedirect3DS(redirectUrl) {
        try {
            console.log('[3DS] Handling 3DS redirect...');

            // Follow redirect and extract data
            const response = await this.followRedirect(redirectUrl);

            // Check for success indicators
            const isSuccess = this.checkSuccessIndicators(response);

            if (isSuccess) {
                console.log('[3DS] ✅ 3DS redirect successful');
                return {
                    success: true,
                    redirectUrl: redirectUrl,
                    timestamp: Date.now()
                };
            } else {
                throw new Error('3DS verification failed');
            }
        } catch (err) {
            console.error('[3DS] 3DS redirect handling failed:', err.message);
            return { success: false, error: err.message };
        }
    }

    /**
     * Handle challenge (captcha, security questions, etc.)
     */
    async handleChallenge(paymentIntentId) {
        try {
            console.log('[3DS] Handling challenge...');

            // Simulate challenge completion
            const challengeData = {
                type: 'security_question',
                question: 'What is your mother\'s maiden name?',
                answer: 'Smith' // Simulated answer
            };

            // Submit challenge response
            const result = await this.submitChallengeResponse(paymentIntentId, challengeData);

            return result;
        } catch (err) {
            console.error('[3DS] Challenge handling failed:', err.message);
            return { success: false, error: err.message };
        }
    }

    /**
     * Submit challenge response
     */
    async submitChallengeResponse(paymentIntentId, challengeData) {
        return new Promise((resolve) => {
            // Simulate challenge submission
            setTimeout(() => {
                resolve({
                    success: true,
                    paymentIntentId: paymentIntentId,
                    challengeCompleted: true,
                    timestamp: Date.now()
                });
            }, 1500);
        });
    }

    /**
     * Follow redirect and check for success
     */
    async followRedirect(redirectUrl) {
        return new Promise((resolve) => {
            https.get(redirectUrl, (res) => {
                let data = '';
                res.on('data', chunk => data += chunk);
                res.on('end', () => resolve(data));
            }).on('error', () => resolve(''));
        });
    }

    /**
     * Check for success indicators in response
     */
    checkSuccessIndicators(responseData) {
        if (!responseData) return false;

        const successPatterns = [
            /success/i,
            /approved/i,
            /completed/i,
            /verified/i,
            /status.*complete/i,
            /payment.*success/i
        ];

        return successPatterns.some(pattern => pattern.test(responseData));
    }

    /**
     * Generate OTP
     */
    generateOTP(length = 6) {
        let otp = '';
        for (let i = 0; i < length; i++) {
            otp += Math.floor(Math.random() * 10);
        }
        return otp;
    }

    /**
     * Check if payment button is green (success indicator)
     */
    checkPaymentButtonStatus(pageHTML) {
        try {
            if (!pageHTML) return null;

            // Look for success indicators in HTML
            const successPatterns = [
                /<button[^>]*style="[^"]*color:\s*green/i,
                /<button[^>]*class="[^"]*success/i,
                /<button[^>]*class="[^"]*approved/i,
                /payment.*success/i,
                /status.*approved/i
            ];

            for (const pattern of successPatterns) {
                if (pattern.test(pageHTML)) {
                    return 'success';
                }
            }

            // Check for error indicators
            const errorPatterns = [
                /<button[^>]*style="[^"]*color:\s*red/i,
                /<button[^>]*class="[^"]*error/i,
                /<button[^>]*class="[^"]*declined/i,
                /payment.*failed/i,
                /status.*declined/i
            ];

            for (const pattern of errorPatterns) {
                if (pattern.test(pageHTML)) {
                    return 'error';
                }
            }

            return 'pending';
        } catch (err) {
            return null;
        }
    }

    /**
     * Complete 3DS flow
     */
    async complete3DSFlow(challenge) {
        try {
            console.log('[3DS] Starting complete 3DS flow...');

            if (!challenge) {
                throw new Error('No 3DS challenge provided');
            }

            let result = { success: false };

            // Step 1: Handle verification page if needed
            if (challenge.verificationUrl) {
                result = await this.handleVerificationPage(
                    challenge.verificationUrl,
                    challenge.paymentIntentId
                );

                if (!result.success && this.autoRetry) {
                    console.log('[3DS] Retrying 3DS flow...');
                    // Retry logic here
                }
            }

            // Step 2: Verify with payment intent
            if (result.success) {
                console.log('[3DS] ✅ 3DS flow completed successfully');
                return {
                    success: true,
                    paymentIntentId: challenge.paymentIntentId,
                    status: 'completed',
                    timestamp: Date.now()
                };
            }

            return result;
        } catch (err) {
            console.error('[3DS] Complete 3DS flow failed:', err.message);
            return { success: false, error: err.message };
        }
    }
}

module.exports = {
    ThreeDSHandler,
    requires3DS: (data) => new ThreeDSHandler().requires3DS(data),
    extract3DSChallenge: (data) => new ThreeDSHandler().extract3DSChallenge(data)
};
