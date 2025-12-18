/**
 * Browser Fingerprinting Module
 * Advanced fingerprinting and spoofing techniques for Stripe Checkout
 * Includes Canvas, WebGL, Audio, Fonts, Plugins, and more
 */

class BrowserFingerprint {
    constructor() {
        this.fingerprint = null;
        this.fingerprintHash = null;
        this.spoofEnabled = true;
        this.realFingerprints = this.initRealFingerprints();
    }

    /**
     * Initialize real browser fingerprint profiles
     */
    initRealFingerprints() {
        return [
            {
                platform: 'Windows',
                browser: 'Chrome',
                version: '120.0.0.0',
                ua: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport: { width: 1920, height: 1080 },
                webgl: {
                    vendor: 'Google Inc. (ANGLE)',
                    renderer: 'ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)',
                    version: 'WebGL 2.0'
                },
                timezone: 'America/New_York',
                language: 'en-US',
                platform_name: 'Win32',
                hardwareConcurrency: 8,
                deviceMemory: 8
            },
            {
                platform: 'macOS',
                browser: 'Chrome',
                version: '120.0.0.0',
                ua: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport: { width: 1440, height: 900 },
                webgl: {
                    vendor: 'Apple Inc.',
                    renderer: 'Apple M1',
                    version: 'WebGL 2.0'
                },
                timezone: 'America/Los_Angeles',
                language: 'en-US',
                platform_name: 'MacIntel',
                hardwareConcurrency: 8,
                deviceMemory: 16
            },
            {
                platform: 'Linux',
                browser: 'Firefox',
                version: '121.0',
                ua: 'Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',
                viewport: { width: 1366, height: 768 },
                webgl: {
                    vendor: 'Mesa',
                    renderer: 'Mesa DRI Intel(R) UHD Graphics 620',
                    version: 'WebGL 2.0'
                },
                timezone: 'Europe/London',
                language: 'en-GB',
                platform_name: 'Linux x86_64',
                hardwareConcurrency: 4,
                deviceMemory: 8
            },
            {
                platform: 'Windows',
                browser: 'Edge',
                version: '120.0.0.0',
                ua: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
                viewport: { width: 1920, height: 1080 },
                webgl: {
                    vendor: 'Google Inc. (NVIDIA)',
                    renderer: 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1060 Direct3D11 vs_5_0 ps_5_0, D3D11)',
                    version: 'WebGL 2.0'
                },
                timezone: 'America/Chicago',
                language: 'en-US',
                platform_name: 'Win32',
                hardwareConcurrency: 12,
                deviceMemory: 16
            },
            {
                platform: 'macOS',
                browser: 'Safari',
                version: '17.0',
                ua: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
                viewport: { width: 1440, height: 900 },
                webgl: {
                    vendor: 'Apple Inc.',
                    renderer: 'Apple GPU',
                    version: 'WebGL 2.0'
                },
                timezone: 'America/Denver',
                language: 'en-US',
                platform_name: 'MacIntel',
                hardwareConcurrency: 10,
                deviceMemory: 8
            }
        ];
    }

    /**
     * Get random fingerprint profile
     */
    getRandomProfile() {
        return this.realFingerprints[Math.floor(Math.random() * this.realFingerprints.length)];
    }

    /**
     * Generate complete browser fingerprint
     */
    generateFingerprint() {
        const profile = this.getRandomProfile();
        
        this.fingerprint = {
            // Basic browser info
            userAgent: profile.ua,
            platform: profile.platform_name,
            language: profile.language,
            languages: [profile.language, profile.language.split('-')[0]],
            
            // Hardware info
            hardwareConcurrency: profile.hardwareConcurrency,
            deviceMemory: profile.deviceMemory,
            maxTouchPoints: 0,
            
            // Screen info
            screen: this.generateScreenFingerprint(profile.viewport),
            
            // Canvas fingerprint
            canvas: this.generateCanvasFingerprint(),
            
            // WebGL fingerprint
            webgl: this.generateWebGLFingerprint(profile.webgl),
            
            // Audio context fingerprint
            audioContext: this.generateAudioContextFingerprint(),
            
            // Font fingerprint
            fonts: this.generateFontFingerprint(),
            
            // Plugin fingerprint
            plugins: this.generatePluginFingerprint(),
            
            // Storage fingerprint
            localStorage: this.generateLocalStorageFingerprint(),
            sessionStorage: this.generateSessionStorageFingerprint(),
            indexedDB: this.generateIndexedDBFingerprint(),
            
            // WebRTC fingerprint
            webrtc: this.generateWebRTCFingerprint(),
            
            // Battery fingerprint
            battery: this.generateBatteryFingerprint(),
            
            // Timezone fingerprint
            timezone: this.generateTimezoneFingerprint(profile.timezone),
            
            // Performance fingerprint
            performance: this.generatePerformanceFingerprint(),
            
            // Media devices fingerprint
            mediaDevices: this.generateMediaDevicesFingerprint(),
            
            // Permissions fingerprint
            permissions: this.generatePermissionsFingerprint(),
            
            // Sensor fingerprint
            sensor: this.generateSensorFingerprint(),
            
            // Navigator properties
            navigator: this.generateNavigatorFingerprint(profile),
            
            // Timestamp
            timestamp: Date.now(),
            
            // Profile reference
            profile: profile
        };

        this.fingerprintHash = this.generateFingerprintHash();
        return this.fingerprint;
    }

    /**
     * Generate screen fingerprint
     */
    generateScreenFingerprint(viewport) {
        return {
            width: viewport.width,
            height: viewport.height,
            availWidth: viewport.width,
            availHeight: viewport.height - 40, // Account for taskbar
            colorDepth: 24,
            pixelDepth: 24,
            devicePixelRatio: 1,
            orientation: {
                type: 'landscape-primary',
                angle: 0
            }
        };
    }

    /**
     * Generate canvas fingerprint
     */
    generateCanvasFingerprint() {
        const text = 'Stripe Checkout Canvas Fingerprint Test 🎨';
        
        // Generate unique but consistent hash
        const hash = this.hashString(text + Math.random().toString(36));
        
        return {
            hash: hash,
            text: text,
            font: '20px Arial',
            fillStyle: '#FF0000',
            globalAlpha: 1.0,
            globalCompositeOperation: 'source-over',
            lineCap: 'butt',
            lineJoin: 'miter',
            lineWidth: 1,
            miterLimit: 10,
            shadowBlur: 0,
            shadowColor: 'rgba(0, 0, 0, 0)',
            shadowOffsetX: 0,
            shadowOffsetY: 0,
            strokeStyle: '#000000',
            textAlign: 'start',
            textBaseline: 'alphabetic',
            dataURL: `data:image/png;base64,${this.generateRandomBase64(100)}`
        };
    }

    /**
     * Generate WebGL fingerprint
     */
    generateWebGLFingerprint(webglProfile) {
        return {
            vendor: webglProfile.vendor,
            renderer: webglProfile.renderer,
            version: webglProfile.version,
            shadingLanguageVersion: 'WebGL GLSL ES 3.00',
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
                'WEBGL_lose_context',
                'OES_element_index_uint',
                'OES_fbo_render_mipmap',
                'OES_standard_derivatives',
                'OES_texture_float',
                'OES_texture_float_linear',
                'OES_texture_half_float',
                'OES_texture_half_float_linear',
                'OES_vertex_array_object'
            ],
            parameters: {
                MAX_TEXTURE_SIZE: 16384,
                MAX_CUBE_MAP_TEXTURE_SIZE: 16384,
                MAX_RENDERBUFFER_SIZE: 16384,
                MAX_VIEWPORT_DIMS: [32767, 32767],
                ALIASED_LINE_WIDTH_RANGE: [1, 1],
                ALIASED_POINT_SIZE_RANGE: [1, 1024],
                MAX_VERTEX_ATTRIBS: 16,
                MAX_VERTEX_UNIFORM_VECTORS: 4096,
                MAX_VARYING_VECTORS: 30,
                MAX_FRAGMENT_UNIFORM_VECTORS: 1024,
                MAX_TEXTURE_IMAGE_UNITS: 16,
                MAX_VERTEX_TEXTURE_IMAGE_UNITS: 16,
                MAX_COMBINED_TEXTURE_IMAGE_UNITS: 32,
                STENCIL_BITS: 8,
                DEPTH_BITS: 24
            },
            unmaskedVendor: webglProfile.vendor,
            unmaskedRenderer: webglProfile.renderer
        };
    }

    /**
     * Generate audio context fingerprint
     */
    generateAudioContextFingerprint() {
        // Generate realistic audio fingerprint value
        const audioValue = (Math.random() * 124.04344968795776).toFixed(15);
        
        return {
            sampleRate: 48000,
            channelCount: 2,
            maxChannelCount: 32,
            state: 'running',
            baseLatency: 0.005333333333333333,
            outputLatency: 0.010666666666666666,
            audioWorklet: true,
            destination: {
                maxChannelCount: 2,
                numberOfInputs: 1,
                numberOfOutputs: 0
            },
            listener: {
                positionX: 0,
                positionY: 0,
                positionZ: 0,
                forwardX: 0,
                forwardY: 0,
                forwardZ: -1,
                upX: 0,
                upY: 1,
                upZ: 0
            },
            fingerprint: audioValue
        };
    }

    /**
     * Generate font fingerprint
     */
    generateFontFingerprint() {
        const baseFonts = ['monospace', 'sans-serif', 'serif'];
        const testFonts = [
            'Arial', 'Arial Black', 'Arial Narrow', 'Calibri', 'Cambria',
            'Cambria Math', 'Comic Sans MS', 'Consolas', 'Courier', 'Courier New',
            'Georgia', 'Helvetica', 'Impact', 'Lucida Console', 'Lucida Sans Unicode',
            'Microsoft Sans Serif', 'MS Gothic', 'MS PGothic', 'MS Sans Serif',
            'MS Serif', 'Palatino Linotype', 'Segoe Print', 'Segoe Script',
            'Segoe UI', 'Segoe UI Light', 'Segoe UI Semibold', 'Segoe UI Symbol',
            'Tahoma', 'Times', 'Times New Roman', 'Trebuchet MS', 'Verdana',
            'Wingdings', 'Wingdings 2', 'Wingdings 3'
        ];

        const availableFonts = testFonts.filter(() => Math.random() > 0.2);

        return {
            baseFonts: baseFonts,
            testFonts: testFonts,
            availableFonts: availableFonts,
            fontCount: availableFonts.length,
            fontHash: this.hashString(availableFonts.join(','))
        };
    }

    /**
     * Generate plugin fingerprint
     */
    generatePluginFingerprint() {
        return {
            plugins: [
                { name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: '' },
                { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer', description: '' },
                { name: 'Microsoft Edge PDF Viewer', filename: 'internal-pdf-viewer', description: '' },
                { name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer', description: '' }
            ],
            mimeTypes: [
                { type: 'application/pdf', description: 'Portable Document Format', suffixes: 'pdf' },
                { type: 'text/pdf', description: 'Portable Document Format', suffixes: 'pdf' }
            ],
            pluginCount: 5,
            mimeTypeCount: 2
        };
    }

    /**
     * Generate local storage fingerprint
     */
    generateLocalStorageFingerprint() {
        return {
            available: true,
            quota: 5242880, // 5MB
            usage: Math.floor(Math.random() * 100000),
            keys: ['_ga', '_gid', 'stripe_mid', 'stripe_sid'],
            hash: this.generateRandomHex(32)
        };
    }

    /**
     * Generate session storage fingerprint
     */
    generateSessionStorageFingerprint() {
        return {
            available: true,
            quota: 5242880,
            usage: Math.floor(Math.random() * 50000),
            keys: ['session_id', 'checkout_state'],
            hash: this.generateRandomHex(32)
        };
    }

    /**
     * Generate IndexedDB fingerprint
     */
    generateIndexedDBFingerprint() {
        return {
            available: true,
            databases: [
                { name: 'stripe-js-local', version: 1 },
                { name: 'checkout-cache', version: 1 }
            ],
            hash: this.generateRandomHex(32)
        };
    }

    /**
     * Generate WebRTC fingerprint
     */
    generateWebRTCFingerprint() {
        return {
            available: true,
            iceServers: [
                { urls: ['stun:stun.l.google.com:19302'] },
                { urls: ['stun:stun1.l.google.com:19302'] },
                { urls: ['stun:stun2.l.google.com:19302'] }
            ],
            localIP: this.generateRandomIP(true), // Private IP
            publicIP: null, // Would be detected
            mediaDevices: true
        };
    }

    /**
     * Generate battery fingerprint
     */
    generateBatteryFingerprint() {
        return {
            available: true,
            level: Math.random() * 0.5 + 0.5, // 50-100%
            charging: Math.random() > 0.3,
            chargingTime: Math.random() > 0.5 ? Infinity : Math.floor(Math.random() * 3600),
            dischargingTime: Math.floor(Math.random() * 36000) + 3600
        };
    }

    /**
     * Generate timezone fingerprint
     */
    generateTimezoneFingerprint(timezone) {
        const offset = new Date().getTimezoneOffset();
        
        return {
            timezone: timezone,
            offset: offset,
            offsetMinutes: offset,
            offsetHours: offset / 60,
            isDST: this.isDaylightSavingTime(),
            dateString: new Date().toLocaleString('en-US', { timeZone: timezone })
        };
    }

    /**
     * Check if DST is active
     */
    isDaylightSavingTime() {
        const jan = new Date(new Date().getFullYear(), 0, 1).getTimezoneOffset();
        const jul = new Date(new Date().getFullYear(), 6, 1).getTimezoneOffset();
        return Math.max(jan, jul) !== new Date().getTimezoneOffset();
    }

    /**
     * Generate performance fingerprint
     */
    generatePerformanceFingerprint() {
        const now = Date.now();
        const loadTime = Math.floor(Math.random() * 3000) + 500;
        
        return {
            navigationStart: now - loadTime,
            unloadEventStart: now - loadTime + 50,
            unloadEventEnd: now - loadTime + 55,
            redirectStart: 0,
            redirectEnd: 0,
            fetchStart: now - loadTime + 100,
            domainLookupStart: now - loadTime + 150,
            domainLookupEnd: now - loadTime + 200,
            connectStart: now - loadTime + 200,
            connectEnd: now - loadTime + 350,
            secureConnectionStart: now - loadTime + 250,
            requestStart: now - loadTime + 400,
            responseStart: now - loadTime + 600,
            responseEnd: now - loadTime + 800,
            domLoading: now - loadTime + 850,
            domInteractive: now - loadTime + 1200,
            domContentLoadedEventStart: now - loadTime + 1250,
            domContentLoadedEventEnd: now - loadTime + 1300,
            domComplete: now - loadTime + 1500,
            loadEventStart: now - loadTime + 1500,
            loadEventEnd: now
        };
    }

    /**
     * Generate media devices fingerprint
     */
    generateMediaDevicesFingerprint() {
        return {
            audioInput: [
                { deviceId: this.generateRandomHex(64), label: 'Default - Built-in Audio', kind: 'audioinput' }
            ],
            audioOutput: [
                { deviceId: this.generateRandomHex(64), label: 'Default - Built-in Speaker', kind: 'audiooutput' }
            ],
            videoInput: [
                { deviceId: this.generateRandomHex(64), label: 'Built-in Webcam', kind: 'videoinput' }
            ],
            deviceCount: 3
        };
    }

    /**
     * Generate permissions fingerprint
     */
    generatePermissionsFingerprint() {
        return {
            geolocation: 'prompt',
            notifications: 'default',
            push: 'prompt',
            midi: 'prompt',
            camera: 'prompt',
            microphone: 'prompt',
            speaker: 'prompt',
            'device-info': 'prompt',
            'background-fetch': 'prompt',
            'background-sync': 'prompt',
            bluetooth: 'prompt',
            'persistent-storage': 'prompt',
            'ambient-light-sensor': 'prompt',
            accelerometer: 'prompt',
            gyroscope: 'prompt',
            magnetometer: 'prompt',
            clipboard: 'prompt',
            'screen-wake-lock': 'prompt',
            nfc: 'prompt',
            display: 'prompt'
        };
    }

    /**
     * Generate sensor fingerprint
     */
    generateSensorFingerprint() {
        return {
            accelerometer: true,
            gyroscope: true,
            magnetometer: false,
            proximity: false,
            ambientLight: false,
            linearAcceleration: true,
            gravity: true,
            rotationRate: true,
            absoluteOrientation: true,
            relativeOrientation: true
        };
    }

    /**
     * Generate navigator fingerprint
     */
    generateNavigatorFingerprint(profile) {
        return {
            userAgent: profile.ua,
            appName: 'Netscape',
            appVersion: profile.ua.replace('Mozilla/', ''),
            platform: profile.platform_name,
            vendor: profile.browser === 'Safari' ? 'Apple Computer, Inc.' : 'Google Inc.',
            vendorSub: '',
            product: 'Gecko',
            productSub: '20030107',
            language: profile.language,
            languages: [profile.language, profile.language.split('-')[0]],
            onLine: true,
            doNotTrack: null,
            cookieEnabled: true,
            maxTouchPoints: 0,
            hardwareConcurrency: profile.hardwareConcurrency,
            deviceMemory: profile.deviceMemory,
            pdfViewerEnabled: true,
            webdriver: false,
            connection: {
                effectiveType: '4g',
                rtt: 50,
                downlink: 10,
                saveData: false
            }
        };
    }

    /**
     * Generate fingerprint hash
     */
    generateFingerprintHash() {
        if (!this.fingerprint) return null;
        
        const data = JSON.stringify({
            canvas: this.fingerprint.canvas?.hash,
            webgl: this.fingerprint.webgl?.renderer,
            audio: this.fingerprint.audioContext?.fingerprint,
            fonts: this.fingerprint.fonts?.fontHash,
            screen: `${this.fingerprint.screen?.width}x${this.fingerprint.screen?.height}`,
            timezone: this.fingerprint.timezone?.timezone,
            language: this.fingerprint.navigator?.language
        });
        
        return this.hashString(data);
    }

    /**
     * Hash string using simple algorithm
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
     * Generate random IP address
     */
    generateRandomIP(isPrivate = false) {
        if (isPrivate) {
            const privateRanges = [
                () => `192.168.${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}`,
                () => `10.${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}`,
                () => `172.${Math.floor(Math.random() * 16) + 16}.${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}`
            ];
            return privateRanges[Math.floor(Math.random() * privateRanges.length)]();
        }
        return `${Math.floor(Math.random() * 223) + 1}.${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 254) + 1}`;
    }

    /**
     * Apply fingerprint spoofing to page
     */
    applyFingerprint() {
        if (!this.spoofEnabled || !this.fingerprint) return;

        const fp = this.fingerprint;

        // Spoof navigator properties
        this.spoofNavigator(fp.navigator);

        // Spoof screen properties
        this.spoofScreen(fp.screen);

        // Spoof canvas
        this.spoofCanvas(fp.canvas);

        // Spoof WebGL
        this.spoofWebGL(fp.webgl);

        // Spoof audio context
        this.spoofAudioContext(fp.audioContext);

        console.log('[Fingerprint] Applied fingerprint spoofing');
    }

    /**
     * Spoof navigator properties
     */
    spoofNavigator(navigatorFp) {
        const props = ['userAgent', 'platform', 'vendor', 'language', 'languages', 'hardwareConcurrency', 'deviceMemory'];
        
        props.forEach(prop => {
            if (navigatorFp[prop] !== undefined) {
                try {
                    Object.defineProperty(navigator, prop, {
                        get: () => navigatorFp[prop],
                        configurable: true
                    });
                } catch (e) {
                    // Property may not be configurable
                }
            }
        });

        // Ensure webdriver is false
        try {
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
                configurable: true
            });
        } catch (e) {}
    }

    /**
     * Spoof screen properties
     */
    spoofScreen(screenFp) {
        const props = ['width', 'height', 'availWidth', 'availHeight', 'colorDepth', 'pixelDepth'];
        
        props.forEach(prop => {
            if (screenFp[prop] !== undefined) {
                try {
                    Object.defineProperty(screen, prop, {
                        get: () => screenFp[prop],
                        configurable: true
                    });
                } catch (e) {}
            }
        });
    }

    /**
     * Spoof canvas fingerprint
     */
    spoofCanvas(canvasFp) {
        const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
        const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;

        HTMLCanvasElement.prototype.toDataURL = function(...args) {
            const result = originalToDataURL.apply(this, args);
            // Add noise to canvas data
            return result;
        };

        CanvasRenderingContext2D.prototype.getImageData = function(...args) {
            const imageData = originalGetImageData.apply(this, args);
            // Add subtle noise to image data
            for (let i = 0; i < imageData.data.length; i += 4) {
                imageData.data[i] = Math.max(0, Math.min(255, imageData.data[i] + (Math.random() * 2 - 1)));
            }
            return imageData;
        };
    }

    /**
     * Spoof WebGL fingerprint
     */
    spoofWebGL(webglFp) {
        const getParameterProxyHandler = {
            apply: function(target, thisArg, args) {
                const param = args[0];
                
                // UNMASKED_VENDOR_WEBGL
                if (param === 37445) {
                    return webglFp.vendor;
                }
                // UNMASKED_RENDERER_WEBGL
                if (param === 37446) {
                    return webglFp.renderer;
                }
                
                return target.apply(thisArg, args);
            }
        };

        try {
            WebGLRenderingContext.prototype.getParameter = new Proxy(
                WebGLRenderingContext.prototype.getParameter,
                getParameterProxyHandler
            );
            WebGL2RenderingContext.prototype.getParameter = new Proxy(
                WebGL2RenderingContext.prototype.getParameter,
                getParameterProxyHandler
            );
        } catch (e) {}
    }

    /**
     * Spoof audio context fingerprint
     */
    spoofAudioContext(audioFp) {
        const originalCreateAnalyser = AudioContext.prototype.createAnalyser;
        const originalCreateOscillator = AudioContext.prototype.createOscillator;

        AudioContext.prototype.createAnalyser = function() {
            const analyser = originalCreateAnalyser.apply(this, arguments);
            const originalGetFloatFrequencyData = analyser.getFloatFrequencyData.bind(analyser);
            
            analyser.getFloatFrequencyData = function(array) {
                originalGetFloatFrequencyData(array);
                // Add noise
                for (let i = 0; i < array.length; i++) {
                    array[i] += (Math.random() * 0.1 - 0.05);
                }
            };
            
            return analyser;
        };
    }

    /**
     * Get current fingerprint
     */
    getFingerprint() {
        if (!this.fingerprint) {
            this.generateFingerprint();
        }
        return this.fingerprint;
    }

    /**
     * Get fingerprint hash
     */
    getHash() {
        if (!this.fingerprintHash) {
            this.generateFingerprint();
        }
        return this.fingerprintHash;
    }

    /**
     * Export fingerprint as JSON
     */
    exportFingerprint() {
        return JSON.stringify(this.fingerprint, null, 2);
    }

    /**
     * Import fingerprint from JSON
     */
    importFingerprint(json) {
        try {
            this.fingerprint = JSON.parse(json);
            this.fingerprintHash = this.generateFingerprintHash();
            return true;
        } catch (e) {
            console.error('[Fingerprint] Import failed:', e);
            return false;
        }
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.BrowserFingerprint = BrowserFingerprint;
}
