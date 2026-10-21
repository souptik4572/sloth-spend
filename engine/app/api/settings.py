"""GET/PUT /settings (IMPL M3.6): currency, chat model, reminder days, demo compression."""

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from .. import user_settings

router = APIRouter()


@router.get("/settings")
async def get_settings() -> dict:
    return (await asyncio.to_thread(user_settings.load)).model_dump()


@router.put("/settings")
async def put_settings(patch: user_settings.SettingsPatch) -> dict:
    try:
        saved = await asyncio.to_thread(user_settings.save, patch)
    except ValidationError as exc:
        first = exc.errors()[0]
        raise HTTPException(422, f"{first['loc'][-1]}: {first['msg']}") from exc
    return saved.model_dump()
