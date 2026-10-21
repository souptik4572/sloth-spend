// Pure display rules for the audit screens (IMPL M5.11). Unit-tested against the engine's golden report.
import type { LucideIcon } from 'lucide-react'
import { Calendar, Copy, Ghost, Layers, TrendingUp } from 'lucide-react'
import type { ChipVariant } from '../components/ui/Chip'
import { dateShort, monthShort, pctChange, pctChip } from './format'
import type { FlagId, Series, StageId } from './types'

export const RECURRING = 0.7

/** Same rule as the engine's report (recurring = scored ≥ 0.7 and not excluded by the user, or kept). */
export function isRecurring(s: Series): boolean {
  if (s.status === 'keep') return true
  return (
    s.recurring_prob !== null &&
    s.recurring_prob >= RECURRING &&
    s.status !== 'not_subscription' &&
    s.status !== 'user_cancelled'
  )
}

const CADENCE: Record<string, string> = {
  weekly: 'Weekly',
  biweekly: 'Every 2 weeks',
  monthly: 'Monthly',
  quarterly: 'Quarterly',
  annual: 'Yearly',
  irregular: 'Irregular'
}

/** "Monthly", "Monthly · bill", "Once a year?" (a single charge that may be annual), "Irregular". */
export function cadenceLabel(s: Series): string {
  if (s.cadence === 'single') return 'Once a year?'
  const base = CADENCE[s.cadence] ?? 'Irregular'
  return s.kind === 'bill' && s.cadence !== 'irregular' ? `${base} · bill` : base
}

/** Drawer chip: "Monthly · near the 5th". */
export function cadenceDetail(s: Series): string {
  if (s.cadence === 'monthly' && s.dom_median) {
    const day = Math.round(s.dom_median)
    const suffix =
      day % 100 >= 11 && day % 100 <= 13
        ? 'th'
        : (({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[day % 10] ?? 'th')
    return `Monthly · near the ${day}${suffix}`
  }
  return cadenceLabel(s)
}

export interface ChangeView {
  text: string
  up: boolean
}

/** The Change column: "+25.0%" for a price rise, "Varies" for a variable bill, otherwise "—". */
export function changeLabel(s: Series): ChangeView {
  const creep = s.flag_details.price_creep
  if (creep) return { text: pctChange(creep.pct), up: true }
  if (s.kind === 'bill' && s.amount_varies) return { text: 'Varies', up: false }
  return { text: '—', up: false }
}

export interface FlagChip {
  id: FlagId | 'low_confidence'
  label: string
  variant: ChipVariant
  icon?: LucideIcon
}

/** "Jul 5/6", or "Jun 30/Jul 1" across months. */
function duplicateDates(first: string, second: string): string {
  const a = dateShort(first)
  const b = dateShort(second)
  return a.split(' ')[0] === b.split(' ')[0] ? `${a}/${b.split(' ')[1]}` : `${a}/${b}`
}

/** Flag chips in the design's order and styles (D-Main). */
export function flagChips(s: Series): FlagChip[] {
  const chips: FlagChip[] = []
  const dup = s.flag_details.duplicate_charge?.[0]
  if (s.flags.includes('duplicate_charge')) {
    chips.push({
      id: 'duplicate_charge',
      label: dup ? `Duplicate · ${duplicateDates(dup.first, dup.second)}` : 'Duplicate',
      variant: 'solid',
      icon: Copy
    })
  }
  const creep = s.flag_details.price_creep
  if (s.flags.includes('price_creep')) {
    chips.push({
      id: 'price_creep',
      label: creep ? `Price ${pctChip(creep.pct)}` : 'Price rise',
      variant: 'accent',
      icon: TrendingUp
    })
  }
  if (s.flags.includes('overlap'))
    chips.push({ id: 'overlap', label: 'Overlap', variant: 'tint', icon: Layers })
  if (s.flags.includes('zombie_suspect'))
    chips.push({ id: 'zombie_suspect', label: 'Zombie suspect', variant: 'outline', icon: Ghost })
  if (s.flags.includes('possible_annual')) {
    chips.push({ id: 'possible_annual', label: 'Possible annual', variant: 'tint', icon: Calendar })
    chips.push({ id: 'low_confidence', label: 'Low confidence', variant: 'dashed' })
  }
  return chips
}

export type Filter = 'all' | 'flagged' | 'subscriptions' | 'bills'

export function matchesFilter(s: Series, f: Filter): boolean {
  if (f === 'flagged') return s.flags.length > 0
  if (f === 'subscriptions') return s.kind === 'subscription'
  if (f === 'bills') return s.kind === 'bill'
  return true
}

export function filterCounts(series: Series[]): Record<Filter, number> {
  return {
    all: series.length,
    flagged: series.filter((s) => matchesFilter(s, 'flagged')).length,
    subscriptions: series.filter((s) => matchesFilter(s, 'subscriptions')).length,
    bills: series.filter((s) => matchesFilter(s, 'bills')).length
  }
}

/** Recurring first by priority, then flagged one-offs, then the rest by score (the engine's order). */
export function sortFindings(series: Series[]): Series[] {
  const group = (s: Series): number => (isRecurring(s) ? 0 : s.flags.length ? 1 : 2)
  return [...series].sort(
    (a, b) =>
      group(a) - group(b) ||
      b.priority - a.priority ||
      (b.recurring_prob ?? 0) - (a.recurring_prob ?? 0) ||
      a.merchant.localeCompare(b.merchant)
  )
}

/** About five gridlines at nice steps: max 196 → 0, 50, 100, 150, 200 (D-Main); 1,980 → 0 … 2,000. */
export function niceAxis(
  max: number,
  intervals = 4
): { top: number; step: number; ticks: number[] } {
  const raw = Math.max(max, 1) / intervals
  const magnitude = 10 ** Math.floor(Math.log10(raw))
  const step = ([1, 2, 2.5, 5, 10].find((m) => m * magnitude >= raw) ?? 10) * magnitude
  const top = Math.max(Math.ceil(max / step), 1) * step
  const ticks = Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step)
  return { top, step, ticks }
}

/** "Jan: CloudBox Pro’s $119.88 annual charge · Jul: …" for the chart legend. */
export function highlightLegend(monthly: { month: string; highlights: string[] }[]): string {
  return monthly
    .filter((m) => m.highlights.length)
    .map((m) => {
      const h = m.highlights
      const text = h.length > 2 ? `${h[0]}, ${h[1]} and ${h.length - 2} more` : h.join(' and ')
      return `${monthShort(m.month)}: ${text}`
    })
    .join(' · ')
}

export const STAGE_LABELS: Record<StageId, string> = {
  parse: 'Read rows',
  normalize: 'Clean merchant names',
  detect: 'Find double charges',
  features: 'Measure billing patterns',
  score: 'Score recurring charges',
  forecast: 'Forecast the next 30 days',
  flags: 'Flag price rises and overlaps',
  summary: 'Write the summary',
  done: 'Save the report'
}

export const STAGE_ORDER: StageId[] = [
  'parse',
  'normalize',
  'detect',
  'features',
  'score',
  'forecast',
  'flags',
  'summary',
  'done'
]
