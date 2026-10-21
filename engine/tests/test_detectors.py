"""Detectors (spec §13.1) on the real sample statement: IronTrap creep + duplicate, TuneTide creep, Metro not
flagged, FreshCart not recurring under the heuristic scorer."""

import json

import pandas as pd
import pytest
from conftest import DATA, FIXTURES

from app import detectors
from app.features import series_features
from app.normalize import desc_key
from app.tabular import heuristic_prob

REPORT = pd.Timestamp("2026-10-15")


@pytest.fixture(scope="module")
def debits() -> pd.DataFrame:
    df = pd.read_csv(DATA / "sample_bank_12m.csv", dtype=str)
    df["tx_date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y", errors="coerce")
    df = df.dropna(subset=["tx_date"]).reset_index(drop=True)
    df["amount"] = df["Amount"].astype(float)
    df = df[df["amount"] < 0].copy()
    df["amount"] = -df["amount"]
    df["tx_date"] = df["tx_date"].dt.date.astype(str)
    df["id"] = range(len(df))
    mapping = json.loads((FIXTURES / "sample_merchant_map.json").read_text())
    df["merchant"] = df["Description"].map(lambda d: mapping[desc_key(d)]["merchant"])
    return df


def series(debits, name):
    return debits[debits["merchant"] == name].sort_values("tx_date")


def dedup(g):
    dups = detectors.duplicate_charges(g, detectors.raw_cadence_days(g))
    second = {p["tx_ids"][1] for p in dups}
    return g[~g["id"].isin(second)], dups


def test_irontrap_duplicate_and_creep(debits):
    g, dups = dedup(series(debits, "IronTrap Fitness"))
    assert [(d["first"], d["second"], d["amount"]) for d in dups] == [("2026-07-05", "2026-07-06", 49.99)]
    fit = series_features(g, REPORT, "Fitness", True)["cadence_fit"]
    assert detectors.price_creep(g, fit) == {"from": 39.99, "to": 49.99, "pct": 25.0, "since": "2026-07-05"}


def test_tunetide_creep(debits):
    g, dups = dedup(series(debits, "TuneTide"))
    assert dups == []
    fit = series_features(g, REPORT, "Music", True)["cadence_fit"]
    assert detectors.price_creep(g, fit)["pct"] == 9.1


def test_metro_electric_is_not_creep(debits):
    g, _ = dedup(series(debits, "Metro Electric"))
    fit = series_features(g, REPORT, "Utilities", True)["cadence_fit"]
    assert fit >= 0.6 and detectors.price_creep(g, fit) is None  # variable bills aren't "price creep"


def test_freshcart_is_not_recurring_under_the_heuristic(debits):
    f = series_features(series(debits, "FreshCart"), REPORT, "Groceries", False)
    assert f["cadence"] == "irregular"
    assert heuristic_prob(pd.DataFrame([f]))[0] < 0.5


def test_duplicates_need_a_monthly_rhythm():
    g = pd.DataFrame({"tx_date": ["2026-01-01", "2026-01-02", "2026-01-04"], "amount": [5.0, 5.0, 5.0], "id": [1, 2, 3]})
    assert detectors.duplicate_charges(g, detectors.raw_cadence_days(g)) == []  # coffee twice ≠ double billing


def test_overlap_needs_two_active_recurring_in_a_category():
    rows = [{"merchant": "A", "recurring": True, "status": "active", "category": "Streaming"},
            {"merchant": "B", "recurring": True, "status": "active", "category": "Streaming"},
            {"merchant": "C", "recurring": True, "status": "keep", "category": "Streaming"},
            {"merchant": "D", "recurring": True, "status": "active", "category": "Utilities"}]
    assert detectors.overlaps(rows) == {m: {"category": "Streaming", "merchants": ["A", "B"]} for m in ("A", "B")}


def test_possible_annual_rule():
    assert detectors.possible_annual(119.88, "Cloud Storage", True)
    assert not detectors.possible_annual(119.88, "Dining", True)
    assert not detectors.possible_annual(119.88, "Cloud Storage", False)
    assert not detectors.possible_annual(9.99, "Cloud Storage", True)


def test_zombie_and_priority():
    s = {"recurring": True, "category": "Streaming", "status": "active", "flags": ["overlap"], "n_charges": 3}
    assert detectors.zombie_reasons(s) == ["overlap"]
    assert detectors.zombie_reasons({**s, "status": "keep"}) is None
    assert detectors.zombie_reasons({**s, "category": "Utilities"}) is None
    assert detectors.zombie_reasons({**s, "flags": [], "n_charges": 2}) is None
    assert detectors.priority(49.99, ["duplicate_charge", "price_creep"]) == pytest.approx(124.975)
    assert detectors.kind_of("Housing") == "bill" and detectors.kind_of("Music") == "subscription"
    assert detectors.kind_of("Dining") == "other"
