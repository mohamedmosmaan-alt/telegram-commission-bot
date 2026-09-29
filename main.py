"""
Entry point.

RUN_MODE=polling  -> good for a local machine or your own always-on PC.
                      No public URL needed. Just run `python main.py`.

RUN_MODE=webhook  -> good for Render's free web service. Render assigns you
                      a public HTTPS URL; set WEBHOOK_BASE_URL to it.
                      Render sets $PORT automatically.

Either way, a background job (using python-telegram-bot's built-in
JobQueue — no extra scheduler dependency needed) refreshes the customer
cache from Google every SYNC_INTERVAL_MINUTES, and does one sync at startup.
"""
import sys

from telegram import BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.bot.admin_handlers import admin_sync, admin_stats, admin_find, admin_duplicates, admin_help
from app.bot.handlers import (
    start,
    receive_contact,
    reject_typed_phone,
    receive_secondary_id,
    handle_customer_message,
    cancel,
    unknown_command,
)
from app.bot.states import REQUEST_PHONE, AWAITING_SECONDARY_ID, WAIT_FOR_CUSTOMER_MESSAGE
from app.config.settings import settings, validate_settings
from app.database.db import init_db
from app.services.sync_service import run_sync
from app.utils.logging_config import logger


async def scheduled_sync(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Running scheduled sync…")
    run_sync()


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Verify your account"),
            BotCommand("cancel", "Cancel the current operation"),
        ]
    )
    # one sync at startup so the bot isn't empty if this is a fresh deploy
    run_sync()


def build_application() -> Application:
    application = Application.builder().token(settings.telegram_bot_token).post_init(post_init).build()

    conversation = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REQUEST_PHONE: [
                MessageHandler(filters.CONTACT, receive_contact),
                # any typed text here is refused — verification is contact-button only (see handlers.py)
                MessageHandler(filters.TEXT & ~filters.COMMAND, reject_typed_phone),
            ],
            AWAITING_SECONDARY_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_secondary_id),
            ],
            WAIT_FOR_CUSTOMER_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_customer_message),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conversation)

    # admin commands are outside the conversation so they work regardless of state
    application.add_handler(CommandHandler("sync", admin_sync))
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CommandHandler("find", admin_find))
    application.add_handler(CommandHandler("duplicates", admin_duplicates))
    application.add_handler(CommandHandler("adminhelp", admin_help))

    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    application.job_queue.run_repeating(
        scheduled_sync, interval=settings.sync_interval_minutes * 60, first=settings.sync_interval_minutes * 60
    )

    return application


def main() -> None:
    problems = validate_settings()
    if problems:
        logger.error("Configuration problems found:")
        for p in problems:
            logger.error(f"  - {p}")
        logger.error("Fix your .env file (see .env.example) and try again.")
        sys.exit(1)

    init_db()
    application = build_application()

    if settings.run_mode == "webhook":
        webhook_url = f"{settings.webhook_base_url.rstrip('/')}/{settings.webhook_secret_path}"
        logger.info(f"Starting in webhook mode: listening on 0.0.0.0:{settings.port}, url={webhook_url}")
        application.run_webhook(
            listen="0.0.0.0",
            port=settings.port,
            url_path=settings.webhook_secret_path,
            webhook_url=webhook_url,
        )
    else:
        logger.info("Starting in polling mode.")
        application.run_polling()


if __name__ == "__main__":
    main()
