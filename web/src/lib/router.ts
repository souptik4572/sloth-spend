// A small history router: real paths, because email links open /verify/confirm, /login/link and /reset.
import { createElement, useEffect, useSyncExternalStore, type AnchorHTMLAttributes } from 'react'

const listeners = new Set<() => void>()
const notify = (): void => listeners.forEach((fn) => fn())
window.addEventListener('popstate', notify)

function subscribe(fn: () => void): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

const snapshot = (): string => window.location.pathname + window.location.search

export interface Location {
  path: string
  query: URLSearchParams
  /** What the previous screen handed over (e.g. the email just signed up with). Lost on reload. */
  state: Record<string, unknown>
}

export function useLocation(): Location {
  useSyncExternalStore(subscribe, snapshot)
  const state = window.history.state
  return {
    path: window.location.pathname.replace(/\/+$/, '') || '/',
    query: new URLSearchParams(window.location.search),
    state: state && typeof state === 'object' ? state : {}
  }
}

export function navigate(
  to: string,
  { replace = false, state = {} }: { replace?: boolean; state?: Record<string, unknown> } = {}
): void {
  window.history[replace ? 'replaceState' : 'pushState'](state, '', to)
  notify()
}

/**
 * Reads a one-time token from the address bar, then removes it so it isn't left in history, bookmarks or a
 * screenshot. Every page is also served with Referrer-Policy: no-referrer.
 */
export function takeToken(): string {
  const params = new URLSearchParams(window.location.search)
  const token = params.get('token') ?? ''
  if (token) {
    params.delete('token')
    const rest = params.toString()
    window.history.replaceState(
      window.history.state,
      '',
      window.location.pathname + (rest ? `?${rest}` : '')
    )
  }
  return token
}

export function Redirect({ to }: { to: string }): null {
  useEffect(() => navigate(to, { replace: true }), [to])
  return null
}

export interface LinkProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  to: string
  state?: Record<string, unknown>
}

/** An <a href> that navigates in place (and still opens in a new tab with a modifier key). */
export function Link({ to, state, onClick, ...rest }: LinkProps): React.JSX.Element {
  return createElement('a', {
    ...rest,
    href: to,
    onClick: (e: React.MouseEvent<HTMLAnchorElement>) => {
      onClick?.(e)
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)
        return
      e.preventDefault()
      navigate(to, { state })
    }
  })
}
