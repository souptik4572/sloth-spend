import asyncio
import logging
import os
import sys
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db, telemetry
from .api import admin, health
from .config import settings
from .reminders import run_scheduler
from .security import require_token
from .state import runtime
from .tabular import tabular

log = logging.getLogger("slothspend")


class _QuietPolls(logging.Filter):
    """The renderer polls /health every second on Boot; keep those out of the log."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return "/health" not in msg and '"OPTIONS ' not in msg


def _stdin_watchdog() -> None:
    """Electron keeps our stdin open. EOF means the parent quit or crashed."""
    try:
        sys.stdin.read()
    finally:
        os._exit(0)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    telemetry.init()
    db.init()
    if not os.environ.get("SLOTH_NO_WATCHDOG"):
        threading.Thread(target=_stdin_watchdog, daemon=True).start()
    threading.Thread(target=tabular.warm_up, daemon=True).start()  # never block startup on torch
    runtime.scheduler_task = asyncio.create_task(run_scheduler())  # renewal reminders (§7.10)
    log.info("engine ready on 127.0.0.1:%s", settings.port)
    yield
    runtime.scheduler_task.cancel()


app = FastAPI(lifespan=lifespan, dependencies=[Depends(require_token)])
app.add_middleware(
    CORSMiddleware,
    # Dev renderer (electron-vite picks a localhost port) and the packaged file:// origin ("null").
    # The per-launch token is the real guard.
    allow_origin_regex=r"^(http://localhost:\d+|null)$",
    allow_methods=["*"],
    allow_headers=["X-Sloth-Token", "Content-Type"],
)
app.include_router(health.router)
app.include_router(admin.router)


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("uvicorn.access").addFilter(_QuietPolls())
    logging.getLogger("httpx").setLevel(logging.WARNING)  # Ollama status checks run on every poll
    # log_config=None: avoid uvicorn's colour formatter touching sys.stderr in frozen builds
    uvicorn.run(app, host="127.0.0.1", port=settings.port, log_config=None)


if __name__ == "__main__":
    run()
