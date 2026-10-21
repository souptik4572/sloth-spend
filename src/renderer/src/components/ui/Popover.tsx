import { useEffect, useRef, type ReactNode } from 'react'
import { cn } from '../../lib/cn'

export interface PopoverProps {
  open: boolean
  onClose: () => void
  /** The trigger, rendered inline; the panel is positioned under it. */
  anchor: ReactNode
  align?: 'start' | 'end'
  width?: number
  label?: string
  className?: string
  children: ReactNode
}

/** A panel anchored under its trigger. Closes on Esc or a click outside. Used by the inbox (D-Notif) and menus. */
export function Popover({
  open,
  onClose,
  anchor,
  align = 'end',
  width = 440,
  label,
  className,
  children
}: PopoverProps): React.JSX.Element {
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent): void => {
      if (root.current && !root.current.contains(e.target as Node)) onClose()
    }
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open, onClose])

  return (
    <div ref={root} className="relative inline-flex">
      {anchor}
      {open && (
        <div
          role={label ? 'dialog' : undefined}
          aria-label={label}
          className={cn(
            'absolute top-[calc(100%+8px)] z-30 box-border max-w-[calc(100vw-32px)]',
            'animate-[sloth-rise_300ms_ease-out]',
            align === 'end' ? 'right-0' : 'left-0',
            className
          )}
          style={{ width }}
        >
          {children}
        </div>
      )}
    </div>
  )
}
