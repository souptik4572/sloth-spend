import asyncio

from app import ollama_setup
from app.config import DOWNLOAD_MODEL


def test_every_route_requires_the_token(client):
    assert client.get("/health").status_code == 401
    assert client.get("/health", headers={"X-Sloth-Token": "wrong"}).status_code == 401
    assert client.post("/shutdown").status_code == 401


def test_health_shape_with_ollama_unreachable(client, auth):
    r = client.get("/health", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["engine"] == "ok"
    assert body["ollama"]["status"] == "unreachable"
    assert body["ollama"]["model"] == DOWNLOAD_MODEL
    assert body["ollama"]["available_models"] == []
    assert body["ollama"]["loopback"] is True
    assert body["tabpfn"]["status"] in {"cold", "unavailable"}
    assert body["tabpfn"]["upgrade"] == {"state": "none", "error": None}
    assert body["telemetry"] is False


def test_cors_preflight_needs_no_token(client):
    r = client.options(
        "/health",
        headers={
            "Origin": "null",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Sloth-Token",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "null"


def test_cors_rejects_other_origins(client, auth):
    r = client.get("/health", headers={**auth, "Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_version_parsing_and_minimum():
    assert ollama_setup.parse_version("0.40.6") == (0, 40, 6)
    assert ollama_setup.parse_version("0.20") == (0, 20, 0)
    assert ollama_setup.parse_version("v0.20.1-rc2") == (0, 20, 1)
    assert ollama_setup.parse_version("garbage") is None
    assert ollama_setup.parse_version("0.19.9") < ollama_setup.MIN_VERSION


def test_loopback_detection():
    assert ollama_setup.is_loopback("http://127.0.0.1:11434")
    assert ollama_setup.is_loopback("localhost:11434")
    assert ollama_setup.is_loopback("http://[::1]:11434")
    assert not ollama_setup.is_loopback("http://192.168.1.20:11434")


def test_pick_model_uses_any_installed_gemma():
    assert ollama_setup.pick_model(["gemma4:latest", "llama3:8b"]) == "gemma4:latest"
    assert ollama_setup.pick_model(["gemma3:4b"]) == "gemma3:4b"
    assert ollama_setup.pick_model(["llama3:8b", "qwen3:4b"]) is None
    assert ollama_setup.pick_model([]) is None


def test_pick_model_prefers_newest_generation_then_tag():
    installed = ["gemma3:12b", "gemma4:e2b", "gemma4:latest", "gemma2:2b"]
    assert ollama_setup.pick_model(installed) == "gemma4:latest"
    assert ollama_setup.pick_model([*installed, "gemma4:e4b"]) == "gemma4:e4b"
    assert ollama_setup.pick_model(["gemma3:4b", "gemma:7b"]) == "gemma3:4b"


def test_pick_model_honours_an_installed_explicit_choice():
    installed = ["gemma4:latest", "gemma3:4b"]
    assert ollama_setup.pick_model(installed, "gemma3:4b") == "gemma3:4b"
    # A choice that isn't installed falls back to the best installed Gemma.
    assert ollama_setup.pick_model(installed, "gemma4:e2b") == "gemma4:latest"


def _fake_ollama(httpserver, version: str, names: list[str]) -> str:
    httpserver.expect_request("/api/version").respond_with_json({"version": version})
    httpserver.expect_request("/api/tags").respond_with_json(
        {"models": [{"name": n, "model": n} for n in names]}
    )
    return httpserver.url_for("/").rstrip("/")


def test_status_ready_with_whatever_gemma_is_installed(httpserver):
    host = _fake_ollama(httpserver, "0.40.6", ["llama3:8b", "gemma4:latest", "gemma3:4b"])
    out = asyncio.run(ollama_setup.status(host, None))
    assert out["status"] == "ready"
    assert out["model"] == "gemma4:latest"
    assert out["model_present"] is True
    assert out["available_models"] == ["gemma4:latest", "gemma3:4b"]


def test_status_missing_model_offers_the_download(httpserver):
    host = _fake_ollama(httpserver, "0.40.6", ["llama3:8b"])
    out = asyncio.run(ollama_setup.status(host, None))
    assert out["status"] == "missing_model"
    assert out["model"] == DOWNLOAD_MODEL
    assert out["available_models"] == []


def test_status_outdated_ollama(httpserver):
    host = _fake_ollama(httpserver, "0.19.2", ["gemma4:latest"])
    assert asyncio.run(ollama_setup.status(host, None))["status"] == "outdated"
