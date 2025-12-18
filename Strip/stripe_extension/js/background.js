/**
 * Background Service Worker
 * Handles extension lifecycle, storage, and cross-tab communication
 */

// Storage for sessions and results
let sessions = {};
let results = [];
let settings = {
    autoFillEnabled: false,
    captchaApiKey: '',
    captchaService: '2captcha',
    proxyEnabled: false,
    proxyList: [],
    verbose: true
};

/**
 * Initialize extension
 */
chrome.runtime.onInstalled.addListener(() => {
    console.log('[BACKGROUND] Stripe Toolkit installed');
    
    // Load settings from storage
    chrome.storage.local.get(['settings', 'sessions', 'results'], (data) => {
        if (data.settings) settings = { ...settings, ...data.settings };
        if (data.sessions) sessions = data.sessions;
        if (data.results) results = data.results;
    });
});

/**
 * Listen for messages from content scripts
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    const tabId = sender.tab?.id;
    
    switch (message.type) {
        case 'initialized':
            handleInitialized(tabId, message.data);
            break;
            
        case 'response':
            handleResponse(tabId, message.data);
            break;
            
        case 'captcha':
            handleCaptcha(tabId, message.data);
            break;
            
        case '3ds':
            handle3DS(tabId, message.data);
            break;
            
        case 'success':
            handleSuccess(tabId, message.data);
            break;
            
        case 'decline':
            handleDecline(tabId, message.data);
            break;
            
        case 'getSettings':
            sendResponse(settings);
            break;
            
        case 'saveSettings':
            saveSettings(message.data);
            sendResponse({ success: true });
            break;
            
        case 'getSessions':
            sendResponse(sessions);
            break;
            
        case 'getResults':
            sendResponse(results);
            break;
            
        case 'clearResults':
            results = [];
            saveResults();
            sendResponse({ success: true });
            break;
            
        default:
            console.log('[BACKGROUND] Unknown message type:', message.type);
    }
    
    return true; // Keep channel open for async responses
});

/**
 * Handle content script initialization
 */
function handleInitialized(tabId, data) {
    console.log('[BACKGROUND] Tab initialized:', tabId, data.url);
    
    sessions[tabId] = {
        url: data.url,
        sessionId: data.sessionId,
        status: 'active',
        startTime: Date.now()
    };
    
    saveSessions();
    
    // Update badge
    chrome.action.setBadgeText({ text: 'ON', tabId: tabId });
    chrome.action.setBadgeBackgroundColor({ color: '#22c55e', tabId: tabId });
}

/**
 * Handle Stripe API response
 */
function handleResponse(tabId, data) {
    console.log('[BACKGROUND] Response from tab:', tabId);
    
    if (sessions[tabId]) {
        sessions[tabId].lastResponse = data;
        sessions[tabId].lastActivity = Date.now();
        saveSessions();
    }
}

/**
 * Handle captcha event
 */
function handleCaptcha(tabId, data) {
    console.log('[BACKGROUND] Captcha event:', tabId, data.result?.success);
    
    if (sessions[tabId]) {
        sessions[tabId].captchaRequired = true;
        sessions[tabId].captchaSolved = data.result?.success;
        saveSessions();
    }
    
    // Update badge
    chrome.action.setBadgeText({ text: 'CAP', tabId: tabId });
    chrome.action.setBadgeBackgroundColor({ color: '#f59e0b', tabId: tabId });
}

/**
 * Handle 3DS event
 */
function handle3DS(tabId, data) {
    console.log('[BACKGROUND] 3DS event:', tabId, data.result?.success);
    
    if (sessions[tabId]) {
        sessions[tabId].threeDSRequired = true;
        sessions[tabId].threeDSCompleted = data.result?.success;
        saveSessions();
    }
    
    // Update badge
    chrome.action.setBadgeText({ text: '3DS', tabId: tabId });
    chrome.action.setBadgeBackgroundColor({ color: '#8b5cf6', tabId: tabId });
}

/**
 * Handle success event
 */
function handleSuccess(tabId, data) {
    console.log('[BACKGROUND] Payment success:', tabId);
    
    // Add to results
    results.push({
        type: 'success',
        tabId: tabId,
        url: sessions[tabId]?.url,
        paymentIntent: data.paymentIntent?.id,
        timestamp: Date.now()
    });
    
    // Keep only last 100 results
    if (results.length > 100) {
        results = results.slice(-100);
    }
    
    saveResults();
    
    // Update session
    if (sessions[tabId]) {
        sessions[tabId].status = 'success';
        sessions[tabId].endTime = Date.now();
        saveSessions();
    }
    
    // Update badge
    chrome.action.setBadgeText({ text: '✓', tabId: tabId });
    chrome.action.setBadgeBackgroundColor({ color: '#22c55e', tabId: tabId });
    
    // Show notification
    chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icons/icon128.png',
        title: 'Payment Successful',
        message: `Payment completed on ${sessions[tabId]?.url || 'Stripe Checkout'}`
    });
}

/**
 * Handle decline event
 */
function handleDecline(tabId, data) {
    console.log('[BACKGROUND] Payment declined:', tabId, data.error?.decline_code);
    
    // Add to results
    results.push({
        type: 'decline',
        tabId: tabId,
        url: sessions[tabId]?.url,
        error: data.error,
        timestamp: Date.now()
    });
    
    saveResults();
    
    // Update session
    if (sessions[tabId]) {
        sessions[tabId].status = 'declined';
        sessions[tabId].error = data.error;
        sessions[tabId].endTime = Date.now();
        saveSessions();
    }
    
    // Update badge
    chrome.action.setBadgeText({ text: '✗', tabId: tabId });
    chrome.action.setBadgeBackgroundColor({ color: '#ef4444', tabId: tabId });
}

/**
 * Save settings to storage
 */
function saveSettings(newSettings) {
    settings = { ...settings, ...newSettings };
    chrome.storage.local.set({ settings: settings });
}

/**
 * Save sessions to storage
 */
function saveSessions() {
    chrome.storage.local.set({ sessions: sessions });
}

/**
 * Save results to storage
 */
function saveResults() {
    chrome.storage.local.set({ results: results });
}

/**
 * Handle tab close
 */
chrome.tabs.onRemoved.addListener((tabId) => {
    if (sessions[tabId]) {
        sessions[tabId].status = 'closed';
        sessions[tabId].endTime = Date.now();
        saveSessions();
    }
});

/**
 * Handle extension icon click
 */
chrome.action.onClicked.addListener((tab) => {
    // Open popup or options page
    chrome.action.openPopup();
});

/**
 * Context menu setup
 */
chrome.runtime.onInstalled.addListener(() => {
    chrome.contextMenus.create({
        id: 'stripe-toolkit-fill',
        title: 'Fill Card Details',
        contexts: ['page'],
        documentUrlPatterns: ['https://checkout.stripe.com/*']
    });
    
    chrome.contextMenus.create({
        id: 'stripe-toolkit-extract',
        title: 'Extract Checkout Info',
        contexts: ['page'],
        documentUrlPatterns: ['https://checkout.stripe.com/*']
    });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
    if (info.menuItemId === 'stripe-toolkit-fill') {
        chrome.tabs.sendMessage(tab.id, { action: 'showFillDialog' });
    } else if (info.menuItemId === 'stripe-toolkit-extract') {
        chrome.tabs.sendMessage(tab.id, { action: 'getInfo' }, (response) => {
            console.log('[BACKGROUND] Checkout info:', response);
        });
    }
});

console.log('[BACKGROUND] Service worker started');
