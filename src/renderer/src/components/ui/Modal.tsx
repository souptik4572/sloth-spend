import { useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useFocusTrap } from '../../lib/a11y'
import { cn } from '../../lib/cn'

export interface ModalProps {
  open: boolean
  onClose: () => void
  labelledBy: string
  maxWidth?: number
  className?: string
  children: ReactNode
}

/** Centered dialog over a scrim (D-Settings): max 800 px, 64 px from the top, scrolls with the overlay. */
export function Modal({
  open,
  onClose,
  labelledBy,
  maxWidth = 800,
  className,
  children
}: ModalProps): React.JSX.Element | null {
  const panel = useRef<HTMLElement>(null)
  useFocusTrap(panel, open, onClose)
  if (!open) return null
  return createPortal(
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div
        aria-hidden
        className="fixed inset-0 bg-scrim animate-[sloth-fade-in_300ms_ease-out]"
        onClick={onClose}
      />
      <div className="relative mx-auto box-border w-full px-4 py-16" style={{ maxWidth }}>
        <section
          ref={panel}
          role="dialog"
          aria-modal="true"
          aria-labelledby={labelledBy}
          tabIndex={-1}
          className={cn(
            'rounded-section bg-bg px-10 pt-8 pb-10 shadow-[0_2px_4px_var(--shadow)] outline-none',
            'animate-[sloth-rise_400ms_ease-out]',
            className
          )}
        >
          {children}
        </section>
      </div>
    </div>,
    document.body
  )
}
