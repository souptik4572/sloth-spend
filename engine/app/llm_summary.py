"""Sloth's summary (spec §7.8 step 8, IMPL M4.7).

Code writes a calm templated summary with every number pre-formatted. Gemma may only rephrase it: if its
version contains any number the template doesn't, or forgets that nothing was cancelled, the template wins.
"""

import logging
import re

from . import llm
from .money import money, month_name

log = logging.getLogger(__name__)

NOTHING_CANCELLED = "Nothing has been cancelled — that’s your call."
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")

PROMPT = """Rewrite this summary of someone's bank statement in 3 or 4 calm, plain sentences.
Rules: keep every fact; use only the numbers, amounts and names that appear below, written exactly as they
are; add no advice beyond what is there; no greetings, lists, headings or emoji; end by saying nothing has
been cancelled and that it's their call.

{facts}"""


def template(facts: dict) -> str:
    """facts: currency, monthly_recurring, monthly_subscriptions, creep?, overlap?, dispute? (raw numbers)."""
    cur = facts["currency"]
    parts = [f"You pay {money(facts['monthly_recurring'], cur)} a month in recurring charges, and "
             f"{money(facts['monthly_subscriptions'], cur)} of that is subscriptions."]
    creep = facts.get("creep")
    if creep:
        line = (f"{creep['merchant']} went from {money(creep['from'], cur)} to {money(creep['to'], cur)} "
                f"in {month_name(creep['since'])}")
        line += " and charged you twice that month." if creep.get("duplicate_same_month") else "."
        parts.append(line)
    elif facts.get("dispute"):
        d = facts["dispute"]
        parts.append(f"{d['merchant']} charged you {money(d['amount'], cur)} twice in {month_name(d['first'])}.")
    overlap = facts.get("overlap")
    if overlap:
        names = overlap["merchants"]
        joined = " and ".join(names) if len(names) == 2 else ", ".join(names[:-1]) + f" and {names[-1]}"
        parts.append(f"{joined} are all {overlap['category'].lower()} services, so you may only need one."
                     if len(names) > 2 else
                     f"{joined} are both {overlap['category'].lower()} services, so you may only need one.")
    parts.append(NOTHING_CANCELLED)
    return " ".join(parts)


def acceptable(candidate: str, reference: str) -> bool:
    """Gemma's rewrite may not introduce numbers, and must still say nothing was cancelled."""
    allowed = set(NUMBER.findall(reference))
    used = set(NUMBER.findall(candidate))
    return bool(candidate.strip()) and used <= allowed and "cancel" in candidate.lower()


async def write(facts: dict, model: str | None) -> tuple[str, str]:
    """(summary, source) with source = "gemma" | "template"."""
    text = template(facts)
    if model is None:
        return text, "template"
    try:
        reply = await llm.provider().complete(model, [{"role": "user", "content": PROMPT.format(facts=text)}],
                                              temperature=0.4, num_ctx=4096)
        candidate = " ".join(reply.split())
    except Exception as exc:  # noqa: BLE001 — Gemma unreachable: the template is a fine summary
        log.info("summary: Gemma unavailable (%s); using the template", exc)
        return text, "template"
    if acceptable(candidate, text):
        return candidate, "gemma"
    log.info("summary: Gemma's rewrite changed the facts; using the template")
    return text, "template"
