import { Check } from 'lucide-react'
import { cn } from '../../lib/cn'

export type StepState = 'done' | 'ok' | 'current' | 'alert' | 'skip' | 'todo'

export interface Step {
  label: string
  sub?: string
  state: StepState
}

const dot: Record<StepState, string> = {
  done: 'bg-solid text-on-solid',
  ok: 'bg-success text-bg',
  current: 'bg-accent text-on-accent border-2 border-accent-edge',
  alert: 'bg-raised text-ink border-2 border-ink',
  skip: 'bg-transparent border-2 border-dashed border-ink',
  todo: 'border-2 border-subtle'
}

const STATE_TEXT: Record<StepState, string> = {
  done: 'done',
  ok: 'done',
  current: 'current step',
  alert: 'needs attention',
  skip: 'skipped',
  todo: 'not yet'
}

export interface StepperProps {
  steps: Step[]
  label?: string
  /** Pink card behind it: todo dots fill with accent instead of raised. */
  onAccent?: boolean
  className?: string
}

/** The 4-step reminder stepper (D-Reminders): Watching → Reminded → Kept / You cancelled → Verified. */
export function Stepper({
  steps,
  label = 'Progress',
  onAccent,
  className
}: StepperProps): React.JSX.Element {
  return (
    <ol aria-label={label} className={cn('m-0 flex list-none flex-wrap gap-y-3 p-0', className)}>
      {steps.map((s, i) => {
        const last = i === steps.length - 1
        const passed = s.state !== 'todo' && s.state !== 'current'
        return (
          <li
            key={s.label}
            className={cn('flex items-start gap-2', last ? 'flex-none' : 'min-w-[150px] flex-1')}
          >
            <span
              className={cn(
                'flex size-6 shrink-0 items-center justify-center rounded-full',
                dot[s.state],
                s.state === 'todo' && (onAccent ? 'bg-accent' : 'bg-raised')
              )}
            >
              {(s.state === 'done' || s.state === 'ok') && (
                <Check aria-hidden size={14} strokeWidth={3} />
              )}
              {s.state === 'alert' && (
                <span aria-hidden className="text-sm leading-none font-bold">
                  !
                </span>
              )}
            </span>
            <span className="flex flex-col">
              <span
                className={cn(
                  'text-sm leading-[1.6] whitespace-nowrap',
                  s.state === 'todo' || s.state === 'skip'
                    ? 'font-normal text-text-2'
                    : 'font-medium text-ink'
                )}
              >
                {s.label}
                <span className="sr-only">, {STATE_TEXT[s.state]}</span>
              </span>
              {s.sub && <span className="text-xs text-muted">{s.sub}</span>}
            </span>
            {!last && (
              <span
                aria-hidden
                className={cn(
                  'mx-2 mt-[11px] h-0.5 min-w-3 flex-1 rounded-sm',
                  passed ? 'bg-ink' : 'bg-line-strong'
                )}
              />
            )}
          </li>
        )
      })}
    </ol>
  )
}
