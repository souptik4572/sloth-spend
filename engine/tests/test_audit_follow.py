"""Following a running audit (WEB-IMPL W4): a reloaded or second tab replays the audit so far, then follows it live;
the queue note when the server's audit slots are full; the provider stored with the summary."""

import asyncio
import json
import sqlite3
import threading
import time

from conftest import DATA, browser, sign_up, sse, web_sse

from app import db, ingest, report, workspace
from app.state import runtime


def _hold_detect(monkeypatch) -> threading.Event:
    """Pause every audit at its detect stage until the returned event is set (detect runs in a worker thread)."""
    gate = threading.Event()
    original = report.detect

    def slow_detect(ctx):
        gate.wait(10)
        return original(ctx)

    monkeypatch.setattr(report, "detect", slow_detect)
    return gate


def _wait_running(client, headers=None, timeout=10.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = client.get("/audit", headers=headers).json() if headers else client.get("/api/audit").json()
        if status["running"]:
            return status
        time.sleep(0.02)
    raise AssertionError("the audit never started")


def test_a_reloaded_tab_follows_the_running_audit(client, auth, canned_gemma, monkeypatch):
    gate = _hold_detect(monkeypatch)
    results: dict = {}
    first = threading.Thread(target=lambda: results.update(first=sse(client, "/demo/load-sample", {"file": "main"})))
    first.start()

    status = _wait_running(client, auth)
    assert status["file"] == "sample_bank_12m.csv"
    time.sleep(0.2)  # parse and normalize have reported by now
    second = threading.Thread(target=lambda: results.update(second=sse(client, "/audit/follow")))
    second.start()
    time.sleep(0.2)
    gate.set()
    first.join(30)
    second.join(30)

    assert results["first"][-1][0] == "done"
    assert results["second"] == results["first"]  # the whole audit: replayed from parse, then live to done
    assert client.get("/audit", headers=auth).json()["running"] is False
    assert client.post("/audit/follow", headers=auth).status_code == 404


def test_the_audit_says_when_it_waits_for_a_free_slot(canned_gemma, monkeypatch):
    raw = (DATA / "sample_bank_12m.csv").read_bytes()
    parsed = ingest.parse(raw, "sample_bank_12m.csv", "USD")
    import_id = db.create_pending_import("sample_bank_12m.csv", parsed.sha256, parsed.mapping, parsed.currency,
                                         parsed.header_row)
    runtime.pending[import_id] = raw

    async def scenario() -> list[tuple[str, str]]:
        runtime.pipeline_lock = asyncio.Lock()
        full = asyncio.Semaphore(1)
        await full.acquire()  # another person's audit holds the only slot
        monkeypatch.setattr(report, "audit_slots", lambda: full)
        run = await report.start_pipeline(import_id, {}, file_name="sample_bank_12m.csv")
        await asyncio.sleep(0.05)
        waiting = [json.loads(e["data"]) for e in run.events]
        full.release()
        events = [(e["event"], e["data"]) async for e in run.follow()]
        return waiting, events

    waiting, events = asyncio.run(scenario())
    assert waiting == [{"stage": "parse", "done": 0, "total": 1, "note": report.WAITING_NOTE}]
    assert events[-1][0] == "done"


def test_the_summary_records_who_served_gemma(client, auth, canned_gemma, monkeypatch):
    from app import llm_summary

    async def gemma_wrote(facts, model):
        return llm_summary.template(facts), "gemma"

    monkeypatch.setattr(llm_summary, "write", gemma_wrote)
    rep = sse(client, "/demo/load-sample", {"file": "main"})[-1][1]["report"]
    assert rep["meta"]["summary_source"] == "gemma" and rep["meta"]["summary_provider"] == "ollama"
    rescored = client.post("/report/rescore", headers=auth).json()["report"]
    assert rescored["meta"]["summary_source"] == "template" and rescored["meta"]["summary_provider"] is None


def test_an_existing_database_gains_the_provider_column():
    path = db.DB_PATH
    with sqlite3.connect(path) as conn:  # back to a v2 database: report_meta without summary_provider
        conn.execute("DROP TABLE report_meta")
        conn.execute("CREATE TABLE report_meta (id INTEGER PRIMARY KEY CHECK (id = 1), generated_at TEXT, "
                     "summary_source TEXT)")
        conn.execute("PRAGMA user_version = 2")
    db.init()
    with sqlite3.connect(path) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(report_meta)")}
        assert "summary_provider" in cols and conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION


def test_audit_status_is_per_person_on_the_web(web, canned_gemma, monkeypatch):
    asha = browser(web.app, sign_up(web, "asha@example.com", "Asha Rao")["session"])
    ben = browser(web.app, sign_up(browser(web.app), "ben@example.com", "Ben Ito")["session"])
    gate = _hold_detect(monkeypatch)
    done: dict = {}
    t = threading.Thread(target=lambda: done.update(events=web_sse(asha, "/api/demo/load-sample", {"file": "main"})))
    t.start()
    assert _wait_running(asha)["file"] == "sample_bank_12m.csv"
    assert ben.get("/api/audit").json()["running"] is False
    assert ben.post("/api/audit/follow").status_code == 404  # nobody follows someone else's audit
    gate.set()
    t.join(30)
    assert done["events"][-1][0] == "done"
    assert workspace.all_ids()  # both workspaces exist; only Asha's has a report
    assert ben.get("/api/report").status_code == 404 and asha.get("/api/report").status_code == 200
