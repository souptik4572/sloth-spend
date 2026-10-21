import { FileText, Lock, Upload } from 'lucide-react'
import { Card } from '../ui/Card'
import { DemoDataMenu } from './DemoDataMenu'
import { FilePicker } from './FilePicker'
import { dateRange } from '../../lib/format'
import type { ReportMeta } from '../../lib/types'

/** D-Main: which statement(s) the report covers, and the way to add a newer one. */
export function StatementBar({ meta }: { meta: ReportMeta }): React.JSX.Element {
  const imports = meta.imports
  const latest = imports[imports.length - 1]
  const rows = imports.reduce((n, i) => n + (i.row_count ?? 0), 0)
  const title =
    imports.length > 1
      ? `${imports.length} statements · latest ${latest.file_name}`
      : latest?.file_name
  const period = imports.length ? dateRange(imports[0].period_start, latest.period_end) : ''
  return (
    <Card
      as="section"
      radius="tile"
      aria-label="Statement"
      className="flex flex-wrap items-center gap-3 py-3 pr-3 pl-4"
    >
      <div className="flex min-w-0 flex-[1_1_300px] items-center gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-raised">
          <FileText aria-hidden size={18} />
        </span>
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">{title}</div>
          <div className="text-xs leading-[1.65] text-muted">
            {rows} rows · {period} · {meta.currency} ·{' '}
            <span className="inline-flex items-center gap-1 align-middle">
              <Lock aria-hidden size={12} strokeWidth={2.2} />
              Your statement never leaves this computer.
            </span>
          </div>
        </div>
      </div>
      <FilePicker variant="soft" icon={Upload}>
        Import newer statement
      </FilePicker>
      <DemoDataMenu size="sm" />
    </Card>
  )
}
