from fastapi import APIRouter

from .. import llm
from ..config import settings
from ..tabular import tabular

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    # Never blocks on torch: tabular.status is a plain attribute set by the warm-up thread.
    # "llm": whoever serves Gemma right now — local Ollama or the Gemini API (`provider` says which).
    return {
        "engine": "ok",
        "llm": await llm.status(),
        "tabpfn": tabular.health(),
        "telemetry": settings.telemetry,
    }
