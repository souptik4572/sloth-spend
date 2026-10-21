"""Deterministic, explainable detectors (spec §7.7, IMPL M4.4). Duplicates run before feature extraction."""

import numpy as np
import pandas as pd

# Where the UI offers "How to cancel" and "Remind me" (spec §7.7).
CANCELLABLE = {"Streaming", "Music", "Software", "Cloud Storage", "Fitness", "News & Media", "Education",
               "Food Delivery"}
# Bills get "Draft negotiation email" instead.
BILLS = {"Utilities", "Telecom", "Insurance", "Housing"}
OVERLAP_CATEGORIES = {"Streaming", "Music", "Cloud Storage", "Fitness", "News & Media", "Software"}
RECURRING = 0.7  # recurring_prob threshold
ZOMBIE_MIN_CHARGES = 6
ANNUAL_MIN_AMOUNT = 20.0


def kind_of(category: str) -> str:
    return "subscription" if category in CANCELLABLE else "bill" if category in BILLS else "other"


def raw_cadence_days(g: pd.DataFrame) -> float:
    """Median gap before de-duplication — what the duplicate rule needs (IMPL M4.4)."""
    iv = pd.to_datetime(g["tx_date"]).sort_values().diff().dt.days.dropna()
    return float(iv.median()) if len(iv) else 0.0


def duplicate_charges(g: pd.DataFrame, cadence_days: float) -> list[dict]:
    if not cadence_days or cadence_days < 25:
        return []
    g = g.sort_values("tx_date")
    rows = list(zip(pd.to_datetime(g["tx_date"]), g["amount"].astype(float), g["id"]))
    found = []
    for (d1, a1, i1), (d2, a2, i2) in zip(rows, rows[1:]):
        if (d2 - d1).days <= 3 and abs(a2 - a1) <= 0.01 * max(a1, a2):
            found.append({"first": d1.date().isoformat(), "second": d2.date().isoformat(),
                          "amount": round(a2, 2), "tx_ids": [int(i1), int(i2)]})
    return found


def price_creep(g: pd.DataFrame, cadence_fit: float) -> dict | None:
    if cadence_fit < 0.6:
        return None
    g = g.sort_values("tx_date")
    a = g["amount"].to_numpy(float)
    dates = pd.to_datetime(g["tx_date"]).dt.date.to_numpy()
    if len(a) < 3:
        return None
    last = a[-1]
    k = len(a) - 1
    while k > 0 and abs(a[k - 1] - last) <= 0.01 * last:
        k -= 1
    if k == 0:
        return None
    before = a[max(0, k - 3):k]
    baseline = float(np.median(before))
    if baseline <= 0 or (len(before) > 1 and np.std(before) / baseline > 0.05):
        return None
    change = (last - baseline) / baseline
    if change >= 0.05 and (last - baseline) >= 0.5:
        return {"from": round(baseline, 2), "to": round(float(last), 2),
                "pct": round(change * 100, 1), "since": dates[k].isoformat()}
    return None


def overlaps(series: list[dict]) -> dict[str, dict]:
    """merchant → {category, merchants} for ≥ 2 active recurring series in the same overlap category."""
    by_cat: dict[str, list[str]] = {}
    for s in series:
        if s["recurring"] and s["status"] == "active" and s["category"] in OVERLAP_CATEGORIES:
            by_cat.setdefault(s["category"], []).append(s["merchant"])
    out = {}
    for category, merchants in by_cat.items():
        if len(merchants) >= 2:
            for m in merchants:
                out[m] = {"category": category, "merchants": sorted(merchants)}
    return out


def possible_annual(amount: float, category: str, subscription_like: bool) -> bool:
    return subscription_like and amount >= ANNUAL_MIN_AMOUNT and category in CANCELLABLE


def zombie_reasons(s: dict) -> list[str] | None:
    """A cancellable recurring charge worth a second look. Bank data can't see usage, so it's a suspect."""
    if not (s["recurring"] and s["category"] in CANCELLABLE and s["status"] == "active"):
        return None
    because = [f for f in ("overlap", "price_creep", "duplicate_charge") if f in s["flags"]]
    if s["n_charges"] >= ZOMBIE_MIN_CHARGES:
        because.append("long_running")
    return because or None


def priority(monthly_equiv: float, flags: list[str]) -> float:
    return round(monthly_equiv * (1 + 0.5 * ("overlap" in flags) + 0.5 * ("price_creep" in flags)
                                  + 1.0 * ("duplicate_charge" in flags)), 4)
