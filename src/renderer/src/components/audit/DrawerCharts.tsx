import { cn } from '../../lib/cn'
import { money, moneyRound, monthShort } from '../../lib/format'
import type { SeriesDetail } from '../../lib/types'

const BARS_HEIGHT = 96

/** One bar per charge: duplicates in pink, the current price in ink, earlier prices in subtle grey. */
export function ChargeBars({
  detail,
  currency
}: {
  detail: SeriesDetail
  currency: string
}): React.JSX.Element {
  const txs = detail.transactions
  const max = Math.max(...txs.map((t) => t.amount), 1)
  const current = detail.series.last_amount
  const creep = detail.series.flag_details.price_creep
  const levels = [...new Set([current, ...(creep ? [creep.from] : [])])]
  const px = (v: number): number => Math.round((v / max) * (BARS_HEIGHT - 8))
  const samePrice = (a: number, b: number): boolean => Math.abs(a - b) <= 0.01 * Math.max(a, b)
  // Month labels under every other bar, never repeating a month or labelling a duplicate.
  const ticks = txs.reduce<string[]>((out, t, i) => {
    const m = monthShort(t.date)
    const previous = out.filter(Boolean).at(-1)
    out.push(t.is_duplicate || i % 2 === 1 || m === previous ? '' : m)
    return out
  }, [])
  const label =
    `Charge history: ${txs.length} charges from ${txs[0]?.date} to ${txs[txs.length - 1]?.date}` +
    (creep ? `, ${money(creep.from, currency)} rising to ${money(creep.to, currency)}` : '') +
    (txs.some((t) => t.is_duplicate) ? ', with a duplicate charge' : '') +
    '.'
  return (
    <div className="flex gap-2.5">
      <div
        aria-hidden
        className="relative w-12 shrink-0 text-right text-xs text-muted tabular-nums"
        style={{ height: BARS_HEIGHT }}
      >
        {levels.map((v) => (
          <span key={v} className="absolute right-0 leading-none" style={{ bottom: px(v) - 6 }}>
            {money(v, currency)}
          </span>
        ))}
        <span className="absolute right-0 bottom-[-6px] leading-none">
          {moneyRound(0, currency)}
        </span>
      </div>
      <div className="min-w-0 flex-1">
        <div
          role="img"
          aria-label={label}
          className="flex items-end gap-1 border-b border-faint"
          style={{ height: BARS_HEIGHT }}
        >
          {txs.map((t) => (
            <div
              key={t.id}
              title={`${t.date}${t.is_duplicate ? ' (duplicate)' : ''}: ${money(t.amount, currency)}`}
              className={cn(
                'box-border min-w-0 flex-1 rounded-t',
                t.is_duplicate
                  ? 'border-[1.5px] border-accent-edge bg-accent'
                  : samePrice(t.amount, current)
                    ? 'bg-ink'
                    : 'bg-subtle'
              )}
              style={{ height: Math.max(px(t.amount), 2) }}
            />
          ))}
        </div>
        <div aria-hidden className="mt-1.5 flex gap-1 text-xs text-muted">
          {ticks.map((m, i) => (
            <span key={i} className="min-w-0 flex-1 text-center">
              {m}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

/** The q10–q90 band and the most likely next price on a small axis (D-Drawer "Next charge"). */
export function RangeStrip({
  q10,
  q50,
  q90,
  currency
}: {
  q10: number
  q50: number
  q90: number
  currency: string
}): React.JSX.Element {
  const lo = Math.floor(q10 * 0.8)
  const hi = Math.ceil(q90 * 1.2)
  const pct = (v: number): number => ((v - lo) / (hi - lo || 1)) * 100
  const mid = Math.round((lo + hi) / 2)
  return (
    <div aria-hidden>
      <div className="relative h-6">
        <div className="absolute top-[11px] right-0 left-0 h-0.5 bg-line" />
        <div
          className="absolute top-1.5 box-border h-3 min-w-3 rounded-full border-[1.5px] border-ink bg-tint"
          style={{ left: `${pct(q10)}%`, width: `${Math.max(pct(q90) - pct(q10), 0)}%` }}
        />
        <div
          className="absolute top-1 -ml-2 size-4 rounded-full bg-ink shadow-[0_0_0_2px_var(--bg)]"
          style={{ left: `${pct(q50)}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-muted tabular-nums">
        <span>{moneyRound(lo, currency)}</span>
        <span>{moneyRound(mid, currency)}</span>
        <span>{moneyRound(hi, currency)}</span>
      </div>
    </div>
  )
}
