"""CSV ingestion (spec §7.3, IMPL M3.4).

bytes → encoding → delimiter → header row → column mapping → dates → amount/sign → rows.
`parse()` inspects an upload for the column mapper; `commit()` stores the rows of a pending import.
Only rows dated after the latest stored transaction are appended, so newer statements accumulate.
"""

import csv
import hashlib
import io
import json
import re
from dataclasses import asdict, dataclass, field

import pandas as pd

from . import db
from .normalize import desc_key
from .state import runtime

HEADER_SYNONYMS = {
    "date": ["date", "txn date", "transaction date", "posting date", "value date", "value dt", "tran date"],
    "description": ["description", "narration", "details", "particulars", "memo", "payee",
                    "transaction details", "remarks"],
    "amount": ["amount", "amt", "transaction amount", "amount (inr)", "amount (usd)"],
    "debit": ["debit", "withdrawal", "withdrawal amt.", "withdrawal amount", "dr", "money out", "paid out"],
    "credit": ["credit", "deposit", "deposit amt.", "deposit amount", "cr", "money in", "paid in"],
    "type": ["type", "dr/cr", "cr/dr", "transaction type"],
}

ROLES = ("date", "description", "amount", "debit", "credit", "type")
PREVIEW_ROWS = 10
HEADER_SCAN_ROWS = 30
NO_DESCRIPTION = "(no description)"

CURRENCY_MARKERS = [("₹", "INR"), ("rs.", "INR"), ("inr", "INR"), ("€", "EUR"), ("eur", "EUR"),
                    ("£", "GBP"), ("gbp", "GBP"), ("$", "USD"), ("usd", "USD")]
INDIAN_GROUPING = re.compile(r"\b\d{1,2},\d{2},\d{3}(?:\.\d+)?\b")  # 1,18,450.20
INDIAN_RAILS = re.compile(r"\b(UPI|NEFT|IMPS|RTGS)\b", re.IGNORECASE)
DATE_PARTS = re.compile(r"^\s*(\d{1,4})[/\-. ](\d{1,2})[/\-. ](\d{2,4})")


class ImportProblem(Exception):
    """A problem with an upload, worded for the user. `status` is the HTTP status the API returns."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# ── spec §7.3, verbatim ─────────────────────────────────────────────────────

def _norm(cell: str) -> str:
    return re.sub(r"\s+", " ", (cell or "").strip().lower())


def detect_header(rows: list[list[str]]) -> tuple[int, dict[str, int]]:
    best_idx, best_map = -1, {}
    for idx, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        mapping: dict[str, int] = {}
        for col, cell in enumerate(row):
            name = _norm(cell)
            for fld, names in HEADER_SYNONYMS.items():
                if fld not in mapping and name in names:
                    mapping[fld] = col
        if len(mapping) > len(best_map):
            best_idx, best_map = idx, mapping
    return best_idx, best_map


def mapping_confidence(mapping: dict[str, int]) -> float:
    has_amount = "amount" in mapping or "debit" in mapping
    return (("date" in mapping) + ("description" in mapping) + has_amount) / 3


def parse_amount(text: str) -> float | None:
    s = (text or "").strip()
    if not s:
        return None
    negative = (s.startswith("(") and s.endswith(")")) or s.startswith("-") or s.upper().endswith("DR")
    digits = re.sub(r"[^0-9.]", "", s)
    if not digits:
        return None
    value = float(digits)
    return -value if negative else value


# ── reading the file ────────────────────────────────────────────────────────

def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def read_table(text: str) -> list[list[str]]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    # Sniff on the tail: preamble lines at the top (bank name, address) confuse the sniffer.
    sample = "\n".join(lines[-40:])
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","
    rows = list(csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter))
    return [[cell.strip() for cell in row] for row in rows if any(cell.strip() for cell in row)]


def _cell(row: list[str], col: int | None) -> str:
    return row[col] if col is not None and 0 <= col < len(row) else ""


def layout_key(header: list[str]) -> str:
    """Settings key for a remembered column layout ("we'll remember this layout next time")."""
    digest = hashlib.sha1(json.dumps([_norm(c) for c in header]).encode()).hexdigest()[:16]
    return f"layout:{digest}"


# ── detection ───────────────────────────────────────────────────────────────

def detect_currency(header: list[str], data: list[list[str]], mapping: dict[str, int],
                    default: str) -> tuple[str, bool]:
    """(currency, detected). Symbols or codes in headers/amounts first, then Indian number grouping
    (1,18,450.20) or Indian payment rails in descriptions, else the Settings default."""
    money_cols = [mapping[k] for k in ("amount", "debit", "credit") if k in mapping]
    texts = [_norm(c) for c in header]
    texts += [_cell(r, c).lower() for r in data[:200] for c in money_cols]
    blob = " ".join(texts)
    for marker, code in CURRENCY_MARKERS:
        if marker in blob:
            return code, True
    amounts = " ".join(_cell(r, c) for r in data[:200] for c in money_cols)
    if INDIAN_GROUPING.search(amounts):
        return "INR", True
    descriptions = " ".join(_cell(r, mapping.get("description")) for r in data[:200])
    if INDIAN_RAILS.search(descriptions):
        return "INR", True
    return default, False


def infer_dayfirst(date_cells: list[str], currency: str) -> bool:
    """Any first component > 12 → day-first; any second > 12 → month-first; else by currency."""
    first_big = second_big = False
    for text in date_cells:
        m = DATE_PARTS.match(text)
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        if len(m.group(1)) == 4:  # ISO yyyy-mm-dd
            return False
        first_big |= a > 12
        second_big |= b > 12
    if first_big and not second_big:
        return True
    if second_big and not first_big:
        return False
    return currency == "INR"


def sign_from_amounts(data: list[list[str]], mapping: dict[str, int]) -> tuple[bool | None, bool]:
    """(debits_positive, ambiguous) for a single signed amount column (spec §7.3 "Sign")."""
    if "amount" not in mapping or "debit" in mapping or "credit" in mapping or "type" in mapping:
        return None, False
    values = [v for r in data if (v := parse_amount(_cell(r, mapping["amount"]))) not in (None, 0.0)]
    if not values:
        return True, True
    negative_share = sum(v < 0 for v in values) / len(values)
    if negative_share > 0.5:
        return False, False  # negatives are debits
    return True, True  # most amounts positive: ask, suggesting "debits are positive"


# ── parse: what the column mapper needs ─────────────────────────────────────

@dataclass
class Parsed:
    file_name: str
    sha256: str
    header_row: int
    header: list[str]
    mapping: dict[str, int]
    needs_mapping: bool
    missing: list[str]
    columns: list[dict]
    preview: list[list[str]]
    currency: str
    currency_detected: bool
    dayfirst: bool
    debits_positive: bool | None
    sign_ambiguous: bool
    row_count: int
    remembered: bool = False

    def payload(self, import_id: int) -> dict:
        out = asdict(self)
        out.pop("sha256")
        return {"import_id": import_id, "duplicate": False, **out}


def _missing(mapping: dict[str, int]) -> list[str]:
    missing = [f for f in ("date", "description") if f not in mapping]
    if "amount" not in mapping and "debit" not in mapping:
        missing.append("amount")
    return missing


def parse(raw: bytes, file_name: str, default_currency: str = "USD") -> Parsed:
    table = read_table(decode(raw))
    if not table:
        raise ImportProblem(422, "This file is empty. Export a CSV statement from your bank and try again.")
    header_row, mapping = detect_header(table)
    if header_row < 0:
        header_row, mapping = 0, {}
    header = table[header_row]
    data = table[header_row + 1:]
    if not data:
        raise ImportProblem(422, "We couldn't find any rows under the header. Is this a bank statement export?")

    remembered = db.get_setting(layout_key(header))
    debits_positive, ambiguous = None, False
    if remembered:
        saved = json.loads(remembered)
        mapping = {k: int(v) for k, v in saved["mapping"].items()}
        debits_positive = saved.get("debits_positive")
    else:
        debits_positive, ambiguous = sign_from_amounts(data, mapping)

    currency, detected = detect_currency(header, data, mapping, default_currency)
    date_cells = [_cell(r, mapping.get("date")) for r in data]
    dayfirst = infer_dayfirst(date_cells, currency)
    missing = _missing(mapping)
    width = max(len(header), *(len(r) for r in data[:PREVIEW_ROWS]))
    roles = {col: role for role, col in mapping.items()}
    columns = [{"index": i, "name": _cell(header, i) or f"Column {i + 1}", "role": roles.get(i, "ignore")}
               for i in range(width)]
    preview = [[_cell(r, i) for i in range(width)] for r in data[:PREVIEW_ROWS]]
    return Parsed(
        file_name=file_name, sha256=sha256(raw), header_row=header_row, header=header, mapping=mapping,
        needs_mapping=bool(missing) or (ambiguous and not remembered), missing=missing, columns=columns,
        preview=preview, currency=currency, currency_detected=detected, dayfirst=dayfirst,
        debits_positive=debits_positive, sign_ambiguous=ambiguous and not remembered,
        row_count=len(data), remembered=bool(remembered))


# ── extract + commit ────────────────────────────────────────────────────────

@dataclass
class Extracted:
    rows: list[dict] = field(default_factory=list)  # {tx_date, raw_description, amount, direction}
    skipped_dates: int = 0
    skipped_amounts: int = 0


def _direction_from_type(cell: str) -> str | None:
    t = _norm(cell).upper()
    if t.startswith("DR") or t in ("D", "DEBIT", "WITHDRAWAL"):
        return "debit"
    if t.startswith("CR") or t in ("C", "CREDIT", "DEPOSIT"):
        return "credit"
    return None


def extract(data: list[list[str]], mapping: dict[str, int], *, dayfirst: bool,
            debits_positive: bool | None) -> Extracted:
    out = Extracted()
    dates = pd.to_datetime(pd.Series([_cell(r, mapping["date"]) for r in data], dtype="object"),
                           errors="coerce", dayfirst=dayfirst, format="mixed")
    for row, when in zip(data, dates):
        if pd.isna(when):
            out.skipped_dates += 1
            continue
        if "debit" in mapping or "credit" in mapping:
            debit = parse_amount(_cell(row, mapping.get("debit")))
            credit = parse_amount(_cell(row, mapping.get("credit")))
            if debit:  # debit wins when both are filled
                amount, direction = abs(debit), "debit"
            elif credit:
                amount, direction = abs(credit), "credit"
            else:
                out.skipped_amounts += 1
                continue
        else:
            value = parse_amount(_cell(row, mapping["amount"]))
            if not value:
                out.skipped_amounts += 1
                continue
            direction = _direction_from_type(_cell(row, mapping.get("type"))) if "type" in mapping else None
            if direction is None:
                is_debit = value > 0 if debits_positive else value < 0
                direction = "debit" if is_debit else "credit"
            amount = abs(value)
        out.rows.append({
            "tx_date": when.date().isoformat(),
            "raw_description": _cell(row, mapping["description"]) or NO_DESCRIPTION,
            "amount": round(amount, 2),
            "direction": direction,
        })
    out.rows.sort(key=lambda r: r["tx_date"])  # stable: same-day rows keep file order
    return out


def validate_mapping(mapping: dict[str, int], width: int) -> dict[str, int]:
    clean = {}
    for role, col in mapping.items():
        if role not in ROLES:
            raise ImportProblem(422, f"Unknown column role {role!r}.")
        if not isinstance(col, int) or not 0 <= col < width:
            raise ImportProblem(422, f"Column {col!r} for {role} is outside the file.")
        clean[role] = col
    if len(set(clean.values())) != len(clean):
        raise ImportProblem(422, "Each column can only have one role.")
    missing = _missing(clean)
    if missing:
        raise ImportProblem(422, "Choose a column for: " + ", ".join(missing) + ".")
    return clean


@dataclass
class CommitResult:
    import_id: int
    rows: int  # appended to the database
    debits: int
    credits: int
    skipped_dates: int
    skipped_amounts: int
    skipped_overlap: int  # already covered by an earlier statement
    period_start: str
    period_end: str
    currency: str
    report_date: str


def commit(import_id: int, opts: dict | None = None, default_currency: str = "USD") -> CommitResult:
    """Store the rows of a pending import. `opts` (all optional): mapping, debits_positive, currency, dayfirst."""
    opts = opts or {}
    imp = db.get_import(import_id)
    if imp is None:
        raise ImportProblem(404, "That import doesn't exist.")
    if imp["status"] != "pending":
        raise ImportProblem(409, "That statement has already been imported.")
    raw = runtime.pending.get(import_id)
    if raw is None:
        raise ImportProblem(410, "SlothSpend restarted since you chose this file. Please choose it again.")

    parsed = parse(raw, imp["file_name"], default_currency)
    table = read_table(decode(raw))
    data = table[parsed.header_row + 1:]
    width = len(parsed.columns)
    mapping = validate_mapping({k: int(v) for k, v in (opts.get("mapping") or parsed.mapping).items()}, width)
    dayfirst = opts["dayfirst"] if opts.get("dayfirst") is not None else parsed.dayfirst
    currency = opts.get("currency") or parsed.currency
    debits_positive = opts.get("debits_positive")
    if debits_positive is None:
        debits_positive = parsed.debits_positive if opts.get("mapping") is None else (
            sign_from_amounts(data, mapping)[0])

    ext = extract(data, mapping, dayfirst=dayfirst, debits_positive=debits_positive)
    if not ext.rows:
        raise ImportProblem(422, "We couldn't find any dated rows. Is this a bank statement export?")

    latest = db.max_tx_date()
    new_rows = [r for r in ext.rows if latest is None or r["tx_date"] > latest]
    for r in new_rows:
        r["desc_key"] = desc_key(r["raw_description"])

    db.commit_import(import_id, new_rows, {
        "row_count": parsed.row_count,
        "skipped_rows": ext.skipped_dates + ext.skipped_amounts,
        "period_start": ext.rows[0]["tx_date"],
        "period_end": ext.rows[-1]["tx_date"],
        "currency": currency,
        "mapping": mapping,
        "header_row": parsed.header_row,
    })
    db.set_settings({layout_key(parsed.header): json.dumps(
        {"mapping": mapping, "debits_positive": debits_positive})})
    runtime.pending.pop(import_id, None)

    return CommitResult(
        import_id=import_id,
        rows=len(new_rows),
        debits=sum(r["direction"] == "debit" for r in new_rows),
        credits=sum(r["direction"] == "credit" for r in new_rows),
        skipped_dates=ext.skipped_dates,
        skipped_amounts=ext.skipped_amounts,
        skipped_overlap=len(ext.rows) - len(new_rows),
        period_start=ext.rows[0]["tx_date"],
        period_end=ext.rows[-1]["tx_date"],
        currency=currency,
        report_date=db.max_tx_date() or ext.rows[-1]["tx_date"],
    )
