/**
 * Browser Fingerprinting Module
 * Advanced fingerprinting and spoofing techniques
 */

const crypto = require('crypto');

class BrowserFingerprint {
    constructor(options = {}) {
        this.options = options;
        this.verbose = options.verbose !== false;
    }

    /**
     * Generate complete browser fingerprint
     */
    generateFingerprint() {
        const fingerprint = {
            // Canvas fingerprint
            canvas: this.generateCanvasFingerprint(),

            // WebGL fingerprint
            webgl: this.generateWebGLFingerprint(),

            // Font fingerprint
            fonts: this.generateFontFingerprint(),

            // Plugin fingerprint
            plugins: this.generatePluginFingerprint(),

            // Audio context fingerprint
            audioContext: this.generateAudioContextFingerprint(),

            // Local storage fingerprint
            localStorage: this.generateLocalStorageFingerprint(),

            // Session storage fingerprint
            sessionStorage: this.generateSessionStorageFingerprint(),

            // IndexedDB fingerprint
            indexedDB: this.generateIndexedDBFingerprint(),

            // WebRTC fingerprint
            webrtc: this.generateWebRTCFingerprint(),

            // Battery API fingerprint
            battery: this.generateBatteryFingerprint(),

            // Geolocation fingerprint
            geolocation: this.generateGeolocationFingerprint(),

            // Timezone fingerprint
            timezone: this.generateTimezoneFingerprint(),

            // Language fingerprint
            language: this.generateLanguageFingerprint(),

            // Screen fingerprint
            screen: this.generateScreenFingerprint(),

            // Navigator fingerprint
            navigator: this.generateNavigatorFingerprint(),

            // Performance fingerprint
            performance: this.generatePerformanceFingerprint(),

            // Media devices fingerprint
            mediaDevices: this.generateMediaDevicesFingerprint(),

            // Permissions fingerprint
            permissions: this.generatePermissionsFingerprint(),

            // Sensor fingerprint
            sensor: this.generateSensorFingerprint(),

            // Credential fingerprint
            credential: this.generateCredentialFingerprint()
        };

        return fingerprint;
    }

    /**
     * Generate canvas fingerprint
     */
    generateCanvasFingerprint() {
        const text = 'Browser Canvas Fingerprint Test';
        const hash = crypto
            .createHash('sha256')
            .update(text + Math.random())
            .digest('hex');

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
            textBaseline: 'alphabetic'
        };
    }

    /**
     * Generate WebGL fingerprint
     */
    generateWebGLFingerprint() {
        return {
            vendor: 'Google Inc. (ANGLE)',
            renderer: 'ANGLE (Intel HD Graphics 630)',
            version: 'WebGL 2.0',
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
                'WEBGL_debug_renderer_info',
                'WEBGL_debug_shaders',
                'WEBGL_depth_texture',
                'WEBGL_draw_buffers'
            ],
            parameters: {
                MAX_TEXTURE_SIZE: 16384,
                MAX_CUBE_MAP_TEXTURE_SIZE: 16384,
                MAX_RENDERBUFFER_SIZE: 16384,
                MAX_VIEWPORT_DIMS: [16384, 16384],
                ALIASED_LINE_WIDTH_RANGE: [1, 1],
                ALIASED_POINT_SIZE_RANGE: [1, 1024],
                MAX_VERTEX_ATTRIBS: 16,
                MAX_VERTEX_UNIFORM_VECTORS: 4096,
                MAX_VARYING_VECTORS: 8,
                MAX_FRAGMENT_UNIFORM_VECTORS: 1024,
                MAX_TEXTURE_IMAGE_UNITS: 16,
                MAX_VERTEX_TEXTURE_IMAGE_UNITS: 16,
                MAX_COMBINED_TEXTURE_IMAGE_UNITS: 32
            }
        };
    }

    /**
     * Generate font fingerprint
     */
    generateFontFingerprint() {
        const baseFonts = ['monospace', 'sans-serif', 'serif'];
        const testFonts = [
            'Arial',
            'Verdana',
            'Times New Roman',
            'Courier New',
            'Georgia',
            'Palatino',
            'Garamond',
            'Bookman',
            'Comic Sans MS',
            'Trebuchet MS',
            'Impact',
            'Lucida Console',
            'Tahoma',
            'Lucida Grande',
            'Lucida Sans Unicode'
        ];

        const fontList = [];
        for (const font of testFonts) {
            fontList.push({
                name: font,
                available: true,
                hash: crypto.createHash('sha256').update(font).digest('hex').substring(0, 16)
            });
        }

        return {
            baseFonts: baseFonts,
            testFonts: testFonts,
            availableFonts: fontList,
            fontHash: crypto.createHash('sha256').update(JSON.stringify(fontList)).digest('hex')
        };
    }

    /**
     * Generate plugin fingerprint
     */
    generatePluginFingerprint() {
        return {
            plugins: [
                { name: 'Chrome PDF Plugin', version: '1.0' },
                { name: 'Chrome PDF Viewer', version: '1.0' },
                { name: 'Native Client Executable', version: '1.0' },
                { name: 'Shockwave Flash', version: '32.0.0.465' }
            ],
            mimeTypes: [
                { type: 'application/pdf', description: 'Portable Document Format' },
                { type: 'application/x-nacl', description: 'Native Client Executable' },
                { type: 'application/futuresplash', description: 'Shockwave Flash' }
            ]
        };
    }

    /**
     * Generate audio context fingerprint
     */
    generateAudioContextFingerprint() {
        return {
            sampleRate: 48000,
            channelCount: 2,
            maxChannelCount: 32,
            state: 'running',
            baseLatency: 0.005,
            outputLatency: 0.01,
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
            }
        };
    }

    /**
     * Generate local storage fingerprint
     */
    generateLocalStorageFingerprint() {
        return {
            available: true,
            size: Math.floor(Math.random() * 5000000) + 1000000,
            keys: [
                '_ga',
                '_gid',
                '_gat',
                'stripe_mid',
                'stripe_sid',
                'cf_clearance'
            ],
            hash: crypto.randomBytes(16).toString('hex')
        };
    }

    /**
     * Generate session storage fingerprint
     */
    generateSessionStorageFingerprint() {
        return {
            available: true,
            size: Math.floor(Math.random() * 1000000) + 100000,
            keys: [
                'session_id',
                'user_id',
                'cart_id'
            ],
            hash: crypto.randomBytes(16).toString('hex')
        };
    }

    /**
     * Generate IndexedDB fingerprint
     */
    generateIndexedDBFingerprint() {
        return {
            available: true,
            databases: [
                { name: 'stripe', version: 1 },
                { name: 'checkout', version: 1 },
                { name: 'cache', version: 1 }
            ],
            hash: crypto.randomBytes(16).toString('hex')
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
                { urls: ['stun:stun1.l.google.com:19302'] }
            ],
            ipAddress: this.generateRandomIP(),
            port: Math.floor(Math.random() * 65535) + 1024
        };
    }

    /**
     * Generate battery fingerprint
     */
    generateBatteryFingerprint() {
        return {
            available: true,
            level: Math.random(),
            charging: Math.random() > 0.5,
            chargingTime: Math.floor(Math.random() * 3600),
            dischargingTime: Math.floor(Math.random() * 36000)
        };
    }

    /**
     * Generate geolocation fingerprint
     */
    generateGeolocationFingerprint() {
        return {
            available: true,
            latitude: Math.random() * 180 - 90,
            longitude: Math.random() * 360 - 180,
            accuracy: Math.random() * 100,
            altitude: Math.random() * 1000,
            altitudeAccuracy: Math.random() * 100,
            heading: Math.random() * 360,
            speed: Math.random() * 100
        };
    }

    /**
     * Generate timezone fingerprint
     */
    generateTimezoneFingerprint() {
        const timezones = [
            'America/New_York',
            'America/Chicago',
            'America/Denver',
            'America/Los_Angeles',
            'Europe/London',
            'Europe/Paris',
            'Asia/Tokyo',
            'Asia/Shanghai',
            'Australia/Sydney'
        ];

        const tz = timezones[Math.floor(Math.random() * timezones.length)];
        const offset = new Date().getTimezoneOffset();

        return {
            timezone: tz,
            offset: offset,
            offsetMinutes: offset,
            offsetHours: offset / 60
        };
    }

    /**
     * Generate language fingerprint
     */
    generateLanguageFingerprint() {
        return {
            language: 'en-US',
            languages: ['en-US', 'en', 'en-GB'],
            preferredLanguage: 'en-US',
            acceptLanguage: 'en-US,en;q=0.9'
        };
    }

    /**
     * Generate screen fingerprint
     */
    generateScreenFingerprint() {
        return {
            width: 1920,
            height: 1080,
            availWidth: 1920,
            availHeight: 1040,
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
     * Generate navigator fingerprint
     */
    generateNavigatorFingerprint() {
        return {
            userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            appName: 'Netscape',
            appVersion: '5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            platform: 'Linux x86_64',
            hardwareConcurrency: 8,
            deviceMemory: 8,
            maxTouchPoints: 0,
            vendor: 'Google Inc.',
            language: 'en-US',
            onLine: true,
            doNotTrack: '1',
            cookieEnabled: true,
            plugins: 4,
            mimeTypes: 3
        };
    }

    /**
     * Generate performance fingerprint
     */
    generatePerformanceFingerprint() {
        return {
            navigationStart: Date.now() - Math.floor(Math.random() * 10000),
            unloadEventStart: Date.now() - Math.floor(Math.random() * 9000),
            unloadEventEnd: Date.now() - Math.floor(Math.random() * 8000),
            redirectStart: 0,
            redirectEnd: 0,
            fetchStart: Date.now() - Math.floor(Math.random() * 7000),
            domainLookupStart: Date.now() - Math.floor(Math.random() * 6000),
            domainLookupEnd: Date.now() - Math.floor(Math.random() * 5000),
            connectStart: Date.now() - Math.floor(Math.random() * 4000),
            connectEnd: Date.now() - Math.floor(Math.random() * 3000),
            secureConnectionStart: Date.now() - Math.floor(Math.random() * 2000),
            requestStart: Date.now() - Math.floor(Math.random() * 1000),
            responseStart: Date.now() - Math.floor(Math.random() * 500),
            responseEnd: Date.now()
        };
    }

    /**
     * Generate media devices fingerprint
     */
    generateMediaDevicesFingerprint() {
        return {
            audioInput: [
                { deviceId: crypto.randomBytes(16).toString('hex'), label: 'Built-in Audio' }
            ],
            audioOutput: [
                { deviceId: crypto.randomBytes(16).toString('hex'), label: 'Built-in Speaker' }
            ],
            videoInput: [
                { deviceId: crypto.randomBytes(16).toString('hex'), label: 'Built-in Webcam' }
            ]
        };
    }

    /**
     * Generate permissions fingerprint
     */
    generatePermissionsFingerprint() {
        return {
            camera: 'prompt',
            microphone: 'prompt',
            geolocation: 'prompt',
            notifications: 'prompt',
            clipboard: 'prompt',
            payment: 'granted'
        };
    }

    /**
     * Generate sensor fingerprint
     */
    generateSensorFingerprint() {
        return {
            accelerometer: true,
            gyroscope: true,
            magnetometer: true,
            proximity: false,
            ambientLight: false,
            linearAcceleration: true,
            rotationRate: true
        };
    }

    /**
     * Generate credential fingerprint
     */
    generateCredentialFingerprint() {
        return {
            available: true,
            publicKey: {
                create: true,
                get: true
            },
            password: true
        };
    }

    /**
     * Generate random IP
     */
    generateRandomIP() {
        return `${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}`;
    }

    /**
     * Get complete fingerprint hash
     */
    getFingerprintHash(fingerprint) {
        const hash = crypto
            .createHash('sha256')
            .update(JSON.stringify(fingerprint))
            .digest('hex');

        return hash;
    }

    /**
     * Create fingerprint report
     */
    createFingerprintReport() {
        const fingerprint = this.generateFingerprint();
        const hash = this.getFingerprintHash(fingerprint);

        return {
            fingerprint: fingerprint,
            hash: hash,
            timestamp: Date.now(),
            components: Object.keys(fingerprint).length
        };
    }
}

module.exports = {
    BrowserFingerprint
};
