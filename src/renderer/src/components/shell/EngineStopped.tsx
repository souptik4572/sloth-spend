import { useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'
import { useApp } from '../../store'

/**
 * The engine stopped while the workspace was open (IMPL M9.1): say so, show the last lines of its log, and
 * offer a restart. Statements and reminders are safe in the local database either way.
 */
export function EngineStopped(): React.JSX.Element {
  const engine = useApp((s) => s.engine)
  const exitCode = useApp((s) => s.exitCode)
  const stopped = engine === 'stopped'
  const [logs, setLogs] = useState<string[]>([])
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    if (!stopped) return
    void window.sloth.engineLogs().then(setLogs)
  }, [stopped])

  const restart = (): void => {
    setDismissed(false)
    useApp.getState().engineRestarting()
    void window.sloth.restartEngine()
  }

  return (
    <Modal
      open={stopped && !dismissed}
      onClose={() => setDismissed(true)}
      labelledBy="eng-h"
      maxWidth={640}
    >
      <div className="flex flex-col gap-4">
        <h2 id="eng-h" className="m-0 text-h2">
          The local engine stopped.
        </h2>
        <p className="m-0 text-base">
          SlothSpend’s engine on this computer exited
          {exitCode === null ? '' : ` (exit code ${exitCode})`}. Your statements, reminders and
          settings are safe — they’re in the local database. Restart it to carry on.
        </p>
        {logs.length > 0 && (
          <pre
            aria-label="Last lines of the engine log"
            className="m-0 max-h-60 overflow-auto rounded-xl bg-card px-3 py-2.5 font-mono text-xs leading-normal break-words whitespace-pre-wrap text-text-2"
          >
            {logs.join('\n')}
          </pre>
        )}
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="ghost" onClick={() => setDismissed(true)}>
            Not now
          </Button>
          <Button variant="solid" icon={RefreshCw} onClick={restart}>
            Restart engine
          </Button>
        </div>
      </div>
    </Modal>
  )
}
