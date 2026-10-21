"""Process-wide mutable state shared by routes and background tasks."""

import asyncio
from types import SimpleNamespace

runtime = SimpleNamespace(
    scheduler_task=None,  # asyncio.Task running reminders.run_scheduler()
    pipeline_lock=asyncio.Lock(),  # one audit / re-score at a time (IMPL §3.4)
    pending={},  # import_id -> raw CSV bytes awaiting /confirm
    pipeline_task=None,  # the running audit (report.start_pipeline)
    normalize_task=None,  # Gemma finishing deferred merchant names in the background
)
