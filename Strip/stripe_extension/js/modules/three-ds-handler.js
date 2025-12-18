/**
 * 3D Secure (3DS) Handler Module
 * Handles 3DS v1.0 and v2.0 authentication
 * Includes OTP, redirect, and challenge handling
 */

class ThreeDSHandler {
    constructor(options = {}) {
        this.timeout = options.timeout || 60000;
        this.retries = options.retries || 3;
        this.autoRetry = options.autoRetry !== false;
        this.verbose = options.verbose !== false;
        this.currentChallenge = null;
    }

    /**
     * Detect if response requires 3DS
     */
    requires3DS(responseData) {
        try {
            if (typeof responseData === 'string') {
                responseData = JSON.parse(responseData);
            }

            // Check payment intent status
            if (responseData.paymentIntent?.status === 'requires_action') {
                return true;
            }

            // Check for next_action
            if (responseData.paymentIntent?.next_action) {
                return true;
            }

            // Check requires3DS flag
            if (responseData.requires3DS) {
                return true;
            }

            // Check confirmation status
            if (responseData.confirmation?.payment_status === 'requires_action') {
                return true;
            }

            // Check for 3DS indicators in error
            if (responseData.error?.code === 'card_declined' && 
                responseData.error?.decline_code === 'authentication_required') {
                return true;
            }

            return false;
        } catch (err) {
            return false;
        }
    }

    /**
     * Extract 3DS challenge details
     */
    extract3DSChallenge(responseData) {
        try {
            if (typeof responseData === 'string') {
                responseData = JSON.parse(responseData);
            }

            const challenge = {
                paymentIntentId: null,
                paymentIntentClientSecret: null,
                status: 'unknown',
                type: null,
                version: null,
                requiresOTP: false,
                requiresRedirect: false,
                requiresChallenge: false,
                redirectUrl: null,
                iframeUrl: null,
                acsUrl: null,
                creq: null,
                threeDSMethodUrl: null,
                transactionId: null,
                nextAction: null
            };

            // Extract from payment intent
            if (responseData.paymentIntent) {
                const pi = responseData.paymentIntent;
                challenge.paymentIntentId = pi.id;
                challenge.paymentIntentClientSecret = pi.client_secret;
                challenge.status = pi.status;

                if (pi.next_action) {
                    challenge.nextAction = pi.next_action.type;

                    // Redirect type (3DS v1.0)
                    if (pi.next_action.type === 'redirect_to_url') {
                        challenge.type = 'redirect';
                        challenge.version = '1.0';
                        challenge.redirectUrl = pi.next_action.redirect_to_url?.url;
                        challenge.requiresRedirect = true;
                    }

                    // Use Stripe SDK (3DS v2.0 or hCaptcha)
                    if (pi.next_action.type === 'use_stripe_sdk') {
                        const sdk = pi.next_action.use_stripe_sdk;
                        
                        if (sdk.type === 'three_d_secure_redirect') {
                            challenge.type = '3ds_redirect';
                            challenge.version = '2.0';
                            challenge.redirectUrl = sdk.stripe_js;
                            challenge.requiresRedirect = true;
                        } else if (sdk.stripe_js) {
                            challenge.type = 'stripe_sdk';
                            challenge.version = '2.0';
                            challenge.iframeUrl = sdk.stripe_js;
                            challenge.acsUrl = sdk.three_d_secure_2_source?.acs_url;
                            challenge.creq = sdk.three_d_secure_2_source?.creq;
                            challenge.requiresChallenge = true;
                        }
                    }
                }
            }

            // Extract from requires3DS
            if (responseData.requires3DS) {
                const r3ds = responseData.requires3DS;
                challenge.type = challenge.type || '3ds';
                
                if (r3ds.use_stripe_sdk?.stripe_js) {
                    const sdk = r3ds.use_stripe_sdk.stripe_js;
                    challenge.iframeUrl = sdk.source;
                    challenge.acsUrl = sdk.acs_url;
                    challenge.threeDSMethodUrl = sdk.three_ds_method_url;
                    challenge.transactionId = sdk.three_ds_server_trans_id;
                    challenge.requiresChallenge = true;
                }
            }

            // Determine if OTP is required
            if (challenge.redirectUrl?.includes('otp') || 
                challenge.redirectUrl?.includes('sms') ||
                challenge.redirectUrl?.includes('verify')) {
                challenge.requiresOTP = true;
            }

            this.currentChallenge = challenge;
            return challenge.requiresRedirect || challenge.requiresChallenge ? challenge : null;
        } catch (err) {
            this.log('Extract challenge error:', err.message);
            return null;
        }
    }

    /**
     * Handle 3DS challenge
     */
    async handle3DS(challenge) {
        if (!challenge) {
            return { success: false, error: 'No challenge provided' };
        }

        this.log('Handling 3DS challenge...');
        this.log('Type:', challenge.type);
        this.log('Version:', challenge.version);

        try {
            if (challenge.requiresRedirect) {
                return await this.handleRedirect(challenge);
            }

            if (challenge.requiresChallenge) {
                return await this.handleChallenge(challenge);
            }

            if (challenge.requiresOTP) {
                return await this.handleOTP(challenge);
            }

            return { success: false, error: 'Unknown challenge type' };
        } catch (err) {
            return { success: false, error: err.message };
        }
    }

    /**
     * Handle redirect-based 3DS
     */
    async handleRedirect(challenge) {
        this.log('Handling redirect 3DS...');

        if (!challenge.redirectUrl) {
            return { success: false, error: 'No redirect URL' };
        }

        try {
            // Open redirect URL in iframe or new window
            const result = await this.processRedirect(challenge.redirectUrl);
            return result;
        } catch (err) {
            return { success: false, error: err.message };
        }
    }

    /**
     * Process redirect URL
     */
    async processRedirect(url) {
        return new Promise((resolve) => {
            // Create hidden iframe
            const iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            iframe.id = '3ds-iframe';
            
            let resolved = false;

            iframe.onload = () => {
                try {
                    // Check if redirected back to success
                    const iframeUrl = iframe.contentWindow?.location?.href;
                    
                    if (iframeUrl?.includes('success') || 
                        iframeUrl?.includes('complete') ||
                        iframeUrl?.includes('return')) {
                        resolved = true;
                        iframe.remove();
                        resolve({ success: true, method: 'redirect' });
                    }
                } catch (e) {
                    // Cross-origin, can't access
                }
            };

            iframe.src = url;
            document.body.appendChild(iframe);

            // Timeout
            setTimeout(() => {
                if (!resolved) {
                    iframe.remove();
                    resolve({ success: false, error: 'Redirect timeout' });
                }
            }, this.timeout);
        });
    }

    /**
     * Handle challenge-based 3DS (v2.0)
     */
    async handleChallenge(challenge) {
        this.log('Handling 3DS v2.0 challenge...');

        try {
            // If ACS URL and creq available, submit challenge
            if (challenge.acsUrl && challenge.creq) {
                return await this.submitChallengeRequest(challenge);
            }

            // If iframe URL available, process iframe
            if (challenge.iframeUrl) {
                return await this.processIframe(challenge.iframeUrl);
            }

            return { success: false, error: 'Missing challenge data' };
        } catch (err) {
            return { success: false, error: err.message };
        }
    }

    /**
     * Submit challenge request to ACS
     */
    async submitChallengeRequest(challenge) {
        try {
            const response = await fetch(challenge.acsUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: new URLSearchParams({
                    creq: challenge.creq
                })
            });

            const html = await response.text();

            // Check for success indicators
            if (html.includes('success') || html.includes('authenticated')) {
                return { success: true, method: 'challenge' };
            }

            // Check for OTP form
            if (html.includes('otp') || html.includes('sms') || html.includes('code')) {
                return await this.handleOTPForm(html, challenge.acsUrl);
            }

            return { success: false, error: 'Challenge not completed' };
        } catch (err) {
            return { success: false, error: err.message };
        }
    }

    /**
     * Process iframe for 3DS
     */
    async processIframe(url) {
        return new Promise((resolve) => {
            const iframe = document.createElement('iframe');
            iframe.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);width:400px;height:600px;border:none;z-index:99999;background:white;';
            iframe.id = '3ds-challenge-iframe';

            let resolved = false;

            // Listen for messages from iframe
            const messageHandler = (event) => {
                if (event.data?.type === '3ds_complete' || 
                    event.data?.status === 'success' ||
                    event.data?.authenticated) {
                    resolved = true;
                    window.removeEventListener('message', messageHandler);
                    iframe.remove();
                    resolve({ success: true, method: 'iframe' });
                }
            };

            window.addEventListener('message', messageHandler);

            iframe.onload = () => {
                // Try to detect completion
                setTimeout(() => {
                    try {
                        const doc = iframe.contentDocument;
                        if (doc?.body?.innerText?.includes('success') ||
                            doc?.body?.innerText?.includes('authenticated')) {
                            resolved = true;
                            window.removeEventListener('message', messageHandler);
                            iframe.remove();
                            resolve({ success: true, method: 'iframe' });
                        }
                    } catch (e) {}
                }, 2000);
            };

            iframe.src = url;
            document.body.appendChild(iframe);

            // Timeout
            setTimeout(() => {
                if (!resolved) {
                    window.removeEventListener('message', messageHandler);
                    iframe.remove();
                    resolve({ success: false, error: 'Challenge timeout' });
                }
            }, this.timeout);
        });
    }

    /**
     * Handle OTP verification
     */
    async handleOTP(challenge) {
        this.log('Handling OTP verification...');

        // In real scenario, user would receive OTP
        // For automation, we simulate or wait for user input
        
        return new Promise((resolve) => {
            // Create OTP input modal
            const modal = this.createOTPModal((otp) => {
                modal.remove();
                this.verifyOTP(challenge, otp).then(resolve);
            });

            document.body.appendChild(modal);
        });
    }

    /**
     * Create OTP input modal
     */
    createOTPModal(callback) {
        const modal = document.createElement('div');
        modal.id = '3ds-otp-modal';
        modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:99999;';
        
        modal.innerHTML = `
            <div style="background:white;padding:30px;border-radius:10px;text-align:center;max-width:400px;">
                <h3 style="margin:0 0 20px;">3D Secure Verification</h3>
                <p style="margin:0 0 20px;color:#666;">Enter the OTP sent to your phone/email</p>
                <input type="text" id="3ds-otp-input" maxlength="6" style="width:200px;padding:15px;font-size:24px;text-align:center;border:2px solid #ddd;border-radius:5px;letter-spacing:10px;" placeholder="000000">
                <br><br>
                <button id="3ds-otp-submit" style="padding:15px 40px;background:#5469d4;color:white;border:none;border-radius:5px;cursor:pointer;font-size:16px;">Verify</button>
            </div>
        `;

        modal.querySelector('#3ds-otp-submit').onclick = () => {
            const otp = modal.querySelector('#3ds-otp-input').value;
            if (otp.length >= 4) {
                callback(otp);
            }
        };

        modal.querySelector('#3ds-otp-input').onkeypress = (e) => {
            if (e.key === 'Enter') {
                const otp = e.target.value;
                if (otp.length >= 4) {
                    callback(otp);
                }
            }
        };

        return modal;
    }

    /**
     * Verify OTP
     */
    async verifyOTP(challenge, otp) {
        this.log('Verifying OTP:', otp);

        try {
            // Submit OTP to verification endpoint
            const response = await fetch(challenge.redirectUrl || challenge.iframeUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: new URLSearchParams({
                    otp: otp,
                    code: otp,
                    verification_code: otp
                })
            });

            const data = await response.json().catch(() => response.text());

            if (response.ok || data.success || data.authenticated) {
                return { success: true, method: 'otp' };
            }

            return { success: false, error: 'OTP verification failed' };
        } catch (err) {
            return { success: false, error: err.message };
        }
    }

    /**
     * Handle OTP form from HTML
     */
    async handleOTPForm(html, acsUrl) {
        // Parse form action
        const formMatch = html.match(/<form[^>]*action="([^"]+)"/);
        const actionUrl = formMatch ? formMatch[1] : acsUrl;

        return new Promise((resolve) => {
            const modal = this.createOTPModal(async (otp) => {
                modal.remove();
                
                try {
                    const response = await fetch(actionUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded'
                        },
                        body: new URLSearchParams({
                            otp: otp,
                            code: otp
                        })
                    });

                    if (response.ok) {
                        resolve({ success: true, method: 'otp_form' });
                    } else {
                        resolve({ success: false, error: 'OTP verification failed' });
                    }
                } catch (err) {
                    resolve({ success: false, error: err.message });
                }
            });

            document.body.appendChild(modal);
        });
    }

    /**
     * Complete 3DS and confirm payment
     */
    async complete3DS(paymentIntentId, clientSecret) {
        this.log('Completing 3DS for payment intent:', paymentIntentId);

        try {
            // Use Stripe.js to confirm
            if (window.Stripe) {
                const stripe = window.Stripe;
                const result = await stripe.confirmCardPayment(clientSecret);
                
                if (result.error) {
                    return { success: false, error: result.error.message };
                }

                return { success: true, paymentIntent: result.paymentIntent };
            }

            // Manual confirmation
            const response = await fetch(`https://api.stripe.com/v1/payment_intents/${paymentIntentId}/confirm`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: new URLSearchParams({
                    client_secret: clientSecret
                })
            });

            const data = await response.json();

            if (data.status === 'succeeded') {
                return { success: true, paymentIntent: data };
            }

            return { success: false, error: data.error?.message || 'Confirmation failed' };
        } catch (err) {
            return { success: false, error: err.message };
        }
    }

    /**
     * Log message
     */
    log(...args) {
        if (this.verbose) {
            console.log('[3DS]', ...args);
        }
    }

    /**
     * Get current challenge
     */
    getCurrentChallenge() {
        return this.currentChallenge;
    }

    /**
     * Clear current challenge
     */
    clearChallenge() {
        this.currentChallenge = null;
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.ThreeDSHandler = ThreeDSHandler;
}
