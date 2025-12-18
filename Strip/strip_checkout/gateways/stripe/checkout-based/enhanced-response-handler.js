/**
 * Enhanced Response Handler - Properly detects card approval/decline status
 * Fixes issue where declined cards were being reported as approved
 */

const DECLINE_CODES = {
    'card_declined': 'Card was declined by the issuer',
    'insufficient_funds': 'Insufficient funds on the card',
    'lost_card': 'The card has been reported as lost',
    'stolen_card': 'The card has been reported as stolen',
    'expired_card': 'The card has expired',
    'incorrect_cvc': 'The CVC code is incorrect',
    'processing_error': 'An error occurred while processing the card',
    'rate_limit': 'Too many attempts, please try again later',
    'authentication_required': 'Authentication is required for this card',
    'card_velocity_exceeded': 'Card has exceeded velocity limits',
    'duplicate_transaction': 'This appears to be a duplicate transaction',
    'fraudulent': 'The card has been flagged as fraudulent',
    'generic_decline': 'The card was declined for an unspecified reason',
    'not_permitted': 'The card is not permitted for this transaction',
    'pickup_card': 'The card must be picked up',
    'restricted_card': 'The card is restricted',
    'revocation_of_all_authorizations': 'All authorizations have been revoked',
    'revocation_of_authorization': 'Authorization has been revoked',
    'security_violation': 'Security violation detected',
    'service_not_allowed': 'Service not allowed on this card',
    'transaction_not_allowed': 'Transaction not allowed on this card',
    'try_again_later': 'Please try again later',
    'withdrawal_count_limit_exceeded': 'Withdrawal limit exceeded'
};

/**
 * Detect if payment response indicates a card decline
 */
function detectCardDecline(response) {
    if (!response) return false;

    // Check for explicit decline status
    if (response.status === 'declined' || response.status === 'failed') {
        return true;
    }

    // Check payment intent status
    if (response.payment_intent) {
        const pi = response.payment_intent;
        
        // requires_payment_method means previous payment method was declined
        if (pi.status === 'requires_payment_method') {
            return true;
        }

        // Check for last payment error
        if (pi.last_payment_error) {
            return true;
        }

        // Check for declined status
        if (pi.status === 'declined') {
            return true;
        }
    }

    // Check for error object
    if (response.error) {
        const error = response.error;
        
        // Card error types
        if (error.type === 'card_error') {
            return true;
        }

        // Specific decline codes
        if (error.code && error.code.includes('declined')) {
            return true;
        }

        // Check decline_code field
        if (error.decline_code) {
            return true;
        }

        // Check message for decline keywords
        if (error.message && error.message.toLowerCase().includes('decline')) {
            return true;
        }
    }

    // Check charges for declined status
    if (response.charges && response.charges.data && response.charges.data.length > 0) {
        const charge = response.charges.data[0];
        if (charge.status === 'failed' || charge.declined) {
            return true;
        }
    }

    return false;
}

/**
 * Detect if payment response indicates approval
 */
function detectCardApproval(response) {
    if (!response) return false;

    // Check for explicit success status
    if (response.status === 'succeeded' || response.status === 'complete') {
        return true;
    }

    // Check payment intent status
    if (response.payment_intent) {
        const pi = response.payment_intent;
        
        if (pi.status === 'succeeded' || pi.status === 'processing') {
            return true;
        }
    }

    // Check charges for succeeded status
    if (response.charges && response.charges.data && response.charges.data.length > 0) {
        const charge = response.charges.data[0];
        if (charge.status === 'succeeded' && charge.paid === true) {
            return true;
        }
    }

    // Check for no errors
    if (!response.error && !detectCardDecline(response)) {
        return true;
    }

    return false;
}

/**
 * Detect if payment requires 3DS
 */
function detectThreeDSRequired(response) {
    if (!response) return false;

    if (response.requires3DS === true) {
        return true;
    }

    if (response.payment_intent) {
        const pi = response.payment_intent;
        
        if (pi.status === 'requires_action' && pi.next_action) {
            return true;
        }
    }

    return false;
}

/**
 * Extract decline reason from response
 */
function extractDeclineReason(response) {
    if (!response) return 'Unknown decline reason';

    // Check error object
    if (response.error) {
        const error = response.error;
        
        if (error.message) {
            return error.message;
        }

        if (error.decline_code && DECLINE_CODES[error.decline_code]) {
            return DECLINE_CODES[error.decline_code];
        }

        if (error.code) {
            return `Card error: ${error.code}`;
        }
    }

    // Check payment intent error
    if (response.payment_intent && response.payment_intent.last_payment_error) {
        const error = response.payment_intent.last_payment_error;
        
        if (error.message) {
            return error.message;
        }

        if (error.decline_code && DECLINE_CODES[error.decline_code]) {
            return DECLINE_CODES[error.decline_code];
        }
    }

    // Check charges for error
    if (response.charges && response.charges.data && response.charges.data.length > 0) {
        const charge = response.charges.data[0];
        
        if (charge.failure_message) {
            return charge.failure_message;
        }

        if (charge.failure_code) {
            return `Charge failed: ${charge.failure_code}`;
        }
    }

    return 'Card was declined';
}

/**
 * Extract decline code from response
 */
function extractDeclineCode(response) {
    if (!response) return 'generic_decline';

    // Check error object
    if (response.error && response.error.decline_code) {
        return response.error.decline_code;
    }

    // Check payment intent error
    if (response.payment_intent && response.payment_intent.last_payment_error) {
        if (response.payment_intent.last_payment_error.decline_code) {
            return response.payment_intent.last_payment_error.decline_code;
        }
    }

    // Check charges
    if (response.charges && response.charges.data && response.charges.data.length > 0) {
        const charge = response.charges.data[0];
        
        if (charge.failure_code) {
            return charge.failure_code;
        }
    }

    return 'generic_decline';
}

/**
 * Create detailed response with proper decline/approval detection
 */
function createDetailedResponse(result) {
    const response = {
        success: result.success || false,
        status: result.status || (result.success ? 'approved' : 'declined'),
        attempts: result.attempts || 1,
        timestamp: new Date().toISOString()
    };

    // If we have confirmation data, analyze it
    if (result.confirmation) {
        const isDeclined = detectCardDecline(result.confirmation);
        const isApproved = detectCardApproval(result.confirmation);
        const requires3DS = detectThreeDSRequired(result.confirmation);

        // Override success based on actual response
        if (isDeclined) {
            response.success = false;
            response.status = 'declined';
            response.error = {
                code: extractDeclineCode(result.confirmation),
                message: extractDeclineReason(result.confirmation),
                type: 'card_error'
            };
        } else if (requires3DS) {
            response.success = true;
            response.status = 'requires_action';
            response.requires3DS = true;
        } else if (isApproved) {
            response.success = true;
            response.status = 'approved';
        }
    }

    // Add error if present
    if (result.error) {
        response.error = result.error;
    }

    // Add card info if present
    if (result.card) {
        response.card = {
            last4: result.card.cardNumber ? result.card.cardNumber.slice(-4) : 'N/A',
            expiration: result.card.expMonth + '/' + result.card.expYear
        };
    }

    // Add payment method if present
    if (result.paymentMethod) {
        response.payment_method = {
            id: result.paymentMethod.id,
            type: result.paymentMethod.type || 'card'
        };
    }

    return response;
}

/**
 * Format payment response for API
 */
function formatPaymentResponse(result) {
    const response = createDetailedResponse(result);

    return {
        success: response.success,
        status: response.status,
        message: response.status === 'approved' 
            ? 'Payment approved successfully'
            : response.status === 'declined'
            ? `Payment declined: ${response.error?.message || 'Card was declined'}`
            : response.status === 'requires_action'
            ? 'Payment requires 3D Secure verification'
            : 'Payment processing',
        card: response.card,
        error: response.error,
        timestamp: response.timestamp,
        attempts: response.attempts
    };
}

/**
 * Check if payment is approved
 */
function isPaymentApproved(response) {
    return response && response.success === true && response.status === 'approved';
}

/**
 * Check if payment is declined
 */
function isPaymentDeclined(response) {
    return response && response.success === false && response.status === 'declined';
}

/**
 * Check if payment is pending
 */
function isPaymentPending(response) {
    return response && response.status === 'processing' || response.status === 'pending';
}

module.exports = {
    detectCardDecline,
    detectCardApproval,
    detectThreeDSRequired,
    extractDeclineReason,
    extractDeclineCode,
    createDetailedResponse,
    formatPaymentResponse,
    isPaymentApproved,
    isPaymentDeclined,
    isPaymentPending,
    DECLINE_CODES
};
