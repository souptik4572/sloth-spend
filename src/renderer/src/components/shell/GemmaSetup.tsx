import { useRef, useState } from 'react'
import { Download, ExternalLink, RefreshCw } from 'lucide-react'
import { Button } from '../ui/Button'
import { ProgressBar } from '../ui/ProgressBar'
import { stream } from '../../lib/api'
import { gigabytes } from '../../lib/format'
import {
  RateMeter,
  emptyPull,
  etaLabel,
  pullTotals,
  reducePull,
  type PullEvent
} from '../../lib/pull'
import { refreshHealth } from '../../lib/useHealthPolling'
import { useApp } from '../../store'

const OLLAMA_DOWNLOAD = 'https://ollama.com/download'
const DEFAULT_MODEL = 'gemma4:e4b'
const LIGHT_MODEL = 'gemma4:e2b'

const linkButton =
  'inline-flex cursor-pointer items-center gap-1 border-0 bg-transparent p-0 font-medium text-ink underline underline-offset-2 hover:text-link-hover'

/**
 * The fixes on the Boot Gemma row (D-Boot, IMPL M4.11). Any installed Gemma model counts as ready
 * (IMPL §2 #20), so the download is only offered when Ollama has none.
 */
export function GemmaSetup(): React.JSX.Element | null {
  const status = useApp((s) => s.health?.ollama.status)
  const [pulling, setPulling] = useState<string | null>(null)
  const [progress, setProgress] = useState(emptyPull)
  const [eta, setEta] = useState('')
  const [error, setError] = useState<string | null>(null)
  const abort = useRef<AbortController | null>(null)

  const pull = async (model: string): Promise<void> => {
    setPulling(model)
    setError(null)
    setProgress(emptyPull())
    setEta('')
    abort.current = new AbortController()
    // Events arrive one at a time, so plain locals are enough to fold them; React state only renders them.
    let current = emptyPull()
    const meter = new RateMeter()
    let failed: string | null = null
    try {
      await stream(
        '/setup/ollama/pull',
        { model },
        {
          progress: (d) => {
            current = reducePull(current, d as PullEvent)
            const { completed, total } = pullTotals(current)
            meter.push(Date.now(), completed)
            setProgress(current)
            setEta(etaLabel(total - completed, meter.rate()))
          },
          error: (d) => {
            failed = (d as { message: string }).message
          }
        },
        abort.current.signal
      )
    } catch {
      failed = failed ?? 'The download stopped. Check that Ollama is still running, then try again.'
    }
    setPulling(null)
    if (failed) setError(failed)
    await refreshHealth()
  }

  if (pulling) {
    const { completed, total } = pullTotals(progress)
    return (
      <div className="flex flex-col gap-1.5">
        <p className="m-0 text-sm font-medium">
          {progress.status === 'Downloading' ? `Downloading ${pulling}` : progress.status}
        </p>
        <ProgressBar
          value={completed}
          max={total || 1}
          label={`${pulling} download`}
          valueText={total ? `${gigabytes(completed)} of ${gigabytes(total)}` : undefined}
        />
        <div className="flex justify-between gap-3 text-xs text-muted tabular-nums">
          <span>{total ? `${gigabytes(completed)} of ${gigabytes(total)}` : 'Starting…'}</span>
          <span>{eta}</span>
        </div>
      </div>
    )
  }

  const errorLine = error && (
    <p role="alert" className="m-0 text-sm font-medium">
      {error}
    </p>
  )

  if (status === 'unreachable' || status === 'outdated') {
    return (
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap gap-2">
          <Button
            variant="solid"
            iconRight={ExternalLink}
            onClick={() => void window.sloth.openExternal(OLLAMA_DOWNLOAD)}
          >
            {status === 'outdated' ? 'Update Ollama' : 'Install Ollama'}
          </Button>
          <Button variant="soft" icon={RefreshCw} onClick={() => void refreshHealth()}>
            Check again
          </Button>
        </div>
        {errorLine}
      </div>
    )
  }

  if (status === 'missing_model') {
    return (
      <div className="flex flex-col gap-2">
        <div>
          <Button variant="solid" icon={Download} onClick={() => void pull(DEFAULT_MODEL)}>
            Download Gemma 4 (about 5 GB)
          </Button>
        </div>
        {errorLine}
        <p className="m-0 text-sm">
          8 GB of memory or less?{' '}
          <button type="button" className={linkButton} onClick={() => void pull(LIGHT_MODEL)}>
            Use {LIGHT_MODEL} instead
          </button>
        </p>
      </div>
    )
  }

  return errorLine || null
}
