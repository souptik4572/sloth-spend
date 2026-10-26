"""Tenancy (WEB-IMPL §2.2): whose data a request or a background task touches.

The desktop app never sets a workspace, so everything uses the one local database exactly as before. On the web
the session middleware sets `current` for the whole request, streamed responses included; asyncio copies it into
`to_thread` workers and into tasks created inside, so background work stays in the workspace that started it.

Each workspace is a folder holding its own SQLite file. Every SQL statement, the singleton report row and the
read-only SQL tool stay correct per user, and a query can't reach another user's file.
"""

import re
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from .config import settings

DESKTOP_DB = settings.data_dir / "slothspend.db"
ID = re.compile(r"^[0-9a-f]{32}$")  # account ids are uuid4 hex: always a safe folder name

current: ContextVar[str | None] = ContextVar("sloth_workspace", default=None)
_ready: set[str] = set()


def root() -> Path:
    return settings.data_dir / "workspaces"


def folder(workspace_id: str) -> Path:
    if not ID.match(workspace_id):
        raise ValueError(f"not a workspace id: {workspace_id!r}")
    return root() / workspace_id


def on_web() -> bool:
    """Serving SlothSpend Web (a person's workspace is set), not the desktop app on this computer."""
    return current.get() is not None


def db_path() -> Path:
    """The current workspace's database, or the desktop's."""
    ws = current.get()
    return DESKTOP_DB if ws is None else folder(ws) / "slothspend.db"


def ensure(workspace_id: str) -> None:
    """Create the folder and schema once per process (cheap afterwards)."""
    if workspace_id in _ready:
        return
    from . import db  # db imports this module

    folder(workspace_id).mkdir(parents=True, exist_ok=True)
    token = current.set(workspace_id)
    try:
        db.init()
    finally:
        current.reset(token)
    _ready.add(workspace_id)


@contextmanager
def use(workspace_id: str | None) -> Iterator[None]:
    """Run a block as one workspace (None = the desktop database)."""
    if workspace_id is not None:
        ensure(workspace_id)
    token = current.set(workspace_id)
    try:
        yield
    finally:
        current.reset(token)


def all_ids() -> list[str]:
    """Every workspace on disk, for the reminder scheduler."""
    if not root().is_dir():
        return []
    return sorted(p.name for p in root().iterdir() if p.is_dir() and ID.match(p.name))


def remove(workspace_id: str) -> None:
    """Delete a workspace's folder and everything in it (account deletion)."""
    _ready.discard(workspace_id)
    shutil.rmtree(folder(workspace_id), ignore_errors=True)
