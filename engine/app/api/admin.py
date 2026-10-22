"""Admin routes: delete all local data (IMPL M8.4) and shut down (M1)."""

import asyncio
import os

from fastapi import APIRouter, HTTPException

from .. import db, report
from ..state import runtime

router = APIRouter()


@router.delete("/data")
async def delete_data() -> dict:
    """Settings › Delete all local data: statements, merchant edits, chats, reminders. Settings and models stay."""
    if report.busy():
        raise HTTPException(409, "An audit is running. Try again when it finishes.")
    if runtime.normalize_task and not runtime.normalize_task.done():
        runtime.normalize_task.cancel()  # it would write merchant names for deleted rows
    runtime.pending.clear()
    await asyncio.to_thread(db.wipe)
    return {"ok": True}


@router.post("/shutdown")
async def shutdown() -> dict:
    # Answer first, then exit; Electron main follows up by closing our stdin anyway.
    asyncio.get_running_loop().call_later(0.2, os._exit, 0)
    return {"ok": True}
