// Desktop (Electron) or web (WEB-IMPL §2.4): the same renderer runs in both, and the bridge says which.
import type { ComponentType } from 'react'

export function isWeb(): boolean {
  return typeof window !== 'undefined' && window.sloth?.kind === 'web'
}

/** The desktop wording or its web counterpart: "on this computer" isn't true on the web. */
export function byPlatform<T>(desktop: T, web: T): T {
  return isWeb() ? web : desktop
}

/** Pieces only the web app has, plugged into shared screens (the account menu in the top bar). */
export const slots: { account?: ComponentType } = {}
