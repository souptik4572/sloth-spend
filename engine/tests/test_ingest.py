"""CSV ingestion (spec §13.1, IMPL M3.7): layouts, mapping, dates, signs, currency, appends, re-imports."""

import subprocess
import sys

import pytest

from app import db, ingest
from app.normalize import desc_key
from app.state import runtime
from conftest import DATA, ENGINE, FIXTURES


def stage(raw: bytes, name: str = "statement.csv") -> tuple[int, ingest.Parsed]:
    """Upload without the HTTP layer: parse + a pending import row + bytes kept for commit()."""
    parsed = ingest.parse(raw, name)
    import_id = db.create_pending_import(name, parsed.sha256, parsed.mapping, parsed.currency, parsed.header_row)
    runtime.pending[import_id] = raw
    return import_id, parsed


def read(path) -> bytes:
    return path.read_bytes()


# ── layouts ─────────────────────────────────────────────────────────────────

def test_sample_statement_maps_itself():
    _, p = stage(read(DATA / "sample_bank_12m.csv"), "sample_bank_12m.csv")
    assert p.header_row == 0
    assert p.mapping == {"date": 0, "description": 1, "amount": 2}
    assert not p.needs_mapping and p.missing == []
    assert p.dayfirst is False  # 10/15/2026: the second part is > 12
    assert p.debits_positive is False  # most amounts are negative → negatives are debits
    assert (p.currency, p.currency_detected) == ("USD", False)  # no symbol: the Settings default
    assert p.row_count == 412
    assert len(p.preview) == 10 and [c["role"] for c in p.columns] == ["date", "description", "amount"]


def test_sample_statement_commit_counts():
    import_id, _ = stage(read(DATA / "sample_bank_12m.csv"))
    r = ingest.commit(import_id)
    assert r.skipped_dates == 2  # PENDING and "--"
    assert r.rows == 410 and r.credits == 12 and r.debits == 398  # 12 payroll credits
    assert (r.period_start, r.period_end, r.report_date) == ("2025-11-01", "2026-10-15", "2026-10-15")
    imp = db.get_import(import_id)
    assert imp["status"] == "committed" and imp["row_count"] == 412 and imp["skipped_rows"] == 2
    txs = db.transactions(import_id)
    assert all(t["amount"] > 0 for t in txs)
    iron = [t for t in txs if t["desc_key"] == "IRONTRAP FITNESS MEMB"]
    assert len(iron) == 13 and {t["tx_date"] for t in iron} >= {"2026-07-05", "2026-07-06"}
    assert runtime.pending == {}  # bytes are dropped once stored


def test_indian_bank_layout_with_preamble():
    import_id, p = stage(read(FIXTURES / "hdfc_style.csv"))
    assert p.header_row == 13  # 13 preamble lines skipped
    assert p.mapping == {"date": 0, "description": 1, "debit": 3, "credit": 4}
    assert not p.needs_mapping
    assert p.dayfirst is True  # 18/10/26: the first part is > 12
    assert (p.currency, p.currency_detected) == ("INR", True)  # 1,18,450.20 grouping
    r = ingest.commit(import_id)
    assert r.rows == 15 and r.credits == 3
    first = db.transactions(import_id)[0]
    assert (first["tx_date"], first["amount"], first["direction"]) == ("2026-10-01", 32000.0, "debit")


def test_mapper_layout_asks_then_remembers():
    raw = read(FIXTURES / "statement_oct26.csv")
    import_id, p = stage(raw)
    assert p.needs_mapping and p.missing == ["amount"]  # Outflow / Inflow aren't known names
    assert p.mapping == {"date": 0, "description": 1}
    assert [c["name"] for c in p.columns] == ["Tran Date", "Particulars", "Chq No", "Outflow", "Inflow", "Balance"]

    r = ingest.commit(import_id, {"mapping": {"date": 0, "description": 1, "debit": 3, "credit": 4}})
    assert r.rows == 15 and r.credits == 3

    again = ingest.parse(raw, "statement_oct26.csv")  # "we'll remember this layout next time"
    assert again.remembered and not again.needs_mapping
    assert again.mapping == {"date": 0, "description": 1, "debit": 3, "credit": 4}


def test_us_signed_amounts_with_symbols_and_parentheses():
    import_id, p = stage(read(FIXTURES / "us_signed.csv"))
    assert p.mapping == {"date": 0, "description": 1, "amount": 2}
    assert (p.currency, p.currency_detected) == ("USD", True)
    assert p.dayfirst is False and p.debits_positive is False
    ingest.commit(import_id)
    txs = {t["raw_description"]: t for t in db.transactions(import_id)}
    assert txs["TST* SAFFRON NOODLE BAR"]["direction"] == "debit"  # ($42.10)
    assert txs["TST* SAFFRON NOODLE BAR"]["amount"] == 42.10
    assert txs["PAYROLL DEPOSIT NORTHWIND"]["amount"] == 3200.0
    assert sum(t["direction"] == "credit" for t in txs.values()) == 3


# ── signs ───────────────────────────────────────────────────────────────────

def test_type_column_decides_the_sign():
    raw = b"Date,Description,Amount,Type\n2026-10-01,RENT,1800.00,DR\n2026-10-02,SALARY,4250.00,CR\n"
    import_id, p = stage(raw)
    assert p.mapping["type"] == 3 and not p.needs_mapping
    ingest.commit(import_id)
    assert [(t["raw_description"], t["direction"]) for t in db.transactions(import_id)] == [
        ("RENT", "debit"), ("SALARY", "credit")]


def test_mostly_positive_amounts_ask_and_honour_the_toggle():
    raw = b"Date,Description,Amount\n10/01/2026,RENT,1800\n10/02/2026,COFFEE,4.50\n10/03/2026,REFUND,-20\n"
    import_id, p = stage(raw)
    assert p.needs_mapping and p.sign_ambiguous and p.missing == []
    assert p.debits_positive is True  # the mapper's suggested default
    ingest.commit(import_id, {"debits_positive": True})
    assert [t["direction"] for t in db.transactions(import_id)] == ["debit", "debit", "credit"]


def test_debit_wins_when_both_columns_are_filled():
    raw = b"Date,Description,Debit,Credit\n01/10/2026,ODD ROW,10.00,5.00\n"
    import_id, _ = stage(raw)
    ingest.commit(import_id)
    t = db.transactions(import_id)[0]
    assert (t["direction"], t["amount"]) == ("debit", 10.0)


# ── accumulation and re-imports ─────────────────────────────────────────────

def test_newer_statement_appends_only_later_rows():
    first, _ = stage(read(DATA / "sample_bank_12m.csv"))
    ingest.commit(first)
    follow, _ = stage(read(DATA / "followup_cancelled.csv"))
    r = ingest.commit(follow)
    assert r.skipped_overlap == 0 and r.period_start == "2026-10-16" and r.report_date == "2026-11-15"

    overlap = b"Date,Description,Amount\n11/15/2026,SAME DAY AS LAST,-1.00\n11/16/2026,NEXT DAY,-2.00\n"
    third, _ = stage(overlap)
    r = ingest.commit(third)
    assert (r.rows, r.skipped_overlap) == (1, 1)  # the boundary day is already covered
    assert [t["raw_description"] for t in db.transactions(third)] == ["NEXT DAY"]


def test_upload_api_and_reimport_is_a_no_op(client, auth):
    raw = read(DATA / "sample_bank_12m.csv")
    up = lambda: client.post("/import", headers=auth, files={"file": ("sample_bank_12m.csv", raw, "text/csv")})  # noqa: E731
    first = up().json()
    assert first["duplicate"] is False and first["needs_mapping"] is False
    assert first["row_count"] == 412 and first["file_name"] == "sample_bank_12m.csv"
    assert up().json()["import_id"] == first["import_id"]  # chosen again before confirming: same pending row

    ingest.commit(first["import_id"])
    again = up().json()
    assert again["duplicate"] is True and again["import_id"] == first["import_id"]
    assert len(db.transactions()) == 410  # nothing added


def test_delete_pending_import(client, auth):
    body = client.post("/import", headers=auth,
                       files={"file": ("s.csv", read(FIXTURES / "statement_oct26.csv"), "text/csv")}).json()
    assert client.delete(f"/import/{body['import_id']}", headers=auth).json() == {"ok": True}
    assert db.get_import(body["import_id"]) is None and runtime.pending == {}
    assert client.delete(f"/import/{body['import_id']}", headers=auth).status_code == 404

    committed, _ = stage(read(DATA / "sample_bank_12m.csv"))
    ingest.commit(committed)
    assert client.delete(f"/import/{committed}", headers=auth).status_code == 409


def test_unusable_files_get_plain_errors(client, auth):
    empty = client.post("/import", headers=auth, files={"file": ("e.csv", b"", "text/csv")})
    assert empty.status_code == 422 and "empty" in empty.json()["detail"]
    header_only = client.post("/import", headers=auth, files={"file": ("h.csv", b"Date,Description,Amount\n", "text/csv")})
    assert header_only.status_code == 422

    import_id, _ = stage(b"Date,Description,Amount\nPENDING,X,-1\n")
    with pytest.raises(ingest.ImportProblem) as exc:
        ingest.commit(import_id)
    assert exc.value.status == 422 and "dated rows" in exc.value.message

    import_id, _ = stage(read(FIXTURES / "statement_oct26.csv"))
    with pytest.raises(ingest.ImportProblem, match="amount"):
        ingest.commit(import_id, {"mapping": {"date": 0, "description": 1}})


def test_commit_needs_the_uploaded_bytes():
    import_id, _ = stage(read(DATA / "sample_bank_12m.csv"))
    runtime.pending.clear()  # what an engine restart looks like
    with pytest.raises(ingest.ImportProblem) as exc:
        ingest.commit(import_id)
    assert exc.value.status == 410


# ── small pieces ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(("text", "value"), [
    ("-49.99", -49.99), ("49.99", 49.99), ("(42.10)", -42.10), ("$4,250.00", 4250.0),
    ("1,18,450.20", 118450.20), ("12.00 DR", -12.0), ("", None), ("n/a", None),
])
def test_parse_amount(text, value):
    assert ingest.parse_amount(text) == value


def test_dayfirst_inference():
    assert ingest.infer_dayfirst(["18/10/26"], "USD") is True
    assert ingest.infer_dayfirst(["10/18/2026"], "INR") is False
    assert ingest.infer_dayfirst(["01/02/2026"], "INR") is True  # ambiguous: by currency
    assert ingest.infer_dayfirst(["2026-10-18"], "INR") is False  # ISO


def test_desc_key_strips_noise_and_card_masks():
    assert desc_key("POS 4160XXXX2291 FRESHCART #112") == "FRESHCART"
    assert desc_key("ACH DEBIT IRONTRAP FITNESS MEMB 7731 REF#A12") == "IRONTRAP FITNESS MEMB"
    assert desc_key("TUNETIDE MUSIC 10/19") == desc_key("UPI-TUNETIDE MUSIC-428817") == "TUNETIDE MUSIC"


def test_generators_are_deterministic(tmp_path):
    """IMPL M3 exit: regenerating writes byte-identical files to the committed ones."""
    data, fixtures = tmp_path / "data", tmp_path / "fixtures"
    py = [sys.executable, "-I"]
    subprocess.run([*py, str(ENGINE / "scripts" / "make_sample_data.py"), "--data", str(data),
                    "--fixtures", str(fixtures)], check=True, capture_output=True)
    subprocess.run([*py, str(ENGINE / "scripts" / "make_priors.py"), "--out", str(data)],
                   check=True, capture_output=True)
    for name in ["sample_bank_12m.csv", "followup_cancelled.csv", "followup_still_charged.csv",
                 "priors_recurring.csv", "priors_hikes.csv"]:
        assert (data / name).read_bytes() == (DATA / name).read_bytes(), name
    for name in ["hdfc_style.csv", "statement_oct26.csv", "us_signed.csv", "sample_merchant_map.json"]:
        assert (fixtures / name).read_bytes() == (FIXTURES / name).read_bytes(), name
