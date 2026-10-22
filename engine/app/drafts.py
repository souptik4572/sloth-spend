"""Email drafts the user sends themselves (IMPL M6.3, spec §7.9): cancellation, refund, negotiation.

Code writes a complete template from the merchant's own facts (the exact shape in D-Drawer / D-Reminders).
Gemma may rephrase it in a polite, firm tone, but its version is only kept if it starts with the subject
line, keeps the sign-off, adds no number the template doesn't have, and contains no link, email address or
phone number. Anything else, or no Gemma at all, and the template is the draft. SlothSpend never sends it.
"""

import json
import logging
import re
from collections.abc import AsyncIterator
from typing import Literal

from . import db, guard
from .llm_summary import NUMBER
from .money import MONTH_NAMES, date_long, date_short, money, plural

log = logging.getLogger(__name__)

Kind = Literal["cancel_request", "refund", "negotiate"]
TITLES = {"cancel_request": "Cancellation request", "refund": "Refund request", "negotiate": "Negotiation email"}
SIGN_OFF = "Thank you,\n[Your name]"
PER = {"weekly": "a week", "biweekly": "every two weeks", "monthly": "a month", "quarterly": "every three months",
       "annual": "a year", "single": "a year"}

PROMPT = """Rewrite this email so it reads naturally: short, polite and firm. The user will send it themselves.
Rules: keep the first line exactly in the form "Subject: …"; greet the {merchant} team; keep every fact and
write every date and amount exactly as below; add no new facts, links, phone numbers, email addresses or
account numbers; no markdown; end with exactly:
Thank you,
[Your name]

{draft}"""


class NotFound(Exception):
    pass


def facts(series_id: int) -> dict:
    """What the drafts may say about one merchant, straight from the report."""
    s = db.series_by_id(series_id)
    if s is None:
        raise NotFound
    meta = db.report_meta() or {}
    txs = db.merchant_transactions(s["merchant"])
    amounts = [t["amount"] for t in txs if not t["is_duplicate"]] or [s["last_amount"]]
    return {
        "merchant": s["merchant"], "category": s["category"], "kind": s["kind"],
        "currency": meta.get("currency") or "USD", "cadence": s["cadence"], "last_amount": s["last_amount"],
        "last_date": s["last_date"], "first_date": s["first_date"], "next_due": s["next_due_date"],
        "n_charges": s["n_charges"], "min_amount": min(amounts), "max_amount": max(amounts),
        "amount_varies": bool(s["amount_varies"]),
        "duplicates": (s["flag_details_json"] or {}).get("duplicate_charge", []),
        "still_charged": _still_charged(series_id),
    }


def _still_charged(series_id: int) -> dict | None:
    """The charge that arrived after the user cancelled (a STILL_CHARGED reminder), for the refund request."""
    row = db.get_reminder(series_id)
    if not row or row["phase"] != "STILL_CHARGED" or not row["cancelled_on"]:
        return None
    later = db.charges_after(series_id, row["cancelled_on"])["charges_after"]
    if not later:
        return None
    return {"cancelled_on": row["cancelled_on"], "date": later[0]["date"], "amount": later[0]["amount"]}


def _money(f: dict, amount: float) -> str:
    return money(amount, f["currency"])


def _pair_dates(first: str, second: str) -> str:
    """Jul 5 and Jul 6, 2026 — the year once when both share it."""
    if first[:4] == second[:4]:
        return f"{date_short(first)} and {date_long(second)}"
    return f"{date_long(first)} and {date_long(second)}"


def template(kind: Kind, f: dict) -> str:
    m = f["merchant"]
    if kind == "cancel_request":
        plan = "membership" if f["category"] == "Fitness" else "subscription"
        renewal = f", including the renewal due on {date_long(f['next_due'])}" if f["next_due"] else ""
        if f["cadence"] == "single":
            paid = f"I was charged {_money(f, f['last_amount'])} on {date_long(f['last_date'])}."
        else:
            paid = (f"I have been charged {_money(f, f['last_amount'])} {PER.get(f['cadence'], 'each time')}, "
                    f"most recently on {date_long(f['last_date'])}.")
        subject = f"Please cancel my {m} {plan}"
        body = [f"Please cancel my {plan} and stop all future charges{renewal}. {paid}",
                "Please confirm the cancellation by email."]
    elif kind == "refund":
        body = []
        late = f["still_charged"]
        if late:
            subject = f"Refund for {m} charge on {date_long(late['date'])}"
            body.append(f"I cancelled on {date_long(late['cancelled_on'])}, but my card was charged "
                        f"{_money(f, late['amount'])} on {date_long(late['date'])}. Please refund this charge and "
                        "confirm that no further charges will be made.")
        dups = f["duplicates"]
        for i, p in enumerate(dups):
            if not late and i == 0:
                subject = f"Refund for duplicate {m} charge on {date_long(p['second'])}"
            also = "also " if late or i else ""
            body.append(f"I was {also}charged {_money(f, p['amount'])} twice in {MONTH_NAMES[int(p['first'][5:7]) - 1]}, "
                        f"on {_pair_dates(p['first'], p['second'])}. Please refund the "
                        f"{date_short(p['second'])} charge{' too' if also else ''}.")
        if not body:
            subject = f"Refund for {m} charge on {date_long(f['last_date'])}"
            body.append(f"Please refund the {_money(f, f['last_amount'])} charge on {date_long(f['last_date'])}.")
    else:
        since = f"{MONTH_NAMES[int(f['first_date'][5:7]) - 1]} {f['first_date'][:4]}"
        if f["amount_varies"]:
            paid = (f"My bills have ranged from {_money(f, f['min_amount'])} to {_money(f, f['max_amount'])}, "
                    f"most recently {_money(f, f['last_amount'])} on {date_long(f['last_date'])}.")
        else:
            paid = (f"I pay {_money(f, f['last_amount'])} {PER.get(f['cadence'], 'each time')}, most recently "
                    f"on {date_long(f['last_date'])}.")
        history = f"I have been a customer since at least {since}, with {plural(f['n_charges'], 'payment')} so far."
        if f["category"] == "Housing":
            subject = "Request to review my rent"
            ask = ("Before my next renewal, could you let me know whether a lower rate or a discount for a "
                   "longer commitment is possible? I would like to stay if we can agree on a better price.")
        else:
            subject = f"Request for a lower rate on my {m} account"
            ask = ("Could you review my account and let me know whether a lower rate, a discount or a better "
                   "plan is available? I would like to stay with you if we can find a better price.")
        body = [f"{history} {paid}", ask]
    return "\n\n".join([f"Subject: {subject}", f"Hello {m} team,", *body, SIGN_OFF])


FENCE = re.compile(r"^```[a-z]*\n|\n?```$")


def tidy(candidate: str) -> str:
    """Drop a code fence or stray markdown Gemma may wrap the email in."""
    text = FENCE.sub("", candidate.strip()).strip()
    return re.sub(r"^\*\*(Subject:.*?)\*\*", r"\1", text)


def acceptable(candidate: str, reference: str) -> bool:
    if not candidate.startswith("Subject:") or "[Your name]" not in candidate:
        return False
    if guard.find_contacts(candidate):
        return False
    return set(NUMBER.findall(candidate)) <= set(NUMBER.findall(reference))


def _ev(event: str, **data) -> dict:
    return {"event": event, "data": json.dumps(data)}


async def stream(series_id: int, kind: Kind, model: str | None, host: str) -> AsyncIterator[dict]:
    """token… then done {text, source, title}. `done.text` is the final draft (it may replace the tokens)."""
    f = facts(series_id)
    text = template(kind, f)
    if model is None:
        yield _ev("done", text=text, source="template", title=TITLES[kind])
        return
    candidate = ""
    try:
        import ollama

        client = ollama.AsyncClient(host=host, timeout=60.0)
        parts = await client.chat(model=model, stream=True, think=False,
                                  messages=[{"role": "user", "content": PROMPT.format(merchant=f["merchant"],
                                                                                      draft=text)}],
                                  options={"temperature": 0.4, "num_ctx": 4096})
        async for part in parts:
            if part.message.content:
                candidate += part.message.content
                yield _ev("token", text=part.message.content)
    except Exception as exc:  # noqa: BLE001 — Ollama down mid-draft: the template is a complete email
        log.info("draft: Gemma unavailable (%s); using the template", exc)
        yield _ev("done", text=text, source="template", title=TITLES[kind])
        return
    candidate = tidy(candidate)
    if acceptable(candidate, text):
        yield _ev("done", text=candidate, source="gemma", title=TITLES[kind])
    else:
        log.info("draft: Gemma's version changed the facts or the shape; using the template")
        yield _ev("done", text=text, source="template", title=TITLES[kind])
