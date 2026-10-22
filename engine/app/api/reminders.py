"""Reminder routes (spec §8, IMPL M7.4): list them, and the user's decisions from the §7.10 table.

A decision the current phase doesn't allow answers 409 with that phase (a click raced a tick, or a fourth snooze).
"""

import asyncio
from datetime import date

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .. import db, reminders, report

router = APIRouter()

GROUPS = {"REMINDED": "needs_you", "STILL_CHARGED": "needs_you", "WATCHING": "watching", "SNOOZED": "watching",
          "AWAITING_STATEMENT": "watching"}
GROUP_ORDER = {"needs_you": 0, "watching": 1, "done": 2}


def _checked(row: dict) -> dict | None:
    """What the statement check found: the charge after cancelling, or how far the statements now reach."""
    if row["phase"] not in ("STILL_CHARGED", "VERIFIED_STOPPED") or not row["cancelled_on"]:
        return None
    check = db.charges_after(row["series_id"], row["cancelled_on"])
    if row["phase"] == "STILL_CHARGED" and check["charges_after"]:
        return check["charges_after"][0]
    return {"date": check["covers_until"], "amount": None}


def view(row: dict) -> dict:
    """A reminder row plus what the cards need (IMPL §3.2)."""
    due = row["next_due_date"]
    phase = row["phase"]
    return {
        "series_id": row["series_id"], "merchant": row.get("series_merchant") or row["merchant"],
        "amount": row.get("amount"), "cadence": row.get("cadence"), "monthly_equiv": row.get("monthly_equiv"),
        "low_confidence": row.get("cadence") == "single", "cancellable": bool(row.get("cancellable")),
        "next_due_date": due, "days_left": (date.fromisoformat(due) - date.today()).days if due else None,
        "phase": phase, "group": GROUPS.get(phase, "done"), "detail": row["detail"],
        "days_before": row["days_before"], "remind_at": row["remind_at"],
        "remind_on": row["remind_at"][:10] if row["remind_at"] and phase in ("WATCHING", "SNOOZED") else None,
        "reminders_sent": row["reminders_sent"], "max_reminders": reminders.MAX_REMINDERS,
        "cancelled_on": row["cancelled_on"], "events": row["events"], "checked": _checked(row),
    }


def one(series_id: int) -> dict | None:
    row = next((r for r in db.list_reminders() if r["series_id"] == series_id), None)
    return view(row) if row else None


def all_views() -> list[dict]:
    rows = [view(r) for r in db.list_reminders()]
    return sorted(rows, key=lambda r: (GROUP_ORDER[r["group"]], r["next_due_date"] or "9999"))


# Why an action can't happen right now, in the words of the phase it's in.
PHASE_WORDS = {
    None: "there's no reminder for this merchant yet", "WATCHING": "a reminder is already set",
    "REMINDED": "it's waiting for your answer", "SNOOZED": "it's snoozed", "KEPT": "you're keeping it",
    "AWAITING_STATEMENT": "it's waiting for your next statement", "STILL_CHARGED": "it was charged again",
    "VERIFIED_STOPPED": "the charge already stopped", "EXPIRED": "it expired", "STOPPED": "it's stopped",
}


def _conflict(action: str, phase: str | None, sent: int | None) -> str:
    if action == "snooze" and phase == "REMINDED" and (sent or 0) >= reminders.MAX_REMINDERS:
        return (f"That was the last of {reminders.MAX_REMINDERS} reminders, so it can't be snoozed again. "
                "Keep it, or cancel it yourself.")
    return f"That isn't possible right now: {PHASE_WORDS.get(phase, 'it changed')}."


async def _act(fn, *args) -> dict | JSONResponse:
    try:
        row = await asyncio.to_thread(fn, *args)
    except reminders.NotFound as exc:
        raise HTTPException(404, "That merchant isn't in the report.") from exc
    except reminders.NoRenewal as exc:
        raise HTTPException(400, "SlothSpend can't predict when this renews, so it can't remind you.") from exc
    except reminders.Conflict as exc:
        row = await asyncio.to_thread(db.get_reminder, args[0])
        detail = _conflict(fn.__name__, exc.phase, (row or {}).get("reminders_sent"))
        return JSONResponse({"detail": detail, "phase": exc.phase}, status_code=409)
    return {"series_id": row["series_id"], "phase": row["phase"], "remind_at": row["remind_at"],
            "reminder": await asyncio.to_thread(one, row["series_id"])}


class CreateRequest(BaseModel):
    series_id: int
    days_before: int | None = Field(None, ge=1, le=14)


class SnoozeRequest(BaseModel):
    days: int = Field(ge=1, le=14)


class CancelledRequest(BaseModel):
    cancelled_on: date


@router.get("/reminders")
async def list_reminders() -> list[dict]:
    return await asyncio.to_thread(all_views)


@router.post("/reminders")
async def create(req: CreateRequest):
    return await _act(reminders.create, req.series_id, req.days_before)


@router.post("/reminders/{series_id}/keep")
async def keep(series_id: int):
    return await _act(reminders.keep, series_id)


@router.post("/reminders/{series_id}/snooze")
async def snooze(series_id: int, req: SnoozeRequest):
    return await _act(reminders.snooze, series_id, req.days)


@router.post("/reminders/{series_id}/stop")
async def stop(series_id: int):
    return await _act(reminders.stop, series_id)


@router.post("/reminders/{series_id}/cancelled")
async def cancelled(series_id: int, req: CancelledRequest):
    """Marks the series user-cancelled too, so the report is re-scored without it (unless an audit is running)."""
    out = await _act(reminders.cancelled, series_id, req.cancelled_on.isoformat())
    if isinstance(out, dict) and not report.busy():
        out["report"] = await report.rescore()
    return out
