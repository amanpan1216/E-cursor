document.addEventListener('DOMContentLoaded', () => {
    initClock();
    initMenu();
    loadAllSettings();
    setupEventListeners();
    loadHitLogs();
    loadStatistics();
});

function initClock() {
    function updateClock() {
        const now = new Date();
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const seconds = String(now.getSeconds()).padStart(2, '0');
        document.getElementById('digital-clock').textContent = `${hours}:${minutes}:${seconds}`;
        
        const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        document.getElementById('date-display').textContent = now.toLocaleDateString('en-US', options);
    }
    updateClock();
    setInterval(updateClock, 1000);
}

function initMenu() {
    const menuTrigger = document.getElementById('menu-trigger');
    const verticalMenu = document.getElementById('vertical-menu');
    const menuClose = document.getElementById('menu-close');
    const menuItems = document.querySelectorAll('.menu-item');
    const sections = document.querySelectorAll('.settings-section');
    const dashboard = document.getElementById('dashboard');
    const contentContainer = document.getElementById('content-container');

    menuTrigger.addEventListener('click', () => {
        verticalMenu.classList.toggle('active');
    });

    menuClose.addEventListener('click', () => {
        verticalMenu.classList.remove('active');
    });

    menuItems.forEach(item => {
        item.addEventListener('click', () => {
            const sectionId = item.dataset.section;
            
            menuItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            
            if (sectionId === 'dashboard') {
                dashboard.style.display = 'block';
                contentContainer.style.display = 'none';
            } else {
                dashboard.style.display = 'none';
                contentContainer.style.display = 'block';
                sections.forEach(s => s.style.display = 'none');
                document.getElementById(`${sectionId}-section`).style.display = 'block';
            }
            
            verticalMenu.classList.remove('active');
        });
    });
}

async function loadAllSettings() {
    const data = await chrome.storage.local.get([
        'cards', 'currentCardIndex', 'liveCards', 'deadCards',
        'settings', 'email', 'proxyList', 'autofillData'
    ]);
    
    if (data.cards) {
        const cardText = data.cards.map(c => `${c.number}|${c.expMonth}|${c.expYear}|${c.cvv}`).join('\n');
        document.getElementById('card-list-input').value = cardText;
        document.getElementById('card-count-display').textContent = data.cards.length;
        document.getElementById('cards-loaded').textContent = data.cards.length;
        
        if (data.cards[data.currentCardIndex || 0]) {
            const card = data.cards[data.currentCardIndex || 0];
            document.getElementById('current-card-display').textContent = 
                `${card.number.slice(0, 4)}****${card.number.slice(-4)}`;
        }
    }
    
    if (data.email) {
        document.getElementById('email-input').value = data.email;
        document.getElementById('current-email-display').textContent = data.email;
    }
    
    if (data.proxyList) {
        document.getElementById('proxy-input').value = data.proxyList.join('\n');
        if (data.proxyList.length > 0) {
            document.getElementById('current-proxy-display').textContent = 
                data.proxyList[0].split(':')[0] + ':****';
        }
    }
    
    const settings = data.settings || {};
    document.getElementById('proxy-enabled-toggle').checked = settings.proxyEnabled || false;
    document.getElementById('proxy-rotate-toggle').checked = settings.proxyRotate || false;
    document.getElementById('autofill-delay').value = settings.fillDelay || 500;
    document.getElementById('random-name-toggle').checked = settings.randomName || false;
    document.getElementById('random-address-toggle').checked = settings.randomAddress || false;
    document.getElementById('captcha-service').value = settings.captchaService || 'internal';
    document.getElementById('captcha-api-key').value = settings.captchaApiKey || '';
    
    // Load captcha auto-click toggles
    const autoCaptchaToggle = document.getElementById('auto-captcha-click-toggle');
    const autoRecaptchaToggle = document.getElementById('auto-recaptcha-click-toggle');
    if (autoCaptchaToggle) autoCaptchaToggle.checked = settings.autoCaptchaClick !== false;
    if (autoRecaptchaToggle) autoRecaptchaToggle.checked = settings.autoRecaptchaClick !== false;
    document.getElementById('sound-toggle').checked = settings.soundAlerts || false;
    document.getElementById('notification-toggle').checked = settings.notifications || false;
    document.getElementById('auto-detect-toggle').checked = settings.autoDetect !== false;
    document.getElementById('auto-fill-toggle').checked = settings.autoFill || false;
    document.getElementById('auto-submit-toggle').checked = settings.autoSubmit || false;
    document.getElementById('auto-next-toggle').checked = settings.autoNext || false;
    document.getElementById('verbose-toggle').checked = settings.verbose !== false;
    
    const autofill = data.autofillData || {};
    document.getElementById('autofill-name').value = autofill.name || '';
    document.getElementById('autofill-address').value = autofill.address || '';
    document.getElementById('autofill-city').value = autofill.city || '';
    document.getElementById('autofill-zip').value = autofill.zip || '';
    document.getElementById('autofill-country').value = autofill.country || 'US';
}

async function loadHitLogs() {
    const data = await chrome.storage.local.get(['hitLogs', 'liveCards', 'deadCards']);
    const container = document.getElementById('hit-logs-container');
    const liveCards = data.liveCards || [];
    const deadCards = data.deadCards || [];
    
    const allLogs = [
        ...liveCards.map(c => ({ ...c, type: 'live' })),
        ...deadCards.map(c => ({ ...c, type: 'dead' }))
    ].sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
    
    if (allLogs.length === 0) {
        container.innerHTML = '<div class="empty-logs">No hits yet</div>';
        return;
    }
    
    container.innerHTML = allLogs.slice(0, 50).map(log => `
        <div class="hit-log-item ${log.type}">
            <div class="hit-log-card">${log.number.slice(0, 6)}******${log.number.slice(-4)}</div>
            <div class="hit-log-status ${log.type}">${log.type.toUpperCase()}</div>
            <div class="hit-log-time">${log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : ''}</div>
            ${log.error ? `<div class="hit-log-error">${log.error}</div>` : ''}
        </div>
    `).join('');
}

async function loadStatistics() {
    const data = await chrome.storage.local.get(['liveCards', 'deadCards', 'cards']);
    const live = (data.liveCards || []).length;
    const dead = (data.deadCards || []).length;
    const total = live + dead;
    const rate = total > 0 ? ((live / total) * 100).toFixed(1) : 0;
    
    document.getElementById('success-count').textContent = live;
    document.getElementById('decline-count').textContent = dead;
    document.getElementById('attempt-count').textContent = total;
    document.getElementById('success-rate').textContent = `${rate}%`;
}

function setupEventListeners() {
    document.getElementById('save-cc').addEventListener('click', saveCards);
    document.getElementById('clear-cc').addEventListener('click', clearCards);
    document.getElementById('save-email').addEventListener('click', saveEmail);
    document.getElementById('generate-email').addEventListener('click', generateEmail);
    document.getElementById('save-proxy').addEventListener('click', saveProxy);
    document.getElementById('save-autofill').addEventListener('click', saveAutofill);
    document.getElementById('generate-billing').addEventListener('click', generateBilling);
    document.getElementById('save-captcha').addEventListener('click', saveCaptcha);
    document.getElementById('save-settings').addEventListener('click', saveAllSettings);
    document.getElementById('reset-settings').addEventListener('click', resetSettings);
    document.getElementById('clear-all-data').addEventListener('click', clearAllData);
    document.getElementById('copy-all-cards').addEventListener('click', copyLiveCards);
    document.getElementById('clear-hit-logs').addEventListener('click', clearHitLogs);
    document.getElementById('reset-stats-btn').addEventListener('click', resetStatistics);
    
    document.getElementById('mode-autohit').addEventListener('click', () => setMode('autohit'));
    document.getElementById('mode-bypass').addEventListener('click', () => setMode('bypass'));
    
    document.getElementById('card-list-input').addEventListener('input', (e) => {
        const lines = e.target.value.split('\n').filter(l => l.trim());
        document.getElementById('card-count-display').textContent = lines.length;
    });
}

function parseCard(cardString) {
    const cleaned = cardString.replace(/[\s\-]/g, '').trim();
    if (!cleaned) return null;
    
    const parts = cleaned.split('|');
    if (parts.length >= 4) {
        let expYear = parts[2];
        if (expYear.length === 2) expYear = '20' + expYear;
        
        return {
            number: parts[0],
            expMonth: parts[1].padStart(2, '0'),
            expYear: expYear,
            cvv: parts[3],
            raw: cleaned,
            status: 'pending'
        };
    }
    return null;
}

async function saveCards() {
    const input = document.getElementById('card-list-input').value;
    const lines = input.split('\n').filter(l => l.trim());
    const cards = lines.map(parseCard).filter(c => c !== null);
    
    await chrome.storage.local.set({ cards, currentCardIndex: 0 });
    document.getElementById('cards-loaded').textContent = cards.length;
    showNotification(`${cards.length} cards saved`, 'success');
}

async function clearCards() {
    if (confirm('Clear all cards?')) {
        await chrome.storage.local.set({ cards: [], currentCardIndex: 0 });
        document.getElementById('card-list-input').value = '';
        document.getElementById('card-count-display').textContent = '0';
        document.getElementById('cards-loaded').textContent = '0';
        showNotification('Cards cleared', 'success');
    }
}

async function saveEmail() {
    const email = document.getElementById('email-input').value;
    await chrome.storage.local.set({ email });
    document.getElementById('current-email-display').textContent = email;
    showNotification('Email saved', 'success');
}

function generateEmail() {
    const names = ['john', 'jane', 'mike', 'sarah', 'david', 'emma'];
    const domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'protonmail.com'];
    const name = names[Math.floor(Math.random() * names.length)];
    const domain = domains[Math.floor(Math.random() * domains.length)];
    const num = Math.floor(Math.random() * 9999);
    const email = `${name}${num}@${domain}`;
    document.getElementById('email-input').value = email;
}

async function saveProxy() {
    const input = document.getElementById('proxy-input').value;
    const proxyList = input.split('\n').filter(p => p.trim());
    const proxyEnabled = document.getElementById('proxy-enabled-toggle').checked;
    const proxyRotate = document.getElementById('proxy-rotate-toggle').checked;
    
    const data = await chrome.storage.local.get(['settings']);
    const settings = data.settings || {};
    settings.proxyEnabled = proxyEnabled;
    settings.proxyRotate = proxyRotate;
    
    await chrome.storage.local.set({ proxyList, settings });
    
    if (proxyList.length > 0) {
        document.getElementById('current-proxy-display').textContent = proxyList[0].split(':')[0] + ':****';
    }
    showNotification('Proxy settings saved', 'success');
}

async function saveAutofill() {
    const autofillData = {
        name: document.getElementById('autofill-name').value,
        address: document.getElementById('autofill-address').value,
        city: document.getElementById('autofill-city').value,
        zip: document.getElementById('autofill-zip').value,
        country: document.getElementById('autofill-country').value
    };
    
    const data = await chrome.storage.local.get(['settings']);
    const settings = data.settings || {};
    settings.fillDelay = parseInt(document.getElementById('autofill-delay').value) || 500;
    settings.randomName = document.getElementById('random-name-toggle').checked;
    settings.randomAddress = document.getElementById('random-address-toggle').checked;
    
    await chrome.storage.local.set({ autofillData, settings });
    showNotification('Autofill settings saved', 'success');
}

function generateBilling() {
    const firstNames = ['John', 'Jane', 'Michael', 'Sarah', 'David', 'Emily', 'Robert', 'Lisa'];
    const lastNames = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis'];
    const streets = ['Main St', 'Oak Ave', 'Park Rd', 'Cedar Ln', 'Elm St', 'Pine Dr'];
    const cities = ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix', 'Philadelphia'];
    
    const name = `${firstNames[Math.floor(Math.random() * firstNames.length)]} ${lastNames[Math.floor(Math.random() * lastNames.length)]}`;
    const address = `${Math.floor(Math.random() * 9999) + 1} ${streets[Math.floor(Math.random() * streets.length)]}`;
    const city = cities[Math.floor(Math.random() * cities.length)];
    const zip = String(Math.floor(Math.random() * 89999) + 10000);
    
    document.getElementById('autofill-name').value = name;
    document.getElementById('autofill-address').value = address;
    document.getElementById('autofill-city').value = city;
    document.getElementById('autofill-zip').value = zip;
    
    showNotification('Billing details generated', 'success');
}

async function saveCaptcha() {
    const data = await chrome.storage.local.get(['settings']);
    const settings = data.settings || {};
    settings.captchaService = document.getElementById('captcha-service').value;
    settings.captchaApiKey = document.getElementById('captcha-api-key').value;
    settings.autoCaptchaClick = document.getElementById('auto-captcha-click-toggle')?.checked ?? true;
    settings.autoRecaptchaClick = document.getElementById('auto-recaptcha-click-toggle')?.checked ?? true;
    
    await chrome.storage.local.set({ settings });
    chrome.runtime.sendMessage({ type: 'settingsUpdated', settings });
    showNotification('Captcha settings saved', 'success');
}

async function saveAllSettings() {
    const data = await chrome.storage.local.get(['settings']);
    const settings = data.settings || {};
    
    settings.soundAlerts = document.getElementById('sound-toggle').checked;
    settings.notifications = document.getElementById('notification-toggle').checked;
    settings.autoDetect = document.getElementById('auto-detect-toggle').checked;
    settings.autoFill = document.getElementById('auto-fill-toggle').checked;
    settings.autoSubmit = document.getElementById('auto-submit-toggle').checked;
    settings.autoNext = document.getElementById('auto-next-toggle').checked;
    settings.verbose = document.getElementById('verbose-toggle').checked;
    
    await chrome.storage.local.set({ settings });
    chrome.runtime.sendMessage({ type: 'settingsUpdated', settings });
    showNotification('All settings saved', 'success');
}

async function resetSettings() {
    if (confirm('Reset all settings to default?')) {
        const defaultSettings = {
            autoDetect: true,
            autoFill: false,
            autoSubmit: false,
            autoNext: false,
            fillDelay: 500,
            soundAlerts: false,
            notifications: false,
            verbose: true,
            proxyEnabled: false,
            proxyRotate: false,
            randomName: false,
            randomAddress: false,
            captchaService: 'internal',
            captchaApiKey: ''
        };
        
        await chrome.storage.local.set({ settings: defaultSettings });
        loadAllSettings();
        showNotification('Settings reset to default', 'success');
    }
}

async function clearAllData() {
    if (confirm('This will clear ALL data including cards, results, and settings. Continue?')) {
        await chrome.storage.local.clear();
        location.reload();
    }
}

async function copyLiveCards() {
    const data = await chrome.storage.local.get(['liveCards']);
    const liveCards = data.liveCards || [];
    const text = liveCards.map(c => `${c.number}|${c.expMonth}|${c.expYear}|${c.cvv}`).join('\n');
    
    if (text) {
        navigator.clipboard.writeText(text);
        showNotification(`${liveCards.length} live cards copied`, 'success');
    } else {
        showNotification('No live cards to copy', 'warning');
    }
}

async function clearHitLogs() {
    if (confirm('Clear all hit logs?')) {
        await chrome.storage.local.set({ liveCards: [], deadCards: [], hitLogs: [] });
        loadHitLogs();
        loadStatistics();
        showNotification('Hit logs cleared', 'success');
    }
}

async function resetStatistics() {
    if (confirm('Reset all statistics?')) {
        await chrome.storage.local.set({ liveCards: [], deadCards: [] });
        loadStatistics();
        loadHitLogs();
        showNotification('Statistics reset', 'success');
    }
}

function setMode(mode) {
    document.getElementById('mode-autohit').classList.toggle('active', mode === 'autohit');
    document.getElementById('mode-bypass').classList.toggle('active', mode === 'bypass');
    document.getElementById('current-mode').textContent = mode.toUpperCase();
    chrome.storage.local.set({ mode });
}

function showNotification(message, type) {
    const existing = document.querySelector('.notification');
    if (existing) existing.remove();
    
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

chrome.storage.onChanged.addListener((changes, namespace) => {
    if (namespace === 'local') {
        if (changes.liveCards || changes.deadCards) {
            loadHitLogs();
            loadStatistics();
        }
    }
});
