"""Generate the bundled demo statements and test fixtures (spec §11.1, IMPL M3.1). Deterministic.

Writes:
  app/data/sample_bank_12m.csv          12 months, Nov 1 2025 – Oct 15 2026, 412 rows (2 with unreadable dates)
  app/data/followup_cancelled.csv       Oct 16 – Nov 15 2026, no IronTrap charge   → reminder verifies
  app/data/followup_still_charged.csv   same, plus IronTrap $49.99 on Nov 5         → still charged
  tests/fixtures/hdfc_style.csv         Indian bank layout: 13 preamble lines, Withdrawal/Deposit columns, dd/mm/yy
  tests/fixtures/statement_oct26.csv    D-Mapper's file: Outflow/Inflow columns the mapper must ask about
  tests/fixtures/us_signed.csv          US layout: one signed Amount column with $, minus signs and (parentheses)
  tests/fixtures/sample_merchant_map.json  canned "Gemma" output for every description key above

The numbers are tuned to IMPL §7 (golden values); every merchant is fictional.
usage: python scripts/make_sample_data.py [--data DIR] [--fixtures DIR]
"""

import argparse
import csv
import io
import itertools
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

ENGINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE))
from app.normalize import desc_key  # noqa: E402 — the same pre-clean the importer uses

SEED = 20261020
START, END = date(2025, 11, 1), date(2026, 10, 15)
FOLLOW_START, FOLLOW_END = date(2026, 10, 16), date(2026, 11, 15)
TOTAL_ROWS = 412  # incl. the 2 unreadable-date rows

# merchant → (category, subscription_like) — what Gemma would say; becomes the test fixture map.
MERCHANTS: dict[str, tuple[str, bool]] = {
    "IronTrap Fitness": ("Fitness", True),
    "StreamFlix UHD": ("Streaming", True),
    "WatchNest": ("Streaming", True),
    "TuneTide": ("Music", True),
    "CloudBox Pro": ("Cloud Storage", True),
    "Metro Electric": ("Utilities", True),
    "Rent transfer": ("Housing", False),
    "FreshCart": ("Groceries", False),
    "BeanThere Coffee": ("Dining", False),
    "Acme Toolworks Payroll": ("Transfers", False),
}

METRO_AMOUNTS = [88.10, 121.75, 139.80, 126.30, 104.55, 82.90, 71.25, 86.60, 118.45, 124.10, 92.40]

# One-off merchants (dining, rides, shopping): each appears exactly once so it never forms a series.
DINING = (["Copper", "Juniper", "Saffron", "Willow", "Harbor", "Maple", "Cedar", "Olive", "Ember", "Lantern",
           "Thistle", "Marigold", "Basil", "Quince", "Fennel", "Sorrel"],
          ["Kitchen", "Bistro", "Grill", "Noodle Bar", "Taqueria", "Diner", "Bakery", "Pizzeria"])
RIDES = (["Bluebird", "Swiftway", "Northside", "Riverbend", "Lakeshore", "Uptown", "Greenline", "Sunset",
          "Parkway", "Hillcrest"],
         ["Cabs", "Rides", "Taxi", "Car Service"])
SHOPS = (["Paper Lantern", "Tin Robot", "Wild Fern", "Blue Heron", "Old Mill", "Sparrow", "Fox & Pine",
          "Driftwood", "Granite", "Velvet Moth"],
         ["Books", "Hardware", "Outfitters", "Home Goods", "Records", "Toys", "Supply Co", "Gifts"])


def monthly(day: int, first: date, last: date) -> list[date]:
    out, y, m = [], first.year, first.month
    while True:
        d = date(y, m, min(day, 28))
        if d > last:
            return out
        if d >= first:
            out.append(d)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def jitter(rng: np.random.Generator, days: list[date], keep: set[date]) -> list[date]:
    """±1 day on most charges (the drawer says "every ~30 days, ±1 day"), except pinned dates."""
    return [d if d in keep else d + timedelta(days=int(rng.choice([-1, 0, 0, 1]))) for d in days]


def one_offs(rng: np.random.Generator) -> list[tuple[str, str, float, float]]:
    """A shuffled pool of (merchant, category, min, max) one-off merchants."""
    pool = [(f"{a} {b}", "Dining", 12, 85) for a, b in itertools.product(*DINING)]
    pool += [(f"{a} {b}", "Transport", 9, 45) for a, b in itertools.product(*RIDES)]
    pool += [(f"{a} {b}", "Shopping", 15, 220) for a, b in itertools.product(*SHOPS)]
    order = rng.permutation(len(pool))
    return [pool[i] for i in order]


def one_off_description(rng: np.random.Generator, name: str, category: str) -> str:
    upper = name.upper()
    if category == "Dining":
        return str(rng.choice([f"TST* {upper}", f"SQ *{upper}", f"{upper} #{rng.integers(10, 99)}"]))
    if category == "Transport":
        return f"{upper} TRIP {rng.integers(100000, 999999)}"
    return str(rng.choice([f"POS {upper}", f"{upper} STORE {rng.integers(10, 99)}"]))


def fmt_amount(signed: float) -> str:
    return f"{signed:.2f}"


def build_main(rng: np.random.Generator, pool: list) -> tuple[list[tuple[date, str, float]], dict[str, str]]:
    rows: list[tuple[date, str, float]] = []
    owner: dict[str, str] = {}  # description → merchant (for the fixture map)

    def add(d: date, description: str, signed: float, merchant: str) -> None:
        rows.append((d, description, round(signed, 2)))
        owner[description] = merchant

    # IronTrap Fitness: $39.99 Nov–Jun, $49.99 from Jul 5, a duplicate on Jul 6 (spec §11.1).
    iron = jitter(rng, monthly(5, START, END), keep={date(2026, 7, 5), date(2026, 10, 5)})
    for d in iron:
        price = 49.99 if d >= date(2026, 7, 1) else 39.99
        add(d, f"ACH DEBIT IRONTRAP FITNESS MEMB 7731{' REF#A' + str(d.month) if d.month % 2 else ''}",
            -price, "IronTrap Fitness")
    add(date(2026, 7, 6), "ACH DEBIT IRONTRAP FITNESS MEMB 7731 REF#B7", -49.99, "IronTrap Fitness")

    for d in jitter(rng, monthly(12, START, END), keep={date(2026, 10, 12)}):
        desc = f"ECOM STREAMFLIX UHD SUBSCR #A{d.month:02d}" if d.month % 3 else "STREAMFLIX UHD SUBSCR ONLINE"
        add(d, desc, -15.49, "StreamFlix UHD")
    for d in jitter(rng, monthly(20, START, END), keep={date(2026, 9, 20)}):
        desc = "WATCHNEST*MONTHLY 4471" + (" CARD PURCHASE" if d.month % 2 else "")
        add(d, desc, -9.99, "WatchNest")
    for d in jitter(rng, monthly(19, START, END), keep={date(2026, 3, 19), date(2026, 9, 19)}):
        price = 11.99 if d >= date(2026, 3, 1) else 10.99
        add(d, f"TUNETIDE MUSIC {d.month:02d}/{d.day:02d}", -price, "TuneTide")
    add(date(2026, 1, 14), "CLOUDBOX PRO ANNUAL", -119.88, "CloudBox Pro")
    for d, amount in zip(monthly(28, START, END), METRO_AMOUNTS, strict=True):
        add(d, f"METRO ELECTRIC AUTOPAY {rng.integers(100000, 999999)}", -amount, "Metro Electric")
    for d in monthly(1, START, END):
        add(d, "RENT TRANSFER TO OAKWOOD PROP" if d.month % 2 else "ACH RENT TRANSFER TO OAKWOOD PROP",
            -1800.00, "Rent transfer")
        add(d, "PAYROLL DEPOSIT ACME TOOLWORKS", 4250.00, "Acme Toolworks Payroll")

    # FreshCart: groceries with uneven gaps and amounts → not recurring ("Irregular").
    d = START + timedelta(days=1)
    while d <= END:
        add(d, f"POS 4160XXXX2291 FRESHCART #{rng.integers(100, 140)}", -float(rng.uniform(40, 140)), "FreshCart")
        d += timedelta(days=int(rng.integers(2, 21)))
    # BeanThere: small, frequent, uneven → not recurring. The last visit pins report_date to Oct 15.
    d = START
    visits = []
    while d <= END:
        visits.append(d)
        d += timedelta(days=int(rng.integers(1, 7)))
    if visits[-1] != END:
        visits.append(END)
    for d in visits:
        desc = f"BEANTHERE COFFEE {rng.integers(500000, 599999)}" if rng.random() < 0.7 else "SQ *BEANTHERE COFFEE"
        add(d, desc, -float(rng.uniform(3, 9)), "BeanThere Coffee")

    # Fill the rest with one-off merchants on random days.
    need = TOTAL_ROWS - 2 - len(rows)
    span = (END - START).days
    for name, category, lo, hi in pool[:need]:
        when = START + timedelta(days=int(rng.integers(0, span + 1)))
        desc = one_off_description(rng, name, category)
        MERCHANTS.setdefault(name, (category, False))
        add(when, desc, -float(rng.uniform(lo, hi)), name)
    del pool[:need]
    return rows, owner


def build_followup(rng: np.random.Generator, pool: list) -> tuple[list[tuple[date, str, float]], dict[str, str]]:
    rows: list[tuple[date, str, float]] = []
    owner: dict[str, str] = {}

    def add(d: date, description: str, signed: float, merchant: str) -> None:
        rows.append((d, description, round(signed, 2)))
        owner[description] = merchant

    add(date(2026, 10, 19), "TUNETIDE MUSIC 10/19", -11.99, "TuneTide")
    add(date(2026, 10, 20), "WATCHNEST*MONTHLY 4471", -9.99, "WatchNest")
    add(date(2026, 10, 28), "METRO ELECTRIC AUTOPAY 660201", -97.30, "Metro Electric")
    add(date(2026, 11, 1), "ACH RENT TRANSFER TO OAKWOOD PROP", -1800.00, "Rent transfer")
    add(date(2026, 11, 1), "PAYROLL DEPOSIT ACME TOOLWORKS", 4250.00, "Acme Toolworks Payroll")
    for d in (date(2026, 10, 18), date(2026, 10, 31), date(2026, 11, 9)):
        add(d, f"POS 4160XXXX2291 FRESHCART #{rng.integers(100, 140)}", -float(rng.uniform(40, 140)), "FreshCart")
    d = FOLLOW_START
    while d <= FOLLOW_END:
        add(d, f"BEANTHERE COFFEE {rng.integers(500000, 599999)}", -float(rng.uniform(3, 9)), "BeanThere Coffee")
        d += timedelta(days=int(rng.integers(1, 5)))
    if rows[-1][0] != FOLLOW_END:
        add(FOLLOW_END, "SQ *BEANTHERE COFFEE", -4.85, "BeanThere Coffee")
    span = (FOLLOW_END - FOLLOW_START).days
    for name, category, lo, hi in pool[:8]:
        when = FOLLOW_START + timedelta(days=int(rng.integers(0, span + 1)))
        desc = one_off_description(rng, name, category)
        MERCHANTS.setdefault(name, (category, False))
        add(when, desc, -float(rng.uniform(lo, hi)), name)
    del pool[:8]
    # No StreamFlix after Oct 15 in either follow-up (IMPL §2 #18).
    return rows, owner


def statement_csv(rows: list[tuple[date, str, float]], bad_rows: list[tuple[int, list[str]]]) -> str:
    """Newest first, as most banks export; `bad_rows` are spliced in at fixed positions."""
    ordered = sorted(rows, key=lambda r: (r[0], r[1]), reverse=True)
    lines = [[d.strftime("%m/%d/%Y"), desc, fmt_amount(amount)] for d, desc, amount in ordered]
    for position, cells in bad_rows:
        lines.insert(position, cells)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["Date", "Description", "Amount"])
    writer.writerows(lines)
    return buf.getvalue()


# ── fixtures ────────────────────────────────────────────────────────────────

PREAMBLE = [
    ["HDFC BANK Ltd."], ["Page No .: 1"], ["Account Branch : KORAMANGALA"],
    ["Address : 12", "80 FEET ROAD", "KORAMANGALA"], ["City : BANGALORE 560034"], ["State : KARNATAKA"],
    ["Phone no. : 1800 202 6161"], ["OD Limit : 0.00"], ["Currency : INR"], ["Email : xxxxxxx@example.com"],
    ["Cust ID : 88213XXXX"], ["Account No : 50100XXXXXXX"], ["Statement From : 01/10/2026 To : 31/10/2026"],
]

# (dd/mm/yy, particulars, cheque no, withdrawal, deposit) — the D-Mapper preview rows plus a few more.
INDIAN_ROWS = [
    ("01/10/26", "NEFT DR-HOUSING RENT OCT-REF 88213", "", 32000.00, 0),
    ("02/10/26", "UPI-TUNETIDE MUSIC-428817", "", 119.00, 0),
    ("03/10/26", "POS 4160XXXXXX2291 FRESHCART BLR", "", 1284.50, 0),
    ("05/10/26", "ACH D- IRONTRAP FITNESS-MEMB 7731", "", 1499.00, 0),
    ("06/10/26", "UPI-BEANTHERE COFFEE-501123", "", 240.00, 0),
    ("07/10/26", "SALARY CREDIT OCT 2026", "", 0, 145000.00),
    ("12/10/26", "ECOM STREAMFLIX UHD SUBSCR", "", 649.00, 0),
    ("14/10/26", "UPI-METRO ELECTRIC BILL-660201", "", 2310.00, 0),
    ("18/10/26", "CHQ PAID-SOCIETY MAINTENANCE", "004512", 3500.00, 0),
    ("20/10/26", "UPI-WATCHNEST-771045", "", 199.00, 0),
    ("22/10/26", "UPI-BEANTHERE COFFEE-501877", "", 180.00, 0),
    ("24/10/26", "IMPS-REFUND FROM WILD FERN OUTFITTERS", "", 0, 850.00),
    ("26/10/26", "POS 4160XXXXXX2291 FRESHCART BLR", "", 2105.75, 0),
    ("29/10/26", "UPI-SWIFTWAY CABS-883310", "", 312.00, 0),
    ("31/10/26", "INTEREST CREDIT", "", 0, 412.35),
]
OPENING_BALANCE = 150450.20


def inr(value: float) -> str:
    """Indian digit grouping: 118450.2 → 1,18,450.20."""
    whole, frac = f"{value:.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        head = ",".join([head[max(0, i - 2):i] for i in range(len(head), 0, -2)][::-1])
        whole = f"{head},{tail}"
    return f"{whole}.{frac}"


def indian_csv(amount_headers: tuple[str, str]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerows(PREAMBLE)
    writer.writerow(["Tran Date", "Particulars", "Chq No", *amount_headers, "Balance"])
    balance = OPENING_BALANCE
    for when, particulars, cheque, out, inn in INDIAN_ROWS:
        balance = round(balance - out + inn, 2)
        writer.writerow([when, particulars, cheque, inr(out) if out else "", inr(inn) if inn else "", inr(balance)])
    return buf.getvalue()


US_ROWS = [
    ("9/1/2026", "PAYROLL DEPOSIT NORTHWIND", "$3,200.00"),
    ("9/2/2026", "STREAMFLIX UHD SUBSCR", "-$15.49"),
    ("9/3/2026", "FRESHCART #118", "-$86.20"),
    ("9/5/2026", "IRONTRAP FITNESS MEMB", "-$49.99"),
    ("9/7/2026", "BEANTHERE COFFEE", "-$5.40"),
    ("9/9/2026", "TST* SAFFRON NOODLE BAR", "($42.10)"),
    ("9/12/2026", "CLOUDBOX PRO", "-$9.99"),
    ("9/14/2026", "REFUND PAPER LANTERN BOOKS", "$18.00"),
    ("9/15/2026", "METRO ELECTRIC AUTOPAY", "-$92.40"),
    ("9/18/2026", "BLUEBIRD CABS TRIP", "-$23.75"),
    ("9/19/2026", "TUNETIDE MUSIC", "-$11.99"),
    ("9/20/2026", "WATCHNEST*MONTHLY", "-$9.99"),
    ("9/24/2026", "FRESHCART #121", "-$112.35"),
    ("9/28/2026", "BEANTHERE COFFEE", "-$4.25"),
    ("9/30/2026", "INTEREST PAID", "$1.12"),
]


def us_csv() -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["Transaction Date", "Description", "Amount"])
    writer.writerows(US_ROWS)
    return buf.getvalue()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path, default=ENGINE / "app" / "data")
    ap.add_argument("--fixtures", type=Path, default=ENGINE / "tests" / "fixtures")
    args = ap.parse_args()
    args.data.mkdir(parents=True, exist_ok=True)
    args.fixtures.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(SEED)
    pool = one_offs(rng)
    main_rows, main_owner = build_main(rng, pool)
    follow_rows, follow_owner = build_followup(rng, pool)

    bad = [(57, ["PENDING", "CARD AUTHORISATION HOLD", "-12.50"]),
           (203, ["--", "BRANCH ADJUSTMENT", "-3.00"])]
    files = {
        args.data / "sample_bank_12m.csv": statement_csv(main_rows, bad),
        args.data / "followup_cancelled.csv": statement_csv(follow_rows, []),
        args.data / "followup_still_charged.csv": statement_csv(
            [*follow_rows, (date(2026, 11, 5), "ACH DEBIT IRONTRAP FITNESS MEMB 7731", -49.99)], []),
        args.fixtures / "hdfc_style.csv": indian_csv(("Withdrawal Amt.", "Deposit Amt.")),
        args.fixtures / "statement_oct26.csv": indian_csv(("Outflow", "Inflow")),
        args.fixtures / "us_signed.csv": us_csv(),
    }
    owner = {**main_owner, **follow_owner, "ACH DEBIT IRONTRAP FITNESS MEMB 7731": "IronTrap Fitness"}
    merchant_map = {}
    for description, merchant in owner.items():
        category, sub = MERCHANTS[merchant]
        merchant_map[desc_key(description)] = {"merchant": merchant, "category": category,
                                                "subscription_like": sub}
    files[args.fixtures / "sample_merchant_map.json"] = json.dumps(merchant_map, indent=2, sort_keys=True) + "\n"

    for path, text in files.items():
        path.write_text(text, encoding="utf-8")
    lines = files[args.data / "sample_bank_12m.csv"].count("\n") - 1
    print(f"sample_bank_12m.csv: {lines} rows · follow-ups: {len(follow_rows)} / {len(follow_rows) + 1} rows · "
          f"{len(merchant_map)} description keys in the fixture map")


if __name__ == "__main__":
    main()
