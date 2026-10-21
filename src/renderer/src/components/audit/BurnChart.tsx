import { useState } from 'react'
import { Card } from '../ui/Card'
import { Segmented } from '../ui/Segmented'
import { SourceChip, type Source } from '../ui/SourceChip'
import { cn } from '../../lib/cn'
import { money, moneyRound, monthShort } from '../../lib/format'
import type { Report } from '../../lib/types'
import { highlightLegend, niceAxis } from '../../lib/ui-derive'

type Mode = 'subscriptions' | 'all'
const CHART_HEIGHT = 200

function nextMonth(month: string): string {
  const [y, m] = month.split('-').map(Number)
  return m === 12 ? `${y + 1}-01` : `${y}-${String(m + 1).padStart(2, '0')}`
}

/** D-Main: 12 months of recurring cash, plus next month's forecast (most likely + q10–q90). */
export function BurnChart({ report }: { report: Report }): React.JSX.Element {
  const [mode, setMode] = useState<Mode>('subscriptions')
  const cur = report.meta.currency
  const months = report.monthly
  const forecast = report.forecast_next[mode]
  const values = months.map((m) => m[mode])
  const axis = niceAxis(Math.max(...values, forecast.q90, 1))
  const px = (v: number): number => Math.round((v / axis.top) * CHART_HEIGHT)
  const forecastMonth = months.length ? nextMonth(months[months.length - 1].month) : ''
  const peak = months.reduce((a, b) => (b[mode] > a[mode] ? b : a), months[0])
  const description =
    `Bar chart of monthly ${mode === 'subscriptions' ? 'subscription' : 'recurring'} spend from ` +
    `${monthShort(months[0]?.month ?? '')} to ${monthShort(months[months.length - 1]?.month ?? '')}. ` +
    `Highest: ${monthShort(peak?.month ?? '')} at ${money(peak?.[mode] ?? 0, cur)}. ` +
    (highlightLegend(months) ? `Flagged months — ${highlightLegend(months)}. ` : '') +
    `${monthShort(forecastMonth)} forecast: most likely ${money(forecast.q50, cur)}, ` +
    `between ${money(forecast.q10, cur)} and ${money(forecast.q90, cur)}.`

  return (
    <Card as="section" aria-labelledby="burn-h" className="flex flex-col gap-5 p-6">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <div className="mr-auto">
          <h2 id="burn-h" className="m-0 text-h3">
            Monthly {mode === 'subscriptions' ? 'subscription' : 'recurring'} spend
          </h2>
          <p className="mt-1 mb-0 text-sm text-muted">Last 12 months, plus next month’s forecast</p>
        </div>
        <Segmented
          label="Which charges"
          value={mode}
          onChange={setMode}
          options={[
            { value: 'subscriptions', label: 'Subscriptions' },
            { value: 'all', label: 'All recurring' }
          ]}
        />
      </div>

      <div className="flex gap-2.5">
        <div
          aria-hidden
          className="relative w-12 shrink-0 text-right text-xs text-muted tabular-nums"
          style={{ height: CHART_HEIGHT + 10 }}
        >
          {axis.ticks.map((t) => (
            <span key={t} className="absolute right-0 leading-none" style={{ bottom: px(t) - 6 }}>
              {moneyRound(t, cur)}
            </span>
          ))}
        </div>
        <div className="min-w-0 flex-1">
          <div
            role="img"
            aria-label={description}
            className="relative mt-2.5"
            style={{ height: CHART_HEIGHT }}
          >
            {axis.ticks.map((t) => (
              <div
                key={t}
                className={cn(
                  'absolute right-0 left-0 border-t',
                  t === 0 ? 'border-faint' : 'border-line'
                )}
                style={{ bottom: px(t) }}
              />
            ))}
            <div className="absolute inset-0 flex items-end gap-0.5">
              {months.map((m, i) => {
                const v = m[mode]
                const hot = m.highlights.length > 0
                const last = i === months.length - 1
                const tip = `${monthShort(m.month)}${m.partial ? ' so far' : ''}: ${money(v, cur)}${hot ? ` — ${m.highlights.join('; ')}` : ''}`
                return (
                  <div
                    key={m.month}
                    title={tip}
                    className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1"
                  >
                    {(hot || last) && v > 0 && (
                      <span className="text-xs leading-none font-medium tabular-nums">
                        {moneyRound(v, cur)}
                      </span>
                    )}
                    <div
                      className={cn(
                        'box-border w-[72%] max-w-[30px] rounded-t transition-[height] duration-500 ease-out',
                        hot ? 'border-[1.5px] border-accent-edge bg-accent' : 'bg-ink',
                        m.partial &&
                          !hot &&
                          'border-[1.5px] border-ink bg-[repeating-linear-gradient(135deg,var(--ink)_0_3px,transparent_3px_6px)]'
                      )}
                      style={{ height: Math.max(px(v), v > 0 ? 2 : 0) }}
                    />
                  </div>
                )
              })}
              <div
                title={`${monthShort(forecastMonth)} forecast: most likely ${money(forecast.q50, cur)}, between ${money(forecast.q10, cur)} and ${money(forecast.q90, cur)}`}
                className="relative ml-2 h-full min-w-0 flex-1"
              >
                <span
                  className="absolute right-0 left-0 text-center text-xs leading-none font-bold tabular-nums"
                  style={{ bottom: px(forecast.q90) + 8 }}
                >
                  {moneyRound(forecast.q50, cur)}
                </span>
                <div
                  className="absolute left-1/2 -ml-px border-l-2 border-dashed border-ink"
                  style={{ bottom: 0, height: px(forecast.q50) }}
                />
                <div
                  className="absolute left-1/2 -ml-[15px] box-border w-[30px] rounded border-[1.5px] border-ink bg-tint"
                  style={{
                    bottom: px(forecast.q10) - 2,
                    height: Math.max(px(forecast.q90) - px(forecast.q10), 0) + 4
                  }}
                />
                <div
                  className="absolute left-1/2 -ml-1.5 size-3 rounded-full bg-ink shadow-[0_0_0_2px_var(--card)]"
                  style={{ bottom: px(forecast.q50) - 6 }}
                />
              </div>
            </div>
          </div>
          <div
            aria-hidden
            className="mt-2 flex gap-0.5 text-center text-xs leading-tight text-muted"
          >
            {months.map((m) => (
              <span key={m.month} className="min-w-0 flex-1">
                {monthShort(m.month)}
              </span>
            ))}
            <span className="ml-2 min-w-0 flex-1 font-bold text-ink">
              {monthShort(forecastMonth)}
            </span>
          </div>
        </div>
      </div>

      <ul className="m-0 flex list-none flex-wrap gap-x-5 gap-y-2 p-0 text-xs text-muted">
        <li className="flex items-center gap-1.5">
          <span aria-hidden className="size-3 rounded-[3px] bg-ink" />
          Charged
        </li>
        {months.some((m) => m.partial) && (
          <li className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="box-border size-3 rounded-[3px] border-[1.5px] border-ink bg-[repeating-linear-gradient(135deg,var(--ink)_0_2px,transparent_2px_4px)]"
            />
            This month so far
          </li>
        )}
        {highlightLegend(months) && (
          <li className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="box-border size-3 rounded-[3px] border-[1.5px] border-accent-edge bg-accent"
            />
            Month with a flag — {highlightLegend(months)}
          </li>
        )}
        <li className="flex flex-wrap items-center gap-1.5">
          <span aria-hidden className="size-3 rounded-full bg-ink" />
          Forecast, most likely ·
          <span
            aria-hidden
            className="box-border h-2 w-4 rounded-sm border-[1.5px] border-ink bg-tint"
          />
          q10–q90 range · <SourceChip source={report.meta.scorer as Source} />
        </li>
      </ul>
    </Card>
  )
}
