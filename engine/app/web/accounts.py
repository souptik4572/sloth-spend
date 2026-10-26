"""Accounts, sessions, email tokens and rate limits in <SLOTH_DATA_DIR>/accounts.db (WEB-IMPL §2.3).

Secrets are never stored: sessions and email links are random tokens kept only as SHA-256 digests, passwords as
scrypt hashes. Each account's statement data lives in its own workspace database (app/workspace.py).
"""

import hashlib
import secrets
import sqlite3
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..config import settings

SCHEMA_VERSION = 1
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,                       -- uuid4 hex; also the workspace folder name
  email TEXT UNIQUE NOT NULL,                -- lower-cased
  name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  email_verified_at TEXT,
  terms_accepted_at TEXT,
  created_at TEXT NOT NULL,
  password_changed_at TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  persistent INTEGER NOT NULL,               -- "Keep me logged in on this device"
  created_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  user_agent TEXT
);
CREATE INDEX IF NOT EXISTS ix_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS email_tokens (
  token_hash TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  purpose TEXT NOT NULL CHECK (purpose IN ('verify','reset','login')),
  remember INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  used_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_email_tokens_user ON email_tokens(user_id, purpose);

CREATE TABLE IF NOT EXISTS throttle (key TEXT NOT NULL, at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ix_throttle ON throttle(key, at);
"""

PERSISTENT = timedelta(days=30)  # sliding, for "Keep me logged in"
BROWSER_SESSION = timedelta(hours=12)  # sliding; the cookie itself ends with the browser session
TOUCH_EVERY = timedelta(minutes=5)  # how often a busy session's expiry is pushed back
TOKEN_TTL = {"verify": timedelta(hours=24), "reset": timedelta(hours=1), "login": timedelta(minutes=15)}


def path() -> Path:
    return settings.data_dir / "accounts.db"


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(path(), timeout=5)
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
    path().parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


# ── users ───────────────────────────────────────────────────────────────────

def normalize_email(email: str) -> str:
    return email.strip().lower()


def public(user: dict) -> dict:
    """What the browser may see about an account."""
    return {"id": user["id"], "email": user["email"], "name": user["name"], "created_at": user["created_at"]}


def create_user(email: str, name: str, password_hash: str) -> dict:
    user = {"id": uuid.uuid4().hex, "email": normalize_email(email), "name": name, "password_hash": password_hash,
            "created_at": iso(now())}
    with connect() as conn:
        conn.execute("INSERT INTO users(id, email, name, password_hash, terms_accepted_at, created_at) "
                     "VALUES(?, ?, ?, ?, ?, ?)",
                     (user["id"], user["email"], name, password_hash, user["created_at"], user["created_at"]))
    return get_user(user["id"])


def get_user(user_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def user_by_email(email: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (normalize_email(email),)).fetchone()
    return dict(row) if row else None


def mark_verified(user_id: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE users SET email_verified_at = COALESCE(email_verified_at, ?) WHERE id = ?",
                     (iso(now()), user_id))


def set_password(user_id: str, password_hash: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE users SET password_hash = ?, password_changed_at = ? WHERE id = ?",
                     (password_hash, iso(now()), user_id))


def delete_user(user_id: str) -> None:
    """Sessions and email tokens go with it (ON DELETE CASCADE)."""
    with connect() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


# ── sessions ────────────────────────────────────────────────────────────────

def create_session(user_id: str, persistent: bool, user_agent: str | None = None) -> str:
    token = secrets.token_urlsafe(32)
    t = now()
    life = PERSISTENT if persistent else BROWSER_SESSION
    with connect() as conn:
        conn.execute("INSERT INTO sessions(token_hash, user_id, persistent, created_at, last_seen_at, expires_at, "
                     "user_agent) VALUES(?, ?, ?, ?, ?, ?, ?)",
                     (digest(token), user_id, int(persistent), iso(t), iso(t), iso(t + life),
                      (user_agent or "")[:200]))
    return token


def session_user(token: str) -> dict | None:
    """The signed-in user for a session token, or None. Pushes a live session's expiry back (sliding)."""
    t = now()
    with connect() as conn:
        row = conn.execute(
            "SELECT s.token_hash, s.persistent, s.last_seen_at, s.expires_at, u.* FROM sessions s "
            "JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?", (digest(token),)).fetchone()
        if row is None:
            return None
        if row["expires_at"] <= iso(t) or row["email_verified_at"] is None:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (row["token_hash"],))
            return None
        if datetime.fromisoformat(row["last_seen_at"]) + TOUCH_EVERY <= t:
            life = PERSISTENT if row["persistent"] else BROWSER_SESSION
            conn.execute("UPDATE sessions SET last_seen_at = ?, expires_at = ? WHERE token_hash = ?",
                         (iso(t), iso(t + life), row["token_hash"]))
    user = dict(row)
    for key in ("token_hash", "persistent", "last_seen_at", "expires_at"):
        user.pop(key)
    user["session_persistent"] = bool(row["persistent"])
    return user


def delete_session(token: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (digest(token),))


def delete_sessions(user_id: str, keep_token: str | None = None) -> int:
    """Log an account out everywhere (except, optionally, the current device). Returns how many ended."""
    with connect() as conn:
        cur = conn.execute("DELETE FROM sessions WHERE user_id = ? AND token_hash != ?",
                           (user_id, digest(keep_token) if keep_token else ""))
    return cur.rowcount


# ── email links ─────────────────────────────────────────────────────────────

def issue_token(user_id: str, purpose: str, *, remember: bool = True) -> str:
    """A single-use link token. A new reset link cancels any older unused one."""
    token = secrets.token_urlsafe(32)
    t = now()
    with connect() as conn:
        if purpose == "reset":
            conn.execute("UPDATE email_tokens SET used_at = ? WHERE user_id = ? AND purpose = 'reset' "
                         "AND used_at IS NULL", (iso(t), user_id))
        conn.execute("INSERT INTO email_tokens(token_hash, user_id, purpose, remember, created_at, expires_at) "
                     "VALUES(?, ?, ?, ?, ?, ?)",
                     (digest(token), user_id, purpose, int(remember), iso(t), iso(t + TOKEN_TTL[purpose])))
    return token


def _valid_token(conn: sqlite3.Connection, token: str, purpose: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM email_tokens WHERE token_hash = ? AND purpose = ? AND used_at IS NULL AND expires_at > ?",
        (digest(token), purpose, iso(now()))).fetchone()


def peek_token(token: str, purpose: str) -> dict | None:
    """The token's row if it is still usable, without using it (the reset screen shows whose password)."""
    with connect() as conn:
        row = _valid_token(conn, token, purpose)
    return dict(row) if row else None


def consume_token(token: str, purpose: str) -> dict | None:
    """Use a token once. Two clicks on one link: only the first wins."""
    with connect() as conn:
        row = _valid_token(conn, token, purpose)
        if row is None:
            return None
        cur = conn.execute("UPDATE email_tokens SET used_at = ? WHERE token_hash = ? AND used_at IS NULL",
                           (iso(now()), row["token_hash"]))
        if cur.rowcount != 1:
            return None
    return dict(row)


def revoke_tokens(user_id: str, purpose: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE email_tokens SET used_at = ? WHERE user_id = ? AND purpose = ? AND used_at IS NULL",
                     (iso(now()), user_id, purpose))


# ── rate limits ─────────────────────────────────────────────────────────────

def hits(key: str, window_seconds: float) -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM throttle WHERE key = ? AND at > ?",
                            (key, time.time() - window_seconds)).fetchone()[0]


def hit(key: str) -> None:
    with connect() as conn:
        conn.execute("INSERT INTO throttle(key, at) VALUES(?, ?)", (key, time.time()))
        conn.execute("DELETE FROM throttle WHERE at < ?", (time.time() - 86400,))  # keep a day at most


def clear_hits(key: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM throttle WHERE key = ?", (key,))
