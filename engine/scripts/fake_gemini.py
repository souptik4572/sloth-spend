"""A fake Gemini API for local testing (WEB-IMPL W4): run SlothSpend Web in Gemini mode without a key or network.

It answers the few calls SlothSpend makes — model lookups, generateContent, streamGenerateContent — with canned
replies shaped like Gemma's: merchant names (the sample statement's real ones, others title-cased), a function call
on the first Ask Sloth round, drafts handed back unchanged, reminder notes. Its prose says it is fake, so nothing
it writes can be mistaken for real Gemma output. The engine's Gemini tests use the same replies.

usage:
  engine/.venv/bin/python engine/scripts/fake_gemini.py [--port 8790]
  SLOTH_LLM_PROVIDER=gemini GEMINI_API_KEY=fake SLOTH_GEMINI_BASE_URL=http://127.0.0.1:8790 npm run web:api
"""

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

NAMES_FILE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "sample_merchant_map.json"
NAMES: dict = json.loads(NAMES_FILE.read_text()) if NAMES_FILE.exists() else {}
MODELS = ("gemma-4-26b-a4b-it", "gemma-4-31b-it")
ANSWER = "Here is what I found. (Fake Gemini for local testing.) Nothing has been cancelled."


def user_texts(body: dict) -> list[str]:
    return [p["text"] for c in body["contents"] if c["role"] == "user" for p in c["parts"] if "text" in p]


def reply_parts(body: dict) -> list[dict]:
    """What Gemma would say, by request shape."""
    texts = user_texts(body)
    last = texts[-1] if texts else ""
    answered = any("functionResponse" in p for c in body["contents"] for p in c["parts"])
    if "Lines:\n" in last:  # merchant names, wrapped in a fence like a chatty model would
        items = []
        for i, k in re.findall(r'^(\d+): (".*")$', last, re.M):
            key = json.loads(k)
            known = NAMES.get(key)
            items.append({"i": int(i), "m": known["merchant"] if known else key.title()[:30],
                          "c": known["category"] if known else "Other",
                          "s": known["subscription_like"] if known else False})
        return [{"text": "```json\n" + json.dumps({"items": items}) + "\n```"}]
    if "Notification to rephrase" in last:
        return [{"text": json.dumps({"title": "A reminder from SlothSpend",
                                     "body": "Open How to cancel in SlothSpend, or tap Keep it."})}]
    draft = re.search(r"^Subject:.*", last, re.M | re.S)
    if draft and "[Your name]" in last:  # a draft rewrite: hand the email back unchanged
        return [{"text": draft.group(0)}]
    if body.get("tools") and not answered:
        return [{"functionCall": {"name": "get_report_overview", "args": {}}}]
    return [{"text": "Weighing the numbers first.", "thought": True}, {"text": ANSWER}]


def response(parts: list[dict]) -> dict:
    return {"candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 7, "totalTokenCount": 18}}


def sse_body(parts: list[dict]) -> str:
    """streamGenerateContent?alt=sse: one event per part; the last carries usage, like the real API."""
    events = [{"candidates": [{"content": {"role": "model", "parts": [p]}}]} for p in parts]
    events[-1] = response([parts[-1]])
    return "".join(f"data: {json.dumps(e)}\r\n\r\n" for e in events)


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: str, content_type: str = "application/json") -> None:
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802 — http.server's naming
        m = re.fullmatch(r"/v1beta/models/([^/:?]+)", self.path)
        if m and m.group(1) in MODELS:
            self._send(200, json.dumps({"name": f"models/{m.group(1)}"}))
        else:
            self._send(404, json.dumps({"error": {"code": 404, "message": "not found"}}))

    def do_POST(self) -> None:  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        if re.search(r":streamGenerateContent", self.path):
            self._send(200, sse_body(reply_parts(body)), "text/event-stream")
        elif self.path.endswith(":generateContent"):
            self._send(200, json.dumps(response(reply_parts(body))))
        else:
            self._send(404, json.dumps({"error": {"code": 404, "message": "not found"}}))

    def log_message(self, fmt: str, *args) -> None:
        print("fake gemini:", fmt % args)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--port", type=int, default=8790)
    port = parser.parse_args().port
    print(f"Fake Gemini API on http://127.0.0.1:{port} — canned replies, for local testing only")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
