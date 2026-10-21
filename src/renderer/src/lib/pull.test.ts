import { describe, expect, it } from 'vitest'
import { RateMeter, emptyPull, etaLabel, pullTotals, reducePull } from './pull'

describe('reducePull', () => {
  it('sums progress across layers', () => {
    let s = emptyPull()
    s = reducePull(s, { status: 'pulling manifest' })
    s = reducePull(s, { status: 'pulling aaa', completed: 1e9, total: 4e9 })
    s = reducePull(s, { status: 'pulling bbb', completed: 5e8, total: 1e9 })
    s = reducePull(s, { status: 'pulling aaa', completed: 1.6e9, total: 4e9 })
    expect(pullTotals(s)).toEqual({ completed: 2.1e9, total: 5e9 })
    expect(s.status).toBe('Downloading')
  })
  it('names the closing steps', () => {
    expect(reducePull(emptyPull(), { status: 'verifying sha256 digest' }).status).toBe(
      'Checking the download…'
    )
    expect(reducePull(emptyPull(), { status: 'success' }).status).toBe('Done')
  })
})

describe('RateMeter and etaLabel', () => {
  it('estimates from a rolling window', () => {
    const m = new RateMeter(10_000)
    m.push(0, 0)
    m.push(5_000, 50e6)
    m.push(10_000, 100e6)
    expect(m.rate()).toBe(10e6)
    expect(etaLabel(2.9e9, m.rate())).toBe('About 5 min left')
    expect(etaLabel(30e6, m.rate())).toBe('Less than a minute left')
    expect(etaLabel(1e9, 0)).toBe('')
  })
})
