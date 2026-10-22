# SlothSpend — Implementation Plan

> **Companion to** `sloth-spend-spec.md` v1.0 (2026-10-20)
> **UI source of truth** SlothSpend MVP design canvas — https://claude.ai/artifact/MiHiXUydDRazRhDrzKRoec (9 artboards, each in light and dark)
> **Written** 2026-10-21 · **Hard deadline** entry window closes Oct 25, 2026 (check the Week 3 rules page for the exact time)
> **Shape** 11 milestones (M0–M10). M0–M9 are the MVP (≈ 23.5 h of build). M10 is stretch work, started only after the Definition of Done passes.

---

## How to read this document

- **The spec covers the *what* and *why*:** behaviour, security, data model, algorithms and reference code. **This document covers the *how* and *in what order*.** It also settles everything the spec leaves open, and it covers the parts of the design that need data or endpoints the spec doesn't define.
- **What wins when they disagree:**
  - Behaviour, security, privacy and the "inform, never act" rule → **the spec**.
  - Layout, visual language, component look and UI copy → **the design**.
  - Where the design needs something the spec doesn't provide, §3 of this doc extends the contract. Every such change is listed in §2.
- **How references are written:** `§7.4` means a section of the spec. `D-Main` means a design artboard (index below). `M4.3` means task 3 of milestone 4.
- **When to move on:** don't start a milestone until the previous milestone's **Exit checklist** passes. The one exception: M2 (packaging) can run in parallel with M3 when two people are working.
- **Reusing spec code:** when a task says "verbatim from §x", copy the spec's code as-is. Only adapt it where this document says to.

### Design artboard index

| Ref | Artboard (canvas title) | Shows |
|---|---|---|
| **D-Boot** | 1 · Boot — getting models ready | First run: pink hero with the sloth on the left, the "Getting ready" checklist (Engine / Gemma 4 / TabPFN-3.5) on the right, "Continue in limited mode" |
| **D-Import** | 2 · Empty workspace — drop a statement | Workspace shell, Audit/Reminders tabs, pink drop zone, "How it works" in 4 steps, Ask Sloth empty state |
| **D-Mapper** | 3 · Column mapper | "Help SlothSpend read this file": detected-column status, currency, date order, "debits are positive", a role select on each column of the 10-row preview, Run audit / Cancel |
| **D-Progress** | 4 · Audit in progress | "Reading your statement.": elapsed timer, overall progress bar, 9 named stages with model chips, sub-progress "Gemma cleaned 41 / 62 merchants" |
| **D-Main** | 5 · Audit report + Ask Sloth | Statement bar, Sloth's summary (pink card), 4 summary cards, burn chart with a Subscriptions/All toggle, findings table with filters and expandable row actions, live chat |
| **D-Drawer** | 6 · Merchant drawer + How to cancel | Right sheet over a scrim: chips, recurring score with corrections, charge bars, reasons, "Looks like", next-charge range, flag cards, merchant edit, How to cancel with a draft |
| **D-Reminders** | 7 · Reminders + refund draft | Banner, latest-statement card, Needs you / Watching / Done groups, phase steppers, chat showing a refund draft and a reminder chip |
| **D-Settings** | 8 · Settings | Centered modal: Appearance, Models, Statements, Reminders, Privacy + egress table, Delete all local data |
| **D-Notif** | 9 · Notification inbox + desktop toast | 440 px inbox popover anchored to the bell, unread dots, Mark all read; the OS toast |

The dark artboards (`*Dark.dc.html`) render the same components with `theme="dark"`, so they add no new layout. They confirm that both themes must ship (§5.1).

---

## 1. Milestones at a glance

| # | Milestone | Est. | Spec checkpoint | Stories | Exit demo |
|---|---|---|---|---|---|
| **M0** | Bootstrap and design foundation | 1.5 h | — | — | `npm run dev` opens a window; the `#/kitchen-sink` dev route shows every UI primitive in light and dark |
| **M1** | Walking skeleton: Electron ⇄ engine ⇄ Boot | 1.5 h | Day 1 0:00–1:30 | US-1 (read-only) | The dev app boots to a green **Engine** row. Gemma and TabPFN rows show real status. The engine dies when Electron is force-killed |
| **M2** | Package first: PyInstaller, electron-builder, CI | 1.5 h | **A** | — | Both CI installers launch to a green Engine on real machines |
| **M3** | Data foundation: sample data, priors, DB, ingest | 2 h | Day 1 3:00–4:30 | US-2 (parse) | The sample, the HDFC fixture and the US fixture parse. The mapper payload is correct. `test_ingest` is green |
| **M4** | Audit engine: Gemma, features, TabPFN, detectors, pipeline, setup flows | 4 h | **B** | US-1, US-2, US-3, US-4 (API) | `POST /demo/load-sample` streams 9 stages and returns the golden values in §7. The Boot screen can pull Gemma and save the Prior Labs key |
| **M5** | Audit UI | 3.5 h | **C** | US-2, US-3, US-4 | Full flow in dev: drop → (mapper) → progress → report → drawer → correction re-scores in ≤ 5 s |
| **M6** | Ask Sloth and drafts | 3 h | Day 2 0:00–3:00 | US-5, US-6 | Every suggested prompt gets a grounded answer with ≥ 1 visible tool call. The drawer drafts a cancellation/refund/negotiation email |
| **M7** | Reminders and notifications | 2.5 h | **D** | US-7, US-8 | remind → snooze → I cancelled it → follow-up import shows **Verified** / **Still charged**, and survives a restart |
| **M8** | Settings and privacy | 1.5 h | — | US-9 | The Settings modal is fully wired. `test_egress` is green. Delete all local data works |
| **M9** | Hardening, release, landing page | 2.5 h | **E** | all | DoD 1–8 (§13.2) pass on clean Mac and Windows machines. `v0.1.0` tagged. slothspend.tech is live |
| **M10** | Stretch (only after E) | — | — | — | Sentry gen_ai spans → open at login → landing polish → trial detector |

---

## 2. Where the design changes or extends the spec

| # | Area | Spec says | Design shows | Decision for the build |
|---|---|---|---|---|
| 1 | Visual language | §9.1: dark slate `#0F172A`, moss `#7BAE7F`, Inter/DM Sans | Light **and** dark themes. Ink `#0B051D`, pink accent `#FFA8CD`, lilac panels. **Archivo** display + **Inter** UI | **Follow the design.** The tokens are copied exactly into `tokens.css` (§5.1). `BrowserWindow.backgroundColor` follows `nativeTheme` (`#FFFFFF` / `#0B051D`), not `#0F172A` |
| 2 | Theme switching | — | Sun/moon toggle in every top bar; Settings › Appearance; "starts in your computer's setting until you pick one" | `data-theme` on `<html>`. Preference is `system \| light \| dark` in `localStorage["sloth.theme"]`. This is a per-viewer convenience, so it isn't stored in the engine |
| 3 | Fonts | — | Google Fonts `<link>` | **Bundle `@fontsource/inter` and `@fontsource/archivo`.** A CDN link breaks the offline promise (US-9, DoD 7) and the CSP |
| 4 | Charts | §5: Recharts | Small CSS-drawn bars, a forecast dot with a q10–q90 band, a range strip | **Build them by hand** (`BurnChart`, `ChargeBars`, `RangeStrip`) from divs and SVG with tokens. They're simpler than restyling Recharts to match, and drop a dependency. **Recharts is removed** |
| 5 | Burn chart | Monthly recurring bars plus a next-month point and band | A **Subscriptions / All recurring** toggle. Months with a flag drawn in pink with a legend that explains them | `GET /report` adds `monthly[]` and `forecast_next{subscriptions, all}` (§3.2) |
| 6 | Summary | §7.8 step 8 writes `executive_summary`; no placement given | Pink "Sloth's summary" card with a `Gemma 4 · local` chip | Show `meta.executive_summary` with a source chip (`Gemma 4 · local` or `Template`) |
| 7 | Summary cards | Four cards | Each card has a sub-line: subscriptions vs bills split, "If you cancel the 4 zombie suspects yourself — plus a $49.99 double charge to dispute", and flag-count chips | New meta fields: `monthly_subscriptions`, `monthly_bills`, `zombie_count`, `dispute_total`, `flag_counts`, `flagged_merchants` |
| 8 | Findings table | One row per finding, actions inline | Filter chips (**All / Flagged / Subscriptions / Bills** with counts). Columns: Merchant (+ category chip + cadence text), Last charge, Change, Recurring bar, Flags, Next due, and a **More actions** button that expands the row's actions. "1 charge" instead of a score for single charges. A **Low confidence** dashed chip | Row actions sit behind the expander. Each series gets `kind` (`subscription\|bill\|other`), `cadence_label`, `change_label` (§6 M5.7) |
| 9 | Drawer | Sparkline, reasons, archetypes, forecast, flag details, edit, How to cancel | Also: a recurring-score card with **Keep / Not a subscription**, "Looks like · 3 of 5 nearest examples", the **Next charge** block (Due / Most likely / Range / Price-rise chance) with a range strip, one card per flag (the duplicate card has **Draft refund request**), and "Seen in your statement as …" | `GET /series/{id}` adds `reasons[]`, `similar{}`, `raw_descriptions[]`, `desc_keys[]`. New `PATCH /series/{id}/merchant` renames or recategorises all of a merchant's keys and re-scores |
| 10 | Column mapper | Dropdowns, a "debits are positive" toggle, currency | "Header on row 14 · 13 preamble lines skipped", status chips for the required columns, a **Date order** select, and a role select inside each column header | `POST /import` adds `file_name`, `header_row`, `columns[]`, `row_count`. Confirm also accepts `dayfirst`. **Cancel** calls new `DELETE /import/{id}` |
| 11 | Progress | Stages with counts | 9 plain-language stage names, per-stage model chip, elapsed timer | The renderer maps stage ids to labels (§6 M5.4). The SSE format is unchanged |
| 12 | Reminders tab | One card per reminder with a stepper | Grouped **Needs you / Watching / Done**. Tab badge "**2 need you**". Latest-statement card ("checked 2 cancelled subscriptions"). Stepper steps carry dates ("Oct 15", "Skipped", "Today") | `reminders.events_json` records each transition. `GET /reminders` joins series facts. `imports.verified_count` |
| 13 | Notifications | Bell with unread count | A 440 px inbox popover with relative times, unread dots and **Mark all read** | `GET /notifications?all=1` and new `POST /notifications/read-all` |
| 14 | Settings | Model, currency, key, reminder days, demo compression, open at login, telemetry, egress, delete | Adds **Appearance**, key status with **Replace / Remove**, a **Demo mode** switch with seconds, egress destinations as chips | Telemetry and the key live in Electron main (`prefs.json`). Everything else comes from engine `GET/PUT /settings`. **"Open at login" stays hidden until M10** |
| 15 | Boot | Checklist with fixes | Gemma progress with "2.1 GB of 5.0 GB · About 6 min left", a "Use gemma4:e2b instead" link, an inline Prior Labs key form, and a 2 px ring around the row that needs action | ETA is computed client-side from the pull rate. Key handled over IPC (§6 M4.12) |
| 16 | Chat | Streaming markdown, tool badges, chips, copy buttons on drafts | Follow-up buttons under answers ("Draft refund request", "Remind me 3 days before"), a `TabPFN-3.5 · live` chip next to live tools, a draft **card** with Copy, a "Reminder set for …" chip | The client derives these from tool calls (§6 M6.8). Drafts use a fenced `Subject:` block convention |
| 17 | Burn chart, current month | — | October drawn as a full $87.46 | The real October bar is **month-to-date** (report date Oct 15, so $65.48). Draw it with a hatched top and the tooltip "Oct 1–15 so far". The mock's number is placeholder |
| 18 | Follow-up CSVs | §11.1: follow-ups differ only in IronTrap | The reminders board shows IronTrap **Still charged** and StreamFlix **Verified** at the same time | **Both** follow-up CSVs leave out StreamFlix after Oct 15, so the combined state can be demoed |
| 19 | Prototype link | — | D-Progress "Skip ahead to the finished report (prototype)" | Not built |
| 20 | Gemma model | §5, §7: `gemma4:e4b` (fallback `gemma4:e2b`) | "Gemma 4 · local" chips; "Download Gemma 4" | **Use whatever Gemma model Ollama already has** (owner's decision, 2026-10-21). Selection: an explicit choice (Settings / `SLOTH_CHAT_MODEL`) if it is installed, else the best installed Gemma (newest generation first, then the `e4b` → `latest` tags). Only when *no* Gemma is installed does Boot offer to download `gemma4:e4b`. `/health` returns the model in use plus `available_models`; chips and labels name the real generation ("Gemma 3 · local") |
| 21 | TabPFN version | §7.6, §12.4: TabPFN‑3.5 only (license-gated, needs a Prior Labs key); without one, a heuristic scorer | Boot "TabPFN-3.5 · Needs your key"; `TabPFN-3.5` chips | **TabPFN v2 by default; TabPFN‑3.5 is an optional upgrade** (owner's decision, 2026-10-21). Tested in the M2 timeframe: with no key or token, `tabpfn` refuses to download 3.5/3.5‑fast (`TabPFNLicenseError`), but v2 weights are open (Prior Labs License 1.1, no account): ~70 MB from Hugging Face once, then fully offline, with string categoricals, NaNs and quantile output all working. Rule: **no stored key → v2; key stored (encrypted, §6 M4.12) → 3.5 (3.5‑fast on CPU), falling back to v2 with a visible reason if the upgrade fails; key removed → v2.** The heuristic scorer is only for a first run with no network. Chips and labels name the version in use (`TabPFN v2`, `TabPFN-3.5`). |

---

## 3. Contract extensions (on top of spec §7.2 and §8)

### 3.1 SQLite schema changes

Use `PRAGMA user_version`: `0` → run the spec schema and then these changes, and set `1`.

```sql
-- imports: pending vs committed, statement coverage, verification count
ALTER TABLE imports ADD COLUMN status TEXT NOT NULL DEFAULT 'pending';   -- pending|committed|done (rows stored ≠ report built)
ALTER TABLE imports ADD COLUMN header_row INTEGER;
ALTER TABLE imports ADD COLUMN period_start TEXT;
ALTER TABLE imports ADD COLUMN period_end TEXT;
ALTER TABLE imports ADD COLUMN skipped_rows INTEGER DEFAULT 0;
ALTER TABLE imports ADD COLUMN verified_count INTEGER DEFAULT 0;

-- series: UI-ready derived fields
ALTER TABLE series ADD COLUMN kind TEXT;            -- subscription|bill|other
ALTER TABLE series ADD COLUMN dom_median REAL;      -- day of month, for "near the 5th"
ALTER TABLE series ADD COLUMN amount_varies INTEGER DEFAULT 0;
ALTER TABLE series ADD COLUMN monthly_hist_json TEXT;  -- {"2026-01": 119.88, ...} cash per calendar month

-- report_meta: figures the summary cards and burn chart need
ALTER TABLE report_meta ADD COLUMN monthly_subscriptions REAL;
ALTER TABLE report_meta ADD COLUMN monthly_bills REAL;
ALTER TABLE report_meta ADD COLUMN fc30_sub_q10 REAL;
ALTER TABLE report_meta ADD COLUMN fc30_sub_q50 REAL;
ALTER TABLE report_meta ADD COLUMN fc30_sub_q90 REAL;
ALTER TABLE report_meta ADD COLUMN dispute_total REAL;
ALTER TABLE report_meta ADD COLUMN monthly_json TEXT;   -- [{month, subscriptions, all, highlights[]}]
ALTER TABLE report_meta ADD COLUMN summary_source TEXT; -- gemma|template

-- reminders: dated history for the stepper
ALTER TABLE reminders ADD COLUMN events_json TEXT NOT NULL DEFAULT '[]';  -- [{"phase":"WATCHING","at":"…Z"}, …]
```

(Since this is a new database, fold these into the `CREATE TABLE` statements rather than running `ALTER`. They're shown as `ALTER` here only so the changes are easy to see.)

`series` rows are **upserted on `merchant`** (`INSERT … ON CONFLICT(merchant) DO UPDATE`), never deleted and re-inserted, because `reminders.series_id` points at them. After each pipeline run, delete only series rows that have disappeared **and** have no reminder.

### 3.2 API changes (all routes still require `X-Sloth-Token`)

| Change | Method & path | Request → Response |
|---|---|---|
| extended | `GET /health` | `ollama` also gets `loopback: bool` and `available_models`. Status values: `ready \| unreachable \| outdated \| missing_model`. `tabpfn.status`: `cold \| downloading \| warming \| ready \| unavailable \| error`; `tabpfn.model` is the version in use; `tabpfn.upgrade` reports the optional 3.5 upgrade (§2 #21) |
| extended | `POST /import` | → `{import_id, duplicate, needs_mapping, mapping, columns[], header_row, preview[10][], currency, dayfirst, file_name, row_count}`. `duplicate: true` means the same SHA-256 was already imported: nothing to do |
| **new** | `DELETE /import/{id}` | Discards a *pending* import (mapper Cancel) → `{ok}` |
| extended | `POST /import/{id}/confirm` | `{mapping?, debits_positive?, currency?, dayfirst?}` → SSE (§3.4). A second concurrent run → `409` |
| extended | `GET /report` | → `{meta, series[], monthly[], forecast_next:{subscriptions, all}}`. `404` until the first import finishes |
| **new** | `POST /report/rescore` | Re-runs steps 3–7 with the current scorer (after TabPFN becomes ready mid-session) → `{report}` |
| extended | `GET /series/{id}` | → `{series, transactions[], quantiles[], similar, reasons[], raw_descriptions[], desc_keys[], reminder?}` |
| extended | `POST /series/{id}/label` | `label` also accepts `"subscription"`, used for "It's a subscription" on low-score rows |
| **new** | `PATCH /series/{id}/merchant` | `{merchant, category}` writes every `desc_key` of the series with `source='user'`, re-scores (≤ 5 s) → `{report, series_id}`. The new id can differ if the rename merges into an existing merchant |
| extended | `GET /reminders` | Each row also gets `{amount, cadence, low_confidence, days_left, remind_on, cancelled_on, events[], group}` where `group` is `needs_you \| watching \| done` |
| extended | `GET /notifications` | `?since_id=N` (polling, unchanged) **or** `?all=1` (inbox, newest 50, includes `read_at`) |
| **new** | `POST /notifications/read-all` | → `{ok}` |
| extended | `GET/PUT /settings` | `{currency, chat_model, days_before, demo_compress_seconds}`. `0` means demo mode is off |

### 3.3 Shared TypeScript types — `src/renderer/src/lib/types.ts`

These mirror the engine's Pydantic response models (`engine/app/schemas.py`). Keep both files in step and change them in the same commit.

```ts
export type Scorer = "tabpfn-v2" | "tabpfn-3.5" | "tabpfn-3.5-fast" | "heuristic";
export type Cadence = "weekly" | "biweekly" | "monthly" | "quarterly" | "annual" | "irregular" | "single";
export type FlagId = "duplicate_charge" | "price_creep" | "overlap" | "possible_annual" | "zombie_suspect";
export type SeriesStatus = "active" | "keep" | "not_subscription" | "user_cancelled";
export type Phase = "WATCHING" | "REMINDED" | "SNOOZED" | "KEPT" | "EXPIRED" | "STOPPED"
  | "AWAITING_STATEMENT" | "VERIFIED_STOPPED" | "STILL_CHARGED";

export interface Health {
  engine: "ok";
  ollama: { status: "ready" | "unreachable" | "outdated" | "missing_model"; version: string | null;
            model: string /* installed Gemma in use, or the download offer */; model_present: boolean;
            available_models: string[]; loopback: boolean };
  tabpfn: { status: "cold" | "downloading" | "warming" | "ready" | "unavailable" | "error"; model: Scorer | null; error: string | null;
            /** The optional TabPFN-3.5 upgrade: none = no key stored · active = 3.5 in use · failed = still on v2, see error. */
            upgrade: { state: "none" | "downloading" | "active" | "failed"; error: string | null } };
  telemetry: boolean;
}

export interface Q { q10: number; q50: number; q90: number }

export interface FlagDetails {
  duplicate_charge?: { first: string; second: string; amount: number; tx_ids: number[] }[];
  price_creep?: { from: number; to: number; pct: number; since: string };
  overlap?: { category: string; merchants: string[] };
  possible_annual?: { next_due: string };
  zombie_suspect?: { because: ("overlap" | "price_creep" | "duplicate_charge" | "long_running")[] };
}

export interface Series {
  id: number; merchant: string; category: string; kind: "subscription" | "bill" | "other";
  n_charges: number; first_date: string; last_date: string;
  cadence: Cadence; cadence_days: number | null; dom_median: number | null;
  last_amount: number; monthly_equiv: number; amount_varies: boolean;
  recurring_prob: number | null; scorer: Scorer;
  next_due_date: string | null; fc_q10: number | null; fc_q50: number | null; fc_q90: number | null; hike_prob: number | null;
  flags: FlagId[]; flag_details: FlagDetails; priority: number; cancellable: boolean; status: SeriesStatus;
}

export interface ImportInfo { id: number; file_name: string; row_count: number; skipped_rows: number;
  period_start: string; period_end: string; imported_at: string; verified_count: number }

export interface ReportMeta {
  generated_at: string; report_date: string; currency: string; scorer: Scorer;
  monthly_recurring: number; monthly_subscriptions: number; monthly_bills: number;
  fc30: Q; potential_savings: number; zombie_count: number; dispute_total: number;
  flag_counts: Record<FlagId, number>; flagged_merchants: number;
  executive_summary: string; summary_source: "gemma" | "template";
  imports: ImportInfo[];            // oldest → newest
}

export interface MonthPoint { month: string /* YYYY-MM */; subscriptions: number; all: number;
  partial: boolean; highlights: string[] /* "CloudBox Pro’s $119.88 annual charge" */ }

export interface Report { meta: ReportMeta; series: Series[]; monthly: MonthPoint[]; forecast_next: { subscriptions: Q; all: Q } }

export interface SeriesDetail {
  series: Series; transactions: { id: number; date: string; amount: number; is_duplicate: boolean }[];
  quantiles: { q: number; amount: number }[];
  similar: { archetype: string; count: number; k: number; runner_up: string | null };
  reasons: string[]; raw_descriptions: string[]; desc_keys: string[]; reminder: Reminder | null;
}

export interface Reminder {
  series_id: number; merchant: string; amount: number; cadence: Cadence; low_confidence: boolean;
  next_due_date: string; days_left: number; phase: Phase; group: "needs_you" | "watching" | "done";
  detail: string | null; remind_at: string | null; remind_on: string | null; reminders_sent: number;
  cancelled_on: string | null; events: { phase: Phase; at: string }[];
}

export interface Notice { id: number; series_id: number; kind: "reminder" | "verified" | "still_charged";
  title: string; body: string; created_at: string; read_at: string | null }

export interface EngineSettings { currency: "USD" | "INR" | "EUR" | "GBP"; chat_model: string | null /* null = best installed Gemma */;
  days_before: number; demo_compress_seconds: number }
```

### 3.4 SSE event catalogue

| Stream | Events (`event:` / `data:` JSON) |
|---|---|
| Pipeline (`/import/{id}/confirm`, `/demo/load-sample`) | `stage {stage, done, total, note?}` with stage ∈ `parse, normalize, detect, features, score, forecast, flags, summary, done` · `done {report}` · `error {stage, message}` |
| Ollama pull (`/setup/ollama/pull`) | `progress {status, completed?, total?}` · `done {model}` · `error {message}` |
| Chat (`/chat`) | `token {text}` · `tool_start {name, args}` · `tool_end {name, ms, preview}` · `done {rounds}` · `error {message}` |
| Draft (`/series/{id}/draft`) | `token {text}` · `done {source: "gemma"\|"template", title}` |

The pipeline runs as an **`asyncio` task that writes into a queue**, and the SSE generator only reads from that queue. If the renderer reloads mid-audit, the run still finishes and persists. A run is guarded by `runtime.pipeline_lock`, which `rescore` and `label` also take.

---

## 4. Repository layout (final)

The project scaffolds **into this repo's root** (`sloth-spend/`), not a `slothspend/` subfolder. The `.gitignore`, `LICENSE` and spec already there stay. Additions to spec §4 are marked ✚.

```
sloth-spend/
├── sloth-spend-spec.md · IMPL.md · README.md ✚ · LICENSE
├── package.json · electron.vite.config.ts · electron-builder.yml
├── tsconfig.json / tsconfig.node.json / tsconfig.web.json · eslint.config.js ✚ · .prettierrc ✚
├── build/                               # electron-builder buildResources (packaging only):
│                                        #   icon.icns, icon.ico, icon.png, entitlements.mac.plist
├── resources/                           # runtime files shipped in the app: icon.png (window), icon-macos.png (dev Dock)
├── design/icons/                        # source artwork, never packaged — README maps every icon to its home
├── src/
│   ├── main/{index.ts, sidecars.ts, secrets.ts, logbuffer.ts ✚}
│   ├── preload/index.ts
│   └── renderer/
│       ├── index.html                    # CSP meta (M1.6)
│       └── src/
│           ├── main.tsx · App.tsx
│           ├── assets/{brand/logo-mark.svg, mascot/{sloth-hanging, sloth-avatar, sloth-avatar-sleepy}.svg} ✚
│           ├── styles/{index.css, tokens.css} ✚
│           ├── lib/{api.ts, types.ts ✚, format.ts ✚, theme.ts ✚, notify.ts ✚, ui-derive.ts ✚}
│           ├── store.ts ✚                # zustand: tab, drawer, modal, chat prefill, report cache
│           ├── screens/{Boot.tsx, Workspace.tsx, KitchenSink.tsx ✚ (dev only)}
│           └── components/
│               ├── brand/{Logo.tsx (Logo, SlothAvatar, SlothAvatarSleepy, Wordmark), SlothHanging.tsx} ✚
│               ├── ui/{Button, Chip, SourceChip, Card, ProgressBar, Spinner, Switch, Field,
│               │       Select, Stepper, Modal, Sheet, Popover, Menu, Tooltip, CopyButton}.tsx ✚
│               ├── shell/{TopBar, StatusPills, ThemeToggle, NotificationBell, NotificationInbox,
│               │          LimitedBanner, WorkspaceTabs}.tsx ✚
│               ├── audit/{ImportEmpty, DemoDataMenu, StatementBar, ColumnMapper, PipelineProgress,
│               │          SummaryNarrative, SummaryCards, BurnChart, FindingsTable, FindingRow,
│               │          MerchantDrawer, ChargeBars, RangeStrip, FlagCards, MerchantEdit,
│               │          HowToCancel, NegotiateEmail, DraftCard}.tsx
│               ├── reminders/{RemindersPanel, ReminderCard, PhaseStepper, LatestStatement}.tsx
│               ├── chat/{ChatPane, MessageList, ToolBadge, FollowUps, PromptChips, ChatInput}.tsx
│               └── settings/{SettingsModal, EgressTable, DeleteDataDialog}.tsx
├── engine/
│   ├── requirements.txt · requirements-dev.txt ✚ · run_engine.py · slothspend_engine.spec
│   ├── app/
│   │   ├── main.py config.py security.py state.py paths.py schemas.py ✚
│   │   ├── db.py ingest.py normalize.py features.py detectors.py tabular.py
│   │   ├── report.py explain.py ✚ llm_summary.py money.py ✚ ollama_setup.py ✚
│   │   ├── agent.py tools.py drafts.py ✚ reminders.py notes.py telemetry.py
│   │   ├── api/{__init__, health, setup, imports, reports, series, chat, reminders,
│   │   │        notifications, settings, admin}.py ✚
│   │   └── data/{priors_recurring.csv, priors_hikes.csv, sample_bank_12m.csv,
│   │            followup_cancelled.csv, followup_still_charged.csv}
│   ├── scripts/{make_sample_data.py, make_priors.py, smoke_test.py}
│   └── tests/{conftest.py ✚, test_ingest.py, test_features.py, test_detectors.py, test_report.py ✚,
│              test_api.py ✚, test_agent_tools.py ✚, test_reminders.py, test_egress.py,
│              fixtures/{hdfc_style.csv, us_signed.csv, sample_merchant_map.json ✚}}
├── site/{index.html, favicon.ico, favicon.svg, apple-touch-icon.png, icon-192.png, icon-512.png}
└── .github/workflows/{release.yml, ci.yml ✚}
```

---

## 5. Design system implementation

### 5.1 Color tokens (copied exactly from the design) — `src/renderer/src/styles/tokens.css`

```css
:root, [data-theme="light"] {
  color-scheme: light;
  --bg:#FFFFFF; --card:#F8F7FA; --panel:#EFECFF; --raised:#FFFFFF; --tint:#E4E0F7;
  --ink:#0B051D; --text-2:#282636; --muted:#504F5F; --subtle:#6C6B74; --faint:#96959F;
  --line:#E2E2E7; --line-strong:#C4C3CA; --solid:#0B051D; --on-solid:#F9F8F5; --on-solid-2:#E4E0F7;
  --accent:#FFA8CD; --on-accent:#0B051D; --accent-edge:#0B051D; --accent-tint:#FFE3EF; --accent-wash:#FFF4F9;
  --success:#046234; --success-tint:#E9F3EE; --link-hover:#582FB4;
  --scrim:rgba(11,5,29,0.36); --shadow:rgba(0,0,0,0.1);
}
[data-theme="dark"] {
  color-scheme: dark;
  --bg:#0B051D; --card:#161029; --panel:#1F192F; --raised:#2A2340; --tint:#342A4E;
  --ink:#F9F8F5; --text-2:#DCD9E8; --muted:#B5B2C6; --subtle:#9D9AB0; --faint:#6F6A86;
  --line:#2C2542; --line-strong:#4B4366; --solid:#F9F8F5; --on-solid:#0B051D; --on-solid-2:#504F5F;
  --accent:#FFA8CD; --on-accent:#0B051D; --accent-edge:#FFA8CD; --accent-tint:#4A2440; --accent-wash:#2A1630;
  --success:#7ED9A8; --success-tint:#12352A; --link-hover:#C9B8FF;
  --scrim:rgba(0,0,0,0.6); --shadow:rgba(0,0,0,0.5);
}
a { color: var(--ink); } a:hover { color: var(--link-hover); }
:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px; box-shadow: 0 0 0 5px #7B57D8; }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { transition-duration: 1ms !important; animation-duration: 1ms !important; } }
```

**The pink-surface rule.** Every pink (`--accent`) surface carries its own `data-theme="light"` attribute, so ink-on-pink stays dark in both themes. This covers the Boot hero, the import drop zone, Sloth's summary, the Still-charged reminder card and the still-charged inbox row. The design does exactly this, so copy it.

### 5.2 Tailwind v4 wiring — `src/renderer/src/styles/index.css`

```css
@import "tailwindcss";
@import "@fontsource/inter/400.css"; @import "@fontsource/inter/500.css"; @import "@fontsource/inter/700.css";
@import "@fontsource/archivo/400.css"; @import "@fontsource/archivo/700.css";
@import "./tokens.css";

@theme inline {
  --color-bg: var(--bg); --color-card: var(--card); --color-panel: var(--panel); --color-raised: var(--raised);
  --color-tint: var(--tint); --color-ink: var(--ink); --color-text-2: var(--text-2); --color-muted: var(--muted);
  --color-subtle: var(--subtle); --color-faint: var(--faint); --color-line: var(--line); --color-line-strong: var(--line-strong);
  --color-solid: var(--solid); --color-on-solid: var(--on-solid); --color-on-solid-2: var(--on-solid-2);
  --color-accent: var(--accent); --color-on-accent: var(--on-accent); --color-accent-edge: var(--accent-edge);
  --color-accent-tint: var(--accent-tint); --color-success: var(--success); --color-success-tint: var(--success-tint);
  --font-sans: "Inter", -apple-system, system-ui, "Segoe UI", Roboto, Arial, sans-serif;
  --font-display: "Archivo", "Inter", sans-serif;
  --font-mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  --radius-hero: 48px; --radius-section: 32px; --radius-card: 24px; --radius-tile: 16px;
}
body { margin: 0; background: var(--bg); color: var(--ink); font: 16px/1.5 var(--font-sans);
       transition: background-color 400ms ease-out, color 400ms ease-out; }
```

### 5.3 Type scale (from the artboards)

| Token | Font | Size / line-height / weight | Used for |
|---|---|---|---|
| `display-xl` | Archivo | 52 / 1.0 / 700 | Boot "Slow and steady.", drop zone headline, mapper/progress h1 |
| `display-tab` | Archivo | 44 / 1.1 / 700 | **Audit / Reminders** tab nav. The current tab is `--ink`, the other `--subtle` |
| `stat` | Archivo | 43.2 / 0.95 / 700, `tabular-nums` | Summary card figures, "How it works" numerals |
| `h2` | Inter | 32 / 1.25 / 700 | "Getting ready", "Findings", drawer merchant name, "How to cancel", "Settings" |
| `h3` | Inter | 20 / 1.25 / 700 | Card titles, "Ask Sloth", drawer section titles, reminder merchant |
| `lead` | Inter | 20 / 1.4 / 400 | Hero sub-copy, Sloth's summary |
| `body` | Inter | 16 / 1.5 | Default; inputs are always 16 px |
| `small` | Inter | 14 / 1.45 (500 for labels and buttons) | Secondary copy, buttons, chips in rows |
| `caption` | Inter | 12 / 1.45–1.65 (500 for chips) | Meta lines, chart ticks, footers |
| `mono` | system mono | 12 / 1.5 | Tool badges and tool previews |

Every money figure uses `font-variant-numeric: tabular-nums`.

### 5.4 Shape, spacing, elevation

- **Radii.** 48 px: hero surfaces (Boot hero, drop zone). 32 px: major panels (summary card, mapper/progress panels, Settings modal, the drawer's left edge, Boot checklist). 24 px: cards, the Ask Sloth aside, reminder cards, the inbox. 16 px: rows, sub-cards, the statement bar, chat bubbles (the tail corner is 4 px). 12 px: `<pre>`. Fully round (`9999px`): every button, chip, input, select, progress bar and toggle.
- **Control heights.** 52 px primary CTA · 44 px standard button, input and icon button (the touch target floor) · 36 px status pill · 32 px tool badge · 28/24/22 px chips.
- **Gaps.** Page sections 24 px · card grid 16 px · inside cards 10–20 px · chip rows 6 px.
- **Elevation.** Mostly flat: surfaces are separated by tone (`bg → card → panel → raised`). Only overlays (drawer, modal, inbox) get `box-shadow: 0 2px 4px var(--shadow)` plus `--scrim` behind them.
- **Workspace shell.** Header `min-height 72px; padding 14px 24px`. Body `display:flex; flex-wrap:wrap; gap:16px; padding:0 16px 16px`. Main pane `flex:62 1 560px; padding:4px 16px 48px; gap:24px`. Aside `flex:38 1 380px; background:var(--panel); border-radius:24px; padding:20px`. **In the app the aside is sticky** (`position:sticky; top:16px; height:calc(100vh - 88px)`), and only its message list scrolls. The window minimum of 1100 px wide (§6.3) keeps the two columns side by side, and they wrap below that.

### 5.5 Component inventory

| Primitive | Variants (design source) | Notes |
|---|---|---|
| `Button` | `solid` (bg solid / on-solid) · `outline` (1 px ink, transparent) · `soft` (raised + 1 px line) · `ghost` · `outline-strong` (1 px line-strong) · `danger` (Settings delete: outline ink + trash icon) · sizes `lg` 52 / `md` 44 | Always a real `<button>` or `<a>`. Icon-only buttons need `aria-label` |
| `Chip` | `solid` (duplicate) · `accent` (price rise) · `tint` (overlap, possible annual, "For demos") · `outline` (zombie suspect) · `dashed` (low confidence) · `success` (Verified) · `raised` (category) · heights 22/24/28 | Flag chips carry an icon (§5.6) |
| `SourceChip` | `Gemma 4 · local` · `TabPFN v2` · `TabPFN-3.5` · `TabPFN-3.5 Fast` · `TabPFN v2 · live` · `Heuristic` (dashed) · `Template` (dashed) | Every model output shows one (§9.1) |
| `Card` | `card` · `panel` · `raised` · `solid` (savings card) · `accent` (forced light) · `outlined` (Done reminders: bg + 1 px line) | Radius from §5.4 |
| `ProgressBar` | 8 px track `--tint`, fill `--ink` · 6 px score bar (fill `--ink` if ≥ 50 %, else `--subtle`) | `role="progressbar"` with `aria-valuenow` |
| `Switch` | 44 px track, `role="switch"` on a real checkbox | Settings |
| `Field`/`Select`/`Input` | Pill, 44 px, 1 px `--line-strong`, bg `--bg` or `--raised` | Labels always visible except in chat (visually hidden) |
| `Stepper` | 4 steps: done (solid ✓) · ok (success ✓) · current (accent + 2 px edge) · alert (raised + 2 px ink + "!") · skip (dashed ring) · todo (ring `--subtle`). Connector is ink when passed, `--line-strong` when not | Reminders |
| `Sheet` | Right side, `max-width:620px`, radius `32px 0 0 32px`, padding `28px 32px 40px`, scrim | The drawer. Esc closes, focus is trapped, and focus returns to the row that opened it |
| `Modal` | Centered, `max-width:800px`, 64 px top offset, radius 32, padding `32px 40px 40px` | Settings, the delete confirmation |
| `Popover` | 440 px, radius 24, bg `--bg`, padding 20, shadow; anchored right-aligned under the bell | Inbox |
| `Menu` | Popover list of `menuitem`s | "Demo data", row overflow on narrow widths |

### 5.6 Icons (`lucide-react`, 2 px stroke, 16–20 px)

**Source of truth: `design/icons/ui/icons.json`** (the icon kit's map of file → `lucide-react` component → where it's used). Import the components, never the SVG files. The kit's choices: `CircleCheck` (ready pill, Keep, key saved), `Check` (finished steps, I cancelled it, Verified), `X` (close), `Bell` (notifications, Remind me), `SlidersHorizontal` (settings), `Sun`/`Moon` (theme; `Moon` also on Snooze), `Upload` (drop zone, import newer statement), `Download` (Gemma download), `FileText` (statement chip, Choose CSV file), `Lock` ("never leaves this computer"), `ChevronDown` (Demo data), `TrendingUp` (price creep, Change column), `Copy` (duplicate flag, Copy draft), `Layers` (overlap), `Ghost` (zombie suspect), `Calendar` (possible annual), `Ellipsis` (more actions), `ListChecks` (How to cancel), `Ban` (not a subscription), `MessageCircle` (Ask Sloth), `Plus` (new conversation), `Wrench` (tool badge), `ArrowUp` (send), `Info` (banner), `TriangleAlert` (still charged), `LoaderCircle` (working), `Key` (TabPFN key row), `ExternalLink`, `Mail` (draft refund / cancellation request), `Pencil` (mapper "set by you"), `RefreshCw` (draft again, restart engine), `Trash` (delete data). Status pills also use `CircleAlert` (needs action). No emoji anywhere.

### 5.7 Brand art

The SlothSpend icon kit (`design/icons/`, see its README) supplies every brand file, each in exactly one place. The art is hard-coded `#0B051D` on pink or white **in both themes**, which is intentional.

- `Logo` renders `src/renderer/src/assets/brand/logo-mark.svg` (36 px, sloth face on a pink circle) in every header.
- `SlothHanging` renders `assets/mascot/sloth-hanging.svg` on the Boot hero, with alt text.
- `SlothAvatar` (`assets/mascot/sloth-avatar.svg`, 96 px) appears in the Ask Sloth empty states; `SlothAvatarSleepy` (eyes closed) in waiting/working states such as "Reading along with you." (M5).
- App icons are ready-made: `build/icon.icns` (macOS grid), `build/icon.ico` (16–256 px) and `build/icon.png` (1024) for electron-builder; `resources/icon.png` is the Windows/Linux window icon and `resources/icon-macos.png` the Dock icon during `npm run dev`. The app icon uses longer, slanted eye stripes than the logo so it reads as a sloth at 16 px.
- `site/` holds the slothspend.tech favicons (`favicon.ico`, `favicon.svg`, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png`).

### 5.8 Formatting rules — `lib/format.ts` (renderer) and `app/money.py` (engine)

- **Money.** Use `Intl.NumberFormat(locale, {style:"currency", currency})` with `en-IN` for INR (giving `₹1,18,450.20`) and `en-US` otherwise. `money.py` mirrors this, including Indian 2-2-3 grouping, because notes and summaries are formatted in code (§7.8, §7.10). Never let a model format numbers.
- **Dates.** Short form (`Nov 5`) in tables, chips and steppers. Long form (`Nov 5, 2026`) in the drawer, drafts and notes. Ranges look like `Nov 1, 2025 – Oct 15, 2026`. **Show the year only when it differs from the year of `report_date`** in short form (`Jan 14, 2027`).
- **Relative time** (inbox): `now`, `2 min`, `9:00 AM` (today), `Nov 9` (older).
- **Percentages.** Price change `+25.0%` in the table and `+25%` in chips. Recurring score is a rounded integer `98%`. Price-rise chance is `≈ 16%`.

---

## 6. Milestones

### M0 — Bootstrap and design foundation (1.5 h)

**Goal:** a repo where `npm run dev` opens a styled Electron window, the engine venv exists, and every UI primitive exists in both themes.

| # | Task | Details |
|---|---|---|
| M0.1 | Scaffold electron-vite | Run `npm create @quick-start/electron@latest slothspend-tmp -- --template react-ts` in a temp folder and move its contents into the repo root. Keep the existing `.gitignore` and add `out/ release/ engine/.venv engine/build engine/dist *.db`. App name `SlothSpend`, appId `tech.slothspend.desktop` |
| M0.2 | Preload output | The preload must build as **CommonJS** (`out/preload/index.js`), because `sandbox: true` refuses ESM preloads. Don't add `"type": "module"` to `package.json`, or force `build.rollupOptions.output.format = "cjs"` for preload in `electron.vite.config.ts` |
| M0.3 | Renderer dependencies | `tailwindcss @tailwindcss/vite lucide-react react-markdown remark-gfm @microsoft/fetch-event-source zustand @fontsource/inter @fontsource/archivo`. Dev: `vitest`. **No Recharts** (§2 #4) |
| M0.4 | Tooling | ESLint (typescript-eslint + react-hooks) and Prettier. Scripts: `dev`, `build`, `typecheck` (node + web), `lint`, `test` (vitest), `engine:venv`, `engine:test`, `engine:build`, `dist:mac`, `dist:win` |
| M0.5 | Engine venv | `engine/requirements.txt` as in §5. `requirements-dev.txt` holds `pytest pytest-asyncio httpx pyinstaller`. `uv venv engine/.venv --python 3.11 && uv pip install -r engine/requirements.txt -r engine/requirements-dev.txt`. Document `SLOTH_PYTHON=engine/.venv/bin/python` in README |
| M0.6 | Design foundation | `tokens.css` and `index.css` (§5.1–5.2), `lib/theme.ts` (below), all `ui/*` primitives (§5.5), `brand/*` (§5.7), `lib/format.ts` (§5.8) |
| M0.7 | Kitchen sink | `screens/KitchenSink.tsx`, reachable via `#/kitchen-sink` in dev only. It shows every primitive and variant plus a theme toggle, and is how the design is checked visually |

```ts
// lib/theme.ts
export type ThemePref = "system" | "light" | "dark";
const KEY = "sloth.theme";
const mq = window.matchMedia("(prefers-color-scheme: dark)");
export function readPref(): ThemePref {
  try { return (localStorage.getItem(KEY) as ThemePref | null) ?? "system"; } catch { return "system"; }
}
export function applyTheme(pref: ThemePref = readPref()): "light" | "dark" {
  const t = pref === "dark" || (pref === "system" && mq.matches) ? "dark" : "light";
  document.documentElement.dataset.theme = t;
  return t;
}
export function setPref(p: ThemePref) { try { localStorage.setItem(KEY, p); } catch { /* private mode */ } applyTheme(p); }
mq.addEventListener("change", () => readPref() === "system" && applyTheme());
```

Call `applyTheme()` before React mounts, so the window never flashes the wrong theme.

**Exit checklist**
- [ ] `npm run dev` opens a 1360×860 window. `#/kitchen-sink` matches D-Main's chips, buttons and cards in light and dark.
- [ ] `npm run typecheck && npm run lint && npm test` are green.
- [ ] `engine/.venv/bin/python -c "import fastapi, tabpfn, ollama"` succeeds.

---

### M1 — Walking skeleton: Electron ⇄ engine ⇄ Boot (1.5 h) · user story US-1 (read-only)

**Goal:** the real process topology (§3.1, §6) with a Boot screen that reports real status.

| # | Task | Details |
|---|---|---|
| M1.1 | `engine/app/{paths,config,security,state}.py` | `paths.py` and `security.py` verbatim from §7.1. `config.py` is a Pydantic `BaseSettings`-style object reading `SLOTH_PORT`, `SLOTH_TOKEN`, `SLOTH_DATA_DIR`, `OLLAMA_HOST` (default `http://127.0.0.1:11434`), `SLOTH_CHAT_MODEL`, `SLOTH_TELEMETRY`. Its `preferred_model` property returns the `settings` table value if one is set, else the env var, else `None`; `ollama_setup.pick_model()` turns that into the installed Gemma model actually used (§2 #20). `state.py` holds `runtime = SimpleNamespace(scheduler_task=None, pipeline_lock=asyncio.Lock(), pending={})` |
| M1.2 | `engine/app/main.py` | Verbatim from §7.1, plus routers from `app/api/*` and `POST /shutdown`. Shutdown answers `{ok}`, then `loop.call_later(0.2, os._exit, 0)`. In M1 `db.init()` and `run_scheduler` are stubs |
| M1.3 | `GET /health` (`api/health.py` + `ollama_setup.py`) | Ollama: `httpx` GET `{host}/api/version` (1 s timeout). Unreachable → `unreachable`. Version below `0.20.0` (compare as a tuple) → `outdated`. Otherwise GET `/api/tags`; a missing model → `missing_model`, else `ready`. `loopback` = the host resolves to 127.0.0.1, ::1 or localhost. TabPFN comes from `tabular.status` (a stub reporting `unavailable` until M4). **The handler never blocks on torch.** Every blocking call goes through `asyncio.to_thread` |
| M1.4 | `src/main/sidecars.ts` | Verbatim from §6.2, plus: stdout/stderr go into `logbuffer.ts` (a ring of 200 lines), and `proc.on("exit", code => win.webContents.send("engine:exit", code))` |
| M1.5 | `src/main/index.ts` | Verbatim from §6.3, plus: `backgroundColor: nativeTheme.shouldUseDarkColors ? "#0B051D" : "#FFFFFF"`; `win.webContents.on("will-navigate", e => e.preventDefault())`; `setWindowOpenHandler(() => ({ action: "deny" }))`; and IPC handlers `engine:logs`, `window:focus` (`win.show(); win.focus()`), `window:bg`. Extend `OPEN_ALLOW` with `^https://ollama\.com` (already there) |
| M1.6 | `src/preload/index.ts` and CSP | The preload is shown below. CSP in `index.html`: `default-src 'self'; connect-src 'self' http://127.0.0.1:*; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self'`. Dev keeps the template's HMR allowances |
| M1.7 | `lib/api.ts` | `init()` caches `getConfig()`. `req<T>()` adds `X-Sloth-Token` and throws `ApiError(status, body)`. `stream()` wraps `fetchEventSource` with **`openWhenHidden: true`** (the default closes streams when the window is hidden) and **no automatic retry**, because a pipeline must never re-run silently (code below) |
| M1.8 | Boot screen (D-Boot) | The two-column layout from the design: the pink hero (h1, sub-copy, `SlothHanging`, lock line) and the "Getting ready" card with 3 rows. In M1 the rows render status only. Header: logo, `v{version} · no account needed`, `ThemeToggle`. Polls `/health` every 1 s. Engine row states: *Starting…* (spinner) → *Ready* (success). If `engine:exit` arrives, it shows *Stopped* with the last 20 log lines in a `<pre>` and **Restart engine**. "Continue in limited mode" appears once the engine is ok. **If all three are ready, go straight to the workspace after 600 ms** |
| M1.9 | Workspace shell | `TopBar` (logo, `StatusPills`, `ThemeToggle`, bell placeholder, settings button), `WorkspaceTabs` (Audit / Reminders in display-tab type), the empty main pane, and the Ask Sloth aside empty state. Clicking a status pill that isn't green goes back to Boot. `LimitedBanner` (card style, `Info` icon) reads: "Limited mode: rule-based merchant names and a heuristic scorer. Every result is labelled. **Finish setup**" |

```ts
// src/preload/index.ts
import { contextBridge, ipcRenderer } from "electron";
const api = {
  getConfig: () => ipcRenderer.invoke("config:get") as Promise<{ apiBase: string; token: string; version: string; platform: string }>,
  openExternal: (url: string) => ipcRenderer.invoke("shell:open", url),
  restartEngine: () => ipcRenderer.invoke("engine:restart"),
  engineLogs: () => ipcRenderer.invoke("engine:logs") as Promise<string[]>,
  onEngineExit: (cb: (code: number | null) => void) => {
    const h = (_: unknown, code: number | null) => cb(code);
    ipcRenderer.on("engine:exit", h);
    return () => ipcRenderer.off("engine:exit", h);
  },
  priorKey: {
    present: () => ipcRenderer.invoke("secrets:has") as Promise<boolean>,
    save: (key: string) => ipcRenderer.invoke("secrets:set", key),
    remove: () => ipcRenderer.invoke("secrets:clear"),
  },
  telemetry: {
    get: () => ipcRenderer.invoke("prefs:telemetry:get") as Promise<boolean>,
    set: (on: boolean) => ipcRenderer.invoke("prefs:telemetry:set", on),
  },
  focusWindow: () => ipcRenderer.invoke("window:focus"),
  setBackground: (hex: string) => ipcRenderer.invoke("window:bg", hex),
};
contextBridge.exposeInMainWorld("sloth", api);
export type SlothBridge = typeof api;   // declared on Window in src/renderer/src/env.d.ts
```

```ts
// lib/api.ts (core)
import { fetchEventSource } from "@microsoft/fetch-event-source";
let cfg: { apiBase: string; token: string };
export class ApiError extends Error { constructor(public status: number, public body: string) { super(`${status}: ${body}`); } }
export async function init() { cfg = await window.sloth.getConfig(); }
export async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const isForm = body instanceof FormData;
  const r = await fetch(cfg.apiBase + path, {
    method,
    headers: { "X-Sloth-Token": cfg.token, ...(body !== undefined && !isForm ? { "Content-Type": "application/json" } : {}) },
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
  });
  if (!r.ok) throw new ApiError(r.status, await r.text());
  return (await r.json()) as T;
}
export function stream(path: string, body: unknown, on: Record<string, (d: any) => void>, signal?: AbortSignal) {
  return fetchEventSource(cfg.apiBase + path, {
    method: "POST", body: JSON.stringify(body ?? {}), signal, openWhenHidden: true,
    headers: { "X-Sloth-Token": cfg.token, "Content-Type": "application/json" },
    onmessage: (ev) => on[ev.event]?.(ev.data ? JSON.parse(ev.data) : null),
    onerror: (err) => { throw err; },
  });
}
```

**Exit checklist**
- [ ] `npm run dev` shows Boot → Engine green in ≤ 5 s. Gemma shows the real status (Ollama off → *unreachable*). TabPFN shows its stub status (*unavailable*) until M4.
- [ ] `curl 127.0.0.1:$PORT/health` without the token → `401`.
- [ ] Force-quitting Electron (`kill -9`) → the engine process is gone within 3 s (the stdin watchdog).
- [ ] Theme toggle switches the whole window with the 400 ms ease. The preference survives a restart.

---

### M2 — Package first (1.5 h) · **Checkpoint A**

**Goal:** prove PyInstaller + torch + tabpfn + electron-builder on both OSes **before** writing features (§14 "package first").

| # | Task | Details |
|---|---|---|
| M2.1 | `engine/run_engine.py` and `slothspend_engine.spec` | §12.1, with three changes. (1) `app/data/*.csv` are globbed, so the build works before M3 adds them. (2) `torch`, `huggingface_hub` and `python_multipart` are explicit hidden imports, because they are only imported inside functions. (3) `slothspend-engine --self-check` imports every heavy dependency and exits non-zero if one is missing, proving the bundle contains them without slowing normal startup |
| M2.2 | `scripts/smoke_test.py` | Four checks against the built binary: `--self-check`; `/health` reports `engine: ok` within 90 s and rejects a missing token (401); `POST /shutdown` exits the process; closing stdin (Electron dying) exits it. Temp `SLOTH_DATA_DIR`, no `TABPFN_TOKEN`. `npm run engine:smoke` locally |
| M2.3 | `electron-builder.yml` | §12.2 plus: `appId tech.slothspend.desktop`; `files` limited to `out/**`, `package.json` and `resources/**` (asar-unpacked); `artifactName: SlothSpend-${version}-${os}-${arch}.${ext}`. macOS uses **ad-hoc signing (`identity: '-'`) with the hardened runtime off**, because Apple Silicon won't run fully unsigned code; `entitlements.mac.plist` adds `disable-library-validation` for the engine's libraries. Renderer libraries live in `devDependencies` (Vite bundles them), so the app ships no `node_modules` |
| M2.4 | `.github/workflows/release.yml` | §12.3 with Node 24, pip caching keyed on `engine/requirements*.txt`, `timeout-minutes: 60`, and `if-no-files-found: error` on the upload |
| M2.5 | `.github/workflows/ci.yml` ✚ | Runs on PR and push to `main`, on `ubuntu-latest`: `npm ci && npm run typecheck && npm run lint && npm test`, then `pip install -r engine/requirements.txt -r engine/requirements-dev.txt` (CPU torch index) and `pytest engine/tests -q`. About 3 minutes |
| M2.6 | Icons | Done ahead of M2: the icon kit's `build/icon.{icns,ico,png}` are in place (§5.7). Verify the packaged `.app`, DMG, `.exe` and installer show the sloth, and that `electron-builder.yml` keeps `design/`, `site/` and `engine/` out of the app bundle |

**Exit checklist (Checkpoint A)**
- [ ] The `workflow_dispatch` run produces `SlothSpend-0.1.0-mac-arm64.dmg` and `SlothSpend-0.1.0-win-x64.exe`.
- [ ] On a real Apple Silicon Mac and a Windows x64 machine/VM: install → open (Gatekeeper/SmartScreen steps per §12.5) → Boot shows a green Engine in ≤ 20 s.
- [ ] Quit → no `slothspend-engine` in Activity Monitor / Task Manager.
- [ ] **Cut line:** if Windows isn't green by Day 1 midday, ship macOS first and treat Windows as best effort (§14).

---

### M3 — Data foundation (2 h) · user story US-2 (parse)

| # | Task | Details |
|---|---|---|
| M3.1 | `scripts/make_sample_data.py` | Uses seed `20261020`. Columns `Date,Description,Amount`, debits negative, `MM/DD/YYYY`, Nov 1 2025 → Oct 15 2026, ≈ 412 rows, **plus 2 rows with unreadable dates** (to show "2 skipped"). Merchants and amounts must produce the **golden values in §7** exactly. Write messy descriptions per merchant (e.g. `ACH DEBIT IRONTRAP FITNESS MEMB 7731`, `ECOM STREAMFLIX UHD SUBSCR #A19`, `WATCHNEST*MONTHLY 4471`, `TUNETIDE MUSIC 10/19`, `CLOUDBOX PRO ANNUAL`, `METRO ELECTRIC AUTOPAY`, `RENT TRANSFER TO OAKWOOD PROP`, `POS 4160XXXX2291 FRESHCART #112`, `BEANTHERE COFFEE 501123`) and vary them slightly from row to row. Miscellaneous dining, rides and shopping are **mostly one-off merchants**, so the findings table has 9 rows. A monthly salary credit is included. Follow-ups: `followup_cancelled.csv` and `followup_still_charged.csv` cover Oct 16 – Nov 15, 2026. Both contain TuneTide (Oct 19), WatchNest (Oct 20), Metro Electric (Oct 28), Rent (Nov 1) and noise, and **no StreamFlix** (§2 #18). Only `still_charged` has IronTrap $49.99 on Nov 5. It also writes `tests/fixtures/hdfc_style.csv` (13 preamble lines, `Tran Date, Particulars, Chq No, Withdrawal Amt., Deposit Amt., Balance`, dd/mm/yy, INR, amounts like `1,18,450.20`) and `tests/fixtures/us_signed.csv` |
| M3.2 | `scripts/make_priors.py` | Implements §11.2. Each archetype has a human `archetype` label used for "Looks like": `monthly fixed-price subscription`, `monthly subscription with a price rise`, `weekly meal kit`, `quarterly plan`, `annual plan`, `usage-based monthly SaaS`, `phone plan`, `insurance premium`, `utility bill`, `rent`, `grocery runs`, `coffee`, `dining out`, `fuel`, `rides`, `marketplace shopping`, `one-off travel`. Columns are `FEATURES + label + archetype`. It also emits `priors_hikes.csv` with `REG_FEATURES + ratio`. **It imports `app.features.series_features`**, so priors and runtime share one implementation and can't drift apart |
| M3.3 | `app/db.py` | The spec schema plus the changes in §3.1, `user_version` migration, and `PRAGMA journal_mode=WAL; foreign_keys=ON`. Each call opens a **short-lived connection** (`sqlite3.connect(DB_PATH, timeout=5)`, `row_factory=sqlite3.Row`), which is safe across `to_thread` workers. Helper signatures are below |
| M3.4 | `app/ingest.py` | Code verbatim from §7.3, plus `parse(bytes, file_name) -> Parsed` (encoding → delimiter → `detect_header` → mapping → confidence → preview), `commit(import_id, opts) -> CommitResult` (dayfirst inference, sign rules, currency, appending only rows newer than `max(tx_date)` with boundary-day rows skipped, desc_key, insert), and `report_date` = the latest tx date. `columns[]` = header cells with a suggested role (`date\|description\|amount\|debit\|credit\|type\|ignore`) for the mapper selects |
| M3.5 | `api/imports.py` | `POST /import`: compute the sha256. Same sha with `status='done'` → `{duplicate:true}`. Same sha pending → reuse that row. Otherwise insert a pending row and keep the bytes in `runtime.pending[id]`. `DELETE /import/{id}` (pending only). Confirm is wired in M4 |
| M3.6 | `api/settings.py` | `GET/PUT /settings`, backed by the `settings` table. Defaults: `{currency:"USD", chat_model:null, days_before:3, demo_compress_seconds:0}` (`null` = best installed Gemma, §2 #20) |
| M3.7 | `tests/test_ingest.py` | Per §13.1 on the three fixtures: header row (HDFC → row index 13), mapping, dayfirst, sign, row counts, 2 skipped dates; plus "a newer statement appends only later rows" and "re-import of the same sha is a no-op" |
| M3.8 | Done-notes (2026-10-21) | Built as planned, with these additions. **Fixtures:** `hdfc_style.csv` (auto-mapped Indian layout) **plus `statement_oct26.csv`**, the D-Mapper file whose `Outflow`/`Inflow` columns the mapper must ask about (use it for the M5 mapper check). **Import states:** `pending → committed` (rows stored) `→ done` (report built), so a failed audit never re-inserts rows. **Remembered layouts:** a confirmed mapping is saved under `settings['layout:<header hash>']` and reused next time (D-Mapper's "we'll remember this layout"). **Currency detection:** symbols/codes, then Indian digit grouping, then UPI/NEFT/IMPS rails, else the Settings default. **`desc_key`:** one extra pattern strips card masks inside a token (`4160XXXX2291`). **Shared features:** `features.regression_rows` / `next_step_row` live beside `series_features`, so the hikes priors and runtime regression rows share one implementation. **Postman:** `engine/postman/slothspend.postman_collection.json` (23 assertions) |

```python
# app/db.py — helpers used by later milestones
def init() -> None: ...                                   # create + migrate
def get_setting(key: str, default: str | None = None) -> str | None: ...
def get_setting_int(key: str) -> int: ...                 # 0 if unset
def set_settings(values: dict[str, str]) -> None: ...
def create_pending_import(file_name: str, sha: str, mapping: dict, currency: str, header_row: int) -> int: ...
def finish_import(import_id: int, **fields) -> None: ...  # status='done', counts, period
def imports_done() -> list[dict]: ...
def max_tx_date() -> str | None: ...
def insert_transactions(import_id: int, rows: list[dict]) -> int: ...
def debits_frame() -> "pd.DataFrame": ...                 # id, tx_date, amount, desc_key, raw_description, merchant, category, is_duplicate
def merchant_map_get(keys: list[str]) -> dict[str, dict]: ...
def merchant_map_upsert(entries: dict[str, dict]) -> None: ...
def apply_merchant_map() -> None: ...                     # UPDATE transactions SET merchant, category FROM merchant_map
def upsert_series(rows: list[dict]) -> None: ...          # ON CONFLICT(merchant)
def delete_orphan_series(keep_merchants: set[str]) -> None: ...  # never if a reminder references it
def series_by_id(sid: int) -> dict | None: ...
def user_labels_frame() -> "pd.DataFrame": ...
def save_report_meta(meta: dict) -> None: ...
def load_report() -> dict | None: ...
def save_chat(cid: str, role: str, content: str, tool_name: str | None = None, tool_args: dict | None = None) -> None: ...
def load_chat(cid: str, limit: int = 12) -> list[dict]: ...
# reminders and notifications: see M7
def wipe() -> None: ...                                   # DELETE FROM every table except settings
```

**Exit checklist**
- [ ] `python engine/scripts/make_sample_data.py && python engine/scripts/make_priors.py` regenerate byte-identical files (seeded). The CSVs are committed.
- [ ] `pytest engine/tests/test_ingest.py` is green.
- [ ] Optional: a Postman collection (`engine/postman/slothspend.postman_collection.json`, with `{{base}}` and `{{token}}` variables) covers `/health`, `/import`, `/settings`, and `postman collection run` passes against a dev engine.

---

### M4 — Audit engine and setup flows (4 h) · **Checkpoint B** · US-1, US-2, US-3, US-4 (API)

Start with a **15-minute spike** to confirm the installed `tabpfn` exposes `ModelVersion.V2`/`V3_5`/`V3_5_FAST` (already confirmed for 9.2.0: v2 downloads and runs with no key; 3.5 needs one), `create_default_for_version`, and `predict(..., output_type="quantiles", quantiles=…)`, and that the `ollama` client accepts `think=` and the tool-message field name (§7.9). Write the confirmed versions into `requirements.txt` as pins.

| # | Task | Details |
|---|---|---|
| M4.1 | `app/normalize.py` | Verbatim from §7.4, plus `async def run(keys) -> AsyncIterator[tuple[int,int]]`. Cached keys count as done immediately, then it yields after each batch of 25. **If Ollama isn't `ready`**, skip the LLM and use `rule_fallback` for every key. Add a third prompt example so rent lands in Housing: `2: "RENT TRANSFER TO OAKWOOD PROP" -> Rent, Housing, false` |
| M4.2 | `app/features.py` | Verbatim from §7.5, plus `dom_median`, `amount_varies = amount_cv > 0.05`, and `monthly_hist` (cash per calendar month) |
| M4.3 | `app/tabular.py` | §7.6 with a **version ladder** (§2 #21). `choose_version()`: `TABPFN_TOKEN` set (a stored Prior Labs key) → `V3_5` when CUDA or MPS is available, else `V3_5_FAST`; otherwise `V2`. `warm_up()` runs in a background thread: `status="downloading"` while the chosen weights aren't yet in `TABPFN_MODEL_CACHE_DIR`, then `warming`, then it builds both estimators with `create_default_for_version`, touches them once (fit/predict on 40 prior rows) and sets `ready`. A failed 3.5 attempt (`TabPFNLicenseError`, invalid key, license not yet accepted, offline) sets `upgrade={state:"failed", error}` and **falls back to V2**. If V2 can't be fetched either (first run offline) → `status="unavailable"` and the heuristic scorer until a Retry. The engine always runs with `TABPFN_NO_BROWSER=1`, so `tabpfn` never opens a browser. `model_name` ∈ `tabpfn-v2 \| tabpfn-3.5 \| tabpfn-3.5-fast` is stored as each series' `scorer`. Plus `nearest_archetypes(X) -> list[dict]`: standardise the numeric `FEATURES` with prior mean/std, take Euclidean k = 5 neighbours, majority archetype, count, runner-up. All fit/predict calls run under the lock **inside `asyncio.to_thread`** |
| M4.4 | `app/detectors.py` | Verbatim from §7.7, plus `overlap(series)`, `possible_annual(single_rows)`, `zombie(series)`, `priority(series)`. The duplicate check gets `cadence_days = median(raw intervals)` computed **before** de-duplication, because the spec's order needs the cadence first |
| M4.5 | `app/explain.py` | `reasons(series, txs, source) -> list[str]` (three lines, e.g. "Billed every ~30 days, ±1 day, near the 5th of the month." · "The same $39.99 eight times in a row, then $49.99 for the last four." · "Gemma tagged it as a kind of merchant that usually bills a plan."). Spell numbers ≤ 12 as words. Also covers irregular ("No steady rhythm: gaps range from 2 to 19 days."), single ("Charged once, on Jan 14, 2026. Could be an annual plan."), variable ("Amounts vary from $61.20 to $139.80."), and the user-label line ("You marked this as Keep.") |
| M4.6 | `app/report.py` | The pipeline orchestrator (skeleton below). Derivation rules: **recurring** = `prob ≥ 0.7` and status not in `not_subscription`/`user_cancelled`, plus `keep`. **kind**: `subscription` if the category is in the cancellable list (§7.7), `bill` if it's Utilities/Telecom/Insurance/Housing, else `other`. **next_due_date** steps by calendar (`DateOffset(months=1)` for monthly, `years=1` for annual, otherwise days) from `last_date`, rolled forward until it is after `report_date`. **fc30** sums the q10/q50/q90 of each due date in `(report_date, report_date+30d]`, for all recurring series and for subscriptions only. **monthly_equiv** = `last_amount × 30.44 / period_days`. **potential_savings** = Σ `monthly_equiv` of zombie suspects. **dispute_total** = Σ duplicate amounts. **monthly[]** covers the last 12 calendar months of recurring cash, split subs/all; the last month is `partial` when `report_date` isn't month-end; `highlights` come from months containing a duplicate, a price-creep start, or a possible-annual charge |
| M4.7 | `app/llm_summary.py` | Implements §7.8 step 8. The fact sheet is formatted with `money.py`. First sentence template: "You pay {monthly_recurring} a month in recurring charges, and {monthly_subscriptions} of that is subscriptions." The last sentence always says nothing was cancelled. Gemma rewrites it (`temperature 0.4`, `think=False`, `num_ctx 4096`). Validation: every number-like token in the output must appear in the fact sheet, otherwise use the template. Returns `(text, "gemma" \| "template")` |
| M4.8 | `api/reports.py` and `api/series.py` | `POST /import/{id}/confirm`, `POST /demo/load-sample` (reads `DATA/<file>.csv`, then the same flow), `GET /report`, `POST /report/rescore`, `GET /series/{id}`, `POST /series/{id}/label` (upserts `user_labels` with the series' `features_json`; `not_subscription` → label 0 and status `not_subscription`; `keep` → label 1 and status `keep`, which clears zombie; `subscription` → label 1 and status `active`; then `rescore`), `PATCH /series/{id}/merchant`, and `PATCH /merchant-map/{desc_key}` (spec) |
| M4.9 | Heuristic override | In heuristic mode, user labels can't move the scorer, so a labelled merchant's displayed `recurring_prob` is pinned (1.0 or 0.0) and `scorer` stays `heuristic`. In TabPFN mode, the label goes into the context ×3 (§7.6) and the model's own score is shown |
| M4.10 | `POST /setup/ollama/pull` | Wraps `AsyncClient.pull(model, stream=True)` as SSE `progress {status, completed, total}`. Accepts any `gemma*` model name (Boot offers `gemma4:e4b`; Settings may pull another) |
| M4.11 | Boot actions (D-Boot) | **Gemma row:** *unreachable* → **Install Ollama** (`openExternal("https://ollama.com/download")`) + **Retry**. *outdated* → **Update Ollama**. *missing_model* (no Gemma model installed at all) → **Download Gemma 4 (≈ 5 GB)** (`gemma4:e4b`), then a progress bar with "2.1 GB of 5.0 GB" and "About 6 min left" (rolling 10 s rate). The "8 GB of memory or less? **Use gemma4:e2b instead**" link pulls e2b instead. Any installed Gemma model counts as ready (§2 #20). **TabPFN row** (title names the version in use): *downloading* → spinner "Downloading TabPFN v2 — about 70 MB, one time, no account". *warming* → spinner "Warming up — first time only". *ready* → "Ready", plus a quiet, non-blocking **Optional upgrade** line: "Add a free Prior Labs key to use TabPFN-3.5 (non-commercial license)." → the key form (password input, **Save key**, link to platform.priorlabs.ai); never ringed, because v2 is complete on its own. *upgrade failed* → "Still using TabPFN v2: {reason}" + **Try again** / **Remove key**. *unavailable* → "Couldn't download TabPFN v2. Connect to the internet, then Retry" + **Retry** (engine restart). *error* → the message + **Retry**. The **first row needing action** gets the `box-shadow: inset 0 0 0 2px var(--ink)` ring |
| M4.12 | `src/main/secrets.ts` | **Done early (2026-10-21), along with the Boot key form (`components/shell/PriorKeyForm.tsx`).** Code below. IPC handlers: `secrets:has`, `secrets:set` (then `engine:restart`, which makes the engine try the TabPFN-3.5 upgrade), `secrets:clear` (then restart → back to v2), `prefs:telemetry:get/set` (then restart). The key **never** goes back to the renderer. `sidecars.ts` also sets `TABPFN_NO_BROWSER=1` |
| M4.13 | Tests | `conftest.py`: temp `SLOTH_DATA_DIR`, the token, and `normalize` patched to read `fixtures/sample_merchant_map.json` (canned Gemma output for every sample `desc_key`), `SLOTH_DISABLE_TABPFN=1` (heuristic, no downloads). `test_features.py` and `test_detectors.py` per §13.1. `test_report.py` asserts the **golden values in §7** through `POST /demo/load-sample`. `test_api.py` covers 401 without the token, 409 on a concurrent pipeline, and `DELETE /import` |
| M4.14 | Done-notes (2026-10-21) | Built and verified with real models (TabPFN v2 + gemma4:latest): sample audit **31.6 s**, golden values identical to the heuristic run, label re-score ≈ 2.2 s. Findings from building it: **(1) Gemma throughput** — ~68 tok/s and Ollama serves one request at a time (parallel batches gave no speed-up), so 191 keys take ~90 s. Normalisation therefore runs in **priority order** (repeating keys, then one-offs by amount) within a **30 s budget** (`SLOTH_NORMALIZE_BUDGET`) that accounts for the slowest batch; leftovers get the rule now and Gemma finishes them in the background (`normalize.finish_deferred`, which yields while an audit/re-score holds the lock — Gemma and TabPFN share the GPU). Output uses one-letter JSON keys (~⅓ fewer tokens). **(2) Rule fallback** drops card-processor prefixes (`SQ *`, `TST*`…) and keeps three words ("&" not counted) — two words merged different cafés into fake recurring merchants. **(3) TabPFN** refuses >1000 training rows on CPU: contexts are capped at 950 (hike priors sampled to 800). **(4) License safety:** `tabpfn`'s browser_auth deletes `~/.cache/tabpfn/auth_token` on a bad key and writes a good key there in plain text; `tabular.sandbox_license_cache()` redirects it to `<userData>/tabpfn-license` and disables the write (tested). **(5) "Looks like"** compares billing pattern + price (not history length) against priors of the same cadence; subscription priors now span $3.99–$79.99 log-uniform. **(6) Burn-chart highlights** = months with a duplicate or an annual-style charge; a price rise that starts that month is named in the label (so Jan + Jul, not Mar). **(7) Boot:** first launch waits on **Continue** (so the optional key form is seen); later launches skip Boot when everything is ready (`localStorage['sloth.setupDone']`). Schema v2 adds `series.quantiles_json`. |

```python
# app/report.py — orchestrator skeleton
STAGES = ("parse", "normalize", "detect", "features", "score", "forecast", "flags", "summary", "done")

def _ev(name: str, **data) -> dict:
    return {"event": name, "data": json.dumps(data)}

async def start_pipeline(import_id: int, opts: dict) -> asyncio.Queue:
    """Runs to completion even if the SSE client disconnects (§3.4)."""
    if runtime.pipeline_lock.locked():
        raise HTTPException(409, "An audit is already running.")
    q: asyncio.Queue = asyncio.Queue()
    async def job():
        async with runtime.pipeline_lock:
            try:
                await q.put(_ev("stage", stage="parse", done=0, total=1))
                res = await asyncio.to_thread(ingest.commit, import_id, opts)
                await q.put(_ev("stage", stage="parse", done=1, total=1,
                                note=f"{res.rows} rows · {res.skipped} skipped (unreadable dates)"))
                async for done, total in normalize.run(await asyncio.to_thread(db.unmapped_debit_keys)):
                    await q.put(_ev("stage", stage="normalize", done=done, total=total))
                ctx = await asyncio.to_thread(Context.load)       # debits + map + labels + report_date
                for name, fn in (("detect", detect), ("features", features), ("score", score),
                                 ("forecast", forecast), ("flags", flags)):
                    await q.put(_ev("stage", stage=name, done=0, total=1))
                    await asyncio.to_thread(fn, ctx)
                    await q.put(_ev("stage", stage=name, done=1, total=1))
                await q.put(_ev("stage", stage="summary", done=0, total=1))
                ctx.summary, ctx.summary_source = await llm_summary.write(ctx.facts())
                await q.put(_ev("stage", stage="summary", done=1, total=1))
                await q.put(_ev("stage", stage="done", done=0, total=1))
                await asyncio.to_thread(persist, ctx, import_id)  # series upsert, report_meta, sync WATCHING reminders
                verified = await reminders.verify_after_import()
                await asyncio.to_thread(db.finish_import, import_id, verified_count=verified)
                await q.put(_ev("done", report=await asyncio.to_thread(db.load_report)))
            except Exception as exc:
                log.exception("pipeline failed")
                await q.put(_ev("error", stage="pipeline", message=str(exc)))
            finally:
                await q.put(None)
    asyncio.create_task(job())
    return q

async def rescore() -> dict:   # label / merchant edit / TabPFN became ready — no LLM, ≤ 5 s
    async with runtime.pipeline_lock:
        ctx = await asyncio.to_thread(Context.load)
        for fn in (detect, features, score, forecast, flags):
            await asyncio.to_thread(fn, ctx)
        ctx.summary, ctx.summary_source = llm_summary.template(ctx.facts()), "template"
        await asyncio.to_thread(persist, ctx, None)
        return await asyncio.to_thread(db.load_report)
```

`persist()` also **syncs reminders in WATCHING/SNOOZED**: if a series' `next_due_date` changed, update the reminder's `next_due_date` and recompute `remind_at` (compare-and-set). It must **not** touch `AWAITING_STATEMENT` rows, because verification needs the original renewal date. `verify_after_import()` returns how many reminders it moved to a final phase (stored as `verified_count`).

```ts
// src/main/secrets.ts
import { app, safeStorage } from "electron";
import fs from "node:fs";
import path from "node:path";

interface Prefs { priorKey?: string; telemetry?: boolean }
const file = () => path.join(app.getPath("userData"), "prefs.json");
const read = (): Prefs => { try { return JSON.parse(fs.readFileSync(file(), "utf8")); } catch { return {}; } };
const write = (p: Prefs) => fs.writeFileSync(file(), JSON.stringify(p), { mode: 0o600 });

export function setPriorKey(key: string): void {
  if (!safeStorage.isEncryptionAvailable()) throw new Error("OS encryption is unavailable");
  write({ ...read(), priorKey: safeStorage.encryptString(key.trim()).toString("base64") });
}
export const hasPriorKey = (): boolean => Boolean(read().priorKey);
export function clearPriorKey(): void { const { priorKey: _drop, ...rest } = read(); write(rest); }
export const getTelemetry = (): boolean => read().telemetry === true;
export function setTelemetry(on: boolean): void { write({ ...read(), telemetry: on }); }

export function secretsEnv(): Record<string, string> {
  const p = read();
  const env: Record<string, string> = { SLOTH_TELEMETRY: p.telemetry ? "1" : "0" };
  if (p.priorKey) {
    try { env.TABPFN_TOKEN = safeStorage.decryptString(Buffer.from(p.priorKey, "base64")); }
    catch { /* unreadable on this machine: treat as missing */ }
  }
  return env;
}
```

Removing the key leaves the downloaded weights in place, so TabPFN keeps working offline. Settings says so (M8).

**Exit checklist (Checkpoint B)**
- [ ] `pytest engine/tests` is green, including `test_report.py` golden values in heuristic mode.
- [ ] With Ollama + an installed Gemma model and **no key**: TabPFN v2 downloads on first launch, then `/demo/load-sample` completes in ≤ 60 s on Apple Silicon with scorer `tabpfn-v2`. After saving a Prior Labs key the engine restarts on `tabpfn-3.5`; removing the key returns to `tabpfn-v2`. Merchant names look like §7. IronTrap has `price_creep +25.0 %` since Jul 5 and `duplicate Jul 5/6`.
- [ ] `POST /series/{IronTrap}/label {"label":"not_subscription"}` returns in ≤ 5 s and persists across an engine restart.
- [ ] From the Boot screen: pulling Gemma shows progress, saving the key restarts the engine, and TabPFN goes `warming → ready`.

---

### M5 — Audit UI (3.5 h) · **Checkpoint C** · US-2, US-3, US-4

The Audit tab is a state machine in `store.ts`: `empty → mapping → running → report` (plus `error`). On load: `GET /report` returning 404 → `empty`, 200 → `report`.

| # | Task | Design | Details |
|---|---|---|---|
| M5.1 | `ImportEmpty` | D-Import | A pink section (radius 48, padding 16) with a dashed 2 px ink inner border (radius 36). Upload icon in a 64 px raised circle. Headline "Drop a bank statement here." and the 20 px lead. Buttons: **Choose CSV file** (solid lg, hidden `<input type=file accept=".csv,text/csv">`), **Load sample statement** (outline lg), **Demo data ▾**, and the lock line. The whole section is the drop target: highlight it with a `--accent-edge` 3 px ring while dragging. `document` swallows `dragover`/`drop` so a dropped file never navigates away. Below it: "How it works" (4 panel cards: Audit / Ask / Remind / Verify, with Archivo numerals) and the never-cancels line |
| M5.2 | `DemoDataMenu` | D-Import, D-Main | Items: *Sample statement (12 months)*, *Follow-up: IronTrap cancelled*, *Follow-up: IronTrap still charged*. The follow-ups are disabled until a report exists. Each calls `stream("/demo/load-sample", {file})` |
| M5.3 | `ColumnMapper` | D-Mapper | Card (radius 32): h1 "Help SlothSpend read this file", a sub-line generated from what is missing, a file chip "Header on row {n} · {n} preamble lines skipped", required-column chips (`found` = success check, `set by you` = accent, `missing` = outline), **Currency** select ("INR — ₹ (detected)"), **Date order** select ("Day first — 20/10/26" / "Month first — 10/20/26"), and a "Debits are positive" checkbox with a helper line. The preview table puts a header label and a role `<select>` in each `<th>`, and scrolls horizontally inside its box. **Run audit** is enabled once date + description + (amount or debit) are mapped. **Cancel** → `DELETE /import/{id}` → `empty`. The aside shows "Waiting on the columns." |
| M5.4 | `PipelineProgress` | D-Progress | Card: "{file} · {rows} rows", h1 "Reading your statement.", "Slowly and carefully, on this computer. Usually under a minute.", an `m:ss elapsed` timer, the overall bar (`aria-valuetext` "Step 2 of 9: cleaning merchant names"), and 9 rows. Labels: parse→**Read rows**, normalize→**Clean merchant names** (`Gemma 4 · local`), detect→**Find double charges**, features→**Measure billing patterns**, score→**Score recurring charges** (`TabPFN-3.5`), forecast→**Forecast the next 30 days** (`TabPFN-3.5`), flags→**Flag price rises and overlaps**, summary→**Write the summary** (`Gemma 4 · local`), done→**Save the report**. The model chip shows the actual source (`Heuristic`/`Template` in limited mode). Dots: done = solid ✓, current = accent + edge, todo = faint ring. The current row (raised background) shows sub-progress: "Gemma cleaned {done} / {total} merchants". The aside shows "Reading along with you." with a disabled input |
| M5.5 | `StatementBar` | D-Main | Card row: file icon, latest import name, "{rows} rows · {period} · {currency} · 🔒 Your statement never leaves this computer.", **Import newer statement** (soft), **Demo data ▾** |
| M5.6 | `SummaryNarrative` and `SummaryCards` | D-Main | The pink summary card (radius 32): "Sloth's summary" + `SourceChip`, `lead` text. A 4-card grid (`repeat(auto-fit,minmax(260px,1fr))`): **Monthly recurring** ("{subs} subscriptions · {bills} bills"); **Next 30 days** (`TabPFN-3.5` chip, q50, "Likely {q10} – {q90} (q10–q90)" with the conservative-band tooltip from §7.6); **Potential monthly savings** (the `solid` card, "If you cancel the {n} zombie suspects yourself — plus a {dispute} double charge to dispute."; the dispute clause is dropped when it's 0); **Flags** ("{n} on {m} merchants" + count chips in the flag chip styles) |
| M5.7 | `FindingsTable` and `FindingRow` | D-Main | Header "Findings", "Sorted by priority · recurring scores from [SourceChip]". Filters (`aria-pressed`): **All n / Flagged n / Subscriptions n / Bills n**. Grid columns `minmax(170px,2.2fr) minmax(88px,1fr) 72px 100px minmax(150px,1.7fr) 64px 44px` inside a horizontal scroll with `min-width:740px`. **Sort:** recurring rows first by priority desc, then the rest by prob desc. **`cadence_label`:** `Monthly`, `Monthly · bill`, `Weekly`, `Once a year?` (possible annual), `Irregular`. **`change_label`:** `+25.0%` (creep, bold with a trending-up icon), `Varies` (bill with `amount_varies`), `—`. **Recurring:** a 48 px bar + `98%`, or "1 charge". **Flags:** chips with icons (`Duplicate · Jul 5/6`, `Price +25%`, `Overlap`, `Zombie suspect`, `Possible annual` + `Low confidence`) or `—`. **Next due** in short form. Clicking the merchant name opens the drawer. **More actions** expands the row (panel background, radius 16) with: **How to cancel** (solid; opens the drawer scrolled to `#how-to-cancel`) for `cancellable`, or **Draft negotiation email** for bills · **Remind me** (`POST /reminders`, then a toast "Reminder set for {date}") · **Keep** · **Not a subscription** (or **It's a subscription** when prob < 0.5) · **Ask Sloth** (pre-fills chat with "Why was {merchant} flagged?" or "Tell me about {merchant}."). Footer note about bills and drafts. Rows with status `not_subscription` render muted with an outline "Not a subscription" chip |
| M5.8 | `BurnChart` | D-Main | Title "Monthly subscription spend", "Last 12 months, plus next month's forecast". Toggle **Subscriptions / All recurring** (`role=group`, `aria-pressed`). Y-axis has 5 gridlines at nice steps (`niceMax = ceil(max*1.1 / step) * step`). Bars are `--ink`; highlighted months use `--accent` with a 1.5 px `--accent-edge` border; the partial month gets a hatched top (`repeating-linear-gradient` with `--card`). Labels show only above highlighted bars and the last bar. The forecast column (8 px gap) has a dashed stem, a q10–q90 box (`--tint`, 1.5 px ink border) and a 12 px ink dot with a value label. The legend lists `highlights`. The chart is one `role="img"` with a generated `aria-label` sentence (as in the design), and each bar has a `title` tooltip |
| M5.9 | `MerchantDrawer` | D-Drawer | Rendered as a `Sheet`. Header: "Merchant" caption, h2 name, close button. Chips: category, cadence ("Monthly · near the 5th"), flags. **Score card:** "Recurring 98%" + source chip + bar, and the **Keep / Not a subscription** buttons (`label`; the drawer refreshes and the table re-renders from the returned report). **Charges:** `ChargeBars` (one bar per tx, height ∝ amount, duplicate in accent, previous price `--subtle`, current price `--ink`, month ticks every other bar), "{n} charges · {range}", and `reasons[]` as bullets. **Looks like:** 5 dots (filled = count), archetype, "{count} of 5 nearest examples", the runner-up sentence, and "Examples are simulated histories SlothSpend learned from, not other people's data." **Next charge** (+ chip): Due · Most likely · Range (q10–q90) · Price-rise chance (≈, with the tooltip from §7.6), and a `RangeStrip` (axis = round(q10·0.8) … round(q90·1.2), band q10–q90, dot q50). **Why it's flagged:** one card per flag with its icon in a 36 px circle. The duplicate card gets **Draft refund request** (M6). **Merchant details:** Name input, Category select (all 21 categories), **Save** → `PATCH /series/{id}/merchant`, and the note "Seen in your statement as “{raw}”. Your edits win over Gemma's and re-score in a few seconds." **How to cancel / Negotiate:** the section shell is laid out here and wired in M6 and M7 |
| M5.10 | Re-score banner | — | If `meta.scorer == "heuristic"` and `/health` now reports TabPFN `ready`: a card banner "{TabPFN v2 / TabPFN-3.5} is ready. **Re-score with TabPFN**" (also shown after a v2 → 3.5 upgrade, so existing reports pick up the better model) → `POST /report/rescore` |
| M5.11 | `lib/ui-derive.ts` and unit tests | — | Pure functions: `cadenceLabel`, `changeLabel`, `flagChips`, `filterCounts`, `sortFindings`, `niceAxis`, `phaseView` (M7). Vitest specs for each, using the §7 golden fixture JSON |
| M5.12 | Done-notes (2026-10-21) | — | Built and verified in the dev app with real models (gemma4:latest, TabPFN v2) on a fresh DB with Gemma cold: the sample audit takes **27 s** and every §7 golden value matches (10 flags on 5 merchants, Jan $196.34 + Jul highlighted, Oct partial and hatched). `statement_oct26.csv` → mapper with INR + day-first detected → Outflow/Inflow as Debit/Credit → report in ₹ (19 s); `hdfc_style.csv` is detected without the mapper. Not a subscription on StreamFlix re-scores in **3.9 s**; rename Metro Electric → City Power in **3.0 s** (reason "You set this merchant’s name and category."); both survive an app restart. Esc closes the drawer and focus returns to the merchant button. Findings from building it: **(1) Cold-start normalisation** — on a fresh DB with Gemma unloaded, only one batch fit the 30 s budget and the single "CLOUDBOX PRO ANNUAL" charge kept the rule name (not subscription-like), so the possible-annual finding was missing until the next audit. `normalize.prioritise` now puts plan-worded keys (`ANNUAL`, `YEARLY`, `SUBSCR`, `MEMB`, `RENEW`) in the first tier with the repeating keys (tested). **(2) Label spill-over (open question)** — with labels in the TabPFN context ×3 (M4.9), Not a subscription on StreamFlix also lowers WatchNest (100 % → 67 %, below the 0.7 threshold) and TuneTide (→ 80 %), because their features are nearly identical. **(3) UI:** `Hint` is focusable with a CSS tooltip (native `title` wasn’t keyboard-reachable); the burn-chart legend shortens a month with > 2 highlights to “a, b and N more”; Next 30 days says “Nothing recurring is due yet” at $0 instead of “no forecast model yet”. Remind me, Ask Sloth, drafts and I cancelled it are laid out and disabled with “Coming in the next update” (M6/M7); Settings stays disabled until M8 |

**Exit checklist (Checkpoint C)**
- [ ] Drop `tests/fixtures/statement_oct26.csv` → the mapper appears with INR and day-first detected (and `hdfc_style.csv` imports without it) → Run audit → progress → report in ₹ with Indian grouping.
- [ ] Load the sample → the report matches D-Main's structure and the §7 golden values. The October bar is drawn as partial.
- [ ] Not a subscription on StreamFlix → the row, cards and chart update in ≤ 5 s. Overlap disappears from WatchNest. This survives a restart.
- [ ] Rename "Metro Electric" → "City Power" in the drawer → the table updates and the reasons say "You set this merchant's name".
- [ ] Both themes match the light and dark artboards. Keyboard: Tab reaches every control; Esc closes the drawer and focus returns to the row.

---

### M6 — Ask Sloth and drafts (3 h) · US-5, US-6

| # | Task | Details |
|---|---|---|
| M6.1 | `app/tools.py` | Eight tools per the §7.9 table. `SCHEMAS` uses Ollama's function format (`{"type":"function","function":{"name","description","parameters":{JSON Schema}}}`) with short descriptions that say when to use each tool. `execute(name, args)` checks the arguments, runs blocking work in `asyncio.to_thread`, returns JSON truncated to 4,000 chars, and always returns `{"error": …}` instead of raising. `get_merchant` fuzzy-matches with `difflib.get_close_matches(cutoff=0.5)` over merchant names and their lowercase first tokens. `forecast_spend` re-runs the **live** regressor on the selected series and returns `{baseline: Q, scenario: Q, delta_q50, excluded: [...], window: [start, end]}`. `score_merchant` re-fits the classifier with the current labels and returns `{prob, features, similar}`. `run_readonly_sql` is verbatim from §7.9. `set_renewal_reminder` calls `reminders.create(series_id, days_before)` (M7; until then it returns `{"error":"reminders arrive in M7"}`). `overview_block()` is ≤ 1,200 chars: currency, report date, the 4 card numbers, and the top 10 findings as `merchant · category · cadence · last amount · flags · next due`. `prefetch_context(text)` is per §7.9 |
| M6.2 | `app/agent.py` | Verbatim from §7.9, with one more `SYSTEM_PROMPT` rule: *"Put any email draft in a fenced code block whose first line starts with 'Subject:'. Nothing else goes in that block."* Ollama unreachable → one `error {message:"Gemma isn't running. Start Ollama, then try again."}` event. Persists via `db.save_chat` |
| M6.3 | `app/drafts.py` | `POST /series/{id}/draft {kind}`: facts come from `db.series_facts` and the flag details; the prompt per kind (`cancel_request`, `refund`, `negotiate`) applies §7.9's tone rules and forbids links and phone numbers. Streams tokens. The **template fallback** (no Ollama) produces the exact shape shown in D-Drawer and D-Reminders (Subject line, greeting, facts paragraph, request, "Thank you,\n[Your name]"). A `refund` draft covers the latest still-charged charge (from the reminder) **and** any duplicate pairs |
| M6.4 | `api/chat.py` | `POST /chat` (SSE) and `GET /chat/{cid}` (assistant and user messages plus collapsed tool records). `conversation_id` is kept in `localStorage["sloth.cid"]`; **New conversation** creates a fresh UUID |
| M6.5 | `ChatPane` (D-Main aside) | Header: avatar, "Ask Sloth", `Gemma 4 · local`, **New conversation**. A message list (`<ol aria-label="Conversation">`, `aria-live="polite"` on the streaming bubble). User bubbles: `solid`, radius `16 16 4 16`, right-aligned, max 85 %. Assistant bubbles: `raised`, radius `16 16 16 4`, rendered with `react-markdown` + `remark-gfm`, and a blinking 8×16 caret while streaming |
| M6.6 | `ToolBadge` | A `<details>` whose summary is a pill: wrench + `<code>name(args)</code>` + "· 42 ms" (or "· 1.4 s"). It expands to a `<pre>` with `preview`. Next to `forecast_spend` and `score_merchant` badges goes the `TabPFN-3.5 · live` chip (or `Heuristic · live`). Arguments render Python-style: positional for the first string argument, `key=value` for the rest, as in the design |
| M6.7 | `DraftCard` | Fenced blocks starting with `Subject:` render as a card: title ("Refund request", "Cancellation request" or "Negotiation email", inferred from the subject), **Copy** (`navigator.clipboard.writeText`, with a "Copied" state), a bold subject line, and `white-space:pre-line` body. A `Gemma 4 · local` or `Template` chip. Footer: "Check the dates and amounts, then send it yourself." |
| M6.8 | `FollowUps` | Client-side buttons under the final assistant bubble of a turn, derived from that turn's tool calls and the cached report. A merchant with a `duplicate_charge` or `STILL_CHARGED` gets **Draft refund request**. A cancellable merchant without a reminder gets **Remind me {days_before} days before**. A bill gets **Draft negotiation email**. Clicking one sends the matching suggested prompt. `set_renewal_reminder` results render a "🔔 Reminder set for {date}" link-chip (BellPlus icon) that switches to the Reminders tab |
| M6.9 | `PromptChips` and `ChatInput` | "Try asking" shows the §7.9 prompts not yet used in this conversation (max 3). Before any report: dashed, disabled chips under "You'll be able to ask" (D-Import). The input is a pill, 44 px, with a visually hidden label and placeholder "Ask about your charges…". Enter sends, Shift+Enter adds a newline, and it's disabled while streaming. Footer: "Runs on this computer. Sloth never cancels or contacts anyone for you." |
| M6.10 | Drawer drafts | **How to cancel** (`#how-to-cancel`, panel card, radius 24): h2, "You do these steps. SlothSpend does none of them for you.", the 5 static steps (§9.2 copy exactly), **Draft cancellation request** → a `DraftCard` streamed from `/series/{id}/draft` with **Copy** and **Draft cancellation request again**. Bills get a **Negotiation email** section with the same mechanics. The duplicate flag card's **Draft refund request** streams into a `DraftCard` inside that flag card |
| M6.11 | Tests | `test_agent_tools.py` covers every tool against the sample DB (heuristic): `get_merchant("irontrap")` resolves; `find_duplicate_charges` returns Jul 5/6; `forecast_spend(exclude=["StreamFlix UHD","WatchNest"])` gives `delta_q50 ≈ -25.48`; `run_readonly_sql` rejects `DELETE`, `;`-chained statements and PRAGMA writes, and caps at 50 rows. Drafts: the template output for each kind contains no `http` and no digit runs that look like phone numbers |
| M6.12 | Done-notes (2026-10-22) | Built and verified in the dev app with gemma4:latest and TabPFN v2 on the sample. All 5 suggested prompts answer with visible tool badges and report-matching numbers (≈ 4–16 s each): IronTrap's three flags and the Jul 5/6 double charge; the what-if via `forecast_spend` with the **TabPFN v2 · live** chip ($87.46 → $61.98, −$25.48); category growth via `spend_by_category`; the refund draft card; the reminder. "Cancel IronTrap for me" → can't-cancel explanation, a reminder offer and the cancellation-request draft, no links or numbers. Drawer drafts stream from Gemma (cancel 8 s, refund 2.5 s, negotiation 3 s); with Ollama unreachable (`OLLAMA_HOST` pointed at a closed port) they fall back to the template in < 1 s and chat says "Gemma isn't running. Start Ollama, then try again." Findings from building it with a 4B model: **(1) Pre-fetch shows as a badge** — Gemma answers from the pre-fetched facts and often skips tools, so each pre-fetch is a real `get_merchant` call emitted as `tool_start`/`tool_end` and stored like any tool record. **(2) Tool output in the UI's words** — flags as "double charge / price rise…", ISO dates as "Jul 6, 2026" (Gemma echoes what it's given). **(3) `forecast_spend` takes `scope`** (`subscriptions` default, or `all`) and returns one scope: with both scopes in one result Gemma quoted bills for a subscriptions question. **(4) Actions are never trusted to the model** — "remind me …" runs `set_renewal_reminder` in the pre-fetch (the user's own instruction; it only reminds), and an answer that claims a reminder no tool confirmed is replaced with the tool's real result (`guard.claims_reminder`); Gemma claimed "I've set a reminder" in 3 of 4 runs before this. Until M7 the tool returns `reminder_set: false`. **(5) Draft requests start from the code template** (`agent.draft_kind`; "what if I cancel" is a forecast, not a request), so chat drafts carry exact facts. **(6) Safety net** — `guard.scrub` replaces links, email addresses and phone numbers in answers (sent as a `replace` event) and Gemma drafts containing any are rejected for the template. Remind me / I cancelled it / the reminder-set chip stay for M7 |

**Exit checklist**
- [ ] All 5 suggested prompts (§7.9) answer with ≥ 1 visible tool badge and numbers that match the report. The what-if uses `forecast_spend` and shows the live chip.
- [ ] "Cancel IronTrap for me" → a plain explanation that SlothSpend doesn't cancel, plus a reminder offer and a cancellation-request draft, with **no links or phone numbers** (DoD 4).
- [ ] With Ollama stopped, the drawer drafts still work (Template chip) and chat shows the friendly error.

---

### M7 — Reminders and notifications (2.5 h) · **Checkpoint D** · US-7, US-8

| # | Task | Details |
|---|---|---|
| M7.1 | `app/reminders.py` | Verbatim from §7.10, plus: **`tick()` runs once immediately at startup** (the catch-up), then every 30 s. `create(series_id, days_before=None)` → `WATCHING`. It returns 400 when the series has no `next_due_date`. `remind_at` = demo ? now + N s : `renewal_at(next_due) − days_before`, clamped to ≥ now. `verify_after_import()` returns the number of rows it moved to a final phase |
| M7.2 | `db` helpers | `transition(sid, expect, new_phase, **fields) -> bool` is a compare-and-set `UPDATE … WHERE series_id=? AND phase=?`. It builds the `SET` list from the given fields, always sets `updated_at`, and appends `{"phase","at"}` to `events_json` with `json_insert(events_json,'$[#]',json_object(...))` when the phase changes. Also `due_reminders(now_iso)` (active phases and `remind_at <= now`), `reminders_in_phase(p)`, `charges_after(sid, after_iso)` per §7.10, `series_facts(sid)`, `list_reminders()` (joined with the derived fields from §3.2), `insert_notification`, `notifications_since(id)`, `notifications_all(limit=50)`, `mark_read(id)`, `mark_all_read()` |
| M7.3 | `app/notes.py` | `gemma_note(kind, facts)` uses structured output `{"title","body"}`, `temperature 0.4`, `think=False`, and the §7.10 rules. Validate: no `http`, no `www.`, no phone-like pattern, body ≤ 3 sentences, and every number appears in the facts. Otherwise raise, which makes the caller retry and then fall back. `template_note(kind, facts)` covers the three kinds: reminder ("{m} renews {date} for {amt}. If you no longer use it, open How to cancel in SlothSpend — or tap Keep it."), verified ("No {m} charge on your statement through {covers_until}. You're saving {amt} a month."), still_charged ("{amt} on {date}, after you cancelled on {cancelled_on}. A refund request is ready to draft.") |
| M7.4 | `api/reminders.py` and `api/notifications.py` | Per §8 plus §3.2. Each action route maps a compare-and-set failure → 409 `{phase}`. `/cancelled` with no existing row creates one directly in `AWAITING_STATEMENT` and sets `series.status='user_cancelled'`. **Allowed-from rules:** §7.10's table, where "active" = `WATCHING, REMINDED, SNOOZED, AWAITING_STATEMENT, STILL_CHARGED`. "Remind me" from a final phase (`KEPT, EXPIRED, STOPPED, VERIFIED_STOPPED`) resets the row. A 4th snooze → 409 |
| M7.5 | `NotificationBell` and `lib/notify.ts` | Polls `GET /notifications?since_id={last}` every 5 s once the workspace is open. For each new notice: add it to the store, increase the unread badge (an accent dot with a count, `aria-label="Notifications, {n} unread"`), and raise `new Notification(title, {body, silent:false})`. On click: `window.sloth.focusWindow()` + open the Reminders tab + mark it read. `localStorage["sloth.lastToastId"]` stops a notice being raised twice after a reload. Catch-up notices created right after launch have new ids, so they do raise |
| M7.6 | `NotificationInbox` (D-Notif) | A popover under the bell: "Notifications" h2 + **Mark all read**, then a list of links (whole row clickable, 44 px+). Icon circle by kind: reminder = bell on tint, verified = check on success-tint, still_charged = triangle-alert, with the **whole row on accent** (forced light). Title + relative time, body, and an unread dot (`aria-label="Unread"`). Footer: "Reminders fire while SlothSpend is open." Esc or an outside click closes it |
| M7.7 | `RemindersPanel` (D-Reminders) | The tab shows the "**{n} need you**" accent pill when `needs_you > 0`. Then: an info banner "Reminders fire while SlothSpend is open. If it was closed, you'll get them the next time you open it."; the `LatestStatement` card ("{file} · {period}", "Imported {relative} · checked {verified_count} cancelled subscriptions", **Import newer statement**); groups **Needs you**, **Watching**, **Done** (each heading shown only when non-empty); and an empty state, "No reminders yet. Open a finding and choose **Remind me**." |
| M7.8 | `ReminderCard` and `PhaseStepper` | Driven by `phaseView(reminder)` in `ui-derive.ts`, using the table below. Full cards (Needs you, Done-verified) show the 4-step stepper. Compact cards (Watching) show one row: name, "{amt} a {period} · renews {date} · {n} days left", the "We'll remind you on {remind_on}, {N} days before it renews." line, and the buttons. `low_confidence` adds the dashed chip and "It only charged once, so this date is a guess." |
| M7.9 | Drawer wiring | **Cancelled on** date input (default = today, or **report_date + 1 day** when the latest import is the bundled sample), **I cancelled it** (solid lg) → `/reminders/{id}/cancelled` → toast + the Reminders tab, **Remind me before renewal** (outline lg), and the footer lock line "SlothSpend never cancels or contacts anyone for you." |
| M7.10 | Demo compression | When `demo_compress_seconds > 0`, every wait (remind_at, answer-by, the 60-day expiry) uses N seconds (§7.10). The Watching card shows "(demo: {N} s)" |
| M7.11 | `tests/test_reminders.py` | Every case listed in §13.1, plus: `events_json` records each transition; `persist()` re-syncs a WATCHING row whose due date moved but leaves AWAITING_STATEMENT alone |
| M7.12 | Done-notes (2026-10-22) | Checkpoint D verified in the dev app (gemma4:latest, TabPFN v2). **(1)** Demo 30 s: Remind me on IronTrap → quit while WATCHING → relaunch after it came due → the notice was written on the engine's first tick and raised by the window (`sloth.lastToastId` = 1, permission granted); bell "1 unread", tab "1 needs you". **(2)** Ollama unreachable (`OLLAMA_HOST` on a closed port): the log shows the three retries (5/10/20 s), then the template note arrives. **(3)** I cancelled it (drawer default Oct 16) → *Follow-up: IronTrap cancelled* → Verified card + notice; after a fresh DB, *still charged* → the accent Still-charged card + notice, and **Draft refund request** gives the D-Reminders draft (Nov 5 charge after the Oct 16 cancellation, plus the July double charge). **(4)** Snooze cap: snoozing is allowed while fewer than 3 reminders have been sent (spec §7.10 table), so it is reminder 1 → snooze → 2 → snooze → 3, then the Snooze buttons hide and the API answers 409 "That was the last of 3 reminders…". The checklist's "Snooze ×3, then a 4th" would mean 4 reminders, which contradicts "max 3" and "Reminded · n of 3"; the table wins. Findings: **(a) Statement checks don't wait for Gemma** — `verify_after_import` moves the phase inside the import and drafts the note in the background, so a down Ollama (35 s of retries) never stalls an import. **(b) Notes need narrow facts** — with every fact available Gemma wrote "This is your monthly saving" on a reminder and "the last charge was on Oct 16" (the cancellation date) on a verified note; each kind now gets only its own facts under self-describing names (`statements_checked_through`, `user_cancelled_on`…) and rephrases the template. **(c)** `/cancelled` also marks the series `user_cancelled` and re-scores, so the report drops it at once ($1,979.86 → $1,929.87). A statement loaded while that re-score runs gets the usual 409. **(d)** `GET /reminders` adds `checked` (the charge after cancelling, or how far statements reach) for the Still-charged / Verified copy; 409s explain themselves per phase. **(e)** The poller resets `lastToastId` when the inbox's newest id is lower (data was wiped), verified after a fresh DB. Ask Sloth's `set_renewal_reminder` now creates real reminders ("Reminder set for …" chip); an in-progress one returns `reminder_set: false` and the M6 claim guard still applies |

**Phase → UI mapping**

| Phase | Group | Header badges | Stepper (Watching → Reminded → Kept / You cancelled → Verified / Still charged) | Buttons |
|---|---|---|---|---|
| `WATCHING` | Watching (compact) | `{n} days left` (accent) when ≤ 7 | — | Keep it · I cancelled it · Stop |
| `SNOOZED` | Watching (compact) | `Snoozed · {sent} of 3` | — | Keep it · I cancelled it · Stop |
| `REMINDED` | **Needs you** (card) | `{n} days left` (accent) · `Reminded · {sent} of 3` (outline) | ✓ date · **current** "Today" · todo · todo | I cancelled it · Keep it · Snooze 1 d · Snooze 3 d (hidden at 3 sent) · How to cancel · Stop |
| `AWAITING_STATEMENT` | Watching (card) | `Waiting for your next statement` (tint) | ✓ · ✓ or **skip** "Skipped" · ✓ "You cancelled · {date}" · todo | Import newer statement · Stop |
| `STILL_CHARGED` | **Needs you** (accent card) | `Still charged` (solid, triangle) | ✓ · ✓/skip · ✓ · **alert** "Still charged · {date}" | Draft refund request (solid; sends the refund prompt to Ask Sloth) · How to cancel · Stop |
| `VERIFIED_STOPPED` | Done (outlined card) | `Verified` (success) | ✓ · ✓/skip · ✓ · **ok** "Verified · {date}" | — (copy: "No {m} charge through {date}, after its {due} renewal. **You're saving {amt} a month.**") |
| `KEPT` | Done (compact) | `Kept` (tint) | — | Remind me again |
| `EXPIRED` | Done (compact) | `Expired` (outline) | — | Remind me again (copy = `detail`) |
| `STOPPED` | Done (compact) | `Stopped` (outline) | — | Remind me again |

**Exit checklist (Checkpoint D)**
- [ ] Demo mode at 30 s: **Remind me** on IronTrap → quit while it's WATCHING → relaunch → the OS notification arrives on the first tick, and the inbox shows it unread.
- [ ] With Ollama quit, the reminder still arrives with the template text, and the engine log shows the 3 retries.
- [ ] **I cancelled it** (Oct 16) → load *Follow-up: IronTrap cancelled* → a **Verified** card and notification. After Delete all local data (M8, or `wipe()` until then), the still-charged follow-up gives a **Still charged** accent card and **Draft refund request** produces the D-Reminders draft.
- [ ] Snooze 1 d ×3, then a 4th is rejected (the button is hidden; the API returns 409).

---

### M8 — Settings and privacy (1.5 h) · US-9

| # | Task | Details |
|---|---|---|
| M8.1 | `SettingsModal` (D-Settings) | Opened from the top bar's sliders button, with a scrim over the workspace. h2 "Settings" + close. Sections, in order: **Appearance** (a segmented control Light / Dark, plus "System" as a third option; copy "Also in the top bar. SlothSpend starts in your computer's setting until you pick one."); **Models** (Chat model radios: **Automatic** "Use the best Gemma model installed ({model})" plus one radio per entry in `/health` `available_models`; picking one saves `chat_model`. If no Gemma model is installed, an inline **Download gemma4:e4b** button with progress via `/setup/ollama/pull`. **TabPFN**: "Using TabPFN v2 (open weights)" or "Using TabPFN-3.5". Key status: "Not set — optional" with **Add key** ("Upgrade to TabPFN-3.5 with a free Prior Labs key; non-commercial license"), or "Saved · encrypted on this computer" with **Replace key** / **Remove** ("SlothSpend goes back to TabPFN v2"). A failed upgrade shows its reason here too); **Statements** (Default currency select + helper); **Reminders** (days-before stepper − [n] + in 1–14; **Demo mode** switch with a `For demos` chip and the "Compress waits to [30] seconds" field, range 5–600, shown when on); **Privacy** (the **Share performance traces** switch, default off, via IPC → engine restart; the "Where your data goes" table, below); **Delete all local data** (`danger` button → confirmation modal "Delete everything SlothSpend stored on this computer? Statements, merchant edits, chats and reminders. Model downloads stay." → `DELETE /data`, clear `sloth.cid` and `sloth.lastToastId`, reset the Audit tab to `empty`); **Done** |
| M8.2 | `EgressTable` | Copy the 7 rows from §3.3 using the design's wording, with the TabPFN weights row split in two: **TabPFN v2 weights** → `Internet · one time` · Hugging Face · first run · automatic; **TabPFN-3.5 weights** → `Internet · one time` · Prior Labs (license check) + Hugging Face · only after you add a key · off. The *Goes to* column shows a chip: `This computer` (success-tint), `Internet · one time` (tint), `Internet · opt-in` (outline), then the destination on a second line. Closing line: "After the one-time model downloads, SlothSpend makes no network calls at all unless traces are on." |
| M8.3 | Save behaviour | Engine settings `PUT` on change (debounced 400 ms), with an "Saved" caption in the section. Telemetry and key changes restart the engine; the top-bar pills show *Starting…* until `/health` is ok again. Theme is applied instantly |
| M8.4 | `api/admin.py` | `DELETE /data` → `db.wipe()`, cancel any pending import, `{ok}`. `POST /shutdown` (already from M1) |
| M8.5 | `tests/test_egress.py` | Per §13.1: an autouse fixture patches `socket.socket.connect` (and `connect_ex`) to raise on any non-loopback address. Run `/demo/load-sample`, every tool through `tools.execute`, `/series/{id}/draft` for each kind, and a full reminder cycle with demo compression and a fake clock. Ollama is pointed at a local stub (`pytest-httpserver` on 127.0.0.1) so the Gemma code paths run; telemetry off; tabular heuristic. Any outbound attempt fails the test |

**Exit checklist**
- [ ] Every Settings control persists across a restart (theme in localStorage, telemetry in prefs.json, the rest in SQLite).
- [ ] Picking another installed Gemma model in Settings switches chat to it; Automatic goes back to the best installed one.
- [ ] `pytest engine/tests/test_egress.py` is green.
- [ ] Delete all local data → the Audit tab is empty, the Reminders tab is empty, the inbox is empty, and Gemma and TabPFN stay ready.

---

### M9 — Hardening, release, landing page (2.5 h) · **Checkpoint E**

| # | Task | Details |
|---|---|---|
| M9.1 | Failure paths | Engine crash mid-session → the top-bar Engine pill turns *Stopped* and a modal offers the log tail + **Restart engine**. Pipeline `error` event → an error card in the Audit tab with the stage name, **Try again**, and the import kept pending. A CSV with no parseable rows → mapper copy "We couldn't find any dated rows. Is this a bank statement export?". A 409 on a concurrent import → toast "An audit is already running." `OLLAMA_HOST` not loopback → the Gemma pill shows a warning and Settings explains it |
| M9.2 | Performance budgets | Measure and record in the README: sample audit ≤ 60 s (Mac) / ≤ 120 s (Windows CPU) on the default TabPFN v2, and again with `V3_5` / `V3_5_FAST` when a key is set; re-score ≤ 5 s; `/health` p95 < 50 ms during a pipeline (proves nothing blocks the event loop). If the Windows budget fails, cut the regressor context to the newest 400 rows (priors_hikes sample), seeded |
| M9.3 | Lifecycle checks | Quit → no engine process. Force-kill Electron → the engine exits within seconds. Relaunch boots normally (DoD 8). The port is fresh on every launch |
| M9.4 | Clean-machine DoD | Run §13.2 steps 1–8 on a clean Apple Silicon Mac and a clean Windows x64 VM, with Wi-Fi **off** for step 7. Record the results in `docs/dod-results.md` with timings and screenshots (these also feed the write-up) |
| M9.5 | README | What it is, the "Inform, never act" principle, install (Gatekeeper `xattr -cr`, SmartScreen "Run anyway"), first-run (Ollama, any Gemma model, TabPFN v2 downloads automatically; optional free Prior Labs key to upgrade to TabPFN-3.5 — "a model licence, not an app login"), the egress table, dev setup (`engine:venv`, `SLOTH_PYTHON`, `npm run dev`), tests, a list of commits made after the deadline (if any, §1), and licences (TabPFN v2 weights: Prior Labs License 1.1 — include its attribution; TabPFN-3.5 weights: non-commercial) |
| M9.6 | `site/index.html` | §10 content in the app's visual language, a single static file. It may use Google Fonts since it's a website, not the app. Light/dark tokens from §5.1. Hero + video embed slot, audit → ask → remind → verify, the "Inform, never act" block, the egress table, download buttons pointing to the GitHub Release assets, first-run notes, a DEV post link. Deploy to the free .tech domain (GitHub Pages or Cloudflare Pages) |
| M9.7 | Release | Pin dependencies (`uv pip compile` → `requirements.lock`, `package-lock.json` committed). `git tag v0.1.0 && git push --tags` → `release.yml` → a GitHub Release with the dmg and exe |

**Exit checklist (Checkpoint E):** DoD 1–8 all pass on both machines. `v0.1.0` Release assets download and install. slothspend.tech serves the landing page.

---

### M10 — Stretch (only after Checkpoint E, in this order)

1. **Sentry gen_ai spans** — `telemetry.py` verbatim from §7.11. The spans in §7.9 are already in place; add `tabpfn.fit`, `tabpfn.predict` (rows, model, device), `normalize.batch` and `reminders.send`. Off by default. Verify with traces on that no prompt text is sent (`send_default_pii=False`, no `gen_ai.prompt` attributes).
2. **Open at login** — `app.setLoginItemSettings({ openAtLogin, openAsHidden: true })` (macOS and Windows) through IPC `prefs:login:get/set`. Un-hide the Settings row (D-Settings copy).
3. **Landing page polish** — the demo video, screenshots from M9.4.
4. **Trial-conversion detector** — a $0 or $1 charge followed within 7–31 days by the same merchant's full price → flag `trial_converted`, with its own chip and flag card.

---

## 7. Golden values for the bundled sample (acceptance numbers)

These are the expected results of `/demo/load-sample` with the canned merchant map (`fixtures/sample_merchant_map.json`). `test_report.py` asserts them in heuristic mode, and they must match the copy in D-Main and D-Drawer. `make_sample_data.py` is tuned until they hold.

| Item | Expected |
|---|---|
| Statement | `sample_bank_12m.csv`, ≈ 412 rows, 2 skipped (unreadable dates), Nov 1, 2025 – Oct 15, 2026, USD, `report_date` = 2026-10-15 |
| Findings rows | 9: Rent transfer, IronTrap Fitness, Metro Electric, StreamFlix UHD, TuneTide, WatchNest, CloudBox Pro, FreshCart, BeanThere Coffee |
| Filters | All 9 · Flagged 5 · Subscriptions 5 · Bills 2 |
| IronTrap Fitness | Fitness, monthly near the 5th, 13 charges (8 × $39.99 Nov 5 – Jun 5, then $49.99 Jul 5, **Jul 6 duplicate**, Aug 5, Sep 5, Oct 5). `price_creep` $39.99 → $49.99 **+25.0 %** since 2026-07-05. `duplicate_charge` Jul 5/6, $49.99. `zombie_suspect`. Next due **Nov 5, 2026** |
| StreamFlix UHD | Streaming, monthly ~12th, $15.49 → `overlap` + `zombie_suspect`, next due Nov 12 |
| WatchNest | Streaming, monthly ~20th, $9.99 → `overlap` + `zombie_suspect`, last Sep 20, next due Oct 20 |
| TuneTide | Music, monthly ~19th, $10.99 → $11.99 from Mar 19 → `price_creep` **+9.1 %** + `zombie_suspect`, last Sep 19, next due Oct 19 |
| CloudBox Pro | Cloud Storage, a single $119.88 on Jan 14, 2026 → `possible_annual`, next due **Jan 14, 2027**, "1 charge", Low confidence |
| Metro Electric | Utilities, monthly bill $60–$140, **last $92.40 on Sep 28**, next due Oct 28, **no creep flag**, change "Varies" |
| Rent transfer | Housing, monthly $1,800.00 on the 1st, next due Nov 1 |
| FreshCart / BeanThere | `recurring_prob < 0.5`, no flags, "Irregular" |
| Monthly recurring | **$1,979.86** = $87.46 subscriptions + $1,892.40 bills |
| Potential monthly savings | **$87.46** (4 zombie suspects) + **$49.99** to dispute |
| Flags | **10 on 5 merchants**: 1 duplicate · 2 price rises · 2 overlap · 1 possible annual · 4 zombie suspects |
| Burn chart (subscriptions) | Nov–Feb $76.46 except **Jan $196.34**; Mar–Jun $77.46; **Jul $137.45**; Aug–Sep $87.46; **Oct $65.48 (partial, to the 15th)**; highlights on Jan and Jul |
| Next 30 days | Window Oct 16 – Nov 14. Subscriptions q50 = $87.46 when the regressor predicts no change. All-recurring q50 ≈ $1,980 (Metro's q50 varies, so it isn't pinned) |
| Follow-ups | `followup_cancelled` → IronTrap `VERIFIED_STOPPED` ("No charge through 2026-11-15"). `followup_still_charged` → `STILL_CHARGED` ("Charged again on 2026-11-05"). Both have no StreamFlix charge |

---

## 8. Test matrix

| Layer | Suite | Runs where | Milestone |
|---|---|---|---|
| Engine unit | `test_ingest`, `test_features`, `test_detectors` | `ci.yml`, local | M3, M4 |
| Engine integration | `test_report` (golden §7), `test_api` (token, 409, delete import, label persistence) | `ci.yml` | M4 |
| Agent | `test_agent_tools` (tools + SQL guard + draft templates) | `ci.yml` | M6 |
| Reminders | `test_reminders` (§13.1 list + events + sync) | `ci.yml` | M7 |
| Privacy | `test_egress` | `ci.yml` | M8 |
| Renderer unit | Vitest: `format.ts`, `ui-derive.ts` (labels, sort, filters, `phaseView`, axis) | `ci.yml` | M0, M5, M7 |
| Binary smoke | `smoke_test.py` against the PyInstaller build | `release.yml` | M2 |
| Manual | §13.2 DoD 1–8 on clean machines | M9.4 | M9 |

Tests never need Ollama, TabPFN weights or the network. Gemma is stubbed (canned map, an `httpserver` stub, or mocked `gemma_note`) and TabPFN runs as `heuristic`.

---

## 9. Traceability

| Story / DoD | Built in | Checked by |
|---|---|---|
| US-1 boot checklist with fixes | M1.8, M4.10–4.12 | M1 + M4 exit, DoD 1 |
| US-2 drop CSV / sample → report within budget | M3.4–3.5, M4.6–4.8, M5.1–5.4 | `test_ingest`, `test_report`, DoD 2 |
| US-3 recurring, creep, duplicates, forecast with a band | M4.2–4.6, M5.6–5.9 | `test_detectors`, golden §7 |
| US-4 corrections re-score ≤ 5 s and persist | M4.8–4.9, M5.7, M5.9 | `test_api`, DoD 3 |
| US-5 Ask Sloth with visible tools | M6.1–6.9 | `test_agent_tools`, DoD 4 |
| US-6 drafts the user sends | M6.3, M6.7, M6.10 | DoD 4, 6 |
| US-7 renewal reminders survive restarts | M7.1–7.8, M7.10 | `test_reminders`, DoD 5 |
| US-8 verify on the next statement | M7.1, M7.4, M7.9, M4.6 `persist` | `test_reminders`, DoD 6 |
| US-9 nothing leaves the laptop | M0.3 (bundled fonts), M1.6 (CSP), M8 | `test_egress`, DoD 7 |
| Inform, never act | §3.2 rules in M6.2, M6.3, M7.3, copy in M5/M6/M7 | DoD 4, review of every prompt |

---

## 10. Schedule, cut lines, working agreements

**Schedule** (matches spec §14; build first, then the write-up before Oct 25):

| Block | Milestones | Checkpoint |
|---|---|---|
| Day 1 morning | M0 → M1 → M2 | **A** |
| Day 1 afternoon | M3 → M4 | **B** |
| Day 1 evening | M5 | **C** |
| Day 2 morning | M6 → M7 | **D** |
| Day 2 afternoon | M8 → M9 | **E** |
| Day 2 evening | M10 stretch, buffer | — |
| Days 3–5 (≤ Oct 25) | Demo recording, ElevenLabs narration, DEV post, landing page live, final README | — |

**Cut lines** (in order; never cut the offline test):
1. If A slips past Day 1 midday, ship macOS first and treat Windows as best effort.
2. If C slips: drop `RangeStrip` and "Looks like" in the drawer (keep the numbers), and drop burn-chart highlights.
3. If D slips: drop snooze and follow-up verification, keep the reminder itself (§14). The Reminders tab then shows only Watching and Done.
4. If E slips: the landing page becomes a README section and `site/` waits until after the deadline (listed in the README as a post-deadline commit).

**Working agreements**
- One branch per milestone (`m4-audit-engine`), merged to `main` when its exit checklist passes. Tag checkpoints `checkpoint-a` … `checkpoint-e`.
- When spec code is copied verbatim, the commit message cites the section (`engine: detectors (spec §7.7 verbatim) + overlap/annual/zombie`).
- Any change to an API shape updates `schemas.py` **and** `types.ts` in the same commit.
- UI copy comes from the design artboards. New copy (errors, empty states) keeps the calm voice: short sentences, no exclamation marks, never implies SlothSpend acts for the user.
