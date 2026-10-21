"""Merchant normalisation (IMPL M4.1): priority order, time budget, cache precedence, rule fallback."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from app import db, normalize
from app.normalize import KeyStat, Normalizer, rule_fallback


def run(norm: Normalizer) -> list[tuple[int, int]]:
    async def collect():
        return [p async for p in norm.run()]
    return asyncio.run(collect())


class FakeClient:
    """Answers like Gemma would; `drop` leaves some indexes out, `bad` returns broken JSON."""

    def __init__(self, drop=(), bad=False):
        self.calls, self.drop, self.bad = 0, set(drop), bad

    async def chat(self, model, messages, **kw):
        self.calls += 1
        if self.bad:
            return SimpleNamespace(message=SimpleNamespace(content="{not json"))
        lines = messages[0]["content"].split("Lines:\n")[1].splitlines()
        items = [{"i": i, "m": json.loads(line.split(": ", 1)[1]).title(), "c": "Streaming", "s": True}
                 for i, line in enumerate(lines) if i not in self.drop]
        return SimpleNamespace(message=SimpleNamespace(content=json.dumps({"items": items})))


def test_prioritise_repeating_then_large_one_offs():
    stats = [KeyStat("COFFEE ONCE", 1, 4.5, 4.5), KeyStat("BIG ONE OFF", 1, 300, 300),
             KeyStat("NETFLIX", 12, 186, 15.49), KeyStat("RENT", 12, 21600, 1800), KeyStat("MID", 1, 40, 40)]
    assert normalize.prioritise(stats) == ["RENT", "NETFLIX", "BIG ONE OFF", "MID", "COFFEE ONCE"]


def test_batch_fills_gaps_with_the_rule():
    keys = ["STREAMFLIX UHD SUBSCR", "SQ *COPPER KITCHEN"]
    out = asyncio.run(normalize.normalize_batch(FakeClient(drop={1}), "m", keys))
    assert out[keys[0]]["source"] == "llm" and out[keys[0]]["category"] == "Streaming"
    assert out[keys[1]] == rule_fallback(keys[1])
    broken = asyncio.run(normalize.normalize_batch(FakeClient(bad=True), "m", keys))
    assert all(v["source"] == "rule" for v in broken.values())


def test_without_gemma_everything_gets_the_rule():
    stats = [KeyStat(f"SHOP {i}", 1, 10, 10) for i in range(3)]
    progress = run(Normalizer(stats, model=None))
    assert progress[-1] == (3, 3)
    assert {e["source"] for e in db.merchant_map_get([s.key for s in stats]).values()} == {"rule"}


def test_budget_defers_the_rest_to_the_background(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr("ollama.AsyncClient", lambda **kw: client)
    stats = [KeyStat(f"SHOP {i:03}", 2 if i < 30 else 1, 100 - i, 50) for i in range(60)]
    norm = Normalizer(stats, model="gemma", budget_seconds=-1)  # budget already spent after the first check
    progress = run(norm)
    assert progress[-1] == (60, 60) and client.calls == 0
    assert len(norm.deferred) == 60 and norm.deferred[0] == "SHOP 000"  # highest priority first

    norm = Normalizer(stats, model="gemma", budget_seconds=60)
    run(norm)
    assert client.calls == 3 and norm.deferred == [] and norm.llm_named == 60  # rule entries retried


def test_cache_and_user_edits_win():
    db.merchant_map_upsert({"NETFLIX": {"merchant": "My Netflix", "category": "Streaming",
                                        "subscription_like": True, "source": "user"}})
    db.merchant_map_upsert({"NETFLIX": {"merchant": "Netflix", "category": "Other",
                                        "subscription_like": False, "source": "llm"}})
    assert db.merchant_map_get(["NETFLIX"])["NETFLIX"]["merchant"] == "My Netflix"
    db.merchant_map_upsert({"SPOTIFY": {"merchant": "Spotify", "category": "Music",
                                        "subscription_like": True, "source": "llm"}})
    db.merchant_map_upsert({"SPOTIFY": rule_fallback("SPOTIFY")})
    assert db.merchant_map_get(["SPOTIFY"])["SPOTIFY"]["source"] == "llm"  # the rule never downgrades Gemma


def test_finish_deferred_upgrades_rule_names(monkeypatch):
    monkeypatch.setattr("ollama.AsyncClient", lambda **kw: FakeClient())
    db.merchant_map_upsert({"OLIVE BAKERY": rule_fallback("OLIVE BAKERY")})
    named = asyncio.run(normalize.finish_deferred(["OLIVE BAKERY"], "gemma", "http://x"))
    assert named == 1 and db.merchant_map_get(["OLIVE BAKERY"])["OLIVE BAKERY"]["source"] == "llm"


@pytest.mark.parametrize(("key", "name"), [
    ("SQ *COPPER KITCHEN", "Copper Kitchen"), ("SQ *COPPER GRILL", "Copper Grill"),
    ("TST* OLIVE BAKERY", "Olive Bakery"), ("SQ *BEANTHERE COFFEE", "Beanthere Coffee"),
    ("BEANTHERE COFFEE", "Beanthere Coffee"), ("FOX & PINE TOYS", "Fox & Pine Toys"),
    ("WATCHNEST*MONTHLY", "Watchnest Monthly"),
])
def test_rule_fallback_keeps_shops_apart(key, name):
    assert rule_fallback(key)["merchant"] == name
