import { useState } from 'react'
import { Info, RefreshCw } from 'lucide-react'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { rescore } from '../../lib/audit'
import { tabpfnLabel } from '../../lib/status'
import type { ReportMeta } from '../../lib/types'
import { useApp } from '../../store'

/**
 * IMPL M5.10: the report was scored by an older scorer than the one now loaded — e.g. made in limited mode
 * before TabPFN v2 finished downloading, or before a key upgraded it to TabPFN-3.5.
 */
export function RescoreBanner({ meta }: { meta: ReportMeta }): React.JSX.Element | null {
  const health = useApp((s) => s.health)
  const [busy, setBusy] = useState(false)
  const model = health?.tabpfn.status === 'ready' ? health.tabpfn.model : null
  if (!model || model === meta.scorer) return null
  return (
    <Card radius="tile" role="status" className="flex flex-wrap items-center gap-3 py-3 pr-3 pl-4">
      <Info aria-hidden size={18} className="shrink-0" />
      <p className="m-0 min-w-0 flex-[1_1_300px] text-sm">
        <strong className="font-medium">{tabpfnLabel(health)} is ready.</strong> This report was
        scored with {meta.scorer === 'heuristic' ? 'a simple rule' : 'an earlier model'}.
      </p>
      <Button
        variant="solid"
        icon={RefreshCw}
        disabled={busy}
        onClick={() => {
          setBusy(true)
          void rescore().finally(() => setBusy(false))
        }}
      >
        Re-score with TabPFN
      </Button>
    </Card>
  )
}
