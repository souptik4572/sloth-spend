import { useEffect, useLayoutEffect, useRef, type FormEvent, type KeyboardEvent } from 'react'
import { ArrowUp, SquarePen } from 'lucide-react'
import { SlothAvatar, SlothAvatarSleepy } from '../brand/Logo'
import { IconButton } from '../ui/Button'
import { SourceChip } from '../ui/SourceChip'
import { Turn } from './Turn'
import { useAudit, type AuditPhase } from '../../auditStore'
import { isStreaming, useChat } from '../../chatStore'
import { loadConversation, newConversation, send } from '../../lib/ask'
import { SUGGESTED_PROMPTS, unusedPrompts } from '../../lib/chat'
import { cn } from '../../lib/cn'
import { useApp } from '../../store'

const ASIDE =
  'sticky top-4 box-border flex h-[calc(100vh-88px)] min-h-[560px] min-w-0 flex-[38_1_380px] flex-col gap-4 rounded-card bg-panel p-5'
const FOOTER = 'Runs on this computer. Sloth never cancels or contacts anyone for you.'

type Waiting = Exclude<AuditPhase, 'report'>

const WAITING: Record<
  Waiting,
  { title: string; text: string; placeholder: string; sleepy?: boolean }
> = {
  loading: {
    title: 'Nothing to ask about yet.',
    text: 'Load a statement and I’ll answer questions about it — right here on this computer.',
    placeholder: 'Load a statement first'
  },
  empty: {
    title: 'Nothing to ask about yet.',
    text: 'Load a statement and I’ll answer questions about it — right here on this computer.',
    placeholder: 'Load a statement first'
  },
  mapping: {
    title: 'Waiting on the columns.',
    text: 'Once the audit runs, I can answer questions about this statement.',
    placeholder: 'Load a statement first'
  },
  running: {
    title: 'Reading along with you.',
    text: 'I’ll be ready to answer questions as soon as the audit finishes.',
    placeholder: 'Available when the audit is done',
    sleepy: true
  },
  error: {
    title: 'Nothing to ask about yet.',
    text: 'Once an audit finishes, I can answer questions about it.',
    placeholder: 'Load a statement first'
  }
}

function Header({ onNew }: { onNew?: () => void }): React.JSX.Element {
  return (
    <div className="flex items-center gap-2.5">
      <h2 className="m-0 text-h3">Ask Sloth</h2>
      <SourceChip source="gemma" onPanel size={24} />
      {onNew && (
        <IconButton
          icon={SquarePen}
          label="New conversation"
          bordered={false}
          className="ml-auto"
          onClick={onNew}
        />
      )}
    </div>
  )
}

function Chips({
  label,
  prompts,
  disabled
}: {
  label: string
  prompts: string[]
  disabled?: boolean
}): React.JSX.Element | null {
  if (!prompts.length) return null
  return (
    <div className="flex flex-col gap-2">
      <p className="m-0 text-xs font-medium text-muted">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        {prompts.map((q) => (
          <button
            key={q}
            type="button"
            disabled={disabled}
            onClick={() => void send(q)}
            className={cn(
              'box-border min-h-11 rounded-full border bg-transparent px-3.5 py-2 text-left text-sm leading-tight',
              disabled
                ? 'border-dashed border-subtle text-muted'
                : 'cursor-pointer border-line-strong text-ink hover:border-ink'
            )}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}

function Input({
  placeholder,
  disabled
}: {
  placeholder: string
  disabled?: boolean
}): React.JSX.Element {
  const input = useChat((s) => s.input)
  const setInput = useChat((s) => s.setInput)
  const focusNonce = useChat((s) => s.focusNonce)
  const ref = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (focusNonce) ref.current?.focus()
  }, [focusNonce])
  // Grow with the text, up to about five lines.
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 128)}px`
  }, [input])

  const submit = (e?: FormEvent): void => {
    e?.preventDefault()
    if (!disabled) void send(input)
  }
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>): void => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }
  const canSend = !disabled && input.trim().length > 0
  return (
    <form
      onSubmit={submit}
      className={cn(
        'relative flex items-end gap-2 rounded-[22px] bg-raised py-1 pr-1 pl-5 focus-within:shadow-[0_0_0_2px_var(--ink)]',
        disabled && 'opacity-70'
      )}
    >
      <label htmlFor="ask-input" className="sr-only">
        Ask Sloth a question
      </label>
      <textarea
        id="ask-input"
        ref={ref}
        rows={1}
        value={input}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={onKeyDown}
        className="box-border h-11 min-w-0 flex-1 resize-none border-0 bg-transparent py-2.5 font-[inherit] text-base leading-6 text-ink outline-none placeholder:text-muted"
      />
      <button
        type="submit"
        disabled={!canSend}
        aria-label="Send"
        className={cn(
          'flex size-11 shrink-0 items-center justify-center rounded-full border-0',
          canSend ? 'cursor-pointer bg-solid text-on-solid' : 'bg-subtle text-bg'
        )}
      >
        <ArrowUp aria-hidden size={20} />
      </button>
    </form>
  )
}

/** Before a report (D-Import, D-Mapper, D-Progress): what Sloth will do, with nothing to type into yet. */
function WaitingPane({ phase }: { phase: Waiting }): React.JSX.Element {
  const st = WAITING[phase]
  return (
    <aside aria-label="Ask Sloth" className={ASIDE}>
      <Header />
      <div
        aria-live="polite"
        className="flex flex-1 flex-col items-center justify-center gap-4 p-6 text-center"
      >
        {st.sleepy ? <SlothAvatarSleepy /> : <SlothAvatar />}
        <p className="m-0 text-h3">{st.title}</p>
        <p className="m-0 max-w-[32ch] text-sm text-text-2">{st.text}</p>
      </div>
      <Chips label="You’ll be able to ask" prompts={SUGGESTED_PROMPTS.slice(0, 3)} disabled />
      <Input placeholder={st.placeholder} disabled />
      <p className="m-0 text-center text-xs leading-[1.65] text-muted">{FOOTER}</p>
    </aside>
  )
}

/** D-Main's aside: the conversation, "Try asking", and the input (IMPL M6.5–M6.9). */
function Conversation(): React.JSX.Element {
  const turns = useChat((s) => s.turns)
  const cid = useChat((s) => s.cid)
  const streaming = useChat(isStreaming)
  const engine = useApp((s) => s.engine)
  const list = useRef<HTMLOListElement>(null)
  const count = turns.length

  useEffect(() => {
    if (engine === 'ok') void loadConversation()
  }, [cid, engine])

  // Follow the answer as it streams, unless the user has scrolled up to read.
  const last = turns[turns.length - 1]
  const lastSize = last ? last.text.length + last.tools.length : 0
  const prevCount = useRef(count)
  useEffect(() => {
    const el = list.current
    if (!el) return
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < 160
    if (near || count !== prevCount.current) el.scrollTop = el.scrollHeight
    prevCount.current = count
  }, [count, lastSize])

  return (
    <aside aria-label="Ask Sloth" className={ASIDE}>
      <Header onNew={count ? newConversation : undefined} />
      {count ? (
        <ol
          ref={list}
          aria-label="Conversation"
          className="m-0 flex min-h-0 flex-1 list-none flex-col gap-3 overflow-y-auto p-0 pr-1"
        >
          {turns.map((t) => (
            <Turn key={t.id} turn={t} />
          ))}
        </ol>
      ) : (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 p-6 text-center">
          <SlothAvatar />
          <p className="m-0 text-h3">Ready when you are.</p>
          <p className="m-0 max-w-[34ch] text-sm text-text-2">
            Ask about your charges in plain language. Gemma answers here on this computer, using
            your report.
          </p>
        </div>
      )}
      <Chips label="Try asking" prompts={unusedPrompts(turns)} disabled={streaming} />
      <Input placeholder="Ask about your charges…" disabled={streaming} />
      <p className="m-0 text-center text-xs leading-[1.65] text-muted">{FOOTER}</p>
    </aside>
  )
}

export function ChatPane(): React.JSX.Element {
  const phase = useAudit((s) => s.phase)
  return phase === 'report' ? <Conversation /> : <WaitingPane phase={phase} />
}
