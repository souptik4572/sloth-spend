"""Accounts API under /api/auth (WEB-IMPL §2.3), shaped by the web designs (sign up, check your inbox, log in,
email me a sign-in link, forgot / reset password, account menu).

Answers never reveal whether an email has an account: sign-up, "resend", "forgot" and "email me a link" reply the
same either way, and only the inbox learns more. A session exists only for a verified email. Every link is
single-use and short-lived; passwords and tokens are stored hashed (accounts.py).
"""

import asyncio
import logging
import re
from contextvars import ContextVar

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .. import workspace
from ..state import runtime
from . import accounts, emails, mailer, passwords
from .config import web

router = APIRouter(prefix="/auth")
log = logging.getLogger(__name__)

COOKIE = "sloth_session"
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Set by the gate (gate.py) for every /api request that carries a live session.
current_user: ContextVar[dict | None] = ContextVar("sloth_user", default=None)
current_token: ContextVar[str | None] = ContextVar("sloth_session_token", default=None)

# (key prefix, max, window seconds). Failed logins are per email and per IP; emails per address and per IP.
LOGIN_EMAIL = ("login-email", 5, 15 * 60)
LOGIN_IP = ("login-ip", 30, 15 * 60)
MAIL_TO = ("mail-to", 3, 15 * 60)
MAIL_IP = ("mail-ip", 20, 60 * 60)
SIGNUP_IP = ("signup-ip", 10, 60 * 60)

NO_MATCH = "That email and password don’t match."
LINK_GONE = "That link has expired or was already used."


# ── request bodies ──────────────────────────────────────────────────────────

class Signup(BaseModel):
    name: str = Field(max_length=80)
    email: str = Field(max_length=254)
    password: str = Field(max_length=passwords.MAX_LENGTH)
    accept_terms: bool = False


class Login(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=passwords.MAX_LENGTH)
    remember: bool = True


class EmailOnly(BaseModel):
    email: str = Field(max_length=254)
    remember: bool = True


class Token(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class Reset(Token):
    password: str = Field(max_length=passwords.MAX_LENGTH)


class ChangePassword(BaseModel):
    current: str = Field(max_length=passwords.MAX_LENGTH)
    new: str = Field(max_length=passwords.MAX_LENGTH)


class Confirm(BaseModel):
    password: str = Field(max_length=passwords.MAX_LENGTH)


# ── helpers ─────────────────────────────────────────────────────────────────

def client_ip(request: Request) -> str:
    if web.trust_proxy and (forwarded := request.headers.get("x-forwarded-for")):
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _limited(rule: tuple[str, int, int], who: str) -> bool:
    prefix, limit, window = rule
    return await asyncio.to_thread(accounts.hits, f"{prefix}:{who}", window) >= limit


async def _count(rule: tuple[str, int, int], who: str) -> None:
    await asyncio.to_thread(accounts.hit, f"{rule[0]}:{who}")


def _email(raw: str) -> str:
    email = accounts.normalize_email(raw)
    if not EMAIL.match(email):
        raise HTTPException(422, "Enter an email address like name@example.com.")
    return email


async def _mail(request: Request, email: str, message) -> None:
    """Send unless this address had 3 emails in 15 minutes (then quietly skip: answers must not differ)."""
    if await _limited(MAIL_TO, email):
        log.info("not emailing %s again yet (rate limit)", email)
        return
    await _count(MAIL_TO, email)
    await _count(MAIL_IP, client_ip(request))
    mailer.send_later(message)


async def _mail_ip_guard(request: Request) -> None:
    if await _limited(MAIL_IP, client_ip(request)):
        raise HTTPException(429, "Too many emails from here. Wait a few minutes, then try again.")


async def _sign_in(request: Request, user: dict, remember: bool) -> JSONResponse:
    """A session cookie for a verified account, its workspace ready."""
    await asyncio.to_thread(workspace.ensure, user["id"])
    token = await asyncio.to_thread(accounts.create_session, user["id"], remember,
                                    request.headers.get("user-agent"))
    response = JSONResponse({"user": accounts.public(user)})
    set_cookie(response, token, remember)
    return response


def set_cookie(response, token: str, persistent: bool) -> None:
    response.set_cookie(COOKIE, token, max_age=int(accounts.PERSISTENT.total_seconds()) if persistent else None,
                        httponly=True, secure=web.cookie_secure, samesite="lax", path="/")


def clear_cookie(response) -> None:
    response.delete_cookie(COOKIE, path="/", httponly=True, secure=web.cookie_secure, samesite="lax")


def _require_user() -> dict:
    user = current_user.get()
    if user is None:
        raise HTTPException(401, "Log in to continue.")
    return user


def _password_problem(password: str, email: str) -> None:
    if problems := passwords.problems(password, email):
        raise HTTPException(422, "Choose a stronger password: " + "; ".join(p.lower() for p in problems) + ".")


async def _check_password(user: dict, password: str) -> None:
    if not await asyncio.to_thread(passwords.verify_password, password, user["password_hash"]):
        raise HTTPException(403, "That password isn’t right.")


# ── sign up and verify ──────────────────────────────────────────────────────

@router.post("/signup", status_code=202)
async def signup(body: Signup, request: Request) -> dict:
    """Creates an unverified account and emails a confirmation link. The same answer for a taken email."""
    name, email = " ".join(body.name.split()), _email(body.email)
    if not name:
        raise HTTPException(422, "Enter your name.")
    if not body.accept_terms:
        raise HTTPException(422, "Agree to the Terms and Privacy Policy to create an account.")
    _password_problem(body.password, email)
    ip = client_ip(request)
    if await _limited(SIGNUP_IP, ip):
        raise HTTPException(429, "Too many new accounts from here. Wait an hour, then try again.")
    await _mail_ip_guard(request)
    await _count(SIGNUP_IP, ip)

    existing = await asyncio.to_thread(accounts.user_by_email, email)
    if existing and existing["email_verified_at"]:
        await _mail(request, email, emails.account_exists(email, existing["name"]))
    elif existing:  # signed up before but never confirmed: a fresh link (their first password stands)
        token = await asyncio.to_thread(accounts.issue_token, existing["id"], "verify")
        await _mail(request, email, emails.verify(email, existing["name"], token))
    else:
        password_hash = await asyncio.to_thread(passwords.hash_password, body.password)
        try:
            user = await asyncio.to_thread(accounts.create_user, email, name, password_hash)
        except Exception as exc:  # noqa: BLE001 — two sign-ups racing for one email: same answer
            log.info("signup race for %s: %s", email, exc)
            return {"ok": True, "email": email}
        token = await asyncio.to_thread(accounts.issue_token, user["id"], "verify")
        await _mail(request, email, emails.verify(email, name, token))
    return {"ok": True, "email": email}


@router.post("/verify")
async def verify(body: Token, request: Request) -> JSONResponse:
    """The link from "Confirm your email": confirms it and signs in on this device."""
    row = await asyncio.to_thread(accounts.consume_token, body.token, "verify")
    if row is None:
        raise HTTPException(400, f"{LINK_GONE} Log in and we’ll send a new one if you still need it.")
    await asyncio.to_thread(accounts.mark_verified, row["user_id"])
    user = await asyncio.to_thread(accounts.get_user, row["user_id"])
    return await _sign_in(request, user, bool(row["remember"]))


@router.post("/verify/resend", status_code=202)
async def resend_verification(body: EmailOnly, request: Request) -> dict:
    email = _email(body.email)
    await _mail_ip_guard(request)
    user = await asyncio.to_thread(accounts.user_by_email, email)
    if user and not user["email_verified_at"]:
        token = await asyncio.to_thread(accounts.issue_token, user["id"], "verify")
        await _mail(request, email, emails.verify(email, user["name"], token))
    return {"ok": True, "email": email}


# ── log in / out ────────────────────────────────────────────────────────────

@router.post("/login")
async def login(body: Login, request: Request) -> JSONResponse:
    email, ip = accounts.normalize_email(body.email), client_ip(request)
    if await _limited(LOGIN_EMAIL, email) or await _limited(LOGIN_IP, ip):
        raise HTTPException(429, "Too many tries. Wait 15 minutes, or reset your password.")
    user = await asyncio.to_thread(accounts.user_by_email, email)
    if user is None:
        await asyncio.to_thread(passwords.burn_time, body.password)
        ok = False
    else:
        ok = await asyncio.to_thread(passwords.verify_password, body.password, user["password_hash"])
    if not ok:
        await _count(LOGIN_EMAIL, email)
        await _count(LOGIN_IP, ip)
        raise HTTPException(401, NO_MATCH)
    await asyncio.to_thread(accounts.clear_hits, f"{LOGIN_EMAIL[0]}:{email}")
    if not user["email_verified_at"]:
        token = await asyncio.to_thread(accounts.issue_token, user["id"], "verify", remember=body.remember)
        await _mail(request, email, emails.verify(email, user["name"], token))
        return JSONResponse({"detail": "Confirm your email first. We’ve sent you a new link.",
                             "code": "unverified", "email": email}, status_code=403)
    return await _sign_in(request, user, body.remember)


@router.post("/logout")
async def logout() -> JSONResponse:
    if token := current_token.get():
        await asyncio.to_thread(accounts.delete_session, token)
    response = JSONResponse({"ok": True})
    clear_cookie(response)
    return response


@router.get("/me")
async def me() -> dict:
    return {"user": accounts.public(_require_user())}


# ── email me a sign-in link ─────────────────────────────────────────────────

@router.post("/link", status_code=202)
async def request_link(body: EmailOnly, request: Request) -> dict:
    email = _email(body.email)
    await _mail_ip_guard(request)
    user = await asyncio.to_thread(accounts.user_by_email, email)
    if user:
        token = await asyncio.to_thread(accounts.issue_token, user["id"], "login", remember=body.remember)
        await _mail(request, email, emails.sign_in(email, user["name"], token))
    return {"ok": True, "email": email}


@router.post("/link/consume")
async def consume_link(body: Token, request: Request) -> JSONResponse:
    """Opening the link proves the inbox, so it also confirms an unverified email."""
    row = await asyncio.to_thread(accounts.consume_token, body.token, "login")
    if row is None:
        raise HTTPException(400, f"{LINK_GONE} Ask for a new sign-in link, or log in with your password.")
    await asyncio.to_thread(accounts.mark_verified, row["user_id"])
    user = await asyncio.to_thread(accounts.get_user, row["user_id"])
    return await _sign_in(request, user, bool(row["remember"]))


# ── forgot / reset / change password ────────────────────────────────────────

@router.post("/password/forgot", status_code=202)
async def forgot(body: EmailOnly, request: Request) -> dict:
    email = _email(body.email)
    await _mail_ip_guard(request)
    user = await asyncio.to_thread(accounts.user_by_email, email)
    if user:
        token = await asyncio.to_thread(accounts.issue_token, user["id"], "reset")
        await _mail(request, email, emails.reset(email, user["name"], token))
    return {"ok": True, "email": email}


@router.post("/password/reset/check")
async def check_reset(body: Token) -> dict:
    """The reset screen's "For asha@example.com": whose password this link changes, without using it."""
    row = await asyncio.to_thread(accounts.peek_token, body.token, "reset")
    user = row and await asyncio.to_thread(accounts.get_user, row["user_id"])
    if not user:
        raise HTTPException(400, f"{LINK_GONE} Ask for a new reset link.")
    return {"email": user["email"]}


@router.post("/password/reset")
async def reset_password(body: Reset, request: Request) -> JSONResponse:
    """Saves the new password, logs out every other device, and signs in here."""
    row = await asyncio.to_thread(accounts.peek_token, body.token, "reset")
    user = row and await asyncio.to_thread(accounts.get_user, row["user_id"])
    if not user:
        raise HTTPException(400, f"{LINK_GONE} Ask for a new reset link.")
    _password_problem(body.password, user["email"])  # checked before the link is used up
    if await asyncio.to_thread(accounts.consume_token, body.token, "reset") is None:
        raise HTTPException(400, f"{LINK_GONE} Ask for a new reset link.")
    password_hash = await asyncio.to_thread(passwords.hash_password, body.password)
    await asyncio.to_thread(accounts.set_password, user["id"], password_hash)
    await asyncio.to_thread(accounts.mark_verified, user["id"])  # the link proved the inbox
    await asyncio.to_thread(accounts.delete_sessions, user["id"])
    await asyncio.to_thread(accounts.revoke_tokens, user["id"], "login")
    mailer.send_later(emails.password_changed(user["email"], user["name"]))
    return await _sign_in(request, user, remember=False)


@router.post("/password")
async def change_password(body: ChangePassword) -> dict:
    """Settings › Password & security: needs the current password; other devices are logged out."""
    user = _require_user()
    await _check_password(user, body.current)
    _password_problem(body.new, user["email"])
    password_hash = await asyncio.to_thread(passwords.hash_password, body.new)
    await asyncio.to_thread(accounts.set_password, user["id"], password_hash)
    ended = await asyncio.to_thread(accounts.delete_sessions, user["id"], current_token.get())
    mailer.send_later(emails.password_changed(user["email"], user["name"]))
    return {"ok": True, "other_sessions_ended": ended}


@router.post("/logout-others")
async def logout_others() -> dict:
    user = _require_user()
    return {"ok": True, "ended": await asyncio.to_thread(accounts.delete_sessions, user["id"], current_token.get())}


@router.delete("/account")
async def delete_account(body: Confirm) -> JSONResponse:
    """Deletes the account and its whole workspace (statements, chats, reminders, settings). Not undoable."""
    user = _require_user()
    await _check_password(user, body.password)
    for task in (runtime.pipeline_task, runtime.normalize_task):  # the current workspace is this user's
        if task and not task.done():
            task.cancel()
    runtime.drop(user["id"])
    await asyncio.to_thread(accounts.delete_user, user["id"])
    await asyncio.to_thread(workspace.remove, user["id"])
    response = JSONResponse({"ok": True})
    clear_cookie(response)
    return response
