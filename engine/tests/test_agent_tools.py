"""Ask Sloth (IMPL M6.11): every tool against the audited sample (heuristic scorer), the read-only SQL guard,
the drafts' templates and safety net, and one agent turn against a scripted stand-in for Gemma."""

import asyncio
import json
import re
from types import SimpleNamespace

import pytest
from conftest import sse

from app import agent, db, drafts, guard, ollama_setup, tools


def run(name: str, **args) -> dict:
    return json.loads(asyncio.run(tools.execute(name, args)))


# ── tools ───────────────────────────────────────────────────────────────────

def test_overview(sample_report):
    out = run("get_report_overview")
    assert out["monthly_recurring"] == pytest.approx(1979.86) and out["currency"] == "USD"
    assert out["top_findings"][1]["merchant"] == "IronTrap Fitness"
    block = tools.overview_block()
    assert len(block) <= tools.OVERVIEW_LIMIT
    assert "$1,979.86" in block and "IronTrap Fitness · Fitness · monthly · $49.99" in block
    assert "price rise" in block and "price_creep" not in block


def test_get_merchant_fuzzy(sample_report):
    out = run("get_merchant", merchant="irontrap")
    assert out["merchant"] == "IronTrap Fitness"
    assert out["flags"] == ["double charge", "price rise", "zombie suspect"]
    assert out["flag_details"]["price rise"]["from"] == 39.99
    assert out["next_due"] == "Nov 5, 2026" and len(out["recent_charges"]) == 12
    assert run("get_merchant", merchant="Streamflix")["merchant"] == "StreamFlix UHD"
    assert run("get_merchant", merchant="Tunetide Music")["merchant"] == "TuneTide"
    missing = run("get_merchant", merchant="Zzyzx Rentals")
    assert "error" in missing and "IronTrap Fitness" in missing["known_merchants"]


def test_get_merchant_one_off(sample_report):
    out = run("get_merchant", merchant="Copper Grill")
    assert out["recurring"] is False and out["n_charges"] >= 1


def test_find_duplicate_charges(sample_report):
    out = run("find_duplicate_charges", merchant="IronTrap")
    assert [(p["first"], p["second"], p["amount"]) for p in out["pairs"]] == [("Jul 5, 2026", "Jul 6, 2026", 49.99)]
    everywhere = run("find_duplicate_charges")
    assert everywhere["total_to_dispute"] == pytest.approx(49.99)


def test_spend_by_category(sample_report):
    out = run("spend_by_category", start_date="2025-11-01", end_date="2026-10-15")
    cats = {c["category"]: c for c in out["categories"]}
    assert cats["Housing"]["total"] == pytest.approx(1800 * 12)
    assert "2026-10" in cats["Housing"]["by_month"]
    assert out["grew_most"]["category"] in cats
    assert out["grew_most"]["compared"].endswith("2026-09")  # October is partial: left out of the trend


def test_forecast_spend_what_if(sample_report):
    out = run("forecast_spend", exclude_merchants=["StreamFlix UHD", "WatchNest"])
    assert out["excluded"] == ["StreamFlix UHD", "WatchNest"]
    assert out["scope"] == "subscriptions only"
    assert out["baseline"]["q50"] == pytest.approx(87.46)
    assert out["delta_q50"] == pytest.approx(-25.48)
    everything = run("forecast_spend", exclude_merchants=["StreamFlix UHD"], scope="all")
    assert everything["baseline"]["q50"] > 1900 and everything["delta_q50"] == pytest.approx(-15.49)
    assert out["model"] == "heuristic" and out["window"] == ["Oct 15, 2026", "Nov 14, 2026"]
    lenient = run("forecast_spend", days="30", exclude_merchants="streamflix, Nonesuch")
    assert lenient["excluded"] == ["StreamFlix UHD"] and lenient["not_found"] == ["Nonesuch"]


def test_score_merchant(sample_report):
    out = run("score_merchant", merchant="WatchNest")
    assert out["recurring_prob"] >= 0.7 and out["model"] == "heuristic"
    assert out["looks_like"]["k"] == 5
    assert "error" in run("score_merchant", merchant="CloudBox Pro")  # charged once


def test_readonly_sql(sample_report):
    out = run("run_readonly_sql", query="SELECT merchant, last_amount FROM series ORDER BY merchant")
    assert out["columns"] == ["merchant", "last_amount"] and len(out["rows"]) == 9
    assert len(tools.run_readonly_sql("SELECT * FROM transactions")["rows"]) == 50  # the cap
    trimmed = run("run_readonly_sql", query="SELECT * FROM transactions")  # then the 4,000-char budget
    assert trimmed["truncated"] and 0 < len(trimmed["rows"]) < 50
    cte = run("run_readonly_sql", query="WITH t AS (SELECT 1 AS x) SELECT x FROM t")
    assert cte["rows"] == [[1]]
    for bad in ("DELETE FROM transactions", "SELECT 1; DELETE FROM transactions",
                "PRAGMA journal_mode = DELETE", "UPDATE series SET status = 'keep'"):
        assert "error" in run("run_readonly_sql", query=bad), bad
    sneaky = run("run_readonly_sql", query="WITH x AS (SELECT 1) DELETE FROM transactions")
    assert "error" in sneaky
    assert run("run_readonly_sql", query="SELECT COUNT(*) FROM transactions")["rows"][0][0] > 400


@pytest.fixture()
def oct16(monkeypatch):
    """The sample's world: the day after the statement ends."""
    from datetime import datetime, timezone

    from app import reminders

    monkeypatch.setattr(reminders, "now_utc", lambda: datetime(2026, 10, 16, 12, tzinfo=timezone.utc))


def test_reminder_tool(sample_report, oct16):
    out = run("set_renewal_reminder", merchant="IronTrap", days_before=3)
    assert out["reminder_set"] is True and out["remind_on"] == "Nov 2, 2026" and out["days_before"] == 3
    again = run("set_renewal_reminder", merchant="IronTrap", days_before=5)  # WATCHING: re-timed
    assert again["reminder_set"] is True and again["remind_on"] == "Oct 31, 2026"
    iron = next(s for s in sample_report["series"] if s["merchant"] == "IronTrap Fitness")
    db.transition(iron["id"], "WATCHING", "REMINDED")
    busy = run("set_renewal_reminder", merchant="IronTrap")
    assert busy["reminder_set"] is False and "already has one in progress (reminded)" in busy["error"]
    assert run("set_renewal_reminder", merchant="FreshCart")["reminder_set"] is False  # no renewal date


def test_execute_never_raises(sample_report):
    assert "error" in run("nope")
    assert "Missing argument" in run("get_merchant")["error"]
    assert len(asyncio.run(tools.execute("run_readonly_sql", {"query": "SELECT * FROM transactions"}))) <= 4000


def test_prefetch_finds_named_merchants(sample_report):
    names = [s["merchant"] for s in tools.mentioned_merchants(
        "Why was IronTrap flagged, and what if I cancel StreamFlix and Watchnest?")]
    assert names == ["IronTrap Fitness", "StreamFlix UHD", "WatchNest"]
    assert tools.mentioned_merchants("Which category grew the most this year?") == []
    assert [s["merchant"] for s in tools.mentioned_merchants("Cancel Irontrap for me")] == ["IronTrap Fitness"]


# ── drafts ──────────────────────────────────────────────────────────────────

PHONE_LIKE = re.compile(r"\d[\d\s().-]{6,}\d")


@pytest.mark.parametrize("merchant,kind", [("IronTrap Fitness", "cancel_request"), ("IronTrap Fitness", "refund"),
                                           ("Metro Electric", "negotiate"), ("Rent transfer", "negotiate"),
                                           ("CloudBox Pro", "cancel_request")])
def test_templates_are_safe(sample_report, merchant, kind):
    s = next(x for x in sample_report["series"] if x["merchant"] == merchant)
    text = drafts.template(kind, drafts.facts(s["id"]))
    assert text.startswith("Subject: ") and text.endswith("Thank you,\n[Your name]")
    assert "http" not in text and not guard.find_contacts(text)
    assert not [m for m in PHONE_LIKE.findall(text) if not re.search(r"\d{4}", m)]


def test_template_shapes(sample_report):
    iron = next(x for x in sample_report["series"] if x["merchant"] == "IronTrap Fitness")
    f = drafts.facts(iron["id"])
    assert drafts.template("cancel_request", f) == (
        "Subject: Please cancel my IronTrap Fitness membership\n\nHello IronTrap Fitness team,\n\n"
        "Please cancel my membership and stop all future charges, including the renewal due on Nov 5, 2026. "
        "I have been charged $49.99 a month, most recently on Oct 5, 2026.\n\n"
        "Please confirm the cancellation by email.\n\nThank you,\n[Your name]")
    assert drafts.template("refund", f) == (
        "Subject: Refund for duplicate IronTrap Fitness charge on Jul 6, 2026\n\nHello IronTrap Fitness team,\n\n"
        "I was charged $49.99 twice in July, on Jul 5 and Jul 6, 2026. Please refund the Jul 6 charge.\n\n"
        "Thank you,\n[Your name]")
    late = {**f, "still_charged": {"cancelled_on": "2026-10-16", "date": "2026-11-05", "amount": 49.99}}
    assert drafts.template("refund", late).split("\n\n")[2:4] == [
        "I cancelled on Oct 16, 2026, but my card was charged $49.99 on Nov 5, 2026. Please refund this charge "
        "and confirm that no further charges will be made.",
        "I was also charged $49.99 twice in July, on Jul 5 and Jul 6, 2026. Please refund the Jul 6 charge too."]


def test_gemma_draft_must_keep_the_facts():
    reference = drafts.template("refund", {
        "merchant": "IronTrap Fitness", "currency": "USD", "still_charged": None, "last_amount": 49.99,
        "last_date": "2026-10-05", "duplicates": [{"first": "2026-07-05", "second": "2026-07-06", "amount": 49.99}]})
    good = reference.replace("Please refund", "Could you please refund")
    assert drafts.acceptable(good, reference)
    assert not drafts.acceptable(good.replace("$49.99 twice", "$59.99 twice"), reference)  # invented amount
    assert not drafts.acceptable(good + "\nCall 1-800-555-0199.", reference)
    assert not drafts.acceptable("Hi there,\n" + good, reference)  # lost the subject line
    assert drafts.tidy("```\n" + good + "\n```") == good


def test_draft_endpoint_without_gemma(client, auth, sample_report):
    iron = next(x for x in sample_report["series"] if x["merchant"] == "IronTrap Fitness")
    events = sse(client, f"/series/{iron['id']}/draft", {"kind": "cancel_request"})
    assert [e for e, _ in events] == ["done"]
    done = events[-1][1]
    assert done["source"] == "template" and done["title"] == "Cancellation request"
    assert done["text"].startswith("Subject: Please cancel my IronTrap Fitness membership")
    assert client.post("/series/9999/draft", headers=auth, json={"kind": "refund"}).status_code == 404


# ── the agent ───────────────────────────────────────────────────────────────

def part(content: str = "", calls: list | None = None, done: bool = False) -> SimpleNamespace:
    tool_calls = [SimpleNamespace(function=SimpleNamespace(name=n, arguments=a)) for n, a in (calls or [])]
    return SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls or None), done=done,
                           prompt_eval_count=10, eval_count=5)


class ScriptedGemma:
    """Round 1 asks for get_merchant, round 2 answers (by default with an invented phone number to scrub)."""
    seen: list[list[dict]] = []
    reply = ("IronTrap went from $39.99 to $49.99. ", "Call 1-800-555-0199 to cancel.")

    def __init__(self, host=None, **_):
        pass

    async def chat(self, *, messages, tools=None, **_):
        ScriptedGemma.seen.append(list(messages))
        rounds = len(ScriptedGemma.seen)

        async def gen():
            if rounds == 1:
                yield part(calls=[("get_merchant", {"merchant": "IronTrap"})], done=True)
            else:
                for piece in ScriptedGemma.reply:
                    yield part(piece)
                yield part(done=True)
        return gen()


@pytest.fixture()
def gemma_ready(monkeypatch):
    import ollama

    async def ready(host, preferred):
        return {"status": "ready", "model": "gemma4:e4b"}

    ScriptedGemma.seen = []
    monkeypatch.setattr(ScriptedGemma, "reply", ScriptedGemma.reply)  # restored after each test
    monkeypatch.setattr(ollama_setup, "status", ready)
    monkeypatch.setattr(ollama, "AsyncClient", ScriptedGemma)


def test_agent_turn(client, auth, sample_report, gemma_ready):
    events = sse(client, "/chat", {"conversation_id": "c1", "message": "Why was IronTrap flagged?"})
    names = [e for e, _ in events]
    # The pre-fetch is a real lookup, so it shows first (spec §7.9); then Gemma's own call.
    assert events[0][1] == {"name": "get_merchant", "args": {"merchant": "IronTrap Fitness"}}
    assert events[2][1] == {"name": "get_merchant", "args": {"merchant": "IronTrap"}}
    end = events[3][1]
    assert names[:4] == ["tool_start", "tool_end", "tool_start", "tool_end"]
    assert end["name"] == "get_merchant" and "IronTrap Fitness" in end["preview"] and "live" not in end
    assert names[-2:] == ["replace", "done"]
    assert "1-800" not in events[-2][1]["text"] and "the number on your receipt" in events[-2][1]["text"]

    first_prompt = ScriptedGemma.seen[0]
    assert first_prompt[0]["role"] == "system" and "$1,979.86" in first_prompt[0]["content"]
    assert first_prompt[1]["content"].startswith("Facts already looked up:")  # prefetch (spec §7.9)
    assert ScriptedGemma.seen[1][-1]["role"] == "tool" and ScriptedGemma.seen[1][-1]["tool_name"] == "get_merchant"

    hist = client.get("/chat/c1", headers=auth).json()["messages"]
    assert [m["role"] for m in hist] == ["user", "tool", "tool", "assistant"]
    assert hist[2]["tool_name"] == "get_merchant" and hist[2]["tool_args"] == {"merchant": "IronTrap"}
    assert "1-800" not in hist[3]["content"]


def test_agent_without_ollama(client, sample_report):
    events = sse(client, "/chat", {"conversation_id": "c2", "message": "hello"})
    assert events == [("error", {"message": "Gemma isn't running. Start Ollama, then try again."})]


def test_draft_requests_start_from_the_template(client, sample_report, gemma_ready):
    assert agent.draft_kind("Cancel IronTrap for me") == "cancel_request"
    assert agent.draft_kind("Draft a refund request for the duplicate IronTrap charge.") == "refund"
    assert agent.draft_kind("Can you negotiate a lower rate with Metro?") == "negotiate"
    assert agent.draft_kind("Why was IronTrap flagged?") is None
    assert agent.draft_kind("What will subscriptions cost if I cancel StreamFlix and WatchNest?") is None
    sse(client, "/chat", {"conversation_id": "c3", "message": "Draft a refund request for the duplicate IronTrap charge."})
    facts = ScriptedGemma.seen[0][1]["content"]
    assert "Ready-made refund request for IronTrap Fitness" in facts
    assert "Please refund the Jul 6 charge." in facts


def test_remind_me_runs_the_reminder_tool_first(client, sample_report, gemma_ready, oct16):
    assert agent.reminder_days("Remind me three days before IronTrap renews.") == 3
    assert agent.reminder_days("remind me a week before") == 7
    assert agent.reminder_days("Remind me 2 days before") == 2
    assert agent.reminder_days("Remind me before it renews") == 3
    ScriptedGemma.reply = ("Done! I've set a reminder for you three days before IronTrap renews.",)
    events = sse(client, "/chat", {"conversation_id": "c4", "message": "Remind me three days before IronTrap renews."})
    starts = [d for e, d in events if e == "tool_start"]
    assert starts[1] == {"name": "set_renewal_reminder", "args": {"merchant": "IronTrap Fitness", "days_before": 3}}
    facts = ScriptedGemma.seen[0][1]["content"]
    assert "Report this result exactly" in facts and '"reminder_set": true' in facts
    assert "Ready-made" not in facts  # a reminder request isn't a draft request
    assert [e for e, _ in events][-1] == "done" and "replace" not in [e for e, _ in events]  # true claim stays

    # Now the reminder is in progress, so asking again sets nothing: the same claim gets replaced.
    iron = next(s for s in sample_report["series"] if s["merchant"] == "IronTrap Fitness")
    db.transition(iron["id"], "WATCHING", "REMINDED")
    ScriptedGemma.seen = []
    events = sse(client, "/chat", {"conversation_id": "c4", "message": "Remind me three days before IronTrap renews."})
    assert events[-2] == ("replace", {"text": "No new reminder was set: IronTrap Fitness already has one in progress "
                                              "(reminded). See the Reminders tab. IronTrap Fitness’s next charge is "
                                              "due Nov 5, 2026. Nothing has been cancelled."})
