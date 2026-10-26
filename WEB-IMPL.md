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
| W-D1 | **Email + password accounts**, shaped by the web designs (artboards 10–15): name, email, password (≥ 12 characters, a number or symbol, not containing the email), Terms checkbox; **email confirmation** before the first session; **"Email me a sign-in link"**; forgot / reset password (reset logs out other devices). Passwords hashed with stdlib **scrypt** (N=2^15, r=8, p=3; parameters stored per hash); opaque session token in an `httpOnly; SameSite=Lax` cookie (`Secure` on https), only its SHA-256 stored. **Keep me logged in** = 30-day sliding cookie; otherwise a browser-session cookie with a 12-hour sliding server expiry | Self-contained: no OAuth client per environment; scrypt adds no dependency to the desktop bundle |
| W-D2 | **Server Gemini key only** (`GEMINI_API_KEY`). Users never see or manage keys | Chosen by the product owner. The key never reaches the browser |
| W-D3 | **Gemma via the Gemini API**: `gemma-4-26b-a4b-it` (default, MoE, fast) and `gemma-4-31b-it`. Configurable with `SLOTH_GEMINI_MODELS` | The two Gemma 4 models the Gemini API serves; both support system instructions and function calling |
| W-D4 | **Local dev and tests use Ollama** (`SLOTH_LLM_PROVIDER=ollama`, any installed Gemma, e.g. `gemma4:latest`). Prod uses `SLOTH_LLM_PROVIDER=gemini` | Same Gemma family both ways; offline development; no quota in CI |
| W-D5 | **One engine, two providers** behind `app/llm.py`. Desktop default stays `ollama`, so desktop behaviour is unchanged | No forked pipeline/agent code; both products get every fix |
| W-D6 | **One SQLite file per workspace** (`<data>/workspaces/<user-uuid>/slothspend.db`), selected per request through a `contextvar`. Accounts live in `<data>/accounts.db` | Every existing SQL statement, the singleton `report_meta` row and the read-only SQL tool stay correct. `run_readonly_sql` opens *only that file*, so a prompt-injected query physically cannot read another user's data. Deleting a workspace is deleting a folder |
| W-D7 | **Docker image + persistent volume** (`/data`), `docker-compose.yml` for local (with host Ollama) and prod (Gemini). Runs on Fly.io / Render / Railway / any VM | Chosen by the product owner. SQLite needs a real disk, which rules out a stateless Cloud Run |
| W-D8 | **TabPFN v2 runs on the server CPU** (shared model weights, per-request in-context data). Optional TabPFN-3.5 via the operator's `TABPFN_TOKEN` | Keeps "Live TabPFN" forecasts and re-scores; data is never mixed because TabPFN fits in context per call |
| W-D9 | **Reuse the desktop renderer.** `web/` is a Vite app whose entry installs a browser implementation of `window.sloth` and an auth gate, then mounts the same `App` | ~9k lines of UI are shared, so web parity is the default and drift is impossible |
| W-D10 | **Same origin.** FastAPI serves the built SPA and `/api/*`; Vite proxies `/api` in dev. No CORS. CSRF: SameSite cookie **plus** a required `X-Sloth-CSRF` header on every non-GET | Cookies + SSE "just work"; cross-site forms can't set custom headers |
| W-D12 | **Email**: `SLOTH_SMTP_URL` (`smtp://…:587` STARTTLS required off-localhost, or `smtps://…:465`) in production; without it, a dev **outbox** writes each message to `<data>/outbox/*.eml` and logs its links. Delivery runs in the background so answers take the same time whether or not an account exists | Sign-up works locally with no mail server; no account probing by timing |
| W-D11 | **Honest privacy copy.** Web copy says "on SlothSpend's server" and lists Google (Gemini API) in the egress table. The operator must use a **paid-tier** key: on the free tier Google may use prompts to improve its products | The desktop promise ("never leaves this computer") is not true on the web and must not be shown there |

---

## 1. Feature parity matrix

Every desktop feature, where it lives on the web, and the milestone that proves it. ✅ = shared code works
as-is · 🔁 = adapted · 🆕 = web-only.

| Area | Desktop feature | Web behaviour | Code | Milestone |
|---|---|---|---|---|
| **Boot / health (US-1)** | Engine · Gemma · TabPFN status rows with one-click fixes | Server · Gemma (Gemini API or local Ollama) · TabPFN rows. No download/install fixes in Gemini mode; "Try again" | 🔁 `Boot`, `StatusPills`, `/health` | W0 (API), W3 (UI) |
| | Gemma download (Ollama pull with progress, ETA) | Not on the web: the operator installs models (`/setup/ollama/pull` isn't mounted, so no user can make the server download) | 🔁 hidden | W0, W2, W3 |
| | Ollama outdated / not found / missing model | Gemini: *key missing*, *key rejected*, *model unavailable*, *rate-limited*, *unreachable* | 🔁 | W0, W3 |
| | Limited mode banner (template / heuristic fallbacks) | Same | ✅ `LimitedBanner` | W3 |
| | Prior Labs key (TabPFN-3.5) in the OS keychain | Operator `TABPFN_TOKEN` env; Settings shows which TabPFN is active (read-only) | 🔁 `PriorKeyForm` hidden | W7 |
| | Engine stopped dialog + restart + last log lines | "Can't reach SlothSpend" banner with automatic retry; no server logs shown to users | 🔁 `EngineStopped` | W3 |
| **Accounts** | — (single user) | Sign up + email confirmation, log in (keep me logged in), email me a sign-in link, forgot / reset password, log out, change password, log out other devices, delete account; rate limits | 🆕 | W2 (API + screens 10–14), W3 (account menu, 15), W7 (Settings › Password & security, delete account UI) |
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

The engine's routes mount under `/api` unchanged. In front of them, `app/web/gate.py` (a plain ASGI middleware,
so it holds for streamed responses too) replaces the desktop's per-launch token:

1. **CSRF**: every non-GET needs `X-Sloth-CSRF: 1` and, when the browser sends an `Origin`, the public origin.
2. **Session**: cookie → account → `auth.current_user` and `workspace.current` for the whole request.
3. Everything outside `/api/auth/*` needs a session (401).
4. **Limits**: statement upload ≤ 10 MB; Gemma-backed routes (`/chat`, `/demo/load-sample`, `/import/{id}/confirm`,
   `/series/{id}/draft`) ≤ `SLOTH_USER_LLM_PER_MIN` (30) per account per minute.
5. **Headers**: nosniff, `Referrer-Policy: no-referrer` (tokens travel in email links), `X-Frame-Options: DENY`,
   COOP, Permissions-Policy, HSTS on https; pages get a strict CSP; API answers `Cache-Control: no-store`.

| Route | Body → result |
|---|---|
| `POST /api/auth/signup` | `{name, email, password, accept_terms}` → 202 `{ok, email}`; emails a confirmation link (24 h). A taken email gets the **same answer** and an "you already have an account" email |
| `POST /api/auth/verify` | `{token}` → `{user}` + cookie (confirms the email, signs in) |
| `POST /api/auth/verify/resend` | `{email}` → 202, same answer for anyone |
| `POST /api/auth/login` | `{email, password, remember}` → `{user}` + cookie · 401 *"That email and password don’t match."* for both wrong password and unknown email · 403 `{code: "unverified"}` (and a new link) · 5 failures / 15 min per email, 30 per IP → 429 |
| `POST /api/auth/logout` | → `{ok}` (session deleted server-side) |
| `GET /api/auth/me` | → `{user: {id, email, name, created_at}}` or 401 |
| `POST /api/auth/link` · `/link/consume` | "Email me a sign-in link": `{email, remember}` → 202 (same answer for anyone) · `{token}` → `{user}` + cookie (15 min, once; also confirms the email) |
| `POST /api/auth/password/forgot` | `{email}` → 202, same answer for anyone; reset link (1 h, once; a newer link cancels older ones) |
| `POST /api/auth/password/reset/check` | `{token}` → `{email}` without using the link (the reset screen's "For …") |
| `POST /api/auth/password/reset` | `{token, password}` → `{user}` + cookie; other devices logged out; "password changed" email |
| `POST /api/auth/password` | `{current, new}` → `{ok, other_sessions_ended}` (W7 screen) |
| `POST /api/auth/logout-others` | → `{ok, ended}` (W7 screen) |
| `DELETE /api/auth/account` | `{password}` → `{ok}`: tasks cancelled, account, sessions, links and the workspace folder deleted (W7 screen) |
| `/api/setup/ollama/pull`, `/api/shutdown` | Not mounted on the web (404) |

Emails rate-limited to 3 per address per 15 min (silently skipped beyond: answers must not differ) and 20 per IP
per hour (429). Sign-ups: 10 per IP per hour.

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
engine/app/workspace.py         # W1 tenancy (per-user SQLite, contextvar)
engine/app/web/                 # W2: accounts.py, passwords.py, mailer.py, emails.py, auth.py, gate.py,
                                #     server.py (python -m app.web), config.py
engine/tests/test_llm_gemini.py # W0 provider tests (Gemini REST stub)
engine/tests/test_web_*.py      # W1 tenancy, W2 auth + gate (W8 adds the web egress test)
engine/scripts/llm_smoke.py     # W0 live check against Ollama or the Gemini API
web/                            # W2 Vite app: auth screens 10–14; W3 adds bridge.ts + the workspace
Dockerfile · docker-compose.yml · .env.example   # W8
WEB-IMPL.md                     # this plan
```

---

## 4. Milestones

| # | Milestone | Exit demo |
|---|---|---|
| **W0** | Gemma provider seam (Ollama ↔ Gemini API) | Every Gemma feature (names, summary, chat with tools, drafts, notes) runs through `app/llm.py`. Desktop tests unchanged and green; Gemini translation tested against a REST stub; `llm_smoke.py` passes on local Ollama (and on Gemini with a key) |
| **W1 + W2** | Multi-tenant engine + accounts, web server and auth screens (built together, 2026-10-26) | Two workspaces audit, chat, remind and query SQL concurrently with zero crossover; `python -m app.web` serves `/api` behind sign-in; sign up → confirm → log in / sign-in link / reset work in the browser; desktop untouched |
| **W3** | Web shell (built 2026-10-26) | Signed in → Boot (Gemma via Gemini/Ollama, TabPFN) → workspace with the logged-in top bar and account menu (artboard 15); offline banner; source chips by provider |
| **W4** | Audit on the web (built 2026-10-26) | Upload → mapper → 9-stage progress → report → drawer → correction re-score ≤ 5 s; sample + follow-ups |
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

### W1 + W2 — Workspaces, accounts, web server and auth screens

Built as one milestone at the product owner's request (2026-10-26), from the web artboards 10–14 in the
SlothSpend MVP design canvas.

| # | Task |
|---|---|
| W1.1 | `app/workspace.py`: `current` contextvar, per-user folder + SQLite file, `ensure` (schema once per process), `use`, `all_ids`, `remove`; ids must be uuid4 hex (never a path) |
| W1.2 | `db.connect`/`init` and `tools.run_readonly_sql` use `workspace.db_path()`; desktop (no workspace) keeps `<data>/slothspend.db` |
| W1.3 | `state.runtime` resolves per workspace (audit lock, pending uploads, task handles); `audit_slots()` caps audits + re-scores server-wide (`SLOTH_MAX_AUDITS`, 2). TabPFN already serialises inference with its own lock |
| W1.4 | `reminders.run_scheduler(workspaces)` ticks every workspace in turn; `/shutdown` moved to its own router |
| W2.1 | `app/web/`: config, scrypt passwords + the three rules, accounts DB (users, sessions, single-use email tokens, throttle), SMTP/outbox mailer, the five emails, auth router (§2.3), gate (§2.3), server (engine routes + SPA with history fallback, HEAD for uptime checks) |
| W2.2 | `web/`: Vite app reusing the renderer's tokens, fonts, `Button`, `Spinner`, `ThemeToggle`, `Wordmark`; history router (tokens removed from the address bar on read); session store; screens: Sign up, Check your inbox (confirm and sign-in-link variants), Log in (+ error alert, sign-in link), Forgot password (+ sent state), Reset password (+ expired-link state), link landings, a temporary signed-in page; light + dark; stacks at phone width |
| W2.3 | Scripts: `web:dev` (Vite, :5173, proxies `/api`), `web:api` (engine web server, :8770, data in `.sloth-web/`), `web:build`, `web:serve`; `typecheck`, `lint` and `vitest` cover `web/` |

**Deviations from the plan**
- scrypt (stdlib) instead of argon2id: same strength class, no new dependency in the desktop bundle.
- The designs added email confirmation, sign-in links, forgot/reset and "keep me logged in": all built (W-D1, W-D12).
- Password rules follow the design (≥ 12, number or symbol, not the email) instead of "≥ 10 + common list".
- Sign-up's Terms / Privacy links point at the README's *Inform, never act* and *Privacy* sections until real
  legal pages exist (`VITE_TERMS_URL`, `VITE_PRIVACY_URL`).
- A reset signs in on the device that opened the link (the design's "logs you out on your *other* devices").
- The model download isn't mounted on the web at all (it was "Ollama mode only").
- The scheduler walks every workspace folder each 30 s tick — fine for hundreds of accounts; a due-index in
  `accounts.db` is the follow-up if it ever shows up in profiles.

**Exit checklist**
- [x] Engine: 221 tests green (187 + 27 `test_web_auth.py` + 7 `test_web_tenancy.py`), incl. two concurrent
      audits (USD sample + INR HDFC) with no crossover, per-person settings / chats / reminders /
      notifications, the SQL tool confined to its own file, the scheduler ticking both workspaces, delete-data
      scoped to one person.
- [x] Renderer + web: `npm run typecheck`, `npm run lint`, `npm test` (66) green; `npm run web:build` builds.
- [x] Live (`python -m app.web`, local `gemma4:latest`): sign up → outbox email → confirm → sample audit in
      30 s (Gemma names + summary, TabPFN v2) → Ask Sloth answers with a `get_merchant` tool call; a second
      account sees no report and no chat.
- [x] Screens checked in headless Chrome: Log in and Sign up (dark), Forgot (light), Check your inbox,
      Reset (expired link), Sign up at 500 px.
- [ ] Manual review in a real browser (user).

### W3 — Web shell

| # | Task |
|---|---|
| W3.1 | `/health` key `ollama` → `llm` in the engine, its tests, the Postman collection and the renderer types; `Health.llm.provider` and the Gemini statuses typed |
| W3.2 | Platform seam in the shared renderer: `lib/platform.ts` (`isWeb()`, `byPlatform(desktop, web)`, `slots`), `window.sloth.kind`, `lib/copy.ts`; web bridge `web/src/bridge.ts` (§2.4), imported before any renderer module |
| W3.3 | `lib/api.ts`: CSRF header instead of the token on the web; any 401 raises `sloth:signed-out` → the web app reloads to Log in with "You were logged out. Log in again to carry on." |
| W3.4 | Status rows and pills: web wording for Engine ("Connected to SlothSpend"), Gemma (every Gemini status; nothing to install, problems are the operator's) and TabPFN ("on SlothSpend's server"); `gemmaLabel` reads `gemma-4-…` ids; chips say where Gemma runs (`Gemma 4 · Gemini API` / `· Ollama`, `· local` on the desktop, no claim while offline); pills follow artboard 15 (`Gemma 4`) |
| W3.5 | Boot on the web: no "no account needed", no Ollama download, no Prior Labs key, "Check again" instead of Restart/Retry, provider-honest footnote; skipped automatically whenever everything is ready |
| W3.6 | "On this computer" copy switched by platform in Import, Statement bar, Progress, Drawer, Drafts, Ask Sloth (desktop wording byte-identical) |
| W3.7 | `ConnectionBanner` replaces the engine-stopped dialog on the web: shown after a lost connection, gone when the server answers |
| W3.8 | Account menu (artboard 15) in the top bar slot: avatar with initials, name + email, Account, Password & security, Get the desktop app, Log out; arrow keys; Esc / click-outside close. `AccountDialog`: profile + delete account (password confirm), change password (rules), log out other devices |
| W3.9 | Web app mounts the renderer `App` (lazy chunk) at `/`; per-account `localStorage` reset when a different account signs in on the same browser; logging out reloads to Log in so nothing of the account stays in memory |

**Deviations**
- Account and Password & security open an account dialog now (the API existed since W2), not the Settings modal;
  Settings' web sections (egress table, traces, delete data copy) stay in W7.
- The Settings modal on the web still shows desktop privacy wording until W7 (the key form is already hidden there).
- Provenance follow-up for W4: a stored summary/merchant name records *gemma*, not which provider wrote it, so a chip
  names the provider in use now. Only visible if an operator switches providers; W4 stores the provider with them.

**Exit checklist**
- [x] Engine 221 · renderer + web 71 tests green; `typecheck`, `lint`, `web:build` and the desktop
      `electron-vite build` all clean.
- [x] Live in headless Chrome (DevTools protocol) on `python -m app.web`: signed-in workspace with the audited report,
      chips `Gemma 4 · Ollama`, pills `Engine | Gemma 4 | TabPFN v2`, no "this computer" anywhere; account menu opens
      with focus on its first item; Password & security dialog; 390 px phone with 0 px horizontal overflow; Log out →
      `/login` and `/api/auth/me` 401.
- [x] Gemini mode with no key: Boot stays with "Gemma · Not set up", nothing to install, no key form; Continue in
      limited mode → workspace with the Limited banner; server killed → connection banner; server back → banner gone;
      session ended server-side → next poll's 401 → Log in with the notice.
- [ ] Manual review in a real browser (user).

### W4 — Audit on the web

| # | Task |
|---|---|
| W4.1 | Provenance: `report_meta.summary_provider` (schema v3, migrated in place) records who served Gemma for the stored summary; the summary chip shows it (`SourceChip provider`), so it stays true after a provider change. Re-scores (template summary) clear it |
| W4.2 | Replayable audits: `report.Run` keeps every SSE event; `GET /audit` (running? file, rows, started) and `POST /audit/follow` (replay from the first stage, then live). The renderer checks before showing a report, so a reloaded or second tab follows a running audit — with its true elapsed time — instead of showing stale data or a 409 |
| W4.3 | Busy server: when every audit slot is taken, the audit's first event says so ("Waiting for a free moment — other audits are running. Slow and steady.") |
| W4.4 | Upload size checked in the browser before sending (10 MB on the web, 20 MB on the desktop) |
| W4.5 | `engine/scripts/fake_gemini.py` (`npm run web:fake-gemini`): canned Gemini API for running the web app in Gemini mode without a key; its prose says it's fake. The Gemini tests use the same replies |
| W4.6 | Fixes found by the browser run (shared with the desktop): the column mapper sent a default "Debits are positive" when the engine couldn't tell, overriding the engine's inference and inverting every amount — it now follows the picked Amount column's preview (same rule as the engine) until the person sets it; the mapper intro names everything that's missing ("which columns hold the date, the description and the money") |

**Exit checklist**
- [x] Engine 226 (+5 `test_audit_follow.py`: replay to a second follower, waiting note, provider stored / cleared,
      v2 → v3 migration, per-person audit status on the web) · renderer 73 · typecheck, lint, both builds.
- [x] Browser (DevTools protocol, `python -m app.web`), **Gemini mode via the fake API**: drop zone → upload a CSV with
      unreadable headers → mapper (date / description / amount) → progress → **reload mid-audit: progress followed**
      → report in 2.5–2.8 s, summary chip `Gemma 4 · Gemini API` → drawer → rename re-scored in 2.2–2.4 s →
      "Not a subscription" re-scored in 2.3 s (subscriptions $87.46 → $71.97) → follow-up statement appended.
- [x] Same flow, **Ollama mode with local `gemma4:latest`**: audit 26–32 s (Gemma names under the 30 s budget, the rest
      finish in the background), chip `Gemma 4 · Ollama`, follow after reload, corrections re-scored in 2.4–4.9 s.
      Server-side the re-score is 2.4–4.6 s; the spread exists only in Ollama mode, where Gemma and TabPFN share the
      local GPU (Gemini mode: a steady 2.3 s). Within the 5 s budget in every run.
- [ ] Gemini mode with a real key (operator).
- [ ] Manual review in a real browser (user).

W5–W9 task tables are written at the start of each milestone, from §1–§2, so they reflect what the
previous review changed.
