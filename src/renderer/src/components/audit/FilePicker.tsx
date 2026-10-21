import { useRef, type ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { Button, type ButtonSize, type ButtonVariant } from '../ui/Button'
import { importFile } from '../../lib/audit'

/** A button that opens the OS file dialog for a CSV statement and imports what's chosen. */
export function FilePicker({
  variant,
  size,
  icon,
  children
}: {
  variant: ButtonVariant
  size?: ButtonSize
  icon?: LucideIcon
  children: ReactNode
}): React.JSX.Element {
  const input = useRef<HTMLInputElement>(null)
  return (
    <>
      <Button variant={variant} size={size} icon={icon} onClick={() => input.current?.click()}>
        {children}
      </Button>
      <input
        ref={input}
        type="file"
        accept=".csv,text/csv"
        className="hidden"
        tabIndex={-1}
        aria-hidden
        onChange={(e) => {
          const file = e.target.files?.[0]
          e.target.value = '' // choosing the same file again still fires
          if (file) void importFile(file)
        }}
      />
    </>
  )
}
