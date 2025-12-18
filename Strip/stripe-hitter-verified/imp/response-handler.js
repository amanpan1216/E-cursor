/**
 * Payment Response Handler
 * Processes and formats Stripe payment responses with detailed status information
 */

const PaymentStatus = {
    APPROVED: 'approved',
    DECLINED: 'declined',
    FAILED: 'failed',
    PENDING: 'pending',
    REQUIRES_ACTION: 'requires_action',
    PROCESSING: 'processing',
    SUCCEEDED: 'succeeded',
    REQUIRES_PAYMENT_METHOD: 'requires_payment_method',
    CANCELED: 'canceled'
};

const DeclineReasons = {
    'card_declined': 'Card was declined by the issuer',
    'expired_card': 'Card has expired',
    'incorrect_cvc': 'Incorrect CVC provided',
    'processing_error': 'Processing error occurred',
    'rate_limit': 'Rate limit exceeded',
    'lost_card': 'Card reported as lost',
    'stolen_card': 'Card reported as stolen',
    'insufficient_funds': 'Insufficient funds',
    'do_not_honor': 'Card issuer declined the transaction',
    'generic_decline': 'Card declined for unknown reason',
    'checkout_amount_mismatch': 'Amount mismatch with checkout session',
    'invalid_account': 'Invalid account',
    'invalid_amount': 'Invalid amount',
    'invalid_currency': 'Invalid currency'
};

function getDeclineReason(errorCode) {
    return DeclineReasons[errorCode] || 'Unknown decline reason';
}

function parsePaymentIntentStatus(status) {
    const statusMap = {
        'succeeded': PaymentStatus.APPROVED,
        'processing': PaymentStatus.PROCESSING,
        'requires_payment_method': PaymentStatus.REQUIRES_PAYMENT_METHOD,
        'requires_action': PaymentStatus.REQUIRES_ACTION,
        'requires_capture': PaymentStatus.PENDING,
        'canceled': PaymentStatus.CANCELED
    };
    return statusMap[status] || PaymentStatus.FAILED;
}

function formatPaymentResponse(response, statusCode) {
    const result = {
        timestamp: new Date().toISOString(),
        statusCode: statusCode || 200,
        success: false,
        status: PaymentStatus.FAILED,
        message: 'Payment processing failed',
        details: {}
    };

    // Handle error responses
    if (response.error) {
        const error = response.error;
        result.success = false;
        result.status = PaymentStatus.DECLINED;
        result.message = error.message || 'Payment declined';
        result.errorCode = error.code;
        result.errorType = error.type;
        result.declineReason = getDeclineReason(error.code);
        result.details = {
            code: error.code,
            message: error.message,
            type: error.type,
            param: error.param,
            chargeId: error.charge
        };
        return result;
    }

    // Handle payment intent responses
    if (response.payment_intent) {
        const pi = response.payment_intent;
        result.paymentIntentId = pi.id;
        result.amount = pi.amount;
        result.currency = pi.currency;
        result.status = parsePaymentIntentStatus(pi.status);
        
        if (pi.status === 'succeeded') {
            result.success = true;
            result.status = PaymentStatus.APPROVED;
            result.message = 'Payment approved and processed successfully';
            result.details = {
                paymentIntentId: pi.id,
                amount: pi.amount,
                currency: pi.currency,
                status: pi.status,
                created: pi.created,
                chargeId: pi.charges?.data?.[0]?.id,
                receiptEmail: pi.receipt_email
            };
        } else if (pi.status === 'processing') {
            result.success = false;
            result.status = PaymentStatus.PROCESSING;
            result.message = 'Payment is being processed';
            result.details = {
                paymentIntentId: pi.id,
                amount: pi.amount,
                currency: pi.currency,
                status: pi.status
            };
        } else if (pi.status === 'requires_action') {
            result.success = false;
            result.status = PaymentStatus.REQUIRES_ACTION;
            result.message = 'Payment requires additional action (3D Secure or similar)';
            result.requires3DS = true;
            result.details = {
                paymentIntentId: pi.id,
                nextAction: pi.next_action?.type,
                redirectUrl: pi.next_action?.redirect_to_url?.url
            };
        } else if (pi.status === 'requires_payment_method') {
            result.success = false;
            result.status = PaymentStatus.REQUIRES_PAYMENT_METHOD;
            result.message = 'Payment method required';
            result.details = {
                paymentIntentId: pi.id,
                amount: pi.amount,
                currency: pi.currency
            };
        } else if (pi.status === 'canceled') {
            result.success = false;
            result.status = PaymentStatus.CANCELED;
            result.message = 'Payment was canceled';
            result.details = {
                paymentIntentId: pi.id,
                cancellationReason: pi.cancellation_reason
            };
        }
        return result;
    }

    // Handle checkout session responses
    if (response.status === 'complete') {
        result.success = true;
        result.status = PaymentStatus.APPROVED;
        result.message = 'Checkout completed successfully';
        result.details = {
            sessionId: response.id,
            status: response.status,
            paymentStatus: response.payment_status,
            paymentIntentId: response.payment_intent
        };
        return result;
    }

    // Handle generic error responses
    if (response.message) {
        result.success = false;
        result.status = PaymentStatus.FAILED;
        result.message = response.message;
        result.details = response;
        return result;
    }

    return result;
}

function formatBatchResponse(responses) {
    const summary = {
        timestamp: new Date().toISOString(),
        totalAttempts: responses.length,
        approved: 0,
        declined: 0,
        failed: 0,
        pending: 0,
        results: []
    };

    responses.forEach((response, index) => {
        const formatted = formatPaymentResponse(response.data, response.statusCode);
        summary.results.push({
            attemptNumber: index + 1,
            ...formatted
        });

        // Count statuses
        switch (formatted.status) {
            case PaymentStatus.APPROVED:
            case PaymentStatus.SUCCEEDED:
                summary.approved++;
                break;
            case PaymentStatus.DECLINED:
                summary.declined++;
                break;
            case PaymentStatus.PROCESSING:
            case PaymentStatus.PENDING:
                summary.pending++;
                break;
            default:
                summary.failed++;
        }
    });

    return summary;
}

function createDetailedResponse(paymentResult) {
    const response = {
        timestamp: new Date().toISOString(),
        success: paymentResult.success,
        status: PaymentStatus.FAILED,
        message: 'Payment processing failed',
        card: {
            number: paymentResult.card?.cardNumber?.slice(-4) || 'XXXX',
            expiration: `${paymentResult.card?.expMonth}/${paymentResult.card?.expYear}`,
            type: getCardType(paymentResult.card?.cardNumber)
        },
        attempts: paymentResult.attempts || 0,
        details: {}
    };

    if (paymentResult.success) {
        response.status = PaymentStatus.APPROVED;
        response.message = 'Payment approved successfully';
        response.details = {
            paymentMethodId: paymentResult.paymentMethod?.id,
            paymentIntentId: paymentResult.paymentIntent?.id,
            amount: paymentResult.paymentIntent?.amount,
            currency: paymentResult.paymentIntent?.currency,
            requires3DS: paymentResult.requires3DS || false,
            confirmation: paymentResult.confirmation
        };
    } else if (paymentResult.error) {
        const error = paymentResult.error;
        response.status = PaymentStatus.DECLINED;
        response.message = error.message || 'Payment declined';
        response.errorCode = error.code;
        response.declineReason = getDeclineReason(error.code);
        response.details = {
            code: error.code,
            type: error.type,
            message: error.message,
            param: error.param
        };
    }

    return response;
}

function getCardType(cardNumber) {
    if (!cardNumber) return 'Unknown';
    
    const patterns = {
        'Visa': /^4[0-9]{12}(?:[0-9]{3})?$/,
        'Mastercard': /^5[1-5][0-9]{14}$/,
        'AmEx': /^3[47][0-9]{13}$/,
        'Discover': /^6(?:011|5[0-9]{2})[0-9]{12}$/,
        'Diners': /^3(?:0[0-5]|[68][0-9])[0-9]{11}$/,
        'JCB': /^(?:2131|1800|35\d{3})\d{11}$/
    };

    for (const [type, pattern] of Object.entries(patterns)) {
        if (pattern.test(cardNumber)) {
            return type;
        }
    }
    return 'Unknown';
}

function isPaymentApproved(response) {
    if (!response) return false;
    return response.status === PaymentStatus.APPROVED || 
           response.status === PaymentStatus.SUCCEEDED ||
           (response.payment_intent?.status === 'succeeded');
}

function isPaymentDeclined(response) {
    if (!response) return false;
    return response.status === PaymentStatus.DECLINED ||
           response.error?.code === 'card_declined' ||
           (response.error && !isPaymentApproved(response));
}

function isPaymentPending(response) {
    if (!response) return false;
    return response.status === PaymentStatus.PROCESSING ||
           response.status === PaymentStatus.PENDING ||
           response.status === PaymentStatus.REQUIRES_ACTION ||
           response.payment_intent?.status === 'processing' ||
           response.payment_intent?.status === 'requires_action';
}

module.exports = {
    PaymentStatus,
    DeclineReasons,
    formatPaymentResponse,
    formatBatchResponse,
    createDetailedResponse,
    getCardType,
    getDeclineReason,
    parsePaymentIntentStatus,
    isPaymentApproved,
    isPaymentDeclined,
    isPaymentPending
};
