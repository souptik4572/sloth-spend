"""Web server configuration from the environment (WEB-IMPL §2.3)."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[3]


def _public_url() -> str:
    return os.environ.get("SLOTH_PUBLIC_URL", "http://localhost:8770").rstrip("/")


def _cookie_secure() -> bool:
    flag = os.environ.get("SLOTH_COOKIE_SECURE")
    return flag == "1" if flag in ("0", "1") else _public_url().startswith("https://")


@dataclass(frozen=True)
class WebSettings:
    # Where people open SlothSpend; email links point here. In dev that's the Vite server.
    public_url: str = field(default_factory=_public_url)
    host: str = field(default_factory=lambda: os.environ.get("SLOTH_WEB_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.environ.get("SLOTH_WEB_PORT", "8770")))
    cookie_secure: bool = field(default_factory=_cookie_secure)
    # smtp://user:pass@host:587 (STARTTLS) or smtps://user:pass@host:465. Empty = the dev outbox.
    smtp_url: str = field(default_factory=lambda: os.environ.get("SLOTH_SMTP_URL", "").strip())
    mail_from: str = field(default_factory=lambda: os.environ.get("SLOTH_MAIL_FROM", "SlothSpend <no-reply@localhost>"))
    dist: Path = field(default_factory=lambda: Path(os.environ.get("SLOTH_WEB_DIST", REPO / "web" / "dist")))
    # Behind a reverse proxy, take the client IP from X-Forwarded-For (rate limits).
    trust_proxy: bool = field(default_factory=lambda: os.environ.get("SLOTH_TRUST_PROXY") == "1")
    # Gemma calls one account may start per minute, so nobody drains the shared Gemini key.
    llm_per_minute: int = field(default_factory=lambda: int(os.environ.get("SLOTH_USER_LLM_PER_MIN", "30")))
    max_upload_bytes: int = 10 * 1024 * 1024

    @property
    def public_origin(self) -> str:
        u = urlparse(self.public_url)
        return f"{u.scheme}://{u.netloc}"

    def link(self, path: str) -> str:
        return f"{self.public_url}{path}"


web = WebSettings()
