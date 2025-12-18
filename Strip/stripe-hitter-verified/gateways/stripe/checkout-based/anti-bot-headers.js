/**
 * Anti-Bot Detection Headers & Techniques
 * Implements headers and techniques to bypass anti-bot detection
 */

const crypto = require('crypto');

class AntiBotHeaders {
    constructor(options = {}) {
        this.userAgent = options.userAgent || this.getRandomUserAgent();
        this.referer = options.referer || 'https://checkout.stripe.com';
        this.origin = options.origin || 'https://checkout.stripe.com';
        this.verbose = options.verbose !== false;
    }

    /**
     * Get comprehensive anti-bot headers
     */
    getHeaders() {
        const headers = {
            // Standard browser headers
            'User-Agent': this.userAgent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'max-age=0',
            'Pragma': 'no-cache',
            'Upgrade-Insecure-Requests': '1',

            // Referer and origin
            'Referer': this.referer,
            'Origin': this.origin,

            // Security headers
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Sec-Ch-Ua': this.getSecChUa(),
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Linux"',

            // Browser capabilities
            'X-Requested-With': 'XMLHttpRequest',
            'X-Forwarded-For': this.getRandomIP(),
            'X-Forwarded-Proto': 'https',
            'X-Real-IP': this.getRandomIP(),

            // Stripe-specific headers
            'X-Stripe-Client-User-Agent': this.getStripeUserAgent(),
            'X-Stripe-Client-Version': '3.0.0',

            // Additional anti-bot headers
            'DNT': '1',
            'Connection': 'keep-alive',
            'Keep-Alive': '300',
            'TE': 'trailers',

            // Timing headers
            'X-Request-Start': Date.now().toString(),
            'X-Request-ID': this.generateRequestID(),

            // Browser fingerprint headers
            'X-Browser-Fingerprint': this.generateBrowserFingerprint(),
            'X-Device-ID': this.generateDeviceID(),
            'X-Session-ID': this.generateSessionID()
        };

        if (this.verbose) {
            console.log('[ANTI-BOT] Generated headers:', Object.keys(headers).length);
        }

        return headers;
    }

    /**
     * Get Sec-Ch-Ua header value
     */
    getSecChUa() {
        const versions = [
            '"Google Chrome";v="120", "Chromium";v="120", ";Not A Brand";v="99"',
            '"Microsoft Edge";v="120", "Chromium";v="120", ";Not A Brand";v="99"',
            '"Brave";v="120", "Chromium";v="120", ";Not A Brand";v="99"'
        ];
        return versions[Math.floor(Math.random() * versions.length)];
    }

    /**
     * Get random user agent
     */
    getRandomUserAgent() {
        const userAgents = [
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
        ];
        return userAgents[Math.floor(Math.random() * userAgents.length)];
    }

    /**
     * Get Stripe user agent
     */
    getStripeUserAgent() {
        const agents = [
            'stripe.js/3.0.0',
            'stripe-js/3.1.0',
            'stripe-checkout/3.0.0',
            'stripe-payment/3.0.0'
        ];
        return agents[Math.floor(Math.random() * agents.length)];
    }

    /**
     * Get random IP address
     */
    getRandomIP() {
        return `${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}`;
    }

    /**
     * Generate request ID
     */
    generateRequestID() {
        return `req_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
    }

    /**
     * Generate browser fingerprint
     */
    generateBrowserFingerprint() {
        const fingerprint = {
            ua: this.userAgent,
            lang: 'en-US',
            tz: -300,
            plugins: 4,
            fonts: 10,
            canvas: crypto.randomBytes(16).toString('hex'),
            webgl: crypto.randomBytes(16).toString('hex')
        };
        return Buffer.from(JSON.stringify(fingerprint)).toString('base64');
    }

    /**
     * Generate device ID
     */
    generateDeviceID() {
        return `device_${crypto.randomBytes(16).toString('hex')}`;
    }

    /**
     * Generate session ID
     */
    generateSessionID() {
        return `session_${Date.now()}_${Math.random().toString(36).substring(2, 15)}`;
    }

    /**
     * Get anti-bot cookies
     */
    getCookies() {
        return {
            '_ga': `GA1.2.${Math.floor(Math.random() * 1000000000)}.${Math.floor(Date.now() / 1000)}`,
            '_gid': `GA1.2.${Math.floor(Math.random() * 1000000000)}.${Math.floor(Date.now() / 1000)}`,
            '_gat': '1',
            'cf_clearance': this.generateCFClearance(),
            'stripe_mid': this.generateStripeMID(),
            'stripe_sid': this.generateStripeSID()
        };
    }

    /**
     * Generate Cloudflare clearance cookie
     */
    generateCFClearance() {
        return crypto.randomBytes(32).toString('hex');
    }

    /**
     * Generate Stripe MID cookie
     */
    generateStripeMID() {
        return `mid_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
    }

    /**
     * Generate Stripe SID cookie
     */
    generateStripeSID() {
        return `sid_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
    }

    /**
     * Get timing information for realistic behavior
     */
    getTimingInfo() {
        return {
            page_load_time: Math.floor(Math.random() * 3000) + 500,
            interaction_delay: Math.floor(Math.random() * 500) + 100,
            mouse_movements: Math.floor(Math.random() * 20) + 5,
            keyboard_events: Math.floor(Math.random() * 10) + 2,
            scroll_events: Math.floor(Math.random() * 15) + 3
        };
    }

    /**
     * Get JavaScript execution context
     */
    getJSContext() {
        return {
            navigator: {
                userAgent: this.userAgent,
                language: 'en-US',
                languages: ['en-US', 'en'],
                platform: 'Linux x86_64',
                hardwareConcurrency: 8,
                deviceMemory: 8,
                maxTouchPoints: 0,
                vendor: 'Google Inc.'
            },
            screen: {
                width: 1920,
                height: 1080,
                availWidth: 1920,
                availHeight: 1040,
                colorDepth: 24,
                pixelDepth: 24
            },
            window: {
                innerWidth: 1920,
                innerHeight: 1080,
                outerWidth: 1920,
                outerHeight: 1080,
                screenX: 0,
                screenY: 0
            }
        };
    }

    /**
     * Get WebGL fingerprint
     */
    getWebGLFingerprint() {
        return {
            vendor: 'Google Inc. (ANGLE)',
            renderer: 'ANGLE (Intel HD Graphics 630)',
            version: 'WebGL 2.0',
            extensions: [
                'ANGLE_instanced_arrays',
                'EXT_blend_minmax',
                'EXT_color_buffer_half_float',
                'EXT_disjoint_timer_query',
                'EXT_float_blend',
                'EXT_frag_depth',
                'EXT_shader_texture_lod',
                'EXT_sRGB',
                'EXT_texture_compression_bptc',
                'EXT_texture_compression_rgtc',
                'EXT_texture_filter_anisotropic',
                'WEBGL_color_buffer_float',
                'WEBGL_compressed_texture_s3tc',
                'WEBGL_debug_renderer_info',
                'WEBGL_debug_shaders',
                'WEBGL_depth_texture',
                'WEBGL_draw_buffers'
            ]
        };
    }

    /**
     * Get Canvas fingerprint
     */
    getCanvasFingerprint() {
        const text = 'Browser Canvas Fingerprint';
        const hash = crypto
            .createHash('sha256')
            .update(text + this.userAgent)
            .digest('hex');
        return hash;
    }

    /**
     * Get realistic mouse movements
     */
    getMouseMovements() {
        const movements = [];
        let x = Math.floor(Math.random() * 1920);
        let y = Math.floor(Math.random() * 1080);

        for (let i = 0; i < Math.floor(Math.random() * 20) + 5; i++) {
            x += Math.floor(Math.random() * 100) - 50;
            y += Math.floor(Math.random() * 100) - 50;
            movements.push({
                x: Math.max(0, Math.min(1920, x)),
                y: Math.max(0, Math.min(1080, y)),
                timestamp: Date.now() + i * 50
            });
        }

        return movements;
    }

    /**
     * Get realistic keyboard events
     */
    getKeyboardEvents() {
        return [
            { key: 'Enter', timestamp: Date.now() + 100 },
            { key: 'Tab', timestamp: Date.now() + 200 },
            { key: 'Backspace', timestamp: Date.now() + 300 }
        ];
    }

    /**
     * Get anti-detection techniques
     */
    getAntiDetectionTechniques() {
        return {
            // Disable headless detection
            disable_headless: true,

            // Randomize timing
            randomize_timing: true,

            // Realistic user behavior
            simulate_user_behavior: true,

            // Browser fingerprinting
            fingerprint_browser: true,

            // WebGL spoofing
            spoof_webgl: true,

            // Canvas fingerprinting
            spoof_canvas: true,

            // Plugin spoofing
            spoof_plugins: true,

            // Timezone spoofing
            spoof_timezone: true,

            // Language spoofing
            spoof_language: true,

            // Geolocation spoofing
            spoof_geolocation: true,

            // Screen resolution spoofing
            spoof_screen: true,

            // Memory spoofing
            spoof_memory: true,

            // CPU spoofing
            spoof_cpu: true,

            // GPU spoofing
            spoof_gpu: true
        };
    }

    /**
     * Get complete anti-bot configuration
     */
    getCompleteConfig() {
        return {
            headers: this.getHeaders(),
            cookies: this.getCookies(),
            timing: this.getTimingInfo(),
            jsContext: this.getJSContext(),
            webgl: this.getWebGLFingerprint(),
            canvas: this.getCanvasFingerprint(),
            mouseMovements: this.getMouseMovements(),
            keyboardEvents: this.getKeyboardEvents(),
            antiDetection: this.getAntiDetectionTechniques()
        };
    }
}

module.exports = {
    AntiBotHeaders
};
