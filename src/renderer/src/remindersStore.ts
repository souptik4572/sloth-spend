import { create } from 'zustand'
import type { Notice, Reminder } from './lib/types'

/** Reminders (D-Reminders) and the notification inbox (D-Notif), kept in step by lib/notify.ts. */
interface RemindersState {
  reminders: Reminder[]
  loaded: boolean
  inbox: Notice[]
  /** Settings › demo compression; 0 = off. */
  demoSeconds: number
  setReminders: (reminders: Reminder[]) => void
  setInbox: (inbox: Notice[]) => void
  setDemoSeconds: (n: number) => void
  markReadLocal: (id: number | 'all') => void
}

export const useReminders = create<RemindersState>((set) => ({
  reminders: [],
  loaded: false,
  inbox: [],
  demoSeconds: 0,
  setReminders: (reminders) => set({ reminders, loaded: true }),
  setInbox: (inbox) => set({ inbox }),
  setDemoSeconds: (demoSeconds) => set({ demoSeconds }),
  markReadLocal: (id) =>
    set((s) => ({
      inbox: s.inbox.map((n) =>
        (id === 'all' || n.id === id) && !n.read_at
          ? { ...n, read_at: new Date().toISOString() }
          : n
      )
    }))
}))

export const unreadCount = (s: { inbox: Notice[] }): number =>
  s.inbox.filter((n) => !n.read_at).length

/** The reminder for a series, if it's still in progress (not ended). */
export function activeReminder(reminders: Reminder[], seriesId: number): Reminder | null {
  return reminders.find((r) => r.series_id === seriesId && r.group !== 'done') ?? null
}
