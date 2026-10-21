"""Per-merchant series features (spec §7.5) and next-charge regression rows (spec §7.6, Model B).

Both the runtime pipeline and scripts/make_priors.py call these exact functions, so the simulated
priors TabPFN learns from and the user's real series are described identically (no train/serve skew).
"""

import numpy as np
import pandas as pd

CADENCES = {  # label: (period_days, tolerance_days)
    "weekly": (7.0, 2),
    "biweekly": (14.0, 3),
    "monthly": (30.44, 4),
    "quarterly": (91.3, 8),
    "annual": (365.25, 15),
}

FEATURES = ["n_charges", "span_days", "median_interval", "interval_cv", "cadence", "cadence_fit",
            "dom_std", "amount_cv", "modal_amount_share", "log_amount", "days_since_last",
            "category", "subscription_like"]

REG_FEATURES = ["prev_amount_log", "prev2_amount_log", "charges_since_change", "n_changes_so_far",
                "tenure_charges", "cadence", "category", "month_of_year"]

PRICE_CHANGE_TOLERANCE = 0.01  # amounts within 1 % count as the same price


def series_features(g: pd.DataFrame, report_date: pd.Timestamp, category: str, sub_hint: bool) -> dict:
    g = g.sort_values("tx_date")
    dates = pd.to_datetime(g["tx_date"])
    amounts = g["amount"].to_numpy(float)
    iv = dates.diff().dt.days.dropna().to_numpy(float)

    best_label, best_fit = "irregular", 0.0
    if len(iv):
        for label, (period, tol) in CADENCES.items():
            fit = float(np.mean(np.abs(iv - period) <= tol))
            if fit > best_fit:
                best_label, best_fit = label, fit
    if best_fit < 0.5:
        best_label = "irregular"

    med = float(np.median(amounts))
    mode_amount = float(pd.Series(amounts).round(2).mode().iloc[0])
    mean_iv = float(np.mean(iv)) if len(iv) else np.nan
    return {
        "n_charges": int(len(amounts)),
        "span_days": int((dates.iloc[-1] - dates.iloc[0]).days),
        "median_interval": float(np.median(iv)) if len(iv) else np.nan,
        "interval_cv": float(np.std(iv) / mean_iv) if len(iv) > 1 and mean_iv > 0 else np.nan,
        "cadence": best_label,
        "cadence_fit": best_fit,
        "dom_std": float(dates.dt.day.std(ddof=0)),
        "amount_cv": float(np.std(amounts) / med) if med > 0 else 0.0,
        "modal_amount_share": float(np.mean(np.abs(amounts - mode_amount) <= 0.01 * max(med, 1.0))),
        "log_amount": float(np.log1p(med)),
        "days_since_last": int((report_date - dates.iloc[-1]).days),
        "category": category,
        "subscription_like": int(sub_hint),
    }


def _changed(a: float, b: float) -> bool:
    return abs(a - b) > PRICE_CHANGE_TOLERANCE * max(a, b)


def _step_row(amounts: np.ndarray, dates: pd.Series, k: int, cadence: str, category: str) -> dict:
    """Regression features describing the history *before* charge k (0-based, k ≥ 1)."""
    prior = amounts[:k]
    changes = [i for i in range(1, k) if _changed(prior[i], prior[i - 1])]
    last_change = changes[-1] if changes else 0
    return {
        "prev_amount_log": float(np.log1p(prior[-1])),
        "prev2_amount_log": float(np.log1p(prior[-2])) if k >= 2 else np.nan,
        "charges_since_change": int(k - last_change),
        "n_changes_so_far": len(changes),
        "tenure_charges": int(k),
        "cadence": cadence,
        "category": category,
        "month_of_year": int(dates.iloc[k].month) if k < len(dates) else np.nan,
    }


def regression_rows(g: pd.DataFrame, cadence: str, category: str) -> pd.DataFrame:
    """One row per charge k ≥ 2 (1-indexed) with target ratio = amount_k / amount_{k-1}."""
    g = g.sort_values("tx_date")
    amounts = g["amount"].to_numpy(float)
    dates = pd.to_datetime(g["tx_date"]).reset_index(drop=True)
    rows = []
    for k in range(1, len(amounts)):
        row = _step_row(amounts, dates, k, cadence, category)
        row["ratio"] = float(amounts[k] / amounts[k - 1]) if amounts[k - 1] > 0 else 1.0
        rows.append(row)
    return pd.DataFrame(rows, columns=[*REG_FEATURES, "ratio"])


def next_step_row(g: pd.DataFrame, cadence: str, category: str, next_month: int) -> dict:
    """The query row for a series' *next* (not yet seen) charge."""
    g = g.sort_values("tx_date")
    amounts = g["amount"].to_numpy(float)
    dates = pd.to_datetime(g["tx_date"]).reset_index(drop=True)
    row = _step_row(amounts, dates, len(amounts), cadence, category)
    row["month_of_year"] = int(next_month)
    return row
