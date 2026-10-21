import { useState, type ReactNode } from 'react'
import {
  Ban,
  Bell,
  BellPlus,
  CalendarCheck,
  CalendarClock,
  CopyPlus,
  Ghost,
  Layers,
  Lock,
  MessageCircle,
  Moon,
  SlidersHorizontal,
  Sun,
  ThumbsUp,
  Trash2,
  TrendingUp,
  TriangleAlert,
  Upload,
  X
} from 'lucide-react'
import { Button, IconButton } from '../components/ui/Button'
import { Chip } from '../components/ui/Chip'
import { SourceChip } from '../components/ui/SourceChip'
import { Card } from '../components/ui/Card'
import { ProgressBar, ScoreBar } from '../components/ui/ProgressBar'
import { Spinner } from '../components/ui/Spinner'
import { Switch } from '../components/ui/Switch'
import { Field, Select, TextInput } from '../components/ui/Field'
import { Stepper } from '../components/ui/Stepper'
import { Modal } from '../components/ui/Modal'
import { Sheet } from '../components/ui/Sheet'
import { Menu } from '../components/ui/Menu'
import { Popover } from '../components/ui/Popover'
import { Hint } from '../components/ui/Hint'
import { CopyButton } from '../components/ui/CopyButton'
import { Segmented } from '../components/ui/Segmented'
import { Logo, SlothAvatar, Wordmark } from '../components/brand/Logo'
import { SlothHanging } from '../components/brand/SlothHanging'
import { ThemeToggle } from '../components/shell/ThemeToggle'
import { readPref, setPref, type ThemePref } from '../lib/theme'
import { money, pctChip } from '../lib/format'

function Section({ title, children }: { title: string; children: ReactNode }): React.JSX.Element {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="m-0 text-h3">{title}</h2>
      {children}
    </section>
  )
}

const DRAFT = `Subject: Please cancel my IronTrap Fitness membership

Hello IronTrap Fitness team,

Please cancel my membership and stop all future charges, including the renewal due on Nov 5, 2026.

Thank you,
[Your name]`

/** Dev-only gallery of every primitive (IMPL M0.7). Open with #/kitchen-sink. */
export function KitchenSink(): React.JSX.Element {
  const [themePref, setThemePref] = useState<ThemePref>(readPref)
  const [chart, setChart] = useState<'subs' | 'all'>('subs')
  const [demo, setDemo] = useState(true)
  const [traces, setTraces] = useState(false)
  const [modal, setModal] = useState(false)
  const [sheet, setSheet] = useState(false)
  const [inbox, setInbox] = useState(false)

  return (
    <div className="min-h-screen bg-bg text-ink">
      <header className="flex min-h-[72px] flex-wrap items-center gap-x-4 gap-y-3 px-6 py-3.5">
        <span className="mr-auto">
          <Wordmark />
        </span>
        <span className="text-xs text-muted">Kitchen sink · dev only</span>
        <ThemeToggle />
        <Popover
          open={inbox}
          onClose={() => setInbox(false)}
          label="Notifications"
          anchor={
            <IconButton
              icon={Bell}
              label="Notifications, 2 unread"
              onClick={() => setInbox((o) => !o)}
            />
          }
        >
          <div className="flex flex-col gap-3 rounded-card bg-bg p-5 shadow-[0_2px_4px_var(--shadow)]">
            <h2 className="m-0 text-h3">Notifications</h2>
            <p className="m-0 text-sm text-muted">
              Popover anchored to the bell. Esc or click outside closes it.
            </p>
          </div>
        </Popover>
        <IconButton icon={SlidersHorizontal} label="Settings" onClick={() => setModal(true)} />
      </header>

      <main className="mx-auto flex max-w-[1280px] flex-col gap-10 px-6 pt-2 pb-16">
        <nav aria-label="Workspace" className="flex flex-wrap items-baseline gap-x-7 gap-y-1">
          <span className="text-display-tab text-ink">Audit</span>
          <span className="text-display-tab text-subtle">Reminders</span>
        </nav>

        <Section title="Type scale">
          <div className="flex flex-col gap-3">
            <p className="m-0 text-display-xl">Slow and steady.</p>
            <p className="m-0 text-stat">{money(1979.86)}</p>
            <p className="m-0 text-h2">Findings</p>
            <p className="m-0 text-h3">Monthly subscription spend</p>
            <p className="m-0 max-w-[62ch] text-lead">
              You pay {money(1979.86)} a month in recurring charges, and {money(87.46)} of that is
              subscriptions.
            </p>
            <p className="m-0">Body 16 / 1.5 — the default.</p>
            <p className="m-0 text-small text-muted">Small 14 / 1.45, muted.</p>
            <p className="m-0 text-caption text-muted">Caption 12 / 1.45.</p>
            <code className="font-mono text-xs">find_duplicate_charges(&quot;IronTrap&quot;)</code>
          </div>
        </Section>

        <Section title="Buttons">
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="solid" size="lg" icon={Upload}>
              Choose CSV file
            </Button>
            <Button variant="outline" size="lg">
              Load sample statement
            </Button>
            <Button variant="solid" icon={CalendarCheck}>
              I cancelled it
            </Button>
            <Button variant="soft" icon={BellPlus}>
              Remind me
            </Button>
            <Button variant="soft" icon={ThumbsUp}>
              Keep
            </Button>
            <Button variant="soft" icon={Ban}>
              Not a subscription
            </Button>
            <Button variant="ghost" icon={MessageCircle}>
              Ask Sloth
            </Button>
            <Button variant="outline-strong">Draft refund request</Button>
            <Button variant="danger" icon={Trash2}>
              Delete all local data
            </Button>
            <Button variant="solid" disabled>
              Disabled
            </Button>
            <IconButton icon={X} label="Close" />
            <CopyButton text={DRAFT} />
          </div>
        </Section>

        <Section title="Chips">
          <div className="flex flex-wrap items-center gap-1.5">
            <Chip variant="solid" icon={CopyPlus}>
              Duplicate · Jul 5/6
            </Chip>
            <Chip variant="accent" icon={TrendingUp}>
              Price {pctChip(25)}
            </Chip>
            <Chip variant="tint" icon={Layers}>
              Overlap
            </Chip>
            <Chip variant="outline" icon={Ghost}>
              Zombie suspect
            </Chip>
            <Chip variant="tint" icon={CalendarClock}>
              Possible annual
            </Chip>
            <Chip variant="dashed">Low confidence</Chip>
            <Chip variant="raised" size={22}>
              Fitness
            </Chip>
            <Chip variant="panel">Monthly · near the 5th</Chip>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <Chip variant="accent" size={28} strong>
              3 days left
            </Chip>
            <Chip variant="outline" size={28}>
              Reminded · 1 of 3
            </Chip>
            <Chip variant="solid" size={28} icon={TriangleAlert}>
              Still charged
            </Chip>
            <Chip variant="success" size={28} strong>
              Verified
            </Chip>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <SourceChip source="gemma" />
            <SourceChip source="tabpfn-3.5" />
            <SourceChip source="tabpfn-3.5-fast" />
            <SourceChip source="tabpfn-3.5" live />
            <SourceChip source="heuristic" />
            <SourceChip source="template" />
          </div>
        </Section>

        <Section title="Cards">
          <div className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-4">
            <Card className="flex flex-col gap-2.5 p-6">
              <h3 className="m-0 text-sm font-medium text-muted">Monthly recurring</h3>
              <p className="m-0 text-stat">{money(1979.86)}</p>
              <p className="m-0 text-sm text-muted">
                {money(87.46)} subscriptions · {money(1892.4)} bills
              </p>
            </Card>
            <Card tone="solid" className="flex flex-col gap-2.5 p-6">
              <h3 className="m-0 text-sm font-medium text-on-solid-2">Potential monthly savings</h3>
              <p className="m-0 text-stat">{money(87.46)}</p>
              <p className="m-0 text-sm text-on-solid-2">
                If you cancel the 4 zombie suspects yourself.
              </p>
            </Card>
            <Card tone="panel" className="p-6">
              <p className="m-0 text-sm">Panel tone — Ask Sloth aside, How to cancel.</p>
            </Card>
            <Card tone="outlined" className="p-6">
              <p className="m-0 text-sm">Outlined — Done reminders.</p>
            </Card>
          </div>
          <Card tone="accent" radius="section" className="flex flex-col gap-3 px-8 py-7">
            <div className="flex items-center gap-3">
              <h3 className="m-0 text-sm font-bold">Sloth’s summary</h3>
              <SourceChip source="gemma" onPanel />
            </div>
            <p className="m-0 max-w-[62ch] text-lead">
              Pink surfaces force the light token set, so this stays ink-on-pink in dark mode.
            </p>
          </Card>
        </Section>

        <Section title="Progress and status">
          <div className="flex max-w-xl flex-col gap-4">
            <ProgressBar value={42} label="Gemma 4 download" valueText="2.1 GB of 5.0 GB" />
            <div className="flex items-center gap-2">
              <ScoreBar prob={0.98} />
              <span className="text-sm tabular-nums">98%</span>
              <ScoreBar prob={0.12} />
              <span className="text-sm tabular-nums">12%</span>
            </div>
            <span className="flex items-center gap-2 text-sm">
              <Spinner /> Starting…
            </span>
          </div>
        </Section>

        <Section title="Steppers">
          <Card tone="accent" className="p-6">
            <Stepper
              onAccent
              steps={[
                { label: 'Watching', sub: 'Oct 15', state: 'done' },
                { label: 'Reminded', sub: 'Skipped', state: 'skip' },
                { label: 'You cancelled', sub: 'Oct 16', state: 'done' },
                { label: 'Still charged', sub: 'Nov 5', state: 'alert' }
              ]}
            />
          </Card>
          <Card className="p-6">
            <Stepper
              steps={[
                { label: 'Watching', sub: 'Oct 15', state: 'done' },
                { label: 'Reminded', sub: 'Today', state: 'current' },
                { label: 'Kept / You cancelled', state: 'todo' },
                { label: 'Verified', state: 'todo' }
              ]}
            />
          </Card>
          <Card tone="outlined" className="p-6">
            <Stepper
              steps={[
                { label: 'Watching', sub: 'Oct 15', state: 'done' },
                { label: 'Reminded', sub: 'Nov 9', state: 'done' },
                { label: 'You cancelled', sub: 'Nov 9', state: 'done' },
                { label: 'Verified', sub: 'Nov 15', state: 'ok' }
              ]}
            />
          </Card>
        </Section>

        <Section title="Form controls">
          <div className="flex max-w-3xl flex-wrap items-end gap-3">
            <Field label="Prior Labs key" className="min-w-60 flex-1">
              {(id) => (
                <TextInput id={id} type="password" placeholder="Paste key" autoComplete="off" />
              )}
            </Field>
            <Button variant="solid">Save key</Button>
          </div>
          <div className="flex max-w-3xl flex-wrap items-end gap-3">
            <Field label="Currency" className="min-w-52">
              {(id) => (
                <Select id={id} defaultValue="INR">
                  <option value="INR">INR — ₹ (detected)</option>
                  <option value="USD">USD — $</option>
                </Select>
              )}
            </Field>
            <Field label="Cancelled on" className="min-w-52">
              {(id) => <TextInput id={id} type="date" surface="raised" defaultValue="2026-10-16" />}
            </Field>
            <Field label="Ask Sloth a question" hideLabel className="min-w-72 flex-1">
              {(id) => <TextInput id={id} surface="raised" placeholder="Ask about your charges…" />}
            </Field>
          </div>
          <div className="flex max-w-xl flex-col gap-4">
            <Switch
              label={
                <>
                  Demo mode <Chip size={22}>For demos</Chip>
                </>
              }
              description="Every reminder wait becomes a few seconds, so you can show the full flow quickly."
              checked={demo}
              onChange={setDemo}
            />
            <Switch
              label="Share performance traces"
              description="Sends span timings, token counts and tool names to Sentry. Off by default."
              checked={traces}
              onChange={setTraces}
            />
          </div>
          <div className="flex flex-wrap gap-4">
            <Segmented
              label="Which charges"
              value={chart}
              onChange={setChart}
              options={[
                { value: 'subs', label: 'Subscriptions' },
                { value: 'all', label: 'All recurring' }
              ]}
            />
            <Segmented
              label="Theme"
              value={themePref}
              onChange={(v) => {
                setThemePref(v)
                setPref(v)
              }}
              options={[
                { value: 'light', label: 'Light', icon: Sun },
                { value: 'dark', label: 'Dark', icon: Moon },
                { value: 'system', label: 'System' }
              ]}
            />
          </div>
          <p className="m-0 text-sm text-muted">
            Likely $1,955.46 – $2,027.46{' '}
            <Hint text="10th to 90th percentile. Each charge’s range is added up, so the band is a little wide on purpose.">
              (q10–q90)
            </Hint>
          </p>
        </Section>

        <Section title="Overlays">
          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={() => setModal(true)}>Open modal</Button>
            <Button onClick={() => setSheet(true)}>Open sheet</Button>
            <Menu
              label="Demo data"
              items={[
                {
                  label: 'Sample statement',
                  hint: '12 months, bundled',
                  onSelect: () => undefined
                },
                { label: 'Follow-up: IronTrap cancelled', onSelect: () => undefined },
                {
                  label: 'Follow-up: IronTrap still charged',
                  disabled: true,
                  onSelect: () => undefined
                }
              ]}
            />
          </div>
        </Section>

        <Section title="Brand">
          <div className="flex flex-wrap items-center gap-6">
            <Logo />
            <Card tone="panel" className="p-4">
              <SlothAvatar />
            </Card>
            <Card tone="accent" radius="hero" className="flex flex-col gap-4 p-12">
              <p className="m-0 text-display-xl">Slow and steady.</p>
              <SlothHanging className="self-center" />
              <p className="m-0 flex items-center gap-2 text-sm font-medium">
                <Lock aria-hidden size={16} strokeWidth={2.2} />
                SlothSpend informs, never acts.
              </p>
            </Card>
          </div>
        </Section>
      </main>

      <Modal open={modal} onClose={() => setModal(false)} labelledBy="ks-modal-h">
        <div className="flex flex-col gap-6">
          <div className="flex items-center justify-between">
            <h2 id="ks-modal-h" className="m-0 text-h2">
              Settings
            </h2>
            <IconButton icon={X} label="Close settings" onClick={() => setModal(false)} />
          </div>
          <p className="m-0 text-sm text-muted">
            Esc closes. Tab stays inside. Focus returns to the opener.
          </p>
          <div>
            <Button variant="solid" onClick={() => setModal(false)}>
              Done
            </Button>
          </div>
        </div>
      </Modal>

      <Sheet open={sheet} onClose={() => setSheet(false)} labelledBy="ks-sheet-h">
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <p className="m-0 text-xs font-medium text-muted">Merchant</p>
            <h2 id="ks-sheet-h" className="mt-0.5 mb-0 text-h2">
              IronTrap Fitness
            </h2>
          </div>
          <IconButton icon={X} label="Close details" onClick={() => setSheet(false)} />
        </div>
        <Card tone="panel" className="flex flex-col gap-3 p-4">
          <pre className="m-0 font-sans text-sm whitespace-pre-line text-text-2">{DRAFT}</pre>
          <div>
            <CopyButton text={DRAFT} />
          </div>
        </Card>
      </Sheet>
    </div>
  )
}
