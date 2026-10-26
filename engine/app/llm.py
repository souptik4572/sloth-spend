"""Who serves Gemma (WEB-IMPL §2.1): local Ollama (desktop, local dev) or the Gemini API (the web).

Callers speak one shape — the engine's Ollama-style messages and tool schemas — and get back plain text
(`complete`) or streamed `Chunk`s with text and tool calls (`stream`). The Gemini provider translates on the
way in and out, retries patiently on 429 (slow and steady), and never lets thought parts reach the user.
Every caller already falls back to a template when a call raises, so a failure here never breaks a feature.
"""

import asyncio
import json
import logging
import re
import time
import weakref
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import httpx

from . import ollama_setup
from .config import settings

log = logging.getLogger(__name__)


@dataclass
class ToolCall:
    name: str
    arguments: dict


@dataclass
class Chunk:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    done: bool = False
    input_tokens: int = 0
    output_tokens: int = 0


# What Ask Sloth says when Gemma can't answer, by provider and status (no "Start Ollama" on the web).
UNAVAILABLE = {
    "ollama": {
        "unreachable": "Gemma isn't running. Start Ollama, then try again.",
        "outdated": "Ollama needs an update before Gemma can answer. Update it, then try again.",
        "missing_model": "No Gemma model is installed yet. Download one from the setup screen, then try again.",
    },
    "gemini": {
        "unreachable": "Gemma can't be reached right now. Try again in a moment.",
        "missing_key": "Gemma isn't set up on this server yet, so Ask Sloth can't answer. "
                       "Your audit still works with templates.",
        "bad_key": "This server's Gemini API key was rejected, so Gemma can't answer right now.",
        "missing_model": "The Gemma model this server uses isn't available on the Gemini API right now.",
        "rate_limited": "Gemma is busy right now. Give it a minute, then try again.",
    },
}


def unavailable_message(status: str, provider_name: str | None = None) -> str:
    messages = UNAVAILABLE.get(provider_name or provider().name, UNAVAILABLE["ollama"])
    return messages.get(status, messages["unreachable"])


# ── Ollama ──────────────────────────────────────────────────────────────────

class OllamaProvider:
    """Exactly the calls the desktop app always made. `ollama` is imported lazily (tests patch its client)."""

    name = "ollama"
    label = "local"

    async def status(self, preferred: str | None) -> dict:
        return {"provider": self.name, **await ollama_setup.status(settings.ollama_host, preferred)}

    async def complete(self, model: str, messages: list[dict], *, schema: dict | None = None,
                       temperature: float = 0.4, num_ctx: int = 4096, timeout: float | None = 60.0) -> str:
        import ollama

        client = ollama.AsyncClient(host=settings.ollama_host, timeout=timeout)
        extra = {"format": schema} if schema else {}
        resp = await client.chat(model=model, messages=messages, think=False,
                                 options={"temperature": temperature, "num_ctx": num_ctx}, **extra)
        return resp.message.content or ""

    async def stream(self, model: str, messages: list[dict], *, tools: list[dict] | None = None,
                     temperature: float = 0.4, num_ctx: int = 4096,
                     timeout: float | None = 60.0) -> AsyncIterator[Chunk]:
        import ollama

        client = ollama.AsyncClient(host=settings.ollama_host, timeout=timeout)
        parts = await client.chat(model=model, messages=messages, tools=tools, stream=True, think=False,
                                  options={"temperature": temperature, "num_ctx": num_ctx})
        async for part in parts:
            calls = [ToolCall(c.function.name, dict(c.function.arguments or {}))
                     for c in part.message.tool_calls or []]
            yield Chunk(text=part.message.content or "", tool_calls=calls, done=bool(part.done),
                        input_tokens=getattr(part, "prompt_eval_count", 0) or 0,
                        output_tokens=getattr(part, "eval_count", 0) or 0)


# ── Gemini API ──────────────────────────────────────────────────────────────

MAX_TRIES = 3
BACKOFF = (2.0, 5.0, 10.0)  # seconds, when a 429/5xx doesn't say how long to wait
MAX_WAIT = 20.0
STATUS_TTL = {"ready": 60.0}  # seconds a status check is reused; anything else is re-checked after 10 s
STATUS_TTL_OTHER = 10.0
JSON_ONLY = "\n\nReply with JSON only (no prose, no code fences) that matches this JSON schema:\n{schema}"


class GeminiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"Gemini API {status}: {message}")
        self.status = status


def gemini_schema(schema: dict) -> dict:
    """JSON Schema → the Gemini API's OpenAPI subset (upper-case types, supported keywords only)."""
    out: dict = {}
    for key, value in schema.items():
        if key == "type" and isinstance(value, str):
            out["type"] = value.upper()
        elif key == "properties":
            out["properties"] = {name: gemini_schema(prop) for name, prop in value.items()}
        elif key == "items":
            out["items"] = gemini_schema(value)
        elif key in ("description", "enum", "required", "nullable", "format"):
            out[key] = value
    return out


def gemini_tools(tools: list[dict]) -> list[dict]:
    """Ollama/OpenAI-style tools → one `functionDeclarations` tool. No-argument functions omit `parameters`."""
    declarations = []
    for tool in tools:
        fn = tool.get("function", tool)
        decl = {"name": fn["name"], "description": fn.get("description", "")}
        params = fn.get("parameters") or {}
        if params.get("properties"):
            decl["parameters"] = gemini_schema(params)
        declarations.append(decl)
    return [{"functionDeclarations": declarations}]


def gemini_contents(messages: list[dict]) -> tuple[str, list[dict]]:
    """Engine messages → (systemInstruction text, contents). System messages anywhere join the instruction;
    adjacent turns of one role merge, since the API expects user and model turns to alternate."""
    system: list[str] = []
    contents: list[dict] = []

    def add(role: str, part: dict) -> None:
        if contents and contents[-1]["role"] == role:
            contents[-1]["parts"].append(part)
        else:
            contents.append({"role": role, "parts": [part]})

    for m in messages:
        role, content = m.get("role"), m.get("content") or ""
        if role == "system":
            if content:
                system.append(content)
        elif role == "assistant":
            if content:
                add("model", {"text": content})
            for call in m.get("tool_calls") or []:
                fn = call.get("function", call)
                add("model", {"functionCall": {"name": fn["name"], "args": dict(fn.get("arguments") or {})}})
        elif role == "tool":
            try:
                result = json.loads(content)
            except ValueError:
                result = content
            response = result if isinstance(result, dict) else {"result": result}
            add("user", {"functionResponse": {"name": m.get("tool_name") or "tool", "response": response}})
        else:
            add("user", {"text": content})
    return "\n\n".join(system), contents


def extract_json(text: str) -> str:
    """The JSON object in a reply that may wrap it in prose or ```json fences. Returns text as-is if none."""
    candidate = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", candidate, re.S)
    if fenced:
        candidate = fenced.group(1).strip()
    try:
        json.loads(candidate)
        return candidate
    except ValueError:
        pass
    start, end = candidate.find("{"), candidate.rfind("}")
    if 0 <= start < end:
        inner = candidate[start:end + 1]
        try:
            json.loads(inner)
            return inner
        except ValueError:
            pass
    return text


def _parts(data: dict) -> tuple[str, list[ToolCall]]:
    feedback = data.get("promptFeedback") or {}
    if feedback.get("blockReason"):
        raise GeminiError(400, f"prompt blocked ({feedback['blockReason']})")
    text, calls = "", []
    for cand in (data.get("candidates") or [])[:1]:
        for part in (cand.get("content") or {}).get("parts") or []:
            if part.get("thought"):
                continue  # reasoning is never shown or kept
            if "text" in part:
                text += part["text"]
            elif "functionCall" in part:
                fc = part["functionCall"]
                calls.append(ToolCall(fc.get("name", ""), dict(fc.get("args") or {})))
    return text, calls


def _usage(data: dict) -> tuple[int, int]:
    usage = data.get("usageMetadata") or {}
    return int(usage.get("promptTokenCount") or 0), int(usage.get("candidatesTokenCount") or 0)


def _error_text(body: bytes) -> str:
    try:
        return json.loads(body)["error"]["message"]
    except (ValueError, KeyError, TypeError):
        return body[:200].decode("utf-8", "replace")


def retry_delay(body: bytes, attempt: int) -> float:
    """The server's RetryInfo delay ("12s", "1.5s") if it sent one, else the backoff; capped at MAX_WAIT."""
    try:
        for detail in json.loads(body)["error"].get("details", []):
            if str(detail.get("@type", "")).endswith("RetryInfo"):
                return min(float(str(detail["retryDelay"]).rstrip("s")), MAX_WAIT)
    except (ValueError, KeyError, TypeError, AttributeError):
        pass
    return BACKOFF[min(attempt, len(BACKOFF) - 1)]


def _retryable(status: int) -> bool:
    return status == 429 or status >= 500


class GeminiProvider:
    """Gemma through the Gemini API, with the server's key. REST over httpx (no SDK to bundle)."""

    name = "gemini"
    label = "Gemini API"

    def __init__(self) -> None:
        self._slots: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()  # event loop → Semaphore
        self._checked: tuple[float, str, list[str]] | None = None  # (expires, status, available models)
        self._no_json_mode: set[str] = set()  # models that refused responseMimeType=application/json

    # plumbing

    def _slot(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        if loop not in self._slots:
            self._slots[loop] = asyncio.Semaphore(max(1, settings.llm_concurrency))
        return self._slots[loop]

    def _headers(self) -> dict:
        return {"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"}

    def _url(self, model: str, action: str) -> str:
        return f"{settings.gemini_base_url}/v1beta/models/{model}:{action}"

    def _body(self, messages: list[dict], *, tools: list[dict] | None, temperature: float,
              json_mode: bool) -> dict:
        system, contents = gemini_contents(messages)
        body: dict = {"contents": contents, "generationConfig": {"temperature": temperature}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if tools:
            body["tools"] = gemini_tools(tools)
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        return body

    async def _generate(self, model: str, body: dict, timeout: float | None) -> dict:
        if not settings.gemini_api_key:
            raise GeminiError(401, "no GEMINI_API_KEY on this server")
        for attempt in range(MAX_TRIES):
            async with self._slot():
                async with httpx.AsyncClient(timeout=timeout) as client:
                    r = await client.post(self._url(model, "generateContent"), json=body, headers=self._headers())
            if _retryable(r.status_code) and attempt < MAX_TRIES - 1:
                wait = retry_delay(r.content, attempt)
                log.info("Gemini API %s; trying again in %.1fs", r.status_code, wait)
                await asyncio.sleep(wait)
                continue
            if r.status_code >= 400:
                raise GeminiError(r.status_code, _error_text(r.content))
            return r.json()
        raise AssertionError("unreachable")  # the last attempt always returns or raises

    # the Provider surface

    async def status(self, preferred: str | None) -> dict:
        allowed = list(settings.gemini_models)
        default = allowed[0] if allowed else ""
        out = {"provider": self.name, "status": "missing_key", "version": None,
               "model": preferred if preferred in allowed else default, "model_present": False,
               "available_models": [], "loopback": False}
        if not settings.gemini_api_key:
            return out
        now = time.monotonic()
        if self._checked is None or self._checked[0] <= now:
            state, available = await self._check(allowed)
            ttl = STATUS_TTL.get(state, STATUS_TTL_OTHER)
            self._checked = (now + ttl, state, available)
        _, state, available = self._checked
        out["status"], out["available_models"] = state, available
        if state == "ready":
            out["model"] = preferred if preferred in available else available[0]
            out["model_present"] = True
        return out

    async def _check(self, allowed: list[str]) -> tuple[str, list[str]]:
        """One GET per allowed model: which exist for this key. A cheap metadata call, no tokens used."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                replies = await asyncio.gather(*(
                    client.get(f"{settings.gemini_base_url}/v1beta/models/{m}", headers=self._headers())
                    for m in allowed))
        except httpx.HTTPError as exc:
            log.info("Gemini API unreachable: %s", exc)
            return "unreachable", []
        codes = [r.status_code for r in replies]
        available = [m for m, r in zip(allowed, replies, strict=True) if r.status_code == 200]
        if available:
            return "ready", available
        if any(c in (400, 401, 403) for c in codes):
            return "bad_key", []
        if any(c == 429 for c in codes):
            return "rate_limited", []
        if codes and all(c == 404 for c in codes):
            return "missing_model", []
        return "unreachable", []

    def forget_status(self) -> None:
        self._checked = None

    async def complete(self, model: str, messages: list[dict], *, schema: dict | None = None,
                       temperature: float = 0.4, num_ctx: int = 4096, timeout: float | None = 60.0) -> str:
        if schema:  # the schema goes in the prompt; JSON mode is a bonus where the model accepts it
            messages = [*messages[:-1], {**messages[-1], "content": (messages[-1].get("content") or "")
                                         + JSON_ONLY.format(schema=json.dumps(schema))}]
        json_mode = bool(schema) and model not in self._no_json_mode
        try:
            data = await self._generate(model, self._body(messages, tools=None, temperature=temperature,
                                                          json_mode=json_mode), timeout)
        except GeminiError as exc:
            if not (json_mode and exc.status == 400):
                raise
            log.info("%s refused JSON mode (%s); asking in the prompt only", model, exc)
            self._no_json_mode.add(model)
            data = await self._generate(model, self._body(messages, tools=None, temperature=temperature,
                                                          json_mode=False), timeout)
        text, _ = _parts(data)
        return extract_json(text) if schema else text

    async def stream(self, model: str, messages: list[dict], *, tools: list[dict] | None = None,
                     temperature: float = 0.4, num_ctx: int = 4096,
                     timeout: float | None = 60.0) -> AsyncIterator[Chunk]:
        if not settings.gemini_api_key:
            raise GeminiError(401, "no GEMINI_API_KEY on this server")
        body = self._body(messages, tools=tools, temperature=temperature, json_mode=False)
        url = self._url(model, "streamGenerateContent") + "?alt=sse"
        usage = (0, 0)
        for attempt in range(MAX_TRIES):
            wait = None
            async with self._slot():
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream("POST", url, json=body, headers=self._headers()) as r:
                        if r.status_code >= 400:
                            content = await r.aread()
                            if not (_retryable(r.status_code) and attempt < MAX_TRIES - 1):
                                raise GeminiError(r.status_code, _error_text(content))
                            wait = retry_delay(content, attempt)  # nothing streamed yet: safe to retry
                        else:
                            async for line in r.aiter_lines():
                                if not line.startswith("data:"):
                                    continue
                                data = json.loads(line[5:])
                                usage = _usage(data) if data.get("usageMetadata") else usage
                                text, calls = _parts(data)
                                if text or calls:
                                    yield Chunk(text=text, tool_calls=calls)
            if wait is None:
                yield Chunk(done=True, input_tokens=usage[0], output_tokens=usage[1])
                return
            log.info("Gemini API busy; trying again in %.1fs", wait)
            await asyncio.sleep(wait)


# ── selection ───────────────────────────────────────────────────────────────

PROVIDERS = {"ollama": OllamaProvider(), "gemini": GeminiProvider()}


def provider():
    """The configured provider (SLOTH_LLM_PROVIDER). Unknown values fall back to Ollama, the desktop default."""
    return PROVIDERS.get(settings.llm_provider, PROVIDERS["ollama"])


async def status() -> dict:
    """{provider, status, model, model_present, available_models, version, loopback} for the user's choice."""
    return await provider().status(settings.preferred_model)


async def gemma_model() -> str | None:
    """The Gemma model to use now, or None when it isn't usable (callers then write templates)."""
    s = await status()
    return s["model"] if s["status"] == "ready" else None


def status_of(exc: Exception) -> str:
    """Which UNAVAILABLE sentence fits an exception from a call."""
    if isinstance(exc, GeminiError):
        return {429: "rate_limited", 401: "bad_key", 403: "bad_key", 404: "missing_model"}.get(exc.status,
                                                                                            "unreachable")
    return "unreachable"
