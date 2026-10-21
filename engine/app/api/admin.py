import asyncio
import os

from fastapi import APIRouter

router = APIRouter()


@router.post("/shutdown")
async def shutdown() -> dict:
    # Answer first, then exit; Electron main follows up by closing our stdin anyway.
    asyncio.get_running_loop().call_later(0.2, os._exit, 0)
    return {"ok": True}
