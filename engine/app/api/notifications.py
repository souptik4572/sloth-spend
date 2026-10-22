"""Notification routes (spec §8, IMPL §3.2): polling, the inbox, and read state."""

import asyncio

from fastapi import APIRouter, HTTPException

from .. import db

router = APIRouter()


@router.get("/notifications")
async def notifications(since_id: int = 0, all: bool = False) -> list[dict]:  # noqa: A002 — the API's own name
    """?since_id=N for polling (oldest first), or ?all=1 for the inbox (newest 50, with read_at)."""
    if all:
        return await asyncio.to_thread(db.notifications_all, 50)
    return await asyncio.to_thread(db.notifications_since, since_id)


@router.post("/notifications/read-all")
async def read_all() -> dict:
    await asyncio.to_thread(db.mark_all_read)
    return {"ok": True}


@router.post("/notifications/{notification_id}/read")
async def read(notification_id: int) -> dict:
    if not await asyncio.to_thread(db.mark_read, notification_id):
        raise HTTPException(404, "No such notification.")
    return {"ok": True}
