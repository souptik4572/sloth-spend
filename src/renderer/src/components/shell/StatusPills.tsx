import { CircleAlert, CircleCheck } from 'lucide-react'
import { Spinner } from '../ui/Spinner'
import { cn } from '../../lib/cn'
import {
  engineView,
  gemmaLabel,
  gemmaView,
  tabpfnLabel,
  tabpfnView,
  type RowView
} from '../../lib/status'
import { useApp } from '../../store'

const pill =
  'flex h-9 items-center gap-1.5 rounded-full border border-line pr-3.5 pl-2.5 text-sm font-medium whitespace-nowrap'

function PillIcon({ view }: { view: RowView }): React.JSX.Element {
  if (view.tone === 'ready')
    return <CircleCheck aria-hidden size={16} strokeWidth={2.4} className="text-success" />
  if (view.tone === 'working') return <Spinner size={16} />
  return <CircleAlert aria-hidden size={16} strokeWidth={2.4} className="text-muted" />
}

/** Engine / Gemma · local / TabPFN pills (each names the model in use). A pill that isn't green opens setup (Boot). */
export function StatusPills(): React.JSX.Element {
  const { engine, exitCode, health, setScreen } = useApp()
  const items: Array<[string, RowView]> = [
    ['Engine', engineView(engine, exitCode)],
    [`${gemmaLabel(health)} · local`, gemmaView(health, engine)],
    [tabpfnLabel(health), tabpfnView(health, engine)]
  ]
  return (
    <ul aria-label="Local models" className="m-0 flex list-none flex-wrap gap-2 p-0">
      {items.map(([label, view]) => (
        <li key={label}>
          {view.tone === 'ready' ? (
            <span className={pill} title={view.detail}>
              <PillIcon view={view} />
              {label}
            </span>
          ) : (
            <button
              type="button"
              onClick={() => setScreen('boot')}
              title={`${view.status}. ${view.detail}`}
              aria-label={`${label}: ${view.status}. Open setup`}
              className={cn(
                pill,
                'cursor-pointer bg-transparent text-ink hover:border-line-strong'
              )}
            >
              <PillIcon view={view} />
              {label}
            </button>
          )}
        </li>
      ))}
    </ul>
  )
}
