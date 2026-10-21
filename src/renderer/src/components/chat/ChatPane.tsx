import { ArrowUp } from 'lucide-react'
import { SlothAvatar, SlothAvatarSleepy } from '../brand/Logo'
import { SourceChip } from '../ui/SourceChip'
import { useAudit, type AuditPhase } from '../../auditStore'

const SUGGESTIONS = [
  'Why was this flagged?',
  'What will next month cost?',
  'Draft a refund request'
]

const STATES: Record<
  AuditPhase,
  { title: string; text: string; placeholder: string; sleepy?: boolean; chipsLabel: string }
> = {
  loading: {
    title: 'Nothing to ask about yet.',
    text: 'Load a statement and I’ll answer questions about it — right here on this computer.',
    placeholder: 'Load a statement first',
    chipsLabel: 'You’ll be able to ask'
  },
  empty: {
    title: 'Nothing to ask about yet.',
    text: 'Load a statement and I’ll answer questions about it — right here on this computer.',
    placeholder: 'Load a statement first',
    chipsLabel: 'You’ll be able to ask'
  },
  mapping: {
    title: 'Waiting on the columns.',
    text: 'Once the audit runs, I can answer questions about this statement.',
    placeholder: 'Load a statement first',
    chipsLabel: 'You’ll be able to ask'
  },
  running: {
    title: 'Reading along with you.',
    text: 'I’ll be ready to answer questions as soon as the audit finishes.',
    placeholder: 'Available when the audit is done',
    sleepy: true,
    chipsLabel: 'You’ll be able to ask'
  },
  report: {
    title: 'Ready when you are.',
    text: 'Asking about your charges in plain language arrives in the next update — it runs here on this computer.',
    placeholder: 'Coming in the next update',
    chipsLabel: 'Soon you’ll be able to ask'
  },
  error: {
    title: 'Nothing to ask about yet.',
    text: 'Once an audit finishes, I can answer questions about it.',
    placeholder: 'Load a statement first',
    chipsLabel: 'You’ll be able to ask'
  }
}

/**
 * Ask Sloth aside (38 % column, sticky). Until M6 it shows the per-phase waiting states from the design
 * (D-Import, D-Mapper, D-Progress); the live conversation arrives in M6.
 */
export function ChatPane(): React.JSX.Element {
  const phase = useAudit((s) => s.phase)
  const st = STATES[phase]
  return (
    <aside
      aria-label="Ask Sloth"
      className="sticky top-4 box-border flex h-[calc(100vh-88px)] min-h-[560px] min-w-0 flex-[38_1_380px] flex-col gap-4 rounded-card bg-panel p-5"
    >
      <div className="flex items-center gap-2.5">
        <h2 className="m-0 text-h3">Ask Sloth</h2>
        <SourceChip source="gemma" onPanel size={24} />
      </div>

      <div
        aria-live="polite"
        className="flex flex-1 flex-col items-center justify-center gap-4 p-6 text-center"
      >
        {st.sleepy ? <SlothAvatarSleepy /> : <SlothAvatar />}
        <p className="m-0 text-h3">{st.title}</p>
        <p className="m-0 max-w-[32ch] text-sm text-text-2">{st.text}</p>
      </div>

      <div className="flex flex-col gap-2">
        <p className="m-0 text-xs font-medium text-muted">{st.chipsLabel}</p>
        <div className="flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((q) => (
            <button
              key={q}
              type="button"
              disabled
              className="min-h-11 rounded-full border border-dashed border-subtle bg-transparent px-3.5 py-2 text-left text-sm leading-tight text-muted"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      <div className="relative flex items-center gap-2 rounded-full bg-raised py-1 pr-1 pl-5 opacity-70">
        <label htmlFor="ask-input" className="sr-only">
          Ask Sloth a question
        </label>
        <input
          id="ask-input"
          type="text"
          disabled
          placeholder={st.placeholder}
          className="h-11 min-w-0 flex-1 border-0 bg-transparent text-base text-ink outline-none"
        />
        <button
          type="button"
          disabled
          aria-label="Send"
          className="flex size-11 shrink-0 items-center justify-center rounded-full bg-subtle text-bg"
        >
          <ArrowUp aria-hidden size={20} />
        </button>
      </div>
      <p className="m-0 text-center text-xs leading-[1.65] text-muted">
        Runs on this computer. Sloth never cancels or contacts anyone for you.
      </p>
    </aside>
  )
}
