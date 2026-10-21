import { describe, expect, it } from 'vitest'
import {
  approxPct,
  dateLong,
  dateRange,
  dateShort,
  elapsed,
  gigabytes,
  money,
  moneyRound,
  monthShort,
  pctChange,
  pctChip,
  relativeTime,
  score
} from './format'

describe('money', () => {
  it('formats USD with two decimals', () => {
    expect(money(1979.86)).toBe('$1,979.86')
    expect(money(49.99, 'USD')).toBe('$49.99')
  })
  it('uses Indian 2-2-3 grouping for INR', () => {
    expect(money(118450.2, 'INR')).toBe('₹1,18,450.20')
  })
  it('rounds for chart labels', () => {
    expect(moneyRound(87.46)).toBe('$87')
    expect(moneyRound(196.34)).toBe('$196')
  })
})

describe('dates', () => {
  it('short form omits the report year', () => {
    expect(dateShort('2026-11-05', 2026)).toBe('Nov 5')
    expect(dateShort('2027-01-14', 2026)).toBe('Jan 14, 2027')
  })
  it('long form and ranges', () => {
    expect(dateLong('2026-11-05')).toBe('Nov 5, 2026')
    expect(dateRange('2025-11-01', '2026-10-15')).toBe('Nov 1, 2025 – Oct 15, 2026')
  })
  it('month labels from YYYY-MM', () => {
    expect(monthShort('2026-01')).toBe('Jan')
    expect(monthShort('2025-11-20')).toBe('Nov')
  })
  it('relative inbox times', () => {
    const now = new Date('2026-11-16T10:00:00')
    expect(relativeTime('2026-11-16T09:59:40', now)).toBe('now')
    expect(relativeTime('2026-11-16T09:58:00', now)).toBe('2 min')
    expect(relativeTime('2026-11-16T09:00:00', now)).toBe('9:00 AM')
    expect(relativeTime('2026-11-09T09:00:00', now)).toBe('Nov 9')
  })
})

describe('percentages and misc', () => {
  it('formats price changes', () => {
    expect(pctChange(25)).toBe('+25.0%')
    expect(pctChip(25)).toBe('+25%')
    expect(pctChip(9.1)).toBe('+9.1%')
  })
  it('formats scores', () => {
    expect(score(0.981)).toBe('98%')
    expect(approxPct(0.158)).toBe('≈ 16%')
  })
  it('formats timers and sizes', () => {
    expect(elapsed(21_400)).toBe('0:21')
    expect(gigabytes(2.1e9)).toBe('2.1 GB')
  })
})
