import json
import random
import string
import time
import urllib.request
import urllib.error
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from accounts.models import UserProfile
from core.telegram import send_telegram_message

class Command(BaseCommand):
    help = 'Runs the Telegram bot using long polling'

    def generate_otp(self):
        return ''.join(random.choices(string.digits, k=6))

    def handle(self, *args, **options):
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        if not token:
            self.stdout.write(self.style.ERROR("TELEGRAM_BOT_TOKEN is not set in settings/env."))
            return

        self.stdout.write(self.style.SUCCESS("Starting Telegram bot..."))
        
        offset = None
        while True:
            try:
                url = f"https://api.telegram.org/bot{token}/getUpdates?timeout=30"
                if offset:
                    url += f"&offset={offset}"

                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=40) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    
                if not data.get("ok"):
                    self.stdout.write(self.style.ERROR(f"Error from Telegram API: {data}"))
                    time.sleep(5)
                    continue

                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    message = update.get("message")
                    if not message:
                        continue
                    
                    chat_id = message.get("chat", {}).get("id")
                    text = message.get("text", "")

                    if text.startswith("/start"):
                        parts = text.split()
                        if len(parts) > 1:
                            t_token = parts[1]
                            # Find user by telegram_token
                            profile = UserProfile.objects.filter(telegram_token=t_token).first()
                            if profile:
                                profile.telegram_chat_id = str(chat_id)
                                profile.telegram_token = None # Clear token
                                
                                # Generate OTP
                                otp = self.generate_otp()
                                profile.otp_code = otp
                                profile.otp_created_at = timezone.now()
                                profile.save(update_fields=['telegram_chat_id', 'telegram_token', 'otp_code', 'otp_created_at'])
                                
                                msg_text = f"Sizning tasdiqlash kodingiz: <b>{otp}</b>\n\nIltimos, ushbu kodni platformaga kiriting."
                                send_telegram_message(chat_id, msg_text)
                            else:
                                send_telegram_message(chat_id, "Kechirasiz, havola yaroqsiz yoki eskirgan.")
                        else:
                            send_telegram_message(chat_id, "Xush kelibsiz! Tizimga ulanish uchun platformadan berilgan maxsus havoladan o'ting.")
                            
            except urllib.error.URLError as e:
                self.stdout.write(self.style.ERROR(f"Network error: {e}"))
                time.sleep(5)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Unexpected error: {e}"))
                time.sleep(5)
