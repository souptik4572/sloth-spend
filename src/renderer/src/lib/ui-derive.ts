// Pure display rules for the audit screens (IMPL M5.11). Unit-tested against the engine's golden report.
import type { LucideIcon } from 'lucide-react'
import { Calendar, Copy, Ghost, Layers, TrendingUp } from 'lucide-react'
import type { ChipVariant } from '../components/ui/Chip'
import type { Step } from '../components/ui/Stepper'
import { dateLong, dateShort, money, monthShort, pctChange, pctChip } from './format'
import type { FlagId, Reminder, Series, StageId } from './types'

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

// ── Reminders (IMPL M7.8): phase → card ─────────────────────────────────────

const PER: Record<string, string> = {
  weekly: 'a week',
  biweekly: 'every two weeks',
  monthly: 'a month',
  quarterly: 'every three months',
  annual: 'a year',
  single: 'a year'
}

export type ReminderActionId =
  'cancelled' | 'keep' | 'snooze1' | 'snooze3' | 'howto' | 'stop' | 'import' | 'refund' | 'again'

export interface PhaseBadge {
  label: string
  variant: ChipVariant
  icon?: 'alert' | 'check'
}

export interface PhaseView {
  /** Full card with the stepper, or a one-row compact card. */
  layout: 'card' | 'compact'
  tone: 'default' | 'accent' | 'outlined'
  subline: string
  badges: PhaseBadge[]
  steps: Step[] | null
  /** Bold lead-in, then the rest of the sentence. */
  message: { strong?: string; text: string; saving?: string } | null
  actions: ReminderActionId[]
}

function daysLeftLabel(n: number): string {
  return n === 0 ? 'Due today' : `${n} day${n === 1 ? '' : 's'} left`
}

function eventDay(r: Reminder, phase: Reminder['phase']): string | null {
  const ev = [...r.events].reverse().find((e) => e.phase === phase)
  return ev ? ev.at.slice(0, 10) : null
}

/** "Today" for today's date, else "Nov 9". */
function stepDate(iso: string | null, today: string): string {
  if (!iso) return ''
  return iso === today ? 'Today' : dateShort(iso)
}

export function phaseView(r: Reminder, currency: string, today: string): PhaseView {
  const due = dateShort(r.next_due_date)
  const amount =
    r.amount !== null ? `${money(r.amount, currency)} ${PER[r.cadence ?? ''] ?? ''}`.trim() : ''
  const left = r.days_left
  const watchedOn = eventDay(r, 'WATCHING')
  const remindedOn = eventDay(r, 'REMINDED')
  const watched: Step = { label: 'Watching', sub: stepDate(watchedOn, today), state: 'done' }
  const reminded: Step = remindedOn
    ? { label: 'Reminded', sub: stepDate(remindedOn, today), state: 'done' }
    : { label: 'Reminded', sub: 'Skipped', state: 'skip' }
  const cancelledStep: Step = {
    label: 'You cancelled',
    sub: r.cancelled_on ? dateShort(r.cancelled_on) : '',
    state: 'done'
  }
  const howto: ReminderActionId[] = r.cancellable ? ['howto'] : []
  const sentOf = `${r.reminders_sent} of ${r.max_reminders}`

  switch (r.phase) {
    case 'WATCHING':
    case 'SNOOZED': {
      const badges: PhaseBadge[] = []
      if (r.phase === 'SNOOZED') badges.push({ label: `Snoozed · ${sentOf}`, variant: 'outline' })
      else if (left !== null && left >= 0 && left <= 7)
        badges.push({ label: daysLeftLabel(left), variant: 'accent' })
      if (r.low_confidence) badges.push({ label: 'Low confidence', variant: 'dashed' })
      const renews = r.low_confidence
        ? `likely renews ${dateLong(r.next_due_date)}`
        : `renews ${due}`
      const leftText =
        !r.low_confidence && left !== null && left >= 0
          ? ` · ${daysLeftLabel(left).toLowerCase()}`
          : ''
      return {
        layout: 'compact',
        tone: 'default',
        subline: `${amount} · ${renews}${leftText}`,
        badges,
        steps: null,
        message: null,
        actions: ['keep', 'cancelled', 'stop']
      }
    }
    case 'REMINDED': {
      const badges: PhaseBadge[] = []
      if (left !== null && left >= 0) badges.push({ label: daysLeftLabel(left), variant: 'accent' })
      badges.push({ label: `Reminded · ${sentOf}`, variant: 'outline' })
      const snooze: ReminderActionId[] =
        r.reminders_sent < r.max_reminders ? ['snooze1', 'snooze3'] : []
      return {
        layout: 'card',
        tone: 'default',
        subline: `${amount} · renews ${due}`,
        badges,
        steps: [
          watched,
          { label: 'Reminded', sub: stepDate(remindedOn, today), state: 'current' },
          { label: 'Kept / You cancelled', sub: '', state: 'todo' },
          { label: 'Verified', sub: '', state: 'todo' }
        ],
        message: { text: r.detail ?? `Renews ${due}. Keep it, or cancel it yourself?` },
        actions: ['cancelled', 'keep', ...snooze, ...howto, 'stop']
      }
    }
    case 'AWAITING_STATEMENT':
      return {
        layout: 'card',
        tone: 'default',
        subline: `${amount} · renews ${due}`,
        badges: [{ label: 'Waiting for your next statement', variant: 'tint' }],
        steps: [watched, reminded, cancelledStep, { label: 'Verified', sub: '', state: 'todo' }],
        message: {
          text:
            r.detail && r.detail.startsWith('That statement')
              ? r.detail
              : `Import a statement that covers ${due} and SlothSpend will check the charge stopped.`
        },
        actions: ['import', 'stop']
      }
    case 'STILL_CHARGED': {
      const charge = r.checked
      const chargeAmount = charge?.amount ?? r.amount
      return {
        layout: 'card',
        tone: 'accent',
        subline: `${amount} · renewed ${due}`,
        badges: [{ label: 'Still charged', variant: 'solid', icon: 'alert' }],
        steps: [
          watched,
          reminded,
          cancelledStep,
          { label: 'Still charged', sub: charge ? dateShort(charge.date) : '', state: 'alert' }
        ],
        message: {
          strong: charge
            ? `Charged again on ${dateLong(charge.date)}${chargeAmount !== null ? ` — ${money(chargeAmount, currency)}` : ''}`
            : 'Charged again',
          text: `${r.cancelled_on ? `, after you cancelled on ${dateShort(r.cancelled_on)}` : ''}. Ask ${r.merchant} for a refund; the draft is ready in Ask Sloth.`
        },
        actions: ['refund', ...howto, 'stop']
      }
    }
    case 'VERIFIED_STOPPED': {
      const through = r.checked?.date
      const saving = r.monthly_equiv || r.amount
      return {
        layout: 'card',
        tone: 'outlined',
        subline: `${amount} · was due ${due}`,
        badges: [{ label: 'Verified', variant: 'success', icon: 'check' }],
        steps: [
          watched,
          reminded,
          cancelledStep,
          { label: 'Verified', sub: through ? dateShort(through) : '', state: 'ok' }
        ],
        message: {
          text: `No ${r.merchant} charge through ${through ? dateShort(through) : 'your latest statement'}, after its ${due} renewal. `,
          saving: saving ? `You’re saving ${money(saving, currency)} a month.` : undefined
        },
        actions: []
      }
    }
    default: {
      const label = { KEPT: 'Kept', EXPIRED: 'Expired', STOPPED: 'Stopped' }[r.phase]
      return {
        layout: 'compact',
        tone: 'default',
        subline: `${amount} · ${r.phase === 'KEPT' ? 'renews' : 'was due'} ${due}`,
        badges: [{ label, variant: r.phase === 'KEPT' ? 'tint' : 'outline' }],
        steps: null,
        message: r.detail ? { text: r.detail } : null,
        actions: ['again']
      }
    }
  }
}

/** How many reminders need the user (the tab's "{n} need you" pill). */
export function needsYou(reminders: Reminder[]): number {
  return reminders.filter((r) => r.group === 'needs_you').length
}

/**
 * The column mapper's "Debits are positive" when the engine couldn't tell (it found no amount column): the same
 * rule as the engine's `sign_from_amounts`, on the preview rows of the column the person picked. Mostly negative
 * amounts → debits carry the minus sign; otherwise suggest positive debits.
 */
export function guessDebitsPositive(preview: string[][], column: number): boolean {
  if (column < 0) return true
  const values = preview
    .map((row) => signedAmount(row[column] ?? ''))
    .filter((v): v is number => v !== null && v !== 0)
  if (!values.length) return true
  return values.filter((v) => v < 0).length / values.length <= 0.5
}

/** "-5.96", "$3,200.00", "(12.50)", "−4.00", "12.50-" → a signed number; anything else → null. */
export function signedAmount(cell: string): number | null {
  const text = cell.trim().replace(/−/g, '-')
  if (!text) return null
  const negative = /^\(.*\)$/.test(text) || /^-|-$/.test(text.replace(/[^\d.,()-]/g, ''))
  const digits = text.replace(/[^\d.]/g, '')
  if (!digits || !/\d/.test(digits)) return null
  const n = Number.parseFloat(digits)
  return Number.isFinite(n) ? (negative ? -n : n) : null
}
