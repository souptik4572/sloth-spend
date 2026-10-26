"""The SlothSpend Web server (WEB-IMPL W1–W2): the shared engine's routes under /api behind sign-in, the accounts
API under /api/auth, and the built web app (web/dist) for every other path.

Not mounted on the web: /shutdown (desktop process control) and /setup/ollama/pull (the operator installs models).
"""

import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from .. import llm, telemetry, workspace
from ..api import admin, chat, health, imports, notifications, reminders, reports, series
from ..api import settings as settings_api
from ..config import settings
from ..reminders import run_scheduler
from ..tabular import tabular
from . import accounts, auth
from .config import web
from .gate import Gate

log = logging.getLogger("slothspend.web")

ENGINE_ROUTERS = (health.router, imports.router, reports.router, series.router, settings_api.router, admin.router,
                  chat.router, reminders.router, notifications.router)

NOT_BUILT = """<!doctype html><meta charset="utf-8"><title>SlothSpend</title>
<p style="font-family:system-ui;margin:48px">The web app isn't built yet. Run <code>npm run web:build</code>, or use
<code>npm run web:dev</code> and open the Vite address.</p>"""


@asynccontextmanager
async def lifespan(_app: FastAPI):
    telemetry.init()
    accounts.init()
    workspace.root().mkdir(parents=True, exist_ok=True)
    threading.Thread(target=tabular.warm_up, daemon=True).start()  # never block startup on torch
    scheduler = asyncio.create_task(run_scheduler(workspace.all_ids))  # every workspace's reminders
    status = await llm.status()
    log.info("SlothSpend Web on http://%s:%s (public %s) · Gemma via %s: %s %s · mail: %s", web.host, web.port,
             web.public_url, status["provider"], status["status"], status["model"],
             "SMTP" if web.smtp_url else f"outbox ({settings.data_dir / 'outbox'})")
    yield
    scheduler.cancel()


def _spa(dist: Path, request_path: str):
    """A built file if one matches, else index.html (the web app routes /login, /reset… itself)."""
    if not (dist / "index.html").is_file():
        return HTMLResponse(NOT_BUILT, status_code=503)
    candidate = (dist / request_path).resolve()
    if request_path and candidate.is_file() and candidate.is_relative_to(dist.resolve()):
        immutable = request_path.startswith("assets/")  # Vite fingerprints these
        return FileResponse(candidate, headers={"cache-control": "public, max-age=31536000, immutable"
                                                if immutable else "no-cache"})
    return FileResponse(dist / "index.html", headers={"cache-control": "no-cache"})


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    api = APIRouter(prefix="/api")
    for router in ENGINE_ROUTERS:
        api.include_router(router)
    api.include_router(auth.router)

    @api.api_route("/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    async def unknown_api(rest: str) -> None:
        raise HTTPException(404, "Not found.")

    app.include_router(api)

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)  # HEAD: uptime checks
    async def spa(path: str):
        return _spa(web.dist, path)

    app.add_middleware(Gate)
    return app


app = create_app()


class _QuietPolls(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/api/health" not in record.getMessage()


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("uvicorn.access").addFilter(_QuietPolls())
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if web.public_url.startswith("https://") and not web.smtp_url:
        log.warning("SLOTH_SMTP_URL is not set: sign-up emails go to the local outbox, not to people")
    uvicorn.run(app, host=web.host, port=web.port, log_config=None, proxy_headers=web.trust_proxy,
                forwarded_allow_ips="*" if web.trust_proxy else None)
