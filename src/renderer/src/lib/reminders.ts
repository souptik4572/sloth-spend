// Reminder actions (IMPL M7.4–M7.9): Remind me, Keep it, Snooze, Stop, I cancelled it, and the inbox.
import { useAudit } from '../auditStore'
import { SAMPLE_FILES } from './audit'
import { useReminders } from '../remindersStore'
import { useApp } from '../store'
import {
  createReminder,
  errorMessage,
  getSettings,
  listReminders,
  markAllNoticesRead,
  markNoticeRead,
  notificationInbox,
  reminderAction,
  type ReminderAction
} from './api'
import { dateShort } from './format'
import { toast } from './toast'
import type { Notice, ReminderResult } from './types'
import { askForNotifications } from './notify'
import { isWeb } from './platform'

const store = useReminders.getState

export async function loadReminders(): Promise<void> {
  try {
    const [reminders, settings] = await Promise.all([listReminders(), getSettings()])
    store().setReminders(reminders)
    store().setDemoSeconds(settings.demo_compress_seconds)
  } catch {
    /* engine restarting: the next poll fills it in */
  }
}

export async function loadInbox(): Promise<void> {
  try {
    store().setInbox(await notificationInbox())
  } catch {
    /* as above */
  }
}

/** After any change: the list, the open drawer, and (when the engine re-scored) the report. */
async function settle(result: ReminderResult): Promise<void> {
  if (result.report) useAudit.getState().showReport(result.report)
  useAudit.getState().refreshDrawer()
  await loadReminders()
}

function whenText(result: ReminderResult): string {
  const demo = store().demoSeconds
  if (demo) return `in ${demo} s (demo)`
  const on = result.reminder?.remind_on
  return on ? `for ${dateShort(on)}` : 'for later'
}

export async function remindMe(seriesId: number, daysBefore?: number): Promise<boolean> {
  // The click that asks to be reminded is the moment to ask for browser notifications (web only, once).
  if (isWeb()) void askForNotifications()
  try {
    const result = await createReminder(seriesId, daysBefore)
    await settle(result)
    toast(`Reminder set ${whenText(result)}. It only reminds you — nothing is cancelled.`)
    return true
  } catch (err) {
    toast(errorMessage(err, 'The reminder couldn’t be set.'))
    return false
  }
}

async function act(
  seriesId: number,
  action: ReminderAction,
  body?: { days?: number; cancelled_on?: string }
): Promise<ReminderResult | null> {
  try {
    const result = await reminderAction(seriesId, action, body)
    await settle(result)
    return result
  } catch (err) {
    await loadReminders() // the phase moved on (409): show where it is now
    toast(errorMessage(err, 'That change couldn’t be saved.'))
    return null
  }
}

export async function keepIt(seriesId: number): Promise<void> {
  if (await act(seriesId, 'keep')) toast('Kept. No more reminders for this one.')
}

export async function snooze(seriesId: number, days: number): Promise<void> {
  const result = await act(seriesId, 'snooze', { days })
  if (result) toast(`Snoozed. We’ll remind you again ${whenText(result)}.`)
}

export async function stopReminder(seriesId: number): Promise<void> {
  if (await act(seriesId, 'stop')) toast('Reminder stopped.')
}

/** "I cancelled it" (any time): SlothSpend then checks the next statement for the charge. */
export async function cancelledIt(seriesId: number, cancelledOn: string): Promise<boolean> {
  const result = await act(seriesId, 'cancelled', { cancelled_on: cancelledOn })
  if (!result) return false
  toast('Marked as cancelled. SlothSpend will check your next statement.')
  useAudit.getState().closeDrawer()
  useApp.getState().setTab('reminders')
  return true
}

export async function markRead(id: number): Promise<void> {
  store().markReadLocal(id)
  try {
    await markNoticeRead(id)
  } catch {
    /* it stays unread on the engine; the next inbox load shows that */
  }
}

export async function markAllRead(): Promise<void> {
  store().markReadLocal('all')
  try {
    await markAllNoticesRead()
  } catch {
    await loadInbox()
  }
}

/** A notification was clicked (OS or inbox): bring the window forward, show Reminders, mark it read. */
export function openNotice(n: Notice): void {
  void window.sloth.focusWindow()
  useApp.getState().setTab('reminders')
  void markRead(n.id)
}

/** "Cancelled on" default (IMPL M7.9): today, or the day after the statement for the bundled demo data. */
export function defaultCancelledOn(today: Date = new Date()): string {
  const report = useAudit.getState().report
  const latest = report?.meta.imports[report.meta.imports.length - 1]
  if (report && latest && Object.values(SAMPLE_FILES).includes(latest.file_name)) {
    const d = new Date(`${report.meta.report_date}T12:00:00Z`)
    d.setUTCDate(d.getUTCDate() + 1)
    return d.toISOString().slice(0, 10)
  }
  return localDay(today)
}

export function localDay(d: Date = new Date()): string {
  const pad = (n: number): string => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
