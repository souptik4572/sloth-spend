import { useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useFocusTrap } from '../../lib/a11y'
import { cn } from '../../lib/cn'

export interface SheetProps {
  open: boolean
  onClose: () => void
  labelledBy: string
  className?: string
  children: ReactNode
}

/** Right-hand sheet over a scrim (D-Drawer): max 620 px, rounded on the left, scrolls on its own. */
export function Sheet({
  open,
  onClose,
  labelledBy,
  className,
  children
}: SheetProps): React.JSX.Element | null {
  const panel = useRef<HTMLElement>(null)
  useFocusTrap(panel, open, onClose)
  if (!open) return null
  return createPortal(
    <div className="fixed inset-0 z-40">
      <div
        aria-hidden
        className="absolute inset-0 bg-scrim animate-[sloth-fade-in_300ms_ease-out]"
        onClick={onClose}
      />
      <aside
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        tabIndex={-1}
        className={cn(
          'absolute top-0 right-0 bottom-0 box-border flex w-full max-w-[620px] flex-col gap-8 overflow-y-auto',
          'rounded-l-section bg-bg px-8 pt-7 pb-10 shadow-[0_2px_4px_var(--shadow)] outline-none',
          'animate-[sloth-slide-in_400ms_ease-out]',
          className
        )}
      >
        {children}
      </aside>
    </div>,
    document.body
  )
}
