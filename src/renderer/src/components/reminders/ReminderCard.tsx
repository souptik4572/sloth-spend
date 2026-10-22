import { useState } from 'react'
import { AlarmClock, CircleCheck, ListChecks, Mail, TriangleAlert, Upload } from 'lucide-react'
import { FilePicker } from '../audit/FilePicker'
import { Button } from '../ui/Button'
import { Chip } from '../ui/Chip'
import { Stepper } from '../ui/Stepper'
import { useAudit } from '../../auditStore'
import { send } from '../../lib/ask'
import { cn } from '../../lib/cn'
import { dateLong, dateShort } from '../../lib/format'
import {
  cancelledIt,
  defaultCancelledOn,
  keepIt,
  remindMe,
  snooze,
  stopReminder
} from '../../lib/reminders'
import type { Reminder } from '../../lib/types'
import { phaseView, type ReminderActionId } from '../../lib/ui-derive'

function Actions({
  r,
  ids,
  onAccent
}: {
  r: Reminder
  ids: ReminderActionId[]
  onAccent: boolean
}): React.JSX.Element | null {
  const openDrawer = useAudit((s) => s.openDrawer)
  const [busy, setBusy] = useState(false)
  if (!ids.length) return null
  const run = (fn: () => Promise<unknown>): void => {
    setBusy(true)
    void fn().finally(() => setBusy(false))
  }
  const soft = onAccent ? 'border-transparent bg-raised' : undefined
  const button: Record<ReminderActionId, React.JSX.Element> = {
    cancelled: (
      <Button
        key="cancelled"
        variant="soft"
        className={soft}
        disabled={busy}
        onClick={() => run(() => cancelledIt(r.series_id, defaultCancelledOn()))}
      >
        I cancelled it
      </Button>
    ),
    keep: (
      <Button
        key="keep"
        variant="soft"
        disabled={busy}
        onClick={() => run(() => keepIt(r.series_id))}
      >
        Keep it
      </Button>
    ),
    snooze1: (
      <Button
        key="snooze1"
        variant="soft"
        icon={AlarmClock}
        disabled={busy}
        onClick={() => run(() => snooze(r.series_id, 1))}
      >
        Snooze 1 d
      </Button>
    ),
    snooze3: (
      <Button
        key="snooze3"
        variant="soft"
        icon={AlarmClock}
        disabled={busy}
        onClick={() => run(() => snooze(r.series_id, 3))}
      >
        Snooze 3 d
      </Button>
    ),
    howto: (
      <Button
        key="howto"
        variant="soft"
        icon={ListChecks}
        className={soft}
        onClick={() => openDrawer(r.series_id, 'how-to-cancel')}
      >
        How to cancel
      </Button>
    ),
    refund: (
      <Button
        key="refund"
        variant="solid"
        icon={Mail}
        onClick={() => void send(`Draft a refund request for ${r.merchant}.`)}
      >
        Draft refund request
      </Button>
    ),
    import: (
      <FilePicker key="import" variant="soft" icon={Upload}>
        Import newer statement
      </FilePicker>
    ),
    again: (
      <Button
        key="again"
        variant="soft"
        disabled={busy}
        onClick={() => run(() => remindMe(r.series_id))}
      >
        Remind me again
      </Button>
    ),
    stop: (
      <Button
        key="stop"
        variant="ghost"
        disabled={busy}
        onClick={() => run(() => stopReminder(r.series_id))}
      >
        Stop
      </Button>
    )
  }
  return <div className="flex flex-wrap gap-2">{ids.map((id) => button[id])}</div>
}

/** One reminder (D-Reminders), drawn from its phase by phaseView (IMPL M7.8). */
export function ReminderCard({
  r,
  currency,
  today,
  demoSeconds
}: {
  r: Reminder
  currency: string
  today: string
  demoSeconds: number
}): React.JSX.Element {
  const v = phaseView(r, currency, today)
  const id = `rem-${r.series_id}`
  const badges = v.badges.map((b) => (
    <Chip
      key={b.label}
      size={28}
      variant={b.variant}
      strong={b.variant !== 'outline' && b.variant !== 'dashed'}
      icon={b.icon === 'alert' ? TriangleAlert : b.icon === 'check' ? CircleCheck : undefined}
    >
      {b.label}
    </Chip>
  ))

  if (v.layout === 'compact') {
    let line: string | null = null
    if (r.phase === 'WATCHING') {
      line = demoSeconds
        ? `We’ll remind you in about ${demoSeconds} s (demo: ${demoSeconds} s).`
        : r.low_confidence
          ? `We’ll remind you on ${r.remind_on ? dateLong(r.remind_on) : 'the day'}. It only charged once, so this date is a guess.`
          : `We’ll remind you on ${r.remind_on ? dateShort(r.remind_on) : 'the day'}, ${r.days_before} day${r.days_before === 1 ? '' : 's'} before it renews.`
    } else if (r.phase === 'SNOOZED') {
      line = `Snoozed — we’ll remind you again on ${r.remind_on ? dateShort(r.remind_on) : 'soon'}.`
    } else if (v.message) {
      line = v.message.text
    }
    return (
      <article
        aria-labelledby={id}
        className="flex flex-wrap items-center gap-x-5 gap-y-3 rounded-card bg-card px-6 py-5"
      >
        <div className="min-w-0 flex-[1_1_260px]">
          <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
            <h3 id={id} className="m-0 text-h3">
              {r.merchant}
            </h3>
            <span className="text-sm text-muted">{v.subline}</span>
            {badges}
          </div>
          {line && <p className="mt-1 mb-0 text-sm leading-[1.45]">{line}</p>}
        </div>
        <Actions r={r} ids={v.actions} onAccent={false} />
      </article>
    )
  }

  const accent = v.tone === 'accent'
  return (
    <article
      aria-labelledby={id}
      data-theme={accent ? 'light' : undefined}
      className={cn(
        'flex flex-col gap-[18px] rounded-card p-6 text-ink',
        accent ? 'bg-accent' : v.tone === 'outlined' ? 'border border-line bg-bg' : 'bg-card'
      )}
    >
      <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
        <div className="min-w-0 flex-[1_1_240px]">
          <h3 id={id} className="m-0 text-h3">
            {r.merchant}
          </h3>
          <p className={cn('mt-0.5 mb-0 text-sm', accent ? 'text-text-2' : 'text-muted')}>
            {v.subline}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">{badges}</div>
      </div>
      {v.steps && <Stepper steps={v.steps} onAccent={accent} />}
      {v.message && (
        <p className="m-0 text-base leading-normal">
          {v.message.strong && <strong>{v.message.strong}</strong>}
          {v.message.text}
          {v.message.saving && <strong className="text-success">{v.message.saving}</strong>}
        </p>
      )}
      <Actions r={r} ids={v.actions} onAccent={accent} />
    </article>
  )
}
