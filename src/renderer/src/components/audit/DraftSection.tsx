import { useEffect, useRef, useState } from 'react'
import { Mail, RotateCcw } from 'lucide-react'
import { DraftCard } from '../chat/DraftCard'
import { Button, type ButtonVariant } from '../ui/Button'
import { Spinner } from '../ui/Spinner'
import { errorMessage, stream } from '../../lib/api'
import { byPlatform } from '../../lib/platform'
import type { DraftDone, DraftKind } from '../../lib/types'

type State =
  | { phase: 'idle' }
  | { phase: 'streaming'; text: string }
  | { phase: 'done'; draft: DraftDone }
  | { phase: 'error'; message: string }

/**
 * A drawer draft (IMPL M6.10): the button streams `/series/{id}/draft` into a DraftCard with Copy and
 * "Draft … again". Gemma writes it when it's running; otherwise the template does (Template chip).
 */
export function DraftSection({
  seriesId,
  kind,
  label,
  variant = 'soft'
}: {
  seriesId: number
  kind: DraftKind
  label: string
  variant?: ButtonVariant
}): React.JSX.Element {
  const [state, setState] = useState<State>({ phase: 'idle' })
  const abort = useRef<AbortController | null>(null)
  useEffect(() => () => abort.current?.abort(), [])

  const start = (): void => {
    abort.current?.abort()
    const ctl = new AbortController()
    abort.current = ctl
    let text = ''
    setState({ phase: 'streaming', text })
    stream(
      `/series/${seriesId}/draft`,
      { kind },
      {
        token: (d) => {
          text += (d as { text: string }).text
          setState({ phase: 'streaming', text })
        },
        done: (d) => setState({ phase: 'done', draft: d as DraftDone })
      },
      ctl.signal
    ).catch((err: unknown) => {
      if (!ctl.signal.aborted) {
        setState({ phase: 'error', message: errorMessage(err, 'The draft couldn’t be written.') })
      }
    })
  }

  if (state.phase === 'done' || state.phase === 'streaming') {
    const streaming = state.phase === 'streaming'
    return (
      <DraftCard
        text={streaming ? state.text : state.draft.text}
        source={streaming ? 'gemma' : state.draft.source}
        title={streaming ? undefined : state.draft.title}
        streaming={streaming}
      >
        {!streaming && (
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" icon={RotateCcw} onClick={start}>
              {label} again
            </Button>
          </div>
        )}
        {streaming && !state.text && (
          <p className="m-0 flex items-center gap-2 text-sm text-muted">
            <Spinner /> {byPlatform('Writing on this computer…', 'Writing…')}
          </p>
        )}
      </DraftCard>
    )
  }
  return (
    <div className="flex flex-col items-start gap-2">
      <Button variant={variant} icon={Mail} onClick={start}>
        {label}
      </Button>
      {state.phase === 'error' && (
        <p role="alert" className="m-0 text-sm font-medium">
          {state.message}
        </p>
      )}
    </div>
  )
}
