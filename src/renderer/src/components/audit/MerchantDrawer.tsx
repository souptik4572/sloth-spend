import { useEffect, useState, type FormEvent } from 'react'
import {
  Ban,
  Bell,
  Calendar,
  CalendarCheck,
  CircleCheck,
  Copy,
  Ghost,
  Layers,
  Lock,
  TrendingUp,
  X,
  type LucideIcon
} from 'lucide-react'
import { Button, IconButton } from '../ui/Button'
import { Chip } from '../ui/Chip'
import { Field, Select, TextInput } from '../ui/Field'
import { Hint } from '../ui/Hint'
import { ScoreBar } from '../ui/ProgressBar'
import { Sheet } from '../ui/Sheet'
import { SourceChip, type Source } from '../ui/SourceChip'
import { Spinner } from '../ui/Spinner'
import { ChargeBars, RangeStrip } from './DrawerCharts'
import { DraftSection } from './DraftSection'
import { useAudit } from '../../auditStore'
import { errorMessage, getSeries } from '../../lib/api'
import { applyLabel, applyRename } from '../../lib/audit'
import { CATEGORIES } from '../../lib/categories'
import { cn } from '../../lib/cn'
import {
  approxPct,
  dateLong,
  dateRange,
  dateShort,
  money,
  pctChange,
  score
} from '../../lib/format'
import { cancelledIt, defaultCancelledOn, localDay, remindMe } from '../../lib/reminders'
import type { LabelKind, Reminder, Series, SeriesDetail } from '../../lib/types'
import { cadenceDetail, flagChips } from '../../lib/ui-derive'
import { byPlatform } from '../../lib/platform'

const HIKE_HINT =
  'Share of the 19 predicted prices that are more than 2% above today’s price. An approximation.'

const CANCEL_STEPS = [
  'Find the merchant’s receipt or welcome email — it usually links to “Manage subscription”.',
  'Sign in on the merchant’s website or app → Account, Billing or Membership.',
  'Billed through Apple or Google? Cancel from the App Store or Play Store subscriptions page instead.',
  `No self-serve option? Send the cancellation request below — Gemma drafts it${byPlatform(' on this computer', '')} from your own charge history.`,
  'Keep the confirmation, then click I cancelled it so SlothSpend can check your next statement.'
]

function Section({
  id,
  title,
  aside,
  children
}: {
  id: string
  title: string
  aside?: React.ReactNode
  children: React.ReactNode
}): React.JSX.Element {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 id={id} className="m-0 text-h3">
          {title}
        </h3>
        {aside}
      </div>
      {children}
    </section>
  )
}

function FlagCard({
  icon: Icon,
  tone,
  title,
  text,
  children
}: {
  icon: LucideIcon
  tone: string
  title: string
  text: string
  children?: React.ReactNode
}): React.JSX.Element {
  return (
    <li className="flex items-start gap-3.5 rounded-tile bg-card p-4">
      <span className={cn('flex size-9 shrink-0 items-center justify-center rounded-full', tone)}>
        <Icon aria-hidden size={16} strokeWidth={2.2} />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-2.5">
        <div>
          <p className="m-0 text-base font-bold">{title}</p>
          <p className="mt-0.5 mb-0 text-sm text-text-2">{text}</p>
        </div>
        {children}
      </div>
    </li>
  )
}

function Corrections({ s }: { s: Series }): React.JSX.Element {
  const [busy, setBusy] = useState<LabelKind | null>(null)
  const label = (kind: LabelKind): void => {
    setBusy(kind)
    void applyLabel(s.id, kind).finally(() => setBusy(null))
  }
  const looksRecurring = (s.recurring_prob ?? 1) >= 0.5 && s.status !== 'not_subscription'
  return (
    <div role="group" aria-label="Correct the model" className="flex flex-wrap gap-2">
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
    </div>
  )
}

function MerchantEdit({ s, raw }: { s: Series; raw: string | undefined }): React.JSX.Element {
  const [name, setName] = useState(s.merchant)
  const [category, setCategory] = useState(s.category)
  const [saving, setSaving] = useState(false)
  const changed = name.trim() !== s.merchant || category !== s.category
  const save = (e: FormEvent): void => {
    e.preventDefault()
    if (!name.trim() || !changed) return
    setSaving(true)
    void applyRename(s.id, name.trim(), category).finally(() => setSaving(false))
  }
  return (
    <Section id="ed-h" title="Merchant details">
      <form onSubmit={save} className="flex flex-wrap items-end gap-3">
        <Field label="Name" className="flex-[1_1_200px]">
          {(id) => (
            <TextInput
              id={id}
              surface="raised"
              value={name}
              maxLength={40}
              onChange={(e) => setName(e.target.value)}
            />
          )}
        </Field>
        <Field label="Category" className="flex-[1_1_160px]">
          {(id) => (
            <Select id={id} value={category} onChange={(e) => setCategory(e.target.value)}>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Button type="submit" variant="soft" disabled={!changed || saving}>
          {saving && <Spinner />}
          Save
        </Button>
      </form>
      <p className="m-0 text-xs leading-[1.65] text-muted">
        {raw ? `Seen in your statement as “${raw}”. ` : ''}Your edits win over Gemma’s and re-score
        in a few seconds.
      </p>
    </Section>
  )
}

const PHASE_TEXT: Record<Reminder['phase'], string> = {
  WATCHING: 'Reminder set',
  SNOOZED: 'Reminder snoozed',
  REMINDED: 'Reminded — waiting for your answer',
  AWAITING_STATEMENT: 'You cancelled it — waiting for your next statement',
  STILL_CHARGED: 'Still charged after you cancelled',
  VERIFIED_STOPPED: 'Verified: the charge stopped',
  KEPT: 'You’re keeping it',
  EXPIRED: 'The last reminder expired',
  STOPPED: 'Reminder stopped'
}

function HowToCancel({ s, reminder }: { s: Series; reminder: Reminder | null }): React.JSX.Element {
  const [cancelledOn, setCancelledOn] = useState(defaultCancelledOn)
  const [busy, setBusy] = useState(false)
  const run = (fn: () => Promise<unknown>): void => {
    setBusy(true)
    void fn().finally(() => setBusy(false))
  }
  const ended = !reminder || reminder.group === 'done'
  const canRemind = !!s.next_due_date && (ended || reminder?.phase === 'WATCHING')
  return (
    <section
      id="how-to-cancel"
      aria-labelledby="htc-h"
      className="flex scroll-mt-6 flex-col gap-5 rounded-card bg-panel p-6"
    >
      <div>
        <h3 id="htc-h" className="m-0 text-h2">
          How to cancel
        </h3>
        <p className="mt-1 mb-0 text-sm text-text-2">
          You do these steps. SlothSpend does none of them for you.
        </p>
      </div>
      <ol className="m-0 flex list-none flex-col gap-3 p-0">
        {CANCEL_STEPS.map((step, i) => (
          <li key={i} className="flex items-start gap-3">
            <span
              aria-hidden
              className="flex size-7 shrink-0 items-center justify-center rounded-full bg-raised text-sm font-bold"
            >
              {i + 1}
            </span>
            <span className="pt-1 text-sm">{step}</span>
          </li>
        ))}
      </ol>
      <DraftSection seriesId={s.id} kind="cancel_request" label="Draft cancellation request" />
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Cancelled on">
          {(id) => (
            <TextInput
              id={id}
              type="date"
              surface="raised"
              value={cancelledOn}
              max={localDay()}
              onChange={(e) => setCancelledOn(e.target.value)}
              className="w-auto"
            />
          )}
        </Field>
        <Button
          variant="solid"
          size="lg"
          icon={CalendarCheck}
          disabled={busy || !cancelledOn}
          onClick={() => run(() => cancelledIt(s.id, cancelledOn))}
        >
          I cancelled it
        </Button>
        <Button
          variant="outline"
          size="lg"
          icon={Bell}
          disabled={busy || !canRemind}
          title={s.next_due_date ? undefined : 'SlothSpend can’t predict when this renews.'}
          onClick={() => run(() => remindMe(s.id))}
        >
          {reminder?.phase === 'WATCHING' && reminder.remind_on
            ? `Reminder set for ${dateShort(reminder.remind_on)}`
            : 'Remind me before renewal'}
        </Button>
      </div>
      {reminder && (
        <p className="m-0 text-sm text-text-2">
          {PHASE_TEXT[reminder.phase]}
          {reminder.detail ? ` · ${reminder.detail}` : ''}
        </p>
      )}
      <p className="m-0 flex items-center gap-2 text-sm font-medium">
        <Lock aria-hidden size={16} strokeWidth={2.2} />
        SlothSpend never cancels or contacts anyone for you.
      </p>
    </section>
  )
}

function Negotiate({
  merchant,
  seriesId
}: {
  merchant: string
  seriesId: number
}): React.JSX.Element {
  return (
    <section
      id="negotiate"
      aria-labelledby="neg-h"
      className="flex scroll-mt-6 flex-col gap-4 rounded-card bg-panel p-6"
    >
      <div>
        <h3 id="neg-h" className="m-0 text-h2">
          Ask for a better rate
        </h3>
        <p className="mt-1 mb-0 text-sm text-text-2">
          Gemma can draft a short, polite email asking {merchant} for a lower rate, using your own
          charge history. You send it yourself.
        </p>
      </div>
      <DraftSection seriesId={seriesId} kind="negotiate" label="Draft negotiation email" />
      <p className="m-0 flex items-center gap-2 text-sm font-medium">
        <Lock aria-hidden size={16} strokeWidth={2.2} />
        SlothSpend never cancels or contacts anyone for you.
      </p>
    </section>
  )
}

function Body({ d, currency }: { d: SeriesDetail; currency: string }): React.JSX.Element {
  const s = d.series
  const details = s.flag_details
  const chips = flagChips(s)
  const txs = d.transactions
  const sim = d.similar
  const archetype = sim ? sim.archetype.charAt(0).toUpperCase() + sim.archetype.slice(1) : ''
  return (
    <>
      <div className="flex flex-wrap items-center gap-1.5">
        <Chip variant="panel">{s.category}</Chip>
        <Chip variant="panel">{cadenceDetail(s)}</Chip>
        {chips.map((c) => (
          <Chip key={c.id} variant={c.variant} icon={c.icon}>
            {c.label}
          </Chip>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-3 rounded-tile bg-card p-4">
        <div className="min-w-0 flex-[1_1_200px]">
          {s.recurring_prob === null ? (
            <p className="m-0 text-sm font-medium">Charged once — not scored yet</p>
          ) : (
            <>
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="text-sm font-medium">Recurring</span>
                <span className="text-h3 tabular-nums">{score(s.recurring_prob)}</span>
                <SourceChip source={s.scorer as Source} />
              </div>
              <ScoreBar prob={s.recurring_prob} width="100%" className="mt-2" />
            </>
          )}
        </div>
        <Corrections s={s} />
      </div>

      <Section
        id="ch-h"
        title="Charges"
        aside={
          <span className="text-xs text-muted">
            {txs.length} charge{txs.length === 1 ? '' : 's'}
            {txs.length > 1 && ` · ${dateRange(txs[0].date, txs[txs.length - 1].date)}`}
          </span>
        }
      >
        <ChargeBars detail={d} currency={currency} />
        <ul className="m-0 flex list-none flex-col gap-2 p-0 text-sm">
          {d.reasons.map((r) => (
            <li key={r} className="flex gap-2.5">
              <span aria-hidden className="mt-[7px] size-1.5 shrink-0 rounded-full bg-ink" />
              {r}
            </li>
          ))}
        </ul>
      </Section>

      {sim && (
        <Section id="like-h" title="Looks like">
          <div className="flex flex-col gap-3 rounded-tile bg-panel p-4">
            <div className="flex flex-wrap items-center gap-3">
              <span aria-hidden className="flex gap-1">
                {Array.from({ length: sim.k }, (_, i) => (
                  <span
                    key={i}
                    className={cn(
                      'box-border size-3 rounded-full',
                      i < sim.count ? 'bg-ink' : 'border-2 border-ink'
                    )}
                  />
                ))}
              </span>
              <span className="text-base font-medium">{archetype}</span>
              <span className="text-sm text-muted">
                {sim.count} of {sim.k} nearest examples
              </span>
            </div>
            <p className="m-0 text-sm text-text-2">
              {sim.runner_up &&
                sim.count < sim.k &&
                `The other ${sim.k - sim.count} look like a ${sim.runner_up}. `}
              Examples are simulated histories SlothSpend learned from, not other people’s data.
            </p>
          </div>
        </Section>
      )}

      {s.next_due_date && (
        <Section
          id="fc-h"
          title="Next charge"
          aside={s.fc_q50 !== null ? <SourceChip source={s.scorer as Source} /> : undefined}
        >
          <div className="flex flex-wrap items-end gap-x-8 gap-y-4">
            <div>
              <p className="m-0 text-xs text-muted">Due</p>
              <p className="m-0 text-h3">{dateLong(s.next_due_date)}</p>
            </div>
            <div>
              <p className="m-0 text-xs text-muted">Most likely</p>
              <p className="m-0 text-h3 tabular-nums">
                {money(s.fc_q50 ?? s.last_amount, currency)}
              </p>
            </div>
            {s.fc_q10 !== null && s.fc_q90 !== null && (
              <div>
                <p className="m-0 text-xs text-muted">Range (q10–q90)</p>
                <p className="m-0 text-h3 tabular-nums">
                  {money(s.fc_q10, currency)} – {money(s.fc_q90, currency)}
                </p>
              </div>
            )}
            {s.hike_prob !== null && (
              <div>
                <p className="m-0 text-xs text-muted">
                  <Hint text={HIKE_HINT}>Price-rise chance</Hint>
                </p>
                <p className="m-0 text-h3 tabular-nums">{approxPct(s.hike_prob)}</p>
              </div>
            )}
          </div>
          {s.fc_q10 !== null && s.fc_q50 !== null && s.fc_q90 !== null && (
            <RangeStrip q10={s.fc_q10} q50={s.fc_q50} q90={s.fc_q90} currency={currency} />
          )}
        </Section>
      )}

      {s.flags.length > 0 && (
        <Section id="fl-h" title="Why it’s flagged">
          <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
            {details.duplicate_charge?.map((p, i) => (
              <FlagCard
                key={p.second}
                icon={Copy}
                tone="bg-solid text-on-solid"
                title="Duplicate charge"
                text={`${money(p.amount, currency)} on ${dateLong(p.first)}, and again on ${dateLong(p.second)}.`}
              >
                {/* One refund request covers every double charge of this merchant. */}
                {i === 0 && (
                  <DraftSection seriesId={s.id} kind="refund" label="Draft refund request" />
                )}
              </FlagCard>
            ))}
            {details.price_creep && (
              <FlagCard
                icon={TrendingUp}
                tone="bg-accent text-on-accent"
                title="Price creep"
                text={`${money(details.price_creep.from, currency)} → ${money(details.price_creep.to, currency)} (${pctChange(details.price_creep.pct)}) since ${dateLong(details.price_creep.since)}.`}
              />
            )}
            {details.overlap && (
              <FlagCard
                icon={Layers}
                tone="bg-tint text-ink"
                title="Overlap"
                text={`You pay for ${details.overlap.merchants.length} ${details.overlap.category.toLowerCase()} services: ${details.overlap.merchants.join(', ')}. You may only need one.`}
              />
            )}
            {details.zombie_suspect && (
              <FlagCard
                icon={Ghost}
                tone="border border-line-strong bg-raised text-ink"
                title="Zombie suspect"
                text="Bank data can’t see usage — keep it, or cancel it yourself."
              />
            )}
            {details.possible_annual && (
              <FlagCard
                icon={Calendar}
                tone="bg-tint text-ink"
                title="Possible annual plan"
                text={`Charged once, so the renewal date is a guess: ${dateLong(details.possible_annual.next_due)}.`}
              />
            )}
          </ul>
        </Section>
      )}

      <MerchantEdit key={`${s.id}-${s.merchant}-${s.category}`} s={s} raw={d.raw_descriptions[0]} />

      {s.cancellable && <HowToCancel key={s.id} s={s} reminder={d.reminder} />}
      {s.kind === 'bill' && <Negotiate key={s.id} merchant={s.merchant} seriesId={s.id} />}
    </>
  )
}

/** D-Drawer: everything about one merchant, over the report. Esc closes; focus returns to the row. */
export function MerchantDrawer(): React.JSX.Element | null {
  const drawer = useAudit((s) => s.drawer)
  const version = useAudit((s) => s.drawerVersion)
  const closeDrawer = useAudit((s) => s.closeDrawer)
  const currency = useAudit((s) => s.report?.meta.currency ?? 'USD')
  const [detail, setDetail] = useState<SeriesDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const id = drawer?.id
  const section = drawer?.section

  useEffect(() => {
    if (id === undefined) return
    let cancelled = false
    getSeries(id)
      .then((d) => {
        if (cancelled) return
        setDetail(d)
        setError(null)
        if (section && section !== 'top') {
          requestAnimationFrame(() =>
            document.getElementById(section)?.scrollIntoView({ block: 'start' })
          )
        }
      })
      .catch((err) => !cancelled && setError(errorMessage(err, 'Couldn’t load this merchant.')))
    return () => {
      cancelled = true
    }
  }, [id, section, version])

  if (!drawer) return null
  const shown = detail && detail.series.id === drawer.id ? detail : null
  return (
    <Sheet open onClose={closeDrawer} labelledBy="dr-h">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="m-0 text-xs font-medium text-muted">Merchant</p>
          <h2 id="dr-h" className="mt-0.5 mb-0 text-h2">
            {shown?.series.merchant ?? 'Loading…'}
          </h2>
        </div>
        <IconButton icon={X} label="Close details" onClick={closeDrawer} />
      </div>
      {error && (
        <p role="alert" className="m-0 text-sm font-medium">
          {error}
        </p>
      )}
      {!shown && !error && (
        <p className="m-0 flex items-center gap-2 text-sm text-muted">
          <Spinner /> Loading…
        </p>
      )}
      {shown && <Body d={shown} currency={currency} />}
    </Sheet>
  )
}
