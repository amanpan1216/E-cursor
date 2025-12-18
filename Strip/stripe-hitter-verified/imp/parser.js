const { fetchCheckoutInfo, parseCheckoutUrl } = require('./checkout-info');

class StripeCheckoutParser {
    async parseCheckoutUrl(checkoutUrl, options = {}) {
        const parsed = parseCheckoutUrl(checkoutUrl);

        const sessionId = options.sessionId
            || parsed.sessionId
            || options.cs
            || options.checkoutSessionId;

        const publicKey = options.publicKey
            || options.pk
            || parsed.publicKey;

        if (!sessionId) {
            throw new Error('Unable to determine checkout session id');
        }

        if (!publicKey) {
            throw new Error('Unable to determine Stripe publishable key');
        }

        const info = await fetchCheckoutInfo({
            sessionId,
            publicKey,
            locale: options.locale,
            timezone: options.timezone,
            redirectType: options.redirectType,
            fallbackSite: parsed.site
        });

        return this.toLegacyCheckoutData(info);
    }

    toLegacyCheckoutData(info) {
        const firstItem = info.lineItems[0] || {};
        const totals = info.totals || {};
        const subscription = info.subscription || {};

        return {
            sessionId: info.sessionId,
            publicKey: info.publicKey,
            merchantName: info.merchant?.displayName || null,
            merchant: info.merchant || null,
            amount: firstItem.unitAmount ?? firstItem.amount ?? totals.total ?? null,
            subtotal: totals.subtotal ?? null,
            vat: totals.tax ?? null,
            total: totals.total ?? null,
            currency: info.currency || null,
            quantity: firstItem.quantity ?? null,
            productName: firstItem.description || null,
            billingPeriod: subscription.interval
                ? `${subscription.intervalCount || 1} ${subscription.interval}`
                : null,
            email: info.customerEmail || null,
            lineItems: info.lineItems,
            urls: info.urls
        };
    }
}

module.exports = StripeCheckoutParser;
module.exports.StripeCheckoutParser = StripeCheckoutParser;
