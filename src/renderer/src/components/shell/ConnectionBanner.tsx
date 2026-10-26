import { RefreshCw, WifiOff } from 'lucide-react'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { isWeb } from '../../lib/platform'
import { refreshHealth } from '../../lib/useHealthPolling'
import { useApp } from '../../store'

/**
 * SlothSpend Web lost its server (WEB-IMPL §1, "Engine stopped" on the desktop): say so calmly. Health polling
 * keeps retrying every second, and the banner leaves by itself when the server answers.
 */
export function ConnectionBanner(): React.JSX.Element | null {
  const lost = useApp((s) => s.everOk && s.engine !== 'ok')
  if (!isWeb() || !lost) return null
  return (
    <Card radius="tile" className="flex flex-wrap items-center gap-3 py-3 pr-3 pl-4" role="status">
      <WifiOff aria-hidden size={20} className="shrink-0" />
      <p className="m-0 min-w-0 flex-[1_1_300px] text-sm">
        <strong className="font-medium">Can’t reach SlothSpend right now.</strong> Trying again —
        your data is safe on the server.
      </p>
      <Button variant="soft" icon={RefreshCw} onClick={() => void refreshHealth()}>
        Try now
      </Button>
    </Card>
  )
}
