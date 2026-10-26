from fastapi import APIRouter

from .. import llm
from ..config import settings
from ..tabular import tabular

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    # Never blocks on torch: tabular.status is a plain attribute set by the warm-up thread.
    # "ollama" is the active Gemma provider's status (its `provider` says which); W3 renames it to "llm".
    return {
        "engine": "ok",
        "ollama": await llm.status(),
        "tabpfn": tabular.health(),
        "telemetry": settings.telemetry,
    }
