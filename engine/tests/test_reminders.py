"""Renewal reminders (spec §13.1, IMPL M7.11): a controllable clock, Gemma mocked, tick() and
verify_after_import() called directly, plus the routes and their 409s."""

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone

import pytest
from conftest import sse

from app import db, reminders, report


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def to(self, *args) -> None:
        self.now = datetime(*args, tzinfo=timezone.utc)


@pytest.fixture()
def clock(monkeypatch) -> Clock:
    c = Clock()
    monkeypatch.setattr(reminders, "now_utc", c)
    monkeypatch.setattr(reminders, "GEMMA_BACKOFF", [0, 0, 0])
    return c


@pytest.fixture()
def notes(monkeypatch) -> list:
    """Gemma stand-in: records each request and writes a fixed note."""
    calls = []

    async def fake(kind, facts):
        calls.append((kind, facts))
        return {"title": f"{facts['merchant']} {kind}", "body": "Gemma's note."}

    monkeypatch.setattr(reminders, "gemma_note", fake)
    return calls


def sid(rep: dict, merchant: str) -> int:
    return next(s["id"] for s in rep["series"] if s["merchant"] == merchant)


def tick() -> None:
    asyncio.run(reminders.tick())


def notices() -> list[dict]:
    return db.notifications_since(0)


# ── the scheduler ───────────────────────────────────────────────────────────

def test_nothing_before_remind_at_then_one_reminder(sample_report, clock, notes):
    iron = sid(sample_report, "IronTrap Fitness")
    row = reminders.create(iron, 3)
    assert row["phase"] == "WATCHING" and row["remind_at"] == "2026-11-02T09:00:00+00:00"  # renewal Nov 5 − 3 days
    tick()
    assert notices() == [] and db.get_reminder(iron)["phase"] == "WATCHING"

    clock.to(2026, 11, 2, 9)
    tick()
    tick()  # a second tick in the same minute sends nothing more
    assert [(n["kind"], n["title"]) for n in notices()] == [("reminder", "IronTrap Fitness reminder")]
    row = db.get_reminder(iron)
    assert row["phase"] == "REMINDED" and row["reminders_sent"] == 1
    assert row["remind_at"] == "2026-11-08T09:00:00+00:00"  # answer by renewal + 3 days
    assert notes[0][1]["next_due"] == "2026-11-05" and notes[0][1]["amount"] == 49.99


def test_keep_and_a_keep_during_a_tick(sample_report, clock, notes, monkeypatch):
    iron, tune = sid(sample_report, "IronTrap Fitness"), sid(sample_report, "TuneTide")
    reminders.create(iron, 3)
    assert reminders.keep(iron)["phase"] == "KEPT"
    with pytest.raises(reminders.Conflict):
        reminders.keep(iron)

    # The user taps Keep while the scheduler is drafting the note: the tick must not overwrite it.
    reminders.create(tune, 3)
    clock.to(2026, 11, 16, 9)
    real_send = reminders.send

    async def send_then_keep(row, kind, **extra):
        await real_send(row, kind, **extra)
        reminders.keep(row["series_id"])

    monkeypatch.setattr(reminders, "send", send_then_keep)
    tick()
    assert db.get_reminder(tune)["phase"] == "KEPT"


def test_no_answer_expires_after_renewal_plus_three_days(sample_report, clock, notes):
    iron = sid(sample_report, "IronTrap Fitness")
    reminders.create(iron, 3)
    clock.to(2026, 11, 2, 9)
    tick()
    clock.to(2026, 11, 8, 8, 59)
    tick()
    assert db.get_reminder(iron)["phase"] == "REMINDED"
    clock.to(2026, 11, 8, 9)
    tick()
    row = db.get_reminder(iron)
    assert row["phase"] == "EXPIRED" and row["remind_at"] is None
    assert [e["phase"] for e in row["events"]] == ["WATCHING", "REMINDED", "EXPIRED"]  # events_json history


def test_snooze_then_a_second_reminder_and_the_cap(client, auth, sample_report, clock, notes):
    iron = sid(sample_report, "IronTrap Fitness")
    reminders.create(iron, 3)
    clock.to(2026, 11, 2, 9)
    tick()
    out = client.post(f"/reminders/{iron}/snooze", headers=auth, json={"days": 2}).json()
    assert out["phase"] == "SNOOZED" and out["remind_at"] == "2026-11-04T09:00:00+00:00"
    clock.to(2026, 11, 3, 9)
    tick()
    assert len(notices()) == 1
    clock.to(2026, 11, 4, 9)
    tick()
    assert len(notices()) == 2 and db.get_reminder(iron)["reminders_sent"] == 2

    assert client.post(f"/reminders/{iron}/snooze", headers=auth, json={"days": 1}).status_code == 200
    clock.to(2026, 11, 5, 9)
    tick()
    assert db.get_reminder(iron)["reminders_sent"] == reminders.MAX_REMINDERS
    capped = client.post(f"/reminders/{iron}/snooze", headers=auth, json={"days": 1})
    assert capped.status_code == 409 and capped.json()["phase"] == "REMINDED"
    assert capped.json()["detail"].startswith("That was the last of 3 reminders")


def test_gemma_failing_every_attempt_sends_the_template(sample_report, clock, monkeypatch):
    attempts = []

    async def broken(kind, facts):
        attempts.append(kind)
        raise ConnectionError("Ollama is not running")

    monkeypatch.setattr(reminders, "gemma_note", broken)
    iron = sid(sample_report, "IronTrap Fitness")
    reminders.create(iron, 3)
    clock.to(2026, 11, 2, 9)
    tick()
    assert attempts == ["reminder"] * 3
    [n] = notices()
    assert n["title"] == "IronTrap Fitness renews Nov 5"
    assert n["body"] == ("IronTrap Fitness renews Nov 5 for $49.99. If you no longer use it, open How to cancel in "
                         "SlothSpend — or tap Keep it.")


def test_catch_up_on_the_first_tick(sample_report, clock, notes):
    """A row that came due while SlothSpend was closed fires as soon as a fresh scheduler starts."""
    iron = sid(sample_report, "IronTrap Fitness")
    reminders.create(iron, 3)
    clock.to(2026, 11, 3, 9)  # a day late

    async def start_scheduler_briefly():
        task = asyncio.create_task(reminders.run_scheduler())
        for _ in range(50):
            await asyncio.sleep(0.01)
            if notices():
                break
        task.cancel()

    asyncio.run(start_scheduler_briefly())
    assert len(notices()) == 1 and db.get_reminder(iron)["phase"] == "REMINDED"


def test_demo_compression(sample_report, clock, notes):
    db.set_settings({"demo_compress_seconds": "30"})
    iron = sid(sample_report, "IronTrap Fitness")
    assert reminders.create(iron)["remind_at"] == "2026-10-16T12:00:30+00:00"
    clock.now += timedelta(seconds=30)
    tick()
    assert db.get_reminder(iron)["remind_at"] == "2026-10-16T12:01:00+00:00"  # answer-by: N seconds too
    clock.now += timedelta(seconds=30)
    tick()
    assert db.get_reminder(iron)["phase"] == "EXPIRED"


# ── I cancelled it → the next statement ─────────────────────────────────────

def load(client, file: str) -> dict:
    events = sse(client, "/demo/load-sample", {"file": file})
    assert events[-1][0] == "done", events[-1]
    for _ in range(200):  # the statement-check note is written in the background, on the app's loop
        if notices():
            break
        time.sleep(0.01)
    return events[-1][1]["report"]


def test_verified_stopped(client, auth, sample_report, clock, notes):
    iron = sid(sample_report, "IronTrap Fitness")
    out = client.post(f"/reminders/{iron}/cancelled", headers=auth, json={"cancelled_on": "2026-10-16"}).json()
    assert out["phase"] == "AWAITING_STATEMENT" and out["reminder"]["cancelled_on"] == "2026-10-16"
    assert out["remind_at"] == "2026-12-15T12:00:00+00:00"  # 60-day expiry
    assert next(s for s in out["report"]["series"] if s["id"] == iron)["status"] == "user_cancelled"

    rep = load(client, "followup_cancelled")
    row = db.get_reminder(iron)
    assert row["phase"] == "VERIFIED_STOPPED" and row["detail"] == "No charge through Nov 15, 2026"
    assert [(n["kind"], n["series_id"]) for n in notices()] == [("verified", iron)]
    assert notes[-1][1]["covers_until"] == "2026-11-15"
    assert rep["meta"]["imports"][-1]["verified_count"] == 1
    listed = client.get("/reminders", headers=auth).json()[0]
    assert listed["group"] == "done" and listed["checked"] == {"date": "2026-11-15", "amount": None}


def test_still_charged_and_its_refund_draft(client, auth, sample_report, clock, notes):
    from app import drafts

    iron = sid(sample_report, "IronTrap Fitness")
    client.post(f"/reminders/{iron}/cancelled", headers=auth, json={"cancelled_on": "2026-10-16"})
    load(client, "followup_still_charged")
    row = db.get_reminder(iron)
    assert row["phase"] == "STILL_CHARGED" and row["detail"] == "Charged again on Nov 5, 2026"
    assert notes[-1][0] == "still_charged" and notes[-1][1]["charged_on"] == "2026-11-05"
    listed = client.get("/reminders", headers=auth).json()[0]
    assert listed["group"] == "needs_you" and listed["checked"] == {"date": "2026-11-05", "amount": 49.99}
    text = drafts.template("refund", drafts.facts(iron))
    assert text.split("\n\n")[0] == "Subject: Refund for IronTrap Fitness charge on Nov 5, 2026"
    assert "I cancelled on Oct 16, 2026, but my card was charged $49.99 on Nov 5, 2026." in text
    assert "I was also charged $49.99 twice in July" in text


def test_statement_ending_before_the_renewal_keeps_waiting(sample_report, clock, notes):
    rent = sid(sample_report, "Rent transfer")  # renews Nov 1; the statement ends Oct 15
    reminders.cancelled(rent, "2026-10-10")
    assert asyncio.run(reminders.verify_after_import()) == 0
    row = db.get_reminder(rent)
    assert row["phase"] == "AWAITING_STATEMENT"
    assert row["detail"] == "That statement ends Oct 15, 2026, before the renewal. Import a later one."
    assert [e["phase"] for e in row["events"]] == ["AWAITING_STATEMENT"]  # a detail change isn't a transition


def test_report_resyncs_watching_but_not_awaiting(sample_report, clock, notes):
    iron, tune = sid(sample_report, "IronTrap Fitness"), sid(sample_report, "TuneTide")
    reminders.create(iron, 3)
    reminders.cancelled(tune, "2026-10-16")
    with db.connect() as conn:  # both rows were set when the renewal looked different
        conn.execute("UPDATE reminders SET next_due_date = '2026-10-30'")
    asyncio.run(report.rescore())
    assert db.get_reminder(iron)["next_due_date"] == "2026-11-05"
    assert db.get_reminder(iron)["remind_at"] == "2026-11-02T09:00:00+00:00"
    assert db.get_reminder(tune)["next_due_date"] == "2026-10-30"


# ── routes ──────────────────────────────────────────────────────────────────

def test_routes(client, auth, sample_report, clock, notes):
    iron, fresh = sid(sample_report, "IronTrap Fitness"), sid(sample_report, "FreshCart")
    assert client.post("/reminders", headers=auth, json={"series_id": fresh}).status_code == 400  # no renewal
    out = client.post("/reminders", headers=auth, json={"series_id": iron}).json()
    assert out["phase"] == "WATCHING"
    r = out["reminder"]
    assert (r["merchant"], r["amount"], r["cadence"], r["group"], r["remind_on"]) == (
        "IronTrap Fitness", 49.99, "monthly", "watching", "2026-11-02")
    assert r["low_confidence"] is False and isinstance(r["days_left"], int)
    assert client.post(f"/reminders/{iron}/snooze", headers=auth, json={"days": 1}).status_code == 409  # not reminded
    assert client.post(f"/reminders/{iron}/stop", headers=auth).json()["phase"] == "STOPPED"
    assert client.post(f"/reminders/{iron}/stop", headers=auth).status_code == 409
    again = client.post("/reminders", headers=auth, json={"series_id": iron, "days_before": 5}).json()
    assert again["phase"] == "WATCHING" and [e["phase"] for e in again["reminder"]["events"]] == ["WATCHING"]

    cloud = sid(sample_report, "CloudBox Pro")
    annual = client.post("/reminders", headers=auth, json={"series_id": cloud}).json()["reminder"]
    assert annual["low_confidence"] is True and annual["next_due_date"] == "2027-01-14"
    listed = client.get("/reminders", headers=auth).json()
    assert {r["merchant"] for r in listed} == {"IronTrap Fitness", "CloudBox Pro"}
    detail = client.get(f"/series/{iron}", headers=auth).json()
    assert detail["reminder"]["phase"] == "WATCHING"


def test_notification_routes(client, auth, sample_report):
    a = db.insert_notification(1, "reminder", "A", "a")
    b = db.insert_notification(1, "verified", "B", "b")
    assert [n["id"] for n in client.get("/notifications?since_id=0", headers=auth).json()] == [a, b]
    assert [n["id"] for n in client.get(f"/notifications?since_id={a}", headers=auth).json()] == [b]
    assert client.post(f"/notifications/{a}/read", headers=auth).json() == {"ok": True}
    inbox = client.get("/notifications?all=1", headers=auth).json()
    assert [n["id"] for n in inbox] == [b, a] and inbox[1]["read_at"] and inbox[0]["read_at"] is None
    client.post("/notifications/read-all", headers=auth)
    assert all(n["read_at"] for n in client.get("/notifications?all=1", headers=auth).json())
    assert client.post("/notifications/999/read", headers=auth).status_code == 404


def test_note_rules():
    from app import notes

    facts = {"merchant": "IronTrap Fitness", "currency": "USD", "amount": 49.99, "next_due": "2026-11-05"}
    ref = json.dumps(notes._fmt(facts, "reminder")) + json.dumps(notes.template_note("reminder", facts))
    good = {"title": "IronTrap Fitness renews Nov 5", "body": "It renews Nov 5 for $49.99. Open How to cancel."}
    assert notes.acceptable(good, ref)
    assert not notes.acceptable({**good, "body": "It renews Nov 5 for $59.99."}, ref)
    assert not notes.acceptable({**good, "body": "Call 1-800-555-0199."}, ref)
    assert not notes.acceptable({**good, "body": "One. Two. Three. Four."}, ref)
    verified = notes.template_note("verified", {**facts, "monthly_equiv": 49.99, "covers_until": "2026-11-15"})
    assert verified == {"title": "IronTrap Fitness has stopped",
                        "body": "No IronTrap Fitness charge on your statement through Nov 15. You’re saving $49.99 a month."}
    still = notes.template_note("still_charged", {**facts, "cancelled_on": "2026-10-16", "charged_on": "2026-11-05",
                                                  "charged_amount": 49.99})
    assert still["body"] == "$49.99 on Nov 5, 2026, after you cancelled on Oct 16. A refund request is ready to draft."
