// Stripe Toolkit v3.0 - Background Service Worker

chrome.runtime.onInstalled.addListener((details) => {
    if (details.reason === 'install') {
        chrome.runtime.openOptionsPage();
        
        chrome.storage.local.set({
            settings: {
                autoDetect: true,
                autoFill: false,
                autoSubmit: false,
                autoNext: false,
                fillDelay: 500,
                captchaService: 'internal',
                captchaApiKey: '',
                proxyEnabled: false,
                soundAlerts: false,
                verbose: true,
                billingName: '',
                billingEmail: '',
                billingAddress: '',
                billingCity: '',
                billingZip: ''
            },
            cards: [],
            currentCardIndex: 0,
            liveCards: [],
            deadCards: []
        });
    }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    switch (message.type) {
        case 'checkoutDetected':
            handleCheckoutDetected(message);
            break;
        case 'cardResult':
            handleCardResult(message.result);
            break;
        case 'nextCard':
            handleNextCard();
            break;
        case 'startChecking':
            chrome.action.setBadgeText({ text: '...' });
            chrome.action.setBadgeBackgroundColor({ color: '#f39c12' });
            break;
        case 'stopChecking':
            chrome.action.setBadgeText({ text: '' });
            break;
    }
    return true;
});

async function handleCheckoutDetected(data) {
    chrome.notifications.create({
        type: 'basic',
        iconUrl: '../icons/icon128.png',
        title: 'Stripe Toolkit',
        message: 'Checkout page detected!'
    });
    
    chrome.action.setBadgeText({ text: 'ON' });
    chrome.action.setBadgeBackgroundColor({ color: '#4ecca3' });
}

async function handleCardResult(result) {
    const data = await chrome.storage.local.get(['cards', 'currentCardIndex', 'liveCards', 'deadCards']);
    const cards = data.cards || [];
    const currentIndex = data.currentCardIndex || 0;
    let liveCards = data.liveCards || [];
    let deadCards = data.deadCards || [];
    
    if (currentIndex < cards.length) {
        const card = cards[currentIndex];
        card.timestamp = Date.now();
        
        if (result.success || result.status === 'live') {
            card.status = 'live';
            liveCards.push({ ...card });
            
            chrome.notifications.create({
                type: 'basic',
                iconUrl: '../icons/icon128.png',
                title: '✓ LIVE CARD!',
                message: `${card.number.slice(0,4)}****${card.number.slice(-4)}`
            });
        } else {
            card.status = 'dead';
            card.error = result.error || 'Declined';
            deadCards.push({ ...card });
        }
        
        cards[currentIndex] = card;
        await chrome.storage.local.set({ cards, liveCards, deadCards });
    }
}

async function handleNextCard() {
    const data = await chrome.storage.local.get(['cards', 'currentCardIndex']);
    let currentIndex = data.currentCardIndex || 0;
    
    if (currentIndex < (data.cards || []).length - 1) {
        currentIndex++;
        await chrome.storage.local.set({ currentCardIndex: currentIndex });
    } else {
        chrome.action.setBadgeText({ text: 'END' });
        chrome.action.setBadgeBackgroundColor({ color: '#e74c3c' });
    }
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && tab.url) {
        if (tab.url.includes('checkout.stripe.com') || 
            tab.url.includes('cs_live_') || 
            tab.url.includes('cs_test_')) {
            chrome.action.setBadgeText({ text: 'ON', tabId: tabId });
            chrome.action.setBadgeBackgroundColor({ color: '#4ecca3', tabId: tabId });
        }
    }
});

console.log('[Stripe Toolkit] Background initialized');
