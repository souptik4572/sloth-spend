"""The gate in front of every request (WEB-IMPL §2.2–2.3). A plain ASGI middleware, so what it sets holds for the
whole request, server-sent event streams included.

For /api/*:
1. CSRF: a state-changing request needs `X-Sloth-CSRF: 1` (a cross-site form can't send it) and, when the browser
   names an Origin, our own origin. The session cookie is SameSite=Lax on top.
2. Session: the cookie's account becomes `auth.current_user`, and its workspace becomes `workspace.current`, so the
   engine's routes read and write only that person's database.
3. Everything outside /api/auth/* needs a session (401 otherwise).
4. Limits: statement uploads ≤ 10 MB; Gemma-backed routes ≤ SLOTH_USER_LLM_PER_MIN calls per account per minute.

Every response gets security headers; pages also get a strict Content-Security-Policy.
"""

import asyncio
import json
import re
from http.cookies import SimpleCookie

from .. import workspace
from . import accounts, auth
from .config import web

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
UPLOAD = re.compile(r"^/api/import$")
GEMMA_ROUTES = re.compile(r"^/api/(chat|demo/load-sample|import/\d+/confirm|series/\d+/draft)$")

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; "
       "object-src 'none'")
HEADERS = [(b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"no-referrer"),
           (b"x-frame-options", b"DENY"), (b"cross-origin-opener-policy", b"same-origin"),
           (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()")]


def _headers(scope) -> dict[str, str]:
    return {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}


def _session_token(headers: dict[str, str]) -> str | None:
    raw = headers.get("cookie")
    if not raw:
        return None
    try:
        morsel = SimpleCookie(raw).get(auth.COOKIE)
    except Exception:  # noqa: BLE001 — a malformed Cookie header is just "no session"
        return None
    return morsel.value if morsel else None


async def _reply(send, status: int, detail: str, extra: dict | None = None) -> None:
    body = json.dumps({"detail": detail, **(extra or {})}).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
                            (b"cache-control", b"no-store")]})
    await send({"type": "http.response.body", "body": body})


class Gate:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path, method = scope["path"], scope["method"]
        is_api = path == "/api" or path.startswith("/api/")
        send = self._with_headers(send, is_api)
        if not is_api:
            return await self.app(scope, receive, send)

        headers = _headers(scope)
        if method not in SAFE_METHODS:
            origin = headers.get("origin")
            if headers.get("x-sloth-csrf") != "1" or (origin and origin != web.public_origin):
                return await _reply(send, 403, "Blocked a cross-site request.")

        user, token = None, _session_token(headers)
        if token:
            user = await asyncio.to_thread(accounts.session_user, token)
        if user is None and not path.startswith("/api/auth/"):
            return await _reply(send, 401, "Log in to continue.")

        if user is not None and method == "POST":
            if UPLOAD.match(path) and int(headers.get("content-length") or 0) > web.max_upload_bytes + 64 * 1024:
                return await _reply(send, 413, "That file is larger than 10 MB. Export a CSV statement instead.")
            if GEMMA_ROUTES.match(path):
                key = f"gemma:{user['id']}"
                if await asyncio.to_thread(accounts.hits, key, 60) >= web.llm_per_minute:
                    return await _reply(send, 429, "Slow and steady — give Sloth a minute, then try again.")
                await asyncio.to_thread(accounts.hit, key)

        user_token = auth.current_user.set(user)
        session_token = auth.current_token.set(token if user else None)
        ws_token = None
        if user is not None:
            await asyncio.to_thread(workspace.ensure, user["id"])
            ws_token = workspace.current.set(user["id"])
        try:
            await self.app(scope, receive, send)
        finally:
            if ws_token is not None:
                workspace.current.reset(ws_token)
            auth.current_token.reset(session_token)
            auth.current_user.reset(user_token)

    @staticmethod
    def _with_headers(send, is_api: bool):
        extra = list(HEADERS)
        if web.cookie_secure:
            extra.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
        extra.append((b"cache-control", b"no-store") if is_api else (b"content-security-policy", CSP.encode()))

        async def wrapped(message) -> None:
            if message["type"] == "http.response.start":
                names = {k.lower() for k, _ in message.get("headers", [])}
                message = {**message, "headers": [*message.get("headers", []),
                                                  *(h for h in extra if h[0] not in names)]}
            await send(message)

        return wrapped
