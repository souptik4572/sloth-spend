import { useEffect, useState, type ReactNode } from 'react'
import { Cpu, Download, Key, Lock, RefreshCw } from 'lucide-react'
import { Wordmark } from '../components/brand/Logo'
import { SlothHanging } from '../components/brand/SlothHanging'
import { ThemeToggle } from '../components/shell/ThemeToggle'
import { StatusIcon } from '../components/shell/StatusIcon'
import { PriorKeyForm } from '../components/shell/PriorKeyForm'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { cn } from '../lib/cn'
import {
  engineView,
  firstActionable,
  gemmaLabel,
  gemmaView,
  limitedSummary,
  tabpfnLabel,
  tabpfnView,
  type RowView
} from '../lib/status'
import { fullyReady, useApp } from '../store'

interface RowProps {
  title: string
  view: RowView
  actionIcon: typeof Cpu
  ringed: boolean
  children?: ReactNode
}

function CheckRow({ title, view, actionIcon, ringed, children }: RowProps): React.JSX.Element {
  return (
    <li
      className={cn(
        'flex items-start gap-4 rounded-tile bg-raised p-5 transition-shadow duration-300 ease-out',
        ringed && 'shadow-[inset_0_0_0_2px_var(--ink)]'
      )}
    >
      <StatusIcon tone={view.tone} actionIcon={actionIcon} />
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <div>
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h3 className="m-0 text-base leading-tight font-bold">{title}</h3>
            <span
              className={cn(
                'text-sm font-medium',
                view.tone === 'ready' && 'text-success',
                view.tone === 'waiting' && 'text-muted'
              )}
            >
              {view.status}
            </span>
          </div>
          <p className="mt-1 mb-0 text-sm text-muted">{view.detail}</p>
        </div>
        {children}
      </div>
    </li>
  )
}

/** First run and setup (D-Boot): live status for Engine, Gemma (whichever is installed) and TabPFN (v2, or 3.5 with a key). */
export function Boot(): React.JSX.Element {
  const { version, engine, exitCode, health, setScreen, engineRestarting } = useApp()
  const [logs, setLogs] = useState<string[]>([])
  const ready = fullyReady(health)

  const rows = [engineView(engine, exitCode), gemmaView(health, engine), tabpfnView(health, engine)]
  const ring = firstActionable(rows)

  // Everything green: go straight to the workspace (IMPL M1.8).
  useEffect(() => {
    if (engine !== 'ok' || !ready) return
    const t = setTimeout(() => setScreen('workspace'), 600)
    return () => clearTimeout(t)
  }, [engine, ready, setScreen])

  useEffect(() => {
    if (engine === 'stopped') void window.sloth.engineLogs().then(setLogs)
  }, [engine])

  const restart = (): void => {
    engineRestarting()
    void window.sloth.restartEngine()
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg text-ink">
      <header className="flex min-h-[72px] flex-wrap items-center gap-x-4 gap-y-3 px-6 py-3.5">
        <span className="mr-auto">
          <Wordmark />
        </span>
        <span className="text-xs text-muted">
          {version ? `v${version} · ` : ''}no account needed
        </span>
        <ThemeToggle />
      </header>

      <main className="mx-auto box-border flex w-full max-w-[1280px] flex-1 flex-wrap items-stretch gap-6 px-6 pt-2 pb-10">
        <Card
          as="section"
          tone="accent"
          radius="hero"
          aria-labelledby="boot-h"
          className="flex min-w-0 flex-[1_1_460px] flex-col justify-between gap-8 p-12"
        >
          <div>
            <h1 id="boot-h" className="m-0 text-display-xl">
              Slow and steady.
            </h1>
            <p className="mt-4 mb-0 max-w-[30ch] text-lead">
              Getting your local models ready. After this one-time setup, nothing leaves this
              computer.
            </p>
          </div>
          <SlothHanging className="self-center" />
          <p className="m-0 flex items-center gap-2 text-sm font-medium">
            <Lock aria-hidden size={16} strokeWidth={2.2} className="shrink-0" />
            SlothSpend informs, never acts. It never cancels anything or contacts anyone for you.
          </p>
        </Card>

        <Card
          as="section"
          radius="section"
          aria-labelledby="check-h"
          className="flex min-w-0 flex-[1_1_520px] flex-col gap-6 p-10"
        >
          <div>
            <h2 id="check-h" className="m-0 text-h2">
              Getting ready
            </h2>
            <p className="mt-1.5 mb-0 text-sm text-muted">
              Three things need to be ready. Each one can be fixed from here.
            </p>
          </div>

          <ol aria-live="polite" className="m-0 flex list-none flex-col gap-3 p-0">
            <CheckRow title="Engine" view={rows[0]} actionIcon={Cpu} ringed={ring === 0}>
              {engine === 'stopped' && (
                <>
                  {logs.length > 0 && (
                    <pre className="m-0 max-h-60 overflow-auto rounded-xl bg-card px-3 py-2.5 font-mono text-xs leading-normal break-words whitespace-pre-wrap text-text-2">
                      {logs.join('\n')}
                    </pre>
                  )}
                  <div>
                    <Button variant="solid" icon={RefreshCw} onClick={restart}>
                      Restart engine
                    </Button>
                  </div>
                </>
              )}
            </CheckRow>
            <CheckRow
              title={gemmaLabel(health)}
              view={rows[1]}
              actionIcon={Download}
              ringed={ring === 1}
            />
            <CheckRow
              title={tabpfnLabel(health)}
              view={rows[2]}
              actionIcon={Key}
              ringed={ring === 2}
            >
              <PriorKeyForm />
            </CheckRow>
          </ol>

          {engine === 'ok' && !ready && (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-3 pt-1">
              <Button variant="outline" size="lg" onClick={() => setScreen('workspace')}>
                Continue in limited mode
              </Button>
              <p className="m-0 flex-[1_1_240px] text-xs leading-[1.65] text-muted">
                Limited mode uses {limitedSummary(health)}. Every result is labelled so you know.
              </p>
            </div>
          )}
        </Card>
      </main>
    </div>
  )
}
