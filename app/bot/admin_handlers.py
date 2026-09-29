"""
Admin commands (§13). Every handler checks the caller's Telegram user ID
against settings.admin_telegram_ids before doing anything else.
"""
from telegram import Update
from telegram.ext import ContextTypes

from app.config.settings import settings
from app.database.db import get_connection
from app.services.sync_service import run_sync
from app.utils.logging_config import logger, mask_phone


def _is_admin(update: Update) -> bool:
    return update.effective_user.id in settings.admin_telegram_ids


async def _deny(update: Update) -> None:
    logger.warning(f"Unauthorized admin command attempt by user {update.effective_user.id}")
    await update.message.reply_text("Access denied.")


async def admin_sync(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return await _deny(update)
    await update.message.reply_text("Syncing data, please wait…")
    summary = run_sync()
    if summary["status"] == "SUCCESS":
        await update.message.reply_text(
            f"✅ Sync complete.\n"
            f"Agents loaded: {summary['agents_count']}\n"
            f"Commission rows loaded: {summary['commission_count']}\n"
            f"Duplicate phone numbers: {summary['duplicate_count']}\n"
            f"Rows skipped (bad data): {summary['skipped']}"
        )
    else:
        await update.message.reply_text(f"❌ Sync failed: {summary['error']}")


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return await _deny(update)
    with get_connection() as conn:
        total_agents = conn.execute("SELECT COUNT(*) c FROM agents").fetchone()["c"]
        total_commission = conn.execute("SELECT COUNT(*) c FROM commission_reports").fetchone()["c"]
        total_sessions = conn.execute("SELECT COUNT(*) c FROM verified_sessions").fetchone()["c"]
        last_sync = conn.execute("SELECT * FROM sync_log ORDER BY id DESC LIMIT 1").fetchone()
        failed_attempts = conn.execute(
            "SELECT COUNT(*) c FROM verification_attempts WHERE result IN ('NOT_FOUND','DUPLICATE_UNRESOLVED')"
        ).fetchone()["c"]

    last_sync_text = (
        f"{last_sync['finished_at']} ({last_sync['status']}, {last_sync['agents_count']} agents, "
        f"{last_sync['commission_count']} commission rows)"
        if last_sync else "never"
    )
    await update.message.reply_text(
        "📊 System statistics\n\n"
        f"Cached agents: {total_agents}\n"
        f"Cached commission rows: {total_commission}\n"
        f"Verified sessions: {total_sessions}\n"
        f"Failed verification attempts (all time): {failed_attempts}\n"
        f"Last sync: {last_sync_text}"
    )


async def admin_find(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /find <master, agent name, or phone>"""
    if not _is_admin(update):
        return await _deny(update)
    if not context.args:
        await update.message.reply_text("Usage: /find <master, agent name, or phone>")
        return

    query = " ".join(context.args).strip()
    like = f"%{query}%"
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM agents
               WHERE master LIKE ? OR agent_name LIKE ? OR agency_name LIKE ? OR phone_normalized LIKE ?
               LIMIT 10""",
            (like, like, like, like),
        ).fetchall()

        if not rows:
            await update.message.reply_text("No matching agents found.")
            return

        lines = []
        for r in rows:
            session_row = conn.execute(
                "SELECT telegram_user_id FROM verified_sessions WHERE master = ?", (r["master"],)
            ).fetchone()
            has_report = conn.execute(
                "SELECT 1 FROM commission_reports WHERE master = ?", (r["master"],)
            ).fetchone() is not None
            lines.append(
                f"• Master {r['master']} — {r['agent_name']} ({r['agency_name'] or '—'})\n"
                f"  Phone: {mask_phone(r['phone_normalized'])}\n"
                f"  Commission data available: {'yes' if has_report else 'no'}\n"
                f"  Verified by Telegram user: {session_row['telegram_user_id'] if session_row else 'not yet verified'}"
            )
    await update.message.reply_text("\n\n".join(lines))


async def admin_duplicates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return await _deny(update)
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT phone_normalized, GROUP_CONCAT(master) as masters, COUNT(*) as c
               FROM agents GROUP BY phone_normalized HAVING c > 1"""
        ).fetchall()

    if not rows:
        await update.message.reply_text("No duplicate phone numbers found.")
        return

    lines = [f"• {mask_phone(r['phone_normalized'])}: {r['masters']}" for r in rows]
    await update.message.reply_text("⚠️ Duplicate phone numbers:\n\n" + "\n".join(lines))


async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return await _deny(update)
    await update.message.reply_text(
        "Admin commands:\n"
        "/sync — refresh agents + commission data from Google now\n"
        "/stats — system statistics\n"
        "/find <query> — search by master, agent name, agency, or phone\n"
        "/duplicates — list duplicate phone numbers\n"
        "/adminhelp — this message"
    )
