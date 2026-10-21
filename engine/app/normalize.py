"""Merchant normalisation (spec §7.4, IMPL M4.1).

1. Pre-clean each description into a `desc_key` (done at import).
2. Skip keys already in the merchant_map cache (Gemma or user entries; rule entries are retried).
3. Gemma names the rest in batches of 25 with structured output, **most important keys first**:
   repeating keys (possible subscriptions), then one-off charges by amount. Gemma writes ~70 tokens/s
   and Ollama serves one request at a time, so the audit gives Gemma a time budget; keys left over get
   the rule fallback now and are finished by Gemma in the background (the cache keeps them).
4. User edits (source='user') always win; Gemma never overwrites them.
"""

import asyncio
import json
import logging
import os
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError

from . import db

log = logging.getLogger(__name__)

CATEGORIES = ["Streaming", "Music", "Software", "Cloud Storage", "Fitness", "News & Media", "Telecom",
              "Utilities", "Insurance", "Housing", "Food Delivery", "Groceries", "Dining", "Transport",
              "Shopping", "Travel", "Health", "Education", "Transfers", "Fees", "Other"]

NOISE = [
    r"\b\d{0,6}[X\*]{3,}\d{0,6}\b",  # card masks inside one token, e.g. 4160XXXX2291 (added to §7.4)
    r"\b(POS|ACH|DEBIT|CREDIT|CARD|PURCHASE|RECURRING|PAYMENT|ONLINE|ECOM|NEFT|IMPS|UPI|VISA|MASTERCARD|TXN|REF)\b",
    r"\b[X\*]{2,}\d{2,4}\b",
    r"\b\d{4,}\b",
    r"\b\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?\b",
    r"#\S+",
    r"[^A-Z0-9&\.\* ]",
]

BATCH_SIZE = 25
BUDGET_SECONDS = float(os.environ.get("SLOTH_NORMALIZE_BUDGET", "30"))
REQUEST_TIMEOUT = 120.0

# One-letter field names: Gemma's output tokens are the bottleneck, and these cut them by about a third.
SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "i": {"type": "integer"},
                    "m": {"type": "string"},
                    "c": {"type": "string", "enum": CATEGORIES},
                    "s": {"type": "boolean"},
                },
                "required": ["i", "m", "c", "s"],
            },
        }
    },
    "required": ["items"],
}

PROMPT = """You clean bank transaction descriptions.
For each numbered line return: i = the line number; m = the merchant's common brand name (Title Case, no
store numbers, cities or reference codes); c = one category from the allowed list; s = true only if this
kind of merchant usually bills a recurring plan (streaming, music, software, gym, cloud storage, news,
phone plan, insurance).
Examples:
0: "NETFLIX.COM 866" -> {{"i": 0, "m": "Netflix", "c": "Streaming", "s": true}}
1: "WHOLEFDS MKT" -> {{"i": 1, "m": "Whole Foods", "c": "Groceries", "s": false}}
2: "RENT TRANSFER TO OAKWOOD PROP" -> {{"i": 2, "m": "Rent", "c": "Housing", "s": false}}
Lines:
{lines}"""


def desc_key(raw: str) -> str:
    s = raw.upper()
    for pattern in NOISE:
        s = re.sub(pattern, " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return (s or raw.upper())[:60]


class Item(BaseModel):
    i: int
    m: str
    c: str
    s: bool


class Batch(BaseModel):
    items: list[Item]


# Card-processor prefixes that say who took the payment, not who the merchant is ("SQ *COPPER KITCHEN").
PROCESSOR_PREFIX = re.compile(r"^(SQ|SQU|SQUARE|TST|SP|PP|PAYPAL|CKO|LS|PY|IC|D)\b\s*\*?\s*")


def rule_fallback(key: str) -> dict:
    """Name without Gemma: drop processor prefixes, keep up to three words.

    Keeps different shops apart ("Copper Kitchen" vs "Copper Grill" — two words would merge them into a
    fake recurring "Copper") while variants of one merchant still meet ("SQ *BEANTHERE COFFEE" and
    "BEANTHERE COFFEE" → "Beanthere Coffee").
    """
    words = PROCESSOR_PREFIX.sub("", key.replace("*", " * ")).replace("*", " ").split()
    kept, counted = [], 0
    for word in words:  # "&" joins words ("FOX & PINE TOYS") and doesn't use up one of the three
        if counted == 3:
            break
        kept.append(word)
        counted += word != "&"
    name = " ".join(kept).title() or key.title() or "Unknown"
    return {"merchant": name, "category": "Other", "subscription_like": False, "source": "rule"}


async def normalize_batch(client, model: str, keys: list[str]) -> dict[str, dict]:
    """One Gemma call for up to 25 keys. Missing or invalid items fall back to the rule."""
    lines = "\n".join(f"{i}: {json.dumps(k)}" for i, k in enumerate(keys))
    try:
        resp = await client.chat(
            model=model,
            messages=[{"role": "user", "content": PROMPT.format(lines=lines)}],
            format=SCHEMA,
            think=False,
            options={"temperature": 0, "num_ctx": 8192},
        )
        items = Batch.model_validate_json(resp.message.content).items
    except (ValidationError, ValueError) as exc:
        log.warning("Gemma returned unusable JSON for %d keys: %s", len(keys), exc)
        items = []
    by_index = {it.i: it for it in items if 0 <= it.i < len(keys)}
    out: dict[str, dict] = {}
    for i, key in enumerate(keys):
        it = by_index.get(i)
        if it and it.m.strip():
            category = it.c if it.c in CATEGORIES else "Other"
            out[key] = {"merchant": it.m.strip()[:40], "category": category,
                        "subscription_like": it.s, "source": "llm"}
        else:
            out[key] = rule_fallback(key)
    return out


@dataclass
class KeyStat:
    key: str
    count: int
    total: float
    largest: float


def prioritise(stats: list[KeyStat]) -> list[str]:
    """Repeating keys first (they can be subscriptions), then one-offs by size, then the rest."""
    def rank(s: KeyStat) -> tuple:
        tier = 0 if s.count >= 2 else 1 if s.largest >= 20 else 2
        return (tier, -s.total, s.key)
    return [s.key for s in sorted(stats, key=rank)]


@dataclass
class Normalizer:
    """Fills merchant_map for every debit key. `deferred` lists keys left to finish in the background."""

    stats: list[KeyStat]
    model: str | None  # None = Gemma unavailable → rule fallback for everything new
    host: str = "http://127.0.0.1:11434"
    budget_seconds: float = BUDGET_SECONDS
    deferred: list[str] = field(default_factory=list)
    llm_named: int = 0

    async def run(self) -> AsyncIterator[tuple[int, int]]:
        keys = prioritise(self.stats)
        total = len(keys)
        cached = await asyncio.to_thread(db.merchant_map_get, keys)
        retry_rule = self.model is not None
        todo = [k for k in keys if k not in cached or (retry_rule and cached[k]["source"] == "rule")]
        done = total - len(todo)
        yield done, total

        if not todo:
            return
        if self.model is None:
            await asyncio.to_thread(db.merchant_map_upsert, {k: rule_fallback(k) for k in todo})
            yield total, total
            return

        import ollama  # imported lazily: tests and rule-only runs never need the client

        client = ollama.AsyncClient(host=self.host, timeout=REQUEST_TIMEOUT)
        started = time.monotonic()
        batch_seconds = 0.0  # the slowest batch so far: don't start one that would overrun the budget
        while todo:
            if time.monotonic() - started + batch_seconds > self.budget_seconds:
                self.deferred = list(todo)
                await asyncio.to_thread(db.merchant_map_upsert, {k: rule_fallback(k) for k in todo})
                yield total, total
                return
            batch, todo = todo[:BATCH_SIZE], todo[BATCH_SIZE:]
            batch_started = time.monotonic()
            try:
                entries = await normalize_batch(client, self.model, batch)
            except Exception as exc:  # noqa: BLE001 — Ollama down mid-run: finish with the rule
                log.warning("Gemma unavailable during normalisation (%s); using the rule for the rest", exc)
                rest = batch + todo
                await asyncio.to_thread(db.merchant_map_upsert, {k: rule_fallback(k) for k in rest})
                yield total, total
                return
            batch_seconds = max(batch_seconds, time.monotonic() - batch_started)
            self.llm_named += sum(e["source"] == "llm" for e in entries.values())
            await asyncio.to_thread(db.merchant_map_upsert, entries)
            done += len(batch)
            yield done, total


async def finish_deferred(keys: list[str], model: str, host: str) -> int:
    """Background: let Gemma name the keys the audit's time budget left to the rule. Returns how many."""
    import ollama

    from .state import runtime

    client = ollama.AsyncClient(host=host, timeout=REQUEST_TIMEOUT)
    named = 0
    for start in range(0, len(keys), BATCH_SIZE):
        # Yield to audits and re-scores: Gemma and TabPFN share the GPU, and a correction must stay ≤ 5 s.
        while runtime.pipeline_lock.locked():
            await asyncio.sleep(0.5)
        batch = keys[start:start + BATCH_SIZE]
        try:
            entries = await normalize_batch(client, model, batch)
        except Exception as exc:  # noqa: BLE001
            log.info("background normalisation stopped: %s", exc)
            break
        llm = {k: v for k, v in entries.items() if v["source"] == "llm"}
        await asyncio.to_thread(db.merchant_map_upsert, llm)
        named += len(llm)
    if named:
        await asyncio.to_thread(db.apply_merchant_map)
    log.info("background normalisation named %d of %d deferred keys", named, len(keys))
    return named
