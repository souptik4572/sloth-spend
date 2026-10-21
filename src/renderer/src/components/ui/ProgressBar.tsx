import { cn } from '../../lib/cn'

export interface ProgressBarProps {
  value: number
  max?: number
  label: string
  valueText?: string
  className?: string
}

/** 8 px track (--tint) with an ink fill. */
export function ProgressBar({
  value,
  max = 100,
  label,
  valueText,
  className
}: ProgressBarProps): React.JSX.Element {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={Math.round(value)}
      aria-valuetext={valueText}
      className={cn('h-2 overflow-hidden rounded-full bg-tint', className)}
    >
      <div
        className="h-full rounded-full bg-ink transition-[width] duration-500 ease-out"
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

export interface ScoreBarProps {
  /** 0–1 recurring probability. */
  prob: number
  width?: number | string
  className?: string
}

/** 6 px score bar: ink when ≥ 50 %, subtle below. Decorative — pair it with the number. */
export function ScoreBar({ prob, width = 48, className }: ScoreBarProps): React.JSX.Element {
  return (
    <span
      aria-hidden
      className={cn('block h-1.5 overflow-hidden rounded-full bg-tint', className)}
      style={{ width }}
    >
      <span
        className={cn('block h-full rounded-full', prob >= 0.5 ? 'bg-ink' : 'bg-subtle')}
        style={{ width: `${Math.round(prob * 100)}%` }}
      />
    </span>
  )
}
