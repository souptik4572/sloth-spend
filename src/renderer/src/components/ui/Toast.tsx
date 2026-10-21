import { useEffect } from 'react'
import { X } from 'lucide-react'
import { useToast } from '../../lib/toast'

/** Renders the current toast (lib/toast.ts) at the bottom left; it fades after 5 s. */
export function Toaster(): React.JSX.Element {
  const { message, id, hide } = useToast()
  useEffect(() => {
    if (!message) return
    const t = setTimeout(hide, 5000)
    return () => clearTimeout(t)
  }, [message, id, hide])
  return (
    <div
      role="status"
      aria-live="polite"
      className="pointer-events-none fixed bottom-6 left-6 z-[60]"
    >
      {message && (
        <div
          key={id}
          className="pointer-events-auto flex max-w-[440px] animate-[sloth-rise_300ms_ease-out] items-center gap-3 rounded-tile bg-solid py-3 pr-2 pl-4 text-sm text-on-solid shadow-[0_2px_4px_var(--shadow)]"
        >
          <span className="flex-1">{message}</span>
          <button
            type="button"
            aria-label="Dismiss"
            onClick={hide}
            className="flex size-9 cursor-pointer items-center justify-center rounded-full bg-transparent text-on-solid hover:bg-on-solid/10"
          >
            <X aria-hidden size={16} />
          </button>
        </div>
      )}
    </div>
  )
}
