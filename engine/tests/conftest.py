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


def _closed_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# Tests never talk to a real Ollama: point the client at a port nothing listens on.
os.environ["OLLAMA_HOST"] = f"http://127.0.0.1:{_closed_port()}"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth() -> dict:
    return {"X-Sloth-Token": TOKEN}
