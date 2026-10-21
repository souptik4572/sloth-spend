import { describe, expect, it } from 'vitest'
import fixture from './__fixtures__/report.json'
import type { Report, Series } from './types'
import {
  cadenceDetail,
  cadenceLabel,
  changeLabel,
  filterCounts,
  flagChips,
  highlightLegend,
  isRecurring,
  niceAxis,
  sortFindings
} from './ui-derive'

// The engine's real golden report (IMPL §7), exported from a heuristic run with canned Gemma names.
const report = fixture as unknown as Report
const by = (name: string): Series => report.series.find((s) => s.merchant === name)!

describe('labels', () => {
  it('cadence column', () => {
    expect(cadenceLabel(by('IronTrap Fitness'))).toBe('Monthly')
    expect(cadenceLabel(by('Rent transfer'))).toBe('Monthly · bill')
    expect(cadenceLabel(by('CloudBox Pro'))).toBe('Once a year?')
    expect(cadenceLabel(by('FreshCart'))).toBe('Irregular')
    expect(cadenceDetail(by('IronTrap Fitness'))).toBe('Monthly · near the 5th')
  })
  it('change column', () => {
    expect(changeLabel(by('IronTrap Fitness'))).toEqual({ text: '+25.0%', up: true })
    expect(changeLabel(by('TuneTide')).text).toBe('+9.1%')
    expect(changeLabel(by('Metro Electric')).text).toBe('Varies')
    expect(changeLabel(by('Rent transfer')).text).toBe('—')
  })
  it('flag chips match the design', () => {
    expect(flagChips(by('IronTrap Fitness')).map((c) => c.label)).toEqual([
      'Duplicate · Jul 5/6',
      'Price +25%',
      'Zombie suspect'
    ])
    expect(flagChips(by('TuneTide')).map((c) => c.label)).toEqual(['Price +9.1%', 'Zombie suspect'])
    expect(flagChips(by('CloudBox Pro')).map((c) => c.label)).toEqual([
      'Possible annual',
      'Low confidence'
    ])
    expect(flagChips(by('Rent transfer'))).toEqual([])
  })
})

describe('table', () => {
  it('filter counts: All 9 · Flagged 5 · Subscriptions 5 · Bills 2', () => {
    expect(filterCounts(report.series)).toEqual({ all: 9, flagged: 5, subscriptions: 5, bills: 2 })
  })
  it('sorts like the engine and the design', () => {
    const order = sortFindings([...report.series].reverse()).map((s) => s.merchant)
    expect(order).toEqual(report.series.map((s) => s.merchant))
    expect(order.slice(0, 3)).toEqual(['Rent transfer', 'IronTrap Fitness', 'Metro Electric'])
  })
  it('recurring rule', () => {
    expect(isRecurring(by('WatchNest'))).toBe(true)
    expect(isRecurring(by('FreshCart'))).toBe(false)
    expect(isRecurring({ ...by('WatchNest'), status: 'not_subscription' })).toBe(false)
    expect(isRecurring({ ...by('FreshCart'), status: 'keep' })).toBe(true)
  })
})

describe('chart', () => {
  it('nice axis', () => {
    expect(niceAxis(196.34)).toEqual({ top: 200, step: 50, ticks: [0, 50, 100, 150, 200] })
    expect(niceAxis(137.45)).toEqual({ top: 150, step: 50, ticks: [0, 50, 100, 150] })
    expect(niceAxis(1979.86)).toEqual({ top: 2000, step: 500, ticks: [0, 500, 1000, 1500, 2000] })
    expect(niceAxis(0).ticks.length).toBeGreaterThan(1)
  })
  it('legend names the highlighted months', () => {
    expect(highlightLegend(report.monthly)).toBe(
      'Jan: CloudBox Pro’s $119.88 annual charge · Jul: IronTrap Fitness’s price rise and IronTrap Fitness charged twice'
    )
  })
  it('legend shortens a crowded month', () => {
    expect(highlightLegend([{ month: '2026-10', highlights: ['a', 'b', 'c', 'd'] }])).toBe(
      'Oct: a, b and 2 more'
    )
  })
})
