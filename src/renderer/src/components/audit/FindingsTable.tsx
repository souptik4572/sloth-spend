import { useState } from 'react'
import {
  Ban,
  Bell,
  BellRing,
  CircleCheck,
  Ellipsis,
  ListChecks,
  Mail,
  MessageCircle,
  TrendingUp
} from 'lucide-react'
import { Button } from '../ui/Button'
import { Chip } from '../ui/Chip'
import { ScoreBar } from '../ui/ProgressBar'
import { SourceChip, type Source } from '../ui/SourceChip'
import { Spinner } from '../ui/Spinner'
import { useAudit } from '../../auditStore'
import { useChat } from '../../chatStore'
import { activeReminder, useReminders } from '../../remindersStore'
import { applyLabel } from '../../lib/audit'
import { remindMe } from '../../lib/reminders'
import { askAbout } from '../../lib/chat'
import { cn } from '../../lib/cn'
import { dateShort, money, score } from '../../lib/format'
import type { LabelKind, Report, Series } from '../../lib/types'
import {
  cadenceLabel,
  changeLabel,
  filterCounts,
  flagChips,
  matchesFilter,
  sortFindings,
  type Filter
} from '../../lib/ui-derive'

const GRID =
  'grid grid-cols-[minmax(170px,2.2fr)_minmax(88px,1fr)_72px_100px_minmax(150px,1.7fr)_64px_44px] items-center gap-x-3'

const FILTERS: Array<[Filter, string]> = [
  ['all', 'All'],
  ['flagged', 'Flagged'],
  ['subscriptions', 'Subscriptions'],
  ['bills', 'Bills']
]

function RowActions({ s }: { s: Series }): React.JSX.Element {
  const openDrawer = useAudit((st) => st.openDrawer)
  const [busy, setBusy] = useState<LabelKind | 'remind' | null>(null)
  const reminder = useReminders((st) => activeReminder(st.reminders, s.id))
  const label = (kind: LabelKind): void => {
    setBusy(kind)
    void applyLabel(s.id, kind).finally(() => setBusy(null))
  }
  const looksRecurring = (s.recurring_prob ?? 0) >= 0.5 && s.status !== 'not_subscription'
  return (
    <div className="flex flex-wrap gap-2 pt-3 pb-1">
      {s.cancellable && (
        <Button variant="solid" icon={ListChecks} onClick={() => openDrawer(s.id, 'how-to-cancel')}>
          How to cancel
        </Button>
      )}
      {s.kind === 'bill' && (
        <Button variant="solid" icon={Mail} onClick={() => openDrawer(s.id, 'negotiate')}>
          Draft negotiation email
        </Button>
      )}
      {s.next_due_date && (
        <Button
          variant="soft"
          icon={busy === 'remind' ? undefined : reminder ? BellRing : Bell}
          disabled={busy !== null || (!!reminder && reminder.phase !== 'WATCHING')}
          onClick={() => {
            setBusy('remind')
            void remindMe(s.id).finally(() => setBusy(null))
          }}
        >
          {busy === 'remind' && <Spinner />}
          {reminder
            ? reminder.remind_on
              ? `Reminder · ${dateShort(reminder.remind_on)}`
              : 'Reminder on'
            : 'Remind me'}
        </Button>
      )}
      {s.status !== 'keep' && (
        <Button
          variant="soft"
          icon={busy === 'keep' ? undefined : CircleCheck}
          disabled={busy !== null}
          onClick={() => label('keep')}
        >
          {busy === 'keep' && <Spinner />}
          Keep
        </Button>
      )}
      {looksRecurring ? (
        <Button
          variant="soft"
          icon={busy === 'not_subscription' ? undefined : Ban}
          disabled={busy !== null}
          onClick={() => label('not_subscription')}
        >
          {busy === 'not_subscription' && <Spinner />}
          Not a subscription
        </Button>
      ) : (
        <Button
          variant="soft"
          icon={busy === 'subscription' ? undefined : CircleCheck}
          disabled={busy !== null}
          onClick={() => label('subscription')}
        >
          {busy === 'subscription' && <Spinner />}
          It’s a subscription
        </Button>
      )}
      <Button
        variant="soft"
        icon={MessageCircle}
        onClick={() => useChat.getState().prefill(askAbout(s))}
      >
        Ask Sloth
      </Button>
    </div>
  )
}

function FindingRow({
  s,
  refYear,
  cur,
  expanded,
  onToggle
}: {
  s: Series
  refYear: number
  cur: string
  expanded: boolean
  onToggle: () => void
}): React.JSX.Element {
  const openDrawer = useAudit((st) => st.openDrawer)
  const change = changeLabel(s)
  const chips = flagChips(s)
  const muted = s.status === 'not_subscription'
  return (
    <li
      className={cn(
        'transition-colors duration-300',
        expanded ? 'my-1 rounded-tile bg-panel px-3 py-2.5' : 'border-b border-line px-3 py-2',
        muted && 'text-muted'
      )}
    >
      <div className={cn(GRID, 'min-h-14')}>
        <div className="min-w-0">
          <button
            type="button"
            onClick={() => openDrawer(s.id)}
            className="cursor-pointer rounded bg-transparent p-0 text-left text-base leading-tight font-medium text-inherit hover:underline"
          >
            {s.merchant}
          </button>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <Chip variant="raised" size={22}>
              {s.category}
            </Chip>
            <span className="text-xs text-muted">{cadenceLabel(s)}</span>
          </div>
        </div>
        <div>
          <div className="text-sm font-medium tabular-nums">{money(s.last_amount, cur)}</div>
          <div className="text-xs text-muted">{dateShort(s.last_date, refYear)}</div>
        </div>
        <div
          className={cn(
            'flex items-center gap-1 text-sm tabular-nums',
            change.up ? 'font-bold text-ink' : 'text-subtle'
          )}
        >
          {change.up && <TrendingUp aria-hidden size={14} strokeWidth={2.4} />}
          {change.text}
        </div>
        <div className="flex items-center gap-2">
          {s.recurring_prob === null ? (
            <span className="text-xs text-muted">1 charge</span>
          ) : (
            <>
              <ScoreBar prob={s.recurring_prob} />
              <span className="text-sm tabular-nums">{score(s.recurring_prob)}</span>
            </>
          )}
        </div>
        <div className="flex flex-wrap gap-1">
          {muted && (
            <Chip variant="outline" icon={Ban}>
              Not a subscription
            </Chip>
          )}
          {!muted &&
            chips.map((c) => (
              <Chip key={c.id} variant={c.variant} icon={c.icon}>
                {c.label}
              </Chip>
            ))}
          {!muted && chips.length === 0 && <span className="text-sm text-subtle">—</span>}
        </div>
        <div className="text-sm tabular-nums">
          {s.next_due_date ? dateShort(s.next_due_date, refYear) : '—'}
        </div>
        <button
          type="button"
          aria-label={`More actions for ${s.merchant}`}
          aria-expanded={expanded}
          onClick={onToggle}
          className="flex size-11 cursor-pointer items-center justify-center rounded-full bg-transparent text-ink hover:bg-ink/5"
        >
          <Ellipsis aria-hidden size={20} />
        </button>
      </div>
      {expanded && <RowActions s={s} />}
    </li>
  )
}

/** D-Main: findings sorted by priority, with filters and per-row actions. */
export function FindingsTable({ report }: { report: Report }): React.JSX.Element {
  const [filter, setFilter] = useState<Filter>('all')
  const [expanded, setExpanded] = useState<number | null>(null)
  const counts = filterCounts(report.series)
  const rows = sortFindings(report.series).filter((s) => matchesFilter(s, filter))
  const refYear = Number(report.meta.report_date.slice(0, 4))

  return (
    <section aria-labelledby="find-h" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
        <div className="mr-auto">
          <h2 id="find-h" className="m-0 text-h2">
            Findings
          </h2>
          <p className="mt-1 mb-0 flex flex-wrap items-center gap-1.5 text-sm text-muted">
            Sorted by priority · recurring scores from{' '}
            <SourceChip source={report.meta.scorer as Source} />
          </p>
        </div>
        <div role="group" aria-label="Filter findings" className="flex flex-wrap gap-1.5">
          {FILTERS.map(([id, label]) => (
            <button
              key={id}
              type="button"
              aria-pressed={filter === id}
              onClick={() => setFilter(id)}
              className={cn(
                'h-11 cursor-pointer rounded-full border px-4 text-sm font-medium transition-colors duration-300',
                filter === id
                  ? 'border-solid bg-solid text-on-solid'
                  : 'border-line bg-raised text-ink'
              )}
            >
              {label} {counts[id]}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto">
        <div className="min-w-[740px]">
          <div aria-hidden className={cn(GRID, 'px-3 pb-2 text-xs font-medium text-muted')}>
            <span>Merchant</span>
            <span>Last charge</span>
            <span>Change</span>
            <span>Recurring</span>
            <span>Flags</span>
            <span>Next due</span>
            <span />
          </div>
          <ul aria-label="Findings" className="m-0 list-none p-0">
            {rows.map((s) => (
              <FindingRow
                key={s.id}
                s={s}
                refYear={refYear}
                cur={report.meta.currency}
                expanded={expanded === s.id}
                onToggle={() => setExpanded((e) => (e === s.id ? null : s.id))}
              />
            ))}
          </ul>
          {rows.length === 0 && (
            <p className="m-0 px-3 py-6 text-sm text-muted">Nothing here with this filter.</p>
          )}
        </div>
      </div>
      <p className="m-0 text-xs leading-[1.65] text-muted">
        Bills (Housing, Utilities, Telecom, Insurance) offer{' '}
        <strong className="font-medium text-ink">Draft negotiation email</strong> instead of How to
        cancel. Every draft is yours to send.
      </p>
    </section>
  )
}
