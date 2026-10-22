import { useEffect } from 'react'
import { TopBar } from '../components/shell/TopBar'
import { WorkspaceTabs } from '../components/shell/WorkspaceTabs'
import { LimitedBanner } from '../components/shell/LimitedBanner'
import { ChatPane } from '../components/chat/ChatPane'
import { Spinner } from '../components/ui/Spinner'
import { AuditError } from '../components/audit/AuditError'
import { BurnChart } from '../components/audit/BurnChart'
import { ColumnMapper } from '../components/audit/ColumnMapper'
import { FindingsTable } from '../components/audit/FindingsTable'
import { ImportEmpty } from '../components/audit/ImportEmpty'
import { MerchantDrawer } from '../components/audit/MerchantDrawer'
import { PipelineProgress } from '../components/audit/PipelineProgress'
import { RescoreBanner } from '../components/audit/RescoreBanner'
import { StatementBar } from '../components/audit/StatementBar'
import { SummaryCards, SummaryNarrative } from '../components/audit/SummaryCards'
import { RemindersPanel } from '../components/reminders/RemindersPanel'
import { SettingsModal } from '../components/settings/SettingsModal'
import { EngineStopped } from '../components/shell/EngineStopped'
import { useAudit } from '../auditStore'
import { loadReport } from '../lib/audit'
import { startNotifications } from '../lib/notify'
import { useApp } from '../store'

function AuditTab(): React.JSX.Element {
  const { phase, report, pending, run } = useAudit()
  switch (phase) {
    case 'loading':
      return (
        <p className="m-0 flex items-center gap-2 text-sm text-muted">
          <Spinner /> Opening your report…
        </p>
      )
    case 'empty':
      return <ImportEmpty />
    case 'mapping':
      return pending ? <ColumnMapper key={pending.import_id} pending={pending} /> : <ImportEmpty />
    case 'running':
      return run ? <PipelineProgress run={run} /> : <ImportEmpty />
    case 'error':
      return <AuditError />
    case 'report':
      return report ? (
        <>
          <StatementBar meta={report.meta} />
          <RescoreBanner meta={report.meta} />
          <SummaryNarrative meta={report.meta} />
          <SummaryCards meta={report.meta} />
          <BurnChart report={report} />
          <FindingsTable report={report} />
        </>
      ) : (
        <ImportEmpty />
      )
  }
}

/** Workspace shell (D-Import / D-Main): 62 % main pane + 38 % Ask Sloth aside. */
export function Workspace(): React.JSX.Element {
  const tab = useApp((s) => s.tab)
  const engine = useApp((s) => s.engine)
  const phase = useAudit((s) => s.phase)

  // Load the saved report once the engine answers (and again after an engine restart).
  useEffect(() => {
    if (engine === 'ok' && phase === 'loading') void loadReport()
  }, [engine, phase])

  // Reminders and notifications (IMPL M7.5): poll while the engine is up.
  useEffect(() => {
    if (engine !== 'ok') return
    return startNotifications()
  }, [engine])

  // A file dropped outside the drop zone must never navigate the window away.
  useEffect(() => {
    const stop = (e: DragEvent): void => e.preventDefault()
    document.addEventListener('dragover', stop)
    document.addEventListener('drop', stop)
    return () => {
      document.removeEventListener('dragover', stop)
      document.removeEventListener('drop', stop)
    }
  }, [])

  return (
    <div className="flex min-h-screen flex-col bg-bg text-ink">
      <TopBar />
      <div className="flex flex-1 flex-wrap items-start gap-4 px-4 pb-4">
        <main className="box-border flex min-w-0 flex-[62_1_560px] flex-col gap-6 px-4 pt-1 pb-12">
          <WorkspaceTabs />
          <LimitedBanner />
          {tab === 'audit' ? <AuditTab /> : <RemindersPanel />}
        </main>
        <ChatPane />
      </div>
      <MerchantDrawer />
      <SettingsModal />
      <EngineStopped />
    </div>
  )
}
