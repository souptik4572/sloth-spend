"""Workspaces (WEB-IMPL W1): two people use SlothSpend Web at once and nothing crosses over — statements, reports,
settings, chats, reminders, notifications, the read-only SQL tool, the scheduler and "Delete all my data"."""

import asyncio
import json
import threading
from datetime import datetime, timedelta, timezone

import pytest
from conftest import FIXTURES, browser, sign_up, web_sse

from app import db, reminders, tools, workspace
from app.state import runtime


@pytest.fixture()
def two(web):
    """Asha and Ben, each signed in on their own browser."""
    asha = sign_up(web, "asha@example.com", "Asha Rao")
    ben = sign_up(browser(web.app), "ben@example.com", "Ben Ito")
    return {"asha": browser(web.app, asha["session"]), "ben": browser(web.app, ben["session"]),
            "ids": (asha["user"]["id"], ben["user"]["id"])}


def _upload_hdfc(client) -> list[tuple[str, dict]]:
    up = client.post("/api/import", files={"file": ("hdfc.csv", (FIXTURES / "hdfc_style.csv").read_bytes())})
    assert up.status_code == 200, up.text
    return web_sse(client, f"/api/import/{up.json()['import_id']}/confirm")


def test_two_audits_at_once_stay_apart(two, canned_gemma):
    results = {}

    def run(who, fn):
        results[who] = fn(two[who])

    threads = [threading.Thread(target=run, args=("asha", lambda c: web_sse(c, "/api/demo/load-sample",
                                                                            {"file": "main"}))),
               threading.Thread(target=run, args=("ben", _upload_hdfc))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)
    assert results["asha"][-1][0] == "done" and results["ben"][-1][0] == "done", (results["asha"][-1],
                                                                                 results["ben"][-1])

    asha, ben = two["asha"].get("/api/report").json(), two["ben"].get("/api/report").json()
    assert asha["meta"]["currency"] == "USD" and ben["meta"]["currency"] == "INR"
    assert [i["file_name"] for i in asha["meta"]["imports"]] == ["sample_bank_12m.csv"]
    assert [i["file_name"] for i in ben["meta"]["imports"]] == ["hdfc.csv"]
    asha_merchants = {s["merchant"] for s in asha["series"]}
    assert "IronTrap Fitness" in asha_merchants and "IronTrap Fitness" not in {s["merchant"] for s in ben["series"]}

    # A series id from one workspace means nothing in the other.
    iron = next(s for s in asha["series"] if s["merchant"] == "IronTrap Fitness")
    other = two["ben"].get(f"/api/series/{iron['id']}")
    assert other.status_code == 404 or other.json()["series"]["merchant"] != "IronTrap Fitness"


def test_settings_chats_reminders_and_notifications_are_per_person(two, canned_gemma):
    asha, ben = two["asha"], two["ben"]
    assert web_sse(asha, "/api/demo/load-sample", {"file": "main"})[-1][0] == "done"
    assert asha.put("/api/settings", json={"currency": "GBP", "days_before": 5}).status_code == 200
    assert ben.get("/api/settings").json()["currency"] == "USD" and ben.get("/api/settings").json()["days_before"] == 3

    iron = next(s for s in asha.get("/api/report").json()["series"] if s["merchant"] == "IronTrap Fitness")
    assert asha.post("/api/reminders", json={"series_id": iron["id"]}).status_code == 200
    assert [r["merchant"] for r in asha.get("/api/reminders").json()] == ["IronTrap Fitness"]
    assert ben.get("/api/reminders").json() == []
    assert ben.post("/api/reminders", json={"series_id": iron["id"]}).status_code in (400, 404)  # no such series

    asha_id, ben_id = two["ids"]
    with workspace.use(asha_id):
        db.save_chat("c1", "user", "Why was IronTrap flagged?")
        db.insert_notification(iron["id"], "reminder", "IronTrap renews soon", "Keep it, or cancel it yourself?")
    assert [m["content"] for m in asha.get("/api/chat/c1").json()["messages"]] == ["Why was IronTrap flagged?"]
    assert ben.get("/api/chat/c1").json()["messages"] == []
    assert len(asha.get("/api/notifications?all=1").json()) == 1 and ben.get("/api/notifications?all=1").json() == []


def test_the_sql_tool_only_sees_its_own_workspace(two, canned_gemma):
    assert web_sse(two["asha"], "/api/demo/load-sample", {"file": "main"})[-1][0] == "done"
    asha_id, ben_id = two["ids"]

    def count(ws: str) -> int:
        with workspace.use(ws):
            out = json.loads(asyncio.run(tools.execute("run_readonly_sql",
                                                       {"query": "SELECT COUNT(*) FROM transactions"})))
        return out["rows"][0][0]

    assert count(asha_id) == 410 and count(ben_id) == 0  # the sample's 412 rows minus 2 unreadable dates
    with workspace.use(ben_id):  # no path trick reaches another file: ATTACH isn't a SELECT, and it's read-only
        out = json.loads(asyncio.run(tools.execute("run_readonly_sql", {
            "query": f"ATTACH DATABASE '{workspace.folder(asha_id) / 'slothspend.db'}' AS other"})))
    assert "error" in out


def test_the_scheduler_ticks_every_workspace(two, canned_gemma, monkeypatch):
    for who in ("asha", "ben"):
        assert web_sse(two[who], "/api/demo/load-sample", {"file": "main"})[-1][0] == "done"
    ids = two["ids"]
    for ws in ids:
        with workspace.use(ws):
            iron = next(s for s in db.list_series() if s["merchant"] == "IronTrap Fitness")
            db.set_settings({"demo_compress_seconds": "30"})
            assert reminders.create(iron["id"])["phase"] == "WATCHING"

    clock = {"now": datetime.now(timezone.utc) + timedelta(seconds=31)}
    monkeypatch.setattr(reminders, "now_utc", lambda: clock["now"])
    monkeypatch.setattr(reminders, "gemma_note", _no_gemma)
    monkeypatch.setattr(reminders, "GEMMA_BACKOFF", [0])  # straight to the template note

    async def one_round():
        task = asyncio.create_task(reminders.run_scheduler(workspace.all_ids))
        for _ in range(200):
            await asyncio.sleep(0.02)
            if all(_phase(ws) == "REMINDED" for ws in ids):
                break
        task.cancel()

    asyncio.run(one_round())
    assert [_phase(ws) for ws in ids] == ["REMINDED", "REMINDED"]
    for ws in ids:
        with workspace.use(ws):
            assert len(db.notifications_since(0)) == 1  # each person got exactly their own reminder


async def _no_gemma(kind, facts):
    raise RuntimeError("no Gemma in this test")


def _phase(ws: str) -> str:
    with workspace.use(ws):
        iron = next(s for s in db.list_series() if s["merchant"] == "IronTrap Fitness")
        return db.get_reminder(iron["id"])["phase"]


def test_delete_all_my_data_only_touches_mine(two, canned_gemma):
    for who in ("asha", "ben"):
        assert web_sse(two[who], "/api/demo/load-sample", {"file": "main"})[-1][0] == "done"
    assert two["asha"].delete("/api/data").json() == {"ok": True}
    assert two["asha"].get("/api/report").status_code == 404
    assert two["ben"].get("/api/report").status_code == 200


def test_runtime_state_is_per_workspace(two):
    asha_id, ben_id = two["ids"]
    with workspace.use(asha_id):
        runtime.pending[1] = b"asha's upload"
    with workspace.use(ben_id):
        assert 1 not in runtime.pending
        assert runtime.pipeline_lock is not None
    with workspace.use(asha_id):
        assert runtime.pending.pop(1) == b"asha's upload"
    assert 1 not in runtime.pending  # the desktop slot is separate too


def test_workspace_ids_are_never_paths():
    for bad in ("../accounts", "a/b", "", "ABCDEF" * 6, "0" * 31):
        with pytest.raises(ValueError):
            workspace.folder(bad)


def test_reminder_notes_say_browser_on_the_web(two, monkeypatch):
    """The note Gemma rephrases is a browser notification on the web, a desktop one on the desktop."""
    from app import llm, notes

    prompts = []

    class Recorder:
        name = "ollama"

        async def complete(self, model, messages, **kw):
            prompts.append(messages[-1]["content"])
            return json.dumps({"title": "IronTrap renews soon", "body": "Keep it, or open How to cancel."})

    async def gemma():
        return "gemma4:e4b"

    monkeypatch.setattr(llm, "provider", lambda: Recorder())
    monkeypatch.setattr("app.report.gemma_model", gemma)
    facts = {"merchant": "IronTrap Fitness", "amount": 49.99, "next_due": "2026-11-05", "currency": "USD"}
    with workspace.use(two["ids"][0]):
        asyncio.run(notes.gemma_note("reminder", facts))
    asyncio.run(notes.gemma_note("reminder", facts))  # no workspace: the desktop
    assert "Rephrase this browser notification" in prompts[0]
    assert "Rephrase this desktop notification" in prompts[1]
