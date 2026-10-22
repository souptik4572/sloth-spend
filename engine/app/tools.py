"""Ask Sloth's tools (spec §7.9, IMPL M6.1).

Eight typed tools beat free-form SQL for a small model. Every tool returns JSON text (≤ 4,000 chars) and
reports problems as {"error": …} instead of raising, so one bad call never ends a conversation.
`forecast_spend` and `score_merchant` run TabPFN *live* on the current data and labels.
"""

import asyncio
import difflib
import json
import re
import sqlite3
import time
from collections import defaultdict

import pandas as pd

from . import db, reminders, report
from .db import DB_PATH
from .features import FEATURES
from .money import date_long, money
from .tabular import tabular

MAX_OUTPUT = 4000
OVERVIEW_LIMIT = 1200
DUPLICATE_MIN_CADENCE = 25  # same rule as detectors.duplicate_charges: coffee twice a week isn't a double charge
# Flags in the words the UI uses, so answers never show ids like "price_creep".
FLAG_WORDS = {"duplicate_charge": "double charge", "price_creep": "price rise", "overlap": "overlap",
              "possible_annual": "possible annual plan", "zombie_suspect": "zombie suspect"}


def _fn(name: str, description: str, properties: dict | None = None, required: list[str] | None = None) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties or {}, "required": required or []}}}


MERCHANT = {"merchant": {"type": "string", "description": "Merchant name as the user wrote it, e.g. IronTrap"}}

SCHEMAS = [
    _fn("get_report_overview",
        "Summary numbers and the top findings. Use for general questions about the whole statement."),
    _fn("get_merchant",
        "Everything about one merchant: cadence, recent charges, flags, next charge and its forecast. "
        "Use for any question about a specific merchant.", MERCHANT, ["merchant"]),
    _fn("find_duplicate_charges",
        "Pairs of identical charges a few days apart (possible double charges). Leave merchant empty for all.",
        {**MERCHANT, "window_days": {"type": "integer", "description": "Max days between the two charges"}}),
    _fn("spend_by_category",
        "Money out per category and month, with how each category changed. Use for 'which category grew' "
        "or 'how much on X' questions. Both dates are optional (YYYY-MM-DD); leave them out to cover the "
        "whole statement.",
        {"start_date": {"type": "string"}, "end_date": {"type": "string"}}),
    _fn("forecast_spend",
        "Live TabPFN forecast of recurring spend over the next N days, and the change if some merchants are "
        "cancelled. Use for future-spend and 'what if I cancel X' questions.",
        {"days": {"type": "integer", "description": "Window length, default 30"},
         "exclude_merchants": {"type": "array", "items": {"type": "string"},
                               "description": "Merchants to leave out (the what-if)"},
         "scope": {"type": "string", "enum": ["subscriptions", "all"],
                   "description": "subscriptions (default), or all recurring charges including bills"}}),
    _fn("score_merchant",
        "Live TabPFN check of how recurring one merchant's charges look, using the user's corrections, "
        "with the most similar known billing patterns. Use for 'is X a subscription' questions.",
        MERCHANT, ["merchant"]),
    _fn("run_readonly_sql",
        "One read-only SQLite SELECT for questions the other tools can't answer (max 50 rows). Tables: "
        "transactions(tx_date, raw_description, merchant, category, amount, direction 'debit'|'credit', "
        "is_duplicate); series(merchant, category, kind, cadence, last_amount, monthly_equiv, recurring_prob, "
        "next_due_date, flags_json, status); report_meta(report_date, currency, monthly_recurring).",
        {"query": {"type": "string"}}, ["query"]),
    _fn("set_renewal_reminder",
        "Schedule a local reminder before a merchant's next renewal. It only reminds the user; it never "
        "cancels anything.",
        {**MERCHANT, "days_before": {"type": "integer", "description": "Days before the charge, default 3"}},
        ["merchant"]),
]
NAMES = [s["function"]["name"] for s in SCHEMAS]
LIVE_TOOLS = {"forecast_spend", "score_merchant"}


# ── helpers ─────────────────────────────────────────────────────────────────

def _currency() -> str:
    meta = db.report_meta()
    return (meta or {}).get("currency") or "USD"


def _q(q10: float | None, q50: float | None, q90: float | None) -> dict | None:
    return None if q50 is None else {"q10": q10, "q50": q50, "q90": q90}


def resolve(name: str, series: list[dict] | None = None) -> dict | None:
    """Fuzzy merchant lookup: exact, then containment, then difflib over names and their first words."""
    series = db.list_series() if series is None else series
    q = " ".join(str(name).lower().split())
    if not q:
        return None
    by_name = {s["merchant"].lower(): s for s in series}
    if q in by_name:
        return by_name[q]
    rank = lambda s: -(s["priority"] or 0)  # noqa: E731 — prefer the merchant that matters most
    contains = [s for s in series if q in s["merchant"].lower() or s["merchant"].lower() in q]
    if contains:
        return sorted(contains, key=rank)[0]
    firsts: dict[str, dict] = {}
    for s in sorted(series, key=rank, reverse=True):  # best-ranked wins a shared first word
        firsts[s["merchant"].split()[0].lower()] = s
    match = difflib.get_close_matches(q, [*by_name, *firsts], n=1, cutoff=0.5)
    if not match:
        return None
    return by_name.get(match[0]) or firsts[match[0]]


def _words(flags: list[str] | None) -> list[str]:
    return [FLAG_WORDS.get(f, f) for f in flags or []]


def _not_found(name: str) -> dict:
    names = [s["merchant"] for s in sorted(db.list_series(), key=lambda s: -(s["priority"] or 0))][:12]
    return {"error": f"No merchant called {name!r} in the report.", "known_merchants": names}


# ── the tools ───────────────────────────────────────────────────────────────

def get_report_overview() -> dict:
    rep = report.load_report()
    if rep is None:
        return {"error": "There is no report yet. Load a statement first."}
    m, cur = rep["meta"], rep["meta"]["currency"]
    top = [{"merchant": s["merchant"], "category": s["category"], "cadence": s["cadence"],
            "last_amount": s["last_amount"], "flags": _words(s["flags"]), "next_due": s["next_due_date"],
            "status": s["status"]} for s in rep["series"][:10]]
    return {"currency": cur, "report_date": m["report_date"], "monthly_recurring": m["monthly_recurring"],
            "monthly_subscriptions": m["monthly_subscriptions"], "monthly_bills": m["monthly_bills"],
            "next_30_days": m["fc30"], "potential_monthly_savings": m["potential_savings"],
            "zombie_suspects": m["zombie_count"], "double_charges_to_dispute": m["dispute_total"],
            "flag_counts": m["flag_counts"], "top_findings": top}


def get_merchant(merchant: str) -> dict:
    s = resolve(merchant)
    if s is None:
        txs = _one_off_charges(merchant)
        return txs if txs else _not_found(merchant)
    txs = db.merchant_transactions(s["merchant"])
    return {
        "merchant": s["merchant"], "currency": _currency(), "category": s["category"], "kind": s["kind"],
        "status": s["status"], "cadence": s["cadence"], "billed_every_days": s["cadence_days"],
        "usual_day_of_month": s["dom_median"], "n_charges": s["n_charges"], "first_charge": s["first_date"],
        "last_charge": s["last_date"], "last_amount": s["last_amount"], "monthly_equiv": s["monthly_equiv"],
        "recurring_prob": s["recurring_prob"], "scorer": s["scorer"], "next_due": s["next_due_date"],
        "next_charge_forecast": _q(s["fc_q10"], s["fc_q50"], s["fc_q90"]),
        "price_rise_chance": None if s["hike_prob"] is None else round(s["hike_prob"], 2),
        "flags": _words(s["flags_json"]),
        "flag_details": {FLAG_WORDS.get(k, k): v for k, v in (s["flag_details_json"] or {}).items()},
        "recent_charges": [{"date": t["tx_date"], "amount": t["amount"], "duplicate": bool(t["is_duplicate"])}
                           for t in txs[-12:]],
    }


def _one_off_charges(name: str) -> dict | None:
    """A merchant that isn't a series (charged irregularly): just its charges."""
    with db.connect() as conn:
        names = [r[0] for r in conn.execute("SELECT DISTINCT merchant FROM transactions WHERE merchant IS NOT NULL")]
    lower = {n.lower(): n for n in names}
    q = name.lower().strip()
    hit = lower.get(q) or next((n for k, n in lower.items() if q and q in k), None)
    if hit is None:
        close = difflib.get_close_matches(q, list(lower), n=1, cutoff=0.75)
        hit = lower[close[0]] if close else None
    if hit is None:
        return None
    txs = db.merchant_transactions(hit)
    return {"merchant": hit, "currency": _currency(), "recurring": False, "n_charges": len(txs),
            "total": round(sum(t["amount"] for t in txs), 2),
            "charges": [{"date": t["tx_date"], "amount": t["amount"]} for t in txs[-12:]]}


def find_duplicate_charges(merchant: str | None = None, window_days: int = 3) -> dict:
    window = max(1, min(int(window_days), 10))
    series = db.list_series()
    if merchant:
        s = resolve(merchant, series)
        if s is None:
            return _not_found(merchant)
        series = [s]
    pairs = []
    for s in series:
        if not s["cadence_days"] or s["cadence_days"] < DUPLICATE_MIN_CADENCE:
            continue
        txs = db.merchant_transactions(s["merchant"])
        for a, b in zip(txs, txs[1:]):
            gap = (pd.Timestamp(b["tx_date"]) - pd.Timestamp(a["tx_date"])).days
            if gap <= window and abs(a["amount"] - b["amount"]) <= 0.01 * max(a["amount"], b["amount"]):
                pairs.append({"merchant": s["merchant"], "first": a["tx_date"], "second": b["tx_date"],
                              "amount": round(b["amount"], 2), "tx_ids": [a["id"], b["id"]]})
    return {"currency": _currency(), "window_days": window, "pairs": pairs,
            "total_to_dispute": round(sum(p["amount"] for p in pairs), 2)}


def spend_by_category(start_date: str | None = None, end_date: str | None = None) -> dict:
    with db.connect() as conn:
        bounds = conn.execute("SELECT MIN(tx_date), MAX(tx_date) FROM transactions WHERE direction = 'debit'"
                              ).fetchone()
    if not bounds[0]:
        return {"error": "There are no transactions yet."}
    start = _iso(start_date) or bounds[0]
    end = _iso(end_date) or bounds[1]
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT COALESCE(category, 'Other') AS category, substr(tx_date, 1, 7) AS month, "
            "ROUND(SUM(amount), 2) AS total FROM transactions WHERE direction = 'debit' "
            "AND tx_date BETWEEN ? AND ? GROUP BY 1, 2 ORDER BY 1, 2", (start, end)).fetchall()
    months = sorted({r["month"] for r in rows})
    # The statement's last month is usually partial: leave it out of the trend.
    last_day = pd.Timestamp(min(end, bounds[1]))
    full = [m for m in months if not (m == months[-1] and last_day != last_day + pd.offsets.MonthEnd(0))]
    by_cat: dict[str, dict[str, float]] = defaultdict(dict)
    for r in rows:
        by_cat[r["category"]][r["month"]] = r["total"]
    cats = []
    for cat, per_month in by_cat.items():
        entry = {"category": cat, "total": round(sum(per_month.values()), 2), "by_month": per_month}
        if len(full) >= 6:
            first = sum(per_month.get(m, 0.0) for m in full[:3]) / 3
            last = sum(per_month.get(m, 0.0) for m in full[-3:]) / 3
            entry.update(first_3_months_avg=round(first, 2), last_3_months_avg=round(last, 2),
                         change_per_month=round(last - first, 2))
        cats.append(entry)
    cats.sort(key=lambda c: -c["total"])
    out = {"currency": _currency(), "period": [start, end], "categories": cats}
    growing = [c for c in cats if "change_per_month" in c]
    if growing:
        top = max(growing, key=lambda c: c["change_per_month"])
        out["grew_most"] = {"category": top["category"], "change_per_month": top["change_per_month"],
                            "compared": f"{full[0]}..{full[2]} vs {full[-3]}..{full[-1]}"}
    return out


def _iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return pd.Timestamp(str(value)).date().isoformat()
    except (ValueError, TypeError):
        return None


def forecast_spend(days: int = 30, exclude_merchants: list[str] | None = None, scope: str = "subscriptions") -> dict:
    """One scope per call, so a small model can't quote bills when asked about subscriptions."""
    days = max(1, min(int(days), 365))
    scope = "all" if scope == "all" else "subscriptions"
    live = report.live_forecast(days)
    if live is None:
        return {"error": "There is no report yet. Load a statement first."}
    series = db.list_series()
    excluded, not_found = [], []
    for name in exclude_merchants or []:
        s = resolve(name, series)
        if s:
            excluded.append(s["merchant"])
        else:
            not_found.append(name)

    def total(rows: list[dict]) -> dict:
        return {k: round(sum(r[k] for r in rows), 2) for k in ("q10", "q50", "q90")}

    rows = [r for r in live["series"] if scope == "all" or r["kind"] == "subscription"]
    baseline, scenario = total(rows), total([r for r in rows if r["merchant"] not in excluded])
    out = {
        "scope": "all recurring charges, bills included" if scope == "all" else "subscriptions only",
        "currency": live["currency"], "window": [live["report_date"], live["window_end"]],
        "model": live["scorer"], "excluded": excluded,
        "baseline": baseline, "scenario": scenario, "delta_q50": round(scenario["q50"] - baseline["q50"], 2),
        "how_to_read": "baseline = as now, scenario = without the excluded merchants; q50 is most likely, "
                       "q10–q90 the range.",
        "due_in_window": [{k: r[k] for k in ("merchant", "next_due", "charges", "q50")} for r in rows if r["charges"]],
    }
    if not_found:
        out["not_found"] = not_found
    return out


def score_merchant(merchant: str) -> dict:
    s = resolve(merchant)
    if s is None:
        return _not_found(merchant)
    feats = s["features_json"]
    if not feats:
        return {"merchant": s["merchant"], "error": "Charged only once, so there is no pattern to score yet."}
    X = pd.DataFrame([feats])[FEATURES]
    labels = db.user_labels()
    prob = float(tabular.recurring_prob(X, pd.DataFrame(labels) if labels else None)[0])
    similar = tabular.nearest_archetypes(X)[0]
    label = next((lab["label"] for lab in labels if lab["merchant"] == s["merchant"]), None)
    keep = ("n_charges", "median_interval", "interval_cv", "cadence", "cadence_fit", "amount_cv",
            "days_since_last", "category", "subscription_like")
    return {"merchant": s["merchant"], "recurring_prob": round(prob, 3), "model": tabular.scorer,
            "your_label": None if label is None else ("subscription" if label else "not a subscription"),
            "status": s["status"], "features": {k: feats.get(k) for k in keep}, "looks_like": similar}


def run_readonly_sql(query: str) -> dict:
    """Verbatim from spec §7.9: one SELECT/WITH, read-only connection, 50-row cap, 2 s budget."""
    q = query.strip().rstrip(";")
    if ";" in q or not re.match(r"(?is)^\s*(select|with)\b", q):
        return {"error": "Only a single SELECT or WITH statement is allowed."}
    conn = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = ON")
    deadline = time.monotonic() + 2.0
    conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    try:
        cur = conn.execute(f"SELECT * FROM ({q}) LIMIT 50")  # noqa: S608 — read-only, single statement
        cols = [d[0] for d in cur.description]
        return {"columns": cols, "rows": cur.fetchall()}
    except sqlite3.Error as exc:
        return {"error": str(exc)}
    finally:
        conn.close()


def set_renewal_reminder(merchant: str, days_before: int = 3) -> dict:
    s = resolve(merchant)
    if s is None:
        return _not_found(merchant)
    base = {"merchant": s["merchant"], "next_charge_due": s["next_due_date"]}
    try:
        row = reminders.create(s["id"], max(1, min(int(days_before), 14)))
    except reminders.NoRenewal:
        return {**base, "reminder_set": False,
                "error": f"No reminder was set: SlothSpend can't predict when {s['merchant']} renews."}
    except reminders.Conflict as exc:
        return {**base, "reminder_set": False, "phase": exc.phase,
                "error": f"No new reminder was set: {s['merchant']} already has one in progress "
                         f"({str(exc.phase).replace('_', ' ').lower()}). See the Reminders tab."}
    return {**base, "reminder_set": True, "days_before": row["days_before"],
            "remind_on": row["remind_at"][:10] if row["remind_at"] else None,
            "note": "It only reminds you, here on this computer. Nothing is cancelled."}


TOOLS = {"get_report_overview": get_report_overview, "get_merchant": get_merchant,
         "find_duplicate_charges": find_duplicate_charges, "spend_by_category": spend_by_category,
         "forecast_spend": forecast_spend, "score_merchant": score_merchant,
         "run_readonly_sql": run_readonly_sql, "set_renewal_reminder": set_renewal_reminder}


# ── calling them ────────────────────────────────────────────────────────────

def _clean_args(name: str, args: dict) -> dict:
    """Keep the declared arguments and coerce what a small model gets slightly wrong ("30", "A, B")."""
    declared = next(s["function"]["parameters"] for s in SCHEMAS if s["function"]["name"] == name)
    out = {}
    for key, spec in declared["properties"].items():
        if key not in args or args[key] in (None, ""):
            continue
        value = args[key]
        if spec["type"] == "integer":
            value = int(float(value))
        elif spec["type"] == "array":
            value = [v.strip() for v in value.split(",")] if isinstance(value, str) else [str(v) for v in value]
        else:
            value = str(value)
        out[key] = value
    missing = [k for k in declared["required"] if k not in out]
    if missing:
        raise ValueError(f"Missing argument: {', '.join(missing)}.")
    return out


ISO_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _human(value):
    """ISO dates → "Jul 6, 2026" everywhere in a result, so answers use the dates the UI shows."""
    if isinstance(value, str) and ISO_DAY.match(value):
        return date_long(value)
    if isinstance(value, dict):
        return {k: _human(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_human(v) for v in value]
    return value


def _dump(result: dict) -> str:
    """JSON ≤ MAX_OUTPUT chars that still parses: the longest list is shortened until it fits."""
    text = json.dumps(result, default=str, ensure_ascii=False)
    while len(text) > MAX_OUTPUT:
        lists = [(k, v) for k, v in result.items() if isinstance(v, list) and len(v) > 1]
        if not lists:
            return text[:MAX_OUTPUT - 15] + " …(truncated)"
        key, longest = max(lists, key=lambda kv: len(json.dumps(kv[1], default=str)))
        result = {**result, key: longest[:len(longest) // 2], "truncated": True}
        text = json.dumps(result, default=str, ensure_ascii=False)
    return text


async def execute(name: str, args: dict | None) -> str:
    if name not in TOOLS:
        return _dump({"error": f"Unknown tool {name!r}. Available: {', '.join(NAMES)}."})
    try:
        clean = _clean_args(name, dict(args or {}))
        return _dump(_human(await asyncio.to_thread(TOOLS[name], **clean)))
    except Exception as exc:  # noqa: BLE001 — the model gets the error and can try again
        return _dump({"error": str(exc) or exc.__class__.__name__})


# ── context for the model ───────────────────────────────────────────────────

def _period(imports: list[dict]) -> str:
    starts = [i["period_start"] for i in imports if i.get("period_start")]
    ends = [i["period_end"] for i in imports if i.get("period_end")]
    return f"{date_long(min(starts))} – {date_long(max(ends))}" if starts and ends else "loaded"


def overview_block() -> str:
    """≤ 1,200 chars the agent always sees: currency, report date, the four cards, the top findings."""
    rep = report.load_report()
    if rep is None:
        return "No statement has been audited yet."
    m, cur = rep["meta"], rep["meta"]["currency"]
    fc = m["fc30"]
    lines = [
        f"Report in {cur}, statements {_period(m['imports'])} (report date {date_long(m['report_date'])}).",
        f"Monthly recurring {money(m['monthly_recurring'], cur)} ({money(m['monthly_subscriptions'], cur)} "
        f"subscriptions, {money(m['monthly_bills'], cur)} bills). Next 30 days likely {money(fc['q50'], cur)} "
        f"({money(fc['q10'], cur)}–{money(fc['q90'], cur)}). Potential monthly savings "
        f"{money(m['potential_savings'], cur)}; double charges to dispute {money(m['dispute_total'], cur)}.",
        "Top findings (merchant · category · cadence · last amount · flags · next due):",
    ]
    for s in rep["series"][:10]:
        flags = ", ".join(_words(s["flags"])) or "none"
        due = date_long(s["next_due_date"]) if s["next_due_date"] else "—"
        status = "" if s["status"] == "active" else f" · marked {s['status'].replace('_', ' ')}"
        line = (f"- {s['merchant']} · {s['category']} · {s['cadence']} · {money(s['last_amount'], cur)} · "
                f"{flags} · {due}{status}")
        if sum(len(x) + 1 for x in lines) + len(line) > OVERVIEW_LIMIT:
            break
        lines.append(line)
    return "\n".join(lines)


def mentioned_merchants(text: str, series: list[dict] | None = None, limit: int = 3) -> list[dict]:
    """Merchants named in a message: full names, distinctive first words, or near-misses ("Irontrap")."""
    series = db.list_series() if series is None else series
    lower = text.lower()
    words = re.findall(r"[a-z][a-z0-9&'-]{3,}", lower)
    found: list[dict] = []
    for s in sorted(series, key=lambda s: -(s["priority"] or 0)):
        name = s["merchant"].lower()
        first = name.split()[0]
        hit = name in lower or (len(first) >= 4 and re.search(rf"\b{re.escape(first)}\b", lower))
        if not hit and len(first) >= 5:
            hit = bool(difflib.get_close_matches(first, words, n=1, cutoff=0.85))
        if hit:
            found.append(s)
        if len(found) == limit:
            break
    return found
