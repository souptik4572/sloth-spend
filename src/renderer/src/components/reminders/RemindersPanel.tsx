import { Info, Upload } from 'lucide-react'
import { FilePicker } from '../audit/FilePicker'
import { Card } from '../ui/Card'
import { Spinner } from '../ui/Spinner'
import { BrowserNotifications } from './BrowserNotifications'
import { ReminderCard } from './ReminderCard'
import { useAudit } from '../../auditStore'
import { dateRange, relativeDay } from '../../lib/format'
import { byPlatform } from '../../lib/platform'
import { localDay } from '../../lib/reminders'
import type { Reminder, ReportMeta } from '../../lib/types'
import { useReminders } from '../../remindersStore'

const GROUPS: Array<[Reminder['group'], string]> = [
  ['needs_you', 'Needs you'],
  ['watching', 'Watching'],
  ['done', 'Done']
]

function LatestStatement({ meta }: { meta: ReportMeta }): React.JSX.Element | null {
  const latest = meta.imports[meta.imports.length - 1]
  if (!latest) return null
  const checked = latest.verified_count ?? 0
  return (
    <Card
      as="section"
      radius="tile"
      aria-label="Latest statement"
      className="flex flex-wrap items-center gap-3 py-3 pr-3 pl-4"
    >
      <div className="min-w-0 flex-[1_1_300px]">
        <div className="text-sm leading-[1.45] font-medium">
          {latest.file_name} · {dateRange(latest.period_start, latest.period_end)}
        </div>
        <div className="text-xs leading-[1.65] text-muted">
          Imported {relativeDay(latest.imported_at)} · checked {checked} cancelled subscription
          {checked === 1 ? '' : 's'}
        </div>
      </div>
      <FilePicker variant="soft" icon={Upload}>
        Import newer statement
      </FilePicker>
    </Card>
  )
}

/** D-Reminders: what needs a decision, what's being watched, and what's done (IMPL M7.7). */
export function RemindersPanel(): React.JSX.Element {
  const { reminders, loaded, demoSeconds } = useReminders()
  const report = useAudit((s) => s.report)
  const currency = report?.meta.currency ?? 'USD'
  const today = localDay()
  return (
    <div className="flex flex-col gap-4">
      <p className="m-0 flex items-start gap-2.5 rounded-tile bg-panel px-4 py-3.5 text-sm leading-[1.45]">
        <Info aria-hidden size={18} className="mt-px shrink-0" />
        <span>
          {byPlatform(
            'Reminders fire while SlothSpend is open. If it was closed, you’ll get them the next time you open it.',
            'SlothSpend keeps checking your reminders even when this tab is closed. New ones wait in the bell, and pop up while SlothSpend is open in a tab.'
          )}
        </span>
      </p>
      {reminders.length > 0 && <BrowserNotifications />}
      {report && <LatestStatement meta={report.meta} />}
      {!loaded ? (
        <p className="m-0 flex items-center gap-2 text-sm text-muted">
          <Spinner /> Loading reminders…
        </p>
      ) : reminders.length === 0 ? (
        <Card radius="section" className="flex flex-col gap-2 p-8">
          <h2 className="m-0 text-h2">No reminders yet.</h2>
          <p className="m-0 text-sm text-text-2">
            Open a finding and choose <strong>Remind me</strong>. SlothSpend reminds you before it
            renews — it never cancels anything.
          </p>
        </Card>
      ) : (
        GROUPS.map(([group, title]) => {
          const rows = reminders.filter((r) => r.group === group)
          if (!rows.length) return null
          return (
            <section key={group} aria-labelledby={`grp-${group}`} className="flex flex-col gap-3">
              <h2 id={`grp-${group}`} className="mt-2 mb-0 text-h3">
                {title}
              </h2>
              {rows.map((r) => (
                <ReminderCard
                  key={r.series_id}
                  r={r}
                  currency={currency}
                  today={today}
                  demoSeconds={demoSeconds}
                />
              ))}
            </section>
          )
        })
      )}
    </div>
  )
}
