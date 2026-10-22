"""No data leaves the computer (spec §13.1, IMPL M8.5).

Every outbound socket connection to a non-loopback address is refused and recorded. Ollama is a local stub
(pytest-httpserver on 127.0.0.1) so the real Gemma code paths run: merchant names, summary, drafts, chat with a
tool call, and reminder notes. Telemetry is off and TabPFN is the heuristic (conftest), so nothing downloads.
"""

import asyncio
import ipaddress
import json
import re
import socket
import time
from datetime import datetime, timedelta, timezone

import pytest
from conftest import FIXTURES, sse
from werkzeug import Response

from app import db, reminders, tools
from app.config import settings

ATTEMPTS: list = []


def _is_local(address) -> bool:
    if not isinstance(address, tuple):  # AF_UNIX path
        return True
    host = address[0]
    if host in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        return False  # an unresolved name: that would be a lookup and a connection out


@pytest.fixture(autouse=True)
def no_egress(monkeypatch):
    ATTEMPTS.clear()
    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def connect(self, address):
        if not _is_local(address):
            ATTEMPTS.append(address)
            raise ConnectionRefusedError(f"egress blocked: {address}")
        return real_connect(self, address)

    def connect_ex(self, address):
        if not _is_local(address):
            ATTEMPTS.append(address)
            return 111
        return real_connect_ex(self, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    yield
    assert ATTEMPTS == [], f"outbound connections attempted: {ATTEMPTS}"


# ── a local Ollama stand-in ─────────────────────────────────────────────────

CHAT_CALLS: list[dict] = []
NAMES = json.loads((FIXTURES / "sample_merchant_map.json").read_text())


def _reply(body: dict) -> dict:
    """What Gemma would say, by request shape."""
    fmt = body.get("format")
    prompt = body["messages"][-1]["content"]
    if isinstance(fmt, dict) and "items" in fmt.get("properties", {}):  # merchant names
        lines = re.findall(r'^(\d+): (".*")$', prompt, re.M)
        items = []
        for i, k in lines:  # the same names the canned-Gemma tests use; unknown keys get a plain title
            known = NAMES.get(json.loads(k))
            items.append({"i": int(i), "m": known["merchant"] if known else json.loads(k).title()[:30],
                          "c": known["category"] if known else "Other",
                          "s": known["subscription_like"] if known else False})
        return {"role": "assistant", "content": json.dumps({"items": items})}
    if isinstance(fmt, dict):  # a reminder note
        return {"role": "assistant",
                "content": json.dumps({"title": "A reminder from SlothSpend",
                                       "body": "Open How to cancel in SlothSpend, or tap Keep it."})}
    if body.get("tools") and not any(m.get("role") == "tool" for m in body["messages"]):
        return {"role": "assistant", "content": "",
                "tool_calls": [{"function": {"name": "get_report_overview", "arguments": {}}}]}
    return {"role": "assistant", "content": "Here is what I found. Nothing has been cancelled."}


def _chat(request) -> Response:
    body = request.get_json()
    CHAT_CALLS.append(body)
    message = _reply(body)
    base = {"model": body["model"], "created_at": "2026-10-16T12:00:00Z"}
    final = {**base, "message": {"role": "assistant", "content": ""}, "done": True, "done_reason": "stop",
             "prompt_eval_count": 10, "eval_count": 5}
    if body.get("stream"):
        lines = [{**base, "message": message, "done": False}, final]
        return Response("\n".join(json.dumps(x) for x in lines) + "\n", mimetype="application/x-ndjson")
    return Response(json.dumps({**final, "message": message}), mimetype="application/json")


@pytest.fixture()
def ollama_stub(httpserver):
    httpserver.expect_request("/api/version").respond_with_json({"version": "0.20.4"})
    httpserver.expect_request("/api/tags").respond_with_json(
        {"models": [{"name": m, "model": m} for m in ("gemma4:e2b", "gemma4:e4b", "llama3:8b")]})
    httpserver.expect_request("/api/chat", method="POST").respond_with_handler(_chat)
    CHAT_CALLS.clear()
    previous = settings.ollama_host
    object.__setattr__(settings, "ollama_host", httpserver.url_for("").rstrip("/"))  # frozen dataclass
    yield httpserver
    object.__setattr__(settings, "ollama_host", previous)


# ── the whole app, offline ──────────────────────────────────────────────────

def test_everything_stays_on_this_computer(client, auth, ollama_stub, monkeypatch):
    # 1. Import and audit the sample, with Gemma naming merchants and writing the summary.
    events = sse(client, "/demo/load-sample", {"file": "main"})
    assert events[-1][0] == "done", events[-1]
    rep = events[-1][1]["report"]
    assert any(c.get("format") for c in CHAT_CALLS)  # the Gemma code path really ran
    series = {s["merchant"]: s for s in rep["series"]}
    iron = series["IronTrap Fitness"]

    # 2. Every Ask Sloth tool.
    calls = {
        "get_report_overview": {}, "get_merchant": {"merchant": iron["merchant"]},
        "find_duplicate_charges": {}, "spend_by_category": {},
        "forecast_spend": {"exclude_merchants": [iron["merchant"]]}, "score_merchant": {"merchant": iron["merchant"]},
        "run_readonly_sql": {"query": "SELECT COUNT(*) FROM transactions"},
        "set_renewal_reminder": {"merchant": iron["merchant"], "days_before": 3},
    }
    assert set(calls) == set(tools.NAMES)
    for name, args in calls.items():
        out = json.loads(asyncio.run(tools.execute(name, args)))
        assert "error" not in out or name == "score_merchant", (name, out)

    # 3. A chat turn with a tool round, and every draft kind.
    chat = sse(client, "/chat", {"conversation_id": "egress", "message": "How am I doing?"})
    assert [e for e, _ in chat][-1] == "done" and ("tool_start", {"name": "get_report_overview", "args": {}}) in chat
    bill = next(s for s in rep["series"] if s["kind"] == "bill")
    for sid, kind in ((iron["id"], "cancel_request"), (iron["id"], "refund"), (bill["id"], "negotiate")):
        done = sse(client, f"/series/{sid}/draft", {"kind": kind})[-1]
        assert done[0] == "done" and done[1]["text"].startswith("Subject:")

    # 4. A full reminder cycle with demo compression and a fake clock, Gemma writing the notes.
    clock = {"now": datetime(2026, 10, 16, 12, tzinfo=timezone.utc)}
    monkeypatch.setattr(reminders, "now_utc", lambda: clock["now"])
    db.set_settings({"demo_compress_seconds": "30"})
    reminders.stop(iron["id"])
    assert reminders.create(iron["id"])["phase"] == "WATCHING"
    clock["now"] += timedelta(seconds=31)
    asyncio.run(reminders.tick())
    assert db.get_reminder(iron["id"])["phase"] == "REMINDED"
    assert db.notifications_since(0)[-1]["title"] == "A reminder from SlothSpend"
    client.post(f"/reminders/{iron['id']}/cancelled", headers=auth, json={"cancelled_on": "2026-10-16"})
    sse(client, "/demo/load-sample", {"file": "followup_cancelled"})
    for _ in range(200):  # the statement-check note is written in the background
        if any(n["kind"] == "verified" for n in db.notifications_since(0)):
            break
        time.sleep(0.01)
    assert db.get_reminder(iron["id"])["phase"] == "VERIFIED_STOPPED"
    assert any(n["kind"] == "verified" for n in db.notifications_since(0))

    # 5. Delete all local data.
    assert client.delete("/data", headers=auth).json() == {"ok": True}
    assert client.get("/report", headers=auth).status_code == 404
    assert db.notifications_since(0) == [] and db.list_reminders() == []
    assert db.get_setting_int("demo_compress_seconds") == 30  # settings stay


def test_the_guard_itself_catches_a_connection_out():
    with pytest.raises(ConnectionRefusedError):
        socket.create_connection(("93.184.216.34", 443), timeout=1)
    assert ATTEMPTS == [("93.184.216.34", 443)]
    ATTEMPTS.clear()  # expected here; the fixture's final check must still pass


def test_settings_choose_the_chat_model(client, auth, sample_report, ollama_stub):
    """Settings › Chat model: a chosen Gemma answers the chat; Automatic goes back to the best installed."""
    def model_used() -> str:
        CHAT_CALLS.clear()
        events = sse(client, "/chat", {"conversation_id": "models", "message": "Hello"})
        assert events[-1][0] == "done", events[-1]
        return CHAT_CALLS[-1]["model"]

    assert model_used() == "gemma4:e4b"  # Automatic: e4b ranks above e2b; llama isn't a Gemma
    assert client.put("/settings", headers=auth, json={"chat_model": "gemma4:e2b"}).status_code == 200
    assert client.get("/health", headers=auth).json()["ollama"]["model"] == "gemma4:e2b"
    assert model_used() == "gemma4:e2b"
    client.put("/settings", headers=auth, json={"chat_model": None})
    assert model_used() == "gemma4:e4b"
