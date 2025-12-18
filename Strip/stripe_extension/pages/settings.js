// Stripe Toolkit v3.0 - Settings Page

function updateClock() {
    const now = new Date();
    const time = now.toLocaleTimeString('en-US', { hour12: false });
    const date = now.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
    document.getElementById('clock').textContent = time;
    document.getElementById('date').textContent = date;
}

setInterval(updateClock, 1000);
updateClock();

document.querySelectorAll('.sidebar-menu li').forEach(item => {
    item.addEventListener('click', () => {
        document.querySelectorAll('.sidebar-menu li').forEach(li => li.classList.remove('active'));
        document.querySelectorAll('.section').forEach(sec => sec.classList.remove('active'));
        item.classList.add('active');
        document.getElementById(item.getAttribute('data-section')).classList.add('active');
    });
});

async function loadData() {
    const data = await chrome.storage.local.get(['cards', 'liveCards', 'deadCards', 'settings']);
    const liveCards = data.liveCards || [];
    const deadCards = data.deadCards || [];
    const settings = data.settings || {};
    
    document.getElementById('live-count').textContent = liveCards.length;
    document.getElementById('dead-count').textContent = deadCards.length;
    document.getElementById('attempts-count').textContent = liveCards.length + deadCards.length;
    const rate = liveCards.length + deadCards.length > 0 ? ((liveCards.length / (liveCards.length + deadCards.length)) * 100).toFixed(1) : 0;
    document.getElementById('success-rate').textContent = rate + '%';
    
    if ((data.cards || []).length > 0) {
        document.getElementById('cc-list').value = data.cards.map(c => `${c.number}|${c.expMonth}|${c.expYear}|${c.cvv}`).join('\n');
        document.getElementById('card-count').textContent = `Cards: ${data.cards.length}`;
    }
    
    document.getElementById('auto-detect').checked = settings.autoDetect !== false;
    document.getElementById('auto-fill').checked = settings.autoFill || false;
    document.getElementById('auto-submit').checked = settings.autoSubmit || false;
    document.getElementById('auto-next').checked = settings.autoNext || false;
    document.getElementById('sound-alerts').checked = settings.soundAlerts || false;
    document.getElementById('fill-delay').value = settings.fillDelay || 500;
    document.getElementById('billing-name').value = settings.billingName || '';
    document.getElementById('billing-email').value = settings.billingEmail || '';
    document.getElementById('billing-address').value = settings.billingAddress || '';
    document.getElementById('billing-city').value = settings.billingCity || '';
    document.getElementById('billing-zip').value = settings.billingZip || '';
    
    updateHitLogs(liveCards, deadCards);
}

function updateHitLogs(liveCards, deadCards) {
    const logsEl = document.getElementById('hit-logs');
    const allCards = [...liveCards.map(c => ({...c, status: 'live'})), ...deadCards.map(c => ({...c, status: 'dead'}))];
    allCards.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
    
    if (allCards.length === 0) {
        logsEl.innerHTML = '<p style="color: #95a5a6; text-align: center;">No logs yet</p>';
        return;
    }
    
    logsEl.innerHTML = '';
    allCards.slice(0, 20).forEach(card => {
        const entry = document.createElement('div');
        entry.className = `log-entry ${card.status}`;
        entry.textContent = `${card.number.slice(0,4)}****${card.number.slice(-4)} | ${card.expMonth}/${card.expYear} | ${card.status.toUpperCase()}${card.error ? ' - ' + card.error : ''}`;
        logsEl.appendChild(entry);
    });
}

function saveCards() {
    const text = document.getElementById('cc-list').value.trim();
    if (!text) { alert('Please enter cards'); return; }
    
    const cards = text.split('\n').filter(l => l.trim()).map(line => {
        const parts = line.trim().split('|');
        if (parts.length >= 4) {
            return { number: parts[0].replace(/\s/g, ''), expMonth: parts[1].padStart(2, '0'), expYear: parts[2], cvv: parts[3], status: 'pending' };
        }
    }).filter(Boolean);
    
    if (cards.length === 0) { alert('No valid cards'); return; }
    
    chrome.storage.local.set({ cards: cards, currentCardIndex: 0 }, () => {
        document.getElementById('card-count').textContent = `Cards: ${cards.length}`;
        alert(`Saved ${cards.length} cards`);
    });
}

function clearCards() {
    document.getElementById('cc-list').value = '';
    document.getElementById('card-count').textContent = 'Cards: 0';
}

function generateEmail() {
    document.getElementById('email-input').value = `${Math.random().toString(36).substring(2, 10)}@gmail.com`;
}

function saveEmail() {
    const email = document.getElementById('email-input').value;
    if (!email) { alert('Please enter email'); return; }
    chrome.storage.local.get(['settings'], (data) => {
        const settings = data.settings || {};
        settings.billingEmail = email;
        chrome.storage.local.set({ settings: settings }, () => alert('Email saved'));
    });
}

function saveProxies() {
    const text = document.getElementById('proxy-list').value.trim();
    const enabled = document.getElementById('proxy-enabled').checked;
    const proxies = text.split('\n').filter(l => l.trim());
    
    chrome.storage.local.get(['settings'], (data) => {
        const settings = data.settings || {};
        settings.proxyEnabled = enabled;
        settings.proxyList = proxies;
        chrome.storage.local.set({ settings: settings }, () => alert(`Saved ${proxies.length} proxies`));
    });
}

function saveAutofill() {
    chrome.storage.local.get(['settings'], (data) => {
        const settings = data.settings || {};
        settings.billingName = document.getElementById('billing-name').value;
        settings.billingEmail = document.getElementById('billing-email').value;
        settings.billingAddress = document.getElementById('billing-address').value;
        settings.billingCity = document.getElementById('billing-city').value;
        settings.billingZip = document.getElementById('billing-zip').value;
        chrome.storage.local.set({ settings: settings }, () => alert('Autofill saved'));
    });
}

function saveSettings() {
    const settings = {
        autoDetect: document.getElementById('auto-detect').checked,
        autoFill: document.getElementById('auto-fill').checked,
        autoSubmit: document.getElementById('auto-submit').checked,
        autoNext: document.getElementById('auto-next').checked,
        soundAlerts: document.getElementById('sound-alerts').checked,
        fillDelay: parseInt(document.getElementById('fill-delay').value) || 500
    };
    
    chrome.storage.local.get(['settings'], (data) => {
        const updated = { ...data.settings || {}, ...settings };
        chrome.storage.local.set({ settings: updated }, () => {
            chrome.runtime.sendMessage({ type: 'settingsUpdated', settings: updated });
            alert('Settings saved');
        });
    });
}

function generateFromBIN() {
    alert('BIN generator coming soon!');
}

loadData();
setInterval(loadData, 5000);
