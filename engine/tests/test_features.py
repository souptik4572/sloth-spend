"""Series features (spec §13.1): cadence detection, duplicates excluded, regression rows."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.features import (FEATURES, REG_FEATURES, next_step_row, regression_rows, series_extras,
                          series_features)

REPORT = pd.Timestamp("2026-10-15")


def frame(dates: list[date], amounts: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"tx_date": [d.isoformat() for d in dates], "amount": amounts})


def every(days: int, n: int, start=date(2026, 1, 3)) -> list[date]:
    return [start + timedelta(days=days * k) for k in range(n)]


def months(n: int, day: int = 5) -> list[date]:
    return [date(2025 + (m + 10) // 12, (m + 10) % 12 + 1, day) for m in range(n)]


@pytest.mark.parametrize(("dates", "cadence"), [
    (every(7, 10), "weekly"),
    (every(14, 6), "biweekly"),
    (months(12), "monthly"),
    (every(91, 4), "quarterly"),
    ([date(2024, 3, 1), date(2025, 3, 2), date(2026, 3, 1)], "annual"),
    ([date(2026, 1, d) for d in (1, 2, 9, 11, 26, 29)], "irregular"),
])
def test_cadence_detection(dates, cadence):
    f = series_features(frame(dates, [9.99] * len(dates)), REPORT, "Streaming", True)
    assert f["cadence"] == cadence
    assert set(f) == set(FEATURES)


def test_fixed_price_monthly_features():
    f = series_features(frame(months(12), [15.49] * 12), REPORT, "Streaming", True)
    assert f["cadence_fit"] == 1.0 and f["amount_cv"] == pytest.approx(0, abs=1e-12)
    assert f["modal_amount_share"] == 1.0
    assert f["n_charges"] == 12 and f["subscription_like"] == 1


def test_duplicates_are_excluded_by_the_caller():
    """The pipeline drops the duplicate before features, so a double charge doesn't look like a 1-day cadence."""
    d = months(6)
    with_dup = frame([*d, d[3] + timedelta(days=1)], [49.99] * 7).sort_values("tx_date")
    f_dup = series_features(with_dup, REPORT, "Fitness", True)
    f_clean = series_features(frame(d, [49.99] * 6), REPORT, "Fitness", True)
    assert f_dup["cadence_fit"] < f_clean["cadence_fit"] == 1.0


def test_series_extras():
    g_all = frame([date(2026, 7, 5), date(2026, 7, 6), date(2026, 8, 5)], [49.99, 49.99, 49.99])
    g = g_all.drop(index=1)
    extras = series_extras(g_all, g, amount_cv=0.0)
    assert extras == {"dom_median": 5.0, "amount_varies": False,
                      "monthly_hist": {"2026-07": 99.98, "2026-08": 49.99}}


def test_regression_rows_and_next_step():
    g = frame(months(5), [10.99, 10.99, 11.99, 11.99, 11.99])
    rows = regression_rows(g, "monthly", "Music")
    assert list(rows.columns) == [*REG_FEATURES, "ratio"] and len(rows) == 4
    assert rows["ratio"].round(4).tolist() == [1.0, round(11.99 / 10.99, 4), 1.0, 1.0]
    assert np.isnan(rows["prev2_amount_log"].iloc[0])
    assert rows["n_changes_so_far"].tolist() == [0, 0, 1, 1]
    q = next_step_row(g, "monthly", "Music", next_month=4)
    assert q["tenure_charges"] == 5 and q["charges_since_change"] == 3 and q["month_of_year"] == 4
