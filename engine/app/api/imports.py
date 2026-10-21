"""Statement upload for the column mapper (IMPL M3.5). The confirm step (running the audit) arrives in M4."""

import asyncio

from fastapi import APIRouter, HTTPException, UploadFile

from .. import db, ingest, user_settings
from ..state import runtime

router = APIRouter()

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # a 12-month statement is well under 1 MB


def _problem(exc: ingest.ImportProblem) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=exc.message)


@router.post("/import")
async def upload(file: UploadFile) -> dict:
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "That file is larger than 20 MB. Export a CSV statement instead.")
    name = (file.filename or "statement.csv").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    sha = ingest.sha256(raw)

    existing = await asyncio.to_thread(db.find_import_by_sha, sha)
    if existing and existing["status"] != "pending":
        # Re-importing the same file is a no-op (spec §7.3).
        return {"import_id": existing["id"], "duplicate": True, "file_name": existing["file_name"],
                "needs_mapping": False}

    default_currency = user_settings.load().currency
    try:
        parsed = await asyncio.to_thread(ingest.parse, raw, name, default_currency)
    except ingest.ImportProblem as exc:
        raise _problem(exc) from exc

    if existing:  # same file chosen again before confirming: reuse its pending row
        import_id = existing["id"]
        await asyncio.to_thread(db.update_pending_import, import_id, name, parsed.mapping,
                                parsed.currency, parsed.header_row)
    else:
        import_id = await asyncio.to_thread(db.create_pending_import, name, sha, parsed.mapping,
                                            parsed.currency, parsed.header_row)
    runtime.pending[import_id] = raw
    return parsed.payload(import_id)


@router.delete("/import/{import_id}")
async def discard(import_id: int) -> dict:
    """The mapper's Cancel: forget a pending upload. Committed statements can't be removed this way."""
    imp = await asyncio.to_thread(db.get_import, import_id)
    if imp is None:
        raise HTTPException(404, "That import doesn't exist.")
    if imp["status"] != "pending":
        raise HTTPException(409, "That statement has already been imported.")
    await asyncio.to_thread(db.delete_pending_import, import_id)
    runtime.pending.pop(import_id, None)
    return {"ok": True}
