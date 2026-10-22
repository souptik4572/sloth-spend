"""Renewal reminders (spec §7.10, IMPL M7.1). Inform only: SlothSpend never cancels anything.

No workflow engine: rows in `reminders` plus one asyncio loop that ticks at startup (the catch-up) and every
30 s. Every change is compare-and-set on the current phase, so a click and a tick can't overwrite each other.
Delivery is at-least-once. With demo compression on, every wait becomes N seconds.
"""

import asyncio
import logging
from datetime import date, datetime, time, timedelta, timezone

from . import db, user_settings
from .money import date_long
from .notes import gemma_note, template_note

log = logging.getLogger(__name__)

TICK_SECONDS = 30
MAX_REMINDERS = 3
GEMMA_BACKOFF = [5, 10, 20]  # seconds between attempts, then fall back to a template
AWAIT_DAYS = 60
ENDED = db.FINAL_PHASES


class Conflict(Exception):
    """The reminder's current phase doesn't allow this action (HTTP 409)."""

    def __init__(self, phase: str | None):
        super().__init__(phase)
        self.phase = phase


class NoRenewal(Exception):
    """The series has no predictable renewal date (HTTP 400)."""


class NotFound(Exception):
    pass


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def renewal_at(next_due_iso: str) -> datetime:
    return datetime.combine(date.fromisoformat(next_due_iso), time(9, 0), tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _demo() -> int:
    return user_settings.load().demo_compress_seconds


def remind_at_for(next_due: str, days_before: int, demo: int) -> str:
    if demo:
        return _iso(now_utc() + timedelta(seconds=demo))
    return _iso(max(renewal_at(next_due) - timedelta(days=days_before), now_utc()))


# ── sending ─────────────────────────────────────────────────────────────────

async def draft(kind: str, facts: dict) -> dict:
    """Local Gemma with retries; falls back to a template so a reminder never fails."""
    for delay in GEMMA_BACKOFF:
        try:
            return await gemma_note(kind, facts)
        except Exception as exc:  # noqa: BLE001
            log.warning("Gemma unavailable for %s note (%s); retrying in %ss", kind, exc, delay)
            await asyncio.sleep(delay)
    log.info("using the template for the %s note", kind)
    return template_note(kind, facts)


_background: set[asyncio.Task] = set()


def _later(coro) -> None:
    """Run a note in the background (an import must not wait out Gemma's retries)."""
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


async def send(row: dict, kind: str, **extra) -> None:
    facts = {**await asyncio.to_thread(db.series_facts, row["series_id"]), **extra}
    note = await draft(kind, facts)
    await asyncio.to_thread(db.insert_notification, row["series_id"], kind, note["title"], note["body"])


async def tick() -> None:
    demo = await asyncio.to_thread(_demo)
    for row in await asyncio.to_thread(db.due_reminders, _iso(now_utc())):
        sid, phase = row["series_id"], row["phase"]
        if phase in ("WATCHING", "SNOOZED"):
            await send(row, "reminder")
            if demo:
                answer_by = now_utc() + timedelta(seconds=demo)
            else:  # wait for an answer until renewal + 3 days, but always at least a day
                answer_by = max(renewal_at(row["next_due_date"]) + timedelta(days=3), now_utc() + timedelta(days=1))
            await asyncio.to_thread(
                db.transition, sid, phase, "REMINDED",
                remind_at=_iso(answer_by), reminders_sent=row["reminders_sent"] + 1,
                detail=f"Renews {date_long(row['next_due_date'])}. Keep it, or cancel it yourself?")
        elif phase == "REMINDED":
            await asyncio.to_thread(db.transition, sid, phase, "EXPIRED", remind_at=None,
                                    detail="The renewal passed without an answer. Set a new reminder any time.")
        elif phase == "AWAITING_STATEMENT":
            await asyncio.to_thread(db.transition, sid, phase, "EXPIRED", remind_at=None,
                                    detail="No newer statement arrived within 60 days.")


async def verify_after_import() -> int:
    """Called at the end of every import (§7.8). Returns how many cancelled subscriptions it could check."""
    checked = 0
    for row in await asyncio.to_thread(db.reminders_in_phase, "AWAITING_STATEMENT"):
        sid = row["series_id"]
        check = await asyncio.to_thread(db.charges_after, sid, row["cancelled_on"])
        covers = check["covers_until"]
        if check["charges_after"]:
            first = check["charges_after"][0]
            kind, phase, extra = "still_charged", "STILL_CHARGED", {"charged_on": first["date"],
                                                                    "charged_amount": first["amount"]}
            detail = f"Charged again on {date_long(first['date'])}"
        elif covers and covers >= row["next_due_date"]:
            kind, phase, extra = "verified", "VERIFIED_STOPPED", {"covers_until": covers}
            detail = f"No charge through {date_long(covers)}"
        else:
            ends = date_long(covers) if covers else "early"
            await asyncio.to_thread(
                db.transition, sid, "AWAITING_STATEMENT", "AWAITING_STATEMENT",
                detail=f"That statement ends {ends}, before the renewal. Import a later one.")
            continue
        if await asyncio.to_thread(db.transition, sid, "AWAITING_STATEMENT", phase, remind_at=None, detail=detail):
            _later(send(row, kind, **extra))
            checked += 1
    return checked


async def run_scheduler() -> None:
    while True:  # the first tick runs at startup: anything that came due while closed fires now
        try:
            await tick()
        except Exception:  # noqa: BLE001 — one bad row must never stop reminders
            log.exception("reminder tick failed")
        await asyncio.sleep(TICK_SECONDS)


# ── user actions (§7.10 table; called from api/reminders.py in a thread) ─────

def _series(series_id: int) -> dict:
    s = db.series_by_id(series_id)
    if s is None:
        raise NotFound
    return s


def create(series_id: int, days_before: int | None = None) -> dict:
    """Remind me N days before the renewal: a new row, an ended one reset, or a WATCHING one re-timed."""
    s = _series(series_id)
    if not s["next_due_date"]:
        raise NoRenewal
    days = days_before or user_settings.load().days_before
    at = remind_at_for(s["next_due_date"], days, _demo())
    row = db.get_reminder(series_id)
    if row and row["phase"] == "WATCHING":
        db.transition(series_id, "WATCHING", "WATCHING", days_before=days, remind_at=at,
                      next_due_date=s["next_due_date"])
        return db.get_reminder(series_id)
    if row and row["phase"] not in ENDED:
        raise Conflict(row["phase"])
    return db.put_reminder(series_id, "WATCHING", merchant=s["merchant"], next_due_date=s["next_due_date"],
                           days_before=days, remind_at=at)


def keep(series_id: int) -> dict:
    if not db.transition(series_id, ("WATCHING", "REMINDED", "SNOOZED"), "KEPT", remind_at=None,
                         detail="You’re keeping it."):
        raise Conflict((db.get_reminder(series_id) or {}).get("phase"))
    return db.get_reminder(series_id)


def snooze(series_id: int, days: int) -> dict:
    row = db.get_reminder(series_id)
    if row is None or row["phase"] != "REMINDED" or row["reminders_sent"] >= MAX_REMINDERS:
        raise Conflict(row["phase"] if row else None)
    demo = _demo()
    at = now_utc() + (timedelta(seconds=demo) if demo else timedelta(days=days))
    if not db.transition(series_id, "REMINDED", "SNOOZED", remind_at=_iso(at),
                         detail=f"Snoozed until {date_long(at.date().isoformat())}."):
        raise Conflict((db.get_reminder(series_id) or {}).get("phase"))
    return db.get_reminder(series_id)


def cancelled(series_id: int, cancelled_on: str) -> dict:
    """"I cancelled it": from any phase, or with no reminder yet. Then wait for a statement that shows it stopped."""
    s = _series(series_id)
    day = date.fromisoformat(cancelled_on).isoformat()
    demo = _demo()
    expiry = _iso(now_utc() + (timedelta(seconds=demo) if demo else timedelta(days=AWAIT_DAYS)))
    detail = "Waiting for your next statement."
    row = db.get_reminder(series_id)
    if row is None:
        if not s["next_due_date"]:
            raise NoRenewal
        db.put_reminder(series_id, "AWAITING_STATEMENT", merchant=s["merchant"], next_due_date=s["next_due_date"],
                        days_before=user_settings.load().days_before, remind_at=expiry, cancelled_on=day,
                        detail=detail)
    elif not db.transition(series_id, row["phase"], "AWAITING_STATEMENT", remind_at=expiry, cancelled_on=day,
                           detail=detail):
        raise Conflict((db.get_reminder(series_id) or {}).get("phase"))
    db.set_series_status(s["merchant"], "user_cancelled")
    return db.get_reminder(series_id)


def stop(series_id: int) -> dict:
    if not db.transition(series_id, db.ACTIVE_PHASES, "STOPPED", remind_at=None, detail="You stopped this reminder."):
        raise Conflict((db.get_reminder(series_id) or {}).get("phase"))
    return db.get_reminder(series_id)


def resync_after_report() -> int:
    """A new report can move a renewal date: re-time WATCHING rows (others keep the date they were set on)."""
    demo = _demo()
    moved = 0
    for row in db.reminders_in_phase("WATCHING"):
        s = db.series_by_id(row["series_id"])
        due = (s or {}).get("next_due_date")
        if not due or due == row["next_due_date"]:
            continue
        fields = {"next_due_date": due}
        if not demo:
            fields["remind_at"] = remind_at_for(due, row["days_before"], 0)
        moved += db.transition(row["series_id"], "WATCHING", "WATCHING", **fields)
    return moved
