"""
Core verification logic (§3, §5, §7), adapted for the real dataset:
phone -> agent (Master) -> commission report.

Security invariant: a Telegram user can only ever be linked, via
verified_sessions, to the ONE master whose phone number they proved they
control via Telegram's native "share contact" button (never a typed
number — see handlers.py). Every function that returns data still takes
telegram_user_id purely so callers can log who asked.
"""
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config.settings import settings
from app.database.db import get_connection
from app.utils.logging_config import logger, mask_phone


@dataclass
class Agent:
    master: str
    agent_name: str
    agency_name: str | None
    phone_normalized: str


class LookupResult:
    NOT_FOUND = "NOT_FOUND"
    FOUND_UNIQUE = "FOUND_UNIQUE"
    DUPLICATE = "DUPLICATE"


def _row_to_agent(row) -> Agent:
    return Agent(
        master=row["master"],
        agent_name=row["agent_name"],
        agency_name=row["agency_name"],
        phone_normalized=row["phone_normalized"],
    )


def find_by_phone(phone_normalized: str) -> list[Agent]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM agents WHERE phone_normalized = ?", (phone_normalized,)
        ).fetchall()
    return [_row_to_agent(r) for r in rows]


def verify_phone(telegram_user_id: int, phone_normalized: str) -> tuple[str, list[Agent]]:
    matches = find_by_phone(phone_normalized)
    if not matches:
        _log_attempt(telegram_user_id, phone_normalized, "NOT_FOUND", None)
        return LookupResult.NOT_FOUND, []
    if len(matches) == 1:
        _log_attempt(telegram_user_id, phone_normalized, "FOUND", matches[0].master)
        return LookupResult.FOUND_UNIQUE, matches
    _log_attempt(telegram_user_id, phone_normalized, "DUPLICATE_PENDING", None)
    return LookupResult.DUPLICATE, matches


def resolve_duplicate(telegram_user_id: int, phone_normalized: str, secondary_value: str) -> Agent | None:
    """§7: if a phone matches more than one agent, require the Master number
    (or agent name, if configured) to disambiguate."""
    candidates = find_by_phone(phone_normalized)
    field = settings.duplicate_verification_field
    secondary_value_norm = secondary_value.strip().lower()

    for a in candidates:
        compare_value = (a.master if field == "master" else a.agent_name).strip().lower()
        if compare_value == secondary_value_norm:
            _log_attempt(telegram_user_id, phone_normalized, "DUPLICATE_RESOLVED", a.master)
            return a

    _log_attempt(telegram_user_id, phone_normalized, "DUPLICATE_UNRESOLVED", None)
    return None


def create_session(telegram_user_id: int, agent: Agent) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO verified_sessions (telegram_user_id, master, phone_normalized, verified_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(telegram_user_id) DO UPDATE SET
                   master = excluded.master,
                   phone_normalized = excluded.phone_normalized,
                   verified_at = excluded.verified_at""",
            (telegram_user_id, agent.master, agent.phone_normalized, now),
        )
    logger.info(f"Session created: telegram_user={telegram_user_id} -> master={agent.master}")


def get_session(telegram_user_id: int) -> Agent | None:
    with get_connection() as conn:
        session_row = conn.execute(
            "SELECT master FROM verified_sessions WHERE telegram_user_id = ?",
            (telegram_user_id,),
        ).fetchone()
        if not session_row:
            return None
        agent_row = conn.execute(
            "SELECT * FROM agents WHERE master = ?", (session_row["master"],)
        ).fetchone()
    return _row_to_agent(agent_row) if agent_row else None


def get_commission_fields(master: str) -> dict | None:
    """Returns the raw field dict for this master's latest synced commission row."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT fields_json FROM commission_reports WHERE master = ?", (master,)
        ).fetchone()
    if not row:
        return None
    return json.loads(row["fields_json"])


def _log_attempt(telegram_user_id: int, phone_normalized: str, result: str, master: str | None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO verification_attempts (telegram_user_id, phone_masked, result, master, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (telegram_user_id, mask_phone(phone_normalized), result, master, now),
        )
    logger.info(
        f"Verification attempt: user={telegram_user_id} phone={mask_phone(phone_normalized)} result={result}"
    )
