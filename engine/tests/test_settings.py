"""GET/PUT /settings (IMPL M3.6) and the chat-model preference it feeds (IMPL §2 #20)."""

from app.config import settings


def test_defaults(client, auth):
    assert client.get("/settings", headers=auth).json() == {
        "currency": "USD", "chat_model": None, "days_before": 3, "demo_compress_seconds": 0}


def test_partial_update_persists(client, auth):
    r = client.put("/settings", headers=auth, json={"currency": "INR", "days_before": 5})
    assert r.status_code == 200
    assert r.json()["currency"] == "INR" and r.json()["days_before"] == 5
    assert client.get("/settings", headers=auth).json()["demo_compress_seconds"] == 0  # untouched


def test_validation(client, auth):
    assert client.put("/settings", headers=auth, json={"days_before": 0}).status_code == 422
    assert client.put("/settings", headers=auth, json={"days_before": 15}).status_code == 422
    assert client.put("/settings", headers=auth, json={"demo_compress_seconds": 3}).status_code == 422
    assert client.put("/settings", headers=auth, json={"currency": "JPY"}).status_code == 422
    assert client.put("/settings", headers=auth, json={"demo_compress_seconds": 30}).status_code == 200


def test_chat_model_choice_and_automatic(client, auth):
    assert client.put("/settings", headers=auth, json={"chat_model": "gemma3:4b"}).json()["chat_model"] == "gemma3:4b"
    assert settings.preferred_model == "gemma3:4b"  # feeds the Gemma model picker
    assert client.put("/settings", headers=auth, json={"chat_model": "  "}).json()["chat_model"] is None
    assert settings.preferred_model is None  # back to "best installed Gemma"


def test_requires_the_token(client):
    assert client.get("/settings").status_code == 401
    assert client.put("/settings", json={"days_before": 4}).status_code == 401
