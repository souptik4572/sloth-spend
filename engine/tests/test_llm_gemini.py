"""Gemma through the Gemini API (WEB-IMPL W0): translation, streaming, retries, status, and the whole app.

A local pytest-httpserver plays the Gemini REST API, so the real provider code runs end to end and no test
needs a key or the network. The end-to-end test also refuses every non-loopback socket: in Gemini mode the
app talks to the configured Gemini base URL and nothing else.
"""

import asyncio
import ipaddress
import json
import re
import socket

import pytest
from conftest import FIXTURES, sse
from werkzeug import Response

from app import llm, notes
from app.config import settings

KEY = "test-gemini-key"
MODELS = ("gemma-4-26b-a4b-it", "gemma-4-31b-it")
NAMES = json.loads((FIXTURES / "sample_merchant_map.json").read_text())
CALLS: list[dict] = []  # every generate request: {"path", "body", "stream"}


def _set(**values) -> dict:
    """Settings is a frozen dataclass: set fields in place and return what they were."""
    previous = {k: getattr(settings, k) for k in values}
    for k, v in values.items():
        object.__setattr__(settings, k, v)
    return previous


# ── a local Gemini API stand-in ─────────────────────────────────────────────

def _user_texts(body: dict) -> list[str]:
    return [p["text"] for c in body["contents"] if c["role"] == "user" for p in c["parts"] if "text" in p]


def _reply_parts(body: dict) -> list[dict]:
    """What Gemma would say, by request shape."""
    texts = _user_texts(body)
    last = texts[-1] if texts else ""
    answered = any("functionResponse" in p for c in body["contents"] for p in c["parts"])
    if "Lines:\n" in last:  # merchant names, wrapped in a fence like a chatty model would
        items = []
        for i, k in re.findall(r'^(\d+): (".*")$', last, re.M):
            key = json.loads(k)
            known = NAMES.get(key)
            items.append({"i": int(i), "m": known["merchant"] if known else key.title()[:30],
                          "c": known["category"] if known else "Other",
                          "s": known["subscription_like"] if known else False})
        return [{"text": "```json\n" + json.dumps({"items": items}) + "\n```"}]
    if "Notification to rephrase" in last:
        return [{"text": json.dumps({"title": "A reminder from SlothSpend",
                                     "body": "Open How to cancel in SlothSpend, or tap Keep it."})}]
    draft = re.search(r"^Subject:.*", last, re.M | re.S)
    if draft and "[Your name]" in last:  # a draft rewrite: hand the email back unchanged
        return [{"text": draft.group(0)}]
    if body.get("tools") and not answered:
        return [{"functionCall": {"name": "get_report_overview", "args": {}}}]
    return [{"text": "Weighing the numbers first.", "thought": True},
            {"text": "Here is what I found. Nothing has been cancelled."}]


def _response(parts: list[dict]) -> dict:
    return {"candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 7, "totalTokenCount": 18}}


def _authorised(request) -> bool:
    return request.headers.get("x-goog-api-key") == KEY


def _generate(request) -> Response:
    if not _authorised(request):
        return Response(json.dumps({"error": {"code": 403, "message": "API key not valid"}}), status=403)
    body = request.get_json()
    CALLS.append({"path": request.path, "body": body, "stream": False})
    return Response(json.dumps(_response(_reply_parts(body))), mimetype="application/json")


def _stream(request) -> Response:
    if not _authorised(request):
        return Response(json.dumps({"error": {"code": 403, "message": "API key not valid"}}), status=403)
    body = request.get_json()
    CALLS.append({"path": request.path, "body": body, "stream": True})
    parts = _reply_parts(body)
    events = [{"candidates": [{"content": {"role": "model", "parts": [p]}}]} for p in parts]
    events[-1] = _response([parts[-1]])  # the last event carries usage, like the real API
    text = "".join(f"data: {json.dumps(e)}\r\n\r\n" for e in events)
    return Response(text, mimetype="text/event-stream")


@pytest.fixture()
def gemini(httpserver, monkeypatch):
    """Gemini mode against the stub: both models exist; a fresh provider (no cached status)."""
    httpserver.expect_request(re.compile(r"^/v1beta/models/[^/:]+$"), method="GET").respond_with_handler(
        lambda r: Response(json.dumps({"name": f"models{r.path.rsplit('/models', 1)[1]}"}),
                           mimetype="application/json") if _authorised(r) else Response("{}", status=403))
    httpserver.expect_request(re.compile(r".*:generateContent$"), method="POST").respond_with_handler(_generate)
    httpserver.expect_request(re.compile(r".*:streamGenerateContent$"), method="POST").respond_with_handler(_stream)
    CALLS.clear()
    monkeypatch.setitem(llm.PROVIDERS, "gemini", llm.GeminiProvider())
    previous = _set(llm_provider="gemini", gemini_api_key=KEY, gemini_models=MODELS,
                    gemini_base_url=httpserver.url_for("").rstrip("/"))
    yield httpserver
    _set(**previous)


def _is_local(address) -> bool:
    if not isinstance(address, tuple):
        return True
    try:
        return address[0] in ("localhost", "") or ipaddress.ip_address(address[0].split("%")[0]).is_loopback
    except ValueError:
        return False


@pytest.fixture()
def loopback_only(monkeypatch):
    attempts = []
    real = socket.socket.connect

    def connect(self, address):
        if not _is_local(address):
            attempts.append(address)
            raise ConnectionRefusedError(f"egress blocked: {address}")
        return real(self, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    yield
    assert attempts == [], f"outbound connections attempted: {attempts}"


# ── translation ─────────────────────────────────────────────────────────────

def test_messages_become_gemini_contents():
    system, contents = llm.gemini_contents([
        {"role": "system", "content": "You are Sloth."},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "system", "content": "Facts already looked up: …"},  # mid-conversation system message
        {"role": "user", "content": "How am I doing?"},
        {"role": "assistant", "content": "",
         "tool_calls": [{"function": {"name": "get_merchant", "arguments": {"merchant": "IronTrap"}}},
                        {"function": {"name": "get_report_overview", "arguments": {}}}]},
        {"role": "tool", "tool_name": "get_merchant", "content": '{"merchant": "IronTrap Fitness"}'},
        {"role": "tool", "tool_name": "get_report_overview", "content": "[1, 2]"},
    ])
    assert system == "You are Sloth.\n\nFacts already looked up: …"
    assert [c["role"] for c in contents] == ["user", "model", "user", "model", "user"]
    assert contents[3]["parts"] == [{"functionCall": {"name": "get_merchant", "args": {"merchant": "IronTrap"}}},
                                    {"functionCall": {"name": "get_report_overview", "args": {}}}]
    assert contents[4]["parts"] == [  # both answers in one user turn; non-objects are wrapped
        {"functionResponse": {"name": "get_merchant", "response": {"merchant": "IronTrap Fitness"}}},
        {"functionResponse": {"name": "get_report_overview", "response": {"result": [1, 2]}}}]


def test_tool_schemas_use_the_gemini_subset():
    from app import tools

    [tool] = llm.gemini_tools(tools.SCHEMAS)
    decls = {d["name"]: d for d in tool["functionDeclarations"]}
    assert set(decls) == set(tools.NAMES)
    assert "parameters" not in decls["get_report_overview"]  # no-argument functions omit parameters
    merchant = decls["get_merchant"]["parameters"]
    assert merchant["type"] == "OBJECT" and merchant["properties"]["merchant"]["type"] == "STRING"
    assert merchant["required"] == ["merchant"]
    fc = decls["forecast_spend"]["parameters"]["properties"]
    assert fc["exclude_merchants"] == {"type": "ARRAY", "items": {"type": "STRING"},
                                       "description": fc["exclude_merchants"]["description"]}
    assert fc["scope"]["enum"] == ["subscriptions", "all"]


@pytest.mark.parametrize(("text", "expected"), [
    ('{"a": 1}', '{"a": 1}'),
    ('```json\n{"a": 1}\n```', '{"a": 1}'),
    ('Sure! Here it is: {"a": {"b": 2}} Hope that helps.', '{"a": {"b": 2}}'),
    ("no json here", "no json here"),
])
def test_extract_json(text, expected):
    assert llm.extract_json(text) == expected


def test_retry_delay_reads_retry_info():
    body = json.dumps({"error": {"code": 429, "details": [
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "7s"}]}}).encode()
    assert llm.retry_delay(body, 0) == 7.0
    assert llm.retry_delay(json.dumps({"error": {"details": [
        {"@type": "x.RetryInfo", "retryDelay": "90s"}]}}).encode(), 0) == llm.MAX_WAIT
    assert llm.retry_delay(b"not json", 1) == llm.BACKOFF[1]


# ── status ──────────────────────────────────────────────────────────────────

def test_status_without_a_key(monkeypatch):
    monkeypatch.setitem(llm.PROVIDERS, "gemini", llm.GeminiProvider())
    previous = _set(llm_provider="gemini", gemini_api_key="", gemini_models=MODELS)
    try:
        out = asyncio.run(llm.status())
    finally:
        _set(**previous)
    assert out == {"provider": "gemini", "status": "missing_key", "version": None, "model": MODELS[0],
                   "model_present": False, "available_models": [], "loopback": False}


def test_status_ready_is_cached_and_honours_the_chosen_model(gemini):
    out = asyncio.run(llm.status())
    assert out["status"] == "ready" and out["model"] == MODELS[0] and out["available_models"] == list(MODELS)
    checks = len(gemini.log)
    asyncio.run(llm.status())
    assert len(gemini.log) == checks  # a healthy check is reused for a minute: polling never burns quota
    assert asyncio.run(llm.PROVIDERS["gemini"].status(MODELS[1]))["model"] == MODELS[1]
    assert asyncio.run(llm.PROVIDERS["gemini"].status("gemma4:e4b"))["model"] == MODELS[0]  # unknown → default


@pytest.mark.parametrize(("code", "state"), [(403, "bad_key"), (404, "missing_model"), (429, "rate_limited"),
                                             (500, "unreachable")])
def test_status_maps_api_errors(httpserver, monkeypatch, code, state):
    httpserver.expect_request(re.compile(r"^/v1beta/models/.*")).respond_with_data("{}", status=code)
    monkeypatch.setitem(llm.PROVIDERS, "gemini", llm.GeminiProvider())
    previous = _set(llm_provider="gemini", gemini_api_key=KEY, gemini_models=MODELS,
                    gemini_base_url=httpserver.url_for("").rstrip("/"))
    try:
        out = asyncio.run(llm.status())
    finally:
        _set(**previous)
    assert out["status"] == state and out["model_present"] is False


def test_status_when_the_api_is_unreachable(monkeypatch):
    from conftest import _closed_port

    monkeypatch.setitem(llm.PROVIDERS, "gemini", llm.GeminiProvider())
    previous = _set(llm_provider="gemini", gemini_api_key=KEY, gemini_models=MODELS,
                    gemini_base_url=f"http://127.0.0.1:{_closed_port()}")
    try:
        assert asyncio.run(llm.status())["status"] == "unreachable"
    finally:
        _set(**previous)


# ── calls ───────────────────────────────────────────────────────────────────

def test_complete_with_a_schema_asks_for_json(gemini):
    text = asyncio.run(llm.provider().complete(
        MODELS[0], [{"role": "user", "content": 'Lines:\n0: "NETFLIX.COM"'}], schema={"type": "object"}))
    assert json.loads(text)["items"][0]["i"] == 0  # the fence was stripped
    body = CALLS[-1]["body"]
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert "matches this JSON schema" in body["contents"][-1]["parts"][-1]["text"]
    assert CALLS[-1]["path"].endswith(f"/models/{MODELS[0]}:generateContent")


def test_json_mode_is_dropped_when_the_model_refuses_it(httpserver, gemini):
    def picky(request):
        body = request.get_json()
        CALLS.append({"path": request.path, "body": body, "stream": False})
        if "responseMimeType" in body["generationConfig"]:
            return Response(json.dumps({"error": {"code": 400, "message": "JSON mode is not enabled"}}), status=400)
        return Response(json.dumps(_response([{"text": '{"title": "t", "body": "b"}'}])),
                        mimetype="application/json")

    httpserver.clear_all_handlers()
    httpserver.expect_request(re.compile(r".*:generateContent$")).respond_with_handler(picky)
    ask = [{"role": "user", "content": "Notification to rephrase"}]
    provider = llm.provider()
    assert json.loads(asyncio.run(provider.complete(MODELS[0], ask, schema={"type": "object"}))) == \
        {"title": "t", "body": "b"}
    assert len(CALLS) == 2 and MODELS[0] in provider._no_json_mode
    CALLS.clear()
    asyncio.run(provider.complete(MODELS[0], ask, schema={"type": "object"}))
    assert len(CALLS) == 1  # remembered: no second refusal


def test_rate_limits_are_waited_out(httpserver, gemini):
    replies = iter([
        Response(json.dumps({"error": {"code": 429, "message": "slow down", "details": [
            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "0.01s"}]}}), status=429),
        Response(json.dumps(_response([{"text": "ok"}])), mimetype="application/json"),
    ])
    httpserver.clear_all_handlers()
    httpserver.expect_request(re.compile(r".*:generateContent$")).respond_with_handler(lambda r: next(replies))
    assert asyncio.run(llm.provider().complete(MODELS[0], [{"role": "user", "content": "hi"}])) == "ok"


def test_rate_limits_give_up_after_three_tries(httpserver, gemini, monkeypatch):
    monkeypatch.setattr(llm, "BACKOFF", (0.0, 0.0, 0.0))
    httpserver.clear_all_handlers()
    httpserver.expect_request(re.compile(r".*:generateContent$")).respond_with_data(
        json.dumps({"error": {"code": 429, "message": "quota"}}), status=429)
    with pytest.raises(llm.GeminiError) as err:
        asyncio.run(llm.provider().complete(MODELS[0], [{"role": "user", "content": "hi"}]))
    assert err.value.status == 429 and len(httpserver.log) == llm.MAX_TRIES
    assert llm.status_of(err.value) == "rate_limited"


def test_stream_drops_thoughts_and_reports_tool_calls_and_usage(gemini):
    from app import tools

    async def collect(messages, **kw):
        return [c async for c in llm.provider().stream(MODELS[0], messages, **kw)]

    first = asyncio.run(collect([{"role": "user", "content": "How am I doing?"}], tools=tools.SCHEMAS))
    assert first[0].tool_calls == [llm.ToolCall("get_report_overview", {})]
    assert first[-1].done and (first[-1].input_tokens, first[-1].output_tokens) == (11, 7)
    assert CALLS[-1]["body"]["tools"][0]["functionDeclarations"]
    assert CALLS[-1]["path"].endswith(":streamGenerateContent")

    answer = asyncio.run(collect([{"role": "user", "content": "hello"}]))
    assert "".join(c.text for c in answer) == "Here is what I found. Nothing has been cancelled."  # no thought


def test_stream_retries_a_rate_limit_before_the_first_token(httpserver, gemini):
    replies = iter([Response(json.dumps({"error": {"code": 429, "details": [
        {"@type": "x.RetryInfo", "retryDelay": "0.01s"}]}}), status=429)])
    httpserver.clear_all_handlers()
    httpserver.expect_request(re.compile(r".*:streamGenerateContent$")).respond_with_handler(
        lambda r: next(replies, None) or _stream(r))

    async def collect():
        return [c async for c in llm.provider().stream(MODELS[0], [{"role": "user", "content": "hello"}])]

    assert "".join(c.text for c in asyncio.run(collect())).startswith("Here is what I found")


# ── the whole app in Gemini mode ────────────────────────────────────────────

def test_health_and_setup_in_gemini_mode(client, auth, gemini):
    health = client.get("/health", headers=auth).json()["ollama"]
    assert health["provider"] == "gemini" and health["status"] == "ready" and health["model"] == MODELS[0]
    assert client.post("/setup/ollama/pull", headers=auth, json={}).status_code == 404  # nothing to download
    assert client.put("/settings", headers=auth, json={"chat_model": MODELS[1]}).status_code == 200
    assert client.get("/health", headers=auth).json()["ollama"]["model"] == MODELS[1]


def test_chat_without_a_key_says_so_plainly(client, sample_report, monkeypatch):
    monkeypatch.setitem(llm.PROVIDERS, "gemini", llm.GeminiProvider())
    previous = _set(llm_provider="gemini", gemini_api_key="")
    try:
        events = sse(client, "/chat", {"conversation_id": "nokey", "message": "hello"})
    finally:
        _set(**previous)
    assert events == [("error", {"message": llm.UNAVAILABLE["gemini"]["missing_key"]})]
    assert "Ollama" not in events[0][1]["message"]


def test_every_gemma_feature_runs_on_the_gemini_api(client, auth, gemini, loopback_only):
    # 1. The audit: Gemma names merchants (JSON in a fence) and rewrites the summary.
    events = sse(client, "/demo/load-sample", {"file": "main"})
    assert events[-1][0] == "done", events[-1]
    rep = events[-1][1]["report"]
    stages = {d["stage"]: d for e, d in events if e == "stage" and d.get("source")}
    assert stages["normalize"]["source"] == "gemma" and stages["summary"]["source"] == "gemma"
    assert rep["meta"]["summary_source"] == "gemma"
    iron = next(s for s in rep["series"] if s["merchant"] == "IronTrap Fitness")  # names came from "Gemma"

    # 2. Ask Sloth: a tool round over function calling, the thought never shown.
    chat = sse(client, "/chat", {"conversation_id": "gemini", "message": "How am I doing?"})
    assert ("tool_start", {"name": "get_report_overview", "args": {}}) in chat and chat[-1][0] == "done"
    answer = "".join(d["text"] for e, d in chat if e == "token")
    assert answer == "Here is what I found. Nothing has been cancelled." and "Weighing" not in answer
    second = [c for c in CALLS if c["stream"] and c["body"].get("tools")][-1]["body"]
    assert "Everything runs on this computer" not in second["systemInstruction"]["parts"][0]["text"]
    assert second["contents"][-2]["parts"][0]["functionCall"]["name"] == "get_report_overview"
    assert second["contents"][-1]["parts"][0]["functionResponse"]["name"] == "get_report_overview"

    # 3. Every draft kind, streamed and fact-checked.
    bill = next(s for s in rep["series"] if s["kind"] == "bill")
    for sid, kind in ((iron["id"], "cancel_request"), (iron["id"], "refund"), (bill["id"], "negotiate")):
        done = sse(client, f"/series/{sid}/draft", {"kind": kind})[-1]
        assert done[0] == "done" and done[1]["source"] == "gemma" and done[1]["text"].startswith("Subject:")

    # 4. A reminder note, structured JSON.
    note = asyncio.run(notes.gemma_note("reminder", {"merchant": "IronTrap Fitness", "amount": 49.99,
                                                       "next_due": "2026-11-05", "currency": "USD"}))
    assert note == {"title": "A reminder from SlothSpend", "body": "Open How to cancel in SlothSpend, or tap Keep it."}

    assert all(c["path"].startswith("/v1beta/models/gemma-4-") for c in CALLS)
