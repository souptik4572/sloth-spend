import json
import os
import socket
import sys
import tempfile
from pathlib import Path

import pytest

# Configure the engine before app.config is imported anywhere.
TOKEN = "test-token"
os.environ["SLOTH_TOKEN"] = TOKEN
os.environ["SLOTH_DATA_DIR"] = tempfile.mkdtemp(prefix="sloth-test-")
os.environ["SLOTH_NO_WATCHDOG"] = "1"
os.environ["SLOTH_TELEMETRY"] = "0"
os.environ["SLOTH_DISABLE_TABPFN"] = "1"  # heuristic scorer: no model downloads in tests (IMPL M4.13)
os.environ.pop("TABPFN_TOKEN", None)


def _closed_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# Tests never talk to a real Ollama: point the client at a port nothing listens on.
os.environ["OLLAMA_HOST"] = f"http://127.0.0.1:{_closed_port()}"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


ENGINE = Path(__file__).resolve().parent.parent
FIXTURES = ENGINE / "tests" / "fixtures"
DATA = ENGINE / "app" / "data"


@pytest.fixture(autouse=True)
def fresh_db():
    """Every test starts with an empty database and no pending uploads."""
    from app import db
    from app.state import runtime

    for suffix in ("", "-wal", "-shm"):
        Path(f"{db.DB_PATH}{suffix}").unlink(missing_ok=True)
    db.init()
    runtime.pending.clear()
    yield


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth() -> dict:
    return {"X-Sloth-Token": TOKEN}


@pytest.fixture()
def canned_gemma(monkeypatch):
    """Stand-in for Gemma: names every sample description from fixtures/sample_merchant_map.json."""
    from app import normalize, report

    mapping = json.loads((FIXTURES / "sample_merchant_map.json").read_text())

    async def fake_batch(client, model, keys):
        return {k: {**mapping[k], "source": "llm"} if k in mapping else normalize.rule_fallback(k) for k in keys}

    async def fake_model():
        return "gemma-fixture"

    monkeypatch.setattr(normalize, "normalize_batch", fake_batch)
    monkeypatch.setattr(report, "gemma_model", fake_model)
    return mapping


def sse(client, path: str, body: dict | None = None) -> list[tuple[str, dict]]:
    """POST and collect a server-sent event stream as [(event, data), …]."""
    events, name = [], None
    with client.stream("POST", path, headers={"X-Sloth-Token": TOKEN}, json=body or {}) as r:
        assert r.status_code == 200, r.read()
        for line in r.iter_lines():
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                events.append((name, json.loads(line[5:])))
    return events


@pytest.fixture()
def sample_report(client, canned_gemma):
    """The bundled 12-month sample, audited (heuristic scorer, canned Gemma names)."""
    events = sse(client, "/demo/load-sample", {"file": "main"})
    assert events[-1][0] == "done", events[-1]
    return events[-1][1]["report"]
