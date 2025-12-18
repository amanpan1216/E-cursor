const https = require('https');

const STRIPE_API_HOST = 'api.stripe.com';
const STRIPE_ORIGIN = 'https://checkout.stripe.com';
const DEFAULT_LOCALE = 'en-US';
const DEFAULT_TIMEZONE = 'UTC';
const DEFAULT_REDIRECT_TYPE = 'url';
const MAX_LINE_ITEMS = 10;
const MAX_IMAGES_PER_ITEM = 3;
const XOR_KEY = 5;

class StripeCheckoutInfoError extends Error {
    constructor(message, options = {}) {
        super(message);
        this.name = 'StripeCheckoutInfoError';
        this.statusCode = options.statusCode || null;
        this.details = options.details || null;
        if (options.cause) {
            this.cause = options.cause;
        }
    }
}

function parseCheckoutUrl(checkoutUrl) {
    if (!checkoutUrl || typeof checkoutUrl !== 'string') {
        return { sessionId: null, publicKey: null, site: null };
    }

    try {
        checkoutUrl = decodeURIComponent(checkoutUrl);
    } catch (err) {
        console.warn('[PARSE] Failed to decode checkout URL:', err.message);
    }

    const sessionMatch = checkoutUrl.match(/cs_(?:live|test)_[A-Za-z0-9]+/);
    const sessionId = sessionMatch ? sessionMatch[0] : null;

    let publicKey = null;
    let site = null;

    const fragmentIndex = checkoutUrl.indexOf('#');
    if (fragmentIndex !== -1) {
        const fragment = checkoutUrl.slice(fragmentIndex + 1);
        try {
            const decodedFragment = decodeURIComponent(fragment);
            const base64Buffer = Buffer.from(decodedFragment, 'base64');

            const xorChars = [];
            for (const byte of base64Buffer.values()) {
                xorChars.push(String.fromCharCode(byte ^ XOR_KEY));
            }

            const decodedPayload = xorChars.join('');
            
            // Improved regex to include underscores and more characters
            const pkMatch = decodedPayload.match(/pk_(?:live|test)_[A-Za-z0-9_\-]+/);
            if (pkMatch) {
                publicKey = pkMatch[0];
            }

            const siteMatch = decodedPayload.match(/https?:\/\/[^\s"']+/);
            if (siteMatch) {
                site = siteMatch[0];
            }
        } catch (err) {
            console.warn('[PARSE] Failed to decode fragment:', err.message);
        }
    }

    return { sessionId, publicKey, site };
}

function encodeFormData(payload) {
    const params = new URLSearchParams();
    Object.entries(payload).forEach(([key, value]) => {
        if (value === undefined || value === null) {
            return;
        }
        params.append(key, String(value));
    });
    return params.toString();
}

function postStripeInit({ sessionId, publicKey, locale, timezone, redirectType }) {
    return new Promise((resolve, reject) => {
        const body = encodeFormData({
            key: publicKey,
            eid: 'NA',
            browser_locale: locale || DEFAULT_LOCALE,
            browser_timezone: timezone || DEFAULT_TIMEZONE,
            redirect_type: redirectType || DEFAULT_REDIRECT_TYPE
        });

        const options = {
            host: STRIPE_API_HOST,
            path: `/v1/payment_pages/${encodeURIComponent(sessionId)}/init`,
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Content-Length': Buffer.byteLength(body),
                'Accept': 'application/json',
                'Origin': STRIPE_ORIGIN,
                'Referer': `${STRIPE_ORIGIN}/`,
                'User-Agent': 'StripeCheckoutInfo/1.0'
            }
        };

        const request = https.request(options, (response) => {
            let buffer = '';

            response.on('data', (chunk) => {
                buffer += chunk;
            });

            response.on('end', () => {
                try {
                    const parsed = JSON.parse(buffer);
                    if (response.statusCode >= 200 && response.statusCode < 300) {
                        resolve(parsed);
                        return;
                    }

                    reject(new StripeCheckoutInfoError('Stripe responded with an error', {
                        statusCode: response.statusCode,
                        details: parsed
                    }));
                } catch (err) {
                    reject(new StripeCheckoutInfoError('Failed to parse Stripe response', {
                        statusCode: response.statusCode,
                        cause: err
                    }));
                }
            });
        });

        request.on('error', (err) => {
            reject(new StripeCheckoutInfoError('Unable to contact Stripe', { cause: err }));
        });

        request.write(body);
        request.end();
    });
}

function sumTaxAmounts(invoice) {
    if (!invoice || !Array.isArray(invoice.total_tax_amounts)) {
        return null;
    }

    const total = invoice.total_tax_amounts
        .reduce((acc, entry) => acc + (entry.amount || 0), 0);

    return Number.isFinite(total) ? total : null;
}

function normalizeLineItems(invoice) {
    if (!invoice || !invoice.lines || !Array.isArray(invoice.lines.data)) {
        return [];
    }

    return invoice.lines.data.slice(0, MAX_LINE_ITEMS).map((item) => {
        const images = [];
        if (Array.isArray(item.images)) {
            images.push(...item.images);
        }
        if (item.price && item.price.product) {
            const product = item.price.product;
            if (Array.isArray(product.images)) {
                images.push(...product.images);
            }
        }

        const uniqueImages = Array.from(new Set(images)).slice(0, MAX_IMAGES_PER_ITEM);

        const recurring = item.price && item.price.recurring
            ? {
                interval: item.price.recurring.interval || null,
                intervalCount: item.price.recurring.interval_count || null
            }
            : null;

        return {
            id: item.line_item_id || item.id || null,
            description: item.description || null,
            amount: item.amount ?? null,
            currency: item.currency || item.price?.currency || null,
            quantity: item.quantity ?? null,
            unitAmount: item.price?.unit_amount ?? null,
            priceId: item.price?.id || null,
            productId: (typeof item.price?.product === 'string')
                ? item.price.product
                : item.price?.product?.id || null,
            images: uniqueImages,
            recurring
        };
    });
}

function normalizeCheckoutResponse(raw, { sessionId, publicKey, fallbackSite }) {
    const lineItems = normalizeLineItems(raw.invoice);
    const firstItem = lineItems[0] || null;

    const totals = {
        total: raw.invoice?.total ?? null,
        subtotal: raw.invoice?.subtotal ?? null,
        tax: sumTaxAmounts(raw.invoice)
    };

    const merchant = raw.account_settings ? {
        accountId: raw.account_settings.account_id || null,
        displayName: raw.account_settings.display_name || null,
        businessUrl: raw.account_settings.business_url || fallbackSite || null,
        supportEmail: raw.account_settings.support_email || null,
        supportPhone: raw.account_settings.support_phone || null,
        statementDescriptor: raw.account_settings.statement_descriptor || null
    } : (fallbackSite ? { businessUrl: fallbackSite } : null);

    const subscription = firstItem && firstItem.recurring ? {
        interval: firstItem.recurring.interval,
        intervalCount: firstItem.recurring.intervalCount,
        mode: raw.mode || null
    } : {
        interval: null,
        intervalCount: null,
        mode: raw.mode || null
    };

    return {
        sessionId,
        publicKey,
        livemode: raw.livemode ?? null,
        status: raw.status || null,
        currency: raw.currency || firstItem?.currency || null,
        totals,
        customerEmail: raw.customer_email || null,
        merchant,
        lineItems,
        subscription,
        urls: {
            hosted: raw.stripe_hosted_url || null,
            cancel: raw.cancel_url || null,
            success: raw.success_url || null,
            management: raw.management_url || null
        },
        configId: raw.config_id || null,
        initChecksum: raw.init_checksum || null
    };
}

async function fetchCheckoutInfo({ sessionId, publicKey, locale, timezone, redirectType, fallbackSite }) {
    if (!sessionId) {
        throw new StripeCheckoutInfoError('Missing checkout session id');
    }
    if (!publicKey) {
        throw new StripeCheckoutInfoError('Missing Stripe publishable key');
    }

    const raw = await postStripeInit({
        sessionId,
        publicKey,
        locale: locale || DEFAULT_LOCALE,
        timezone: timezone || DEFAULT_TIMEZONE,
        redirectType: redirectType || DEFAULT_REDIRECT_TYPE
    });

    return normalizeCheckoutResponse(raw, { sessionId, publicKey, fallbackSite });
}

module.exports = {
    fetchCheckoutInfo,
    parseCheckoutUrl,
    StripeCheckoutInfoError
};
