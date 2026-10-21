"""Ollama health checks and Gemma model selection (spec §12.4). The model pull arrives in M4 (IMPL M4.10)."""

import re
from urllib.parse import urlparse

import httpx

from .config import DOWNLOAD_MODEL

MIN_VERSION = (0, 20, 0)  # Gemma 4 tool calling needs Ollama ≥ 0.20
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
# Within one Gemma family, prefer these tags (in order) before any other tag.
TAG_ORDER = ("e4b", "latest")


def parse_version(text: str) -> tuple[int, int, int] | None:
    m = re.match(r"^\s*v?(\d+)\.(\d+)(?:\.(\d+))?", text or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)


def is_loopback(host_url: str) -> bool:
    url = host_url if "://" in host_url else f"http://{host_url}"
    return (urlparse(url).hostname or "") in LOOPBACK


def _family(name: str) -> str:
    return name.split(":", 1)[0].rsplit("/", 1)[-1].lower()  # "library/gemma4:e4b" -> "gemma4"


def is_gemma(name: str) -> bool:
    return _family(name).startswith("gemma")


def _rank(name: str) -> tuple:
    """Sort key: newest Gemma generation first, then preferred tags, then name."""
    family = _family(name)
    m = re.match(r"gemma(\d+)", family)
    generation = int(m.group(1)) if m else 1  # plain "gemma" is generation 1
    tag = name.split(":", 1)[1] if ":" in name else "latest"
    tag_rank = TAG_ORDER.index(tag) if tag in TAG_ORDER else len(TAG_ORDER)
    return (-generation, tag_rank, name)


def pick_model(installed: list[str], preferred: str | None = None) -> str | None:
    """The model SlothSpend talks to: the user's explicit choice if installed, else the best installed Gemma."""
    if preferred and preferred in installed:
        return preferred
    gemmas = sorted((n for n in installed if is_gemma(n)), key=_rank)
    return gemmas[0] if gemmas else None


async def status(host: str, preferred: str | None) -> dict:
    """{status, version, model, model_present, available_models, loopback}.

    status ∈ ready|unreachable|outdated|missing_model. `model` is the Gemma model in use, or the one
    Boot offers to download when none is installed.
    """
    out = {"status": "unreachable", "version": None, "model": preferred or DOWNLOAD_MODEL,
           "model_present": False, "available_models": [], "loopback": is_loopback(host)}
    try:
        async with httpx.AsyncClient(base_url=host, timeout=1.0) as client:
            out["version"] = (await client.get("/api/version")).json().get("version")
            parsed = parse_version(out["version"] or "")
            if parsed is None or parsed < MIN_VERSION:
                out["status"] = "outdated"
                return out
            tags = (await client.get("/api/tags")).json().get("models", [])
    except (httpx.HTTPError, ValueError):
        return out
    installed = sorted({t.get("name") or t.get("model") for t in tags} - {None})
    out["available_models"] = sorted((n for n in installed if is_gemma(n)), key=_rank)
    chosen = pick_model(installed, preferred)
    if chosen:
        out.update(model=chosen, model_present=True, status="ready")
    else:
        out.update(model=DOWNLOAD_MODEL, status="missing_model")
    return out
