"""First-run setup (IMPL M4.10): download a Gemma model through Ollama, streaming progress."""

import json
import logging
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from .. import llm
from ..config import DOWNLOAD_MODEL, settings

router = APIRouter()
log = logging.getLogger(__name__)

# Any Gemma model name Ollama accepts, e.g. gemma4:e4b, gemma4:e2b, gemma3:4b (IMPL §2 #20).
MODEL_NAME = re.compile(r"^gemma[0-9a-z.\-]*(:[0-9a-z.\-_]+)?$")


class PullRequest(BaseModel):
    model: str = DOWNLOAD_MODEL


@router.post("/setup/ollama/pull")
async def pull(req: PullRequest | None = None) -> EventSourceResponse:
    if llm.provider().name != "ollama":
        raise HTTPException(404, "Nothing to download: Gemma runs on the Gemini API here.")
    model = (req or PullRequest()).model.strip().lower()
    if not MODEL_NAME.match(model):
        raise HTTPException(422, "Only Gemma models can be downloaded here.")

    async def events():
        import ollama

        client = ollama.AsyncClient(host=settings.ollama_host, timeout=None)
        try:
            async for part in await client.pull(model, stream=True):
                yield {"event": "progress", "data": json.dumps(
                    {"status": part.status, "completed": part.completed, "total": part.total})}
            yield {"event": "done", "data": json.dumps({"model": model})}
        except Exception as exc:  # noqa: BLE001 — Ollama quit, disk full, no network…
            log.warning("pull %s failed: %s", model, exc)
            yield {"event": "error", "data": json.dumps({"message": f"Download stopped: {exc}"})}

    return EventSourceResponse(events(), ping=15)
