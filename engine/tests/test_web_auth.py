"""Accounts on the web (WEB-IMPL W2): sign up, confirm, log in, sign-in links, forgot / reset / change password,
delete account — and the gate: CSRF, sessions, rate limits, upload and Gemma budgets, security headers."""

from datetime import timedelta

import pytest
from conftest import PASSWORD, browser, link_token, mail_to, set_frozen, sign_up

from app import workspace
from app.web import accounts, mailer
from app.web.config import web as web_config

EMAIL = "asha@example.com"


def _signup(web, **overrides):
    body = {"name": "Asha Rao", "email": EMAIL, "password": PASSWORD, "accept_terms": True, **overrides}
    return web.post("/api/auth/signup", json=body)


# ── sign up and confirm ─────────────────────────────────────────────────────

def test_sign_up_then_confirm_signs_in(web):
    r = _signup(web, email="  Asha@Example.COM ")
    assert r.status_code == 202 and r.json() == {"ok": True, "email": EMAIL}
    assert "sloth_session" not in web.cookies  # no session before the email is confirmed
    msg = mail_to(EMAIL, "Confirm your email")
    assert "/verify/confirm?token=" in msg.get_body(("plain",)).get_content() and msg.get_body(("html",))

    assert web.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()["code"] == "unverified"
    r = web.post("/api/auth/verify", json={"token": link_token(msg)})
    assert r.status_code == 200 and r.json()["user"]["name"] == "Asha Rao" and r.json()["user"]["email"] == EMAIL
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Max-Age=2592000" in cookie
    assert web.get("/api/auth/me").json()["user"]["email"] == EMAIL
    assert "password_hash" not in web.get("/api/auth/me").json()["user"]
    assert workspace.folder(r.json()["user"]["id"]).joinpath("slothspend.db").is_file()  # workspace ready

    again = web.post("/api/auth/verify", json={"token": link_token(msg)})
    assert again.status_code == 400 and "already used" in again.json()["detail"]  # single use


@pytest.mark.parametrize(("overrides", "message"), [
    ({"name": "   "}, "Enter your name."),
    ({"accept_terms": False}, "Agree to the Terms"),
    ({"email": "not-an-email"}, "Enter an email address"),
    ({"password": "short1!"}, "at least 12 characters"),
    ({"password": "slowandsteadyforever"}, "a number or symbol"),
    ({"password": "asha-likes-sloths-2026"}, "doesn’t contain your email"),
])
def test_sign_up_rules(web, overrides, message):
    r = _signup(web, **overrides)
    assert r.status_code == 422 and message in r.json()["detail"], r.json()
    assert accounts.user_by_email(EMAIL) is None


def test_a_taken_email_gets_the_same_answer_and_an_email(web):
    sign_up(web)
    first = accounts.user_by_email(EMAIL)
    r = _signup(browser(web.app), name="Someone Else", password="another-pass-99")
    assert r.status_code == 202 and r.json() == {"ok": True, "email": EMAIL}
    assert mail_to(EMAIL, "You already have a SlothSpend account") is not None
    assert accounts.user_by_email(EMAIL) == first  # nothing changed


def test_signing_up_again_before_confirming_resends_the_link(web):
    _signup(web)
    first = link_token(mail_to(EMAIL, "Confirm"))
    mailer.SENT.clear()
    _signup(web)
    second = link_token(mail_to(EMAIL, "Confirm"))
    assert first != second
    assert web.post("/api/auth/verify", json={"token": first}).status_code == 200  # both links work once


def test_resend_verification_answers_the_same_for_anyone(web):
    _signup(web)
    mailer.SENT.clear()
    assert web.post("/api/auth/verify/resend", json={"email": EMAIL}).status_code == 202
    assert mail_to(EMAIL, "Confirm") is not None
    r = web.post("/api/auth/verify/resend", json={"email": "nobody@example.com"})
    assert r.status_code == 202 and r.json() == {"ok": True, "email": "nobody@example.com"}
    assert mail_to("nobody@example.com", timeout=0.3) is None


# ── log in / out ────────────────────────────────────────────────────────────

def test_log_in_keep_me_logged_in_or_not(web):
    sign_up(web)
    web.post("/api/auth/logout")
    other = browser(web.app)
    r = other.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD, "remember": False})
    assert r.status_code == 200 and "Max-Age" not in r.headers["set-cookie"]  # ends with the browser
    assert other.get("/api/auth/me").status_code == 200
    r = web.post("/api/auth/login", json={"email": EMAIL.upper(), "password": PASSWORD, "remember": True})
    assert r.status_code == 200 and "Max-Age=2592000" in r.headers["set-cookie"]


def test_wrong_password_and_unknown_email_look_the_same(web):
    sign_up(web)
    wrong = web.post("/api/auth/login", json={"email": EMAIL, "password": "nope-nope-123"})
    unknown = web.post("/api/auth/login", json={"email": "who@example.com", "password": "nope-nope-123"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "That email and password don’t match."}


def test_five_failures_lock_the_email_for_a_while(web):
    sign_up(web)
    for _ in range(5):
        assert web.post("/api/auth/login", json={"email": EMAIL, "password": "wrong-pass-123"}).status_code == 401
    r = web.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 429 and "reset your password" in r.json()["detail"]


def test_log_out_ends_the_session(web):
    session = sign_up(web)["session"]
    assert web.post("/api/auth/logout").status_code == 200
    assert web.get("/api/auth/me").status_code == 401
    assert browser(web.app, session).get("/api/auth/me").status_code == 401  # revoked server-side, not just here


def test_sessions_expire(web, monkeypatch):
    session = sign_up(web)["session"]
    later = accounts.now() + accounts.PERSISTENT + timedelta(minutes=1)
    monkeypatch.setattr(accounts, "now", lambda: later)
    assert browser(web.app, session).get("/api/auth/me").status_code == 401


# ── email me a sign-in link ─────────────────────────────────────────────────

def test_sign_in_link(web):
    sign_up(web)
    web.post("/api/auth/logout")
    mailer.SENT.clear()
    r = web.post("/api/auth/link", json={"email": EMAIL, "remember": False})
    assert r.status_code == 202
    token = link_token(mail_to(EMAIL, "sign-in link"))
    r = web.post("/api/auth/link/consume", json={"token": token})
    assert r.status_code == 200 and "Max-Age" not in r.headers["set-cookie"]  # remembered the checkbox
    assert web.get("/api/auth/me").status_code == 200
    assert web.post("/api/auth/link/consume", json={"token": token}).status_code == 400  # once only

    assert web.post("/api/auth/link", json={"email": "nobody@example.com"}).json() == \
        {"ok": True, "email": "nobody@example.com"}
    assert mail_to("nobody@example.com", timeout=0.3) is None


def test_sign_in_links_expire_after_15_minutes(web, monkeypatch):
    sign_up(web)
    web.post("/api/auth/link", json={"email": EMAIL})
    token = link_token(mail_to(EMAIL, "sign-in link"))
    later = accounts.now() + timedelta(minutes=16)
    monkeypatch.setattr(accounts, "now", lambda: later)
    assert web.post("/api/auth/link/consume", json={"token": token}).status_code == 400


def test_a_sign_in_link_also_confirms_the_email(web):
    _signup(web)
    web.post("/api/auth/link", json={"email": EMAIL})
    r = web.post("/api/auth/link/consume", json={"token": link_token(mail_to(EMAIL, "sign-in link"))})
    assert r.status_code == 200 and accounts.user_by_email(EMAIL)["email_verified_at"]


# ── forgot / reset / change password ────────────────────────────────────────

def test_forgot_and_reset_password(web):
    old_session = sign_up(web)["session"]
    stranger = browser(web.app)
    mailer.SENT.clear()
    assert stranger.post("/api/auth/password/forgot", json={"email": "nobody@example.com"}).status_code == 202
    assert stranger.post("/api/auth/password/forgot", json={"email": EMAIL}).status_code == 202
    assert mail_to("nobody@example.com", timeout=0.3) is None
    token = link_token(mail_to(EMAIL, "new SlothSpend password"))

    assert stranger.post("/api/auth/password/reset/check", json={"token": token}).json() == {"email": EMAIL}
    weak = stranger.post("/api/auth/password/reset", json={"token": token, "password": "short"})
    assert weak.status_code == 422  # the link survives a rejected password
    r = stranger.post("/api/auth/password/reset", json={"token": token, "password": "a-new-slow-pace-77"})
    assert r.status_code == 200 and stranger.get("/api/auth/me").status_code == 200  # signed in here
    assert browser(web.app, old_session).get("/api/auth/me").status_code == 401  # other devices logged out
    assert stranger.post("/api/auth/password/reset", json={"token": token,
                                                         "password": "yet-another-one-88"}).status_code == 400
    assert mail_to(EMAIL, "password was changed") is not None

    fresh = browser(web.app)
    assert fresh.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 401
    assert fresh.post("/api/auth/login", json={"email": EMAIL, "password": "a-new-slow-pace-77"}).status_code == 200


def test_a_new_reset_link_cancels_the_old_one_and_links_expire(web, monkeypatch):
    sign_up(web)
    web.post("/api/auth/password/forgot", json={"email": EMAIL})
    first = link_token(mail_to(EMAIL, "new SlothSpend password"))
    mailer.SENT.clear()
    web.post("/api/auth/password/forgot", json={"email": EMAIL})
    second = link_token(mail_to(EMAIL, "new SlothSpend password"))
    assert web.post("/api/auth/password/reset/check", json={"token": first}).status_code == 400
    later = accounts.now() + timedelta(hours=1, minutes=1)
    monkeypatch.setattr(accounts, "now", lambda: later)
    assert web.post("/api/auth/password/reset/check", json={"token": second}).status_code == 400


def test_at_most_three_emails_per_address_per_15_minutes(web):
    sign_up(web)
    mailer.SENT.clear()
    for _ in range(5):
        assert web.post("/api/auth/password/forgot", json={"email": EMAIL}).status_code == 202  # same answer
    mail_to(EMAIL, "new SlothSpend password")
    import time
    time.sleep(0.3)
    resets = [m for m in mailer.SENT if "new SlothSpend password" in str(m["Subject"])]
    assert len(resets) == 2  # sign-up's confirmation used one of the three


def test_change_password_logs_out_other_devices(web):
    session = sign_up(web)["session"]
    elsewhere = browser(web.app)
    elsewhere.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    r = web.post("/api/auth/password", json={"current": "wrong-one-123", "new": "a-new-slow-pace-77"})
    assert r.status_code == 403
    r = web.post("/api/auth/password", json={"current": PASSWORD, "new": "a-new-slow-pace-77"})
    assert r.json() == {"ok": True, "other_sessions_ended": 1}
    assert browser(web.app, session).get("/api/auth/me").status_code == 200  # this device stays in
    assert elsewhere.get("/api/auth/me").status_code == 401


def test_delete_account_removes_the_workspace(web, canned_gemma):
    user = sign_up(web)["user"]
    from conftest import web_sse
    assert web_sse(web, "/api/demo/load-sample", {"file": "main"})[-1][0] == "done"
    folder = workspace.folder(user["id"])
    assert folder.is_dir()
    assert web.request("DELETE", "/api/auth/account", json={"password": "wrong-one-123"}).status_code == 403
    assert web.request("DELETE", "/api/auth/account", json={"password": PASSWORD}).status_code == 200
    assert not folder.exists() and accounts.user_by_email(EMAIL) is None
    assert web.get("/api/report").status_code == 401
    assert browser(web.app).post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 401


# ── the gate ────────────────────────────────────────────────────────────────

def test_engine_routes_need_a_session(web):
    for method, path in (("GET", "/api/report"), ("GET", "/api/health"), ("GET", "/api/settings"),
                         ("GET", "/api/reminders"), ("POST", "/api/chat")):
        assert web.request(method, path).status_code == 401, path
    sign_up(web)
    assert web.get("/api/health").json()["engine"] == "ok"
    assert web.post("/api/shutdown").status_code == 404  # desktop-only routes aren't mounted
    assert web.post("/api/setup/ollama/pull", json={}).status_code == 404
    assert web.get("/api/nope").status_code == 404


def test_csrf_needs_the_header_and_our_origin(web):
    sign_up(web)
    bare = {"X-Sloth-CSRF": ""}
    assert web.put("/api/settings", json={"currency": "INR"}, headers=bare).status_code == 403
    assert web.put("/api/settings", json={"currency": "INR"},
                   headers={"Origin": "https://evil.example"}).status_code == 403
    ok = web.put("/api/settings", json={"currency": "INR"}, headers={"Origin": web_config.public_origin})
    assert ok.status_code == 200 and ok.json()["currency"] == "INR"
    assert web.post("/api/auth/login", json={}, headers=bare).status_code == 403  # auth routes too


def test_upload_and_gemma_budgets(web, monkeypatch):
    sign_up(web)
    big = web.post("/api/import", headers={"Content-Length": str(11 * 1024 * 1024)}, content=b"x" * 10)
    assert big.status_code == 413
    previous = set_frozen(web_config, llm_per_minute=2)
    try:
        codes = [web.post("/api/chat", json={"conversation_id": "c", "message": "hi"}).status_code for _ in range(3)]
    finally:
        set_frozen(web_config, **previous)
    assert codes == [200, 200, 429]


def test_security_headers_and_the_web_app(web, tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>SlothSpend</title>")
    (tmp_path / "assets" / "app-123.js").write_text("console.log(1)")
    previous = set_frozen(web_config, dist=tmp_path)
    try:
        page = web.get("/reset?token=abc")  # any app route serves index.html
        asset = web.get("/assets/app-123.js")
        escape = web.get("/../engine/app/config.py")
    finally:
        set_frozen(web_config, **previous)
    assert page.status_code == 200 and "SlothSpend" in page.text
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    assert page.headers["referrer-policy"] == "no-referrer" and page.headers["x-frame-options"] == "DENY"
    assert "immutable" in asset.headers["cache-control"]
    assert "SlothSpend" in escape.text  # never a file outside dist
    api = web.get("/api/auth/me")
    assert api.headers["cache-control"] == "no-store" and "content-security-policy" not in api.headers
