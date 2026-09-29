"""
SQLite is the local cache + operational store (§11).

Tables:
    agents               -- from the agent/phone directory sheet (Fcc_Data),
                             keyed by master. This is what phone verification
                             matches against.
    commission_reports   -- from the commission sheet, one row per master,
                             every column stored as JSON so the exact set of
                             fields (and their order) can change without a
                             schema migration.
    verified_sessions    -- Telegram user <-> verified master link (§5)
    verification_attempts-- every attempt, success or failure, for auditing
    sync_log             -- history of sync runs

Both agents and commission_reports are fully REPLACED on every sync inside
a transaction, so a bot request never sees a half-updated table.
"""
import os
import sqlite3
from contextlib import contextmanager

from app.config.settings import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    master            TEXT PRIMARY KEY,
    agent_name        TEXT NOT NULL,
    agency_name       TEXT,
    phone_normalized  TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agents_phone ON agents(phone_normalized);

CREATE TABLE IF NOT EXISTS commission_reports (
    master        TEXT PRIMARY KEY,
    fields_json   TEXT NOT NULL,   -- ordered dict of every column from the sheet
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS verified_sessions (
    telegram_user_id  INTEGER PRIMARY KEY,
    master            TEXT NOT NULL,
    phone_normalized  TEXT NOT NULL,
    verified_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS verification_attempts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id  INTEGER NOT NULL,
    phone_masked      TEXT,
    result            TEXT NOT NULL,   -- FOUND, NOT_FOUND, DUPLICATE_PENDING, DUPLICATE_RESOLVED, ERROR
    master            TEXT,
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    agents_count    INTEGER,
    commission_count INTEGER,
    duplicate_count INTEGER,
    status          TEXT NOT NULL,   -- SUCCESS, FAILED
    error_message   TEXT
);
"""


def init_db() -> None:
    os.makedirs(os.path.dirname(settings.sqlite_path) or ".", exist_ok=True)
    with get_connection() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_connection():
    conn = sqlite3.connect(settings.sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
