#!/usr/bin/env node

const { parseCheckoutUrl, fetchCheckoutInfo } = require('./gateways/stripe/checkout-based/checkout-info');
const { attemptPayment, parseCardString } = require('./gateways/stripe/checkout-based/payer');
const { 
    detectCardDecline, 
    detectCardApproval,
    extractDeclineReason,
    extractDeclineCode
} = require('./gateways/stripe/checkout-based/enhanced-response-handler');

async function quickPay(checkoutUrl, cardString) {
    try {
        console.log('\n╔════════════════════════════════════════╗');
        console.log('║    QUICK PAYMENT TEST                  ║');
        console.log('╚════════════════════════════════════════╝\n');

        // Step 1: Parse checkout URL
        console.log('[ 1/4] Parsing checkout URL...');
        const parsed = parseCheckoutUrl(checkoutUrl);
        
        if (!parsed.sessionId || !parsed.publicKey) {
            throw new Error('Failed to extract session ID or public key from checkout URL');
        }
        
        console.log('       Session: ' + parsed.sessionId);
        console.log('       PubKey:  ' + parsed.publicKey.substring(0, 20) + '...\n');

        // Step 2: Parse card data
        console.log('[2/4] Parsing card data...');
        const card = parseCardString(cardString);
        console.log('       Card:   ****' + card.cardNumber.slice(-4));
        console.log('       Expiry: ' + card.expMonth + '/' + card.expYear);
        console.log('       CVV:    ***\n');

        // Step 3: Fetch checkout info
        console.log('[3/4] Fetching checkout info...');
        try {
            const checkoutInfo = await fetchCheckoutInfo({
                sessionId: parsed.sessionId,
                publicKey: parsed.publicKey
            });
            
            console.log('       ✅ Checkout info retrieved');
            console.log('       Amount: $' + (checkoutInfo.totals.total / 100).toFixed(2));
            console.log('       Currency: ' + checkoutInfo.currency + '\n');
        } catch (err) {
            console.log('       ⚠️ Warning: Could not fetch checkout info');
            console.log('       Reason: ' + err.message);
            console.log('       Continuing with payment attempt...\n');
        }

        // Step 4: Attempt payment
        console.log('[4/4] Processing payment...\n');
        
        const result = await attemptPayment({
            checkoutUrl,
            card
        });

        // Display results
        console.log('╔════════════════════════════════════════╗');
        console.log('║         PAYMENT RESULT                 ║');
        console.log('╚════════════════════════════════════════╝\n');

        if (result.success && result.status === 'approved') {
            console.log('🎉 PAYMENT APPROVED\n');
            console.log('Card: ' + card.cardNumber);
            console.log('Status: APPROVED');
            console.log('Attempts: ' + result.attempts);
        } else if (!result.success && result.status === 'declined') {
            console.log('❌ PAYMENT DECLINED\n');
            console.log('Card: ' + card.cardNumber);
            console.log('Status: DECLINED');
            console.log('Reason: ' + (result.error?.message || 'Card was declined'));
            console.log('Code: ' + (result.error?.code || 'unknown'));
            console.log('Attempts: ' + result.attempts);
        } else if (result.status === 'requires_action') {
            console.log('⚠️ PAYMENT REQUIRES 3DS\n');
            console.log('Card: ' + card.cardNumber);
            console.log('Status: REQUIRES 3D SECURE');
            console.log('Next Action: Complete 3DS verification');
        } else {
            console.log('⚠️ PAYMENT STATUS: ' + result.status + '\n');
            console.log('Card: ' + card.cardNumber);
            console.log('Status: ' + result.status);
        }

        console.log('\n╔════════════════════════════════════════╗');
        console.log('║         FULL RESPONSE                  ║');
        console.log('╚════════════════════════════════════════╝\n');
        console.log(JSON.stringify(result, null, 2));

    } catch (err) {
        console.error('\n❌ ERROR: ' + err.message);
        
        if (err.stack) {
            console.error('\nStack Trace:');
            console.error(err.stack);
        }
        
        process.exit(1);
    }
}

// Get command line arguments
const args = process.argv.slice(2);

if (args.length < 2) {
    console.log('Usage: node quick-pay.js <checkout-url> <card-string>');
    console.log('\nExample:');
    console.log('  node quick-pay.js "https://checkout.stripe.com/c/pay/cs_live_..." "4242424242424242|12|28|123"');
    process.exit(1);
}

const checkoutUrl = args[0];
const cardString = args[1];

quickPay(checkoutUrl, cardString).catch(err => {
    console.error('Fatal error:', err);
    process.exit(1);
});
