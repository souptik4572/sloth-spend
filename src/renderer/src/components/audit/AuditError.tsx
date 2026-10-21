import { TriangleAlert } from 'lucide-react'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { useAudit } from '../../auditStore'
import { leaveError } from '../../lib/audit'
import { STAGE_LABELS } from '../../lib/ui-derive'
import type { StageId } from '../../lib/types'

/** The audit stopped: say where and why in a sentence, and offer a way back. */
export function AuditError(): React.JSX.Element {
  const error = useAudit((s) => s.error)
  const hasReport = useAudit((s) => s.report !== null)
  const stage =
    error?.stage && error.stage in STAGE_LABELS ? STAGE_LABELS[error.stage as StageId] : null
  return (
    <Card
      as="section"
      radius="section"
      role="alert"
      className="flex flex-col items-start gap-4 p-8"
    >
      <span className="flex size-10 items-center justify-center rounded-full border-2 border-ink bg-raised">
        <TriangleAlert aria-hidden size={18} />
      </span>
      <div>
        <h1 className="m-0 text-h2">The audit stopped.</h1>
        {stage && <p className="mt-1 mb-0 text-sm text-muted">During: {stage}</p>}
      </div>
      <p className="m-0 max-w-[60ch] text-base">{error?.message}</p>
      <Button variant="solid" onClick={leaveError}>
        {hasReport ? 'Back to the report' : 'Back'}
      </Button>
    </Card>
  )
}
