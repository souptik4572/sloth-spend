import { Card } from '../ui/Card'
import { Chip, type ChipVariant } from '../ui/Chip'
import { Hint } from '../ui/Hint'
import { SourceChip, type Source } from '../ui/SourceChip'
import { money } from '../../lib/format'
import type { FlagId, ReportMeta } from '../../lib/types'

const BAND_HINT =
  '10th to 90th percentile. Each charge’s range is added up, so the band is a little wide on purpose.'

const FLAG_CHIPS: Array<[FlagId, string, string, ChipVariant]> = [
  ['duplicate_charge', 'duplicate', 'duplicates', 'solid'],
  ['price_creep', 'price rise', 'price rises', 'accent'],
  ['overlap', 'overlap', 'overlap', 'tint'],
  ['possible_annual', 'possible annual', 'possible annual', 'tint'],
  ['zombie_suspect', 'zombie suspect', 'zombie suspects', 'outline']
]

/** D-Main: Sloth's summary on the pink card. */
export function SummaryNarrative({ meta }: { meta: ReportMeta }): React.JSX.Element {
  return (
    <Card
      as="section"
      tone="accent"
      radius="section"
      aria-labelledby="sum-h"
      className="flex flex-col gap-3 px-8 py-7"
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h2 id="sum-h" className="m-0 text-sm font-bold">
          Sloth’s summary
        </h2>
        <SourceChip
          source={meta.summary_source === 'gemma' ? 'gemma' : 'template'}
          onPanel
          size={24}
        />
      </div>
      <p className="m-0 max-w-[62ch] text-lead">{meta.executive_summary}</p>
    </Card>
  )
}

/** D-Main: Monthly recurring · Next 30 days · Potential monthly savings · Flags. */
export function SummaryCards({ meta }: { meta: ReportMeta }): React.JSX.Element {
  const cur = meta.currency
  const { q10, q50, q90 } = meta.fc30
  const zombies = meta.zombie_count
  return (
    <section
      aria-label="Summary"
      className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-4"
    >
      <Card className="flex flex-col gap-2.5 p-6">
        <h3 className="m-0 text-sm font-medium text-muted">Monthly recurring</h3>
        <p className="m-0 text-stat">{money(meta.monthly_recurring, cur)}</p>
        <p className="m-0 text-sm text-muted">
          {money(meta.monthly_subscriptions, cur)} subscriptions · {money(meta.monthly_bills, cur)}{' '}
          bills
        </p>
      </Card>

      <Card className="flex flex-col gap-2.5 p-6">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="m-0 text-sm font-medium text-muted">Next 30 days</h3>
          <SourceChip source={meta.scorer as Source} />
        </div>
        <p className="m-0 text-stat">{money(q50, cur)}</p>
        <p className="m-0 text-sm text-muted">
          {q50 === 0 ? (
            'Nothing recurring is due yet'
          ) : q10 === q90 ? (
            'At the latest prices — no forecast model yet'
          ) : (
            <>
              Likely {money(q10, cur)} – {money(q90, cur)} <Hint text={BAND_HINT}>(q10–q90)</Hint>
            </>
          )}
        </p>
      </Card>

      <Card tone="solid" className="flex flex-col gap-2.5 p-6">
        <h3 className="m-0 text-sm font-medium text-on-solid-2">Potential monthly savings</h3>
        <p className="m-0 text-stat">{money(meta.potential_savings, cur)}</p>
        <p className="m-0 text-sm text-on-solid-2">
          {zombies
            ? `If you cancel the ${zombies} zombie suspect${zombies === 1 ? '' : 's'} yourself`
            : 'No zombie suspects right now'}
          {meta.dispute_total > 0
            ? ` — plus a ${money(meta.dispute_total, cur)} double charge to dispute.`
            : '.'}
        </p>
      </Card>

      <Card className="flex flex-col gap-2.5 p-6">
        <h3 className="m-0 text-sm font-medium text-muted">Flags</h3>
        <p className="m-0 flex items-baseline gap-2.5">
          <span className="text-stat">
            {Object.values(meta.flag_counts).reduce((a, b) => a + b, 0)}
          </span>
          <span className="text-sm text-muted">
            on {meta.flagged_merchants} merchant{meta.flagged_merchants === 1 ? '' : 's'}
          </span>
        </p>
        <ul className="m-0 flex list-none flex-wrap gap-1.5 p-0">
          {FLAG_CHIPS.filter(([id]) => meta.flag_counts[id] > 0).map(([id, one, many, variant]) => (
            <li key={id}>
              <Chip variant={variant}>
                {meta.flag_counts[id]} {meta.flag_counts[id] === 1 ? one : many}
              </Chip>
            </li>
          ))}
        </ul>
      </Card>
    </section>
  )
}
