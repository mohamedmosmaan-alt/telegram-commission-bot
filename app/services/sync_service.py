"""
Synchronizes the local SQLite cache from Google (§9, §12).

Two independent tables are refreshed on every sync:
  - agents             (from the phone directory sheet)
  - commission_reports (from the commission table, one row per master)

Key design points, unchanged from the original design:
  - One bad row must never crash the whole sync (§15) — logged and skipped.
  - Each table is replaced inside a transaction, so bot queries never see a
    half-written table.
  - Duplicate normalized phone numbers among agents are detected and
    reported in the summary; resolution is handled at lookup time.
"""
import json
from datetime import datetime, timezone

from app.config.settings import settings
from app.database.db import get_connection
from app.integrations.google_sheets import fetch_agents_rows, fetch_commission_rows, DataSourceError
from app.services.phone import try_normalize_phone
from app.utils.logging_config import logger, mask_phone


def _lookup_key(record: dict, *names: str) -> str:
    lower_map = {k.strip().lower(): v for k, v in record.items()}
    for name in names:
        if name in lower_map and str(lower_map[name]).strip():
            return str(lower_map[name]).strip()
    return ""


def _normalize_master(raw) -> str:
    """Masters come back as ints, floats, or strings depending on the sheet cell type."""
    try:
        return str(int(float(raw)))
    except (TypeError, ValueError):
        return str(raw).strip()


def run_sync() -> dict:
    started_at = datetime.now(timezone.utc).isoformat()
    summary = {
        "status": "FAILED", "agents_count": 0, "commission_count": 0,
        "duplicate_count": 0, "skipped": 0, "error": None,
    }

    try:
        raw_agent_rows = fetch_agents_rows()
        raw_commission_rows = fetch_commission_rows()
    except DataSourceError as e:
        summary["error"] = str(e)
        logger.error(f"Sync failed while fetching source data: {e}")
        _log_sync(started_at, summary)
        return summary

    # --- agents ---
    parsed_agents = []
    skipped = 0
    for raw in raw_agent_rows:
        master_raw = _lookup_key(raw, "master")
        agent_name = _lookup_key(raw, "name", "agent name")
        agency_name = _lookup_key(raw, "اسم الوكالة", "agency", "agency name")
        mobile_raw = _lookup_key(raw, "phone num", "mobile", "mobile number", "phone")

        if not master_raw or not mobile_raw:
            skipped += 1
            logger.warning(f"Skipping agent row missing required fields: master={master_raw!r}")
            continue

        phone_normalized = try_normalize_phone(mobile_raw, settings.default_country_code)
        if phone_normalized is None:
            skipped += 1
            logger.warning(
                f"Skipping agent {master_raw}: phone '{mask_phone(mobile_raw)}' could not be normalized."
            )
            continue

        parsed_agents.append({
            "master": _normalize_master(master_raw),
            "agent_name": agent_name or "—",
            "agency_name": agency_name or None,
            "phone_normalized": phone_normalized,
        })

    # duplicate phone detection among agents (§7)
    phone_counts: dict[str, int] = {}
    for a in parsed_agents:
        phone_counts[a["phone_normalized"]] = phone_counts.get(a["phone_normalized"], 0) + 1
    duplicate_count = sum(1 for c in phone_counts.values() if c > 1)

    # --- commission rows ---
    parsed_commission = []
    for raw in raw_commission_rows:
        master_raw = _lookup_key(raw, "master")
        if not master_raw:
            skipped += 1
            continue
        parsed_commission.append({
            "master": _normalize_master(master_raw),
            "fields_json": json.dumps(raw, ensure_ascii=False, default=str),
        })

    now = datetime.now(timezone.utc).isoformat()
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM agents")
            conn.executemany(
                """INSERT INTO agents (master, agent_name, agency_name, phone_normalized, updated_at)
                   VALUES (:master, :agent_name, :agency_name, :phone_normalized, :updated_at)""",
                [{**a, "updated_at": now} for a in parsed_agents],
            )
            conn.execute("DELETE FROM commission_reports")
            conn.executemany(
                """INSERT INTO commission_reports (master, fields_json, updated_at)
                   VALUES (:master, :fields_json, :updated_at)""",
                [{**c, "updated_at": now} for c in parsed_commission],
            )
    except Exception as e:
        summary["error"] = f"Database write failed: {e}"
        logger.error(summary["error"])
        _log_sync(started_at, summary)
        return summary

    summary.update({
        "status": "SUCCESS",
        "agents_count": len(parsed_agents),
        "commission_count": len(parsed_commission),
        "duplicate_count": duplicate_count,
        "skipped": skipped,
    })
    logger.info(
        f"Sync complete: {summary['agents_count']} agents, {summary['commission_count']} commission rows, "
        f"{duplicate_count} duplicate phone number(s), {skipped} row(s) skipped."
    )
    _log_sync(started_at, summary)
    return summary


def _log_sync(started_at: str, summary: dict) -> None:
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO sync_log
                   (started_at, finished_at, agents_count, commission_count, duplicate_count, status, error_message)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    started_at,
                    datetime.now(timezone.utc).isoformat(),
                    summary.get("agents_count", 0),
                    summary.get("commission_count", 0),
                    summary.get("duplicate_count", 0),
                    summary["status"],
                    summary.get("error"),
                ),
            )
    except Exception as e:
        logger.error(f"Could not write sync_log entry: {e}")
