// Notification polling (IMPL M7.5): every 5 s, new notices go to the inbox and raise an OS notification.
import { notificationInbox, notificationsSince } from './api'
import { loadInbox, loadReminders, openNotice } from './reminders'
import { useReminders } from '../remindersStore'
import type { Notice } from './types'

const LAST_KEY = 'sloth.lastToastId'
const POLL_MS = 5000
const REMINDERS_EVERY = 6 // also refresh the reminder list every 30 s (expiries change phases silently)

function readLast(): number {
  try {
    return Number(localStorage.getItem(LAST_KEY)) || 0
  } catch {
    return 0
  }
}

function saveLast(id: number): void {
  try {
    localStorage.setItem(LAST_KEY, String(id))
  } catch {
    /* without storage a reload may raise a notice twice; the inbox still marks it read */
  }
}

function raise(n: Notice): void {
  if (typeof Notification === 'undefined' || Notification.permission === 'denied') return
  const note = new Notification(n.title, { body: n.body, silent: false })
  note.onclick = () => openNotice(n)
}

// The newest notice already raised. Module-level so "Delete all local data" can reset it.
let last = readLast()

/** After the data is deleted, notice ids start again from 1. */
export function resetNotifications(): void {
  last = 0
  saveLast(0)
}

/** Start polling; returns a stop function. */
export function startNotifications(): () => void {
  last = readLast()
  let polls = 0
  let stopped = false
  let timer: ReturnType<typeof setTimeout> | undefined

  const poll = async (): Promise<void> => {
    try {
      const fresh = await notificationsSince(last)
      if (stopped) return
      if (fresh.length) {
        // Anything newer than the last one raised is new to this person — including catch-up notices the
        // engine wrote on its first tick, before this window was open.
        fresh.forEach(raise)
        last = Math.max(...fresh.map((n) => n.id))
        saveLast(last)
        await Promise.all([loadInbox(), loadReminders()])
      } else if (++polls % REMINDERS_EVERY === 0) {
        await loadReminders()
      }
    } catch {
      /* engine restarting: try again on the next poll */
    }
    if (!stopped) timer = setTimeout(() => void poll(), POLL_MS)
  }

  void (async () => {
    try {
      const inbox = await notificationInbox()
      useReminders.getState().setInbox(inbox)
      // After "Delete all local data" ids start again from 1: don't let the old high-water mark hide them.
      const newest = inbox.length ? inbox[0].id : 0
      if (newest < last) {
        last = newest
        saveLast(last)
      }
    } catch {
      /* the first poll retries */
    }
    await loadReminders()
    if (!stopped) void poll()
  })()

  return () => {
    stopped = true
    clearTimeout(timer)
  }
}
