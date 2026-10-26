# SlothSpend Web — Implementation Plan

SlothSpend Web is the browser version of the desktop app: the same audit, Ask Sloth, drafts, reminders and
verification, for many people at once, with **Gemma served by the Gemini API** (one server-side
`GEMINI_API_KEY`) in production and **local Ollama Gemma** for local development and tests.

It is built *on* the desktop codebase, not beside it: one engine (`engine/app`) and one React renderer
(`src/renderer/src`), with a provider seam for Gemma, a workspace seam for tenancy, and a web shell. Every
desktop feature keeps working and stays covered by the existing test suites.

Read this with `IMPL.md` (desktop plan) and `sloth-spend-spec.md`. Milestones are built **one at a time,
each followed by a manual review** (same rule as the desktop build).

---

## 0. Decisions

| # | Decision | Why |
|---|---|---|
| W-D1 | **Email + password accounts.** argon2id hashes, opaque session token in an `httpOnly; Secure; SameSite=Lax` cookie (only its SHA-256 is stored), 30-day sliding expiry | Self-contained: no OAuth client per environment; works the same locally and in prod |
| W-D2 | **Server Gemini key only** (`GEMINI_API_KEY`). Users never see or manage keys | Chosen by the product owner. The key never reaches the browser |
| W-D3 | **Gemma via the Gemini API**: `gemma-4-26b-a4b-it` (default, MoE, fast) and `gemma-4-31b-it`. Configurable with `SLOTH_GEMINI_MODELS` | The two Gemma 4 models the Gemini API serves; both support system instructions and function calling |
| W-D4 | **Local dev and tests use Ollama** (`SLOTH_LLM_PROVIDER=ollama`, any installed Gemma, e.g. `gemma4:latest`). Prod uses `SLOTH_LLM_PROVIDER=gemini` | Same Gemma family both ways; offline development; no quota in CI |
| W-D5 | **One engine, two providers** behind `app/llm.py`. Desktop default stays `ollama`, so desktop behaviour is unchanged | No forked pipeline/agent code; both products get every fix |
| W-D6 | **One SQLite file per workspace** (`<data>/workspaces/<user-uuid>/slothspend.db`), selected per request through a `contextvar`. Accounts live in `<data>/accounts.db` | Every existing SQL statement, the singleton `report_meta` row and the read-only SQL tool stay correct. `run_readonly_sql` opens *only that file*, so a prompt-injected query physically cannot read another user's data. Deleting a workspace is deleting a folder |
| W-D7 | **Docker image + persistent volume** (`/data`), `docker-compose.yml` for local (with host Ollama) and prod (Gemini). Runs on Fly.io / Render / Railway / any VM | Chosen by the product owner. SQLite needs a real disk, which rules out a stateless Cloud Run |
| W-D8 | **TabPFN v2 runs on the server CPU** (shared model weights, per-request in-context data). Optional TabPFN-3.5 via the operator's `TABPFN_TOKEN` | Keeps "Live TabPFN" forecasts and re-scores; data is never mixed because TabPFN fits in context per call |
| W-D9 | **Reuse the desktop renderer.** `web/` is a Vite app whose entry installs a browser implementation of `window.sloth` and an auth gate, then mounts the same `App` | ~9k lines of UI are shared, so web parity is the default and drift is impossible |
| W-D10 | **Same origin.** FastAPI serves the built SPA and `/api/*`; Vite proxies `/api` in dev. No CORS. CSRF: SameSite cookie **plus** a required `X-Sloth-CSRF` header on every non-GET | Cookies + SSE "just work"; cross-site forms can't set custom headers |
| W-D11 | **Honest privacy copy.** Web copy says "on SlothSpend's server" and lists Google (Gemini API) in the egress table. The operator must use a **paid-tier** key: on the free tier Google may use prompts to improve its products | The desktop promise ("never leaves this computer") is not true on the web and must not be shown there |

---

## 1. Feature parity matrix

Every desktop feature, where it lives on the web, and the milestone that proves it. ✅ = shared code works
as-is · 🔁 = adapted · 🆕 = web-only.

| Area | Desktop feature | Web behaviour | Code | Milestone |
|---|---|---|---|---|
| **Boot / health (US-1)** | Engine · Gemma · TabPFN status rows with one-click fixes | Server · Gemma (Gemini API or local Ollama) · TabPFN rows. No download/install fixes in Gemini mode; "Try again" | 🔁 `Boot`, `StatusPills`, `/health` | W0 (API), W3 (UI) |
| | Gemma download (Ollama pull with progress, ETA) | Ollama mode only (local dev); hidden in Gemini mode | ✅ `GemmaSetup` / 🔁 gated | W0, W3 |
| | Ollama outdated / not found / missing model | Gemini: *key missing*, *key rejected*, *model unavailable*, *rate-limited*, *unreachable* | 🔁 | W0, W3 |
| | Limited mode banner (template / heuristic fallbacks) | Same | ✅ `LimitedBanner` | W3 |
| | Prior Labs key (TabPFN-3.5) in the OS keychain | Operator `TABPFN_TOKEN` env; Settings shows which TabPFN is active (read-only) | 🔁 `PriorKeyForm` hidden | W7 |
| | Engine stopped dialog + restart + last log lines | "Can't reach SlothSpend" banner with automatic retry; no server logs shown to users | 🔁 `EngineStopped` | W3 |
| **Accounts** | — (single user) | Sign up, sign in, sign out, change password, delete account, rate-limited login | 🆕 | W2, W3 |
| **Import (US-2)** | Drop/choose a bank CSV; auto-detects header row, date order, debit/credit, currency (USD/INR/EUR/GBP), Indian grouping | Same, via browser upload (≤ 10 MB) | ✅ `ImportEmpty`, `FilePicker`, `ingest.py` | W1 (API), W4 |
| | Column mapper, remembered layouts | Same, per workspace | ✅ `ColumnMapper` | W4 |
| | Newer statements append; overlap skipped; duplicate file detected | Same | ✅ | W4 |
| | Discard a pending import | Same | ✅ | W4 |
| | Demo data → sample statement, follow-ups (cancelled / still charged) | Same | ✅ `DemoDataMenu` | W4 |
| **Audit pipeline** | 9 visible stages over SSE, ≤ 60 s | Same; SSE over the session cookie. One audit per workspace, `SLOTH_MAX_AUDITS` server-wide | ✅ `PipelineProgress` / 🔁 locks | W1, W4 |
| | Gemma merchant cleanup in priority order under a time budget; background finish | Same, through the provider; Gemini batches respect rate limits | 🔁 `normalize.py` | W0, W4 |
| | User renames always win | Same | ✅ | W4 |
| | TabPFN recurring score, q10–q90 next-charge and 30-day forecast | Same, server CPU | ✅ | W4 |
| | Flags: double charge, price creep, overlap, possible annual, zombie suspect | Same | ✅ | W4 |
| | Sloth's summary (Gemma rephrases, must keep every number; template fallback) | Same | 🔁 `llm_summary.py` | W0, W4 |
| | Audit error card with retry | Same | ✅ `AuditError` | W4 |
| **Report (US-3)** | Summary card, 4 summary cards, 12-month burn chart with forecast band, findings table sorted by priority | Same | ✅ | W4 |
| | Statement bar (period, rows, skipped) | Same | ✅ `StatementBar` | W4 |
| | Merchant drawer: charges, reasons, "Looks like", next charge, flags, charts, rename/recategorise | Same | ✅ `MerchantDrawer` | W4 |
| | Source chips (*Gemma 4 · local*, *TabPFN v2*, *Template*, *Heuristic*) | *Gemma 4 · Gemini API* / *Gemma 4 · local* by provider | 🔁 `SourceChip` | W3 |
| **Corrections (US-4)** | Keep / Not a subscription → re-score ≤ 5 s, persists | Same | ✅ `RescoreBanner` | W4 |
| **Ask Sloth (US-5)** | Chat with 8 typed tools, visible tool badges, markdown answers, suggested prompts, prefetch of mentioned merchants | Same, Gemma 4 function calling through the Gemini API | 🔁 `agent.py` | W0, W5 |
| | Live TabPFN `forecast_spend` / `score_merchant` | Same | ✅ | W5 |
| | `run_readonly_sql` (one SELECT, 50 rows, 2 s) | Same, opened on the workspace file only | 🔁 `tools.py` | W1, W5 |
| | Guard: scrub links/phones; replace false "I've set a reminder" claims | Same | ✅ `guard.py` | W5 |
| | Conversation history survives reload | Same, per workspace | ✅ | W5 |
| **Drafts (US-6)** | Cancellation / refund / negotiation email from the drawer and chat; fact-checked; copyable; never sent | Same | 🔁 `drafts.py` | W0, W5 |
| **Reminders (US-7)** | Remind N days before renewal; keep, snooze (max 3), stop, I cancelled it; 4-step stepper | Same | ✅ `RemindersPanel`, `ReminderCard` | W6 |
| | Scheduler: tick at start + every 30 s, compare-and-set, catch-up on next launch | One loop ticks **every workspace** with due rows; a closed tab catches up on next visit | 🔁 `reminders.py` | W1, W6 |
| | Desktop notification + click to open | Browser Notification API (permission asked on first reminder); click focuses the tab and opens the reminder | 🔁 `notify.ts` | W6 |
| | Gemma-written note with retries, template fallback | Same | 🔁 `notes.py` | W0, W6 |
| | Notification inbox, unread state, mark read / all read | Same | ✅ `NotificationBell` | W6 |
| | Demo mode compresses waits to N seconds | Same, per workspace | ✅ | W6 |
| **Verification (US-8)** | Newer statement → Verified (saving $X/month) / Still charged + refund draft; 60-day expiry | Same | ✅ | W6 |
| **Settings (US-9)** | Theme (system/light/dark) | Same (localStorage) | ✅ | W7 |
| | Chat model picker (installed Gemmas) | Gemini Gemma models (Gemini mode) / installed Gemmas (Ollama mode) | 🔁 | W0, W7 |
| | Currency, reminder days, demo mode | Same, per workspace | ✅ | W7 |
| | Opt-in performance traces (Sentry, no prompts or answers) | Per-workspace opt-in via a Sentry `traces_sampler`; off by default | 🔁 `telemetry.py` | W7 |
| | Egress table | Web egress table (server, Google Gemini API, Hugging Face one-time, Sentry opt-in) | 🔁 `EgressTable` | W7 |
| | Delete all local data | **Delete all my data** (keeps account + settings) and **Delete account** | 🔁 `DeleteDataDialog` | W7 |
| | Remote-Ollama warning (`OLLAMA_HOST` not loopback) | Ollama mode only | ✅ | W7 |
| **Privacy test** | `test_egress.py`: whole app with non-loopback sockets refused | Web egress test: the only allowed outbound host is the Gemini API (stubbed) | 🔁 | W8 |
| **Shell** | Theme toggle, tabs (Audit / Reminders), top bar, toasts, a11y | Same + account menu | ✅ / 🆕 | W3 |
| | Open external links | `window.open(url, '_blank', 'noopener')` | 🔁 bridge | W3 |
| **Ops** | PyInstaller + electron-builder + release CI | Docker image, compose, CI build + container smoke test | 🆕 | W8 |
| | Landing page | Adds an "Open in browser" link | 🔁 `site/` | W9 |

---

## 2. Contracts

### 2.1 LLM provider (`engine/app/llm.py`, W0)

```python
provider() -> Provider            # by SLOTH_LLM_PROVIDER: "ollama" (default) | "gemini"
await status(preferred) -> dict   # {provider, status, model, model_present, available_models, version, loopback}
await gemma_model() -> str | None # the model to use now, or None (callers fall back to templates)

class Provider:
    name: str                                     # "ollama" | "gemini"
    label: str                                    # "local" | "Gemini API" (source chips)
    async def status(preferred) -> dict
    async def complete(model, messages, *, schema=None, temperature, num_ctx, timeout) -> str
    def stream(model, messages, *, tools=None, temperature, num_ctx, timeout) -> AsyncIterator[Chunk]

Chunk(text: str = "", tool_calls: list[ToolCall] = [], done: bool = False,
      input_tokens: int = 0, output_tokens: int = 0)
ToolCall(name: str, arguments: dict)
```

Messages and tool schemas stay in the engine's existing (Ollama-shaped) format; the Gemini provider
translates:

| Engine | Gemini REST |
|---|---|
| `system` messages (any position) | concatenated into `systemInstruction` |
| `user` / `assistant` | `contents[].role` `user` / `model` (adjacent same-role turns merged) |
| `assistant.tool_calls[]` | `model` parts `{functionCall: {name, args}}` |
| `tool` message (`tool_name`, JSON text) | `user` part `{functionResponse: {name, response: {result}}}` |
| `tools=[{type:function, function:{…}}]` | `tools: [{functionDeclarations: […]}]`, schema types upper-cased |
| `schema=` (structured output) | `responseMimeType: application/json` + the schema in the prompt; tolerant JSON extraction; if the model rejects JSON mode, it is turned off for that model and the call retried once |
| streaming | `:streamGenerateContent?alt=sse`; parts with `thought: true` are dropped |

Gemini status values: `ready` · `missing_key` · `bad_key` · `missing_model` · `rate_limited` ·
`unreachable`. A 429 waits the server's `retryDelay` (≤ 20 s, ≤ 3 tries) — *slow and steady*; streams only
retry before their first token. `SLOTH_LLM_CONCURRENCY` (default 4) caps concurrent Gemini calls server-wide.
Status checks are cached (60 s healthy, 10 s otherwise) so `/health` polling never burns quota.

Environment:

| Variable | Default | Purpose |
|---|---|---|
| `SLOTH_LLM_PROVIDER` | `ollama` | `ollama` or `gemini` |
| `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) | — | Server key (gemini mode) |
| `SLOTH_GEMINI_MODELS` | `gemma-4-26b-a4b-it,gemma-4-31b-it` | Allowed models, first = default |
| `SLOTH_GEMINI_BASE_URL` | `https://generativelanguage.googleapis.com` | Tests point this at a local stub |
| `SLOTH_LLM_CONCURRENCY` | `4` | Concurrent Gemini calls |

`/health` keeps its shape (the key stays `ollama` until W3 renames it to `llm` in engine and renderer
together) and gains `ollama.provider`.

### 2.2 Workspaces (W1)

- `app/workspace.py`: `current: ContextVar[Workspace]`; `Workspace(id, dir, db_path)`; `use(id)` context manager.
- `db.connect()` and `tools.run_readonly_sql` read the db path from the current workspace. Desktop mode
  (no workspace set) uses the existing `<SLOTH_DATA_DIR>/slothspend.db` exactly as today.
- `runtime` becomes per-workspace (`pipeline_lock`, `pending`, `pipeline_task`, `normalize_task`) via
  `state.for_workspace()`; a server-wide semaphore `SLOTH_MAX_AUDITS` (default 2) bounds CPU.
- The scheduler lists workspaces with due reminders (a small `due_index` in `accounts.db`, updated on every
  reminder write) and ticks each inside `workspace.use(id)`. `asyncio.to_thread` and `create_task` copy the
  context, so background work stays in its workspace; the code that creates raw threads is audited.
- Test: two workspaces audit different statements concurrently; no row, chat, reminder, notification or
  SQL-tool result crosses over.

### 2.3 Web API (W2)

All engine routes mount under `/api` unchanged; `require_token` is replaced in web mode by
`require_session` (cookie → user → `workspace.use(user.id)`), and `X-Sloth-CSRF: 1` on non-GET.

| Route | Body → result |
|---|---|
| `POST /api/auth/signup` | `{email, password}` (≥ 10 chars, checked against a common-password list) → `{user}` + cookie |
| `POST /api/auth/login` | `{email, password}` → `{user}` + cookie · 5 failures / 15 min / email+IP → 429 |
| `POST /api/auth/logout` | → `{ok}` (session row deleted) |
| `GET /api/auth/me` | → `{user: {id, email, created_at}}` or 401 |
| `POST /api/auth/password` | `{current, new}` → `{ok}` (other sessions revoked) |
| `DELETE /api/auth/account` | `{password}` → `{ok}` (workspace folder + account removed) |
| `POST /api/setup/ollama/pull` | Ollama mode only; 404 in Gemini mode |
| `POST /api/shutdown` | Not mounted on the web |

Limits: uploads ≤ 10 MB, chat message ≤ 4,000 chars, per-user LLM budget (`SLOTH_USER_LLM_PER_MIN`,
default 30 calls/min) so one account can't drain the shared key.

### 2.4 Renderer platform seam (W3)

`window.sloth` keeps its type. The web bridge (`web/src/bridge.ts`):

| Bridge member | Desktop | Web |
|---|---|---|
| `getConfig()` | port + token | `{apiBase: '/api', token: '', platform: 'web', version}` |
| `priorKey.*` | keychain | `present()` → server status; `save/remove` → `{ok:false}` (hidden in UI) |
| `telemetry.get/set` | prefs.json + engine restart | workspace setting (W7) |
| `openExternal` | `shell.openExternal` | `window.open(…, 'noopener')` |
| `restartEngine` / `engineLogs` / `onEngineExit` | process supervision | reload / `[]` / no-op (offline banner instead) |
| `focusWindow` | `BrowserWindow.focus` | `window.focus()` |
| `setBackground` | native window colour | `<meta name="theme-color">` |

`api.ts`: sends `X-Sloth-CSRF` when `platform === 'web'`, omits the token header, and on 401 sends the user
to sign-in. Copy that says "this computer" moves to `lib/copy.ts` with desktop and web variants.

---

## 3. Repository layout (additions)

```
engine/app/llm.py               # W0 provider seam (Ollama + Gemini)
engine/app/workspace.py         # W1 tenancy
engine/app/web/                 # W2 accounts, sessions, csrf, limits, web entry (python -m app.web)
engine/tests/test_llm_*.py      # W0 provider tests (Gemini REST stub)
engine/tests/web/               # W1–W2 tenancy + auth tests, W8 web egress test
engine/scripts/llm_smoke.py     # W0 live check against Ollama or the Gemini API
web/                            # W3 Vite app: index.html, src/main.tsx, bridge.ts, auth screens
Dockerfile · docker-compose.yml · .env.example   # W8
WEB-IMPL.md                     # this plan
```

---

## 4. Milestones

| # | Milestone | Exit demo |
|---|---|---|
| **W0** | Gemma provider seam (Ollama ↔ Gemini API) | Every Gemma feature (names, summary, chat with tools, drafts, notes) runs through `app/llm.py`. Desktop tests unchanged and green; Gemini translation tested against a REST stub; `llm_smoke.py` passes on local Ollama (and on Gemini with a key) |
| **W1** | Multi-tenant engine | Two workspaces audit, chat, remind and query SQL concurrently with zero crossover; desktop mode untouched |
| **W2** | Web server: accounts, sessions, CSRF, limits | `python -m app.web` serves `/api` behind sign-in; auth test suite green |
| **W3** | Web shell | `npm run web:dev`: sign up → Boot (Gemma via Gemini/Ollama, TabPFN) → workspace; offline banner; source chips by provider |
| **W4** | Audit on the web | Upload → mapper → 9-stage progress → report → drawer → correction re-score ≤ 5 s; sample + follow-ups |
| **W5** | Ask Sloth + drafts on Gemini | All 5 suggested prompts give grounded answers with ≥ 1 visible tool call on `gemma-4-26b-a4b-it` and on local `gemma4`; all 3 drafts pass the fact check |
| **W6** | Reminders, browser notifications, verification | remind → snooze → I cancelled it → follow-up import → Verified / Still charged, with the tab closed in between |
| **W7** | Settings & privacy (web) | Model picker, currency, reminders, demo mode, traces opt-in, web egress table, delete data, delete account |
| **W8** | Docker, CI, hardening | `docker compose up` (local Ollama profile and Gemini profile) works from a clean clone; security headers; web egress test green; CI builds the image |
| **W9** | DoD + docs | Full DoD run on Gemini and on Ollama with timings in `docs/web-dod-results.md`; README "Web" section; landing link |

### W0 — Gemma provider seam

| # | Task |
|---|---|
| W0.1 | `config.py`: `llm_provider`, `gemini_api_key`, `gemini_models`, `gemini_base_url`, `llm_concurrency` |
| W0.2 | `llm.py`: `Chunk`, `ToolCall`, `OllamaProvider` (exactly today's calls), `GeminiProvider` (REST via `httpx`, translation table §2.1, SSE parsing, thought filtering, 429/5xx retry, JSON-mode fallback, concurrency cap, cached status), `provider()`, `status()`, `gemma_model()` |
| W0.3 | Move call sites onto the seam: `normalize`, `llm_summary`, `drafts`, `notes`, `agent`, `report.gemma_model`, `/health`, `/setup/ollama/pull` (Ollama only), `user_settings.chat_model` validation by provider |
| W0.4 | Agent: provider-specific "unavailable" sentences (no "Start Ollama" in Gemini mode); Sentry `gen_ai.provider.name` from the provider |
| W0.5 | Tests: existing suite unchanged in behaviour (signatures that lost `host` updated); new `test_llm_gemini.py` against a pytest-httpserver Gemini stub covering translation, tools round-trip, SSE, thoughts, JSON fallback, 429 retry, status mapping, and an end-to-end audit + chat turn in Gemini mode |
| W0.6 | `scripts/llm_smoke.py`: names 3 merchants, writes a summary, runs one tool-calling turn, streams a draft — against whichever provider is configured |

**Exit checklist**
- [x] `npm run engine:test` green — 187 (164 existing + 23 in `test_llm_gemini.py`), 2026-10-26.
- [x] `SLOTH_LLM_PROVIDER=ollama engine/.venv/bin/python engine/scripts/llm_smoke.py` passes with local
      `gemma4:latest` (Ollama 0.40.11): names 3/3 in 8.1 s, summary by Gemma, `get_merchant` tool call +
      grounded answer, draft passes the fact check, note passes the rules.
- [ ] `SLOTH_LLM_PROVIDER=gemini GEMINI_API_KEY=… … llm_smoke.py` passes (needs the operator's key). Without
      a key it stops cleanly with the *missing_key* sentence.
- [x] Desktop app unchanged: default provider `ollama`, desktop system prompt byte-identical, `/health` only
      gains `ollama.provider`.

W1–W9 task tables are written at the start of each milestone, from §1–§2, so they reflect what the
previous review changed.
