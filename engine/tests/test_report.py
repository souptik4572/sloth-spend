"""The audit end to end (IMPL M4.13): the golden values of IMPL §7 through POST /demo/load-sample, in heuristic
mode with canned Gemma names, plus confirm, labels, renames and re-scoring."""

import pytest
from conftest import FIXTURES, TOKEN, sse

from app import db, report

ORDER = ["Rent transfer", "IronTrap Fitness", "Metro Electric", "StreamFlix UHD", "TuneTide", "WatchNest",
         "CloudBox Pro", "FreshCart", "BeanThere Coffee"]


def by_name(rep: dict) -> dict[str, dict]:
    return {s["merchant"]: s for s in rep["series"]}


# ── IMPL §7 golden values ───────────────────────────────────────────────────

def test_statement_and_findings(sample_report):
    meta = sample_report["meta"]
    assert meta["report_date"] == "2026-10-15" and meta["currency"] == "USD" and meta["scorer"] == "heuristic"
    imp = meta["imports"][0]
    assert (imp["file_name"], imp["row_count"], imp["skipped_rows"]) == ("sample_bank_12m.csv", 412, 2)
    assert (imp["period_start"], imp["period_end"]) == ("2025-11-01", "2026-10-15")
    assert [s["merchant"] for s in sample_report["series"]] == ORDER


def test_filters(sample_report):
    series = sample_report["series"]
    assert sum(bool(s["flags"]) for s in series) == 5
    assert sum(s["kind"] == "subscription" for s in series) == 5
    assert sum(s["kind"] == "bill" for s in series) == 2


def test_irontrap(sample_report):
    s = by_name(sample_report)["IronTrap Fitness"]
    assert (s["category"], s["cadence"], s["n_charges"], s["next_due_date"]) == ("Fitness", "monthly", 13, "2026-11-05")
    assert s["dom_median"] == 5
    assert s["flags"] == ["duplicate_charge", "price_creep", "zombie_suspect"]
    assert s["flag_details"]["price_creep"] == {"from": 39.99, "to": 49.99, "pct": 25.0, "since": "2026-07-05"}
    dup = s["flag_details"]["duplicate_charge"]
    assert [(d["first"], d["second"], d["amount"]) for d in dup] == [("2026-07-05", "2026-07-06", 49.99)]


@pytest.mark.parametrize(("name", "category", "last", "next_due", "flags"), [
    ("StreamFlix UHD", "Streaming", 15.49, "2026-11-12", ["overlap", "zombie_suspect"]),
    ("WatchNest", "Streaming", 9.99, "2026-10-20", ["overlap", "zombie_suspect"]),
    ("TuneTide", "Music", 11.99, "2026-10-19", ["price_creep", "zombie_suspect"]),
    ("Metro Electric", "Utilities", 92.40, "2026-10-28", []),
    ("Rent transfer", "Housing", 1800.00, "2026-11-01", []),
])
def test_recurring_merchants(sample_report, name, category, last, next_due, flags):
    s = by_name(sample_report)[name]
    assert (s["category"], s["last_amount"], s["next_due_date"], s["flags"]) == (category, last, next_due, flags)
    assert s["recurring_prob"] >= 0.7


def test_tunetide_creep_and_metro_varies(sample_report):
    series = by_name(sample_report)
    assert series["TuneTide"]["flag_details"]["price_creep"]["pct"] == 9.1
    assert series["TuneTide"]["flag_details"]["price_creep"]["since"] == "2026-03-19"
    assert series["Metro Electric"]["amount_varies"] is True and series["Metro Electric"]["last_date"] == "2026-09-28"


def test_possible_annual(sample_report):
    s = by_name(sample_report)["CloudBox Pro"]
    assert (s["cadence"], s["n_charges"], s["recurring_prob"]) == ("single", 1, None)
    assert s["flags"] == ["possible_annual"] and s["next_due_date"] == "2027-01-14"


def test_not_recurring(sample_report):
    for name in ("FreshCart", "BeanThere Coffee"):
        s = by_name(sample_report)[name]
        assert s["recurring_prob"] < 0.5 and s["flags"] == [] and s["cadence"] == "irregular"
        assert s["next_due_date"] is None


def test_money(sample_report):
    meta = sample_report["meta"]
    assert (meta["monthly_recurring"], meta["monthly_subscriptions"], meta["monthly_bills"]) == (1979.86, 87.46, 1892.40)
    assert (meta["potential_savings"], meta["dispute_total"], meta["zombie_count"]) == (87.46, 49.99, 4)
    assert meta["flag_counts"] == {"duplicate_charge": 1, "price_creep": 2, "overlap": 2, "possible_annual": 1,
                                   "zombie_suspect": 4}
    assert meta["flagged_merchants"] == 5


def test_burn_chart(sample_report):
    monthly = sample_report["monthly"]
    assert [m["month"] for m in monthly][0] == "2025-11" and monthly[-1]["month"] == "2026-10"
    assert [m["subscriptions"] for m in monthly] == [76.46, 76.46, 196.34, 76.46, 77.46, 77.46, 77.46, 77.46,
                                                     137.45, 87.46, 87.46, 65.48]
    assert [m["month"] for m in monthly if m["highlights"]] == ["2026-01", "2026-07"]  # not Mar (tiny TuneTide rise)
    assert monthly[-1]["partial"] is True and not any(m["partial"] for m in monthly[:-1])
    assert monthly[8]["highlights"] == ["IronTrap Fitness’s price rise", "IronTrap Fitness charged twice"]


def test_forecast(sample_report):
    sub = sample_report["forecast_next"]["subscriptions"]
    assert sub == {"q10": 87.46, "q50": 87.46, "q90": 87.46}  # heuristic: no price change predicted
    assert sample_report["meta"]["fc30"]["q50"] == pytest.approx(1979.86, abs=0.01)


def test_summary(sample_report):
    meta = sample_report["meta"]
    assert meta["summary_source"] == "template"  # Ollama isn't reachable in tests
    assert meta["executive_summary"] == (
        "You pay $1,979.86 a month in recurring charges, and $87.46 of that is subscriptions. "
        "IronTrap Fitness went from $39.99 to $49.99 in July and charged you twice that month. "
        "StreamFlix UHD and WatchNest are both streaming services, so you may only need one. "
        "Nothing has been cancelled — that’s your call.")


def test_pipeline_stages(client, canned_gemma):
    events = sse(client, "/demo/load-sample", {"file": "main"})
    stages = [d["stage"] for e, d in events if e == "stage" and d["done"] == d["total"]]
    assert stages == list(report.STAGES)
    parse = next(d for e, d in events if e == "stage" and d["stage"] == "parse" and d.get("note"))
    assert parse["note"] == "410 rows · 2 skipped (unreadable dates)"
    normalize = [d for e, d in events if e == "stage" and d["stage"] == "normalize"]
    assert normalize[-1]["done"] == normalize[-1]["total"] == 191  # debit description keys


# ── drawer detail ───────────────────────────────────────────────────────────

def test_series_detail(client, auth, sample_report):
    iron = by_name(sample_report)["IronTrap Fitness"]
    d = client.get(f"/series/{iron['id']}", headers=auth).json()
    assert d["reasons"] == ["Billed every ~30 days, ±1 day, near the 5th of the month.",
                            "The same $39.99 eight times in a row, then $49.99 for the last four.",
                            "Gemma tagged it as a kind of merchant that usually bills a plan."]
    assert d["similar"]["archetype"] == "monthly subscription with a price rise"
    assert len(d["transactions"]) == 13 and sum(t["is_duplicate"] for t in d["transactions"]) == 1
    assert len(d["quantiles"]) == 19 and d["quantiles"][9] == {"q": 0.5, "amount": 49.99}
    assert d["desc_keys"] == ["IRONTRAP FITNESS MEMB"]
    assert d["raw_descriptions"][0].startswith("ACH DEBIT IRONTRAP FITNESS MEMB")
    assert client.get("/series/99999", headers=auth).status_code == 404


def test_metro_reasons_say_amounts_vary(client, auth, sample_report):
    metro = by_name(sample_report)["Metro Electric"]
    reasons = client.get(f"/series/{metro['id']}", headers=auth).json()["reasons"]
    assert reasons[1] == "Amounts vary from $71.25 to $139.80."


# ── corrections, renames, re-scoring ────────────────────────────────────────

def test_not_a_subscription_rescores_and_persists(client, auth, sample_report):
    stream = by_name(sample_report)["StreamFlix UHD"]
    rep = client.post(f"/series/{stream['id']}/label", headers=auth, json={"label": "not_subscription"}).json()["report"]
    after = by_name(rep)
    assert after["StreamFlix UHD"]["status"] == "not_subscription"
    assert after["StreamFlix UHD"]["recurring_prob"] == 0.0  # heuristic mode pins the user's answer (IMPL M4.9)
    assert "overlap" not in after["WatchNest"]["flags"]  # one streaming service left
    assert rep["meta"]["monthly_subscriptions"] == pytest.approx(71.97)
    assert rep["meta"]["summary_source"] == "template"
    assert db.user_labels()[0]["merchant"] == "StreamFlix UHD"


def test_label_survives_an_engine_restart(auth, canned_gemma):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        rep = sse(c, "/demo/load-sample", {"file": "main"})[-1][1]["report"]
        fresh = by_name(rep)["FreshCart"]
        c.post(f"/series/{fresh['id']}/label", headers=auth, json={"label": "subscription"})
    with TestClient(app) as c:  # a new engine process, same database
        s = by_name(c.get("/report", headers=auth).json())["FreshCart"]
        assert s["recurring_prob"] == 1.0 and s["status"] == "active"


def test_keep_clears_the_zombie_flag(client, auth, sample_report):
    tune = by_name(sample_report)["TuneTide"]
    rep = client.post(f"/series/{tune['id']}/label", headers=auth, json={"label": "keep"}).json()["report"]
    assert by_name(rep)["TuneTide"]["flags"] == ["price_creep"]
    assert rep["meta"]["zombie_count"] == 3


def test_rename_merchant(client, auth, sample_report):
    metro = by_name(sample_report)["Metro Electric"]
    r = client.patch(f"/series/{metro['id']}/merchant", headers=auth,
                     json={"merchant": "City Power", "category": "Utilities"}).json()
    names = by_name(r["report"])
    assert "City Power" in names and "Metro Electric" not in names
    assert r["series_id"] == names["City Power"]["id"]
    reasons = client.get(f"/series/{r['series_id']}", headers=auth).json()["reasons"]
    assert reasons[2] == "You set this merchant’s name and category."
    bad = client.patch(f"/series/{r['series_id']}/merchant", headers=auth, json={"merchant": "X", "category": "Nope"})
    assert bad.status_code == 422


def test_rescore_endpoint(client, auth, sample_report):
    r = client.post("/report/rescore", headers=auth)
    assert r.status_code == 200 and r.json()["report"]["meta"]["monthly_recurring"] == 1979.86


def test_report_404_before_any_import(client, auth):
    assert client.get("/report", headers=auth).status_code == 404
    assert client.post("/report/rescore", headers=auth).status_code == 404


# ── confirm, follow-ups, concurrency ────────────────────────────────────────

def test_confirm_with_the_column_mapper(client, auth, canned_gemma):
    up = client.post("/import", headers=auth,
                     files={"file": ("statement_oct26.csv", (FIXTURES / "statement_oct26.csv").read_bytes(), "text/csv")})
    import_id = up.json()["import_id"]
    events = sse(client, f"/import/{import_id}/confirm",
                 {"mapping": {"date": 0, "description": 1, "debit": 3, "credit": 4}})
    assert events[-1][0] == "done"
    rep = events[-1][1]["report"]
    assert rep["meta"]["currency"] == "INR" and rep["meta"]["report_date"] == "2026-10-31"
    assert client.post(f"/import/{import_id}/confirm", headers=auth, json={}).status_code == 409
    assert client.post("/import/99999/confirm", headers=auth, json={}).status_code == 404


def test_confirm_after_a_restart_asks_for_the_file_again(client, auth):
    from app.state import runtime

    up = client.post("/import", headers=auth,
                     files={"file": ("s.csv", (FIXTURES / "us_signed.csv").read_bytes(), "text/csv")}).json()
    runtime.pending.clear()
    assert client.post(f"/import/{up['import_id']}/confirm", headers=auth, json={}).status_code == 410


def test_followup_appends_and_reloading_is_a_no_op(client, sample_report):
    events = sse(client, "/demo/load-sample", {"file": "followup_still_charged"})
    rep = events[-1][1]["report"]
    assert rep["meta"]["report_date"] == "2026-11-15" and len(rep["meta"]["imports"]) == 2
    assert by_name(rep)["IronTrap Fitness"]["n_charges"] == 14
    again = sse(client, "/demo/load-sample", {"file": "main"})
    assert len(again) == 1 and again[0][0] == "done" and again[0][1]["duplicate"] is True


def test_busy_pipeline_is_refused(client, auth, monkeypatch, canned_gemma):
    monkeypatch.setattr(report, "busy", lambda: True)
    r = client.post("/demo/load-sample", headers={"X-Sloth-Token": TOKEN}, json={"file": "main"})
    assert r.status_code == 409


def test_new_routes_require_the_token(client):
    for method, path in [("get", "/report"), ("post", "/report/rescore"), ("post", "/demo/load-sample"),
                         ("get", "/series/1"), ("post", "/series/1/label"), ("post", "/setup/ollama/pull"),
                         ("post", "/import/1/confirm")]:
        assert getattr(client, method)(path).status_code == 401, path


def test_pull_only_accepts_gemma_models(client, auth):
    assert client.post("/setup/ollama/pull", headers=auth, json={"model": "llama3:8b"}).status_code == 422
    assert client.post("/setup/ollama/pull", headers=auth, json={"model": "gemma4:e4b; rm -rf /"}).status_code == 422
