import json
import urllib.request
import urllib.error
from django.conf import settings

def send_telegram_message(chat_id, text, parse_mode='HTML'):
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not token:
        print("TELEGRAM_BOT_TOKEN is not set.")
        return False
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                return True
    except urllib.error.URLError as e:
        print(f"Telegram API Error: {e}")
        
    return False
