"""Ask Sloth (spec §7.9, IMPL M6.2): Gemma with eight typed tools, streamed over SSE and kept in SQLite.

Events: token {text} · tool_start {name, args} · tool_end {name, ms, preview, live?} · replace {text}
(the answer had a link or phone number scrubbed) · done {rounds} · error {message}.
"""

import asyncio
import json
import logging
import re
import time
from collections.abc import AsyncIterator

import sentry_sdk

from . import db, drafts, guard, llm, tools, workspace
from .config import settings
from .tabular import tabular

log = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 4
HISTORY = 12
OPTIONS = {"num_ctx": 16384, "temperature": 0.3}  # num_ctx only matters to Ollama

LOCAL_ONLY = " Everything runs on this computer."  # true on the desktop with local Ollama only
SYSTEM_PROMPT = """You are Sloth, the calm assistant inside SlothSpend. Everything runs on this computer.
Rules:
- Ground every number in a tool result or the facts provided. Never invent amounts or dates.
- Use get_merchant / find_duplicate_charges for questions about a specific merchant.
- Use forecast_spend for future-spend and "what if I cancel" questions.
- SlothSpend never cancels subscriptions or contacts merchants, and neither do you. When the user wants to
  cancel, help them do it themselves: offer set_renewal_reminder and a cancellation-request email draft.
- Never invent cancellation links, phone numbers or merchant-specific steps. Point to the receipt email,
  the merchant's account or billing settings, or the app store's subscriptions page.
- For refund, cancellation or negotiation emails: short, polite, firm; cite exact dates and amounts.
- Put any email draft in a fenced code block whose first line starts with 'Subject:'. Nothing else goes in that block.
- Use the report currency. Keep answers brief and relaxed.
- Call tools with sensible defaults (leave optional arguments out) instead of asking the user for details you can
  look up. Write dates and amounts exactly as the tools give them.
- If a tool returns an error, say plainly what did not happen. Never say something was done unless a tool result
  confirms it."""

# A draft request gets the code-written template as a starting point (exact facts, no invented details).
DRAFT_INTENTS = [("refund", re.compile(r"\brefund", re.I)),
                 ("negotiate", re.compile(r"negotiat|\b(lower|better) (rate|price|bill|deal)", re.I)),
                 ("cancel_request", re.compile(r"\bcancel", re.I))]


HYPOTHETICAL = re.compile(r"\bwhat if\b|\bif (i|we) (cancel|stop|drop)", re.I)


def draft_kind(text: str) -> str | None:
    """Which email the user is asking for, if any. "What if I cancel X" is a forecast question, not a request."""
    kind = next((kind for kind, pattern in DRAFT_INTENTS if pattern.search(text)), None)
    return None if kind == "cancel_request" and HYPOTHETICAL.search(text) else kind


# "Remind me …" is an instruction, not a question: a small model may answer "done" without calling the tool,
# so the reminder is set before Gemma answers and Gemma reports the result (it only ever reminds).
REMIND = re.compile(r"\bremind me\b", re.I)
DAYS = re.compile(r"\b(\d{1,2}|one|two|three|four|five|six|seven|a)\s+(days?|weeks?)\b", re.I)
NUMBERS = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}


def reminder_days(text: str) -> int:
    m = DAYS.search(text)
    if not m:
        return 3
    n = int(m.group(1)) if m.group(1).isdigit() else NUMBERS[m.group(1).lower()]
    return n * 7 if m.group(2).lower().startswith("week") else n

def honest_reminder(results: list[str]) -> str:
    """Replaces an answer that claimed a reminder no tool set: say what actually happened."""
    try:
        last = json.loads(results[-1]) if results else {}
    except ValueError:
        last = {}
    text = last.get("error") or "No reminder was set."
    if last.get("next_charge_due"):
        text += f" {last.get('merchant', 'The')}’s next charge is due {last['next_charge_due']}."
    return text + " Nothing has been cancelled."


def _attr(span, key, value) -> None:
    setter = getattr(span, "set_attribute", None) or span.set_data
    setter(key, value)


def _ev(event: str, **data) -> dict:
    return {"event": event, "data": json.dumps(data, default=str)}


async def run_turn(conversation_id: str, user_text: str) -> AsyncIterator[dict]:
    provider = llm.provider()
    status = await provider.status(settings.preferred_model)
    if status["status"] != "ready":
        yield _ev("error", message=llm.unavailable_message(status["status"], provider.name))
        return
    model = status["model"]

    local = provider.name == "ollama" and not workspace.on_web()
    system = SYSTEM_PROMPT if local else SYSTEM_PROMPT.replace(LOCAL_ONLY, "", 1)
    messages = [{"role": "system", "content": system + "\n\n" + await asyncio.to_thread(tools.overview_block)}]
    messages += await asyncio.to_thread(db.load_chat, conversation_id, HISTORY)
    await asyncio.to_thread(db.save_chat, conversation_id, "user", user_text)

    # Context pre-fetch (spec §7.9): a small model answers far better with the named merchants' facts in
    # hand, even when it skips a tool call. It is a real get_merchant call, so it shows as a badge too.
    facts, reminders = [], []
    merchants = await asyncio.to_thread(tools.mentioned_merchants, user_text)
    for s in merchants:
        args = {"merchant": s["merchant"]}
        yield _ev("tool_start", name="get_merchant", args=args)
        started = time.perf_counter()
        output = await tools.execute("get_merchant", args)
        await asyncio.to_thread(db.save_chat, conversation_id, "tool", output, tool_name="get_merchant",
                                tool_args=args)
        yield _ev("tool_end", name="get_merchant", ms=int((time.perf_counter() - started) * 1000),
                  preview=output[:300])
        facts.append(output)
    if REMIND.search(user_text) and merchants:
        args = {"merchant": merchants[0]["merchant"], "days_before": reminder_days(user_text)}
        yield _ev("tool_start", name="set_renewal_reminder", args=args)
        started = time.perf_counter()
        output = await tools.execute("set_renewal_reminder", args)
        await asyncio.to_thread(db.save_chat, conversation_id, "tool", output, tool_name="set_renewal_reminder",
                                tool_args=args)
        yield _ev("tool_end", name="set_renewal_reminder", ms=int((time.perf_counter() - started) * 1000),
                  preview=output[:300])
        reminders.append(output)
        # Just done for this message (not earlier): "already" made a small model say "is already set".
        facts.append("SlothSpend just tried to set the reminder the user asked for in this message. Tell them what "
                     f"happened, using only this result:\n{output}")
    kind = None if REMIND.search(user_text) else draft_kind(user_text)
    if kind and merchants:
        s = merchants[0]
        template = await asyncio.to_thread(lambda: drafts.template(kind, drafts.facts(s["id"])))
        if kind == "cancel_request":
            ask = ("The user wants to cancel. Say plainly that SlothSpend can't cancel for them, point to where "
                   "they can do it themselves, offer a renewal reminder, and include this ready-made cancellation "
                   "request in a fenced block, changing only the tone:")
        else:
            ask = (f"Ready-made {drafts.TITLES[kind].lower()} for {s['merchant']}, written from the report. "
                   "If the user wants this email, use it in a fenced block, changing only the tone:")
        facts.append(f"{ask}\n{template}")
    if facts:
        messages.append({"role": "system", "content": "Facts already looked up:\n" + "\n".join(facts)})
    messages.append({"role": "user", "content": user_text})

    with sentry_sdk.start_span(op="gen_ai.invoke_agent", name="invoke_agent Ask Sloth") as agent_span:
        _attr(agent_span, "gen_ai.operation.name", "invoke_agent")
        _attr(agent_span, "gen_ai.agent.name", "Ask Sloth")
        _attr(agent_span, "gen_ai.conversation.id", conversation_id)

        answer = ""
        for round_no in range(MAX_TOOL_ROUNDS + 1):
            content, calls = "", []
            try:
                with sentry_sdk.start_span(op="gen_ai.chat", name=f"chat {model}") as span:
                    _attr(span, "gen_ai.operation.name", "chat")
                    _attr(span, "gen_ai.provider.name", provider.name)
                    _attr(span, "gen_ai.request.model", model)
                    stream = provider.stream(
                        model, messages, tools=tools.SCHEMAS if round_no < MAX_TOOL_ROUNDS else None,
                        timeout=None, **OPTIONS)
                    async for part in stream:
                        if part.text:
                            content += part.text
                            yield _ev("token", text=part.text)
                        calls.extend(part.tool_calls)
                        if part.done:
                            _attr(span, "gen_ai.usage.input_tokens", part.input_tokens)
                            _attr(span, "gen_ai.usage.output_tokens", part.output_tokens)
            except Exception as exc:  # noqa: BLE001 — Gemma went away mid-answer
                log.warning("Ask Sloth: Gemma failed (%s)", exc)
                yield _ev("error", message=llm.unavailable_message(llm.status_of(exc), provider.name))
                return

            answer += content
            if not calls:
                clean = guard.scrub(answer)
                if guard.claims_reminder(clean) and not any('"reminder_set": true' in r for r in reminders):
                    clean = honest_reminder(reminders)
                if clean != answer:
                    yield _ev("replace", text=clean)
                await asyncio.to_thread(db.save_chat, conversation_id, "assistant", clean)
                yield _ev("done", rounds=round_no)
                return

            messages.append({
                "role": "assistant", "content": content,
                "tool_calls": [{"function": {"name": c.name, "arguments": c.arguments}} for c in calls],
            })
            for c in calls:
                name, args = c.name, dict(c.arguments)
                yield _ev("tool_start", name=name, args=args)
                started = time.perf_counter()
                with sentry_sdk.start_span(op="gen_ai.execute_tool", name=f"execute_tool {name}") as tspan:
                    _attr(tspan, "gen_ai.operation.name", "execute_tool")
                    _attr(tspan, "gen_ai.tool.name", name)
                    output = await tools.execute(name, args)
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                await asyncio.to_thread(db.save_chat, conversation_id, "tool", output, tool_name=name, tool_args=args)
                if name == "set_renewal_reminder":
                    reminders.append(output)
                end = {"name": name, "ms": elapsed_ms, "preview": output[:300]}
                if name in tools.LIVE_TOOLS:
                    end["live"] = tabular.scorer
                yield _ev("tool_end", **end)
                messages.append({"role": "tool", "tool_name": name, "content": output})
