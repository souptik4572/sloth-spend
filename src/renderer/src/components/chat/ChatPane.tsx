import { ArrowUp } from 'lucide-react'
import { SlothAvatar } from '../brand/Logo'
import { SourceChip } from '../ui/SourceChip'

const EXAMPLES = ['Why was this flagged?', 'What will next month cost?', 'Draft a refund request']

/**
 * Ask Sloth aside (38 % column, sticky). M1 renders the no-statement state from D-Import;
 * the live conversation arrives in M6.
 */
export function ChatPane(): React.JSX.Element {
  return (
    <aside
      aria-label="Ask Sloth"
      className="sticky top-4 box-border flex h-[calc(100vh-88px)] min-h-[560px] min-w-0 flex-[38_1_380px] flex-col gap-4 rounded-card bg-panel p-5"
    >
      <div className="flex items-center gap-2.5">
        <h2 className="m-0 text-h3">Ask Sloth</h2>
        <SourceChip source="gemma" onPanel size={24} />
      </div>

      <div className="flex flex-1 flex-col items-center justify-center gap-4 p-6 text-center">
        <SlothAvatar />
        <p className="m-0 text-h3">Nothing to ask about yet.</p>
        <p className="m-0 max-w-[32ch] text-sm text-text-2">
          Load a statement and I’ll answer questions about it — right here on this computer.
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <p className="m-0 text-xs font-medium text-muted">You’ll be able to ask</p>
        <div className="flex flex-wrap gap-1.5">
          {EXAMPLES.map((q) => (
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
        <label htmlFor="ask-empty" className="sr-only">
          Ask Sloth a question
        </label>
        <input
          id="ask-empty"
          type="text"
          disabled
          placeholder="Load a statement first"
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
    </aside>
  )
}
