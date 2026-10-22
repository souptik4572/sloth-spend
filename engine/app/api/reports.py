"""Audit routes (IMPL M4.8): confirm an import, load the bundled demo statements, read and re-score the report."""

import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from .. import db, ingest, report, user_settings
from ..paths import DATA
from ..state import runtime

router = APIRouter()

SAMPLES = {"main": "sample_bank_12m.csv", "followup_cancelled": "followup_cancelled.csv",
           "followup_still_charged": "followup_still_charged.csv"}


class ConfirmOpts(BaseModel):
    mapping: dict[str, int] | None = None
    debits_positive: bool | None = None
    currency: Literal["USD", "INR", "EUR", "GBP"] | None = None
    dayfirst: bool | None = None


class SampleRequest(BaseModel):
    file: Literal["main", "followup_cancelled", "followup_still_charged"] = "main"


def _stream(queue: asyncio.Queue) -> EventSourceResponse:
    async def events():
        while (item := await queue.get()) is not None:
            yield item
    return EventSourceResponse(events(), ping=15)


async def _start(import_id: int, opts: dict) -> EventSourceResponse:
    try:
        queue = await report.start_pipeline(import_id, opts)
    except report.PipelineBusy as exc:
        raise HTTPException(409, "An audit is already running.") from exc
    return _stream(queue)


@router.post("/import/{import_id}/confirm")
async def confirm(import_id: int, opts: ConfirmOpts | None = None) -> EventSourceResponse:
    """Run the audit on a pending upload — or again on one whose audit failed after its rows were stored.
    Problems known up front are plain HTTP errors, not stream events."""
    imp = await asyncio.to_thread(db.get_import, import_id)
    if imp is None:
        raise HTTPException(404, "That import doesn't exist.")
    if imp["status"] == "done":
        raise HTTPException(409, "That statement has already been imported.")
    if imp["status"] == "pending" and import_id not in runtime.pending:
        raise HTTPException(410, "SlothSpend restarted since you chose this file. Please choose it again.")
    return await _start(import_id, (opts or ConfirmOpts()).model_dump(exclude_none=True))


@router.post("/demo/load-sample")
async def load_sample(req: SampleRequest | None = None) -> EventSourceResponse:
    """Import a bundled statement (D-Import's "Load sample statement" and the Demo data menu)."""
    name = SAMPLES[(req or SampleRequest()).file]
    raw = (DATA / name).read_bytes()
    existing = await asyncio.to_thread(db.find_import_by_sha, ingest.sha256(raw))
    if existing and existing["status"] == "committed":  # Try again after a failed audit
        return await _start(existing["id"], {})
    if existing and existing["status"] != "pending":
        # Already imported: nothing to add, just hand back the current report.
        queue: asyncio.Queue = asyncio.Queue()
        await queue.put(report._ev("done", report=await asyncio.to_thread(report.load_report), duplicate=True))
        await queue.put(None)
        return _stream(queue)
    try:
        parsed = await asyncio.to_thread(ingest.parse, raw, name, user_settings.load().currency)
    except ingest.ImportProblem as exc:
        raise HTTPException(exc.status, exc.message) from exc
    if existing:
        import_id = existing["id"]
    else:
        import_id = await asyncio.to_thread(db.create_pending_import, name, parsed.sha256, parsed.mapping,
                                            parsed.currency, parsed.header_row)
    runtime.pending[import_id] = raw
    return await _start(import_id, {})


@router.get("/report")
async def get_report() -> dict:
    result = await asyncio.to_thread(report.load_report)
    if result is None:
        raise HTTPException(404, "No report yet. Import a statement first.")
    return result


@router.post("/report/rescore")
async def rescore() -> dict:
    """Re-score with the current model and labels — e.g. after TabPFN finished loading or got upgraded."""
    if await asyncio.to_thread(db.report_meta) is None:
        raise HTTPException(404, "No report yet. Import a statement first.")
    if report.busy():
        raise HTTPException(409, "An audit is already running.")
    return {"report": await report.rescore()}
