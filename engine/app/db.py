"""SQLite storage (spec §7.2 + IMPL §3.1). DB file: <SLOTH_DATA_DIR>/slothspend.db.

Every helper opens its own short-lived connection, which is safe from asyncio.to_thread workers.
Later milestones add their helpers here (pipeline M4, chat M6, reminders M7).
"""

import json
import sqlite3
from typing import TYPE_CHECKING
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import settings

if TYPE_CHECKING:
    import pandas as pd

DB_PATH = settings.data_dir / "slothspend.db"
SCHEMA_VERSION = 2

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
        if version < 2:
            # v2 (M4): the 19 forecast quantiles per series, for the drawer's "Next charge" range.
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(series)")}
            if "quantiles_json" not in cols:
                conn.execute("ALTER TABLE series ADD COLUMN quantiles_json TEXT")
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


def debit_key_stats() -> list[dict]:
    """Per description key: how often and how much — normalisation priority (IMPL M4.1)."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT desc_key, COUNT(*) AS n, SUM(amount) AS total, MAX(amount) AS largest "
            "FROM transactions WHERE direction = 'debit' GROUP BY desc_key").fetchall()
    return [dict(r) for r in rows]


def debits_frame() -> "pd.DataFrame":
    import pandas as pd

    with connect() as conn:
        rows = conn.execute(
            "SELECT t.id, t.tx_date, t.amount, t.desc_key, t.raw_description, t.merchant, t.category, "
            "t.is_duplicate, COALESCE(m.subscription_like, 0) AS subscription_like, "
            "COALESCE(m.source, 'rule') AS source "
            "FROM transactions t LEFT JOIN merchant_map m ON m.desc_key = t.desc_key "
            "WHERE t.direction = 'debit' ORDER BY t.tx_date, t.id").fetchall()
    cols = ["id", "tx_date", "amount", "desc_key", "raw_description", "merchant", "category", "is_duplicate",
            "subscription_like", "source"]
    return pd.DataFrame([dict(r) for r in rows], columns=cols)


def latest_tx_date() -> str | None:
    return max_tx_date()


def merchant_transactions(merchant: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, tx_date, amount, raw_description, desc_key, is_duplicate FROM transactions "
            "WHERE direction = 'debit' AND merchant = ? ORDER BY tx_date, id", (merchant,)).fetchall()
    return [dict(r) for r in rows]


def mark_duplicates(ids: set[int]) -> None:
    with connect() as conn:
        conn.execute("UPDATE transactions SET is_duplicate = 0 WHERE is_duplicate != 0")
        conn.executemany("UPDATE transactions SET is_duplicate = 1 WHERE id = ?", [(i,) for i in ids])


# ── merchant_map ────────────────────────────────────────────────────────────

def merchant_map_get(keys: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    with connect() as conn:
        for start in range(0, len(keys), 500):
            chunk = keys[start:start + 500]
            marks = ",".join("?" * len(chunk))
            for r in conn.execute(f"SELECT * FROM merchant_map WHERE desc_key IN ({marks})", chunk):  # noqa: S608
                out[r["desc_key"]] = dict(r)
    return out


def merchant_map_upsert(entries: dict[str, dict]) -> None:
    """Precedence user > llm > rule: a user edit is never overwritten, a Gemma name never by the rule."""
    if not entries:
        return
    now = now_iso()
    with connect() as conn:
        conn.executemany(
            "INSERT INTO merchant_map(desc_key, merchant, category, subscription_like, source, updated_at) "
            "VALUES(?, ?, ?, ?, ?, ?) ON CONFLICT(desc_key) DO UPDATE SET merchant = excluded.merchant, "
            "category = excluded.category, subscription_like = excluded.subscription_like, "
            "source = excluded.source, updated_at = excluded.updated_at "
            "WHERE merchant_map.source != 'user' AND NOT (merchant_map.source = 'llm' AND excluded.source = 'rule')"
            " OR excluded.source = 'user'",
            [(k, e["merchant"], e["category"], int(bool(e["subscription_like"])), e["source"], now)
             for k, e in entries.items()])


def apply_merchant_map() -> None:
    """Copy names and categories from merchant_map onto every transaction."""
    with connect() as conn:
        conn.execute(
            "UPDATE transactions SET merchant = m.merchant, category = m.category "
            "FROM merchant_map m WHERE m.desc_key = transactions.desc_key")


def desc_keys_for_merchant(merchant: str) -> list[str]:
    with connect() as conn:
        return [r[0] for r in conn.execute(
            "SELECT DISTINCT desc_key FROM transactions WHERE merchant = ? ORDER BY desc_key", (merchant,))]


def raw_descriptions_for_merchant(merchant: str, limit: int = 3) -> list[str]:
    with connect() as conn:
        return [r[0] for r in conn.execute(
            "SELECT raw_description, COUNT(*) AS n FROM transactions WHERE merchant = ? "
            "GROUP BY raw_description ORDER BY n DESC, raw_description LIMIT ?", (merchant, limit))]


# ── series, labels, report ──────────────────────────────────────────────────

SERIES_JSON = ("features_json", "similar_json", "flags_json", "flag_details_json", "monthly_hist_json",
               "quantiles_json")


def series_statuses() -> dict[str, str]:
    with connect() as conn:
        return {r["merchant"]: r["status"] for r in conn.execute("SELECT merchant, status FROM series")}


def save_series(rows: list[dict]) -> None:
    """Upsert on merchant (ids stay stable for reminders); drop series that vanished unless a reminder uses them."""
    cols = ["merchant", "category", "features_json", "n_charges", "first_date", "last_date", "cadence",
            "cadence_days", "last_amount", "monthly_equiv", "recurring_prob", "scorer", "similar_json",
            "next_due_date", "fc_q10", "fc_q50", "fc_q90", "hike_prob", "flags_json", "flag_details_json",
            "priority", "cancellable", "status", "kind", "dom_median", "amount_varies", "monthly_hist_json",
            "quantiles_json"]
    sql = (f"INSERT INTO series({', '.join(cols)}) VALUES({', '.join('?' * len(cols))}) "  # noqa: S608
           f"ON CONFLICT(merchant) DO UPDATE SET {', '.join(f'{c} = excluded.{c}' for c in cols[1:])}")
    keep = [r["merchant"] for r in rows]
    with connect() as conn:
        conn.executemany(sql, [tuple(r.get(c) for c in cols) for r in rows])
        marks = ",".join("?" * len(keep)) or "''"
        conn.execute(
            f"DELETE FROM series WHERE merchant NOT IN ({marks}) "  # noqa: S608
            "AND id NOT IN (SELECT series_id FROM reminders)", keep)


def _series_dict(r: sqlite3.Row) -> dict:
    d = dict(r)
    for key in SERIES_JSON:
        d[key] = json.loads(d[key]) if d.get(key) else None
    return d


def list_series() -> list[dict]:
    with connect() as conn:
        return [_series_dict(r) for r in conn.execute("SELECT * FROM series")]


def series_by_id(series_id: int) -> dict | None:
    with connect() as conn:
        r = conn.execute("SELECT * FROM series WHERE id = ?", (series_id,)).fetchone()
    return _series_dict(r) if r else None


def series_id_for(merchant: str) -> int | None:
    with connect() as conn:
        r = conn.execute("SELECT id FROM series WHERE merchant = ?", (merchant,)).fetchone()
    return r[0] if r else None


def set_series_status(merchant: str, status: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE series SET status = ? WHERE merchant = ?", (status, merchant))


def rename_merchant_state(old: str, new: str) -> None:
    """Carry a user label and status over when a merchant is renamed."""
    if old == new:
        return
    with connect() as conn:
        conn.execute("UPDATE OR REPLACE user_labels SET merchant = ? WHERE merchant = ?", (new, old))
        row = conn.execute("SELECT status FROM series WHERE merchant = ?", (old,)).fetchone()
        if row and row["status"] != "active":
            conn.execute("UPDATE series SET status = ? WHERE merchant = ?", (row["status"], new))


def upsert_label(merchant: str, label: int, features: dict) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO user_labels(merchant, label, features_json, created_at) VALUES(?, ?, ?, ?) "
            "ON CONFLICT(merchant) DO UPDATE SET label = excluded.label, features_json = excluded.features_json, "
            "created_at = excluded.created_at", (merchant, label, json.dumps(features), now_iso()))


def user_labels() -> list[dict]:
    with connect() as conn:
        return [{"merchant": r["merchant"], "label": r["label"], **json.loads(r["features_json"])}
                for r in conn.execute("SELECT * FROM user_labels")]


def save_report_meta(meta: dict) -> None:
    cols = ["generated_at", "report_date", "currency", "monthly_recurring", "fc30_q10", "fc30_q50", "fc30_q90",
            "potential_savings", "executive_summary", "scorer", "monthly_subscriptions", "monthly_bills",
            "fc30_sub_q10", "fc30_sub_q50", "fc30_sub_q90", "dispute_total", "monthly_json", "summary_source"]
    with connect() as conn:
        conn.execute(
            f"INSERT INTO report_meta(id, {', '.join(cols)}) VALUES(1, {', '.join('?' * len(cols))}) "  # noqa: S608
            f"ON CONFLICT(id) DO UPDATE SET {', '.join(f'{c} = excluded.{c}' for c in cols)}",
            tuple(meta.get(c) for c in cols))


def report_meta() -> dict | None:
    with connect() as conn:
        r = conn.execute("SELECT * FROM report_meta WHERE id = 1").fetchone()
    if r is None:
        return None
    d = dict(r)
    d["monthly_json"] = json.loads(d["monthly_json"]) if d["monthly_json"] else []
    return d


# ── Ask Sloth conversations ─────────────────────────────────────────────────

def save_chat(conversation_id: str, role: str, content: str, *, tool_name: str | None = None,
              tool_args: dict | None = None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO chat_messages(conversation_id, role, content, tool_name, tool_args_json, created_at) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            (conversation_id, role, content, tool_name, json.dumps(tool_args) if tool_args is not None else None,
             now_iso()))


def load_chat(conversation_id: str, limit: int = 12) -> list[dict]:
    """The last `limit` user/assistant turns as Ollama messages (tool records stay out of the prompt)."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT role, content FROM chat_messages WHERE conversation_id = ? AND role != 'tool' "
            "ORDER BY id DESC LIMIT ?", (conversation_id, limit)).fetchall()
    return [{"role": r["role"], "content": r["content"] or ""} for r in reversed(rows)]


def chat_history(conversation_id: str) -> list[dict]:
    """Everything in a conversation, oldest first, for redrawing the pane."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, role, content, tool_name, tool_args_json, created_at FROM chat_messages "
            "WHERE conversation_id = ? ORDER BY id", (conversation_id,)).fetchall()
    return [{"id": r["id"], "role": r["role"], "content": r["content"], "tool_name": r["tool_name"],
             "tool_args": json.loads(r["tool_args_json"]) if r["tool_args_json"] else None,
             "created_at": r["created_at"]} for r in rows]


# ── reminders (spec §7.10, IMPL M7.2) ───────────────────────────────────────

ACTIVE_PHASES = ("WATCHING", "REMINDED", "SNOOZED", "AWAITING_STATEMENT", "STILL_CHARGED")
FINAL_PHASES = ("KEPT", "EXPIRED", "STOPPED", "VERIFIED_STOPPED")
REMINDER_FIELDS = {"merchant", "next_due_date", "days_before", "remind_at", "reminders_sent", "detail", "cancelled_on"}


def _reminder(r: sqlite3.Row | None) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    d["events"] = json.loads(d.pop("events_json") or "[]")
    return d


def get_reminder(series_id: int) -> dict | None:
    with connect() as conn:
        return _reminder(conn.execute("SELECT * FROM reminders WHERE series_id = ?", (series_id,)).fetchone())


def put_reminder(series_id: int, phase: str, **fields) -> dict:
    """Create the row, or reset an ended one to a fresh start (a new history begins)."""
    now = now_iso()
    cols = {"merchant": None, "next_due_date": None, "days_before": 3, "remind_at": None, "reminders_sent": 0,
            "detail": None, "cancelled_on": None, **fields}
    events = json.dumps([{"phase": phase, "at": now}])
    with connect() as conn:
        conn.execute(
            "INSERT INTO reminders(series_id, merchant, next_due_date, days_before, remind_at, reminders_sent, phase, "
            "detail, cancelled_on, created_at, updated_at, events_json) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(series_id) DO UPDATE SET merchant = excluded.merchant, next_due_date = excluded.next_due_date, "
            "days_before = excluded.days_before, remind_at = excluded.remind_at, reminders_sent = excluded.reminders_sent, "
            "phase = excluded.phase, detail = excluded.detail, cancelled_on = excluded.cancelled_on, "
            "created_at = excluded.created_at, updated_at = excluded.updated_at, events_json = excluded.events_json",
            (series_id, cols["merchant"], cols["next_due_date"], cols["days_before"], cols["remind_at"],
             cols["reminders_sent"], phase, cols["detail"], cols["cancelled_on"], now, now, events))
    return get_reminder(series_id)


def transition(series_id: int, expect: str | tuple[str, ...], new_phase: str, **fields) -> bool:
    """Compare-and-set: only moves the row if it is still in `expect`. Fields not given stay unchanged."""
    unknown = set(fields) - REMINDER_FIELDS
    if unknown:
        raise ValueError(f"unknown reminder fields {sorted(unknown)}")
    expected = (expect,) if isinstance(expect, str) else expect
    now = now_iso()
    sets = ["phase = ?", "updated_at = ?"]
    args: list = [new_phase, now]
    for key, value in fields.items():
        sets.append(f"{key} = ?")
        args.append(value)
    # A real phase change is recorded in the row's history.
    sets.append("events_json = CASE WHEN phase != ? THEN json_insert(events_json, '$[#]', "
                "json_object('phase', ?, 'at', ?)) ELSE events_json END")
    args += [new_phase, new_phase, now]
    marks = ",".join("?" * len(expected))
    with connect() as conn:
        cur = conn.execute(f"UPDATE reminders SET {', '.join(sets)} WHERE series_id = ? AND phase IN ({marks})",  # noqa: S608
                           (*args, series_id, *expected))
        return cur.rowcount == 1


def due_reminders(now: str) -> list[dict]:
    marks = ",".join("?" * len(ACTIVE_PHASES))
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM reminders WHERE remind_at IS NOT NULL AND remind_at <= ? AND phase IN ({marks}) "  # noqa: S608
            "ORDER BY remind_at", (now, *ACTIVE_PHASES)).fetchall()
    return [_reminder(r) for r in rows]


def reminders_in_phase(phase: str) -> list[dict]:
    with connect() as conn:
        return [_reminder(r) for r in conn.execute("SELECT * FROM reminders WHERE phase = ?", (phase,))]


def list_reminders() -> list[dict]:
    """Every reminder with its series' current facts (the derived UI fields are added by the API)."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT r.*, s.last_amount AS amount, s.cadence AS cadence, s.monthly_equiv AS monthly_equiv, "
            "s.cancellable AS cancellable, s.merchant AS series_merchant, s.status AS series_status "
            "FROM reminders r LEFT JOIN series s ON s.id = r.series_id ORDER BY r.updated_at DESC").fetchall()
    return [_reminder(r) for r in rows]


def charges_after(series_id: int, after: str) -> dict:
    """{covers_until: latest stored transaction date, charges_after: [{date, amount}] for this merchant}."""
    with connect() as conn:
        covers = conn.execute("SELECT MAX(tx_date) FROM transactions").fetchone()[0]
        merchant = conn.execute(
            "SELECT COALESCE(s.merchant, r.merchant) FROM reminders r LEFT JOIN series s ON s.id = r.series_id "
            "WHERE r.series_id = ?", (series_id,)).fetchone()
        rows = conn.execute(
            "SELECT tx_date, amount FROM transactions WHERE direction = 'debit' AND merchant = ? AND tx_date > ? "
            "ORDER BY tx_date", (merchant[0] if merchant else None, after)).fetchall()
    return {"covers_until": covers, "charges_after": [{"date": r["tx_date"], "amount": r["amount"]} for r in rows]}


def series_facts(series_id: int) -> dict:
    """What a reminder note may say about a merchant (spec §7.10)."""
    s = series_by_id(series_id)
    r = get_reminder(series_id)
    meta = report_meta() or {}
    if s is None and r is None:
        return {}
    details = (s or {}).get("flag_details_json") or {}
    return {
        "merchant": (s or r)["merchant"], "currency": meta.get("currency") or "USD",
        "amount": (s or {}).get("last_amount"), "cadence": (s or {}).get("cadence"),
        "monthly_equiv": (s or {}).get("monthly_equiv"),
        "next_due": (r or {}).get("next_due_date") or (s or {}).get("next_due_date"),
        "price_creep": details.get("price_creep"), "duplicates": details.get("duplicate_charge", []),
        "cancelled_on": (r or {}).get("cancelled_on"),
    }


# ── notifications ───────────────────────────────────────────────────────────

def insert_notification(series_id: int, kind: str, title: str, body: str) -> int:
    with connect() as conn:
        cur = conn.execute("INSERT INTO notifications(series_id, kind, title, body, created_at) VALUES(?, ?, ?, ?, ?)",
                           (series_id, kind, title, body, now_iso()))
        return int(cur.lastrowid)


def notifications_since(since_id: int) -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM notifications WHERE id > ? ORDER BY id", (since_id,))]


def notifications_all(limit: int = 50) -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM notifications ORDER BY id DESC LIMIT ?", (limit,))]


def mark_read(notification_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("UPDATE notifications SET read_at = COALESCE(read_at, ?) WHERE id = ?",
                           (now_iso(), notification_id))
        return cur.rowcount == 1


def mark_all_read() -> None:
    with connect() as conn:
        conn.execute("UPDATE notifications SET read_at = ? WHERE read_at IS NULL", (now_iso(),))
