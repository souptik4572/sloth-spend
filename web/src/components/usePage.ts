import { useEffect, useRef } from 'react'

let firstScreen = true

/**
 * Sets the tab title and, after the first screen, moves focus to the new screen's heading so keyboard and
 * screen-reader users land at the top of what changed (the heading has tabIndex -1).
 */
export function usePage(title: string, headingId: string): void {
  const done = useRef(false)
  useEffect(() => {
    document.title = `${title} · SlothSpend`
    if (done.current) return
    done.current = true
    if (firstScreen) {
      firstScreen = false
      return
    }
    document.getElementById(headingId)?.focus()
  }, [title, headingId])
}
