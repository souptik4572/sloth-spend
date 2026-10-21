import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

export interface SwitchProps {
  label: ReactNode
  description?: ReactNode
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
  className?: string
}

/** A real checkbox with role="switch" (D-Settings), so Tab and Space work with no extra code. */
export function Switch({
  label,
  description,
  checked,
  onChange,
  disabled,
  className
}: SwitchProps): React.JSX.Element {
  return (
    <label
      className={cn(
        'flex cursor-pointer items-center gap-4',
        disabled && 'cursor-not-allowed opacity-60',
        className
      )}
    >
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2 text-base">{label}</span>
        {description && (
          <span className="block text-xs leading-[1.65] text-muted">{description}</span>
        )}
      </span>
      <input
        type="checkbox"
        role="switch"
        className="peer sr-only"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span
        aria-hidden
        className={cn(
          'relative inline-flex h-7 w-12 shrink-0 items-center rounded-full border transition-colors duration-300 ease-out',
          'peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-ink',
          checked ? 'border-solid bg-solid' : 'border-line-strong bg-tint'
        )}
      >
        <span
          className={cn(
            'absolute size-5 rounded-full transition-[left,background-color] duration-300 ease-out',
            checked
              ? 'left-[24px] bg-on-solid'
              : 'left-[3px] bg-raised shadow-[0_1px_2px_var(--shadow)]'
          )}
        />
      </span>
    </label>
  )
}
