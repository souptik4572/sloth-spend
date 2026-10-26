// Notification polling (IMPL M7.5): every 5 s, new notices go to the inbox and raise an OS notification.
// On the web (WEB-IMPL W6) the pop-up needs the browser's permission, and a tab you're looking at gets a toast
// instead. Pop-ups are tagged per notice, so two open tabs can't show the same one twice, and a catch-up after
// a long absence shows at most MAX_POPUPS plus one summary.
import { notificationInbox, notificationsSince } from './api'
import { isWeb } from './platform'
import { loadInbox, loadReminders, openNotice } from './reminders'
import { toast } from './toast'
import { useApp } from '../store'
import { useReminders } from '../remindersStore'
import type { Notice } from './types'

const LAST_KEY = 'sloth.lastToastId'
const POLL_MS = 5000
const REMINDERS_EVERY = 6 // also refresh the reminder list every 30 s (expiries change phases silently)
const MAX_POPUPS = 3

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

export type NotifyPermission = NotificationPermission | 'unsupported'

export function notifyPermission(): NotifyPermission {
  return typeof Notification === 'undefined' ? 'unsupported' : Notification.permission
}

/**
 * The web asks once, from a click ("Remind me", or the Reminders tab's card): browsers only show the prompt
 * then. The desktop never asks — the app is allowed to notify.
 */
export async function askForNotifications(): Promise<NotifyPermission> {
  const now = notifyPermission()
  if (now !== 'default') return now
  try {
    return await Notification.requestPermission()
  } catch {
    return notifyPermission()
  }
}

function mayPopUp(): boolean {
  const p = notifyPermission()
  return isWeb() ? p === 'granted' : p !== 'unsupported' && p !== 'denied'
}

function raise(n: Notice): void {
  const note = new Notification(n.title, {
    body: n.body,
    silent: false,
    tag: `sloth-notice-${n.id}`
  })
  note.onclick = () => openNotice(n)
}

/** Which new notices pop up: the newest `max`; the older rest are counted into one summary. */
export function popupPlan(fresh: Notice[], max = MAX_POPUPS): { show: Notice[]; more: number } {
  const byAge = [...fresh].sort((a, b) => a.id - b.id)
  return { show: byAge.slice(-max), more: Math.max(0, byAge.length - max) }
}

function announce(fresh: Notice[]): void {
  if (!fresh.length) return
  const newest = fresh.reduce((a, b) => (b.id > a.id ? b : a))
  // Someone looking at SlothSpend in this tab: a toast, not a pop-up over the page they're reading.
  if (isWeb() && document.visibilityState === 'visible' && document.hasFocus()) {
    toast(
      fresh.length === 1
        ? newest.title
        : `${newest.title} — and ${fresh.length - 1} more in the bell`
    )
    return
  }
  if (!mayPopUp()) return
  const { show, more } = popupPlan(fresh)
  show.forEach(raise)
  if (more) {
    const summary = new Notification(`${more} more from SlothSpend`, {
      body: 'Open the bell in SlothSpend to see them all.',
      tag: 'sloth-notice-more'
    })
    summary.onclick = () => {
      void window.sloth.focusWindow()
      useApp.getState().setTab('reminders')
    }
  }
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
      last = Math.max(last, readLast()) // another open tab may have shown some already
      const fresh = await notificationsSince(last)
      if (stopped) return
      if (fresh.length) {
        // Anything newer than the last one shown is new to this person — including catch-up notices the
        // engine wrote while SlothSpend was closed. Re-read the mark: another tab may have just shown them.
        const shown = readLast()
        announce(fresh.filter((n) => n.id > shown))
        last = Math.max(shown, ...fresh.map((n) => n.id))
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
