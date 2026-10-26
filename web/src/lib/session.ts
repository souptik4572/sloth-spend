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
      set({ status: 'signed-in', user })
    } catch (err) {
      set({
        status: err instanceof ApiError && err.status === 0 ? 'offline' : 'signed-out',
        user: null
      })
    }
  },
  signedIn: (user) => set({ status: 'signed-in', user }),
  signedOut: () => set({ status: 'signed-out', user: null }),
  logOut: async () => {
    await api('POST', '/auth/logout').catch(() => undefined) // the cookie is cleared server-side either way
    set({ status: 'signed-out', user: null })
  }
}))

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
