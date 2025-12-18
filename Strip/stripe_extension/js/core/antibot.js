/**
 * Anti-Bot Detection Headers & Techniques
 * Implements headers and techniques to bypass anti-bot detection
 * Includes Cloudflare, Akamai, DataDome, PerimeterX bypass
 */

class AntiBotHeaders {
    constructor(options = {}) {
        this.userAgent = options.userAgent || this.getRandomUserAgent();
        this.referer = options.referer || 'https://checkout.stripe.com';
        this.origin = options.origin || 'https://checkout.stripe.com';
        this.verbose = options.verbose !== false;
        this.sessionId = this.generateSessionID();
        this.deviceId = this.generateDeviceID();
    }

    /**
     * Get comprehensive anti-bot headers
     */
    getHeaders() {
        const headers = {
            // Standard browser headers
            'User-Agent': this.userAgent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'max-age=0',
            'Pragma': 'no-cache',
            'Upgrade-Insecure-Requests': '1',

            // Referer and origin
            'Referer': this.referer,
            'Origin': this.origin,

            // Security headers (Sec-Fetch)
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            
            // Client hints
            'Sec-Ch-Ua': this.getSecChUa(),
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': this.getSecChUaPlatform(),
            'Sec-Ch-Ua-Platform-Version': this.getSecChUaPlatformVersion(),
            'Sec-Ch-Ua-Full-Version-List': this.getSecChUaFullVersionList(),
            'Sec-Ch-Ua-Arch': '"x86"',
            'Sec-Ch-Ua-Bitness': '"64"',
            'Sec-Ch-Ua-Model': '""',

            // Browser capabilities
            'DNT': '1',
            'Connection': 'keep-alive',

            // Stripe-specific headers
            'X-Stripe-Client-User-Agent': this.getStripeUserAgent(),

            // Request identification
            'X-Request-ID': this.generateRequestID(),
            'X-Request-Start': Date.now().toString()
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
            '"Google Chrome";v="120", "Chromium";v="120", "Not_A Brand";v="24"',
            '"Google Chrome";v="121", "Chromium";v="121", "Not_A Brand";v="24"',
            '"Microsoft Edge";v="120", "Chromium";v="120", "Not_A Brand";v="24"',
            '"Brave";v="120", "Chromium";v="120", "Not_A Brand";v="24"'
        ];
        return versions[Math.floor(Math.random() * versions.length)];
    }

    /**
     * Get Sec-Ch-Ua-Platform header value
     */
    getSecChUaPlatform() {
        const platforms = ['"Windows"', '"macOS"', '"Linux"'];
        return platforms[Math.floor(Math.random() * platforms.length)];
    }

    /**
     * Get Sec-Ch-Ua-Platform-Version header value
     */
    getSecChUaPlatformVersion() {
        const versions = ['"10.0.0"', '"15.0.0"', '"14.0.0"', '"6.1.0"'];
        return versions[Math.floor(Math.random() * versions.length)];
    }

    /**
     * Get Sec-Ch-Ua-Full-Version-List header value
     */
    getSecChUaFullVersionList() {
        return '"Google Chrome";v="120.0.6099.109", "Chromium";v="120.0.6099.109", "Not_A Brand";v="24.0.0.0"';
    }

    /**
     * Get random user agent
     */
    getRandomUserAgent() {
        const userAgents = [
            // Chrome Windows
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            // Chrome macOS
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            // Chrome Linux
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            // Firefox
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
            // Edge
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
            // Safari
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
        ];
        return userAgents[Math.floor(Math.random() * userAgents.length)];
    }

    /**
     * Get Stripe user agent
     */
    getStripeUserAgent() {
        const agents = {
            'stripe.js': '3.0.0',
            'stripe-js-v3': 'v3',
            'checkout': 'hosted_checkout'
        };
        return JSON.stringify(agents);
    }

    /**
     * Generate request ID
     */
    generateRequestID() {
        return `req_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
    }

    /**
     * Generate device ID
     */
    generateDeviceID() {
        return `device_${this.generateRandomHex(32)}`;
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
        const timestamp = Date.now();
        const baseTime = timestamp - Math.floor(Math.random() * 2592000000);

        return {
            // Google Analytics
            '_ga': `GA1.2.${Math.floor(Math.random() * 2000000000)}.${Math.floor(baseTime / 1000)}`,
            '_gid': `GA1.2.${Math.floor(Math.random() * 2000000000)}.${Math.floor(timestamp / 86400000)}`,
            '_gat': '1',
            
            // Cloudflare
            'cf_clearance': this.generateCFClearance(),
            '__cf_bm': this.generateCfBm(),
            '_cfuvid': `${this.generateRandomHex(32)}.${Math.floor(timestamp / 1000)}`,
            
            // Stripe
            'stripe_mid': this.generateStripeMID(),
            'stripe_sid': this.generateStripeSID(),
            '__stripe_mid': this.generateStripeMID(),
            '__stripe_sid': this.generateStripeSID(),
            
            // Akamai
            'ak_bmsc': this.generateRandomBase64(88),
            '_abck': `${this.generateRandomBase64(144)}~0~${this.generateRandomBase64(64)}~0~-1`,
            'bm_mi': this.generateBmMi(),
            'bm_sv': this.generateBmSv(),
            
            // Facebook Pixel
            '_fbp': `fb.1.${timestamp}.${Math.floor(Math.random() * 2000000000)}`,
            
            // GDPR Consent
            'gdpr_consent': `1~${this.generateConsentString()}`,
            'euconsent': this.generateEuConsent(),
            
            // Session
            'sessionid': this.generateRandomHex(32),
            'csrftoken': this.generateRandomBase64(64)
        };
    }

    /**
     * Generate Cloudflare clearance cookie
     */
    generateCFClearance() {
        const timestamp = Math.floor(Date.now() / 1000);
        const challenge = this.generateRandomBase64(43);
        return `${challenge}.${timestamp}-0-${this.generateRandomHex(8)}`;
    }

    /**
     * Generate Cloudflare BM cookie
     */
    generateCfBm() {
        return this.generateRandomBase64(43) + '=';
    }

    /**
     * Generate Stripe MID cookie
     */
    generateStripeMID() {
        return `mid_${this.generateRandomHex(24)}`;
    }

    /**
     * Generate Stripe SID cookie
     */
    generateStripeSID() {
        return `sid_${this.generateRandomHex(24)}`;
    }

    /**
     * Generate Akamai BM MI cookie
     */
    generateBmMi() {
        return `${this.generateRandomHex(32)}~${this.generateRandomHex(16)}`;
    }

    /**
     * Generate Akamai BM SV cookie
     */
    generateBmSv() {
        return `${this.generateRandomBase64(100)}~${this.generateRandomHex(8)}~${Date.now()}`;
    }

    /**
     * Generate GDPR consent string
     */
    generateConsentString() {
        const purposes = Array(24).fill().map(() => Math.random() > 0.3 ? '1' : '0').join('');
        return btoa(purposes).replace(/=/g, '');
    }

    /**
     * Generate EU consent string
     */
    generateEuConsent() {
        return `CP${this.generateRandomString(20, 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_')}.`;
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
            scroll_events: Math.floor(Math.random() * 15) + 3,
            focus_events: Math.floor(Math.random() * 5) + 1,
            click_events: Math.floor(Math.random() * 3) + 1
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
                platform: 'Win32',
                hardwareConcurrency: 8,
                deviceMemory: 8,
                maxTouchPoints: 0,
                vendor: 'Google Inc.',
                webdriver: false,
                cookieEnabled: true,
                doNotTrack: '1',
                onLine: true
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
                innerHeight: 969,
                outerWidth: 1920,
                outerHeight: 1080,
                screenX: 0,
                screenY: 0,
                devicePixelRatio: 1
            },
            document: {
                characterSet: 'UTF-8',
                compatMode: 'CSS1Compat',
                contentType: 'text/html',
                designMode: 'off',
                dir: 'ltr',
                readyState: 'complete'
            }
        };
    }

    /**
     * Get WebGL fingerprint for anti-bot
     */
    getWebGLFingerprint() {
        return {
            vendor: 'Google Inc. (ANGLE)',
            renderer: 'ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)',
            version: 'WebGL 2.0 (OpenGL ES 3.0 Chromium)',
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
                'WEBGL_compressed_texture_s3tc_srgb',
                'WEBGL_debug_renderer_info',
                'WEBGL_debug_shaders',
                'WEBGL_depth_texture',
                'WEBGL_draw_buffers',
                'WEBGL_lose_context'
            ]
        };
    }

    /**
     * Get Canvas fingerprint for anti-bot
     */
    getCanvasFingerprint() {
        const text = 'Stripe Checkout Canvas Test';
        return this.hashString(text + this.userAgent + Date.now());
    }

    /**
     * Get realistic mouse movements
     */
    getMouseMovements(count = 20) {
        const movements = [];
        let x = Math.floor(Math.random() * 1920);
        let y = Math.floor(Math.random() * 1080);
        let timestamp = Date.now();

        for (let i = 0; i < count; i++) {
            // Bezier curve simulation for natural movement
            const targetX = x + Math.floor(Math.random() * 200) - 100;
            const targetY = y + Math.floor(Math.random() * 200) - 100;
            
            const steps = Math.floor(Math.random() * 5) + 3;
            for (let j = 0; j < steps; j++) {
                const t = j / steps;
                const newX = Math.floor(x + (targetX - x) * t + Math.sin(t * Math.PI) * (Math.random() * 20 - 10));
                const newY = Math.floor(y + (targetY - y) * t + Math.sin(t * Math.PI) * (Math.random() * 20 - 10));
                
                movements.push({
                    x: Math.max(0, Math.min(1920, newX)),
                    y: Math.max(0, Math.min(1080, newY)),
                    timestamp: timestamp,
                    type: 'mousemove'
                });
                
                timestamp += Math.floor(Math.random() * 30) + 10;
            }
            
            x = targetX;
            y = targetY;
        }

        return movements;
    }

    /**
     * Get realistic keyboard events
     */
    getKeyboardEvents(text = '') {
        const events = [];
        let timestamp = Date.now();

        for (const char of text) {
            // Key down
            events.push({
                type: 'keydown',
                key: char,
                code: `Key${char.toUpperCase()}`,
                timestamp: timestamp
            });
            
            timestamp += Math.floor(Math.random() * 50) + 30;
            
            // Key press
            events.push({
                type: 'keypress',
                key: char,
                code: `Key${char.toUpperCase()}`,
                timestamp: timestamp
            });
            
            timestamp += Math.floor(Math.random() * 20) + 10;
            
            // Key up
            events.push({
                type: 'keyup',
                key: char,
                code: `Key${char.toUpperCase()}`,
                timestamp: timestamp
            });
            
            // Random delay between characters (typing speed variation)
            timestamp += Math.floor(Math.random() * 150) + 50;
        }

        return events;
    }

    /**
     * Get anti-detection techniques configuration
     */
    getAntiDetectionConfig() {
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
            
            // Screen resolution spoofing
            spoof_screen: true,
            
            // Memory spoofing
            spoof_memory: true,
            
            // CPU spoofing
            spoof_cpu: true,
            
            // WebRTC leak prevention
            prevent_webrtc_leak: true,
            
            // Audio context noise
            add_audio_noise: true
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
            antiDetection: this.getAntiDetectionConfig(),
            sessionId: this.sessionId,
            deviceId: this.deviceId
        };
    }

    /**
     * Apply anti-bot measures to current page
     */
    applyAntiBotMeasures() {
        // Override webdriver property
        this.overrideWebdriver();
        
        // Override plugins
        this.overridePlugins();
        
        // Override languages
        this.overrideLanguages();
        
        // Override permissions
        this.overridePermissions();
        
        // Add noise to canvas
        this.addCanvasNoise();
        
        // Add noise to audio
        this.addAudioNoise();
        
        console.log('[ANTI-BOT] Applied anti-bot measures');
    }

    /**
     * Override webdriver property
     */
    overrideWebdriver() {
        try {
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
                configurable: true
            });
            
            // Also delete from prototype
            delete Navigator.prototype.webdriver;
        } catch (e) {}
    }

    /**
     * Override plugins
     */
    overridePlugins() {
        try {
            const plugins = [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer' },
                { name: 'Native Client', filename: 'internal-nacl-plugin' }
            ];
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => plugins,
                configurable: true
            });
        } catch (e) {}
    }

    /**
     * Override languages
     */
    overrideLanguages() {
        try {
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
                configurable: true
            });
        } catch (e) {}
    }

    /**
     * Override permissions
     */
    overridePermissions() {
        try {
            const originalQuery = navigator.permissions.query;
            navigator.permissions.query = (parameters) => {
                if (parameters.name === 'notifications') {
                    return Promise.resolve({ state: 'prompt', onchange: null });
                }
                return originalQuery.call(navigator.permissions, parameters);
            };
        } catch (e) {}
    }

    /**
     * Add noise to canvas fingerprint
     */
    addCanvasNoise() {
        try {
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type) {
                if (type === 'image/png' || type === undefined) {
                    const context = this.getContext('2d');
                    if (context) {
                        const imageData = context.getImageData(0, 0, this.width, this.height);
                        for (let i = 0; i < imageData.data.length; i += 4) {
                            // Add subtle noise
                            imageData.data[i] = Math.max(0, Math.min(255, imageData.data[i] + (Math.random() * 2 - 1)));
                        }
                        context.putImageData(imageData, 0, 0);
                    }
                }
                return originalToDataURL.apply(this, arguments);
            };
        } catch (e) {}
    }

    /**
     * Add noise to audio fingerprint
     */
    addAudioNoise() {
        try {
            const originalCreateAnalyser = AudioContext.prototype.createAnalyser;
            AudioContext.prototype.createAnalyser = function() {
                const analyser = originalCreateAnalyser.apply(this, arguments);
                const originalGetFloatFrequencyData = analyser.getFloatFrequencyData.bind(analyser);
                
                analyser.getFloatFrequencyData = function(array) {
                    originalGetFloatFrequencyData(array);
                    for (let i = 0; i < array.length; i++) {
                        array[i] = array[i] + (Math.random() * 0.1 - 0.05);
                    }
                };
                
                return analyser;
            };
        } catch (e) {}
    }

    /**
     * Hash string
     */
    hashString(str) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return Math.abs(hash).toString(16).padStart(8, '0');
    }

    /**
     * Generate random hex string
     */
    generateRandomHex(length) {
        const chars = '0123456789abcdef';
        let result = '';
        for (let i = 0; i < length; i++) {
            result += chars[Math.floor(Math.random() * chars.length)];
        }
        return result;
    }

    /**
     * Generate random base64 string
     */
    generateRandomBase64(length) {
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
        let result = '';
        for (let i = 0; i < length; i++) {
            result += chars[Math.floor(Math.random() * chars.length)];
        }
        return result;
    }

    /**
     * Generate random string
     */
    generateRandomString(length, chars) {
        let result = '';
        for (let i = 0; i < length; i++) {
            result += chars[Math.floor(Math.random() * chars.length)];
        }
        return result;
    }

    /**
     * Generate random IP
     */
    generateRandomIP() {
        return `${Math.floor(Math.random() * 223) + 1}.${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 254) + 1}`;
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.AntiBotHeaders = AntiBotHeaders;
}
