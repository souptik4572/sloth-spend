// Who is signed in. The session itself is an httpOnly cookie the page can't read; /api/auth/me tells us.
import { create } from 'zustand'
import { api, ApiError, type User } from './api'

export type SessionStatus = 'loading' | 'signed-out' | 'signed-in' | 'offline'

interface SessionState {
  status: SessionStatus
  user: User | null
  load: () => Promise<void>
  signedIn: (user: User) => void
  signedOut: () => void
  logOut: () => Promise<void>
}

export const useSession = create<SessionState>((set) => ({
  status: 'loading',
  user: null,
  load: async () => {
    try {
      const { user } = await api<{ user: User }>('GET', '/auth/me')
      adoptUser(user)
      set({ status: 'signed-in', user })
    } catch (err) {
      set({
        status: err instanceof ApiError && err.status === 0 ? 'offline' : 'signed-out',
        user: null
      })
    }
  },
  signedIn: (user) => {
    adoptUser(user)
    set({ status: 'signed-in', user })
  },
  signedOut: () => set({ status: 'signed-out', user: null }),
  logOut: async () => {
    await api('POST', '/auth/logout').catch(() => undefined) // the cookie is cleared server-side either way
    leave()
  }
}))

const USER_KEY = 'sloth.user'
const NOTICE_KEY = 'sloth.notice'
const KEEP = new Set(['sloth.theme', USER_KEY])

/**
 * One browser can be shared: when a different account signs in, the workspace's per-person keys (Ask Sloth's
 * conversation id, the newest notification already shown) start fresh. The theme is the browser's, so it stays.
 */
export function adoptUser(user: User): void {
  try {
    if (localStorage.getItem(USER_KEY) === user.id) return
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith('sloth.') && !KEEP.has(key)) localStorage.removeItem(key)
    }
    localStorage.setItem(USER_KEY, user.id)
  } catch {
    /* storage unavailable: nothing was kept to leak either */
  }
}

/**
 * Back to Log in with a clean page: a full load drops every in-memory report, chat and reminder, so nothing of
 * this account lingers in the tab. `notice` shows on the Log in screen.
 */
export function leave(notice?: string): void {
  try {
    if (notice) sessionStorage.setItem(NOTICE_KEY, notice)
  } catch {
    /* the notice is a nicety */
  }
  window.location.assign('/login')
}

/** The message `leave` handed to Log in, once. */
export function takeNotice(): string | null {
  try {
    const notice = sessionStorage.getItem(NOTICE_KEY)
    sessionStorage.removeItem(NOTICE_KEY)
    return notice
  } catch {
    return null
  }
}

/** "Asha Rao" → "AR" (the account button). */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  return (
    ((parts[0]?.[0] ?? '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase() ||
    '?'
  )
}

const pending = new Map<string, Promise<unknown>>()

/**
 * Runs a one-time call once per key, however often a screen mounts (React StrictMode mounts twice in dev,
 * and a second "use this link" call would fail because the first already used it).
 */
export function once<T>(key: string, fn: () => Promise<T>): Promise<T> {
  if (!pending.has(key)) pending.set(key, fn())
  return pending.get(key) as Promise<T>
}
