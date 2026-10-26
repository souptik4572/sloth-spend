"""User settings stored in the `settings` table (IMPL M3.6). Values are JSON-encoded."""

import json
import sqlite3
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from . import db

Currency = Literal["USD", "INR", "EUR", "GBP"]


class UserSettings(BaseModel):
    currency: Currency = "USD"
    # Any installed Ollama model name, or one of SLOTH_GEMINI_MODELS on the Gemini API; None = the best Gemma
    # available (IMPL §2 #20, WEB-IMPL §2.1). A name the provider lacks falls back to that default.
    chat_model: str | None = None
    days_before: int = Field(3, ge=1, le=14)
    # 0 = off; otherwise every reminder wait becomes this many seconds (demo mode).
    demo_compress_seconds: int = Field(0, ge=0, le=600)

    @field_validator("chat_model")
    @classmethod
    def _blank_is_automatic(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return v or None

    @field_validator("demo_compress_seconds")
    @classmethod
    def _demo_range(cls, v: int) -> int:
        if v and v < 5:
            raise ValueError("demo compression must be 0 (off) or 5–600 seconds")
        return v


class SettingsPatch(BaseModel):
    """PUT /settings body: only the keys being changed."""

    currency: Currency | None = None
    chat_model: str | None = None
    days_before: int | None = None
    demo_compress_seconds: int | None = None


def load() -> UserSettings:
    try:
        stored = db.all_settings()
    except sqlite3.Error:
        return UserSettings()  # engine still starting, or no database yet
    values = {}
    for key in UserSettings.model_fields:
        if key in stored:
            try:
                values[key] = json.loads(stored[key])
            except ValueError:
                continue  # a corrupt value falls back to its default
    try:
        return UserSettings(**values)
    except ValueError:
        return UserSettings()


def save(patch: SettingsPatch) -> UserSettings:
    """Validates the merged result before writing anything. Raises pydantic.ValidationError."""
    changes = patch.model_dump(exclude_unset=True)
    merged = UserSettings(**{**load().model_dump(), **changes})
    db.set_settings({key: json.dumps(getattr(merged, key)) for key in changes})
    return merged
