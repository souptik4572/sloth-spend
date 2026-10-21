"""Renewal reminders (spec §7.10). M1 stub: the scheduler loop runs but has nothing to do until M7."""

import asyncio

TICK_SECONDS = 30


async def run_scheduler() -> None:
    while True:
        await asyncio.sleep(TICK_SECONDS)
