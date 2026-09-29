"""
Run this ONCE after deploying flask_app.py somewhere (e.g. PythonAnywhere),
to tell Telegram where to send updates. Flask/WSGI hosting doesn't register
the webhook for you the way python-telegram-bot's own run_webhook() does.

Usage (from a PythonAnywhere Bash console, inside the project folder):
    python scripts/set_webhook.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from app.config.settings import settings

if not settings.webhook_base_url:
    print("WEBHOOK_BASE_URL is not set in your .env — set it first (e.g. "
          "https://yourusername.pythonanywhere.com), then re-run this script.")
    sys.exit(1)

webhook_url = f"{settings.webhook_base_url.rstrip('/')}/{settings.webhook_secret_path}"
api_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook"

response = requests.post(api_url, data={"url": webhook_url})
print(response.json())

if response.ok and response.json().get("ok"):
    print(f"\n✅ Webhook set to: {webhook_url}")
else:
    print("\n❌ Something went wrong — check TELEGRAM_BOT_TOKEN and WEBHOOK_BASE_URL in .env")
