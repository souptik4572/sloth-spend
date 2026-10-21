import { useEffect, useRef, type RefObject } from 'react'

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])'

/**
 * While `active`: moves focus into `ref`, keeps Tab inside it, calls `onEscape` on Esc,
 * and gives focus back to whatever had it before when it deactivates.
 */
export function useFocusTrap(
  ref: RefObject<HTMLElement | null>,
  active: boolean,
  onEscape?: () => void
): void {
  // Read the latest callback without re-running the effect (which would steal focus on every render).
  const escape = useRef(onEscape)
  useEffect(() => {
    escape.current = onEscape
  })

  useEffect(() => {
    if (!active || !ref.current) return
    const root = ref.current
    const previous = document.activeElement as HTMLElement | null
    const items = (): HTMLElement[] => Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE))
    ;(items()[0] ?? root).focus()

    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape' && escape.current) {
        e.stopPropagation()
        escape.current()
        return
      }
      if (e.key !== 'Tab') return
      const list = items()
      if (list.length === 0) return
      const first = list[0]
      const last = list[list.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
    root.addEventListener('keydown', onKey)
    return () => {
      root.removeEventListener('keydown', onKey)
      previous?.focus?.()
    }
  }, [ref, active])
}
