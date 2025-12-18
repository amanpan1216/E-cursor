/**
 * Payment Success Detector
 * Detects payment success indicators including green button, status changes, and page elements
 */

class SuccessDetector {
    constructor(options = {}) {
        this.timeout = options.timeout || 30000;
        this.pollInterval = options.pollInterval || 1000;
        this.maxAttempts = options.maxAttempts || 30;
    }

    /**
     * Check if payment is successful
     */
    isPaymentSuccess(responseData) {
        try {
            if (typeof responseData === 'string') {
                responseData = JSON.parse(responseData);
            }

            // Direct success indicators
            if (responseData.success === true) {
                return true;
            }

            // Payment intent succeeded
            if (responseData.paymentIntent?.status === 'succeeded') {
                return true;
            }

            // Confirmation completed
            if (responseData.confirmation?.status === 'complete') {
                return true;
            }

            // Payment status indicators
            if (responseData.status === 'approved' || responseData.status === 'succeeded') {
                return true;
            }

            // Checkout session completed
            if (responseData.status === 'complete') {
                return true;
            }

            return false;
        } catch (err) {
            return false;
        }
    }

    /**
     * Detect green button (Stripe success indicator)
     */
    detectGreenButton(pageHTML) {
        try {
            if (!pageHTML || typeof pageHTML !== 'string') {
                return false;
            }

            // Patterns for green button in Stripe checkout
            const greenButtonPatterns = [
                // Direct style matching
                /button[^>]*style="[^"]*background[^"]*green/i,
                /button[^>]*style="[^"]*color:\s*green/i,
                /button[^>]*style="[^"]*#00[a-f0-9]{4}"/i, // Green hex colors

                // Class-based matching
                /button[^>]*class="[^"]*success[^"]*"/i,
                /button[^>]*class="[^"]*approved[^"]*"/i,
                /button[^>]*class="[^"]*completed[^"]*"/i,
                /button[^>]*class="[^"]*green[^"]*"/i,

                // Stripe-specific patterns
                /stripe.*success/i,
                /payment.*success/i,
                /checkout.*complete/i,

                // SVG checkmark patterns
                /<svg[^>]*class="[^"]*success[^"]*"[^>]*>/i,
                /<svg[^>]*class="[^"]*checkmark[^"]*"[^>]*>/i,

                // Text content patterns
                />Payment Successful</i,
                />Order Confirmed</i,
                />Thank You</i,
                />Transaction Complete</i
            ];

            for (const pattern of greenButtonPatterns) {
                if (pattern.test(pageHTML)) {
                    return true;
                }
            }

            return false;
        } catch (err) {
            return false;
        }
    }

    /**
     * Detect payment success from page content
     */
    detectSuccessFromContent(pageHTML) {
        try {
            if (!pageHTML || typeof pageHTML !== 'string') {
                return null;
            }

            const successIndicators = {
                'payment_successful': [
                    /payment\s+successful/i,
                    /payment\s+completed/i,
                    /payment\s+approved/i,
                    /transaction\s+successful/i,
                    /order\s+confirmed/i
                ],
                'thank_you': [
                    /thank\s+you/i,
                    /thanks\s+for\s+your\s+order/i,
                    /we\s+received\s+your\s+payment/i
                ],
                'confirmation': [
                    /confirmation\s+number/i,
                    /order\s+number/i,
                    /transaction\s+id/i,
                    /reference\s+number/i
                ],
                'success_page': [
                    /success\s+page/i,
                    /success\s+url/i,
                    /redirect.*success/i
                ]
            };

            const detectedIndicators = {};

            for (const [indicator, patterns] of Object.entries(successIndicators)) {
                for (const pattern of patterns) {
                    if (pattern.test(pageHTML)) {
                        detectedIndicators[indicator] = true;
                        break;
                    }
                }
            }

            return Object.keys(detectedIndicators).length > 0 ? detectedIndicators : null;
        } catch (err) {
            return null;
        }
    }

    /**
     * Extract payment confirmation details from page
     */
    extractConfirmationDetails(pageHTML) {
        try {
            if (!pageHTML || typeof pageHTML !== 'string') {
                return null;
            }

            const details = {
                confirmationNumber: null,
                orderNumber: null,
                transactionId: null,
                amount: null,
                currency: null,
                timestamp: null
            };

            // Extract confirmation number
            const confMatch = pageHTML.match(/(?:confirmation|order|reference|transaction)\s+(?:number|id|code):\s*([A-Z0-9\-]+)/i);
            if (confMatch) {
                details.confirmationNumber = confMatch[1];
            }

            // Extract amount
            const amountMatch = pageHTML.match(/(?:amount|total|paid):\s*\$?([\d,]+\.?\d*)/i);
            if (amountMatch) {
                details.amount = amountMatch[1];
            }

            // Extract currency
            const currencyMatch = pageHTML.match(/(?:currency|in)\s+([A-Z]{3})/i);
            if (currencyMatch) {
                details.currency = currencyMatch[1];
            }

            // Extract timestamp
            const timeMatch = pageHTML.match(/(?:date|time|at):\s*(\d{1,2}\/\d{1,2}\/\d{4}[^<]*)/i);
            if (timeMatch) {
                details.timestamp = timeMatch[1];
            }

            return Object.values(details).some(v => v !== null) ? details : null;
        } catch (err) {
            return null;
        }
    }

    /**
     * Poll for payment success
     */
    async pollForSuccess(checkFunction, options = {}) {
        const timeout = options.timeout || this.timeout;
        const pollInterval = options.pollInterval || this.pollInterval;
        const maxAttempts = options.maxAttempts || this.maxAttempts;

        console.log('[SUCCESS] Starting success polling...');

        const startTime = Date.now();
        let attempt = 0;

        return new Promise((resolve) => {
            const pollInterval_id = setInterval(async () => {
                attempt++;

                try {
                    const result = await checkFunction();

                    if (result) {
                        clearInterval(pollInterval_id);
                        console.log(`[SUCCESS] ✅ Payment success detected after ${attempt} attempts`);
                        resolve({
                            success: true,
                            attempts: attempt,
                            duration: Date.now() - startTime,
                            result: result
                        });
                        return;
                    }
                } catch (err) {
                    console.error(`[SUCCESS] Poll attempt ${attempt} error:`, err.message);
                }

                // Check timeout
                if (Date.now() - startTime > timeout) {
                    clearInterval(pollInterval_id);
                    console.log(`[SUCCESS] ❌ Timeout after ${attempt} attempts`);
                    resolve({
                        success: false,
                        attempts: attempt,
                        duration: Date.now() - startTime,
                        error: 'Polling timeout'
                    });
                    return;
                }

                // Check max attempts
                if (attempt >= maxAttempts) {
                    clearInterval(pollInterval_id);
                    console.log(`[SUCCESS] ❌ Max attempts reached (${maxAttempts})`);
                    resolve({
                        success: false,
                        attempts: attempt,
                        duration: Date.now() - startTime,
                        error: 'Max attempts exceeded'
                    });
                }
            }, pollInterval);
        });
    }

    /**
     * Check for payment status change
     */
    async checkStatusChange(previousStatus, checkFunction) {
        try {
            const currentStatus = await checkFunction();

            if (currentStatus && currentStatus !== previousStatus) {
                console.log(`[SUCCESS] Status changed from ${previousStatus} to ${currentStatus}`);
                return {
                    changed: true,
                    previousStatus: previousStatus,
                    currentStatus: currentStatus
                };
            }

            return { changed: false };
        } catch (err) {
            console.error('[SUCCESS] Status check error:', err.message);
            return { changed: false, error: err.message };
        }
    }

    /**
     * Validate payment success
     */
    validatePaymentSuccess(paymentData) {
        try {
            const validations = {
                hasPaymentIntentId: !!paymentData.paymentIntentId,
                hasAmount: !!paymentData.amount,
                hasCurrency: !!paymentData.currency,
                statusIsSucceeded: paymentData.status === 'succeeded' || paymentData.status === 'approved',
                hasConfirmation: !!paymentData.confirmation || !!paymentData.confirmationNumber
            };

            const passedValidations = Object.values(validations).filter(v => v).length;
            const totalValidations = Object.keys(validations).length;

            return {
                isValid: passedValidations >= 3, // At least 3 validations must pass
                validations: validations,
                score: (passedValidations / totalValidations) * 100
            };
        } catch (err) {
            return { isValid: false, error: err.message };
        }
    }

    /**
     * Get success status from multiple sources
     */
    getSuccessStatus(responseData, pageHTML) {
        const results = {
            responseSuccess: this.isPaymentSuccess(responseData),
            greenButton: this.detectGreenButton(pageHTML),
            contentSuccess: this.detectSuccessFromContent(pageHTML),
            confirmationDetails: this.extractConfirmationDetails(pageHTML)
        };

        const successCount = Object.values(results).filter(v => v === true || (v && typeof v === 'object')).length;

        return {
            isSuccessful: successCount >= 2, // At least 2 indicators must confirm success
            indicators: results,
            confidence: (successCount / 4) * 100
        };
    }

    /**
     * Create success report
     */
    createSuccessReport(paymentData, pageData) {
        return {
            timestamp: new Date().toISOString(),
            success: this.isPaymentSuccess(paymentData),
            paymentIntentId: paymentData.paymentIntentId,
            amount: paymentData.amount,
            currency: paymentData.currency,
            status: paymentData.status,
            greenButton: this.detectGreenButton(pageData),
            successIndicators: this.detectSuccessFromContent(pageData),
            confirmationDetails: this.extractConfirmationDetails(pageData),
            validation: this.validatePaymentSuccess(paymentData)
        };
    }
}

module.exports = {
    SuccessDetector,
    isPaymentSuccess: (data) => new SuccessDetector().isPaymentSuccess(data),
    detectGreenButton: (html) => new SuccessDetector().detectGreenButton(html),
    detectSuccessFromContent: (html) => new SuccessDetector().detectSuccessFromContent(html)
};
