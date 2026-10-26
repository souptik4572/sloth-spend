"""Ask Sloth and drafts against real Gemma (WEB-IMPL W5). Exit code 0 = every check passed.

Runs the engine in-process on a fresh data folder with whichever provider is configured, audits the bundled sample,
then asks the five suggested prompts (src/renderer/src/lib/chat.ts) — each in its own conversation — and streams the
three email drafts. Checks per prompt:
  · the turn finishes (no error) with at least one visible tool call, and the tool the question needs;
  · grounded: every money amount in the answer appears in a tool result or in the facts Gemma was given;
  · no link or phone number survives the guard;
  · the reminder prompt really sets the reminder; the draft prompt returns an email the chat shows as a draft card.
Drafts must come from Gemma (not the template fallback) and pass the draft fact check.

usage:
  SLOTH_LLM_PROVIDER=ollama engine/.venv/bin/python engine/scripts/ask_eval.py            # local Gemma
  SLOTH_LLM_PROVIDER=gemini GEMINI_API_KEY=… engine/.venv/bin/python engine/scripts/ask_eval.py
  options: --runs N (ask every prompt N times; default 1) · --json results.json
"""

import argparse
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("SLOTH_DATA_DIR", tempfile.mkdtemp(prefix="sloth-ask-eval-"))
os.environ["SLOTH_TOKEN"] = "ask-eval"
os.environ["SLOTH_NO_WATCHDOG"] = "1"
os.environ.setdefault("SLOTH_TELEMETRY", "0")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app import db, drafts, guard, llm, tools, workspace  # noqa: E402
from app.main import app  # noqa: E402

AUTH = {"X-Sloth-Token": "ask-eval"}
PROMPTS = [  # the Try asking chips, in order (src/renderer/src/lib/chat.ts)
    ("why_flagged", "Why was IronTrap flagged, and did they ever double-charge me?",
     {"get_merchant", "find_duplicate_charges"}),
    ("what_if", "What will subscriptions cost next month if I cancel StreamFlix and WatchNest?", {"forecast_spend"}),
    ("category", "Which category grew the most this year?", {"spend_by_category"}),
    ("refund_draft", "Draft a refund request for the duplicate IronTrap charge.",
     {"get_merchant", "find_duplicate_charges"}),
    ("remind", "Remind me three days before IronTrap renews.", {"set_renewal_reminder"}),
]
MONEY = re.compile(r"[$₹€£]\s?\d[\d,]*(?:\.\d+)?|\b\d[\d,]*\.\d{2}\b")
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def amounts(text: str) -> set[float]:
    return {round(float(re.sub(r"[^\d.]", "", m)), 2) for m in MONEY.findall(text) if re.search(r"\d", m)}


def numbers(text: str) -> set[float]:
    out = set()
    for m in NUMBER.findall(text):
        try:
            out.add(round(float(m.replace(",", "")), 2))
        except ValueError:
            pass
    return out


def sse(client: TestClient, path: str, body: dict) -> list[tuple[str, dict]]:
    events, name = [], None
    with client.stream("POST", path, headers=AUTH, json=body) as r:
        if r.status_code != 200:
            return [("error", {"message": f"HTTP {r.status_code}: {r.read()[:200]!r}"})]
        for line in r.iter_lines():
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                events.append((name, json.loads(line[5:])))
    return events


def wait_for_tabpfn(client: TestClient, seconds: float = 180) -> str:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        t = client.get("/health", headers=AUTH).json()["tabpfn"]
        if t["status"] in ("ready", "unavailable", "error"):
            return t.get("model") or t["status"]
        time.sleep(1)
    return "still loading"


def ask(client: TestClient, key: str, prompt: str, needs: set[str], context: str, run: int) -> dict:
    cid = f"eval-{key}-{run}"
    started = time.perf_counter()
    events = sse(client, "/chat", {"conversation_id": cid, "message": prompt})
    seconds = time.perf_counter() - started
    answer = "".join(d["text"] for e, d in events if e == "token")
    replaced = [d["text"] for e, d in events if e == "replace"]
    final = replaced[-1] if replaced else answer
    called = [d["name"] for e, d in events if e == "tool_start"]
    errors = [d["message"] for e, d in events if e == "error"]
    history = client.get(f"/chat/{cid}", headers=AUTH).json()["messages"]
    sources = context + "\n" + "\n".join(m["content"] or "" for m in history if m["role"] == "tool")
    ungrounded = sorted(amounts(final) - numbers(sources))

    checks = {
        "finished": bool(events) and events[-1][0] == "done" and not errors,
        "tool call shown": bool(called),
        "right tool": bool(needs & set(called)),
        "grounded amounts": not ungrounded,
        "no links/phones": not guard.find_contacts(final) and "http" not in final.lower(),
    }
    if key == "category":  # the conclusion, not just the numbers: name the category the tool found
        found = [json.loads(m["content"]).get("grew_most", {}).get("category") for m in history
                 if m["role"] == "tool" and m["tool_name"] == "spend_by_category"]
        checks["names the category the tool found"] = bool(found) and str(found[-1]).lower() in final.lower()
    if key == "remind":
        reminders = client.get("/reminders", headers=AUTH).json()
        checks["reminder set"] = any("irontrap" in r["merchant"].lower() and r["phase"] == "WATCHING" for r in reminders)
    if key == "refund_draft":  # the chat pane's rule (splitDrafts): a fenced or plain "Subject: … [Your name]" email
        checks["email shown as a draft card"] = bool(re.search(r"^\s*\**Subject:[\s\S]*\[Your name\]", final, re.M))
    return {"key": key, "run": run, "prompt": prompt, "seconds": round(seconds, 1), "tools": called,
            "ungrounded": ungrounded, "errors": errors, "checks": checks, "answer": final,
            "tool_results": [m["content"] for m in history if m["role"] == "tool"]}


def draft(client: TestClient, series: dict, kind: str) -> dict:
    started = time.perf_counter()
    events = sse(client, f"/series/{series['id']}/draft", {"kind": kind})
    seconds = time.perf_counter() - started
    done = next((d for e, d in reversed(events) if e == "done"), {})
    reference = drafts.template(kind, drafts.facts(series["id"]))
    text = done.get("text", "")
    checks = {"written by Gemma (not the template)": done.get("source") == "gemma",
              "passes the fact check": bool(text) and drafts.acceptable(text, reference)}
    return {"key": f"draft:{kind}", "merchant": series["merchant"], "seconds": round(seconds, 1), "checks": checks,
            "answer": text}


def main() -> int:
    parser = argparse.ArgumentParser(description="Ask Sloth + drafts against real Gemma")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    with TestClient(app) as client:
        status = client.get("/health", headers=AUTH).json()["llm"]
        print(f"Gemma: {status['provider']} · {status['status']} · {status['model']}")
        if status["status"] != "ready":
            print(llm.unavailable_message(status["status"], status["provider"]))
            return 1
        print("TabPFN:", wait_for_tabpfn(client))
        started = time.perf_counter()
        done = sse(client, "/demo/load-sample", {"file": "main"})
        if done[-1][0] != "done":
            print("audit failed:", done[-1])
            return 1
        report = done[-1][1]["report"]
        print(f"audit: {time.perf_counter() - started:.1f}s · summary by {report['meta']['summary_source']} · "
              f"{len(report['series'])} series")

        with workspace.use(None):
            context = tools.overview_block()
        series = report["series"]
        iron = next(s for s in series if "irontrap" in s["merchant"].lower())
        bill = next(s for s in series if s["kind"] == "bill")
        context += "\n" + "\n".join(drafts.template(k, drafts.facts(iron["id"]))
                                    for k in ("refund", "cancel_request", "negotiate"))

        results = []
        for run in range(1, args.runs + 1):
            for key, prompt, needs in PROMPTS:
                if key == "remind":  # a second run would find the first reminder; start from none
                    for r in client.get("/reminders", headers=AUTH).json():
                        client.post(f"/reminders/{r['series_id']}/stop", headers=AUTH)
                results.append(ask(client, key, prompt, needs, context, run))
        for s, kind in ((iron, "cancel_request"), (iron, "refund"), (bill, "negotiate")):
            results.append(draft(client, s, kind))

    failed = 0
    for r in results:
        bad = [name for name, ok in r["checks"].items() if not ok]
        failed += bool(bad)
        label = r.get("prompt") or f"{r['key']} ({r['merchant']})"
        extra = f" · tools: {', '.join(r['tools'])}" if r.get("tools") is not None else ""
        if r.get("ungrounded"):
            extra += f" · ungrounded amounts: {r['ungrounded']}"
        if r.get("errors"):
            extra += f" · error: {r['errors'][0]}"
        print(f"{'ok  ' if not bad else 'FAIL'} {label} [{r['seconds']}s]{extra}" + (f" · failed: {bad}" if bad else ""))
        print("     " + " ".join(r["answer"].split())[:240])
    if args.json:
        args.json.write_text(json.dumps({"model": status, "results": results}, indent=2, default=str))
    print(f"\n{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    with workspace.use(None):
        db.init()
    sys.exit(main())
