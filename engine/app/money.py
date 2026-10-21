"""Money, date and word formatting for text the engine writes (summaries, reasons, notes).

Mirrors the renderer's lib/format.ts so the same number reads the same everywhere (IMPL §5.8).
Models never format numbers: code does, and passes the finished strings in.
"""

from datetime import date

SYMBOLS = {"USD": "$", "INR": "₹", "EUR": "€", "GBP": "£"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
               "October", "November", "December"]
WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"]


def _group_indian(whole: str) -> str:
    if len(whole) <= 3:
        return whole
    head, tail = whole[:-3], whole[-3:]
    pairs = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    if head:
        pairs.insert(0, head)
    return ",".join(pairs) + "," + tail


def money(amount: float, currency: str = "USD") -> str:
    """$1,979.86 · ₹1,18,450.20 · -$12.50"""
    sign = "-" if amount < 0 else ""
    whole, frac = f"{abs(amount):.2f}".split(".")
    grouped = _group_indian(whole) if currency == "INR" else f"{int(whole):,}"
    return f"{sign}{SYMBOLS.get(currency, currency + ' ')}{grouped}.{frac}"


def _d(value: date | str) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def date_long(value: date | str) -> str:
    """Nov 5, 2026"""
    d = _d(value)
    return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"


def date_short(value: date | str, ref_year: int | None = None) -> str:
    """Nov 5 — with the year only when it differs from ref_year."""
    d = _d(value)
    base = f"{MONTHS[d.month - 1]} {d.day}"
    return f"{base}, {d.year}" if ref_year is not None and d.year != ref_year else base


def month_name(value: date | str) -> str:
    return MONTH_NAMES[_d(value).month - 1]


def number_word(n: int) -> str:
    """Numbers up to twelve as words ("eight times"), larger ones as digits."""
    return WORDS[n] if 0 <= n < len(WORDS) else str(n)


def ordinal(n: int) -> str:
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def plural(n: int, word: str) -> str:
    return f"{number_word(n)} {word}{'' if n == 1 else 's'}"
