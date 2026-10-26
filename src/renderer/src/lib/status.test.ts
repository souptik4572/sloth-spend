import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import {
  engineView,
  firstActionable,
  gemmaLabel,
  gemmaView,
  limitedSummary,
  tabpfnLabel,
  tabpfnView,
  gemmaWhere
} from './status'
import type { Health } from './types'

const health = (
  over: Partial<Health['llm']> = {},
  tab: Partial<Health['tabpfn']> = {}
): Health => ({
  engine: 'ok',
  llm: {
    provider: 'ollama',
    status: 'ready',
    version: '0.40.6',
    model: 'gemma4:e4b',
    model_present: true,
    available_models: ['gemma4:e4b'],
    loopback: true,
    ...over
  },
  tabpfn: {
    status: 'ready',
    model: 'tabpfn-v2',
    error: null,
    upgrade: { state: 'none', error: null },
    ...tab
  },
  telemetry: false
})

describe('engineView', () => {
  it('covers starting, ok and stopped', () => {
    expect(engineView('starting', null).tone).toBe('working')
    expect(engineView('ok', null).tone).toBe('ready')
    const stopped = engineView('stopped', 1)
    expect(stopped.tone).toBe('error')
    expect(stopped.detail).toContain('exit code 1')
  })
})

describe('gemmaView', () => {
  it('waits for the engine', () => {
    expect(gemmaView(null, 'starting').tone).toBe('waiting')
  })
  it('maps every Ollama status', () => {
    expect(gemmaView(health({ status: 'unreachable' }), 'ok').status).toBe('Ollama not found')
    expect(gemmaView(health({ status: 'outdated', version: '0.19.0' }), 'ok').detail).toContain(
      '0.19.0'
    )
    expect(gemmaView(health({ status: 'missing_model' }), 'ok').status).toBe('Needs a Gemma model')
    expect(gemmaView(health(), 'ok').tone).toBe('ready')
  })
  it('warns when Ollama is not on this computer', () => {
    const remote = gemmaView(health({ loopback: false }), 'ok')
    expect(remote.detail).toContain('OLLAMA_HOST')
    expect([remote.tone, remote.status]).toEqual(['action', 'Not on this computer']) // the pill warns
  })
})

describe('tabpfnView', () => {
  it('defaults to TabPFN v2, ready without a key', () => {
    const v = tabpfnView(health(), 'ok')
    expect(v.tone).toBe('ready')
    expect(v.detail).toBe('TabPFN v2 scores your charges on this computer.')
  })
  it('names TabPFN-3.5 once the key upgrade is active', () => {
    const v = tabpfnView(
      health({}, { model: 'tabpfn-3.5', upgrade: { state: 'active', error: null } }),
      'ok'
    )
    expect(v.detail).toBe('TabPFN-3.5 scores your charges on this computer.')
    expect(tabpfnView(health({}, { model: 'tabpfn-3.5-fast' }), 'ok').detail).toContain('CPU')
  })
  it('explains a failed upgrade while staying on v2', () => {
    const v = tabpfnView(
      health({}, { upgrade: { state: 'failed', error: 'license not accepted' } }),
      'ok'
    )
    expect(v.tone).toBe('ready')
    expect(v.detail).toContain('Still using TabPFN v2')
    expect(v.detail).toContain('license not accepted')
  })
  it('covers download, warm-up, unavailable and error', () => {
    expect(tabpfnView(health({}, { status: 'downloading' }), 'ok').detail).toContain('70 MB')
    expect(tabpfnView(health({}, { status: 'warming' }), 'ok').tone).toBe('working')
    expect(tabpfnView(health({}, { status: 'unavailable', error: null }), 'ok').tone).toBe('action')
    expect(tabpfnView(health({}, { status: 'error', error: 'boom' }), 'ok').detail).toBe('boom')
  })
})

describe('tabpfnLabel', () => {
  it('names the version in use', () => {
    expect(tabpfnLabel(health())).toBe('TabPFN v2')
    expect(tabpfnLabel(health({}, { model: 'tabpfn-3.5' }))).toBe('TabPFN-3.5')
    expect(tabpfnLabel(health({}, { model: null }))).toBe('TabPFN')
  })
})

describe('limitedSummary', () => {
  it('names only what is limited', () => {
    expect(limitedSummary(health())).toBeNull()
    expect(limitedSummary(health({}, { status: 'unavailable' }))).toBe(
      'a simple rule instead of TabPFN'
    )
    expect(limitedSummary(health({ status: 'unreachable' }))).toBe(
      'rule-based merchant names and template text'
    )
  })
})

describe('firstActionable', () => {
  it('finds the first row needing the user', () => {
    const rows = [
      engineView('ok', null),
      gemmaView(health({ status: 'missing_model' }), 'ok'),
      tabpfnView(health({}, { status: 'unavailable' }), 'ok')
    ]
    expect(firstActionable(rows)).toBe(1)
    expect(firstActionable([engineView('ok', null)])).toBe(-1)
  })
})

describe('gemmaLabel', () => {
  it('names whichever Gemma generation is installed', () => {
    expect(gemmaLabel(health({ model: 'gemma4:latest' }))).toBe('Gemma 4')
    expect(gemmaLabel(health({ model: 'gemma3:4b' }))).toBe('Gemma 3')
    expect(gemmaLabel(health({ model: 'gemma:7b' }))).toBe('Gemma')
  })
  it('falls back to plain Gemma before a model is known', () => {
    expect(gemmaLabel(null)).toBe('Gemma')
    expect(gemmaLabel(health({ status: 'missing_model', model_present: false }))).toBe('Gemma')
  })
  it('reports the installed model as ready', () => {
    expect(gemmaView(health({ model: 'gemma4:latest' }), 'ok').detail).toContain('gemma4:latest')
  })
})

describe('on the web (WEB-IMPL W3)', () => {
  const g = globalThis as { window?: unknown }
  let previous: unknown
  beforeEach(() => {
    previous = g.window
    g.window = { sloth: { kind: 'web' } }
  })
  afterEach(() => {
    g.window = previous
  })

  const gemini = (status: Health['llm']['status'], model = 'gemma-4-26b-a4b-it'): Health =>
    health({
      provider: 'gemini',
      status,
      model,
      model_present: status === 'ready',
      loopback: false
    })

  it('names the server instead of a local engine', () => {
    expect(engineView('ok', null).detail).toBe('Connected to SlothSpend.')
    const lost = engineView('starting', null)
    expect(lost.tone).toBe('working')
    expect(lost.status).toBe('Connecting…')
  })

  it('maps every Gemini API status, never asking the visitor to install anything', () => {
    expect(gemmaView(gemini('ready'), 'ok')).toEqual({
      tone: 'ready',
      status: 'Ready',
      detail: 'gemma-4-26b-a4b-it runs on the Gemini API.'
    })
    expect(gemmaView(gemini('rate_limited'), 'ok').tone).toBe('working')
    for (const status of ['missing_key', 'bad_key', 'missing_model', 'unreachable'] as const) {
      const view = gemmaView(gemini(status), 'ok')
      expect(view.tone).toBe('error')
      expect(view.detail).not.toMatch(/Ollama|this computer|install/i)
      expect(view.detail).toContain('templates')
    }
  })

  it('reads Gemini model names and says where Gemma ran', () => {
    expect(gemmaLabel(gemini('ready'))).toBe('Gemma 4')
    expect(gemmaLabel(gemini('missing_key'))).toBe('Gemma')
    expect(gemmaWhere(gemini('ready'))).toBe('Gemini API')
    expect(gemmaWhere(health())).toBe('Ollama')
    expect(gemmaWhere(null)).toBeNull() // offline: no claim about who runs Gemma
    expect(gemmaView(health(), 'ok').detail).toBe('gemma4:e4b runs on Ollama on the server.')
  })

  it('places TabPFN on the server', () => {
    expect(tabpfnView(health(), 'ok').detail).toBe(
      'TabPFN v2 scores your charges on SlothSpend’s server.'
    )
    expect(tabpfnView(health({}, { status: 'unavailable', model: null }), 'ok').detail).not.toMatch(
      /internet|retry/i
    )
  })
})

describe('on the desktop', () => {
  it('keeps saying local', () => {
    expect(gemmaWhere(health())).toBe('local')
    expect(gemmaView(health(), 'ok').detail).toBe('gemma4:e4b runs locally through Ollama.')
  })
})
