/**
 * Session Management Module
 * Handles persistent sessions, cookies, and checkout state
 */

class SessionManager {
    constructor() {
        this.sessions = new Map();
        this.currentSession = null;
        this.storageKey = 'stripe_toolkit_sessions';
        this.maxSessionAge = 3600000; // 1 hour
        this.loadSessions();
    }

    /**
     * Create new session for checkout URL
     */
    createSession(checkoutUrl) {
        const sessionId = this.generateSessionId();
        const urlHash = this.hashUrl(checkoutUrl);
        
        const session = {
            id: sessionId,
            checkoutUrl: checkoutUrl,
            urlHash: urlHash,
            status: 'active',
            createdAt: Date.now(),
            updatedAt: Date.now(),
            expiresAt: Date.now() + this.maxSessionAge,
            
            // Fingerprint data
            fingerprint: null,
            fingerprintHash: null,
            
            // Headers
            headers: {},
            headersOrder: [],
            
            // Cookies
            cookies: {},
            cookieString: '',
            
            // Proxy
            proxy: null,
            
            // Checkout data
            checkoutData: {
                sessionId: null,
                publicKey: null,
                expectedAmount: null,
                currency: null,
                customerEmail: null,
                initChecksum: null,
                configId: null
            },
            
            // Payment data
            paymentData: {
                paymentMethodId: null,
                paymentIntentId: null,
                clientSecret: null
            },
            
            // Tokens
            tokens: {
                csrf: null,
                nonce: null,
                stripe: null,
                captcha: null
            },
            
            // Request/Response log
            requestLog: [],
            responseLog: [],
            
            // State
            state: {
                step: 'init',
                attempts: 0,
                lastError: null,
                requires3DS: false,
                requiresCaptcha: false
            }
        };

        this.sessions.set(sessionId, session);
        this.currentSession = session;
        this.saveSessions();
        
        console.log('[SESSION] Created new session:', sessionId);
        return session;
    }

    /**
     * Get session by checkout URL
     */
    getSessionByUrl(checkoutUrl) {
        const urlHash = this.hashUrl(checkoutUrl);
        
        for (const [id, session] of this.sessions) {
            if (session.urlHash === urlHash && session.status === 'active') {
                if (Date.now() < session.expiresAt) {
                    this.currentSession = session;
                    return session;
                } else {
                    // Session expired
                    session.status = 'expired';
                }
            }
        }
        
        return null;
    }

    /**
     * Get or create session for checkout URL
     */
    getOrCreateSession(checkoutUrl) {
        let session = this.getSessionByUrl(checkoutUrl);
        
        if (!session) {
            session = this.createSession(checkoutUrl);
        }
        
        return session;
    }

    /**
     * Update session data
     */
    updateSession(sessionId, updates) {
        const session = this.sessions.get(sessionId);
        
        if (!session) {
            console.error('[SESSION] Session not found:', sessionId);
            return null;
        }

        // Deep merge updates
        Object.keys(updates).forEach(key => {
            if (typeof updates[key] === 'object' && updates[key] !== null && !Array.isArray(updates[key])) {
                session[key] = { ...session[key], ...updates[key] };
            } else {
                session[key] = updates[key];
            }
        });

        session.updatedAt = Date.now();
        this.saveSessions();
        
        return session;
    }

    /**
     * Set session fingerprint
     */
    setFingerprint(sessionId, fingerprint, hash) {
        return this.updateSession(sessionId, {
            fingerprint: fingerprint,
            fingerprintHash: hash
        });
    }

    /**
     * Set session headers
     */
    setHeaders(sessionId, headers, order = null) {
        const headersOrder = order || Object.keys(headers);
        return this.updateSession(sessionId, {
            headers: headers,
            headersOrder: headersOrder
        });
    }

    /**
     * Set session cookies
     */
    setCookies(sessionId, cookies) {
        const cookieString = Object.entries(cookies)
            .map(([key, value]) => `${key}=${value}`)
            .join('; ');
            
        return this.updateSession(sessionId, {
            cookies: cookies,
            cookieString: cookieString
        });
    }

    /**
     * Set session proxy
     */
    setProxy(sessionId, proxy) {
        return this.updateSession(sessionId, { proxy: proxy });
    }

    /**
     * Set checkout data
     */
    setCheckoutData(sessionId, data) {
        return this.updateSession(sessionId, {
            checkoutData: data
        });
    }

    /**
     * Set payment data
     */
    setPaymentData(sessionId, data) {
        return this.updateSession(sessionId, {
            paymentData: data
        });
    }

    /**
     * Set tokens
     */
    setTokens(sessionId, tokens) {
        return this.updateSession(sessionId, {
            tokens: tokens
        });
    }

    /**
     * Update session state
     */
    updateState(sessionId, stateUpdates) {
        const session = this.sessions.get(sessionId);
        if (!session) return null;

        session.state = { ...session.state, ...stateUpdates };
        session.updatedAt = Date.now();
        this.saveSessions();
        
        return session;
    }

    /**
     * Log request
     */
    logRequest(sessionId, request) {
        const session = this.sessions.get(sessionId);
        if (!session) return;

        session.requestLog.push({
            timestamp: Date.now(),
            url: request.url,
            method: request.method,
            headers: request.headers,
            body: request.body
        });

        // Keep only last 50 requests
        if (session.requestLog.length > 50) {
            session.requestLog = session.requestLog.slice(-50);
        }

        this.saveSessions();
    }

    /**
     * Log response
     */
    logResponse(sessionId, response) {
        const session = this.sessions.get(sessionId);
        if (!session) return;

        session.responseLog.push({
            timestamp: Date.now(),
            status: response.status,
            headers: response.headers,
            body: response.body
        });

        // Keep only last 50 responses
        if (session.responseLog.length > 50) {
            session.responseLog = session.responseLog.slice(-50);
        }

        this.saveSessions();
    }

    /**
     * End session
     */
    endSession(sessionId, status = 'completed') {
        const session = this.sessions.get(sessionId);
        if (!session) return;

        session.status = status;
        session.updatedAt = Date.now();
        this.saveSessions();
        
        if (this.currentSession?.id === sessionId) {
            this.currentSession = null;
        }
        
        console.log('[SESSION] Ended session:', sessionId, status);
    }

    /**
     * Get current session
     */
    getCurrentSession() {
        return this.currentSession;
    }

    /**
     * Get all sessions
     */
    getAllSessions() {
        return Array.from(this.sessions.values());
    }

    /**
     * Get active sessions
     */
    getActiveSessions() {
        return this.getAllSessions().filter(s => s.status === 'active' && Date.now() < s.expiresAt);
    }

    /**
     * Clean expired sessions
     */
    cleanExpiredSessions() {
        const now = Date.now();
        let cleaned = 0;

        for (const [id, session] of this.sessions) {
            if (session.expiresAt < now || session.status === 'expired') {
                this.sessions.delete(id);
                cleaned++;
            }
        }

        if (cleaned > 0) {
            this.saveSessions();
            console.log('[SESSION] Cleaned expired sessions:', cleaned);
        }

        return cleaned;
    }

    /**
     * Save sessions to storage
     */
    saveSessions() {
        try {
            const data = {};
            for (const [id, session] of this.sessions) {
                data[id] = session;
            }
            localStorage.setItem(this.storageKey, JSON.stringify(data));
        } catch (e) {
            console.error('[SESSION] Failed to save sessions:', e);
        }
    }

    /**
     * Load sessions from storage
     */
    loadSessions() {
        try {
            const data = localStorage.getItem(this.storageKey);
            if (data) {
                const parsed = JSON.parse(data);
                for (const [id, session] of Object.entries(parsed)) {
                    this.sessions.set(id, session);
                }
                console.log('[SESSION] Loaded sessions:', this.sessions.size);
            }
        } catch (e) {
            console.error('[SESSION] Failed to load sessions:', e);
        }
    }

    /**
     * Export session to JSON
     */
    exportSession(sessionId) {
        const session = this.sessions.get(sessionId);
        if (!session) return null;
        return JSON.stringify(session, null, 2);
    }

    /**
     * Import session from JSON
     */
    importSession(json) {
        try {
            const session = JSON.parse(json);
            if (session.id) {
                this.sessions.set(session.id, session);
                this.saveSessions();
                return session;
            }
        } catch (e) {
            console.error('[SESSION] Failed to import session:', e);
        }
        return null;
    }

    /**
     * Generate session ID
     */
    generateSessionId() {
        return `sess_${Date.now()}_${Math.random().toString(36).substring(2, 15)}`;
    }

    /**
     * Hash URL for comparison
     */
    hashUrl(url) {
        // Extract checkout session ID from URL
        const match = url.match(/cs_[a-zA-Z0-9_]+/);
        if (match) {
            return match[0];
        }
        
        // Fallback to simple hash
        let hash = 0;
        for (let i = 0; i < url.length; i++) {
            const char = url.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return Math.abs(hash).toString(16);
    }

    /**
     * Get session stats
     */
    getStats() {
        const all = this.getAllSessions();
        const active = this.getActiveSessions();
        
        return {
            total: all.length,
            active: active.length,
            completed: all.filter(s => s.status === 'completed').length,
            failed: all.filter(s => s.status === 'failed').length,
            expired: all.filter(s => s.status === 'expired').length
        };
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.SessionManager = SessionManager;
}
