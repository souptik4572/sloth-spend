"""Sloth's summary (IMPL M4.7), money formatting and the drawer reasons (IMPL M4.5)."""

import asyncio
from types import SimpleNamespace

import pytest

from app import explain, llm_summary
from app.money import date_long, date_short, money, number_word, ordinal

FACTS = {"currency": "USD", "monthly_recurring": 1979.86, "monthly_subscriptions": 87.46,
         "creep": {"merchant": "IronTrap Fitness", "from": 39.99, "to": 49.99, "pct": 25.0, "since": "2026-07-05",
                   "duplicate_same_month": True},
         "overlap": {"category": "Streaming", "merchants": ["StreamFlix UHD", "WatchNest"]}}


def test_template_matches_the_design():
    assert llm_summary.template(FACTS) == (
        "You pay $1,979.86 a month in recurring charges, and $87.46 of that is subscriptions. "
        "IronTrap Fitness went from $39.99 to $49.99 in July and charged you twice that month. "
        "StreamFlix UHD and WatchNest are both streaming services, so you may only need one. "
        "Nothing has been cancelled — that’s your call.")


def test_rewrites_may_not_invent_numbers():
    ref = llm_summary.template(FACTS)
    assert llm_summary.acceptable("You spend $1,979.86 monthly; $87.46 is subscriptions. Nothing was cancelled.", ref)
    assert not llm_summary.acceptable("You could save $500 a year. Nothing was cancelled.", ref)
    assert not llm_summary.acceptable("You spend $1,979.86 monthly.", ref)  # must say nothing was cancelled


def test_gemma_rewrite_is_used_only_when_faithful(monkeypatch):
    def client_saying(text):
        async def chat(**kw):
            return SimpleNamespace(message=SimpleNamespace(content=text))
        return lambda **kw: SimpleNamespace(chat=chat)

    good = "Your recurring charges are $1,979.86 a month, $87.46 of it subscriptions. Nothing has been cancelled."
    monkeypatch.setattr("ollama.AsyncClient", client_saying(good))
    assert asyncio.run(llm_summary.write(FACTS, "gemma", "http://x")) == (good, "gemma")
    monkeypatch.setattr("ollama.AsyncClient", client_saying("You owe $9,999. Nothing has been cancelled."))
    assert asyncio.run(llm_summary.write(FACTS, "gemma", "http://x"))[1] == "template"
    assert asyncio.run(llm_summary.write(FACTS, None, "http://x"))[1] == "template"


@pytest.mark.parametrize(("amount", "currency", "text"), [
    (1979.86, "USD", "$1,979.86"), (118450.2, "INR", "₹1,18,450.20"), (1800, "INR", "₹1,800.00"),
    (-12.5, "USD", "-$12.50"), (9.99, "GBP", "£9.99"),
])
def test_money(amount, currency, text):
    assert money(amount, currency) == text


def test_dates_and_words():
    assert date_long("2026-11-05") == "Nov 5, 2026"
    assert date_short("2027-01-14", 2026) == "Jan 14, 2027" and date_short("2026-11-05", 2026) == "Nov 5"
    assert number_word(8) == "eight" and number_word(13) == "13"
    assert [ordinal(n) for n in (1, 2, 3, 5, 11, 22)] == ["1st", "2nd", "3rd", "5th", "11th", "22nd"]


def test_amount_lines():
    assert explain.amounts_line([15.49] * 12, "USD", False) == "The same $15.49 every time (12 of 12)."
    assert explain.amounts_line([10.99] * 4 + [11.99], "USD", False) == \
        "The same $10.99 four times in a row, then $11.99 for the last one."
    assert explain.amounts_line([88.1, 121.75, 71.25, 92.4, 139.8], "USD", True) == \
        "Amounts vary from $71.25 to $139.80."


def test_single_charge_reason():
    s = {"cadence": "single", "last_date": "2026-01-14", "category": "Cloud Storage", "status": "active"}
    txs = [{"tx_date": "2026-01-14", "amount": 119.88, "is_duplicate": 0}]
    lines = explain.reasons(s, txs, source="llm", subscription_like=True, currency="USD")
    assert lines[0] == "Charged once, on Jan 14, 2026. Could be an annual plan."
