"""Runtime configuration from the environment Electron main sets at spawn (spec Appendix B)."""

import os
from dataclasses import dataclass, field
from pathlib import Path

# What Boot offers to download when Ollama has no Gemma model at all. Any installed Gemma model is
# used as-is (see ollama_setup.pick_model); this is not a restriction.
DOWNLOAD_MODEL = "gemma4:e4b"


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

    @property
    def preferred_model(self) -> str | None:
        # M3 adds the Settings-table override (IMPL M1.1); until then the env var, if set.
        return self.env_chat_model or None


settings = Settings()
