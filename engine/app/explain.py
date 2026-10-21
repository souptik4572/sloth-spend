"""Plain-language reasons for the merchant drawer (IMPL M4.5), e.g.
"Billed every ~30 days, ±1 day, near the 5th of the month."
"The same $39.99 eight times in a row, then $49.99 for the last four."
"""

import numpy as np
import pandas as pd

from .money import date_long, money, number_word, ordinal

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _runs(amounts: list[float]) -> list[tuple[float, int]]:
    """Consecutive runs of the same price (within 1 %): [(price, count), …]."""
    runs: list[tuple[float, int]] = []
    for a in amounts:
        if runs and abs(a - runs[-1][0]) <= 0.01 * max(a, runs[-1][0]):
            runs[-1] = (runs[-1][0], runs[-1][1] + 1)
        else:
            runs.append((a, 1))
    return runs


def rhythm(s: dict, dates: pd.Series) -> str:
    if s["cadence"] == "single":
        return f"Charged once, on {date_long(s['last_date'])}. Could be an annual plan."
    iv = dates.sort_values().diff().dt.days.dropna().to_numpy(float)
    if not len(iv):
        return f"Charged on {date_long(s['last_date'])}."
    median = float(np.median(iv))
    spread = max(1, round(float(np.median(np.abs(iv - median)))))
    days = round(median)
    if s["cadence"] == "irregular":
        return f"No steady rhythm: gaps range from {int(iv.min())} to {int(iv.max())} days."
    if s["cadence"] in ("weekly", "biweekly"):
        weekday = WEEKDAYS[int(pd.Series(dates.dt.weekday).mode().iloc[0])]
        return f"Billed every ~{days} days, usually on {weekday}."
    if s["cadence"] == "monthly" and s.get("dom_median"):
        return (f"Billed every ~{days} days, ±{spread} day{'s' if spread != 1 else ''}, "
                f"near the {ordinal(round(s['dom_median']))} of the month.")
    return f"Billed every ~{days} days."


def amounts_line(amounts: list[float], currency: str, varies: bool) -> str:
    if len(amounts) == 1:
        return f"{money(amounts[0], currency)} that time."
    runs = _runs(amounts)
    if len(runs) == 1:
        return f"The same {money(runs[0][0], currency)} every time ({len(amounts)} of {len(amounts)})."
    if varies and len(runs) > 3:
        return f"Amounts vary from {money(min(amounts), currency)} to {money(max(amounts), currency)}."
    if len(runs) == 2:
        (a, n), (b, m) = runs
        last = "the last one" if m == 1 else f"the last {number_word(m)}"
        times = "once" if n == 1 else f"{number_word(n)} times in a row"
        return f"The same {money(a, currency)} {times}, then {money(b, currency)} for {last}."
    return f"The price changed {number_word(len(runs) - 1)} times; it’s {money(runs[-1][0], currency)} now."


def source_line(source: str, subscription_like: bool, category: str) -> str:
    if source == "user":
        return "You set this merchant’s name and category."
    if source == "llm":
        if subscription_like:
            return "Gemma tagged it as a kind of merchant that usually bills a plan."
        return f"Gemma tagged it as {category}, not a usual subscription."
    return "Name and category come from a simple rule, because Gemma wasn’t available."


LABEL_LINES = {"keep": "You marked this as Keep.",
               "not_subscription": "You marked this as not a subscription.",
               "user_cancelled": "You told SlothSpend you cancelled it."}


def reasons(s: dict, txs: list[dict], *, source: str, subscription_like: bool, currency: str) -> list[str]:
    """Lines for the drawer's Charges section. `txs` are the merchant's debits incl. duplicates."""
    kept = [t for t in txs if not t["is_duplicate"]] or txs
    dates = pd.to_datetime(pd.Series([t["tx_date"] for t in kept]))
    out = [rhythm(s, dates), amounts_line([t["amount"] for t in kept], currency, bool(s.get("amount_varies"))),
           source_line(source, subscription_like, s["category"])]
    if s.get("status") in LABEL_LINES:
        out.append(LABEL_LINES[s["status"]])
    return out
