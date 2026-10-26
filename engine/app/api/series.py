"""One merchant: drawer detail, corrections and renames (IMPL M4.8). Every change re-scores (≤ 5 s)."""

import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from .. import db, drafts, explain, report
from . import reminders as reminders_api
from ..normalize import CATEGORIES
from ..tabular import QUANTILES

router = APIRouter()

LABELS = {"subscription": (1, "active"), "not_subscription": (0, "not_subscription"), "keep": (1, "keep")}


class LabelRequest(BaseModel):
    label: Literal["subscription", "not_subscription", "keep"]


class DraftRequest(BaseModel):
    kind: Literal["cancel_request", "refund", "negotiate"]


class MerchantEdit(BaseModel):
    merchant: str = Field(min_length=1, max_length=40)
    category: str


def _get(series_id: int) -> dict:
    s = db.series_by_id(series_id)
    if s is None:
        raise HTTPException(404, "That merchant isn't in the report.")
    return s


async def _rescore() -> dict:
    if report.audit_running():
        raise HTTPException(409, "An audit is already running. Try again in a moment.")
    return await report.rescore()  # another re-score in progress: this one waits its turn (seconds)


def _source(keys: list[str]) -> tuple[str, bool]:
    entries = db.merchant_map_get(keys).values()
    sources = {e["source"] for e in entries}
    source = "user" if "user" in sources else "llm" if "llm" in sources else "rule"
    return source, any(e["subscription_like"] for e in entries)


@router.get("/series/{series_id}")
async def detail(series_id: int) -> dict:
    def build() -> dict:
        s = _get(series_id)
        txs = db.merchant_transactions(s["merchant"])
        keys = db.desc_keys_for_merchant(s["merchant"])
        source, sub_like = _source(keys)
        meta = db.report_meta() or {}
        currency = meta.get("currency") or "USD"
        return {
            "series": report.series_out(s),
            "transactions": [{"id": t["id"], "date": t["tx_date"], "amount": t["amount"],
                              "is_duplicate": bool(t["is_duplicate"])} for t in txs],
            "quantiles": [{"q": q, "amount": a} for q, a in zip(QUANTILES, s["quantiles_json"] or [], strict=False)],
            "similar": s["similar_json"],
            "reasons": explain.reasons(s, txs, source=source, subscription_like=sub_like, currency=currency),
            "raw_descriptions": db.raw_descriptions_for_merchant(s["merchant"]),
            "desc_keys": keys,
            "reminder": reminders_api.one(series_id),
        }
    return await asyncio.to_thread(build)


@router.post("/series/{series_id}/label")
async def label(series_id: int, req: LabelRequest) -> dict:
    """Keep / Not a subscription / It's a subscription. TabPFN learns it in context (spec §7.6)."""
    s = await asyncio.to_thread(_get, series_id)
    value, status = LABELS[req.label]
    if s["features_json"]:  # one-off "possible annual" rows have no features to learn from
        await asyncio.to_thread(db.upsert_label, s["merchant"], value, s["features_json"])
    await asyncio.to_thread(db.set_series_status, s["merchant"], status)
    return {"report": await _rescore()}


async def _rename(keys: list[str], old: str | None, edit: MerchantEdit) -> dict:
    if edit.category not in CATEGORIES:
        raise HTTPException(422, f"Unknown category {edit.category!r}.")
    name = " ".join(edit.merchant.split())

    def write() -> None:
        current = db.merchant_map_get(keys)
        db.merchant_map_upsert({k: {"merchant": name, "category": edit.category, "source": "user",
                                    "subscription_like": bool(current.get(k, {}).get("subscription_like"))}
                                for k in keys})
        db.apply_merchant_map()
        if old:
            db.rename_merchant_state(old, name)

    await asyncio.to_thread(write)
    result = await _rescore()
    return {"report": result, "series_id": await asyncio.to_thread(db.series_id_for, name)}


@router.patch("/series/{series_id}/merchant")
async def rename_series(series_id: int, edit: MerchantEdit) -> dict:
    """The drawer's Merchant details: rename / recategorise every description of this merchant."""
    s = await asyncio.to_thread(_get, series_id)
    keys = await asyncio.to_thread(db.desc_keys_for_merchant, s["merchant"])
    return await _rename(keys, s["merchant"], edit)


@router.patch("/merchant-map/{key}")
async def rename_key(key: str, edit: MerchantEdit) -> dict:
    """Spec §8: rename / recategorise one description key."""
    if not await asyncio.to_thread(db.merchant_map_get, [key]):
        raise HTTPException(404, "Unknown description key.")
    return await _rename([key], None, edit)


@router.post("/series/{series_id}/draft")
async def draft(series_id: int, req: DraftRequest) -> EventSourceResponse:
    """A cancellation, refund or negotiation email for the user to send (IMPL M6.3). Streams tokens."""
    await asyncio.to_thread(_get, series_id)
    model = await report.gemma_model()
    return EventSourceResponse(drafts.stream(series_id, req.kind, model), ping=15)
