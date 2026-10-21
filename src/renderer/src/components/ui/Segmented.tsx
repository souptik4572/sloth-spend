import type { LucideIcon } from 'lucide-react'
import { cn } from '../../lib/cn'

export interface SegmentOption<T extends string> {
  value: T
  label: string
  icon?: LucideIcon
}

export interface SegmentedProps<T extends string> {
  label: string
  value: T
  options: SegmentOption<T>[]
  onChange: (value: T) => void
  className?: string
}

/** Pill toggle group with aria-pressed buttons (burn chart "Subscriptions / All recurring", Settings › Appearance). */
export function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
  className
}: SegmentedProps<T>): React.JSX.Element {
  return (
    <div
      role="group"
      aria-label={label}
      className={cn('inline-flex gap-1 rounded-full bg-raised p-1', className)}
    >
      {options.map((o) => {
        const on = o.value === value
        const Icon = o.icon
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={on}
            onClick={() => onChange(o.value)}
            className={cn(
              'inline-flex h-11 cursor-pointer items-center gap-2 rounded-full px-4 text-sm font-medium',
              'transition-[background-color,color] duration-300 ease-out',
              on ? 'bg-solid text-on-solid' : 'bg-transparent text-ink hover:bg-ink/5'
            )}
          >
            {Icon && <Icon aria-hidden size={16} />}
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
