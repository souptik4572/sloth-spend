"""Ask Sloth routes (IMPL M6.4): stream a turn, and redraw a conversation."""

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from .. import agent, db

router = APIRouter()


class ChatRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=2000)


@router.post("/chat")
async def chat(req: ChatRequest) -> EventSourceResponse:
    return EventSourceResponse(agent.run_turn(req.conversation_id, req.message.strip()), ping=15)


@router.get("/chat/{conversation_id}")
async def history(conversation_id: str) -> dict:
    return {"conversation_id": conversation_id,
            "messages": await asyncio.to_thread(db.chat_history, conversation_id)}
