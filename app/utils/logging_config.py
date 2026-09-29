"""
Central logging configuration.

Design choice for §14: we never write full phone numbers or full customer
records to logs. mask_phone() keeps only the last 4 digits, which is enough
to trace an issue with a customer over the phone ("ends in 5678?") without
leaving a searchable, exportable list of full phone numbers on disk.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

from app.config.settings import settings


def mask_phone(phone: str) -> str:
    if not phone:
        return "<empty>"
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) <= 4:
        return "*" * len(digits)
    return "*" * (len(digits) - 4) + digits[-4:]


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("telegram_customer_bot")
    if logger.handlers:
        return logger  # already configured (avoid duplicate handlers on reload)

    logger.setLevel(settings.log_level.upper())

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    log_dir = os.path.dirname(settings.log_file) or "."
    os.makedirs(log_dir, exist_ok=True)
    file_handler = RotatingFileHandler(
        settings.log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


logger = setup_logging()
