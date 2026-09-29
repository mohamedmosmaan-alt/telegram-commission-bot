import os
import tempfile

import pytest

from app.config import settings as settings_module
from app.database.db import init_db, get_connection


@pytest.fixture(autouse=True)
def isolated_sqlite(monkeypatch):
    """Every test gets its own throwaway SQLite file, never the real bot.db."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(settings_module.settings, "sqlite_path", path)
    init_db()
    yield path
    os.remove(path)


def insert_agent(master, agent_name, phone_normalized, agency_name=None):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO agents (master, agent_name, agency_name, phone_normalized, updated_at)
               VALUES (?, ?, ?, ?, '2026-01-01T00:00:00')""",
            (master, agent_name, agency_name, phone_normalized),
        )


def insert_commission(master, fields_json_str):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO commission_reports (master, fields_json, updated_at)
               VALUES (?, ?, '2026-01-01T00:00:00')""",
            (master, fields_json_str),
        )
