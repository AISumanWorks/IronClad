import requests
import os
from modules.system_logger import logger

class NotificationManager:
    def __init__(self):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        
    def send_message(self, message):
        if not self.token or not self.chat_id:
            # Silent fail or warn once? We don't want to spam logs if not configured.
            return

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            # Timeout is important to not block the trading loop
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            logger.log(f"Failed to send Telegram alert: {e}", "ERROR")

    def send_signal_alert(self, signal):
        """
        Sends a formatted trade alert.
        signal: dict containing ticker, signal, price, strategy, confidence, etc.
        """
        icon = "🟢" if signal['signal'] == "BUY" else "🔴"
        
        msg = f"{icon} *TRADE ALERT* {icon}\n\n" \
              f"*Ticker:* `{signal['ticker']}`\n" \
              f"*Action:* {signal['signal']}\n" \
              f"*Price:* {signal['price']}\n" \
              f"*Strategy:* {signal['strategy']}\n" \
              f"*Confidence:* {signal['confidence']:.2f}\n" \
              f"*Time:* {signal['timestamp'].split('T')[1][:5]}" # HH:MM
              
        self.send_message(msg)
