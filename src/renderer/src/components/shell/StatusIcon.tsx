import { Check, Hourglass, TriangleAlert, type LucideIcon } from 'lucide-react'
import { Spinner } from '../ui/Spinner'
import { cn } from '../../lib/cn'
import type { Tone } from '../../lib/status'

/** 40 px status circle for a Boot row. `actionIcon` says what the fix is (download, key…). */
export function StatusIcon({
  tone,
  actionIcon: ActionIcon
}: {
  tone: Tone
  actionIcon: LucideIcon
}): React.JSX.Element {
  const base = 'flex size-10 shrink-0 items-center justify-center rounded-full'
  switch (tone) {
    case 'ready':
      return (
        <span className={cn(base, 'bg-success-tint text-success')}>
          <Check aria-hidden size={20} strokeWidth={2.6} />
        </span>
      )
    case 'working':
      return (
        <span className={cn(base, 'bg-panel text-ink')}>
          <Spinner size={20} />
        </span>
      )
    case 'action':
      return (
        <span className={cn(base, 'bg-accent text-on-accent')}>
          <ActionIcon aria-hidden size={20} strokeWidth={2.2} />
        </span>
      )
    case 'error':
      return (
        <span className={cn(base, 'border-2 border-ink bg-raised text-ink')}>
          <TriangleAlert aria-hidden size={18} strokeWidth={2.2} />
        </span>
      )
    case 'waiting':
      return (
        <span className={cn(base, 'bg-panel text-muted')}>
          <Hourglass aria-hidden size={18} strokeWidth={2} />
        </span>
      )
  }
}
