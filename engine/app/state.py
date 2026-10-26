"""Mutable state shared by routes and background tasks — one set per workspace (WEB-IMPL §2.2).

`runtime.pipeline_lock`, `runtime.pending` and the task handles resolve to the *current* workspace's slot, so each
user has their own audit lock, pending uploads and background work; the desktop (no workspace) has one slot, as
before. `audit_slots()` caps audits and re-scores across all workspaces, since TabPFN shares the server's CPU.
"""

import asyncio
import os
import weakref
from types import SimpleNamespace

from . import workspace

MAX_AUDITS = int(os.environ.get("SLOTH_MAX_AUDITS", "2"))


def _fresh() -> SimpleNamespace:
    return SimpleNamespace(
        scheduler_task=None,  # asyncio.Task running reminders.run_scheduler() (process-wide; desktop slot)
        pipeline_lock=asyncio.Lock(),  # one audit / re-score at a time in this workspace (IMPL §3.4)
        pending={},  # import_id -> raw CSV bytes awaiting /confirm
        pipeline_task=None,  # the running audit (report.start_pipeline)
        normalize_task=None,  # Gemma finishing deferred merchant names in the background
    )


class _PerWorkspace:
    """Attribute access goes to the current workspace's namespace."""

    def __init__(self) -> None:
        object.__setattr__(self, "_slots", {})

    def _slot(self) -> SimpleNamespace:
        slots = object.__getattribute__(self, "_slots")
        ws = workspace.current.get()
        if ws not in slots:
            slots[ws] = _fresh()
        return slots[ws]

    def __getattr__(self, name: str):
        return getattr(self._slot(), name)

    def __setattr__(self, name: str, value) -> None:
        setattr(self._slot(), name, value)

    def drop(self, workspace_id: str) -> None:
        """Forget a deleted workspace's state (its tasks must already be cancelled)."""
        object.__getattribute__(self, "_slots").pop(workspace_id, None)


runtime = _PerWorkspace()

_audit_slots: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()  # event loop → Semaphore


def audit_slots() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    if loop not in _audit_slots:
        _audit_slots[loop] = asyncio.Semaphore(max(1, MAX_AUDITS))
    return _audit_slots[loop]
