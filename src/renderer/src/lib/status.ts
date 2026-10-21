// Maps engine state + /health into what the Boot rows and header pills show (D-Boot, D-Main header).
import type { Health } from './types'

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

export function tabpfnView(h: Health | null, engine: EngineState): RowView {
  if (engine !== 'ok' || !h) return WAITING
  const t = h.tabpfn
  switch (t.status) {
    case 'cold':
      return { tone: 'working', status: 'Starting', detail: 'Loading the model in the background.' }
    case 'warming':
      return {
        tone: 'working',
        status: 'Warming up',
        detail: 'Downloading weights and warming up — first time only.'
      }
    case 'missing_weights':
      return {
        tone: 'action',
        status: 'Needs your key',
        detail:
          'Paste your free Prior Labs key (non-commercial license). It’s stored encrypted on this computer and used once to download the model weights. This is a model license, not an app login.'
      }
    case 'error':
      return {
        tone: 'error',
        status: 'Couldn’t load',
        detail: t.error ?? 'TabPFN-3.5 failed to load.'
      }
    case 'ready':
      return {
        tone: 'ready',
        status: 'Ready',
        detail:
          t.model === 'tabpfn-3.5-fast'
            ? 'TabPFN-3.5 Fast scores your charges on this computer’s CPU.'
            : 'TabPFN-3.5 scores your charges on this computer.'
      }
  }
}

/** Index of the first row the user can act on (it gets the ink ring), or -1. */
export function firstActionable(rows: RowView[]): number {
  return rows.findIndex((r) => r.tone === 'action' || r.tone === 'error')
}
