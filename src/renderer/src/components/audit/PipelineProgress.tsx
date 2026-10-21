import { useEffect, useState } from 'react'
import { Check, Lock } from 'lucide-react'
import { Card } from '../ui/Card'
import { ProgressBar } from '../ui/ProgressBar'
import { SourceChip, type Source } from '../ui/SourceChip'
import { Spinner } from '../ui/Spinner'
import type { RunState } from '../../auditStore'
import { cn } from '../../lib/cn'
import { elapsed } from '../../lib/format'
import type { Health, StageId } from '../../lib/types'
import { STAGE_LABELS, STAGE_ORDER } from '../../lib/ui-derive'
import { useApp } from '../../store'

/** Which source a stage will use, before it reports one (from /health), or after (from its event). */
function stageSource(
  stage: StageId,
  reported: string | null | undefined,
  health: Health | null
): Source | null {
  const gemmaUp = health?.ollama.status === 'ready'
  const tabpfn =
    health?.tabpfn.status === 'ready' ? (health.tabpfn.model ?? 'heuristic') : 'heuristic'
  switch (stage) {
    case 'normalize':
      return reported === 'rule' || (!reported && !gemmaUp) ? 'rules' : 'gemma'
    case 'score':
    case 'forecast':
      return ((reported as Source) ?? tabpfn) as Source
    case 'summary':
      return reported === 'template' || (!reported && !gemmaUp) ? 'template' : 'gemma'
    default:
      return null
  }
}

/** D-Progress: nine plain-language steps, the model behind each, and an elapsed timer. */
export function PipelineProgress({ run }: { run: RunState }): React.JSX.Element {
  const health = useApp((s) => s.health)
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])

  const isDone = (id: StageId): boolean => {
    const ev = run.stages[id]
    return !!ev && ev.done >= ev.total && ev.total > 0
  }
  const completed = STAGE_ORDER.filter(isDone).length
  const current = STAGE_ORDER.find((id) => !isDone(id)) ?? 'done'
  const currentIndex = STAGE_ORDER.indexOf(current)

  return (
    <Card
      as="section"
      radius="section"
      aria-labelledby="prog-h"
      className="flex flex-col gap-7 p-8"
    >
      <div className="flex flex-wrap items-end gap-x-6 gap-y-4">
        <div className="min-w-0 flex-[1_1_360px]">
          <p className="mt-0 mb-2 text-sm font-medium text-muted">
            {run.file}
            {run.rows !== null && ` · ${run.rows} rows`}
          </p>
          <h1 id="prog-h" className="m-0 text-display-xl">
            Reading your statement.
          </h1>
          <p className="mt-3 mb-0 text-lead text-text-2">
            Slowly and carefully, on this computer. Usually under a minute.
          </p>
        </div>
        <p className="m-0 text-sm font-medium text-muted tabular-nums">
          {elapsed(now - run.startedAt)} elapsed
        </p>
      </div>

      <ProgressBar
        value={completed}
        max={STAGE_ORDER.length}
        label="Audit progress"
        valueText={`Step ${Math.min(currentIndex + 1, 9)} of 9: ${STAGE_LABELS[current].toLowerCase()}`}
        className="h-2.5"
      />

      <ol aria-label="Audit steps" className="m-0 flex list-none flex-col gap-1 p-0">
        {STAGE_ORDER.map((id) => {
          const ev = run.stages[id]
          const done = isDone(id)
          const active = id === current && !done
          const source = stageSource(id, ev?.source, health)
          const status =
            id === 'parse' && ev?.note
              ? ev.note
              : id === 'normalize' && done && ev
                ? `${ev.total} merchant descriptions`
                : id === 'normalize' && active
                  ? 'Batches of 25, cached for next time'
                  : ''
          return (
            <li
              key={id}
              aria-current={active ? 'step' : undefined}
              className={cn(
                'flex items-start gap-3.5 rounded-tile px-3.5 py-3',
                active && 'bg-raised'
              )}
            >
              <span
                className={cn(
                  'flex size-7 shrink-0 items-center justify-center rounded-full',
                  done && 'bg-solid text-on-solid',
                  active && 'border-2 border-accent-edge bg-accent text-on-accent',
                  !done && !active && 'border-2 border-faint'
                )}
              >
                {done && <Check aria-hidden size={14} strokeWidth={3} />}
                {active && <Spinner size={14} />}
              </span>
              <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
                  <span
                    className={cn(
                      'text-base',
                      done || active ? 'font-medium text-ink' : 'text-muted'
                    )}
                  >
                    {STAGE_LABELS[id]}
                  </span>
                  {source && <SourceChip source={source} />}
                  {status && <span className="text-xs text-muted">{status}</span>}
                </div>
                {active && id === 'normalize' && ev && ev.total > 0 && (
                  <div className="flex items-center gap-3">
                    <ProgressBar
                      value={ev.done}
                      max={ev.total}
                      label="Merchants cleaned"
                      className="h-1.5 max-w-80 flex-1"
                    />
                    <span className="text-sm font-medium tabular-nums">
                      {source === 'gemma' ? 'Gemma cleaned' : 'Named'} {ev.done} / {ev.total}{' '}
                      merchants
                    </span>
                  </div>
                )}
              </div>
            </li>
          )
        })}
      </ol>

      <p className="m-0 flex items-center gap-2 text-sm font-medium">
        <Lock aria-hidden size={16} strokeWidth={2.2} />
        Your statement never leaves this computer.
      </p>
    </Card>
  )
}
