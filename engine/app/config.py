"""Runtime configuration from the environment Electron main sets at spawn (spec Appendix B)."""

import os
from dataclasses import dataclass, field
from pathlib import Path

# What Boot offers to download when Ollama has no Gemma model at all. Any installed Gemma model is
# used as-is (see ollama_setup.pick_model); this is not a restriction.
DOWNLOAD_MODEL = "gemma4:e4b"

# The Gemma models the Gemini API serves (WEB-IMPL W-D3); the first is the default.
GEMINI_MODELS = "gemma-4-26b-a4b-it,gemma-4-31b-it"


def _csv(value: str) -> tuple[str, ...]:
    return tuple(v.strip() for v in value.split(",") if v.strip())


@dataclass(frozen=True)
class Settings:
    port: int = field(default_factory=lambda: int(os.environ.get("SLOTH_PORT", "8765")))
    token: str = field(default_factory=lambda: os.environ.get("SLOTH_TOKEN", ""))
    data_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("SLOTH_DATA_DIR", Path.cwd() / ".sloth-data"))
    )
    ollama_host: str = field(
        default_factory=lambda: os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    )
    telemetry: bool = field(default_factory=lambda: os.environ.get("SLOTH_TELEMETRY") == "1")
    # Optional explicit choice (any Ollama model name). Empty = pick the best installed Gemma.
    env_chat_model: str = field(default_factory=lambda: os.environ.get("SLOTH_CHAT_MODEL", "").strip())
    # Who serves Gemma (WEB-IMPL §2.1): "ollama" (desktop, local dev) or "gemini" (the web, server key).
    llm_provider: str = field(
        default_factory=lambda: os.environ.get("SLOTH_LLM_PROVIDER", "ollama").strip().lower() or "ollama"
    )
    gemini_api_key: str = field(
        default_factory=lambda: (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    )
    gemini_models: tuple[str, ...] = field(
        default_factory=lambda: _csv(os.environ.get("SLOTH_GEMINI_MODELS", "")) or _csv(GEMINI_MODELS)
    )
    gemini_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "SLOTH_GEMINI_BASE_URL", "https://generativelanguage.googleapis.com").rstrip("/")
    )
    llm_concurrency: int = field(default_factory=lambda: int(os.environ.get("SLOTH_LLM_CONCURRENCY", "4")))

    @property
    def preferred_model(self) -> str | None:
        """An explicit chat model: Settings first, then SLOTH_CHAT_MODEL; None = best installed Gemma."""
        from . import user_settings  # local import: user_settings → db → config

        return user_settings.load().chat_model or self.env_chat_model or None


settings = Settings()
