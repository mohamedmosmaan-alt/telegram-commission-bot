"""
WSGI entry point for PythonAnywhere (or any other WSGI host) — the
recommended free, no-credit-card hosting path for this bot.

Why this file exists: PythonAnywhere's free tier runs your code as a WSGI
web app that Apache keeps alive permanently (it does NOT sleep from
inactivity, unlike some other free hosts) — but it only runs your code
while handling an HTTP request, so there's no long-lived background loop
for python-telegram-bot's JobQueue to tick in. Two adjustments handle that:

  1. Telegram webhook updates arrive as normal HTTP POST requests, handled
     with Flask (PythonAnywhere's free tier is WSGI-only, so PTB's own
     run_webhook()/run_polling() — which need to own the whole process —
     don't fit; this file drives the same Application object by hand).
  2. Instead of a timer-based background sync, each incoming webhook
     request opportunistically re-syncs the cache if it's older than
     SYNC_INTERVAL_MINUTES (see _maybe_resync below) — so data still
     refreshes on its own, just triggered by traffic instead of a clock.
     An admin can still force it instantly with /sync.

One event loop is created once at import time and reused for every
request (see _loop below). This matches PythonAnywhere's free tier, which
serves one worker process at a time, so requests are handled one after
another rather than truly concurrently — reusing a single loop is both
simpler and required here, since the underlying HTTP client python-
telegram-bot uses is bound to the loop it was created on.
"""
import asyncio
import time

from flask import Flask, request
from telegram import Update

from app.config.settings import settings, validate_settings
from app.database.db import init_db
from app.services.sync_service import run_sync
from app.utils.logging_config import logger
from main import build_application

problems = validate_settings()
if problems:
    raise RuntimeError("Configuration problems: " + "; ".join(problems))

init_db()
run_sync()  # initial load so the bot isn't empty on first deploy

telegram_app = build_application()

_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)
_loop.run_until_complete(telegram_app.initialize())
_loop.run_until_complete(telegram_app.bot.set_my_commands([
    ("start", "Verify your phone number and see your report"),
    ("cancel", "Cancel the current operation"),
]))

flask_app = Flask(__name__)
_last_sync_at = [time.time()]


def _maybe_resync() -> None:
    if time.time() - _last_sync_at[0] >= settings.sync_interval_minutes * 60:
        logger.info("Lazily re-syncing (triggered by incoming request)...")
        run_sync()
        _last_sync_at[0] = time.time()


@flask_app.route(f"/{settings.webhook_secret_path}", methods=["POST"])
def telegram_webhook():
    _maybe_resync()
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    _loop.run_until_complete(telegram_app.process_update(update))
    return "OK"


@flask_app.route("/", methods=["GET"])
def health_check():
    return "Bot is running."
