import hmac

from fastapi import Header, HTTPException

from .config import settings


async def require_token(x_sloth_token: str | None = Header(default=None)) -> None:
    if not x_sloth_token or not settings.token or not hmac.compare_digest(x_sloth_token, settings.token):
        raise HTTPException(status_code=401, detail="bad token")
