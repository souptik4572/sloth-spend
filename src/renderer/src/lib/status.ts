// Maps engine state + /health into what the Boot rows and header pills show (D-Boot, D-Main header).
import type { Health, Scorer } from './types'

export type EngineState = 'starting' | 'ok' | 'stopped'

/** ready = green · working = spinner · action = the user can fix it · error = failed · waiting = blocked on the engine */
export type Tone = 'ready' | 'working' | 'action' | 'error' | 'waiting'

export interface RowView {
  tone: Tone
  status: string
  detail: string
}

export function engineView(engine: EngineState, exitCode: number | null): RowView {
  if (engine === 'ok') {
    return {
      tone: 'ready',
      status: 'Ready',
      detail: 'The local engine is running on this computer.'
    }
  }
  if (engine === 'stopped') {
    const code = exitCode === null ? '' : ` (exit code ${exitCode})`
    return {
      tone: 'error',
      status: 'Stopped',
      detail: `The local engine stopped${code}. The last lines of its log are below.`
    }
  }
  return {
    tone: 'working',
    status: 'Starting…',
    detail: 'The local engine is starting on this computer.'
  }
}

const WAITING: RowView = {
  tone: 'waiting',
  status: 'Waiting for the engine',
  detail: 'Checked as soon as the local engine is running.'
}

export function gemmaView(h: Health | null, engine: EngineState): RowView {
  if (engine !== 'ok' || !h) return WAITING
  const o = h.ollama
  const remote = o.loopback
    ? ''
    : ' Note: OLLAMA_HOST points at another computer, so merchant names would leave this one.'
  switch (o.status) {
    case 'unreachable':
      return {
        tone: 'action',
        status: 'Ollama not found',
        detail:
          'SlothSpend runs Gemma through Ollama on this computer. Install Ollama and open it; this row turns green by itself.' +
          remote
      }
    case 'outdated':
      return {
        tone: 'action',
        status: 'Update Ollama',
        detail: `${o.version ? `Ollama ${o.version}` : 'An older Ollama'} is installed. Gemma 4 tool calling needs version 0.20 or newer.`
      }
    case 'missing_model':
      return {
        tone: 'action',
        status: 'Needs a Gemma model',
        detail:
          `Ollama found on this computer, but no Gemma model yet. One-time download of ${o.model}, about 5 GB.` +
          remote
      }
    case 'ready':
      return {
        tone: 'ready',
        status: 'Ready',
        detail: `${o.model} runs locally through Ollama.` + remote
      }
  }
}

/**
 * Display name for whichever Gemma model is in use: "gemma4:latest" → "Gemma 4", "gemma3:4b" → "Gemma 3".
 * Before a model is known (or none is installed) it falls back to plain "Gemma".
 */
export function gemmaLabel(h: Health | null): string {
  if (!h || !h.ollama.model_present) return 'Gemma'
  const m = /gemma(\d+)/i.exec(h.ollama.model)
  return m ? `Gemma ${m[1]}` : 'Gemma'
}

const TABPFN_NAMES: Record<Exclude<Scorer, 'heuristic'>, string> = {
  'tabpfn-v2': 'TabPFN v2',
  'tabpfn-3.5': 'TabPFN-3.5',
  'tabpfn-3.5-fast': 'TabPFN-3.5 Fast'
}

/** Display name of the TabPFN version in use ("TabPFN v2", "TabPFN-3.5"), or plain "TabPFN" before one loads. */
export function tabpfnLabel(h: Health | null): string {
  const model = h?.tabpfn.model
  return model ? TABPFN_NAMES[model] : 'TabPFN'
}

export function tabpfnView(h: Health | null, engine: EngineState): RowView {
  if (engine !== 'ok' || !h) return WAITING
  const t = h.tabpfn
  switch (t.status) {
    case 'cold':
      return { tone: 'working', status: 'Starting', detail: 'Loading TabPFN in the background.' }
    case 'downloading':
      return {
        tone: 'working',
        status: 'Downloading',
        detail:
          t.upgrade.state === 'downloading'
            ? 'Downloading TabPFN-3.5 with your Prior Labs key — one time only.'
            : 'Downloading TabPFN v2 — about 70 MB, one time, no account needed.'
      }
    case 'warming':
      return {
        tone: 'working',
        status: 'Warming up',
        detail: 'Loading the model — first time only.'
      }
    case 'unavailable':
      return {
        tone: 'action',
        status: 'Not available yet',
        detail:
          t.error ??
          'Couldn’t download TabPFN v2 (about 70 MB, one time). Connect to the internet, then retry. Until then, a simple rule scores charges.'
      }
    case 'error':
      return { tone: 'error', status: 'Couldn’t load', detail: t.error ?? 'TabPFN failed to load.' }
    case 'ready': {
      const name = tabpfnLabel(h)
      const where = t.model === 'tabpfn-3.5-fast' ? 'this computer’s CPU' : 'this computer'
      const upgrade =
        t.upgrade.state === 'failed'
          ? ` Still using TabPFN v2: the TabPFN-3.5 upgrade didn’t work (${t.upgrade.error ?? 'unknown error'}).`
          : t.model === 'tabpfn-v2'
            ? ' Optional: add a free Prior Labs key to upgrade to TabPFN-3.5.'
            : ''
      return {
        tone: 'ready',
        status: 'Ready',
        detail: `${name} scores your charges on ${where}.${upgrade}`
      }
    }
  }
}

/**
 * What limited mode means right now, or null when Gemma and TabPFN are both ready.
 * e.g. "rule-based merchant names" (Gemma missing) and/or "a simple rule instead of TabPFN".
 */
export function limitedSummary(h: Health | null): string | null {
  if (!h) return null
  const parts: string[] = []
  if (h.ollama.status !== 'ready') parts.push('rule-based merchant names and template text')
  if (h.tabpfn.status !== 'ready') parts.push('a simple rule instead of TabPFN')
  return parts.length ? parts.join(', and ') : null
}

/** Index of the first row the user can act on (it gets the ink ring), or -1. */
export function firstActionable(rows: RowView[]): number {
  return rows.findIndex((r) => r.tone === 'action' || r.tone === 'error')
}
