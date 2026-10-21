from fastapi import APIRouter

from .. import ollama_setup
from ..config import settings
from ..tabular import tabular

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    # Never blocks on torch: tabular.status is a plain attribute set by the warm-up thread.
    return {
        "engine": "ok",
        "ollama": await ollama_setup.status(settings.ollama_host, settings.preferred_model),
        "tabpfn": tabular.health(),
        "telemetry": settings.telemetry,
    }
