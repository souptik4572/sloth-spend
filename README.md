# SlothSpend

**Slow and steady subscription audits, on your own computer.**

SlothSpend is a desktop app for macOS and Windows. Drop in a year of bank-statement CSV and it finds the
subscriptions you forgot, the prices that crept up and the charges that came twice — then helps you deal with
them at your own pace. Two open models do the work, both running locally:

- **Gemma** (through [Ollama](https://ollama.com)) cleans merchant names, answers questions with typed tools,
  and drafts notes and emails.
- **TabPFN** (v2 open weights by default) decides which charges recur, forecasts the next 30 days with a range,
  and learns from your corrections in seconds.

Website: [slothspend.tech](https://slothspend.tech) · Releases:
[github.com/souptik4572/sloth-spend/releases](https://github.com/souptik4572/sloth-spend/releases)

## Inform, never act

The sloth never rushes and never acts for you.

- It never cancels a subscription, logs in anywhere, or contacts a merchant. It drafts; you send.
- It never invents a link or a phone number: drafts and answers are checked, and anything that looks like one
  is removed before you see it.
- It never claims to have done something it didn't. If the model says "I've set a reminder" and no tool
  confirmed it, the answer is replaced with what actually happened.
- Every number shows which model produced it (Gemma, TabPFN v2, or a labelled template or rule when a model
  isn't available).

## How it works

1. **Audit** — import a CSV. Merchant names are normalised by Gemma; TabPFN scores which series recur and
   forecasts the next charge with q10–q90 quantiles; deterministic detectors flag double charges, price creep,
   overlapping services and possible annual plans.
2. **Ask** — Ask Sloth answers with eight typed tools, including a *live* TabPFN forecast for "what if I cancel
   X and Y?". Each tool call is shown.
3. **Remind** — a reminder a few days before a renewal, as a desktop notification while SlothSpend is open (or
   the next time you open it). Keep it, snooze it, or cancel it yourself.
4. **Verify** — after you say you cancelled, the next statement you import is checked: *Verified* if the charge
   stopped, *Still charged* (with a refund request ready) if it didn't.

## Install

Download from the [latest release](https://github.com/souptik4572/sloth-spend/releases/latest):
`SlothSpend-0.1.0-mac-arm64.dmg` (Apple Silicon) or `SlothSpend-0.1.0-win-x64.exe` (Windows x64).

This is an unsigned hackathon build:

- **macOS:** drag SlothSpend to Applications, then right-click → **Open** the first time. If macOS still says it
  can't be opened, run `xattr -cr /Applications/SlothSpend.app` once.
- **Windows:** SmartScreen may warn about an unknown publisher. Choose **More info** → **Run anyway**.

### First run

1. Install [Ollama](https://ollama.com/download) (0.20 or newer) and open it.
2. Any Gemma model you already have in Ollama works. If you have none, SlothSpend offers to download
   `gemma4:e4b`.
3. TabPFN v2 downloads automatically the first time (about 70 MB, no account).
4. Optional: paste a free [Prior Labs](https://platform.priorlabs.ai) key in Settings to upgrade to
   TabPFN-3.5. It's a model licence, not an app login — accept the TabPFN-3.5 licence on your Prior Labs account
   first. The key is stored encrypted with your OS keychain and never shown again.

## Where your data goes

| Data | Goes to | When | Default |
|---|---|---|---|
| Transactions, merchants, amounts, chats, reminders | This computer — local SQLite in the app-data folder | Always | — |
| Merchant descriptions → Gemma | This computer — Ollama on 127.0.0.1 | Import | On |
| Reminder and email facts → Gemma | This computer — Ollama on 127.0.0.1 | A reminder fires or you ask for a draft | On |
| TabPFN inputs | This computer — local PyTorch | Import and chat | On |
| TabPFN v2 weights | Internet, one time — Hugging Face | First run | Automatic |
| TabPFN-3.5 weights | Internet, one time — Prior Labs (licence check) + Hugging Face | Only after you add a key | Off |
| Gemma weights | Internet, one time — Ollama registry | First run | You start it |
| Span timings, token counts, tool names (no prompt or answer text) | Internet, opt-in — Sentry | Only if traces are on | Off |

After the one-time model downloads, SlothSpend makes **no network calls at all** unless traces are on.
`engine/tests/test_egress.py` runs the whole app — audit, every chat tool, drafts, a reminder cycle and
"Delete all local data" — with every non-loopback connection refused, and fails on any attempt. If you point
`OLLAMA_HOST` at another computer, the app warns you that Gemma's inputs leave this one.

## Performance (measured)

Packaged macOS build, Apple Silicon (M-series), TabPFN v2, `gemma4:latest`, 2026-10-22:

| Check | Budget | Measured |
|---|---|---|
| Launch → engine healthy | ≤ 20 s | 7.1 s (with a saved Prior Labs key; ~0.1 s to spawn without one) |
| Window shown | — | 0.18 s |
| Sample audit (412 rows, 12 months) | ≤ 60 s | 27.7 s |
| Re-score after "Not a subscription" | ≤ 5 s | 2.4 s |
| `/health` p95 during an audit | < 50 ms | 19 ms (max 83 ms over 411 polls) |
| Quit → engine process gone | — | 0.13 s |
| Force-kill the app → engine exits | within seconds | 0.02 s (stdin EOF) |

Not measured yet: Windows (CPU budget ≤ 120 s) and TabPFN-3.5 / 3.5 Fast timings. See
[`docs/dod-results.md`](docs/dod-results.md).

## Develop

Requirements: Node 24, Python 3.11, [uv](https://docs.astral.sh/uv/), Ollama.

```bash
npm install
npm run engine:venv        # engine/.venv from engine/requirements.lock (+ dev tools)
npm run dev                # Electron + Vite; the engine runs from engine/.venv
```

`SLOTH_PYTHON=/path/to/python` overrides the interpreter used in development. Packaged builds:

```bash
npm run engine:build       # PyInstaller onedir → engine/dist/slothspend-engine
npm run engine:smoke       # starts the frozen engine and checks /health
npm run dist:mac           # or dist:win (on Windows)
```

Tests:

```bash
npm test                   # renderer (Vitest)
npm run engine:test        # engine (pytest), including test_egress.py
npm run lint && npm run typecheck
```

`git tag v0.1.0 && git push --tags` runs `.github/workflows/release.yml`, which builds the dmg and exe on macOS
and Windows runners and publishes a GitHub Release. Engine dependencies are pinned in
`engine/requirements.lock`; Node dependencies in `package-lock.json`.

## Commits after the deadline

None so far. The Hacktoberfest 2026 entry window closes on Oct 25, 2026; any later commits will be listed here.

## Licences

- SlothSpend: MIT — see [LICENSE](LICENSE).
- **TabPFN v2 weights:** Prior Labs License 1.1 (Apache 2.0 with an attribution requirement).
  **Built with PriorLabs-TabPFN.**
- **TabPFN-3.5 weights:** downloaded only with your own Prior Labs key, under Prior Labs' non-commercial licence.
- The `tabpfn` Python package: Apache 2.0, © Prior Labs GmbH.
- Gemma models are downloaded by you through Ollama and used under Google's Gemma terms.
