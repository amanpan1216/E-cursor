document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    loadCards();
    loadCheckoutInfo();
    loadResults();
    loadSettings();
    setupEventListeners();
    updateStatus();
});

let cards = [];
let currentCardIndex = 0;
let isChecking = false;
let liveCards = [];
let deadCards = [];

function initTabs() {
    const tabs = document.querySelectorAll('.tab');
    const contents = document.querySelectorAll('.tab-content');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetTab = tab.dataset.tab;
            tabs.forEach(t => t.classList.remove('active'));
            contents.forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(`${targetTab}-tab`).classList.add('active');
        });
    });

    document.querySelectorAll('.collapsible-header').forEach(header => {
        header.addEventListener('click', () => {
            header.parentElement.classList.toggle('collapsed');
        });
    });
}

async function loadCards() {
    const data = await chrome.storage.local.get(['cards', 'currentCardIndex', 'liveCards', 'deadCards']);
    cards = data.cards || [];
    currentCardIndex = data.currentCardIndex || 0;
    liveCards = data.liveCards || [];
    deadCards = data.deadCards || [];
    renderCardList();
    updateCurrentCard();
    updateProgress();
}

function parseCard(cardString) {
    const cleaned = cardString.replace(/[\s\-]/g, '').trim();
    if (!cleaned) return null;
    
    const parts = cleaned.split('|');
    if (parts.length >= 4) {
        let expMonth = parts[1];
        let expYear = parts[2];
        
        if (expYear.length === 2) {
            expYear = '20' + expYear;
        }
        
        return {
            number: parts[0],
            expMonth: expMonth.padStart(2, '0'),
            expYear: expYear,
            cvv: parts[3],
            raw: cleaned,
            status: 'pending'
        };
    }
    return null;
}

function renderCardList() {
    const cardList = document.getElementById('card-list');
    document.getElementById('card-count').textContent = cards.length;
    
    if (cards.length === 0) {
        cardList.innerHTML = '<div class="empty-state">No cards saved</div>';
        return;
    }
    
    cardList.innerHTML = cards.map((card, index) => `
        <div class="card-item ${card.status} ${index === currentCardIndex ? 'current' : ''}" data-index="${index}">
            <div class="card-info">
                <span class="card-num">${maskCard(card.number)}</span>
                <span class="card-exp">${card.expMonth}/${card.expYear.slice(-2)}</span>
            </div>
            <div class="card-actions">
                <span class="card-status-badge ${card.status}">${card.status}</span>
                <button class="btn-icon delete-card" data-index="${index}">×</button>
            </div>
        </div>
    `).join('');
    
    cardList.querySelectorAll('.delete-card').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            deleteCard(parseInt(btn.dataset.index));
        });
    });
    
    cardList.querySelectorAll('.card-item').forEach(item => {
        item.addEventListener('click', () => {
            currentCardIndex = parseInt(item.dataset.index);
            saveCards();
            renderCardList();
            updateCurrentCard();
        });
    });
}

function maskCard(number) {
    if (number.length < 8) return number;
    return number.slice(0, 4) + ' **** **** ' + number.slice(-4);
}

function updateCurrentCard() {
    const card = cards[currentCardIndex];
    if (card) {
        document.getElementById('current-card-number').textContent = formatCardNumber(card.number);
        document.getElementById('current-card-exp').textContent = `${card.expMonth}/${card.expYear.slice(-2)}`;
        document.getElementById('current-card-cvv').textContent = card.cvv;
        document.getElementById('current-card-status').textContent = card.status;
        document.getElementById('current-card-status').className = `card-status ${card.status}`;
    } else {
        document.getElementById('current-card-number').textContent = '---- ---- ---- ----';
        document.getElementById('current-card-exp').textContent = '--/--';
        document.getElementById('current-card-cvv').textContent = '---';
        document.getElementById('current-card-status').textContent = 'No card';
    }
}

function formatCardNumber(number) {
    return number.replace(/(\d{4})/g, '$1 ').trim();
}

function updateProgress() {
    const total = cards.length;
    const checked = liveCards.length + deadCards.length;
    const progress = total > 0 ? (checked / total) * 100 : 0;
    
    document.getElementById('progress-fill').style.width = `${progress}%`;
    document.getElementById('checked-count').textContent = checked;
    document.getElementById('live-count').textContent = liveCards.length;
    document.getElementById('dead-count').textContent = deadCards.length;
    document.getElementById('stat-total').textContent = total;
    document.getElementById('stat-live').textContent = liveCards.length;
    document.getElementById('stat-dead').textContent = deadCards.length;
}

async function saveCards() {
    await chrome.storage.local.set({ 
        cards, 
        currentCardIndex,
        liveCards,
        deadCards
    });
}

function deleteCard(index) {
    cards.splice(index, 1);
    if (currentCardIndex >= cards.length) {
        currentCardIndex = Math.max(0, cards.length - 1);
    }
    saveCards();
    renderCardList();
    updateCurrentCard();
}

async function loadCheckoutInfo() {
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        
        if (tab.url?.includes('checkout.stripe.com') || tab.url?.includes('stripe.com')) {
            setStatus('Connected', 'success');
            
            const response = await chrome.tabs.sendMessage(tab.id, { action: 'getInfo' });
            if (response) {
                document.getElementById('info-url').textContent = tab.url.substring(0, 40) + '...';
                document.getElementById('info-session-id').textContent = response.sessionId || '-';
                document.getElementById('info-amount').textContent = response.amount || '-';
                document.getElementById('info-merchant').textContent = response.merchantName || '-';
            }
        } else {
            setStatus('Not on checkout', 'warning');
        }
    } catch (err) {
        setStatus('Error', 'error');
    }
}

function loadResults() {
    renderLiveList();
    renderDeadList();
}

function renderLiveList() {
    const liveList = document.getElementById('live-list');
    if (liveCards.length === 0) {
        liveList.innerHTML = '<div class="empty-state">No live cards yet</div>';
        return;
    }
    
    liveList.innerHTML = liveCards.map(card => `
        <div class="result-item success">
            <span class="result-card">${card.number}|${card.expMonth}|${card.expYear}|${card.cvv}</span>
            <span class="result-time">${new Date(card.timestamp).toLocaleTimeString()}</span>
        </div>
    `).join('');
}

function renderDeadList() {
    const deadList = document.getElementById('dead-list');
    if (deadCards.length === 0) {
        deadList.innerHTML = '<div class="empty-state">No dead cards yet</div>';
        return;
    }
    
    deadList.innerHTML = deadCards.slice(-20).map(card => `
        <div class="result-item decline">
            <span class="result-card">${maskCard(card.number)}</span>
            <span class="result-error">${card.error || 'Declined'}</span>
        </div>
    `).join('');
}

async function loadSettings() {
    const data = await chrome.storage.local.get(['settings']);
    const settings = data.settings || {};
    
    document.getElementById('auto-detect').checked = settings.autoDetect !== false;
    document.getElementById('auto-fill-enabled').checked = settings.autoFill || false;
    document.getElementById('auto-submit').checked = settings.autoSubmit || false;
    document.getElementById('fill-delay').value = settings.fillDelay || 500;
    document.getElementById('captcha-service').value = settings.captchaService || 'internal';
    document.getElementById('captcha-api-key').value = settings.captchaApiKey || '';
    document.getElementById('proxy-enabled').checked = settings.proxyEnabled || false;
    document.getElementById('proxy-list').value = (settings.proxyList || []).join('\n');
    document.getElementById('verbose-logging').checked = settings.verbose !== false;
    document.getElementById('sound-alerts').checked = settings.soundAlerts || false;
    
    document.getElementById('billing-name').value = settings.billingName || '';
    document.getElementById('billing-email').value = settings.billingEmail || '';
    document.getElementById('billing-address').value = settings.billingAddress || '';
    document.getElementById('billing-city').value = settings.billingCity || '';
    document.getElementById('billing-zip').value = settings.billingZip || '';
}

function setupEventListeners() {
    document.getElementById('add-cards').addEventListener('click', () => {
        const input = document.getElementById('cards-input').value;
        const lines = input.split('\n').filter(line => line.trim());
        let added = 0;
        
        lines.forEach(line => {
            const card = parseCard(line);
            if (card) {
                const exists = cards.some(c => c.number === card.number);
                if (!exists) {
                    cards.push(card);
                    added++;
                }
            }
        });
        
        if (added > 0) {
            saveCards();
            renderCardList();
            showNotification(`${added} cards added`, 'success');
            document.getElementById('cards-input').value = '';
        } else {
            showNotification('No valid cards to add', 'error');
        }
    });
    
    document.getElementById('clear-input').addEventListener('click', () => {
        document.getElementById('cards-input').value = '';
    });
    
    document.getElementById('clear-cards').addEventListener('click', () => {
        if (confirm('Clear all saved cards?')) {
            cards = [];
            currentCardIndex = 0;
            saveCards();
            renderCardList();
            updateCurrentCard();
            showNotification('All cards cleared', 'success');
        }
    });
    
    document.getElementById('start-checking').addEventListener('click', startChecking);
    document.getElementById('stop-checking').addEventListener('click', stopChecking);
    
    document.getElementById('fill-current').addEventListener('click', async () => {
        const card = cards[currentCardIndex];
        if (!card) {
            showNotification('No card selected', 'error');
            return;
        }
        
        try {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            await chrome.tabs.sendMessage(tab.id, { 
                action: 'fillCard', 
                card: card
            });
            showNotification('Card filled', 'success');
        } catch (err) {
            showNotification('Error: ' + err.message, 'error');
        }
    });
    
    document.getElementById('next-card').addEventListener('click', () => {
        if (currentCardIndex < cards.length - 1) {
            currentCardIndex++;
            saveCards();
            renderCardList();
            updateCurrentCard();
        } else {
            showNotification('No more cards', 'warning');
        }
    });
    
    document.getElementById('refresh-info').addEventListener('click', loadCheckoutInfo);
    
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
        
        showNotification('Billing generated', 'success');
    });
    
    document.getElementById('copy-live').addEventListener('click', () => {
        const text = liveCards.map(c => `${c.number}|${c.expMonth}|${c.expYear}|${c.cvv}`).join('\n');
        navigator.clipboard.writeText(text);
        showNotification('Live cards copied', 'success');
    });
    
    document.getElementById('copy-dead').addEventListener('click', () => {
        const text = deadCards.map(c => `${c.number}|${c.expMonth}|${c.expYear}|${c.cvv}`).join('\n');
        navigator.clipboard.writeText(text);
        showNotification('Dead cards copied', 'success');
    });
    
    document.getElementById('clear-results').addEventListener('click', () => {
        if (confirm('Clear all results?')) {
            liveCards = [];
            deadCards = [];
            cards.forEach(c => c.status = 'pending');
            saveCards();
            renderLiveList();
            renderDeadList();
            renderCardList();
            updateProgress();
            showNotification('Results cleared', 'success');
        }
    });
    
    document.getElementById('save-settings').addEventListener('click', async () => {
        const settings = {
            autoDetect: document.getElementById('auto-detect').checked,
            autoFill: document.getElementById('auto-fill-enabled').checked,
            autoSubmit: document.getElementById('auto-submit').checked,
            fillDelay: parseInt(document.getElementById('fill-delay').value) || 500,
            captchaService: document.getElementById('captcha-service').value,
            captchaApiKey: document.getElementById('captcha-api-key').value,
            proxyEnabled: document.getElementById('proxy-enabled').checked,
            proxyList: document.getElementById('proxy-list').value.split('\n').filter(p => p.trim()),
            verbose: document.getElementById('verbose-logging').checked,
            soundAlerts: document.getElementById('sound-alerts').checked,
            billingName: document.getElementById('billing-name').value,
            billingEmail: document.getElementById('billing-email').value,
            billingAddress: document.getElementById('billing-address').value,
            billingCity: document.getElementById('billing-city').value,
            billingZip: document.getElementById('billing-zip').value
        };
        
        await chrome.storage.local.set({ settings });
        await chrome.runtime.sendMessage({ type: 'settingsUpdated', settings });
        showNotification('Settings saved', 'success');
    });
}

async function startChecking() {
    if (cards.length === 0) {
        showNotification('No cards to check', 'error');
        return;
    }
    
    isChecking = true;
    document.getElementById('start-checking').disabled = true;
    document.getElementById('stop-checking').disabled = false;
    setStatus('Checking...', 'warning');
    
    await checkNextCard();
}

function stopChecking() {
    isChecking = false;
    document.getElementById('start-checking').disabled = false;
    document.getElementById('stop-checking').disabled = true;
    setStatus('Stopped', 'info');
}

async function checkNextCard() {
    if (!isChecking || currentCardIndex >= cards.length) {
        stopChecking();
        if (currentCardIndex >= cards.length) {
            setStatus('Completed', 'success');
            showNotification('All cards checked!', 'success');
        }
        return;
    }
    
    const card = cards[currentCardIndex];
    card.status = 'checking';
    renderCardList();
    updateCurrentCard();
    
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        
        if (!tab.url?.includes('stripe.com') && !tab.url?.includes('checkout')) {
            showNotification('Please open a checkout page', 'error');
            stopChecking();
            return;
        }
        
        await chrome.tabs.sendMessage(tab.id, { 
            action: 'fillCard', 
            card: card
        });
        
        const settings = await chrome.storage.local.get(['settings']);
        const delay = settings.settings?.fillDelay || 500;
        await new Promise(r => setTimeout(r, delay));
        
        if (settings.settings?.autoSubmit) {
            await chrome.tabs.sendMessage(tab.id, { action: 'submit' });
        }
        
    } catch (err) {
        console.error('Check error:', err);
    }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'cardResult') {
        handleCardResult(message.result);
    } else if (message.type === 'checkoutDetected') {
        setStatus('Checkout detected!', 'success');
        loadCheckoutInfo();
    }
});

function handleCardResult(result) {
    const card = cards[currentCardIndex];
    if (!card) return;
    
    card.timestamp = Date.now();
    
    if (result.success || result.status === 'live') {
        card.status = 'live';
        liveCards.push({ ...card });
        
        const settings = document.getElementById('sound-alerts');
        if (settings?.checked) {
            playSound('live');
        }
        showNotification('LIVE CARD!', 'success');
    } else {
        card.status = 'dead';
        card.error = result.error || result.declineCode || 'Declined';
        deadCards.push({ ...card });
    }
    
    saveCards();
    renderCardList();
    updateCurrentCard();
    updateProgress();
    renderLiveList();
    renderDeadList();
    
    currentCardIndex++;
    saveCards();
    
    if (isChecking) {
        setTimeout(checkNextCard, 1000);
    }
}

function playSound(type) {
    const audio = new Audio(type === 'live' 
        ? 'data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2teleQYAQJzb0qVpBgBFnNfOoWYHAE2f2M+gZAcAVKLZz59jBwBbpdnPnmIHAGKo2s6dYQcAaarb0J1gBwBwrNvQnF8HAHeu3NGcXgcAfbDd0ZtdBwCEst7Sm1wHAIu039KaWwcAkrXg05paBwCZt+HTmVkHAKC54dOYWAcAp7vi1JhXBwCuveXVl1YHALa/5dWWVQcAvMHm1pVUBwDDw+fWlFMHAMrF6NeUUgcA0cfp15NSBwDYyerYklEHAN/L6tiRUAcA5s3r2ZFPBwDtz+zZkE4HAPTRsQ=='
        : 'data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQ=='
    );
    audio.play().catch(() => {});
}

function setStatus(text, type) {
    const status = document.getElementById('status');
    status.querySelector('.status-text').textContent = text;
    status.querySelector('.status-dot').className = `status-dot ${type}`;
}

async function updateStatus() {
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (tab.url?.includes('stripe.com') || tab.url?.includes('checkout')) {
            setStatus('Ready', 'success');
        } else {
            setStatus('Open checkout', 'warning');
        }
    } catch (e) {
        setStatus('Ready', 'info');
    }
}

function showNotification(message, type) {
    document.querySelectorAll('.notification').forEach(n => n.remove());
    
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Open full settings page
document.getElementById('open-settings')?.addEventListener('click', () => {
    chrome.runtime.openOptionsPage();
});

document.getElementById('open-full-settings')?.addEventListener('click', () => {
    chrome.runtime.openOptionsPage();
});
