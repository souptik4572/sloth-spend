"""Reminder notes (spec §7.10, IMPL M7.3): a title and a short body for each notification.

Code formats every fact (merchant, amount, dates, saving). Gemma may phrase the note with structured output,
but it is only used when it adds no number, link or phone number and stays within three sentences; otherwise
`gemma_note` raises, the caller retries, and finally `template_note` writes it. A reminder never fails.
"""

import json
import re

from . import guard
from .llm_summary import NUMBER
from .money import date_long, date_short, money

Kind = str  # "reminder" | "verified" | "still_charged"
PER = {"weekly": "a week", "biweekly": "every two weeks", "monthly": "a month", "quarterly": "every three months",
       "annual": "a year", "single": "a year"}

SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}, "body": {"type": "string"}},
          "required": ["title", "body"]}

PROMPT = """Rephrase this {kind_of} notification from SlothSpend, a calm money app that never cancels anything for
the user, so it reads naturally. Return JSON with "title" (under 60 characters) and "body" (at most 3 short,
complete sentences).
Rules: keep its meaning; use only these facts and write every amount and date exactly as given; no links, phone
numbers or merchant-specific instructions; {ending}

Facts:
{facts}

Notification to rephrase:
{example}"""

ENDINGS = {
    "reminder": "end by pointing to How to cancel in SlothSpend, or Keep it.",
    "verified": "say plainly how much they're saving.",
    "still_charged": "say a refund request is ready to draft in SlothSpend.",
}


def _fmt(facts: dict, kind: Kind) -> dict:
    """Only the facts a note of this kind needs, formatted, under names a small model can't misread."""
    cur = facts.get("currency") or "USD"
    out = {"merchant": facts["merchant"]}
    if kind == "verified":
        if facts.get("monthly_equiv") or facts.get("amount"):
            out["monthly_saving"] = money(facts.get("monthly_equiv") or facts["amount"], cur)
        if facts.get("covers_until"):
            out["statements_checked_through"] = date_short(facts["covers_until"])
    elif kind == "still_charged":
        if facts.get("charged_on"):
            out["charged_again_on"] = date_long(facts["charged_on"])
            out["charged_again_amount"] = money(facts["charged_amount"], cur)
        elif facts.get("amount") is not None:
            out["charged_again_amount"] = money(facts["amount"], cur)
        if facts.get("cancelled_on"):
            out["user_cancelled_on"] = date_short(facts["cancelled_on"])
    else:
        if facts.get("amount") is not None:
            out["amount"] = money(facts["amount"], cur)
        if facts.get("next_due"):
            out["renewal_date"] = date_short(facts["next_due"])
    return out


def template_note(kind: Kind, facts: dict) -> dict:
    f = _fmt(facts, kind)
    m = f["merchant"]
    if kind == "verified":
        body = f"No {m} charge on your statement through {f.get('statements_checked_through', 'the latest date')}."
        if f.get("monthly_saving"):
            body += f" You’re saving {f['monthly_saving']} a month."
        return {"title": f"{m} has stopped", "body": body}
    if kind == "still_charged":
        amount = f.get("charged_again_amount", "A charge")
        when = f.get("charged_again_on", "your latest statement")
        after = f", after you cancelled on {f['user_cancelled_on']}" if f.get("user_cancelled_on") else ""
        return {"title": f"{m} charged again",
                "body": f"{amount} on {when}{after}. A refund request is ready to draft."}
    renews = f" {f['renewal_date']}" if f.get("renewal_date") else " soon"
    amount = f" for {f['amount']}" if f.get("amount") else ""
    return {"title": f"{m} renews{renews}",
            "body": f"{m} renews{renews}{amount}. If you no longer use it, open How to cancel in SlothSpend — "
                    "or tap Keep it."}


def acceptable(note: dict, facts_text: str) -> bool:
    title, body = str(note.get("title", "")).strip(), str(note.get("body", "")).strip()
    if not title or not body or len(title) > 80:
        return False
    text = f"{title} {body}"
    if "http" in text.lower() or "www." in text.lower() or guard.find_contacts(text):
        return False
    if len(re.findall(r"[.!?](\s|$)", body)) > 3:
        return False
    return set(NUMBER.findall(text)) <= set(NUMBER.findall(facts_text))


async def gemma_note(kind: Kind, facts: dict) -> dict:
    """Raises when Gemma is unavailable or its note breaks a rule (the caller retries, then uses the template)."""
    from . import llm, workspace
    from .report import gemma_model

    model = await gemma_model()
    if model is None:
        raise RuntimeError("Gemma isn't available")
    f = _fmt(facts, kind)
    facts_text = "\n".join(f"{k}: {v}" for k, v in f.items())
    example = template_note(kind, facts)
    # The template's own wording counts as allowed text too.
    reference = facts_text + "\n" + json.dumps(example, ensure_ascii=False)
    reply = await llm.provider().complete(model, [{"role": "user", "content": PROMPT.format(
        kind_of="browser" if workspace.on_web() else "desktop", ending=ENDINGS.get(kind, ""), facts=facts_text,
        example=f"Title: {example['title']}\nBody: {example['body']}")}],
        schema=SCHEMA, temperature=0.4, num_ctx=2048)
    note = json.loads(reply)
    note = {"title": " ".join(str(note.get("title", "")).split()), "body": " ".join(str(note.get("body", "")).split())}
    if not acceptable(note, reference):
        raise ValueError(f"Gemma's {kind} note broke a rule: {note!r}")
    return note
