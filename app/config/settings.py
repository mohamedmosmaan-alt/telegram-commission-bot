"""
Central configuration, loaded entirely from environment variables.
Never hard-code secrets here — see .env.example for the full list.
"""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()  # loads a local .env file if present (never commit it)


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    try:
        return int(val) if val else default
    except ValueError:
        return default


def _get_admin_ids() -> set[int]:
    raw = os.getenv("ADMIN_TELEGRAM_IDS", "")
    ids = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if chunk.isdigit():
            ids.add(int(chunk))
    return ids


@dataclass(frozen=True)
class Settings:
    # --- Telegram ---
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    admin_telegram_ids: set = field(default_factory=_get_admin_ids)

    # --- Run mode ---
    # "polling"  -> good for local machines / always-on PCs, no public URL needed
    # "webhook"  -> good for Render's free web service
    run_mode: str = os.getenv("RUN_MODE", "polling")
    webhook_base_url: str = os.getenv("WEBHOOK_BASE_URL", "")  # e.g. https://your-app.onrender.com
    webhook_secret_path: str = os.getenv("WEBHOOK_SECRET_PATH", "telegram-webhook")
    port: int = _get_int("PORT", 8000)

    # --- Google Sheets (canonical data source) ---
    # Both tabs live in ONE Google Sheet (recommended): one tab is the agent/phone
    # directory (like Fcc_Data.xlsx), the other is the commission report table
    # (like the "Sheet1" tab of Fcc_Commission_New.xlsx — the flat table with
    # one row per Master, NOT the single-record template tab).
    google_service_account_json: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")  # path to json key file
    google_sheet_id: str = os.getenv("GOOGLE_SHEET_ID", "")
    google_sheet_agents_worksheet: str = os.getenv("GOOGLE_SHEET_AGENTS_WORKSHEET", "Fcc_Data")
    google_sheet_commission_worksheet: str = os.getenv("GOOGLE_SHEET_COMMISSION_WORKSHEET", "Fcc_Commission")

    # --- Fallback: raw Excel files on Drive (only used if USE_EXCEL_FALLBACK=true) ---
    use_excel_fallback: bool = _get_bool("USE_EXCEL_FALLBACK", False)
    google_drive_excel_file_id_agents: str = os.getenv("GOOGLE_DRIVE_EXCEL_FILE_ID_AGENTS", "")
    google_drive_excel_file_id_commission: str = os.getenv("GOOGLE_DRIVE_EXCEL_FILE_ID_COMMISSION", "")

    # --- Sync ---
    sync_interval_minutes: int = _get_int("SYNC_INTERVAL_MINUTES", 15)

    # --- Database ---
    sqlite_path: str = os.getenv("SQLITE_PATH", "data/bot.db")

    # --- Duplicate-phone secondary verification field (kept for safety even though
    # the current dataset has none) ---
    # one of: "master" or "agent_name"
    duplicate_verification_field: str = os.getenv("DUPLICATE_VERIFICATION_FIELD", "master")

    # --- Country / normalization ---
    default_country_code: str = os.getenv("DEFAULT_COUNTRY_CODE", "20")  # Egypt

    # --- Logging ---
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: str = os.getenv("LOG_FILE", "logs/bot.log")


settings = Settings()


def validate_settings() -> list[str]:
    """Returns a list of human-readable problems. Empty list = ready to run."""
    problems = []
    if not settings.telegram_bot_token:
        problems.append("TELEGRAM_BOT_TOKEN is missing.")
    if not settings.admin_telegram_ids:
        problems.append("ADMIN_TELEGRAM_IDS is empty — no one will be able to use admin commands.")
    if not settings.use_excel_fallback and not settings.google_sheet_id:
        problems.append("GOOGLE_SHEET_ID is missing (required unless USE_EXCEL_FALLBACK=true).")
    if settings.use_excel_fallback and not (
        settings.google_drive_excel_file_id_agents and settings.google_drive_excel_file_id_commission
    ):
        problems.append(
            "USE_EXCEL_FALLBACK=true but GOOGLE_DRIVE_EXCEL_FILE_ID_AGENTS / "
            "GOOGLE_DRIVE_EXCEL_FILE_ID_COMMISSION are not both set."
        )
    if not settings.google_service_account_json:
        problems.append("GOOGLE_SERVICE_ACCOUNT_JSON (path to your service account key file) is missing.")
    if settings.run_mode == "webhook" and not settings.webhook_base_url:
        problems.append("RUN_MODE=webhook but WEBHOOK_BASE_URL is not set.")
    return problems
