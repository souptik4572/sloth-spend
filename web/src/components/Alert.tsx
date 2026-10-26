import type { ReactNode } from 'react'
import { TriangleAlert } from 'lucide-react'

/** The pink error note above a form (Log in, artboard 12). Announced when it appears. */
export function Alert({ children }: { children: ReactNode }): React.JSX.Element {
  return (
    <p
      role="alert"
      data-theme="light"
      className="m-0 flex items-start gap-2.5 rounded-tile bg-accent px-4 py-3.5 text-small text-ink"
    >
      <TriangleAlert aria-hidden size={18} strokeWidth={2.2} className="mt-px shrink-0" />
      <span>{children}</span>
    </p>
  )
}
