"""Generate TabPFN's in-context priors (spec §11.2, IMPL M3.2). Deterministic.

Simulates *transaction histories* for 17 archetypes, then describes them with the exact functions the
runtime uses (app.features.series_features / regression_rows), so priors and user data can't drift apart.

Writes:
  app/data/priors_recurring.csv  FEATURES + label (1 recurring, 0 not) + archetype   → recurring classifier
  app/data/priors_hikes.csv      REG_FEATURES + ratio (next / previous amount)       → next-charge regressor
usage: python scripts/make_priors.py [--out DIR]
"""

import argparse
import sys
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ENGINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE))
from app.features import FEATURES, REG_FEATURES, regression_rows, series_features  # noqa: E402
from app.normalize import CATEGORIES  # noqa: E402

SEED = 20261021
SERIES_PER_ARCHETYPE = 40
HIKE_SERIES_PER_ARCHETYPE = 30
NOISE = 0.10  # share of series whose category / subscription hint is wrong, so TabPFN can't rely on the hint
FIRST_DAY, LAST_DAY = date(2023, 1, 1), date(2026, 10, 1)

History = tuple[list[date], list[float]]


def _start(rng: np.random.Generator, span_days: int) -> date:
    latest = (LAST_DAY - FIRST_DAY).days - span_days
    return FIRST_DAY + timedelta(days=int(rng.integers(0, max(latest, 1))))


def _weekend_shift(rng: np.random.Generator, d: date) -> date:
    """Banks often post weekend charges on Monday."""
    if d.weekday() >= 5 and rng.random() < 0.6:
        return d + timedelta(days=7 - d.weekday())
    return d


def _periodic(rng: np.random.Generator, n: int, period: float, jitter: int) -> list[date]:
    start = _start(rng, int(period * n) + 10)
    out = []
    for k in range(n):
        d = start + timedelta(days=round(k * period) + int(rng.integers(-jitter, jitter + 1)))
        out.append(_weekend_shift(rng, d))
    return sorted(out)


def _gaps(rng: np.random.Generator, n: int, lo: int, hi: int) -> list[date]:
    d = _start(rng, hi * n)
    out = []
    for _ in range(n):
        out.append(d)
        d += timedelta(days=int(rng.integers(lo, hi + 1)))
    return out


def _with_hike(rng: np.random.Generator, prices: list[float], period: float, chance_per_year=0.35) -> list[float]:
    """At each charge, a hike happens with the per-period share of a 35 %/year chance (+5–25 %)."""
    p = 1 - (1 - chance_per_year) ** (period / 365.25)
    out, price = [], prices[0]
    for k in range(len(prices)):
        if k and rng.random() < p:
            price = round(price * (1 + rng.uniform(0.05, 0.25)), 2)
        out.append(price)
    return out


# ── archetypes: (label, sub_like, categories, simulate) ─────────────────────

def _subscription_price(rng) -> float:
    """Log-uniform $3.99–$79.99: music and streaming at the bottom, gyms and software at the top."""
    return round(float(np.exp(rng.uniform(np.log(3.99), np.log(79.99)))), 2)


def monthly_fixed(rng) -> History:
    n = int(rng.integers(3, 14))
    return _periodic(rng, n, 30.44, 2), [_subscription_price(rng)] * n


def monthly_price_rise(rng) -> History:
    n = int(rng.integers(4, 14))
    price = _subscription_price(rng)
    step = int(rng.integers(2, n))
    risen = round(price * (1 + rng.uniform(0.05, 0.25)), 2)
    return _periodic(rng, n, 30.44, 2), [price] * step + [risen] * (n - step)


def weekly_meal_kit(rng) -> History:
    n = int(rng.integers(4, 31))
    base = rng.uniform(50, 90)
    return _periodic(rng, n, 7, 1), [round(base * rng.uniform(0.97, 1.03), 2) for _ in range(n)]


def quarterly_plan(rng) -> History:
    n = int(rng.integers(2, 6))
    return _periodic(rng, n, 91.3, 5), [round(float(rng.uniform(20, 300)), 2)] * n


def annual_plan(rng) -> History:
    n = int(rng.integers(2, 4))
    return _periodic(rng, n, 365.25, 7), [round(float(rng.uniform(30, 200)), 2)] * n


def usage_saas(rng) -> History:
    n = int(rng.integers(3, 14))
    base = rng.uniform(10, 120)
    return _periodic(rng, n, 30.44, 2), [round(base * rng.lognormal(0, 0.2), 2) for _ in range(n)]


def phone_plan(rng) -> History:
    n = int(rng.integers(3, 14))
    base = rng.uniform(30, 80)
    return _periodic(rng, n, 30.44, 1), [round(base * rng.uniform(0.98, 1.02), 2) for _ in range(n)]


def insurance(rng) -> History:
    n = int(rng.integers(3, 14))
    return _periodic(rng, n, 30.44, 1), [round(float(rng.uniform(50, 250)), 2)] * n


def utility_bill(rng) -> History:
    n = int(rng.integers(3, 14))
    base = rng.uniform(40, 160)
    season = rng.uniform(0.15, 0.35)
    return (_periodic(rng, n, 30.44, 3),
            [round(base * (1 + season * np.sin(k / 12 * 2 * np.pi)) * rng.uniform(0.9, 1.1), 2) for k in range(n)])


def rent(rng) -> History:
    n = int(rng.integers(3, 14))
    return _periodic(rng, n, 30.44, 1), [round(float(rng.uniform(800, 3000)), -1)] * n


def groceries(rng) -> History:
    n = int(rng.integers(5, 41))
    # Half are "weekly-ish" (the hard negative: a rhythm, but variable amounts and no plan).
    dates = _periodic(rng, n, 7, 2) if rng.random() < 0.5 else _gaps(rng, n, 2, 14)
    return dates, [round(float(rng.uniform(20, 200)), 2) for _ in range(n)]


def coffee(rng) -> History:
    n = int(rng.integers(10, 81))
    return _gaps(rng, n, 1, 6), [round(float(rng.uniform(3, 9)), 2) for _ in range(n)]


def dining(rng) -> History:
    n = int(rng.integers(2, 16))
    return _gaps(rng, n, 3, 30), [round(float(rng.uniform(15, 120)), 2) for _ in range(n)]


def fuel(rng) -> History:
    n = int(rng.integers(3, 21))
    return _gaps(rng, n, 5, 20), [round(float(rng.uniform(30, 80)), 2) for _ in range(n)]


def rides(rng) -> History:
    n = int(rng.integers(2, 25))
    return _gaps(rng, n, 1, 20), [round(float(rng.uniform(8, 40)), 2) for _ in range(n)]


def shopping(rng) -> History:
    n = int(rng.integers(2, 20))
    return _gaps(rng, n, 2, 40), [round(float(rng.uniform(10, 300)), 2) for _ in range(n)]


def travel(rng) -> History:
    n = int(rng.integers(2, 4))
    return _gaps(rng, n, 30, 200), [round(float(rng.uniform(100, 900)), 2) for _ in range(n)]


SUBSCRIPTION_CATS = ["Streaming", "Music", "Software", "Cloud Storage", "News & Media", "Fitness"]
ARCHETYPES: list[tuple[str, int, bool, list[str], Callable]] = [
    ("monthly fixed-price subscription", 1, True, SUBSCRIPTION_CATS, monthly_fixed),
    ("monthly subscription with a price rise", 1, True, SUBSCRIPTION_CATS, monthly_price_rise),
    ("weekly meal kit", 1, True, ["Food Delivery"], weekly_meal_kit),
    ("quarterly plan", 1, True, ["Software", "Insurance", "Education"], quarterly_plan),
    ("annual plan", 1, True, ["Software", "Cloud Storage", "News & Media", "Education"], annual_plan),
    ("usage-based monthly SaaS", 1, True, ["Software", "Cloud Storage"], usage_saas),
    ("phone plan", 1, True, ["Telecom"], phone_plan),
    ("insurance premium", 1, True, ["Insurance"], insurance),
    ("utility bill", 1, False, ["Utilities"], utility_bill),
    ("rent", 1, False, ["Housing"], rent),
    ("grocery runs", 0, False, ["Groceries"], groceries),
    ("coffee", 0, False, ["Dining"], coffee),
    ("dining out", 0, False, ["Dining"], dining),
    ("fuel", 0, False, ["Transport"], fuel),
    ("rides", 0, False, ["Transport"], rides),
    ("marketplace shopping", 0, False, ["Shopping"], shopping),
    ("one-off travel", 0, False, ["Travel"], travel),
]
# Archetypes whose regressor rows teach "prices step up sometimes" (fixed-price plans).
HIKE_ARCHETYPES = {"monthly fixed-price subscription": 30.44, "monthly subscription with a price rise": 30.44,
                   "quarterly plan": 91.3, "annual plan": 365.25, "phone plan": 30.44,
                   "insurance premium": 30.44, "rent": 30.44, "weekly meal kit": 7.0,
                   "usage-based monthly SaaS": 30.44, "utility bill": 30.44}


def _frame(dates: list[date], amounts: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"tx_date": pd.to_datetime(dates), "amount": amounts})


def build_recurring(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for name, label, sub_like, cats, simulate in ARCHETYPES:
        for _ in range(SERIES_PER_ARCHETYPE):
            dates, amounts = simulate(rng)
            category = str(rng.choice(cats))
            hint = sub_like
            if rng.random() < NOISE:
                category = str(rng.choice(CATEGORIES))
            if rng.random() < NOISE:
                hint = not hint
            report_date = pd.Timestamp(max(dates) + timedelta(days=int(rng.integers(0, 31))))
            feats = series_features(_frame(dates, amounts), report_date, category, hint)
            rows.append({**feats, "label": label, "archetype": name})
    return pd.DataFrame(rows, columns=[*FEATURES, "label", "archetype"])


def build_hikes(rng: np.random.Generator) -> pd.DataFrame:
    frames = []
    simulators = {name: (cats, simulate) for name, _, _, cats, simulate in ARCHETYPES}
    for name, period in HIKE_ARCHETYPES.items():
        cats, simulate = simulators[name]
        for _ in range(HIKE_SERIES_PER_ARCHETYPE):
            dates, amounts = simulate(rng)
            if len(set(amounts)) == 1:  # fixed price: apply the yearly hike chance
                amounts = _with_hike(rng, amounts, period)
            if len(amounts) < 2:
                continue
            cadence = series_features(_frame(dates, amounts), pd.Timestamp(max(dates)), "", False)["cadence"]
            frames.append(regression_rows(_frame(dates, amounts), cadence, str(rng.choice(cats))))
    return pd.concat(frames, ignore_index=True)[[*REG_FEATURES, "ratio"]]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ENGINE / "app" / "data")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(SEED)
    recurring = build_recurring(rng)
    hikes = build_hikes(rng)
    recurring.to_csv(args.out / "priors_recurring.csv", index=False, float_format="%.6g", lineterminator="\n")
    hikes.to_csv(args.out / "priors_hikes.csv", index=False, float_format="%.6g", lineterminator="\n")
    print(f"priors_recurring.csv: {len(recurring)} series ({int(recurring.label.sum())} recurring) · "
          f"priors_hikes.csv: {len(hikes)} charge steps ({int((hikes.ratio > 1.02).sum())} price rises)")


if __name__ == "__main__":
    main()
