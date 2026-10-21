# SlothSpend — MVP Specification

> **Version** 1.0 · 2026-10-20
> **Target** DEV × MLH Hacktoberfest Open-Source AI Challenge, Week 3 (entry window Oct 19–25, 2026)
> **Build budget** 2 days for app + packaged builds; remaining days for the write-up and demo video
> **Form factor** Zero-login, local-first Electron desktop app for macOS (Apple Silicon) and Windows (x64)

SlothSpend audits a 12-month bank-statement CSV entirely on the user's machine, finds recurring charges, price creep and duplicate charges, forecasts the next 30 days of subscription spend, and lets the user interrogate the audit through a local chatbot. It then patiently reminds the user before renewals and checks later statements to confirm a charge really stopped.

> **Inform, never act.** SlothSpend never cancels a subscription, never logs into or automates a merchant's website, and never contacts anyone on the user's behalf. It explains, reminds and drafts; the user decides and does the cancelling.

---

## 0. Decisions at a glance (v0 → v1)

| | Decision | Why |
|---|---|---|
| **Remove** | Automated cancellation — Browserbase + Stagehand, the dark-pattern demo portal, the approval gate | **SlothSpend never cancels anything.** It informs; the user cancels manually. This also removes the only point where data left the machine during normal use, two API keys, and the riskiest Day-2 work. |
| **Remove** | Temporal (bundled CLI dev server, worker, workflows) | Not needed once nothing is automated. Reminders are a SQLite table plus a small scheduler loop in the engine — one less binary to bundle, spawn, port-manage and keep alive. Only technology the product needs goes in. |
| **Change** | `gemma3` → **`gemma4:e4b`** (fallback `gemma4:e2b`) | `gemma3` has no tool calling in Ollama, so the v0 chat agent errors on the first request. Gemma 4 has native function calling (needs Ollama ≥ 0.20). |
| **Change** | "zombie_prob" = P(recurring) → **`recurring_prob` (TabPFN) + "Zombie suspect" review flag** | A bank CSV has no usage signal; calling every Netflix charge a zombie is wrong and judges will notice. |
| **Change** | Synthetic priors sampled in feature space + made-up regression target → **simulated transaction histories run through the same feature code; regressor predicts next-charge ratio with quantiles** | Removes train/serve skew and circularity; gives real uncertainty bands. |
| **Change** | Chat tools read cached rows → **live TabPFN tools inside the agent** (`forecast_spend` what-ifs, `score_merchant`) | Prior Labs explicitly favours TabPFN inside a wider prediction agent. |
| **Change** | Fixed port, unauthenticated localhost API → **dynamic port + per-launch token** | Any local process or web page could otherwise read the user's financial report from `127.0.0.1:8765`. |
| **Add** | CSV ingestion with header/sign/date detection + column-mapper fallback; newer statements append | v0 had no parser; "messy CSV" was unimplemented. Appending newer statements is what makes verification possible. |
| **Add** | Deterministic detectors: price creep, duplicate charge, overlap, possible annual | The demo's hero moment (July 5/6 double charge) had no implementation. |
| **Add** | **How to cancel** panel: generic checklist, a locally drafted cancellation request the user sends, and "I cancelled it" | The user does the cancelling; SlothSpend makes it easy and then verifies. |
| **Add** | **Renewal reminders**: a notification N days before renewal, snooze, catch-up after the app was closed, and a check on the next statement that a cancelled charge really stopped | Inform-only follow-through: the user cancels, SlothSpend confirms it worked. |
| **Add** | Boot/health screen with guided Ollama model pull and TabPFN weight setup | Ollama is user-installed and TabPFN-3.5 weights are license-gated. |
| **Cut** | Auth0 | Conflicts with zero-login; needs a user account and phone push. |
| **Cut** | In-app ElevenLabs briefing | Sends a financial summary to a cloud API; use ElevenLabs to **narrate the demo video** instead (explicitly allowed by the category). |
| **Cut** | SHAP explanations, nightly audits, Electron-side Sentry, macOS x64 build, Linux | Time. |
| **Stretch** | Sentry gen_ai agent tracing (opt-in), open at login so reminders fire on time, trial-conversion detector | Only after the Definition of Done passes. |

---

## 1. Challenge constraints that shape the build

- **Dates:** entry window Oct 19–25, 2026; winners the week of Oct 26. Check the Week 3 rules page for the exact cutoff time (Week 1 closed at 11:59 PM PDT).
- **New project rule:** the repo must be created and completed inside the window. Commits after the deadline must be listed in the README.
- **Judging:** Writing Quality (weighted most), Relevance to Prompt + Theme, Creativity, Technical Execution, Use of Partner Technology.
- **One prize per participant per challenge.** A submission is auto-entered into every category it qualifies for but can only win once — so depth in a few categories beats breadth across nine.
- **Prompt:** build with open-source AI at the core and explain *why open innovation matters*. "Show your work" via agent-session sharing is encouraged.
- **Categories (from the HF26 hub as of Oct 19 — re-check the Week 3 page, which may differ):**
  - Primary targets: **Overall**, **Best Use of TabPFN ($200)**, **Best Use of Gemma ($200)**.
  - Cheap qualifiers: **Sentry Agent Tracing**, **.tech Domain**, **GitHub Copilot** (GitHub Actions release pipeline counts), **Entire** (agent sessions in the write-up), **ElevenLabs** (demo narration).
  - Not used: **Browserbase**, **Auth0** and **Temporal** — the MVP has no browser automation, no accounts and no workflow engine. Only technology the product actually needs goes in; partner categories follow from that, not the other way round.
- **Theme "Slow and Steady"** → design pillar: *the sloth never rushes and never acts for you.* It waits weeks for the right moment to remind you, retries patiently when the local model is busy, and checks your next statement before declaring victory.

---

## 2. Product scope

### 2.1 User stories (MVP)

| ID | Story | Acceptance |
|---|---|---|
| US-1 | Open the app with no account and see whether everything it needs is ready. | Boot screen shows Engine, Gemma, TabPFN status with one-click fixes. |
| US-2 | Drop a bank CSV (or load the sample) and get an audit. | Report renders in ≤ 60 s (Apple Silicon) / ≤ 120 s (Windows CPU) for the sample. |
| US-3 | See which charges are recurring, which went up, which were double-charged, and what next month will cost. | Findings table + summary cards + burn chart with a q10–q90 band. |
| US-4 | Correct the model ("not a subscription", "keep") and see the audit update immediately. | Re-score ≤ 5 s, persists across restarts. |
| US-5 | Ask questions about the audit in plain language. | Ask Sloth answers with visible tool calls, grounded in numbers. |
| US-6 | Get a ready-to-send cancellation request, refund request or negotiation email that I send myself. | One click from a finding or the chat; copyable; SlothSpend never sends it. |
| US-7 | Be reminded before a subscription renews, so I can cancel it myself if I want to. | Desktop notification N days before renewal (default 3) with the How to cancel checklist; survives app restarts. |
| US-8 | After I cancel, find out whether the charges really stopped. | "I cancelled it" + a newer statement → "Verified: no charge" or "Still charged" with a refund-request draft. |
| US-9 | Trust that my bank data never leaves the laptop. | After model setup, the full flow works with Wi-Fi off; egress table in Settings. |

### 2.2 Scope

| In scope (MVP) | Stretch (only after DoD) | Out of scope |
|---|---|---|
| CSV ingest (US + Indian bank layouts), sample + follow-up CSVs | Sentry gen_ai spans (opt-in) | **Cancelling anything, browser automation, contacting merchants** |
| Gemma 4 merchant normalisation (local) | Open at login so reminders fire on time | Bank connections (Plaid, AA) |
| TabPFN-3.5 recurring classifier + next-charge regressor | Trial-conversion detector | Accounts / login / sync |
| Price-creep, duplicate, overlap, possible-annual detectors | Landing page polish | Auto-update, notarisation |
| Ask Sloth chat with tools + streaming | macOS x64 build | Linux, mobile |
| Email drafts the user sends (cancellation request / refund / negotiation) | | Multiple accounts, FX conversion |
| How to cancel checklist + "I cancelled it" | | Nightly scheduled audits |
| Renewal reminders (remind → snooze → user decides → verify on next statement) | | In-app voice briefing |
| Notification inbox + OS notifications | | |
| Landing page on slothspend.tech | | |
| Packaged `.dmg` (arm64) and `.exe` (x64) via CI | | |

---

## 3. Architecture

```
┌───────────────────── SlothSpend.dmg / SlothSpend Setup.exe ─────────────────────┐
│                                                                                 │
│  Electron main (TypeScript)                                                     │
│   • allocates a free port + a per-launch token   • spawns/supervises the engine │
│   • stores the Prior Labs key with safeStorage   • graceful + crash-safe exit   │
│        │ IPC via contextBridge (config, secrets, openExternal, restartEngine)   │
│        ▼                                                                        │
│  Renderer (React + Vite + Tailwind) ── HTTP / SSE + X-Sloth-Token ──► engine    │
│   Boot · Audit · Ask Sloth · Reminders · Settings      slothspend-engine        │
│   OS notifications for reminders                       (PyInstaller)            │
│                                                        FastAPI · SQLite         │
│                                                        TabPFN-3.5               │
│                                                        Ollama client            │
│                                                        reminder scheduler       │
└───────────────────────────────────────────────────────────┬─────────────────────┘
                                                            │ loopback only
                                                            ▼
                                              Ollama daemon (user-installed)
                                              gemma4:e4b
```

### 3.1 Process topology

| Process | Binary | Port | Lifetime |
|---|---|---|---|
| Electron main | app | — | app |
| Engine | `resources/engine/slothspend-engine[.exe]` (dev: `python -m app.main`) | `enginePort` (dynamic, 127.0.0.1) | spawned by main; exits on stdin EOF, so an Electron crash can't orphan it |
| Ollama | user-installed daemon | 11434 | external; engine warns if `OLLAMA_HOST` is not loopback |

### 3.2 Security model

- Engine binds to `127.0.0.1` only. Every route requires header `X-Sloth-Token` (32-byte random per launch, compared with `hmac.compare_digest`).
- CORS allows only the dev renderer origin and the packaged `file://` origin (`null`); the token is the real guard.
- Renderer: `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true`. Preload exposes a minimal API. `shell:open` only opens `https` URLs on an allowlist.
- The Prior Labs key is encrypted with Electron `safeStorage`, never returned to the renderer (a presence boolean only), and passed to the engine as `TABPFN_TOKEN` at spawn.
- **Inform, never act.** There is no browser automation, no merchant integration and no outbound messaging. The engine's only side effects are its own SQLite file and in-app/OS notifications. Every chat tool is read-only except `set_renewal_reminder`, which schedules a reminder and nothing else.
- Gemma is told never to invent cancellation links, phone numbers or merchant-specific steps (it can't verify them); the How to cancel checklist is static, generic copy.

### 3.3 Data egress (put this table in Settings and the write-up)

| Data | Destination | When | Default |
|---|---|---|---|
| CSV rows, merchants, amounts, chat history, reminders | Nowhere — local SQLite in the OS app-data folder | always | — |
| Merchant descriptions → Gemma | Local Ollama on 127.0.0.1 | import | on |
| Reminder and email facts → Gemma | Local Ollama on 127.0.0.1 | when a reminder fires or a draft is requested | on |
| TabPFN inputs | Local PyTorch | import / chat | on |
| TabPFN-3.5 weights | Prior Labs download (one time, license-gated) | first run | needs user's key |
| Gemma weights | Ollama registry (one time) | first run | user-triggered |
| Span timings, token counts, tool names (no prompt or response text) | Sentry | telemetry opt-in | off |

After the one-time model downloads, SlothSpend makes **no network calls at all** unless telemetry is switched on.

---

## 4. Repository layout

```
slothspend/
├── package.json
├── electron.vite.config.ts
├── electron-builder.yml
├── tsconfig.json / tsconfig.node.json / tsconfig.web.json
├── build/                         # icons for electron-builder
├── src/
│   ├── main/
│   │   ├── index.ts               # app lifecycle, window, IPC
│   │   ├── sidecars.ts            # port, engine spawn, teardown
│   │   └── secrets.ts             # safeStorage-backed Prior Labs key
│   ├── preload/index.ts
│   └── renderer/
│       ├── index.html
│       └── src/
│           ├── App.tsx
│           ├── api.ts             # fetch + SSE helpers (token header), notification polling
│           ├── screens/{Boot,Workspace,Settings}.tsx
│           └── components/{ImportBar,ColumnMapper,SummaryCards,BurnChart,FindingsTable,
│                           MerchantDrawer,HowToCancel,ChatPane,ToolBadge,RemindersPanel,
│                           NotificationBell}.tsx
├── engine/
│   ├── requirements.txt
│   ├── run_engine.py              # PyInstaller entry point
│   ├── slothspend_engine.spec
│   ├── app/
│   │   ├── main.py  config.py  security.py  state.py  paths.py
│   │   ├── db.py  ingest.py  normalize.py  features.py  detectors.py
│   │   ├── tabular.py  report.py  llm_summary.py
│   │   ├── agent.py  tools.py  telemetry.py
│   │   ├── reminders.py  notes.py # scheduler loop + Gemma/template reminder text
│   │   └── data/{priors_recurring.csv, priors_hikes.csv, sample_bank_12m.csv,
│   │            followup_cancelled.csv, followup_still_charged.csv}
│   ├── scripts/{make_sample_data.py, make_priors.py, smoke_test.py}
│   └── tests/{test_ingest.py, test_features.py, test_detectors.py, test_reminders.py, test_egress.py}
├── site/
│   └── index.html                 # landing page on slothspend.tech
└── .github/workflows/release.yml
```

---

## 5. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Shell | Electron (current stable) + **electron-vite** (`npm create @quick-start/electron@latest -- --template react-ts`) | Saves hours on main/preload/renderer build wiring. Output in `out/`. |
| UI | React + TypeScript, Tailwind CSS, Recharts, `react-markdown`, `lucide-react`, `@microsoft/fetch-event-source` | `EventSource` cannot send headers; use fetch-event-source for SSE with the token. |
| Engine | Python 3.11, FastAPI, uvicorn, `sse-starlette`, `python-multipart`, pandas, numpy | 3.11 has the smoothest PyInstaller + torch story. |
| Tabular | `tabpfn` (a release exposing `ModelVersion.V3_5` / `V3_5_FAST`) | Local inference; weights license-gated (§12.4). |
| LLM | `ollama` Python client, model `gemma4:e4b` (`gemma4:e2b` on ≤ 8 GB RAM) | Needs `think=` and streaming tool calls; Ollama ≥ 0.20 for Gemma 4 tools. |
| Telemetry | `sentry-sdk[fastapi]` (opt-in) | gen_ai spans, no prompt content. |
| Packaging | PyInstaller (onedir), electron-builder (dmg arm64, NSIS x64), GitHub Actions | |

Pin exact versions with `uv lock` / `npm ci` after the first green build. Do **not** reuse v0 pins (`ollama==0.4.4` and `tabpfn>=2.0.0` are stale or too loose); `stagehand`, `temporalio` and `elevenlabs` are no longer dependencies.

`engine/requirements.txt` (unpinned starting point):

```
fastapi
uvicorn
sse-starlette
python-multipart
pydantic>=2
pandas
numpy
tabpfn
ollama
sentry-sdk[fastapi]
```

Dev only: `pytest`, `pyinstaller`.

---

## 6. Electron main: boot, supervision, teardown

### 6.1 Boot sequence

1. `app.whenReady()` → allocate a free `enginePort` and a per-launch token.
2. Create the window **immediately** and load the renderer; it shows the Boot screen.
3. Spawn the engine.
4. Renderer calls `window.sloth.getConfig()` → `{ apiBase, token, version, platform }` and polls `GET /health` every second.
5. The Workspace unlocks once the Engine is `ok`. Missing Ollama or TabPFN → degraded mode with a banner (rule-based normalisation / heuristic scorer), never a blank window.

There is exactly one child process. No PID files or process-group tricks are needed: the engine exits on its own when its stdin closes, which happens on a normal quit and on an Electron crash.

### 6.2 `src/main/sidecars.ts`

```ts
import { app } from "electron";
import { spawn, execFileSync, type ChildProcess } from "node:child_process";
import net from "node:net";
import path from "node:path";

const isWin = process.platform === "win32";
const isDev = !app.isPackaged;

export interface RuntimeConfig {
  enginePort: number;
  token: string;
  dataDir: string;
}

export function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address() as net.AddressInfo;
      srv.close(() => resolve(port));
    });
  });
}

function engineCommand(): { cmd: string; args: string[]; cwd?: string } {
  if (isDev) {
    const py = process.env.SLOTH_PYTHON ?? (isWin ? "python" : "python3");
    return { cmd: py, args: ["-m", "app.main"], cwd: path.join(app.getAppPath(), "engine") };
  }
  const exe = isWin ? "slothspend-engine.exe" : "slothspend-engine";
  return { cmd: path.join(process.resourcesPath, "engine", exe), args: [] };
}

export function killTree(pid: number | undefined): void {
  if (!pid) return;
  try {
    if (isWin) execFileSync("taskkill", ["/pid", String(pid), "/T", "/F"], { stdio: "ignore" });
    else process.kill(pid, "SIGTERM");
  } catch {
    /* already gone */
  }
}

export function startEngine(cfg: RuntimeConfig, secretsEnv: Record<string, string>): ChildProcess {
  const { cmd, args, cwd } = engineCommand();
  const proc = spawn(cmd, args, {
    cwd,
    env: {
      ...process.env,
      ...secretsEnv,
      SLOTH_PORT: String(cfg.enginePort),
      SLOTH_TOKEN: cfg.token,
      SLOTH_DATA_DIR: cfg.dataDir,
      TABPFN_MODEL_CACHE_DIR: path.join(cfg.dataDir, "tabpfn-weights"),
      PYTHONUNBUFFERED: "1",
    },
    stdio: ["pipe", "pipe", "pipe"], // stdin stays open: EOF tells the engine its parent is gone
    windowsHide: true,
  });
  proc.stdout?.on("data", (d) => console.log(`[engine] ${d}`));
  proc.stderr?.on("data", (d) => console.error(`[engine] ${d}`));
  return proc;
}

export async function stopEngine(proc: ChildProcess | null, cfg: RuntimeConfig): Promise<void> {
  if (!proc) return;
  try {
    await fetch(`http://127.0.0.1:${cfg.enginePort}/shutdown`, {
      method: "POST",
      headers: { "X-Sloth-Token": cfg.token },
      signal: AbortSignal.timeout(2000),
    });
  } catch {
    /* engine may already be down */
  }
  proc.stdin?.end();
  await new Promise((r) => setTimeout(r, 1500));
  if (proc.exitCode === null) killTree(proc.pid);
}
```

### 6.3 `src/main/index.ts` (essentials)

```ts
import { app, BrowserWindow, ipcMain, shell } from "electron";
import { randomBytes } from "node:crypto";
import path from "node:path";
import type { ChildProcess } from "node:child_process";
import { freePort, startEngine, stopEngine, type RuntimeConfig } from "./sidecars";
import { secretsEnv } from "./secrets";

let cfg: RuntimeConfig;
let engine: ChildProcess | null = null;
let quitting = false;

const OPEN_ALLOW = [/^https:\/\/slothspend\.tech/, /^https:\/\/ollama\.com/,
  /^https:\/\/platform\.priorlabs\.ai/, /^https:\/\/github\.com/];

async function boot(): Promise<void> {
  cfg = {
    enginePort: await freePort(),
    token: randomBytes(32).toString("hex"),
    dataDir: app.getPath("userData"),
  };
  engine = startEngine(cfg, secretsEnv());
}

app.whenReady().then(async () => {
  if (process.platform === "win32") app.setAppUserModelId("tech.slothspend.desktop"); // Windows toast notifications
  const booting = boot();

  ipcMain.handle("config:get", async () => {
    await booting;
    return {
      apiBase: `http://127.0.0.1:${cfg.enginePort}`,
      token: cfg.token,
      version: app.getVersion(),
      platform: process.platform,
    };
  });
  ipcMain.handle("shell:open", (_e, url: string) => {
    if (OPEN_ALLOW.some((re) => re.test(url))) return shell.openExternal(url);
  });
  ipcMain.handle("engine:restart", async () => {
    await stopEngine(engine, cfg);
    engine = startEngine(cfg, secretsEnv());
  });

  const win = new BrowserWindow({
    width: 1360, height: 860, minWidth: 1100, minHeight: 720,
    title: "SlothSpend", backgroundColor: "#0F172A",
    webPreferences: {
      preload: path.join(__dirname, "../preload/index.js"),
      contextIsolation: true, nodeIntegration: false, sandbox: true,
    },
  });
  if (process.env.ELECTRON_RENDERER_URL) win.loadURL(process.env.ELECTRON_RENDERER_URL);
  else win.loadFile(path.join(__dirname, "../renderer/index.html"));
});

app.on("before-quit", (e) => {
  if (quitting) return;
  e.preventDefault();
  quitting = true;
  stopEngine(engine, cfg).finally(() => app.quit());
});

app.on("window-all-closed", () => app.quit());
```

`secrets.ts` maps the stored Prior Labs key to `TABPFN_TOKEN` and the telemetry toggle to `SLOTH_TELEMETRY=1|0`. Saving either calls `engine:restart`; reminders live in SQLite, so nothing is lost.

---

## 7. Engine (Python sidecar)

### 7.1 App, lifespan, security

`app/paths.py`

```python
import sys
from pathlib import Path

# PyInstaller onedir puts bundled data under sys._MEIPASS; in dev use the package folder.
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
DATA = BASE / "app" / "data"
```

`app/main.py`

```python
import asyncio
import os
import sys
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db, telemetry
from .config import settings
from .reminders import run_scheduler
from .security import require_token
from .state import runtime
from .tabular import tabular


def _stdin_watchdog() -> None:
    """Electron keeps our stdin open. EOF means the parent quit or crashed."""
    try:
        sys.stdin.read()
    finally:
        os._exit(0)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    telemetry.init()
    db.init()
    if not os.environ.get("SLOTH_NO_WATCHDOG"):
        threading.Thread(target=_stdin_watchdog, daemon=True).start()
    threading.Thread(target=tabular.warm_up, daemon=True).start()  # never block startup on torch
    runtime.scheduler_task = asyncio.create_task(run_scheduler())  # renewal reminders (§7.10)
    yield
    runtime.scheduler_task.cancel()


app = FastAPI(lifespan=lifespan, dependencies=[Depends(require_token)])
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "null"],
    allow_methods=["*"],
    allow_headers=["X-Sloth-Token", "Content-Type"],
)
# Routers (report, chat, reminders, setup) are included here.


def run() -> None:
    # log_config=None: avoid uvicorn's colour formatter touching sys.stderr in frozen builds
    uvicorn.run(app, host="127.0.0.1", port=settings.port, log_config=None)


if __name__ == "__main__":
    run()
```

`app/security.py`

```python
import hmac

from fastapi import Header, HTTPException

from .config import settings


async def require_token(x_sloth_token: str | None = Header(default=None)) -> None:
    if not x_sloth_token or not hmac.compare_digest(x_sloth_token, settings.token):
        raise HTTPException(status_code=401, detail="bad token")
```

`run_engine.py` (PyInstaller entry): `from app.main import run; run()`.

### 7.2 SQLite schema (`app/db.py`)

Open with `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON`. DB file: `<userData>/slothspend.db`.

```sql
CREATE TABLE IF NOT EXISTS imports (
  id INTEGER PRIMARY KEY,
  file_name TEXT, file_sha256 TEXT UNIQUE, currency TEXT,
  mapping_json TEXT, row_count INTEGER, imported_at TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY,
  import_id INTEGER REFERENCES imports(id) ON DELETE CASCADE,
  tx_date TEXT NOT NULL,              -- ISO date
  raw_description TEXT NOT NULL,
  desc_key TEXT NOT NULL,             -- pre-cleaned description (cache key)
  amount REAL NOT NULL,               -- always positive
  direction TEXT NOT NULL CHECK (direction IN ('debit','credit')),
  merchant TEXT, category TEXT,
  is_duplicate INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_tx_merchant ON transactions(merchant, tx_date);

CREATE TABLE IF NOT EXISTS merchant_map (
  desc_key TEXT PRIMARY KEY,
  merchant TEXT NOT NULL, category TEXT NOT NULL,
  subscription_like INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL CHECK (source IN ('llm','rule','user')),
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS series (
  id INTEGER PRIMARY KEY,
  merchant TEXT UNIQUE NOT NULL, category TEXT,
  features_json TEXT,                 -- the exact row fed to TabPFN
  n_charges INTEGER, first_date TEXT, last_date TEXT,
  cadence TEXT, cadence_days REAL,
  last_amount REAL, monthly_equiv REAL,
  recurring_prob REAL, scorer TEXT,   -- 'tabpfn-3.5' | 'tabpfn-3.5-fast' | 'heuristic'
  similar_json TEXT,                  -- nearest prior archetypes (explanation)
  next_due_date TEXT,
  fc_q10 REAL, fc_q50 REAL, fc_q90 REAL, hike_prob REAL,
  flags_json TEXT,                    -- ["price_creep","duplicate_charge","overlap","zombie_suspect","possible_annual"]
  flag_details_json TEXT,
  priority REAL,
  cancellable INTEGER DEFAULT 0,
  status TEXT DEFAULT 'active'        -- active|keep|not_subscription|user_cancelled
);

CREATE TABLE IF NOT EXISTS user_labels (
  merchant TEXT PRIMARY KEY,
  label INTEGER NOT NULL,             -- 1 recurring, 0 not
  features_json TEXT NOT NULL,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS report_meta (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  generated_at TEXT, report_date TEXT, currency TEXT,
  monthly_recurring REAL, fc30_q10 REAL, fc30_q50 REAL, fc30_q90 REAL,
  potential_savings REAL, executive_summary TEXT, scorer TEXT
);

CREATE TABLE IF NOT EXISTS chat_messages (
  id INTEGER PRIMARY KEY,
  conversation_id TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('user','assistant','tool')),
  content TEXT, tool_name TEXT, tool_args_json TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS reminders (
  series_id INTEGER PRIMARY KEY REFERENCES series(id),  -- one reminder per subscription
  merchant TEXT NOT NULL,
  next_due_date TEXT NOT NULL,          -- renewal date (YYYY-MM-DD)
  days_before INTEGER DEFAULT 3,
  remind_at TEXT,                       -- UTC time of the next scheduled event; NULL = nothing pending
  reminders_sent INTEGER DEFAULT 0,
  phase TEXT NOT NULL,                  -- WATCHING|REMINDED|SNOOZED|KEPT|EXPIRED|STOPPED|
                                        -- AWAITING_STATEMENT|VERIFIED_STOPPED|STILL_CHARGED
  detail TEXT, cancelled_on TEXT,
  created_at TEXT, updated_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_reminders_due ON reminders(remind_at);

CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY,
  series_id INTEGER REFERENCES series(id),
  kind TEXT NOT NULL,                   -- reminder|verified|still_charged
  title TEXT NOT NULL, body TEXT NOT NULL,
  created_at TEXT, read_at TEXT
);

CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
```

### 7.3 CSV ingestion (`app/ingest.py`)

Pipeline: bytes → encoding (`utf-8-sig`, fallback `latin-1`) → delimiter (`csv.Sniffer`, fallback `,`) → **header row detection** (first 30 rows; many Indian bank exports have preamble lines) → column mapping → date parsing → amount/sign → debits only for analysis.

```python
import re

HEADER_SYNONYMS = {
    "date": ["date", "txn date", "transaction date", "posting date", "value date", "value dt", "tran date"],
    "description": ["description", "narration", "details", "particulars", "memo", "payee",
                    "transaction details", "remarks"],
    "amount": ["amount", "amt", "transaction amount", "amount (inr)", "amount (usd)"],
    "debit": ["debit", "withdrawal", "withdrawal amt.", "withdrawal amount", "dr", "money out", "paid out"],
    "credit": ["credit", "deposit", "deposit amt.", "deposit amount", "cr", "money in", "paid in"],
    "type": ["type", "dr/cr", "cr/dr", "transaction type"],
}


def _norm(cell: str) -> str:
    return re.sub(r"\s+", " ", (cell or "").strip().lower())


def detect_header(rows: list[list[str]]) -> tuple[int, dict[str, int]]:
    best_idx, best_map = -1, {}
    for idx, row in enumerate(rows[:30]):
        mapping: dict[str, int] = {}
        for col, cell in enumerate(row):
            name = _norm(cell)
            for field, names in HEADER_SYNONYMS.items():
                if field not in mapping and name in names:
                    mapping[field] = col
        if len(mapping) > len(best_map):
            best_idx, best_map = idx, mapping
    return best_idx, best_map


def mapping_confidence(mapping: dict[str, int]) -> float:
    has_amount = "amount" in mapping or "debit" in mapping
    return (("date" in mapping) + ("description" in mapping) + has_amount) / 3


def parse_amount(text: str) -> float | None:
    s = (text or "").strip()
    if not s:
        return None
    negative = (s.startswith("(") and s.endswith(")")) or s.startswith("-") or s.upper().endswith("DR")
    digits = re.sub(r"[^0-9.]", "", s)
    if not digits:
        return None
    value = float(digits)
    return -value if negative else value
```

Rules:

- **Dates:** `pd.to_datetime(errors="coerce")` with `dayfirst` inferred — any first component > 12 → day-first; any second component > 12 → month-first; otherwise default by currency (INR → day-first, USD → month-first). Rows with unparseable dates are dropped and counted.
- **Sign:** separate debit/credit columns → debit wins. Single amount column → if > 50 % negative, negatives are debits; a `type` column with DR/CR overrides. Otherwise show the mapper's "debits are positive" toggle.
- **Currency:** detect `$ ₹ € £` in amount cells or headers; else the Settings default.
- **Confidence < 1.0** → `POST /import` returns `needs_mapping: true` with a 10-row preview and the UI shows `ColumnMapper`.
- **Re-import** of the same file (SHA-256) is a no-op.
- **Newer statements accumulate:** a later export appends only rows dated after the latest stored transaction (boundary-day overlap is skipped), then the report recomputes over everything. This is how reminders verify that a cancelled charge stopped (§7.10).
- `report_date` = the latest transaction date in the file (keeps demos deterministic; never `now()`).
- European decimal commas are out of scope (documented limitation).

### 7.4 Merchant normalisation with Gemma (`app/normalize.py`)

1. **Pre-clean** each description into a `desc_key` (uppercase; strip card masks, long digit runs, dates, `#refs`, and rail/channel noise such as POS, ACH, NEFT, IMPS, UPI, ECOM). Many rows collapse to the same key.
2. **Dedupe** keys and skip any already in `merchant_map` (cache survives re-imports).
3. **Batch** 25 keys per call to `gemma4:e4b` with **Ollama structured outputs** (JSON schema in `format`), `temperature 0`, `think=False`, `num_ctx 8192`. Output is keyed by **index**, so the model can't mangle keys.
4. **Validate** with Pydantic; any missing or invalid index → rule fallback (title-case first two tokens, category `Other`, `source='rule'`). The fallback must be generic — no hard-coded demo merchants.
5. User edits in the drawer write `source='user'` and win over everything.

```python
import json
import re

import ollama
from pydantic import BaseModel

CATEGORIES = ["Streaming", "Music", "Software", "Cloud Storage", "Fitness", "News & Media", "Telecom",
              "Utilities", "Insurance", "Housing", "Food Delivery", "Groceries", "Dining", "Transport",
              "Shopping", "Travel", "Health", "Education", "Transfers", "Fees", "Other"]

NOISE = [
    r"\b(POS|ACH|DEBIT|CREDIT|CARD|PURCHASE|RECURRING|PAYMENT|ONLINE|ECOM|NEFT|IMPS|UPI|VISA|MASTERCARD|TXN|REF)\b",
    r"\b[X\*]{2,}\d{2,4}\b",
    r"\b\d{4,}\b",
    r"\b\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?\b",
    r"#\S+",
    r"[^A-Z0-9&\.\* ]",
]


def desc_key(raw: str) -> str:
    s = raw.upper()
    for pattern in NOISE:
        s = re.sub(pattern, " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return (s or raw.upper())[:60]


SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "i": {"type": "integer"},
                    "merchant": {"type": "string"},
                    "category": {"type": "string", "enum": CATEGORIES},
                    "subscription_like": {"type": "boolean"},
                },
                "required": ["i", "merchant", "category", "subscription_like"],
            },
        }
    },
    "required": ["items"],
}

PROMPT = """You clean bank transaction descriptions.
For each numbered line return: the merchant's common brand name (Title Case, no store numbers,
cities or reference codes), one category from the allowed list, and subscription_like=true only if
this kind of merchant usually bills a recurring plan (streaming, music, software, gym, cloud storage,
news, phone plan, insurance).
Examples:
0: "NETFLIX.COM 866" -> Netflix, Streaming, true
1: "WHOLEFDS MKT" -> Whole Foods, Groceries, false
Lines:
{lines}"""


class Item(BaseModel):
    i: int
    merchant: str
    category: str
    subscription_like: bool


class Batch(BaseModel):
    items: list[Item]


def rule_fallback(key: str) -> dict:
    name = " ".join(key.split()[:2]).title() or "Unknown"
    return {"merchant": name, "category": "Other", "subscription_like": False, "source": "rule"}


async def normalize_batch(client: ollama.AsyncClient, model: str, keys: list[str]) -> dict[str, dict]:
    lines = "\n".join(f"{i}: {json.dumps(k)}" for i, k in enumerate(keys))
    try:
        resp = await client.chat(
            model=model,
            messages=[{"role": "user", "content": PROMPT.format(lines=lines)}],
            format=SCHEMA,
            think=False,
            options={"temperature": 0, "num_ctx": 8192},
        )
        items = Batch.model_validate_json(resp.message.content).items
    except Exception:
        items = []
    by_index = {it.i: it for it in items if 0 <= it.i < len(keys)}
    out: dict[str, dict] = {}
    for i, key in enumerate(keys):
        it = by_index.get(i)
        if it and it.merchant.strip():
            category = it.category if it.category in CATEGORIES else "Other"
            out[key] = {"merchant": it.merchant.strip()[:40], "category": category,
                        "subscription_like": it.subscription_like, "source": "llm"}
        else:
            out[key] = rule_fallback(key)
    return out
```

`subscription_like` is reused as a **TabPFN feature** — Gemma acts as a local feature extractor for TabPFN. This "two open models cooperating" angle serves both featured categories.

### 7.5 Feature extraction (`app/features.py`)

Unit: one merchant series of **debits**, duplicates removed (detectors run first, §7.7). Series with ≥ 2 charges go to TabPFN; single charges go to the possible-annual rule.

```python
import numpy as np
import pandas as pd

CADENCES = {  # label: (period_days, tolerance_days)
    "weekly": (7.0, 2),
    "biweekly": (14.0, 3),
    "monthly": (30.44, 4),
    "quarterly": (91.3, 8),
    "annual": (365.25, 15),
}

FEATURES = ["n_charges", "span_days", "median_interval", "interval_cv", "cadence", "cadence_fit",
            "dom_std", "amount_cv", "modal_amount_share", "log_amount", "days_since_last",
            "category", "subscription_like"]


def series_features(g: pd.DataFrame, report_date: pd.Timestamp, category: str, sub_hint: bool) -> dict:
    g = g.sort_values("tx_date")
    dates = pd.to_datetime(g["tx_date"])
    amounts = g["amount"].to_numpy(float)
    iv = dates.diff().dt.days.dropna().to_numpy(float)

    best_label, best_fit = "irregular", 0.0
    if len(iv):
        for label, (period, tol) in CADENCES.items():
            fit = float(np.mean(np.abs(iv - period) <= tol))
            if fit > best_fit:
                best_label, best_fit = label, fit
    if best_fit < 0.5:
        best_label = "irregular"

    med = float(np.median(amounts))
    mode_amount = float(pd.Series(amounts).round(2).mode().iloc[0])
    mean_iv = float(np.mean(iv)) if len(iv) else np.nan
    return {
        "n_charges": int(len(amounts)),
        "span_days": int((dates.iloc[-1] - dates.iloc[0]).days),
        "median_interval": float(np.median(iv)) if len(iv) else np.nan,
        "interval_cv": float(np.std(iv) / mean_iv) if len(iv) > 1 and mean_iv > 0 else np.nan,
        "cadence": best_label,
        "cadence_fit": best_fit,
        "dom_std": float(dates.dt.day.std(ddof=0)),
        "amount_cv": float(np.std(amounts) / med) if med > 0 else 0.0,
        "modal_amount_share": float(np.mean(np.abs(amounts - mode_amount) <= 0.01 * max(med, 1.0))),
        "log_amount": float(np.log1p(med)),
        "days_since_last": int((report_date - dates.iloc[-1]).days),
        "category": category,
        "subscription_like": int(sub_hint),
    }
```

TabPFN takes raw DataFrames with string categoricals and NaNs, so `cadence` and `category` stay as strings.

### 7.6 TabPFN-3.5 models (`app/tabular.py`)

**Model A — recurring classifier.** Context = `priors_recurring.csv` (≈ 600 simulated series, §11) **+ the user's own corrections** from `user_labels` (appended, repeated ×3 to emphasise them). Because TabPFN learns in context, a correction re-scores everything in seconds with no training loop — this is the headline TabPFN story.

**Model B — next-charge regressor.** One row per historical charge *k ≥ 2* of each recurring series: `prev_amount_log`, `prev2_amount_log`, `charges_since_change`, `n_changes_so_far`, `tenure_charges`, `cadence`, `category`, `month_of_year` → target `amount_k / amount_{k-1}`. Context = the user's own rows (pooled across merchants) + `priors_hikes.csv` (simulated annual hikes, so sparse histories still know hikes happen). Query = each series' *next* step. Predict 19 quantiles (0.05…0.95):

- next-charge quantiles = `last_amount × ratio_quantiles`
- `hike_prob ≈ share of the 19 predicted quantiles above 1.02` (approximation — say so in the UI tooltip)

**30-day forecast.** For each active recurring series, enumerate due dates in `(report_date, report_date + 30d]` from its cadence; sum q10 / q50 / q90 separately. The band is conservative (a sum of quantiles is not the quantile of a sum) — note it in the tooltip.

**Explanation without SHAP.** For each series, find the 5 nearest prior rows (standardised numeric features) and report the majority archetype ("Looks like: monthly fixed-price subscription — 5/5 nearest examples").

**Version + device.** `V3_5` when CUDA or MPS is available, else `V3_5_FAST` (alpha) on CPU. Hold a `threading.Lock` around fit/predict.

**Weights gate.** If no `*.safetensors` file for 3.5 exists in `TABPFN_MODEL_CACHE_DIR` **and** `TABPFN_TOKEN` is unset, don't construct the model at all (avoid any interactive login attempt in a GUI process) → `status = "missing_weights"` → heuristic scorer.

```python
import threading
from pathlib import Path
import os

import numpy as np
import pandas as pd

from .features import FEATURES
from .paths import DATA

QUANTILES = [round(q, 2) for q in np.arange(0.05, 0.951, 0.05)]
REG_FEATURES = ["prev_amount_log", "prev2_amount_log", "charges_since_change", "n_changes_so_far",
                "tenure_charges", "cadence", "category", "month_of_year"]


class Tabular:
    def __init__(self) -> None:
        self.status = "cold"            # cold | warming | ready | missing_weights | error
        self.model_name = None
        self.error: str | None = None
        self._lock = threading.Lock()
        self._clf = None
        self._reg = None
        self.priors = pd.read_csv(DATA / "priors_recurring.csv")
        self.hikes = pd.read_csv(DATA / "priors_hikes.csv")

    def _weights_present(self) -> bool:
        cache = Path(os.environ.get("TABPFN_MODEL_CACHE_DIR", ""))
        return cache.is_dir() and any("v3.5" in p.name for p in cache.glob("*.safetensors"))

    def warm_up(self) -> None:
        if not self._weights_present() and not os.environ.get("TABPFN_TOKEN"):
            self.status = "missing_weights"
            return
        self.status = "warming"
        try:
            import torch
            from tabpfn import TabPFNClassifier, TabPFNRegressor
            from tabpfn.constants import ModelVersion

            accel = torch.cuda.is_available() or torch.backends.mps.is_available()
            version = ModelVersion.V3_5 if accel else ModelVersion.V3_5_FAST
            self.model_name = "tabpfn-3.5" if accel else "tabpfn-3.5-fast"
            self._clf = TabPFNClassifier.create_default_for_version(version)
            self._reg = TabPFNRegressor.create_default_for_version(version)
            # Touch the weights once (downloads on first run when a token is present).
            sample = self.priors.sample(40, random_state=0)
            with self._lock:
                self._clf.fit(sample[FEATURES], sample["label"])
                self._clf.predict_proba(sample[FEATURES].head(2))
            self.status = "ready"
        except Exception as exc:  # surfaced on the Boot screen
            self.status, self.error = "error", str(exc)

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    def recurring_prob(self, X: pd.DataFrame, user_labels: pd.DataFrame) -> np.ndarray:
        if not self.ready:
            return heuristic_prob(X)
        ctx = pd.concat([self.priors, *([user_labels] * 3)], ignore_index=True)
        with self._lock:
            self._clf.fit(ctx[FEATURES], ctx["label"])
            proba = self._clf.predict_proba(X[FEATURES])
        return proba[:, list(self._clf.classes_).index(1)]

    def ratio_quantiles(self, ctx: pd.DataFrame, query: pd.DataFrame) -> np.ndarray:
        """Returns an (n_query, 19) array of predicted next/last price ratios."""
        if not self.ready or len(query) == 0:
            return np.ones((len(query), len(QUANTILES)))
        full = pd.concat([self.hikes, ctx], ignore_index=True)
        with self._lock:
            self._reg.fit(full[REG_FEATURES], full["ratio"])
            qs = self._reg.predict(query[REG_FEATURES], output_type="quantiles", quantiles=QUANTILES)
        return np.vstack(qs).T


def heuristic_prob(X: pd.DataFrame) -> np.ndarray:
    """Fallback when TabPFN weights are unavailable. Clearly labelled 'heuristic' in the UI."""
    score = (0.55 * X["cadence_fit"].fillna(0)
             + 0.25 * X["modal_amount_share"].fillna(0)
             + 0.10 * (X["n_charges"] >= 4)
             + 0.10 * X["subscription_like"].fillna(0))
    return score.clip(0, 1).to_numpy()


tabular = Tabular()
```

### 7.7 Detectors (`app/detectors.py`)

All rule-based, explainable, and run **before** feature extraction (duplicates are removed from the series used for features).

| Flag | Rule | Detail shown |
|---|---|---|
| `duplicate_charge` | Same merchant, amounts within 1 %, dates ≤ 3 days apart, series cadence ≥ 25 days | both dates + amount + tx ids |
| `price_creep` | Fixed-price series (cadence_fit ≥ 0.6). Find the current price run (trailing charges within 1 % of the last). Baseline = median of up to 3 charges before the run, and those must be stable (CV ≤ 5 %). Flag if change ≥ +5 % and ≥ 0.50 currency units | from → to, %, since date |
| `overlap` | ≥ 2 active recurring series (prob ≥ 0.7) in the same category among Streaming, Music, Cloud Storage, Fitness, News & Media, Software | "You pay for 3 streaming services" |
| `possible_annual` | Single charge, `subscription_like`, amount ≥ 20, cancellable category | next due = date + 365 d, "low confidence" chip |
| `zombie_suspect` | prob ≥ 0.7, cancellable, status not keep/not_subscription/user_cancelled, and (overlap or price_creep or duplicate or ≥ 6 charges) | "Bank data can't see usage — keep it, or cancel it yourself" |

```python
import numpy as np
import pandas as pd


def duplicate_charges(g: pd.DataFrame, cadence_days: float) -> list[dict]:
    if not cadence_days or cadence_days < 25:
        return []
    g = g.sort_values("tx_date")
    rows = list(zip(pd.to_datetime(g["tx_date"]), g["amount"].astype(float), g["id"]))
    found = []
    for (d1, a1, i1), (d2, a2, i2) in zip(rows, rows[1:]):
        if (d2 - d1).days <= 3 and abs(a2 - a1) <= 0.01 * max(a1, a2):
            found.append({"first": d1.date().isoformat(), "second": d2.date().isoformat(),
                          "amount": round(a2, 2), "tx_ids": [int(i1), int(i2)]})
    return found


def price_creep(g: pd.DataFrame, cadence_fit: float) -> dict | None:
    if cadence_fit < 0.6:
        return None
    g = g.sort_values("tx_date")
    a = g["amount"].to_numpy(float)
    dates = pd.to_datetime(g["tx_date"]).dt.date.to_numpy()
    if len(a) < 3:
        return None
    last = a[-1]
    k = len(a) - 1
    while k > 0 and abs(a[k - 1] - last) <= 0.01 * last:
        k -= 1
    if k == 0:
        return None
    before = a[max(0, k - 3):k]
    baseline = float(np.median(before))
    if baseline <= 0 or (len(before) > 1 and np.std(before) / baseline > 0.05):
        return None
    change = (last - baseline) / baseline
    if change >= 0.05 and (last - baseline) >= 0.5:
        return {"from": round(baseline, 2), "to": round(float(last), 2),
                "pct": round(change * 100, 1), "since": dates[k].isoformat()}
    return None
```

**Priority** (sort order) = `monthly_equiv × (1 + 0.5·overlap + 0.5·price_creep + 1.0·duplicate)`.
**Cancellable categories** (where the UI offers **How to cancel** and **Remind me**): Streaming, Music, Software, Cloud Storage, Fitness, News & Media, Education, Food Delivery memberships. Bills (Utilities, Telecom, Insurance, Housing) get **Draft negotiation email** instead. The user sends it — that's what makes SlothSpend a *bill negotiator* without ever acting on their behalf.

### 7.8 Report pipeline (`app/report.py`)

`POST /import/{id}/confirm` and `POST /demo/load-sample` stream progress over SSE:

1. `parse` — rows → `transactions` (debits analysed; credits stored for chat questions)
2. `normalize` — unique `desc_key`s via cache + Gemma batches (progress `done/total`)
3. `detect` — duplicates per merchant, mark `is_duplicate`
4. `features` — per series (dedup'd)
5. `score` — TabPFN classifier → `recurring_prob`, nearest archetypes
6. `forecast` — regressor quantiles, next due dates, hike probability, 30-day sums
7. `flags` — creep, overlap, possible annual, zombie suspect, priority
8. `summary` — Gemma rewrites a templated fact sheet into 3–4 calm sentences (`temperature 0.4`). Numbers are formatted in code and passed in; the prompt forbids new numbers. Template fallback when Ollama is down.
9. `done` — persist `series` and `report_meta`, then call `reminders.verify_after_import()` for reminders in `AWAITING_STATEMENT` (§7.10)

Re-score after a user label (`POST /series/{id}/label`) re-runs steps 5–7 only (no LLM) and must finish in ≤ 5 s.

### 7.9 Ask Sloth agent (`app/agent.py`, `app/tools.py`)

**Model** `gemma4:e4b`, `think=False`, `options={"num_ctx": 16384, "temperature": 0.3}` — always set `num_ctx`; Ollama's default context for Gemma 4 is far smaller than the model supports.

**Tools (keep ≤ 8 for a small model; typed beats free-form SQL):**

| Tool | Args | Does |
|---|---|---|
| `get_report_overview` | — | Summary numbers + top 10 findings (compact) |
| `get_merchant` | `merchant` | Series row, flags, forecast quantiles, last 12 charges (fuzzy match via `difflib`) |
| `find_duplicate_charges` | `merchant?`, `window_days=3` | Duplicate pairs with dates/amounts |
| `spend_by_category` | `start_date?`, `end_date?` | Debit totals by category and month |
| `forecast_spend` | `days=30`, `exclude_merchants=[]` | **Live TabPFN** regressor run → q10/q50/q90 and the delta vs. baseline ("what if I cancel X and Y?") |
| `score_merchant` | `merchant` | **Live TabPFN** classifier with current user labels → prob, features, nearest archetypes |
| `run_readonly_sql` | `query` | Single SELECT/WITH on a read-only connection, 50-row cap, 2 s timeout |
| `set_renewal_reminder` | `merchant`, `days_before=3` | Creates or updates the merchant's reminder (§7.10). Inform-only: it schedules a reminder and nothing else. |

Email drafting is not a tool: the system prompt covers it, and the drawer's draft buttons (cancellation request, refund request, negotiation) send a canned prompt with the merchant's facts pre-fetched. Drafts are for the user to send; SlothSpend never sends anything.

**Context pre-fetch (small-model reliability):** before the first LLM call, fuzzy-match merchant names in the user message and inject their `get_merchant` facts as a system note. This dramatically improves grounding with a 4B-class model even when it skips a tool call.

**Loop:** up to 4 tool rounds; tool outputs truncated to ~4 k chars; last 12 messages of history; persisted in `chat_messages`.

```python
import json
import time
from typing import AsyncIterator

import ollama
import sentry_sdk

from . import db, tools
from .config import settings

MAX_TOOL_ROUNDS = 4

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
- Use the report currency. Keep answers brief and relaxed."""


def _attr(span, key, value) -> None:
    setter = getattr(span, "set_attribute", None) or span.set_data
    setter(key, value)


async def run_turn(conversation_id: str, user_text: str) -> AsyncIterator[dict]:
    client = ollama.AsyncClient(host=settings.ollama_host)
    messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n\n" + tools.overview_block()}]
    messages += db.load_chat(conversation_id, limit=12)
    facts = tools.prefetch_context(user_text)
    if facts:
        messages.append({"role": "system", "content": "Facts already looked up:\n" + facts})
    messages.append({"role": "user", "content": user_text})
    db.save_chat(conversation_id, "user", user_text)

    with sentry_sdk.start_span(op="gen_ai.invoke_agent", name="invoke_agent Ask Sloth") as agent_span:
        _attr(agent_span, "gen_ai.operation.name", "invoke_agent")
        _attr(agent_span, "gen_ai.agent.name", "Ask Sloth")
        _attr(agent_span, "gen_ai.conversation.id", conversation_id)

        for round_no in range(MAX_TOOL_ROUNDS + 1):
            content, calls = "", []
            with sentry_sdk.start_span(op="gen_ai.chat", name=f"chat {settings.chat_model}") as span:
                _attr(span, "gen_ai.operation.name", "chat")
                _attr(span, "gen_ai.provider.name", "ollama")
                _attr(span, "gen_ai.request.model", settings.chat_model)
                stream = await client.chat(
                    model=settings.chat_model,
                    messages=messages,
                    tools=tools.SCHEMAS if round_no < MAX_TOOL_ROUNDS else None,
                    stream=True,
                    think=False,
                    options={"num_ctx": 16384, "temperature": 0.3},
                )
                async for part in stream:
                    if part.message.content:
                        content += part.message.content
                        yield {"event": "token", "data": json.dumps({"text": part.message.content})}
                    if part.message.tool_calls:
                        calls.extend(part.message.tool_calls)
                    if part.done:
                        _attr(span, "gen_ai.usage.input_tokens", part.prompt_eval_count or 0)
                        _attr(span, "gen_ai.usage.output_tokens", part.eval_count or 0)

            if not calls:
                db.save_chat(conversation_id, "assistant", content)
                yield {"event": "done", "data": json.dumps({"rounds": round_no})}
                return

            messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": [{"function": {"name": c.function.name, "arguments": c.function.arguments}}
                               for c in calls],
            })
            for c in calls:
                name, args = c.function.name, dict(c.function.arguments or {})
                yield {"event": "tool_start", "data": json.dumps({"name": name, "args": args})}
                started = time.perf_counter()
                with sentry_sdk.start_span(op="gen_ai.execute_tool", name=f"execute_tool {name}") as tspan:
                    _attr(tspan, "gen_ai.operation.name", "execute_tool")
                    _attr(tspan, "gen_ai.tool.name", name)
                    output = await tools.execute(name, args)
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                db.save_chat(conversation_id, "tool", output, tool_name=name, tool_args=args)
                yield {"event": "tool_end", "data": json.dumps({"name": name, "ms": elapsed_ms,
                                                                 "preview": output[:300]})}
                messages.append({"role": "tool", "tool_name": name, "content": output})
```

Check the tool-message field name (`tool_name` vs. `name`) against the installed `ollama` client version.

Read-only SQL tool:

```python
import json
import re
import sqlite3
import time

from .db import DB_PATH


def run_readonly_sql(query: str) -> str:
    q = query.strip().rstrip(";")
    if ";" in q or not re.match(r"(?is)^\s*(select|with)\b", q):
        return json.dumps({"error": "Only a single SELECT or WITH statement is allowed."})
    conn = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = ON")
    deadline = time.monotonic() + 2.0
    conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    try:
        cur = conn.execute(f"SELECT * FROM ({q}) LIMIT 50")
        cols = [d[0] for d in cur.description]
        return json.dumps({"columns": cols, "rows": cur.fetchall()}, default=str)
    except sqlite3.Error as exc:
        return json.dumps({"error": str(exc)})
    finally:
        conn.close()
```

**Suggested prompts** (chips under the input):
- "Why was IronTrap flagged, and did they ever double-charge me?"
- "What will subscriptions cost next month if I cancel StreamFlix and WatchNest?"
- "Which category grew the most this year?"
- "Draft a refund request for the duplicate IronTrap charge."
- "Remind me three days before IronTrap renews."

### 7.10 Renewal reminders (inform only, no workflow engine)

SlothSpend never cancels anything and never touches a merchant's website. Reminders are the follow-through: nudge the user before a renewal, let them decide, and — after they cancel on their own — check the next statement to confirm the charge stopped.

There is no workflow engine. Reminders are rows in the `reminders` table (§7.2) plus one asyncio loop inside the engine that wakes every 30 seconds. That's enough: one process, a handful of rows, nothing external to coordinate, and SQLite already survives restarts.

```
WATCHING ──remind_at reached──► REMINDED ──"Keep it"──────────────────────► KEPT
   │                              │  ▲
   │                              │  └─ snooze 1–14 d (max 3 reminders) via SNOOZED
   │                              ├── renewal + 3 days, no answer ─────────► EXPIRED
   │ "I cancelled it" (any time)  │ "I cancelled it"
   └────────────────────────────► AWAITING_STATEMENT
                                    │ newer statement imported
                                    ├── charged again ─────────────────────► STILL_CHARGED (+ refund draft)
                                    ├── covers renewal, no charge ─────────► VERIFIED_STOPPED
                                    └── 60 days, no statement ─────────────► EXPIRED
any active phase ── "Stop" ──► STOPPED      (demo: every wait compresses to N seconds)
```

**Rules**
- `remind_at` always holds the time of the row's next scheduled event (a nudge or an expiry deadline); `NULL` means nothing is pending. Store every timestamp as UTC ISO-8601 so string comparison orders correctly.
- Every transition is compare-and-set on the current phase (`UPDATE reminders SET … WHERE series_id = ? AND phase = ?`), so a button click and a scheduler tick can't overwrite each other.
- **Reminders fire while the app is running.** Rows persist, so anything that came due while SlothSpend was closed fires on the first tick after launch (catch-up). "Open at login" (stretch) keeps them on time. Say this plainly in the UI.
- Delivery is at-least-once: if the app dies between drafting a note and saving the new phase, the next launch sends it again.

**User actions** (API in §8)

| Action | Allowed from | New phase | `remind_at` |
|---|---|---|---|
| Remind me (N days before) | no reminder, or an ended phase | `WATCHING` | renewal − N days (demo: now + N s) |
| Snooze d days | `REMINDED` with fewer than 3 sent | `SNOOZED` | now + d days |
| Keep it | `WATCHING`, `REMINDED`, `SNOOZED` | `KEPT` | `NULL` |
| I cancelled it (date) | any phase, or no reminder yet (row is created) | `AWAITING_STATEMENT` | now + 60 days (expiry) |
| Stop | any active phase | `STOPPED` | `NULL` |

`app/reminders.py`

```python
import asyncio
import logging
from datetime import date, datetime, time, timedelta, timezone

from . import db
from .notes import gemma_note, template_note

log = logging.getLogger(__name__)

TICK_SECONDS = 30
MAX_REMINDERS = 3
GEMMA_BACKOFF = [5, 10, 20]  # seconds between attempts, then fall back to a template


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def renewal_at(next_due_iso: str) -> datetime:
    return datetime.combine(date.fromisoformat(next_due_iso), time(9, 0), tzinfo=timezone.utc)


async def draft(kind: str, facts: dict) -> dict:
    """Local Gemma 4 with retries; falls back to a template so a reminder never fails."""
    for delay in GEMMA_BACKOFF:
        try:
            return await gemma_note(kind, facts)
        except Exception:
            log.warning("Gemma unavailable for %s note; retrying in %ss", kind, delay)
            await asyncio.sleep(delay)
    return template_note(kind, facts)


async def send(row: dict, kind: str) -> None:
    facts = await asyncio.to_thread(db.series_facts, row["series_id"])
    note = await draft(kind, facts)
    await asyncio.to_thread(db.insert_notification, row["series_id"], kind, note["title"], note["body"])


async def tick() -> None:
    demo = await asyncio.to_thread(db.get_setting_int, "demo_compress_seconds")
    for row in await asyncio.to_thread(db.due_reminders, now_utc().isoformat()):
        sid, phase = row["series_id"], row["phase"]
        if phase in ("WATCHING", "SNOOZED"):
            await send(row, "reminder")
            if demo:
                answer_by = now_utc() + timedelta(seconds=demo)
            else:  # wait for an answer until renewal + 3 days, but always at least a day
                answer_by = max(renewal_at(row["next_due_date"]) + timedelta(days=3), now_utc() + timedelta(days=1))
            await asyncio.to_thread(
                db.transition, sid, phase, "REMINDED",
                remind_at=answer_by.isoformat(),
                reminders_sent=row["reminders_sent"] + 1,
                detail=f"Renews {row['next_due_date']}. Keep it, or cancel it yourself?",
            )
        elif phase == "REMINDED":
            await asyncio.to_thread(db.transition, sid, phase, "EXPIRED", remind_at=None,
                                    detail="The renewal passed without an answer. Set a new reminder any time.")
        elif phase == "AWAITING_STATEMENT":
            await asyncio.to_thread(db.transition, sid, phase, "EXPIRED", remind_at=None,
                                    detail="No newer statement arrived within 60 days.")


async def verify_after_import() -> None:
    """Called at the end of every import (§7.8)."""
    for row in await asyncio.to_thread(db.reminders_in_phase, "AWAITING_STATEMENT"):
        sid = row["series_id"]
        check = await asyncio.to_thread(db.charges_after, sid, row["cancelled_on"])
        if check["charges_after"]:
            kind, phase = "still_charged", "STILL_CHARGED"
            detail = f"Charged again on {check['charges_after'][0]['date']}"
        elif check["covers_until"] and check["covers_until"] >= row["next_due_date"]:
            kind, phase = "verified", "VERIFIED_STOPPED"
            detail = f"No charge through {check['covers_until']}"
        else:
            await asyncio.to_thread(
                db.transition, sid, "AWAITING_STATEMENT", "AWAITING_STATEMENT",
                detail=f"That statement ends {check['covers_until']}, before the renewal. Import a later one.",
            )
            continue
        await send(row, kind)
        await asyncio.to_thread(db.transition, sid, "AWAITING_STATEMENT", phase, remind_at=None, detail=detail)


async def run_scheduler() -> None:
    while True:
        try:
            await tick()
        except Exception:  # one bad row must never stop reminders
            log.exception("reminder tick failed")
        await asyncio.sleep(TICK_SECONDS)
```

`db` helpers: `due_reminders(now_iso)` returns rows with `remind_at <= now` in an active phase; `transition(series_id, expect, new_phase, **fields)` is the compare-and-set update (fields not passed stay unchanged; returns `False` if the phase moved on); `charges_after(series_id, after_iso)` returns `{"covers_until": <latest stored tx date>, "charges_after": [{"date", "amount"}, …]}`.

`app/notes.py` — `gemma_note(kind, facts)` asks local Gemma 4 for `{"title", "body"}` via structured output (`temperature 0.4`, `think=False`). Facts (merchant, amount, renewal date, price change, duplicates, monthly saving) are formatted in code; the prompt allows only those numbers and forbids links, phone numbers and merchant-specific instructions. Bodies are ≤ 3 sentences and end by pointing to the in-app **How to cancel** checklist. `template_note(kind, facts)` returns the same shape without an LLM, e.g. *"IronTrap Fitness renews Nov 5 for $49.99. If you no longer use it, open How to cancel in SlothSpend — or tap Keep it."*

**Demo moments**
1. **Remind me** on IronTrap with 30 s demo compression → quit SlothSpend while it's `WATCHING` → relaunch → the notification arrives on the first tick.
2. Quit Ollama before the reminder fires → the engine log shows the retries → the reminder still arrives with the template text.
3. **I cancelled it** → load `followup_cancelled.csv` → `VERIFIED_STOPPED`: *"No IronTrap charge on your Nov 5 statement — you're saving $49.99 a month."*
4. Load `followup_still_charged.csv` instead → `STILL_CHARGED` with a refund-request draft.

### 7.11 Telemetry (`app/telemetry.py`, stretch, opt-in)

```python
import os

import sentry_sdk

SENTRY_DSN = "https://<public-key>@o0.ingest.sentry.io/<project>"  # a DSN is safe to ship


def init() -> None:
    if os.environ.get("SLOTH_TELEMETRY") != "1":
        return  # spans become no-ops
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=1.0,
        send_default_pii=False,  # never send prompts, responses or CSV content
        release=os.environ.get("SLOTH_VERSION", "dev"),
    )
```

Spans: `invoke_agent Ask Sloth` → `chat gemma4:e4b` (input/output tokens from Ollama's `prompt_eval_count` / `eval_count`) → `execute_tool {name}`; plus custom spans `tabpfn.fit`, `tabpfn.predict` (rows, model, device), `normalize.batch`, and `reminders.send`. For the write-up: latency per span, tokens per turn, **$0 cost**, and one debugging story (e.g., a tool call that failed until `num_ctx` was raised).

---

## 8. HTTP API contract

All routes require `X-Sloth-Token`. SSE uses `text/event-stream` with named events. Nothing in this API acts outside the computer.

| Method & path | Purpose | Request | Response |
|---|---|---|---|
| `GET /health` | Boot checklist | — | `{engine, ollama:{status, version, model, model_present}, tabpfn:{status, model, error}, telemetry}` |
| `POST /setup/ollama/pull` | Pull `gemma4:e4b` with progress | `{model}` | SSE `progress {status, completed, total}` → `done` |
| `POST /import` | Upload a CSV (first or newer statement) | multipart `file` | `{import_id, needs_mapping, mapping, preview[10], currency, dayfirst}` |
| `POST /import/{id}/confirm` | Run the pipeline, then verify reminders awaiting a statement | `{mapping?, debits_positive?, currency?}` | SSE `stage {stage, done, total}` → `done {report}` |
| `POST /demo/load-sample` | Import a bundled CSV | `{file: "main" \| "followup_cancelled" \| "followup_still_charged"}` | same SSE as confirm |
| `GET /report` | Summary + findings | — | `{meta, series[]}` |
| `GET /series/{id}` | Drawer detail | — | `{series, transactions[], quantiles[], similar[], reminder?}` |
| `POST /series/{id}/label` | Correction | `{label: "subscription" \| "not_subscription" \| "keep"}` | `{report}` (re-scored) |
| `POST /series/{id}/draft` | Draft an email the user sends themselves | `{kind: "cancel_request" \| "refund" \| "negotiate"}` | SSE `token` → `done` |
| `PATCH /merchant-map/{desc_key}` | Rename / recategorise | `{merchant, category}` | `{ok}` |
| `POST /chat` | Ask Sloth turn | `{conversation_id, message}` | SSE `token`, `tool_start`, `tool_end`, `done`, `error` |
| `GET /chat/{conversation_id}` | History | — | `{messages[]}` |
| `POST /reminders` | Create or reset a reminder | `{series_id, days_before?}` | `{series_id, phase, remind_at}`; 400 if there's no predictable renewal date |
| `GET /reminders` | List | — | `[{series_id, merchant, next_due_date, phase, detail, remind_at, reminders_sent}]` |
| `POST /reminders/{series_id}/keep` · `/cancelled` · `/snooze` · `/stop` | User decisions (§7.10 table) | `/cancelled {cancelled_on}` (creates the row if needed), `/snooze {days}` | `{phase}`; 409 if the current phase doesn't allow it |
| `GET /notifications?since_id=` | New notifications (renderer polls every 5 s) | — | `[{id, series_id, kind, title, body, created_at}]` |
| `POST /notifications/{id}/read` | Mark read | — | `{ok}` |
| `GET /settings` · `PUT /settings` | Currency, model, reminder default, demo compression | `{currency, chat_model, days_before, demo_compress_seconds}` | `{...}` |
| `DELETE /data` | Wipe all local data, including reminders | — | `{ok}` |
| `POST /shutdown` | Graceful exit | — | `{ok}` |

---

## 9. Renderer UI

### 9.1 Look and feel

Calm and slow, on purpose. Dark slate base (`#0F172A`), moss-green accent (`#7BAE7F`), sand neutrals, one original line-art sloth mascot (no third-party characters). Motion is gentle (300–500 ms ease-out). Font: Inter or DM Sans. Every number shows its currency; every model output shows its source chip (`TabPFN-3.5`, `Gemma 4 · local`, `heuristic`).

### 9.2 Screens

**Boot** — checklist with live status and a fix per row:
- Engine (spinner; an error shows the last 20 log lines and "Restart engine").
- Gemma: Ollama unreachable → "Install Ollama" (opens ollama.com) + "Retry". Version < 0.20 → "Update Ollama". Model missing → "Download Gemma 4 (≈ 5 GB)" with a progress bar; e2b offered for low-RAM machines.
- TabPFN: `missing_weights` → "Paste your free Prior Labs key (non-commercial license)" + link to platform.priorlabs.ai; `warming` → spinner; `error` → message.
- "Continue in limited mode" whenever the Engine is ready.

**Top bar** — logo, status pills (Engine, Gemma, TabPFN), a notification bell with unread count, Settings. The renderer polls `/notifications` every 5 s, raises an OS notification (HTML5 `Notification`) for each new one, and clicking it opens the Reminders tab.

**Workspace** — split pane (≈ 62 / 38).

*Left — Audit tab*
1. **Import bar / empty state:** drop zone, "Load sample statement", a small "Demo data" menu for the follow-up statements, and the line *"Your statement never leaves this computer."*
2. **ColumnMapper** (only when needed): preview table with dropdowns for Date / Description / Amount or Debit+Credit, a "debits are positive" toggle, and currency.
3. **Pipeline progress:** stages with counts ("Gemma cleaned 41 / 62 merchants").
4. **Summary cards:** Monthly recurring · Next 30 days (q50 with q10–q90) · Potential monthly savings · Flags.
5. **Burn chart:** monthly recurring spend (bars, last 12 months) + next-month forecast (point + band).
6. **Findings table** (sorted by priority): Merchant + category chip · Cadence · Last charge · Change (creep) · Recurring score bar · Flags · Next due · Actions: `Keep`, `Not a subscription`, `Remind me`, `How to cancel` (cancellable categories) or `Draft negotiation email` (bills), `Ask Sloth`.
7. **Merchant drawer:** charge timeline sparkline, plain-language reasons ("Billed every ~30 days, ±1 day; same amount 11 of 12 times"), nearest archetypes, forecast range, flag details, editable merchant/category, and the **How to cancel** section.

**How to cancel** (static copy plus one local draft; SlothSpend does none of these steps itself):
1. Find the merchant's receipt or welcome email — it usually links to "Manage subscription".
2. Sign in on the merchant's website or app → Account / Billing / Membership.
3. Billed through Apple or Google? Cancel from the App Store or Play Store subscriptions page instead.
4. No self-serve option? Send the cancellation request below — Gemma drafts it on this computer from your own charge history.
5. Keep the confirmation, then click **I cancelled it** so SlothSpend can check your next statement.

Buttons: **Draft cancellation request** · **Copy** · **I cancelled it** (date picker; defaults to today — with the bundled sample, the demo default is the day after its last transaction) · **Remind me before renewal**. Footer: *"SlothSpend never cancels or contacts anyone for you."*

*Left — Reminders tab:* one card per reminder — merchant, amount, renewal date, days left — with a stepper (Watching → Reminded → Kept / You cancelled → Verified / Still charged). Buttons by phase: **Keep it** · **I cancelled it** · **Snooze 1 d / 3 d** · **Stop**. A `STILL_CHARGED` card adds **Draft refund request**. A banner explains: *"Reminders fire while SlothSpend is open. If it was closed, you'll get them the next time you open it."*

*Right — Ask Sloth:* streaming markdown messages, collapsible tool badges (`get_merchant("IronTrap") · 42 ms`), suggested-prompt chips, copy buttons on drafts. A `set_renewal_reminder` result renders as a "Reminder set for Nov 2" chip linking to the Reminders tab. "Ask Sloth" on a finding pre-fills the input.

**Settings** (modal): chat model (e4b / e2b) · currency · Prior Labs key · reminders: days before renewal (default 3), demo: compress reminder waits to N s · open at login (stretch) · telemetry toggle (default off) · the data-egress table · "Delete all local data".

---

## 10. slothspend.tech (landing page)

A single static page from `site/index.html` on any static host (Netlify, Cloudflare Pages, GitHub Pages). Claim the free .tech domain via the Hacktoberfest promos page.

- Hero + 60-second video, and how it works: **audit → ask → remind → verify**.
- The **"Inform, never act"** principle and the privacy/egress table.
- Download buttons (GitHub Release assets) and first-run notes: install Ollama, paste a free Prior Labs key, Gatekeeper/SmartScreen steps.
- A link to the DEV post.

---

## 11. Sample data and priors

### 11.1 `scripts/make_sample_data.py` → `sample_bank_12m.csv`

Seeded RNG, ~400 rows, Nov 2025 → mid-Oct 2026, columns `Date,Description,Amount` (debits negative), messy descriptions, fictional merchants only.

| Merchant | Pattern | Expected outcome |
|---|---|---|
| IronTrap Fitness | Monthly ~5th, 39.99 → 49.99 from Jul 2026; extra charge Jul 6 | recurring, **price_creep +25 %**, **duplicate Jul 5/6**, zombie suspect |
| StreamFlix UHD | Monthly ~12th, 15.49 | recurring, **overlap** |
| WatchNest | Monthly ~20th, 9.99 | recurring, **overlap** |
| TuneTide | Monthly, 10.99 → 11.99 from Mar | recurring, price_creep +9.1 % |
| CloudBox Pro | Single annual charge 119.88 in Jan | **possible_annual** |
| Metro Electric | Monthly bill 60–140 | recurring bill, no creep flag, negotiation email |
| Rent transfer | Monthly 1,800 | recurring bill (Housing) |
| FreshCart | Most Saturdays, 40–140 | **not recurring** (hard negative) |
| BeanThere Coffee | Frequent, 3–9 | not recurring |
| Misc. dining, rides, shopping; monthly salary credit | irregular | ignored / credits |

Two follow-up statements for the reminder demo (same columns, Oct 16 – Nov 15, 2026, covering IronTrap's Nov 5 renewal):
- `followup_cancelled.csv` — no IronTrap charge → `VERIFIED_STOPPED`.
- `followup_still_charged.csv` — IronTrap charged 49.99 on Nov 5 → `STILL_CHARGED`.

Both are reachable from the Import bar's "Demo data" menu.

Also generate `tests/fixtures/` with an HDFC-style export (preamble lines, `Narration`, `Withdrawal Amt.`, `Deposit Amt.`, dd/mm/yy) and a signed-amount US export.

### 11.2 `scripts/make_priors.py` → `priors_recurring.csv`, `priors_hikes.csv`

Simulate **transaction histories** per archetype (≈ 40 series each), then run the **same** `series_features()` used at runtime — no train/serve skew.

- Positives (label 1): monthly fixed streaming/software (±1–2 day jitter, weekend shifts), monthly with a hike, weekly meal kit, quarterly, annual (2 charges), usage-based SaaS (variable monthly), phone plan, insurance premium, utility bill, rent.
- Negatives (label 0): weekly-ish groceries with variable amounts, coffee, dining, fuel, rides, marketplace shopping, one-off travel.
- Category/`subscription_like` come from the archetype (mirroring what Gemma would output), with 10 % noise so TabPFN can't rely on the hint alone.
- `priors_hikes.csv`: for subscription archetypes, a 35 %/year chance of a +5–25 % step; emit per-charge regression rows with `ratio`.

Commit both CSVs (CSV avoids bundling pyarrow).

---

## 12. Packaging and release

### 12.1 PyInstaller (`engine/slothspend_engine.spec`)

```python
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas, binaries, hiddenimports = [], [], []
for pkg in ["tabpfn", "sentry_sdk", "ollama", "sse_starlette"]:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

datas += [
    ("app/data/priors_recurring.csv", "app/data"),
    ("app/data/priors_hikes.csv", "app/data"),
    ("app/data/sample_bank_12m.csv", "app/data"),
    ("app/data/followup_cancelled.csv", "app/data"),
    ("app/data/followup_still_charged.csv", "app/data"),
]
hiddenimports += collect_submodules("uvicorn") + collect_submodules("app")

a = Analysis(
    ["run_engine.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="slothspend-engine",
    console=True,   # windowless mode leaves sys.stdout/stderr = None and breaks uvicorn; main spawns with windowsHide
    upx=False,      # UPX breaks torch DLLs and triggers antivirus false positives
)
coll = COLLECT(exe, a.binaries, a.datas, upx=False, name="slothspend-engine")
```

Output: `engine/dist/slothspend-engine/{slothspend-engine[.exe], _internal/}`. Expect a large bundle (PyTorch); keep torch **CPU-only on Windows**.

### 12.2 `electron-builder.yml`

```yaml
appId: tech.slothspend.desktop
productName: SlothSpend
directories:
  output: release
  buildResources: build
files:
  - out/**
  - package.json
extraResources:
  - from: engine/dist/slothspend-engine
    to: engine
mac:
  category: public.app-category.finance
  identity: null             # unsigned hackathon build (see 12.5)
  target:
    - target: dmg
      arch: [arm64]
win:
  target:
    - target: nsis
      arch: [x64]
nsis:
  oneClick: false
  allowToChangeInstallationDirectory: true
  createDesktopShortcut: true
publish: null
```

### 12.3 CI (`.github/workflows/release.yml`)

PyInstaller only builds for the host OS/arch, so each target needs its own runner. macOS x64 is cut (a `macos-13` job can add it later).

```yaml
name: release
on:
  push:
    tags: ["v*"]
  workflow_dispatch:

jobs:
  build:
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: macos-14
            platform: mac
          - os: windows-latest
            platform: win
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - name: CPU-only PyTorch (Windows)
        if: matrix.platform == 'win'
        run: pip install torch --index-url https://download.pytorch.org/whl/cpu
      - name: Build engine
        working-directory: engine
        run: |
          pip install -r requirements.txt pyinstaller
          pyinstaller slothspend_engine.spec --noconfirm --clean
      - name: Smoke-test engine binary
        run: python engine/scripts/smoke_test.py
      - name: Build and package app
        run: |
          npm ci
          npm run build
          npx electron-builder --${{ matrix.platform }} --publish never
      - uses: actions/upload-artifact@v4
        with:
          name: SlothSpend-${{ matrix.platform }}
          path: |
            release/*.dmg
            release/*.exe

  release:
    needs: build
    if: startsWith(github.ref, 'refs/tags/')
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          path: dist
      - uses: softprops/action-gh-release@v2
        with:
          files: dist/**/*
```

`engine/scripts/smoke_test.py` launches the built binary with a temp data dir, `SLOTH_TOKEN=test`, `SLOTH_NO_WATCHDOG=1`, polls `/health` until `engine == "ok"` (90 s), then `POST /shutdown`. Non-zero exit fails the job.

### 12.4 First-run model setup

- **Gemma:** not bundled. Boot screen checks Ollama (`/api/version`, `/api/tags`) and pulls `gemma4:e4b` with streamed progress.
- **TabPFN-3.5:** weights are license-gated (non-commercial) and require a Prior Labs account + API key. Not bundled (license + size). User pastes the key once → stored with safeStorage → passed as `TABPFN_TOKEN` → engine downloads into `<userData>/tabpfn-weights` (`TABPFN_MODEL_CACHE_DIR`). After that it works offline. Without a key the app runs in heuristic mode and says so.
- This is a one-time *model license* step, not an app login — say so in the README and write-up.

### 12.5 Unsigned builds

- macOS: Gatekeeper will block or call the app "damaged". README: drag to Applications, then `xattr -cr /Applications/SlothSpend.app`, or right-click → Open. Signing/notarisation is out of scope.
- Windows: SmartScreen → "More info" → "Run anyway". Disabling UPX reduces antivirus false positives.

---

## 13. Testing and Definition of Done

### 13.1 Automated (pytest)

- `test_ingest.py` — 3 fixtures (sample, HDFC-style, signed US): header row, mapping, dayfirst, sign, row counts; a newer statement appends only later rows.
- `test_features.py` — cadence detection for weekly/monthly/annual/irregular; duplicates excluded.
- `test_detectors.py` — IronTrap creep (+25 %, since Jul) and duplicate (Jul 5/6); TuneTide creep; Metro Electric **not** flagged for creep; FreshCart not recurring (heuristic scorer, so tests run without weights).
- `test_reminders.py` — temp SQLite, `reminders.now_utc` monkeypatched to a controllable clock, `GEMMA_BACKOFF = [0, 0, 0]`, `gemma_note` mocked; call `tick()` / `verify_after_import()` directly:
  - nothing is sent before `remind_at`; at `remind_at` → one notification, `REMINDED`
  - Keep → `KEPT`; a Keep that lands mid-tick isn't overwritten (compare-and-set)
  - no answer → `EXPIRED` after renewal + 3 days
  - snooze 2 days → `SNOOZED` → a second reminder 2 days later; a fourth snooze is rejected (409)
  - I cancelled it + `verify_after_import()`: no later charge and coverage past the renewal → `VERIFIED_STOPPED`; a later charge → `STILL_CHARGED`; coverage ending before the renewal → stays `AWAITING_STATEMENT`
  - Gemma failing every attempt → the template note is sent
  - catch-up: an overdue row in an existing database fires on the first tick of a fresh scheduler
- `test_egress.py` — run the pipeline, every chat tool and a full reminder cycle with `socket.socket.connect` patched to reject non-loopback addresses (telemetry off, weights cached). Any outbound attempt fails the test.

### 13.2 Definition of Done (manual, on a clean Apple Silicon Mac and a clean Windows x64 machine/VM)

1. Install from the CI artifact; launch; Engine green ≤ 20 s; Gemma + TabPFN green once set up.
2. "Load sample statement" → report ≤ 60 s (Mac) / ≤ 120 s (Windows CPU) with the expected outcomes in §11.1.
3. "Not a subscription" on any row → re-scored ≤ 5 s; persists after restart.
4. Each suggested prompt gets a grounded answer with ≥ 1 visible tool call; the what-if uses `forecast_spend`. "Cancel IronTrap for me" gets a plain explanation that SlothSpend doesn't cancel, plus a reminder offer and a cancellation-request draft — with no invented links or phone numbers.
5. Reminders: **Remind me** on IronTrap with 30 s demo compression → quit while it's `WATCHING` → relaunch → the OS notification arrives. With Ollama stopped, the reminder still arrives with the template text.
6. **I cancelled it** → load `followup_cancelled.csv` → "Verified" notification. After "Delete all local data", repeat with `followup_still_charged.csv` → "Still charged" + refund-request draft.
7. **Offline test:** Wi-Fi off, telemetry off → steps 2–6 still work.
8. Quit → no `slothspend-engine` process remains (Activity Monitor / Task Manager). Force-kill Electron → the engine exits within seconds (stdin EOF) and the next launch boots normally.

---

## 14. Two-day build plan

Rule: **package first.** The most likely way to miss the deadline is a PyInstaller/torch packaging surprise found on Day 2 evening.

### Day 1 — foundation and audit

| Time | Work | Checkpoint |
|---|---|---|
| 0:00–1:30 | Scaffold electron-vite react-ts; engine with `/health`, token, watchdog; main spawns the engine on a dynamic port; Boot screen | Dev app boots green |
| 1:30–3:00 | Walking-skeleton packaging: spec imports tabpfn/torch (unused), electron-builder config, CI matrix | **A:** both CI installers launch to green on real machines |
| 3:00–4:30 | `make_sample_data.py` (incl. follow-up CSVs), `make_priors.py`, DB schema, `ingest.py` + tests | Sample + fixtures parse |
| 4:30–6:00 | Normalisation (pre-clean, cache, Gemma schema batches, fallback); Ollama health + pull | Merchants clean |
| 6:00–8:30 | Features, TabPFN classifier/regressor, heuristic fallback, detectors, report pipeline | **B:** `/demo/load-sample` returns §11.1 outcomes |
| 8:30–11:00 | Audit UI: import, mapper, progress, cards, chart, table, drawer, labels | **C:** end-to-end audit in dev |

### Day 2 — agent, reminders, ship

| Time | Work | Checkpoint |
|---|---|---|
| 0:00–3:00 | Ask Sloth: tools, pre-fetch, loop, SSE, chat UI, email drafts, persistence | Suggested prompts pass |
| 3:00–4:30 | Reminders: table + scheduler loop, `notes.py` with template fallback, reminder and notification endpoints, Reminders tab, bell + OS notifications, How to cancel section | **D:** remind → snooze → I cancelled it → follow-up import verifies; survives a restart |
| 4:30–7:00 | Hardening: CI release build, first-run flows, clean-machine tests, orphan check, egress test; tag `v0.1.0` | **E:** DoD 1–8 pass |
| 7:00–9:00 | Stretch in order: Sentry spans → open at login → landing polish → trial detector | — |
| 9:00–11:00 | Buffer | — |

Dropping browser automation and Temporal frees about 1.5 hours on Day 2 and removes a whole bundled binary; the time went to hardening and buffer.

**Cut lines.** If A slips past Day 1 midday, ship macOS first and treat Windows as best effort. If D slips, drop snooze and follow-up verification; keep the reminder itself. Never cut the offline test.

### Days 3–5 (before Oct 25) — the write-up (weighted most)

Record the demo, narrate with ElevenLabs, capture screenshots (and Sentry traces if the stretch landed), write the DEV post, link Entire sessions, publish the landing page, final README.

---

## 15. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| PyInstaller + torch bundle fails on one OS | High | High | Checkpoint A on Day 1; CPU torch on Windows; UPX off; smoke test in CI |
| TabPFN weights unavailable (license/key) or slow on CPU | Medium | Medium | First-run key flow; Fast variant on CPU; heuristic mode |
| Gemma 4 E4B skips or garbles tool calls | Medium | Medium | ≤ 8 typed tools, context pre-fetch, round cap, low temperature |
| Gemma invents cancellation links, phone numbers or steps | Medium | Medium | Prompt rule, no links allowed in the note schema, static generic checklist, DoD 4 check |
| Ollama context default truncates history | High | Medium | Always pass `num_ctx` |
| Reminders only fire while the app is running | High | Low | Catch-up on next launch, open-at-login stretch, said plainly in the UI |
| Gatekeeper / SmartScreen scares judges | High | Low | README steps; video shows the app running |
| Port conflicts or an orphaned engine | Low | Medium | Dynamic port, stdin watchdog, graceful shutdown |
| Over-scoping across categories | High | High | One-prize rule → depth on TabPFN and Gemma; no technology added for a badge |

---

## 16. Write-up and demo plan

**DEV post outline**
1. Hook: "My bank statement is a sloth's nightmare. So I hired a sloth."
2. 60-second video (ElevenLabs narration) — import → findings → Ask Sloth → Remind me → quit and relaunch → reminder notification → How to cancel → I cancelled it → newer statement → "Verified".
3. **Why open innovation matters:** after the one-time model downloads, zero network calls; the Wi-Fi-off test; $0 per audit; swap Gemma sizes; TabPFN corrections without retraining.
4. **TabPFN-3.5 inside a prediction agent:** in-context learning from corrections, quantile forecasts with honest bands, live what-if tools.
5. **Gemma 4 locally, three jobs:** the merchant normaliser that feeds TabPFN, the tool-calling agent, and the reminder/email drafter.
6. **Slow and steady, without extra machinery:** reminders that wait weeks, retry when the local model is busy, fall back to a template, catch up after the app was closed, and verify on the next statement — all from one SQLite table.
7. **Why it doesn't cancel for you:** your accounts, your call — no credentials, no bots on dark-pattern sites, nothing done in your name. The agent informs; you act.
8. If the Sentry stretch landed: agent traces (latency, tokens, $0) and one debugging story.
9. Honest limitations: no usage data (hence "zombie suspect"), reminders need the app running, unsigned builds, non-commercial TabPFN weights.
10. How it was built: Entire session links; GitHub Actions release pipeline.
11. Prize categories entered.

---

## Appendix A — Review of the v0 design

Severity: 🔴 breaks the demo or the build · 🟠 hurts correctness or judging · 🟡 polish.

| # | Sev | Area | v0 issue | v1 fix |
|---|---|---|---|---|
| 1 | 🔴 | Gemma | `gemma3` has no tool calling in Ollama; `chat(..., tools=…)` errors | `gemma4:e4b`, Ollama ≥ 0.20 (§7.9) |
| 2 | 🔴 | Browserbase | Cloud browser can't reach `127.0.0.1:8765/mock-portal` | **Removed** — v1 has no browser automation; SlothSpend never cancels |
| 3 | 🔴 | Stagehand | v2 API (`Stagehand(env=…)`, `stagehand.page.act`), pinned `0.3.5`; no `MODEL_API_KEY` | **Removed** with browser automation |
| 4 | 🔴 | TabPFN | Weights are license-gated; CI "pre-cache" neither authenticates nor bundles weights (they land in a user cache) | First-run key + `TABPFN_MODEL_CACHE_DIR`; heuristic fallback (§12.4) |
| 5 | 🔴 | Electron | Markdown link artefacts in code: `"[http://127.0.0.1](http://127.0.0.1):…"` in the health check (and `portal_url`) — health never passes | Plain URLs; config via IPC (§6) |
| 6 | 🔴 | Packaging | macOS x64 DMG built on an arm64 runner ships an arm64-only sidecar | arm64 only; separate runner for x64 later (§12.3) |
| 7 | 🔴 | CI | Temporal binary never downloaded (`temporal_arch` unused) | **Removed** — v1 doesn't use Temporal |
| 8 | 🔴 | PyInstaller | `console=False` → `sys.stdout/stderr` are `None` on Windows → uvicorn logging crash | `console=True` + `windowsHide`, `log_config=None` (§12.1) |
| 9 | 🔴 | Startup | 20 s health timeout while TabPFN/torch load at startup; rejection leaves a blank window | Window first, Boot screen, background warm-up (§6.1) |
| 10 | 🔴 | Temporal | `wait_condition(timeout=…)` raises on expiry (unhandled); activity imports in the workflow module fight the sandbox | **Removed** — v1 doesn't use Temporal |
| 11 | 🟠 | Modelling | "zombie_prob" is really P(recurring) | `recurring_prob` + zombie-suspect review flag (§7.7) |
| 12 | 🟠 | Modelling | Priors sampled in feature space from the decision rule's own distributions; features computed differently at runtime | Simulate histories, reuse `series_features` (§11.2) |
| 13 | 🟠 | Modelling | Regressor target `1 + 0.25·delta`, then `max(pred, latest)` — forecast is meaningless | Next-charge ratio regression with quantiles (§7.6) |
| 14 | 🟠 | Detectors | Creep compares latest to the mean of all prior charges; misfires on variable bills | Price-run baseline + stability check (§7.7) |
| 15 | 🟠 | Detectors | Duplicate charge (demo hero) not implemented; relies on the LLM writing SQL | Deterministic detector (§7.7) |
| 16 | 🟠 | Gemma | One prompt for all descriptions; keys can be altered; `format="json"`; no cache; fallback hard-codes demo merchants | Pre-clean, dedupe, schema batches keyed by index, cache, generic fallback (§7.4) |
| 17 | 🟠 | Ingest | No CSV parsing/column mapping at all | §7.3 |
| 18 | 🟠 | Chat | SQL tool guard is `startswith("SELECT")` on a writable connection | Read-only URI, `query_only`, limit, timeout, typed tools (§7.9) |
| 19 | 🟠 | TabPFN prize | `inspect_tabpfn_merchant` reads cached rows; TabPFN never runs inside the agent | Live `forecast_spend` / `score_merchant` tools (§7.9) |
| 20 | 🟠 | Chat | One tool round, no streaming, no persistence (`chat_messages` never created), default context | Loop, SSE, table, `num_ctx` (§7.9) |
| 21 | 🟠 | Security | Unauthenticated localhost API on a fixed port exposes the financial report to any local process or web page | Dynamic ports + per-launch token (§3.2) |
| 22 | 🟠 | Privacy | "100 % offline" contradicted by ElevenLabs summaries, Sentry, Browserbase/Stagehand | No browser automation, opt-in Sentry, narration-only ElevenLabs; zero network calls after setup (§3.3) |
| 23 | 🟠 | Secrets | No place for keys; risk of baking keys into the installer | safeStorage + env at spawn (§6.3) |
| 24 | 🟠 | Temporal | Workflow only gated an automated cancellation; no retry policy, idempotency or state sync; "wait for billing cycle" missing | **Removed** — SQLite-backed reminders with Gemma retries, template fallback and statement verification instead (§7.10) |
| 25 | 🟠 | Temporal prize | `--headless` hides the Temporal Web UI — the best visual proof for judges | **Removed** — v1 doesn't use Temporal |
| 26 | 🟠 | Setup | Ollama not bundled, so "zero setup" isn't true | Guided detect + pull on the Boot screen (§9.2) |
| 27 | 🟠 | Lifecycle | SIGTERM only on `before-quit`; a crash orphans the sidecars | One sidecar that exits on stdin EOF + graceful shutdown (§6.2) |
| 28 | 🟠 | Strategy | Nine categories targeted, but one submission can win only once; Browserbase/Auth0 not on the hub list | Focus on Overall/TabPFN/Gemma (§1) |
| 29 | 🟡 | Packaging | `upx=True` | Off (§12.1) |
| 30 | 🟡 | Scope | Mock portal duplicated (React component + FastAPI route) | **Removed** with browser automation |
| 31 | 🟡 | Scope | SHAP mentioned, not built; slow for TabPFN | Plain-language reasons + nearest archetypes (§7.6) |
| 32 | 🟡 | Locale | Currency hard-coded `$`; Indian bank layouts unsupported | Currency detection + HDFC-style fixture (§7.3) |
| 33 | 🟡 | TabPFN | `device="auto"` constructors, no version selection | `create_default_for_version(V3_5 / V3_5_FAST)` (§7.6) |
| 34 | 🟡 | Deps | Stale pins (`ollama 0.4.4`, `stagehand 0.3.5`, `tabpfn>=2.0.0`) | Lock after first green build (§5) |
| 35 | 🟡 | Builder | Per-platform `extraResources` blocks | Not needed: only the engine is bundled (§12.2) |
| 36 | 🟡 | Determinism | Implicit "now" in features | `report_date` = latest transaction (§7.3) |
| 37 | 🟡 | Coverage | Series need ≥ 2 charges, so annual plans vanish | `possible_annual` rule (§7.7) |
| 38 | 🟡 | Rules | Repo must be created within Oct 19–25 | Start the repo now; note post-deadline commits in README |

---

## Appendix B — Environment variables

| Variable | Set by | Used for |
|---|---|---|
| `SLOTH_PORT`, `SLOTH_TOKEN`, `SLOTH_DATA_DIR` | main | engine bind, auth, data folder |
| `TABPFN_MODEL_CACHE_DIR` | main | TabPFN weight cache |
| `TABPFN_TOKEN` | main (from the Prior Labs key) | first-run weight download |
| `OLLAMA_HOST` | user env (default `http://127.0.0.1:11434`) | Ollama client; warn if not loopback |
| `SLOTH_CHAT_MODEL` | Settings | `gemma4:e4b` / `gemma4:e2b` |
| `SLOTH_TELEMETRY` | main (from Settings) | Sentry opt-in |
| `SLOTH_NO_WATCHDOG` | dev/CI | disable stdin watchdog for manual runs |
| `SLOTH_PYTHON` | dev | interpreter for `npm run dev` (e.g. `engine/.venv/bin/python`) |

Reminder defaults and demo compression live in the `settings` table, not in env vars.
