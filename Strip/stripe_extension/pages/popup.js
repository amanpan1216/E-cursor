/**
 * Popup Script
 * Handles UI interactions and communication with content/background scripts
 */

document.addEventListener('DOMContentLoaded', () => {
    // Initialize
    initTabs();
    loadCheckoutInfo();
    loadSessionInfo();
    loadResults();
    loadSettings();
    setupEventListeners();
});

/**
 * Initialize tab switching
 */
function initTabs() {
    const tabs = document.querySelectorAll('.tab');
    const contents = document.querySelectorAll('.tab-content');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetTab = tab.dataset.tab;

            // Update active states
            tabs.forEach(t => t.classList.remove('active'));
            contents.forEach(c => c.classList.remove('active'));

            tab.classList.add('active');
            document.getElementById(`${targetTab}-tab`).classList.add('active');
        });
    });

    // Initialize collapsible sections
    document.querySelectorAll('.collapsible-header').forEach(header => {
        header.addEventListener('click', () => {
            header.parentElement.classList.toggle('collapsed');
        });
    });
}

/**
 * Load checkout info from current tab
 */
async function loadCheckoutInfo() {
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        
        if (!tab.url?.includes('checkout.stripe.com')) {
            updateStatus('Not on Stripe Checkout', 'warning');
            return;
        }

        updateStatus('Connected', 'success');

        const response = await chrome.tabs.sendMessage(tab.id, { action: 'getInfo' });
        
        if (response) {
            document.getElementById('info-session-id').textContent = response.sessionId || '-';
            document.getElementById('info-amount').textContent = response.amount || '-';
            document.getElementById('info-merchant').textContent = response.merchantName || '-';
        }
    } catch (err) {
        console.error('Error loading checkout info:', err);
        updateStatus('Error', 'error');
    }
}

/**
 * Load session info
 */
async function loadSessionInfo() {
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        
        // Get session from content script
        const session = await chrome.tabs.sendMessage(tab.id, { action: 'getSession' });
        
        if (session) {
            document.getElementById('session-id').textContent = session.id || '-';
            document.getElementById('session-status').textContent = session.status || '-';
            document.getElementById('session-status').className = `badge ${session.status}`;
            document.getElementById('session-created').textContent = 
                session.createdAt ? new Date(session.createdAt).toLocaleString() : '-';
        }

        // Get fingerprint
        const fingerprint = await chrome.tabs.sendMessage(tab.id, { action: 'getFingerprint' });
        
        if (fingerprint) {
            document.getElementById('fingerprint-hash').textContent = 
                fingerprint.fingerprintHash?.substring(0, 16) + '...' || '-';
            document.getElementById('fingerprint-browser').textContent = 
                fingerprint.profile?.browser || '-';
            document.getElementById('fingerprint-platform').textContent = 
                fingerprint.profile?.platform || '-';
        }

        // Get headers
        const headers = await chrome.tabs.sendMessage(tab.id, { action: 'getHeaders' });
        
        if (headers) {
            document.getElementById('headers-display').textContent = 
                JSON.stringify(headers, null, 2);
        }

        // Get cookies
        const cookies = await chrome.tabs.sendMessage(tab.id, { action: 'getCookies' });
        
        if (cookies) {
            document.getElementById('cookies-display').textContent = 
                JSON.stringify(cookies, null, 2);
        }
    } catch (err) {
        console.error('Error loading session info:', err);
    }
}

/**
 * Load results from background
 */
async function loadResults() {
    try {
        const results = await chrome.runtime.sendMessage({ type: 'getResults' });
        
        const resultsList = document.getElementById('results-list');
        
        if (!results || results.length === 0) {
            resultsList.innerHTML = '<div class="empty-state">No results yet</div>';
            return;
        }

        resultsList.innerHTML = results.slice(-20).reverse().map(result => `
            <div class="result-item ${result.type}">
                <div class="result-header">
                    <span class="result-type">${result.type === 'success' ? '✓' : '✗'}</span>
                    <span class="result-time">${new Date(result.timestamp).toLocaleTimeString()}</span>
                </div>
                <div class="result-details">
                    ${result.type === 'success' 
                        ? `Payment: ${result.paymentIntent || 'N/A'}`
                        : `Error: ${result.error?.decline_code || result.error?.message || 'Unknown'}`
                    }
                </div>
            </div>
        `).join('');

        // Update stats
        const total = results.length;
        const success = results.filter(r => r.type === 'success').length;
        const declined = results.filter(r => r.type === 'decline').length;

        document.getElementById('stat-total').textContent = total;
        document.getElementById('stat-success').textContent = success;
        document.getElementById('stat-declined').textContent = declined;
    } catch (err) {
        console.error('Error loading results:', err);
    }
}

/**
 * Load settings from background
 */
async function loadSettings() {
    try {
        const settings = await chrome.runtime.sendMessage({ type: 'getSettings' });
        
        if (settings) {
            document.getElementById('captcha-service').value = settings.captchaService || 'internal';
            document.getElementById('captcha-api-key').value = settings.captchaApiKey || '';
            document.getElementById('proxy-enabled').checked = settings.proxyEnabled || false;
            document.getElementById('proxy-list').value = (settings.proxyList || []).join('\n');
            document.getElementById('auto-fill-enabled').checked = settings.autoFillEnabled || false;
            document.getElementById('verbose-logging').checked = settings.verbose !== false;
        }
    } catch (err) {
        console.error('Error loading settings:', err);
    }
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
    // Refresh info button
    document.getElementById('refresh-info').addEventListener('click', loadCheckoutInfo);

    // Fill card button
    document.getElementById('fill-card').addEventListener('click', async () => {
        const card = document.getElementById('card-input').value;
        
        if (!card) {
            showNotification('Please enter card details', 'error');
            return;
        }

        try {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            const response = await chrome.tabs.sendMessage(tab.id, { 
                action: 'fillCard', 
                card: card 
            });
            
            if (response.success) {
                showNotification('Card filled successfully', 'success');
            } else {
                showNotification('Failed to fill card', 'error');
            }
        } catch (err) {
            showNotification('Error: ' + err.message, 'error');
        }
    });

    // Process checkout button
    document.getElementById('process-checkout').addEventListener('click', async () => {
        const card = document.getElementById('card-input').value;
        
        if (!card) {
            showNotification('Please enter card details', 'error');
            return;
        }

        const billing = {
            name: document.getElementById('billing-name').value,
            email: document.getElementById('billing-email').value,
            address: {
                line1: document.getElementById('billing-address').value,
                city: document.getElementById('billing-city').value,
                postalCode: document.getElementById('billing-zip').value,
                country: 'US'
            }
        };

        try {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            
            updateStatus('Processing...', 'warning');
            
            const response = await chrome.tabs.sendMessage(tab.id, { 
                action: 'processCheckout', 
                card: card,
                billing: billing
            });
            
            if (response.success) {
                showNotification('Payment successful!', 'success');
                updateStatus('Success', 'success');
            } else if (response.requires3DS) {
                showNotification('3DS verification required', 'warning');
                updateStatus('3DS Required', 'warning');
            } else {
                showNotification(`Failed: ${response.error || response.declineCode || 'Unknown error'}`, 'error');
                updateStatus('Failed', 'error');
            }
            
            loadResults();
        } catch (err) {
            showNotification('Error: ' + err.message, 'error');
            updateStatus('Error', 'error');
        }
    });

    // Generate billing button
    document.getElementById('generate-billing').addEventListener('click', () => {
        const firstNames = ['John', 'Jane', 'Michael', 'Sarah', 'David', 'Emily'];
        const lastNames = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia'];
        const cities = ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix'];
        
        const name = `${firstNames[Math.floor(Math.random() * firstNames.length)]} ${lastNames[Math.floor(Math.random() * lastNames.length)]}`;
        const email = `${name.toLowerCase().replace(' ', '.')}${Math.floor(Math.random() * 999)}@gmail.com`;
        const address = `${Math.floor(Math.random() * 9999) + 1} Main St`;
        const city = cities[Math.floor(Math.random() * cities.length)];
        const zip = String(Math.floor(Math.random() * 89999) + 10000);

        document.getElementById('billing-name').value = name;
        document.getElementById('billing-email').value = email;
        document.getElementById('billing-address').value = address;
        document.getElementById('billing-city').value = city;
        document.getElementById('billing-zip').value = zip;

        showNotification('Billing details generated', 'success');
    });

    // Regenerate fingerprint button
    document.getElementById('regenerate-fingerprint').addEventListener('click', async () => {
        try {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            await chrome.tabs.sendMessage(tab.id, { action: 'regenerateFingerprint' });
            loadSessionInfo();
            showNotification('Fingerprint regenerated', 'success');
        } catch (err) {
            showNotification('Error: ' + err.message, 'error');
        }
    });

    // Copy headers button
    document.getElementById('copy-headers').addEventListener('click', () => {
        const headers = document.getElementById('headers-display').textContent;
        navigator.clipboard.writeText(headers);
        showNotification('Headers copied', 'success');
    });

    // Copy cookies button
    document.getElementById('copy-cookies').addEventListener('click', () => {
        const cookies = document.getElementById('cookies-display').textContent;
        navigator.clipboard.writeText(cookies);
        showNotification('Cookies copied', 'success');
    });

    // Clear results button
    document.getElementById('clear-results').addEventListener('click', async () => {
        await chrome.runtime.sendMessage({ type: 'clearResults' });
        loadResults();
        showNotification('Results cleared', 'success');
    });

    // Save settings button
    document.getElementById('save-settings').addEventListener('click', async () => {
        const settings = {
            captchaService: document.getElementById('captcha-service').value,
            captchaApiKey: document.getElementById('captcha-api-key').value,
            proxyEnabled: document.getElementById('proxy-enabled').checked,
            proxyList: document.getElementById('proxy-list').value.split('\n').filter(p => p.trim()),
            autoFillEnabled: document.getElementById('auto-fill-enabled').checked,
            verbose: document.getElementById('verbose-logging').checked
        };

        await chrome.runtime.sendMessage({ type: 'saveSettings', data: settings });
        showNotification('Settings saved', 'success');
    });
}

/**
 * Update status indicator
 */
function updateStatus(text, type = 'info') {
    const status = document.getElementById('status');
    const dot = status.querySelector('.status-dot');
    const textEl = status.querySelector('.status-text');

    textEl.textContent = text;
    dot.className = `status-dot ${type}`;
}

/**
 * Show notification
 */
function showNotification(message, type = 'info') {
    // Remove existing notifications
    document.querySelectorAll('.notification').forEach(n => n.remove());

    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);

    // Remove after 3 seconds
    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}
