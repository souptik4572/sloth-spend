import { describe, expect, it } from 'vitest'
import {
  engineView,
  firstActionable,
  gemmaLabel,
  gemmaView,
  limitedSummary,
  tabpfnLabel,
  tabpfnView
} from './status'
import type { Health } from './types'

const health = (
  over: Partial<Health['ollama']> = {},
  tab: Partial<Health['tabpfn']> = {}
): Health => ({
  engine: 'ok',
  ollama: {
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
    expect(gemmaView(health({ loopback: false }), 'ok').detail).toContain('OLLAMA_HOST')
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
