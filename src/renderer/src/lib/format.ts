// Money, date and percentage formatting (IMPL §5.8). The engine mirrors these in app/money.py.

export type Currency = 'USD' | 'INR' | 'EUR' | 'GBP'

const moneyFormats = new Map<string, Intl.NumberFormat>()

export function money(amount: number, currency: string = 'USD'): string {
  let fmt = moneyFormats.get(currency)
  if (!fmt) {
    const locale = currency === 'INR' ? 'en-IN' : currency === 'EUR' ? 'en-IE' : 'en-US'
    fmt = new Intl.NumberFormat(locale, {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    })
    moneyFormats.set(currency, fmt)
  }
  return fmt.format(amount)
}

/** Whole-unit money for chart ticks and bar labels ("$87", "₹1,800"). */
export function moneyRound(amount: number, currency: string = 'USD'): string {
  const locale = currency === 'INR' ? 'en-IN' : currency === 'EUR' ? 'en-IE' : 'en-US'
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    maximumFractionDigits: 0
  }).format(Math.round(amount))
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** Parses "YYYY-MM-DD" (or a full ISO timestamp) without timezone drift for plain dates. */
function parts(iso: string): { y: number; m: number; d: number } {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return { y, m, d }
}

/** "Nov 5" — adds the year only when it differs from refYear (the report date's year). */
export function dateShort(iso: string, refYear?: number): string {
  const { y, m, d } = parts(iso)
  const base = `${MONTHS[m - 1]} ${d}`
  return refYear !== undefined && y !== refYear ? `${base}, ${y}` : base
}

/** "Nov 5, 2026" */
export function dateLong(iso: string): string {
  const { y, m, d } = parts(iso)
  return `${MONTHS[m - 1]} ${d}, ${y}`
}

/** "Nov 1, 2025 – Oct 15, 2026" */
export function dateRange(startIso: string, endIso: string): string {
  return `${dateLong(startIso)} – ${dateLong(endIso)}`
}

/** "Jan" from "2026-01" or "2026-01-14". */
export function monthShort(iso: string): string {
  return MONTHS[parts(iso.length === 7 ? `${iso}-01` : iso).m - 1]
}

/** Inbox times: "now", "2 min", "9:00 AM" (today), "Nov 9" (older). */
export function relativeTime(iso: string, now: Date = new Date()): string {
  const then = new Date(iso)
  const mins = Math.floor((now.getTime() - then.getTime()) / 60000)
  if (mins < 1) return 'now'
  if (mins < 60) return `${mins} min`
  if (then.toDateString() === now.toDateString()) {
    return then.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
  }
  return `${MONTHS[then.getMonth()]} ${then.getDate()}`
}

/** "+25.0%" for the findings table. */
export function pctChange(pct: number): string {
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`
}

/** "+25%" or "+9.1%" for chips: drops a trailing ".0". */
export function pctChip(pct: number): string {
  const s = pct.toFixed(1).replace(/\.0$/, '')
  return `${pct >= 0 ? '+' : ''}${s}%`
}

/** Recurring score as a rounded integer percentage: 0.981 → "98%". */
export function score(prob: number): string {
  return `${Math.round(prob * 100)}%`
}

/** "≈ 16%" for the price-rise chance. */
export function approxPct(prob: number): string {
  return `≈ ${Math.round(prob * 100)}%`
}

/** "0:21" elapsed timer. */
export function elapsed(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/** "2.1 GB" for download progress. */
export function gigabytes(bytes: number): string {
  return `${(bytes / 1e9).toFixed(1)} GB`
}
