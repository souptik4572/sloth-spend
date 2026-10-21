"""SQLite storage (spec §7.2 + IMPL §3.1). DB file: <SLOTH_DATA_DIR>/slothspend.db.

Every helper opens its own short-lived connection, which is safe from asyncio.to_thread workers.
Later milestones add their helpers here (pipeline M4, chat M6, reminders M7).
"""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import settings

DB_PATH = settings.data_dir / "slothspend.db"
SCHEMA_VERSION = 1

# Spec §7.2 with the IMPL §3.1 additions folded in (a new database, so no ALTERs).
SCHEMA = """
CREATE TABLE IF NOT EXISTS imports (
  id INTEGER PRIMARY KEY,
  file_name TEXT, file_sha256 TEXT UNIQUE, currency TEXT,
  mapping_json TEXT, row_count INTEGER, imported_at TEXT,
  status TEXT NOT NULL DEFAULT 'pending',      -- pending | committed (rows stored) | done (report built)
  header_row INTEGER,
  period_start TEXT, period_end TEXT,
  skipped_rows INTEGER DEFAULT 0,
  verified_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY,
  import_id INTEGER REFERENCES imports(id) ON DELETE CASCADE,
  tx_date TEXT NOT NULL,
  raw_description TEXT NOT NULL,
  desc_key TEXT NOT NULL,
  amount REAL NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('debit','credit')),
  merchant TEXT, category TEXT,
  is_duplicate INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_tx_merchant ON transactions(merchant, tx_date);
CREATE INDEX IF NOT EXISTS ix_tx_date ON transactions(tx_date);

CREATE TABLE IF NOT EXISTS merchant_map (
  desc_key TEXT PRIMARY KEY,
  merchant TEXT NOT NULL, category TEXT NOT NULL,
  subscription_like INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL CHECK (source IN ('llm','rule','user')),
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS series (
  id INTEGER PRIMARY KEY,
  merchant TEXT UNIQUE NOT NULL, category TEXT,
  features_json TEXT,
  n_charges INTEGER, first_date TEXT, last_date TEXT,
  cadence TEXT, cadence_days REAL,
  last_amount REAL, monthly_equiv REAL,
  recurring_prob REAL, scorer TEXT,
  similar_json TEXT,
  next_due_date TEXT,
  fc_q10 REAL, fc_q50 REAL, fc_q90 REAL, hike_prob REAL,
  flags_json TEXT,
  flag_details_json TEXT,
  priority REAL,
  cancellable INTEGER DEFAULT 0,
  status TEXT DEFAULT 'active',
  kind TEXT,
  dom_median REAL,
  amount_varies INTEGER DEFAULT 0,
  monthly_hist_json TEXT
);

CREATE TABLE IF NOT EXISTS user_labels (
  merchant TEXT PRIMARY KEY,
  label INTEGER NOT NULL,
  features_json TEXT NOT NULL,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS report_meta (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  generated_at TEXT, report_date TEXT, currency TEXT,
  monthly_recurring REAL, fc30_q10 REAL, fc30_q50 REAL, fc30_q90 REAL,
  potential_savings REAL, executive_summary TEXT, scorer TEXT,
  monthly_subscriptions REAL, monthly_bills REAL,
  fc30_sub_q10 REAL, fc30_sub_q50 REAL, fc30_sub_q90 REAL,
  dispute_total REAL, monthly_json TEXT, summary_source TEXT
);

CREATE TABLE IF NOT EXISTS chat_messages (
  id INTEGER PRIMARY KEY,
  conversation_id TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('user','assistant','tool')),
  content TEXT, tool_name TEXT, tool_args_json TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS reminders (
  series_id INTEGER PRIMARY KEY REFERENCES series(id),
  merchant TEXT NOT NULL,
  next_due_date TEXT NOT NULL,
  days_before INTEGER DEFAULT 3,
  remind_at TEXT,
  reminders_sent INTEGER DEFAULT 0,
  phase TEXT NOT NULL,
  detail TEXT, cancelled_on TEXT,
  created_at TEXT, updated_at TEXT,
  events_json TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS ix_reminders_due ON reminders(remind_at);

CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY,
  series_id INTEGER REFERENCES series(id),
  kind TEXT NOT NULL,
  title TEXT NOT NULL, body TEXT NOT NULL,
  created_at TEXT, read_at TEXT
);

CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""

# Tables wiped by "Delete all local data" (settings survive), children before parents.
DATA_TABLES = ["notifications", "reminders", "chat_messages", "user_labels", "report_meta", "series",
               "merchant_map", "transactions", "imports"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def init() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            conn.executescript(SCHEMA)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def wipe() -> None:
    """Delete all local data except settings (Settings › Delete all local data)."""
    with connect() as conn:
        for table in DATA_TABLES:
            conn.execute(f"DELETE FROM {table}")  # noqa: S608 — fixed table names


# ── settings ────────────────────────────────────────────────────────────────

def get_setting(key: str, default: str | None = None) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def get_setting_int(key: str) -> int:
    try:
        return int(get_setting(key) or 0)
    except ValueError:
        return 0


def set_settings(values: dict[str, str | None]) -> None:
    """Upsert each key; a None value deletes the key (back to its default)."""
    with connect() as conn:
        for key, value in values.items():
            if value is None:
                conn.execute("DELETE FROM settings WHERE key = ?", (key,))
            else:
                conn.execute(
                    "INSERT INTO settings(key, value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))


def all_settings() -> dict[str, str]:
    with connect() as conn:
        return {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")}


# ── imports ─────────────────────────────────────────────────────────────────

def create_pending_import(file_name: str, sha: str, mapping: dict, currency: str, header_row: int) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO imports(file_name, file_sha256, currency, mapping_json, header_row, status) "
            "VALUES(?, ?, ?, ?, ?, 'pending')",
            (file_name, sha, currency, json.dumps(mapping), header_row))
        return int(cur.lastrowid)


def get_import(import_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM imports WHERE id = ?", (import_id,)).fetchone()
    return dict(row) if row else None


def find_import_by_sha(sha: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM imports WHERE file_sha256 = ?", (sha,)).fetchone()
    return dict(row) if row else None


def update_pending_import(import_id: int, file_name: str, mapping: dict, currency: str, header_row: int) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE imports SET file_name = ?, mapping_json = ?, currency = ?, header_row = ? "
            "WHERE id = ? AND status = 'pending'",
            (file_name, json.dumps(mapping), currency, header_row, import_id))


def delete_pending_import(import_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM imports WHERE id = ? AND status = 'pending'", (import_id,))
        return cur.rowcount > 0


def finish_import(import_id: int, **fields) -> None:
    """Mark an import done (report built) and store any extra columns given (e.g. verified_count)."""
    allowed = {"verified_count", "row_count", "skipped_rows", "period_start", "period_end"}
    sets, args = ["status = 'done'"], []
    for key, value in fields.items():
        if key not in allowed:
            raise ValueError(f"unknown import field {key!r}")
        sets.append(f"{key} = ?")
        args.append(value)
    with connect() as conn:
        conn.execute(f"UPDATE imports SET {', '.join(sets)} WHERE id = ?", (*args, import_id))  # noqa: S608


def list_imports(statuses: tuple[str, ...] = ("committed", "done")) -> list[dict]:
    marks = ",".join("?" * len(statuses))
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM imports WHERE status IN ({marks}) ORDER BY id", statuses).fetchall()  # noqa: S608
    return [dict(r) for r in rows]


# ── transactions ────────────────────────────────────────────────────────────

def max_tx_date() -> str | None:
    with connect() as conn:
        return conn.execute("SELECT MAX(tx_date) FROM transactions").fetchone()[0]


def commit_import(import_id: int, rows: list[dict], fields: dict) -> int:
    """Insert parsed rows and mark the import committed — one transaction, so it's all or nothing."""
    with connect() as conn:
        cur = conn.execute("SELECT status FROM imports WHERE id = ?", (import_id,)).fetchone()
        if cur is None or cur["status"] != "pending":
            raise ValueError(f"import {import_id} is not pending")
        conn.executemany(
            "INSERT INTO transactions(import_id, tx_date, raw_description, desc_key, amount, direction) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            [(import_id, r["tx_date"], r["raw_description"], r["desc_key"], r["amount"], r["direction"])
             for r in rows])
        conn.execute(
            "UPDATE imports SET status = 'committed', imported_at = ?, row_count = ?, skipped_rows = ?, "
            "period_start = ?, period_end = ?, currency = ?, mapping_json = ?, header_row = ? WHERE id = ?",
            (now_iso(), fields["row_count"], fields["skipped_rows"], fields["period_start"],
             fields["period_end"], fields["currency"], json.dumps(fields["mapping"]), fields["header_row"],
             import_id))
        return len(rows)


def transactions(import_id: int | None = None) -> list[dict]:
    sql = "SELECT * FROM transactions"
    args: tuple = ()
    if import_id is not None:
        sql += " WHERE import_id = ?"
        args = (import_id,)
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql + " ORDER BY tx_date, id", args)]
