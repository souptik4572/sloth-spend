import Markdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { DraftCard } from './DraftCard'
import { ToolBadge } from './ToolBadge'
import { Button } from '../ui/Button'
import { useAudit } from '../../auditStore'
import { send } from '../../lib/ask'
import { cn } from '../../lib/cn'
import { followUps, splitDrafts } from '../../lib/chat'
import type { ChatTurn } from '../../lib/types'

// Answers are plain reading: no links (Sloth never points anywhere), compact lists and code.
const MARKDOWN: Components = {
  p: ({ children }) => <p className="m-0">{children}</p>,
  ul: ({ children }) => <ul className="m-0 flex flex-col gap-1 pl-[18px]">{children}</ul>,
  ol: ({ children }) => <ol className="m-0 flex flex-col gap-1 pl-[22px]">{children}</ol>,
  a: ({ children }) => <span>{children}</span>,
  h1: ({ children }) => <p className="m-0 font-bold">{children}</p>,
  h2: ({ children }) => <p className="m-0 font-bold">{children}</p>,
  h3: ({ children }) => <p className="m-0 font-bold">{children}</p>,
  code: ({ children }) => <code className="font-mono text-xs">{children}</code>,
  pre: ({ children }) => (
    <pre className="m-0 rounded-[12px] bg-panel px-3 py-2.5 font-mono text-xs whitespace-pre-wrap">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto">
      <table className="border-collapse text-xs tabular-nums">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border-b border-line px-2 py-1 text-left">{children}</th>,
  td: ({ children }) => <td className="border-b border-line px-2 py-1">{children}</td>
}

function Answer({ turn }: { turn: ChatTurn }): React.JSX.Element {
  const report = useAudit((s) => s.report)
  const segments = splitDrafts(turn.text)
  const next = followUps(turn, report)
  return (
    <li className="flex flex-col gap-2 rounded-[16px_16px_16px_4px] bg-raised px-4 py-3.5 text-sm leading-normal">
      {segments.map((seg, i) =>
        seg.kind === 'draft' ? (
          <DraftCard
            key={i}
            text={seg.text}
            source="gemma"
            surface="panel"
            streaming={turn.streaming && i === segments.length - 1}
          />
        ) : (
          <div
            key={i}
            className={cn(
              'flex flex-col gap-2',
              turn.streaming && i === segments.length - 1 && 'sloth-caret'
            )}
          >
            <Markdown remarkPlugins={[remarkGfm]} components={MARKDOWN}>
              {seg.text}
            </Markdown>
          </div>
        )
      )}
      {turn.streaming && segments.length === 0 && (
        <span className="text-muted">
          Thinking
          <span aria-hidden className="sloth-caret-inline" />
        </span>
      )}
      {turn.error && (
        <div className="flex flex-col items-start gap-2">
          <p role="alert" className="m-0 font-medium">
            {turn.error}
          </p>
          <Button variant="outline-strong" onClick={() => void send(turn.user)}>
            Try again
          </Button>
        </div>
      )}
      {next.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {next.map((f) => (
            <Button key={f.label} variant="outline-strong" onClick={() => void send(f.prompt)}>
              {f.label}
            </Button>
          ))}
        </div>
      )}
    </li>
  )
}

/** One exchange: the question, the tools Sloth used, and the answer (D-Main's aside). */
export function Turn({ turn }: { turn: ChatTurn }): React.JSX.Element {
  return (
    <>
      <li className="max-w-[85%] self-end rounded-[16px_16px_4px_16px] bg-solid px-3.5 py-2.5 text-sm leading-[1.45] whitespace-pre-line text-on-solid">
        {turn.user}
      </li>
      {turn.tools.length > 0 && (
        <li className="flex flex-col items-start gap-1.5">
          {turn.tools.map((call, i) => (
            <ToolBadge key={i} call={call} />
          ))}
        </li>
      )}
      {(turn.text || turn.streaming || turn.error) && <Answer turn={turn} />}
    </>
  )
}
