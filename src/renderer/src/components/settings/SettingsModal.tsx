import { useEffect, useState, type ReactNode } from 'react'
import { CircleCheck, Minus, Monitor, Moon, Plus, Sun, Trash2, X } from 'lucide-react'
import { DeleteDataDialog } from './DeleteDataDialog'
import { EgressTable } from './EgressTable'
import { GemmaSetup } from '../shell/GemmaSetup'
import { PriorKeyForm } from '../shell/PriorKeyForm'
import { Button, IconButton } from '../ui/Button'
import { Chip } from '../ui/Chip'
import { Field, Select, TextInput } from '../ui/Field'
import { Modal } from '../ui/Modal'
import { Segmented } from '../ui/Segmented'
import { Switch } from '../ui/Switch'
import { cn } from '../../lib/cn'
import { useEngineSettings, type SaveState } from '../../lib/settings'
import { readPref, setPref, type ThemePref } from '../../lib/theme'
import type { Currency, Health } from '../../lib/types'
import { useTheme } from '../../lib/useTheme'
import { useApp } from '../../store'
import { isWeb } from '../../lib/platform'

const CURRENCIES: Array<[Currency, string]> = [
  ['USD', 'USD — $'],
  ['INR', 'INR — ₹'],
  ['EUR', 'EUR — €'],
  ['GBP', 'GBP — £']
]

const MODEL_NOTES: Record<string, string> = {
  'gemma4:e4b': 'Recommended. Best answers and tool use.',
  'gemma4:e2b': 'Lighter. For computers with 8 GB of memory or less.'
}

const DEMO_DEFAULT = 30

function Saved({ state }: { state?: SaveState }): React.JSX.Element | null {
  if (!state) return null
  return (
    <span aria-live="polite" className="text-xs font-medium text-muted">
      {state === 'saving' ? 'Saving…' : state === 'saved' ? 'Saved' : 'Couldn’t save'}
    </span>
  )
}

function Section({
  id,
  title,
  aside,
  children
}: {
  id: string
  title: string
  aside?: ReactNode
  children: ReactNode
}): React.JSX.Element {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-4">
      <div className="flex items-baseline gap-3">
        <h3 id={id} className="m-0 text-h3">
          {title}
        </h3>
        {aside}
      </div>
      {children}
    </section>
  )
}

function ModelOption({
  name,
  title,
  note,
  checked,
  onPick
}: {
  name: string
  title: string
  note: string
  checked: boolean
  onPick: () => void
}): React.JSX.Element {
  return (
    <label
      className={cn(
        'flex cursor-pointer items-start gap-3 rounded-tile p-4',
        checked ? 'bg-panel shadow-[inset_0_0_0_2px_var(--ink)]' : 'bg-card hover:bg-raised'
      )}
    >
      <input
        type="radio"
        name="chat-model"
        value={name}
        checked={checked}
        onChange={onPick}
        className="mt-0.5 size-5 shrink-0 accent-[var(--ink)]"
      />
      <span>
        <span className="block text-base font-medium">{title}</span>
        <span className="block text-sm leading-[1.45] text-text-2">{note}</span>
      </span>
    </label>
  )
}

function tabpfnLine(h: Health | null): string {
  const t = h?.tabpfn
  if (!t) return 'TabPFN status unknown'
  if (t.status === 'ready') {
    if (t.model === 'tabpfn-v2') return 'Using TabPFN v2 (open weights)'
    if (t.model === 'tabpfn-3.5-fast') return 'Using TabPFN-3.5 Fast'
    return 'Using TabPFN-3.5'
  }
  if (t.status === 'downloading' || t.status === 'warming' || t.status === 'cold')
    return 'TabPFN is getting ready…'
  return `TabPFN isn’t available, so a simple rule scores charges${t.error ? ` (${t.error})` : ''}`
}

/** D-Settings (IMPL M8.1): appearance, models, statements, reminders, privacy, delete. */
export function SettingsModal(): React.JSX.Element {
  const open = useApp((s) => s.settingsOpen)
  const close = (): void => useApp.getState().setSettingsOpen(false)
  const health = useApp((s) => s.health)
  const { settings, status, update } = useEngineSettings(open)
  useTheme() // re-render when the top-bar toggle changes the theme
  const themePref = readPref()
  const [telemetry, setTelemetry] = useState<boolean | null>(null)
  const [telemetryBusy, setTelemetryBusy] = useState(false)
  // What's typed in the seconds field while it's being edited; otherwise the saved value shows.
  const [demoDraft, setDemoDraft] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)

  useEffect(() => {
    if (!open) return
    void window.sloth.telemetry.get().then(setTelemetry)
  }, [open])
  const demo = settings?.demo_compress_seconds ?? 0
  const demoText = demoDraft ?? String(demo || DEMO_DEFAULT)

  const toggleTelemetry = async (on: boolean): Promise<void> => {
    setTelemetryBusy(true)
    setTelemetry(on)
    useApp.getState().engineRestarting() // the pills show Starting… until /health answers again
    setTelemetry(await window.sloth.telemetry.set(on))
    setTelemetryBusy(false)
  }

  const commitDemo = (text: string): void => {
    setDemoDraft(text)
    const n = Number(text)
    if (Number.isInteger(n) && n >= 5 && n <= 600) update({ demo_compress_seconds: n }, 'reminders')
  }

  const installed = health?.llm.available_models ?? []
  const best = installed[0]
  const days = settings?.days_before ?? 3

  return (
    <>
      <Modal open={open} onClose={close} labelledBy="set-h">
        <div className="flex flex-col gap-8">
          <div className="flex items-center gap-3">
            <h2 id="set-h" className="m-0 mr-auto text-display-tab">
              Settings
            </h2>
            <IconButton icon={X} label="Close settings" onClick={close} />
          </div>

          <Section id="s-look" title="Appearance">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
              <p className="m-0 flex-[1_1_260px] text-sm leading-[1.45] text-muted">
                Also in the top bar. SlothSpend starts in your computer’s setting until you pick
                one.
              </p>
              <Segmented<ThemePref>
                label="Theme"
                value={themePref}
                onChange={(p) => setPref(p)}
                options={[
                  { value: 'light', label: 'Light', icon: Sun },
                  { value: 'dark', label: 'Dark', icon: Moon },
                  { value: 'system', label: 'System', icon: Monitor }
                ]}
              />
            </div>
          </Section>

          <Section id="s-models" title="Models" aside={<Saved state={status.models} />}>
            {installed.length ? (
              <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
                <legend className="mb-2 p-0 text-sm font-medium">Chat model</legend>
                <div className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-3">
                  <ModelOption
                    name="auto"
                    title="Automatic"
                    note={`Use the best Gemma model installed (${best}).`}
                    checked={!settings?.chat_model}
                    onPick={() => update({ chat_model: null }, 'models')}
                  />
                  {installed.map((m) => (
                    <ModelOption
                      key={m}
                      name={m}
                      title={m}
                      note={MODEL_NOTES[m] ?? 'Installed in Ollama on this computer.'}
                      checked={settings?.chat_model === m}
                      onPick={() => update({ chat_model: m }, 'models')}
                    />
                  ))}
                </div>
              </fieldset>
            ) : (
              <div className="flex flex-col gap-2 rounded-tile bg-card p-4">
                <p className="m-0 text-sm font-medium">Chat model</p>
                <p className="m-0 text-sm text-text-2">
                  No Gemma model is installed in Ollama yet. Merchant names and text use simple
                  rules until one is.
                </p>
                <GemmaSetup />
              </div>
            )}
            {health?.llm.loopback === false && (
              <p
                role="note"
                className="m-0 rounded-tile border border-line-strong px-4 py-3 text-sm leading-[1.45]"
              >
                <strong>Gemma isn’t on this computer.</strong> OLLAMA_HOST points SlothSpend at
                Ollama on another computer, so merchant names, chats and reminder facts travel there
                over your network. Unset OLLAMA_HOST and restart SlothSpend to keep everything on
                this one.
              </p>
            )}
            <div className="flex flex-col gap-3 rounded-tile bg-card p-4">
              <p className="m-0 flex items-center gap-2 text-sm font-medium">
                {health?.tabpfn.status === 'ready' && (
                  <CircleCheck aria-hidden size={16} strokeWidth={2.4} className="text-success" />
                )}
                {tabpfnLine(health)}
              </p>
              {!isWeb() && <PriorKeyForm />}
            </div>
          </Section>

          <Section id="s-stmt" title="Statements" aside={<Saved state={status.statements} />}>
            <Field
              label="Default currency"
              hint="Used when a statement doesn’t show its currency."
              className="max-w-[320px]"
            >
              {(id) => (
                <Select
                  id={id}
                  value={settings?.currency ?? 'USD'}
                  disabled={!settings}
                  onChange={(e) => update({ currency: e.target.value as Currency }, 'statements')}
                >
                  {CURRENCIES.map(([code, label]) => (
                    <option key={code} value={code}>
                      {label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </Section>

          <Section id="s-rem" title="Reminders" aside={<Saved state={status.reminders} />}>
            <Field label="Remind me this many days before a renewal">
              {(id) => (
                <div className="flex items-center gap-2">
                  <IconButton
                    icon={Minus}
                    label="Fewer days"
                    disabled={!settings || days <= 1}
                    onClick={() => update({ days_before: days - 1 }, 'reminders')}
                  />
                  <TextInput
                    id={id}
                    type="number"
                    min={1}
                    max={14}
                    value={days}
                    disabled={!settings}
                    onChange={(e) => {
                      const n = Number(e.target.value)
                      if (Number.isInteger(n) && n >= 1 && n <= 14)
                        update({ days_before: n }, 'reminders')
                    }}
                    className="w-20 text-center"
                  />
                  <IconButton
                    icon={Plus}
                    label="More days"
                    disabled={!settings || days >= 14}
                    onClick={() => update({ days_before: days + 1 }, 'reminders')}
                  />
                </div>
              )}
            </Field>
            <div className="flex flex-col gap-3 rounded-tile bg-card p-4">
              <Switch
                label={
                  <>
                    Demo mode
                    <Chip size={22} variant="tint">
                      For demos
                    </Chip>
                  </>
                }
                description="Every reminder wait becomes a few seconds, so you can show the full flow quickly."
                checked={demo > 0}
                disabled={!settings}
                onChange={(on) =>
                  update(
                    { demo_compress_seconds: on ? Number(demoText) || DEMO_DEFAULT : 0 },
                    'reminders'
                  )
                }
              />
              {demo > 0 && (
                <div className="flex flex-wrap items-center gap-2">
                  <label htmlFor="s-demo" className="text-sm font-medium">
                    Compress waits to
                  </label>
                  <TextInput
                    id="s-demo"
                    type="number"
                    min={5}
                    max={600}
                    value={demoText}
                    onChange={(e) => commitDemo(e.target.value)}
                    onBlur={() => setDemoDraft(null)}
                    aria-describedby="s-demo-hint"
                    className="w-24 text-center"
                  />
                  <span className="text-sm">seconds</span>
                  <span id="s-demo-hint" className="text-xs text-muted">
                    5–600
                  </span>
                </div>
              )}
            </div>
          </Section>

          <Section id="s-priv" title="Privacy">
            <Switch
              label="Share performance traces"
              description="Sends span timings, token counts and tool names to Sentry. Never prompts, answers or statement data. Off by default. Changing it restarts the engine."
              checked={telemetry === true}
              disabled={telemetry === null || telemetryBusy}
              onChange={(on) => void toggleTelemetry(on)}
            />
            <EgressTable />
          </Section>

          <section
            aria-labelledby="s-data"
            className="flex flex-wrap items-center gap-x-4 gap-y-3 border-t border-line pt-6"
          >
            <div className="min-w-0 flex-[1_1_280px]">
              <h3 id="s-data" className="m-0 text-base font-bold">
                Delete all local data
              </h3>
              <p className="mt-0.5 mb-0 text-sm leading-[1.45] text-muted">
                Removes every statement, merchant edit, chat and reminder from this computer. This
                can’t be undone.
              </p>
            </div>
            <Button variant="danger" icon={Trash2} onClick={() => setConfirmDelete(true)}>
              Delete all local data
            </Button>
          </section>

          <div className="flex justify-end">
            <Button variant="solid" size="lg" className="px-7" onClick={close}>
              Done
            </Button>
          </div>
        </div>
      </Modal>
      <DeleteDataDialog open={confirmDelete} onClose={() => setConfirmDelete(false)} />
    </>
  )
}
