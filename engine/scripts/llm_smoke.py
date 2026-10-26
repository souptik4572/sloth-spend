"""Live check of every Gemma feature against the configured provider (WEB-IMPL W0.6). Exit code 0 = pass.

Runs the engine's real code paths against real Gemma, without the database:
  1. Status: the provider is ready and names the model it will use.
  2. Merchant names: one structured-output batch; most keys must come back named by Gemma.
  3. Summary: Gemma's rewrite (a fact-check rejection falls back to the template — reported, not a failure).
  4. Ask Sloth: Gemma calls get_merchant through function calling, then answers from the tool result.
  5. Draft: a streamed email rewrite that passes the draft fact check.
  6. Reminder note: structured JSON that passes the note rules.

usage:
  SLOTH_LLM_PROVIDER=ollama engine/.venv/bin/python engine/scripts/llm_smoke.py           # local Gemma
  SLOTH_LLM_PROVIDER=gemini GEMINI_API_KEY=… engine/.venv/bin/python engine/scripts/llm_smoke.py
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("SLOTH_DATA_DIR", tempfile.mkdtemp(prefix="sloth-llm-smoke-"))  # never the user's data
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import drafts, llm, llm_summary, normalize, notes, tools  # noqa: E402

KEYS = ["NETFLIX.COM 866", "ACH DEBIT IRONTRAP FITNESS MEMB", "WHOLEFDS MKT 10234"]
FACTS = {"currency": "USD", "monthly_recurring": 1979.86, "monthly_subscriptions": 87.46,
         "creep": {"merchant": "IronTrap Fitness", "from": 39.99, "to": 49.99, "pct": 25.0, "since": "2026-07-05",
                   "duplicate_same_month": True}}
MERCHANT = {"merchant": "IronTrap Fitness", "cadence": "monthly", "last_amount": "$49.99",
            "next_charge_due": "Nov 5, 2026", "flags": ["price rise", "double charge"],
            "recent_charges": [["Oct 5, 2026", "$49.99"], ["Sep 5, 2026", "$49.99"], ["Sep 7, 2026", "$49.99"]]}
EMAIL = """Subject: Refund request for a duplicate IronTrap Fitness charge

Hello IronTrap Fitness team,

I was charged $49.99 on Sep 5, 2026 and again on Sep 7, 2026 for the same membership. Please refund the
duplicate charge of $49.99 to my original payment method.

Thank you,
[Your name]"""

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'ok  ' if ok else 'FAIL'} {name}{' — ' + detail if detail else ''}")
    if not ok:
        failures.append(name)


async def main() -> int:
    provider = llm.provider()
    status = await llm.status()
    check("status", status["status"] == "ready",
          f"{provider.name} · {status['status']} · {status['model']} · available {status['available_models']}")
    if status["status"] != "ready":
        print(llm.unavailable_message(status["status"], provider.name))
        return 1
    model = status["model"]

    started = time.perf_counter()
    named = await normalize.normalize_batch(provider, model, KEYS)
    by_gemma = [k for k, v in named.items() if v["source"] == "llm"]
    check("merchant names", len(by_gemma) >= 2,
          f"{len(by_gemma)}/{len(KEYS)} by Gemma in {time.perf_counter() - started:.1f}s: "
          + ", ".join(f"{v['merchant']} ({v['category']})" for v in named.values()))

    started = time.perf_counter()
    summary, source = await llm_summary.write(FACTS, model)
    check("summary", bool(summary), f"source={source} in {time.perf_counter() - started:.1f}s: {summary[:120]}")

    started = time.perf_counter()
    messages = [{"role": "system", "content": "You are Sloth, a calm money assistant. Use the tools for facts."},
                {"role": "user", "content": "How much does IronTrap charge me, and when is the next charge?"}]
    calls = [c async for chunk in provider.stream(model, messages, tools=tools.SCHEMAS) for c in chunk.tool_calls]
    check("tool call", any(c.name == "get_merchant" for c in calls), f"calls={[(c.name, c.arguments) for c in calls]}")
    messages.append({"role": "assistant", "content": "",
                     "tool_calls": [{"function": {"name": c.name, "arguments": c.arguments}} for c in calls]})
    for c in calls:
        messages.append({"role": "tool", "tool_name": c.name, "content": json.dumps(MERCHANT)})
    answer = "".join([chunk.text async for chunk in provider.stream(model, messages, tools=tools.SCHEMAS)])
    check("tool answer", "49.99" in answer and "Nov" in answer,
          f"in {time.perf_counter() - started:.1f}s: {' '.join(answer.split())[:160]}")

    started = time.perf_counter()
    prompt = [{"role": "user", "content": drafts.PROMPT.format(merchant="IronTrap Fitness", draft=EMAIL)}]
    draft = drafts.tidy("".join([chunk.text async for chunk in provider.stream(model, prompt)]))
    check("draft", drafts.acceptable(draft, EMAIL), f"in {time.perf_counter() - started:.1f}s: {draft[:80]!r}")

    started = time.perf_counter()
    try:
        note = await notes.gemma_note("reminder", {"merchant": "IronTrap Fitness", "amount": 49.99,
                                                   "next_due": "2026-11-05", "currency": "USD"})
        check("reminder note", True, f"in {time.perf_counter() - started:.1f}s: {note}")
    except Exception as exc:  # noqa: BLE001 — the app would retry, then use the template
        check("reminder note", False, f"{type(exc).__name__}: {exc}")

    print("llm smoke passed" if not failures else f"llm smoke failed: {', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
