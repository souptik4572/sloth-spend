import type { HTMLAttributes, ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '../../lib/cn'

export type ChipVariant =
  | 'solid' // duplicate charge, "Still charged"
  | 'accent' // price rise, "3 days left"
  | 'tint' // overlap, possible annual, model chips
  | 'outline' // zombie suspect, "Reminded · 1 of 3"
  | 'dashed' // low confidence, heuristic/template sources
  | 'success' // Verified
  | 'raised' // category in table rows
  | 'panel' // category in the drawer

export type ChipSize = 22 | 24 | 28

const variants: Record<ChipVariant, string> = {
  solid: 'bg-solid text-on-solid border border-solid',
  accent: 'bg-accent text-on-accent border border-accent',
  tint: 'bg-tint text-ink border border-tint',
  outline: 'bg-transparent text-ink border border-line-strong',
  dashed: 'bg-transparent text-muted border border-dashed border-subtle',
  success: 'bg-success-tint text-success border border-success-tint',
  raised: 'bg-raised text-ink border border-line',
  panel: 'bg-panel text-ink border border-panel'
}

const sizes: Record<ChipSize, string> = {
  22: 'h-[22px] px-2 text-xs gap-1',
  24: 'h-6 px-[9px] text-xs gap-1',
  28: 'h-7 px-3 text-sm gap-1.5'
}

export interface ChipProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: ChipVariant
  size?: ChipSize
  icon?: LucideIcon
  strong?: boolean
  children: ReactNode
}

export function Chip({
  variant = 'tint',
  size = 24,
  icon: Icon,
  strong,
  className,
  children,
  ...rest
}: ChipProps): React.JSX.Element {
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center rounded-full whitespace-nowrap',
        strong ? 'font-bold' : 'font-medium',
        variants[variant],
        sizes[size],
        className
      )}
      {...rest}
    >
      {Icon && <Icon aria-hidden size={size === 28 ? 14 : 12} strokeWidth={2.4} />}
      {children}
    </span>
  )
}
