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


def _stream(run: report.Run) -> EventSourceResponse:
    return EventSourceResponse(run.follow(), ping=15)


async def _start(import_id: int, opts: dict, file_name: str, rows: int | None = None) -> EventSourceResponse:
    try:
        run = await report.start_pipeline(import_id, opts, file_name=file_name, rows=rows)
    except report.PipelineBusy as exc:
        raise HTTPException(409, "An audit is already running.") from exc
    return _stream(run)


def _running() -> report.Run | None:
    run = runtime.pipeline_run
    return run if run is not None and not run.finished else None


@router.get("/audit")
async def audit_status() -> dict:
    """Is an audit running in this workspace? A reloaded (or second) tab asks before showing the report."""
    run = _running()
    return run.status() if run else {"running": False, "file": None, "rows": None, "started_at": None}


@router.post("/audit/follow")
async def follow_audit() -> EventSourceResponse:
    """The running audit's events from its first stage on, then live, ending with done or error."""
    run = _running()
    if run is None:
        raise HTTPException(404, "No audit is running.")
    return _stream(run)


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
    return await _start(import_id, (opts or ConfirmOpts()).model_dump(exclude_none=True), imp["file_name"],
                        imp["row_count"])


@router.post("/demo/load-sample")
async def load_sample(req: SampleRequest | None = None) -> EventSourceResponse:
    """Import a bundled statement (D-Import's "Load sample statement" and the Demo data menu)."""
    name = SAMPLES[(req or SampleRequest()).file]
    raw = (DATA / name).read_bytes()
    existing = await asyncio.to_thread(db.find_import_by_sha, ingest.sha256(raw))
    if existing and existing["status"] == "committed":  # Try again after a failed audit
        return await _start(existing["id"], {}, name)
    if existing and existing["status"] != "pending":
        # Already imported: nothing to add, just hand back the current report.
        run = report.Run(name)
        await run.put(report._ev("done", report=await asyncio.to_thread(report.load_report), duplicate=True))
        await run.put(None)
        return _stream(run)
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
    return await _start(import_id, {}, name)


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
