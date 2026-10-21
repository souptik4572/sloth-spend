import { TopBar } from '../components/shell/TopBar'
import { WorkspaceTabs } from '../components/shell/WorkspaceTabs'
import { LimitedBanner } from '../components/shell/LimitedBanner'
import { ChatPane } from '../components/chat/ChatPane'
import { Card } from '../components/ui/Card'
import { useApp } from '../store'

/** Workspace shell (D-Import / D-Main): 62 % main pane + 38 % Ask Sloth aside. */
export function Workspace(): React.JSX.Element {
  const tab = useApp((s) => s.tab)
  return (
    <div className="flex min-h-screen flex-col bg-bg text-ink">
      <TopBar />
      <div className="flex flex-1 flex-wrap items-start gap-4 px-4 pb-4">
        <main className="box-border flex min-w-0 flex-[62_1_560px] flex-col gap-6 px-4 pt-1 pb-12">
          <WorkspaceTabs />
          <LimitedBanner />
          {tab === 'audit' ? (
            // M5 replaces this with the drop zone, mapper, progress and report.
            <Card radius="section" className="flex flex-col gap-2 p-8">
              <h1 className="m-0 text-h2">Nothing to audit yet.</h1>
              <p className="m-0 text-sm text-muted">
                Importing a statement arrives with the audit milestones. The engine and models above
                are live.
              </p>
            </Card>
          ) : (
            <Card radius="section" className="flex flex-col gap-2 p-8">
              <h1 className="m-0 text-h2">No reminders yet.</h1>
              <p className="m-0 text-sm text-muted">
                Open a finding and choose Remind me. Reminders fire while SlothSpend is open.
              </p>
            </Card>
          )}
        </main>
        <ChatPane />
      </div>
    </div>
  )
}
