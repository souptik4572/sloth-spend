import { Wrench } from 'lucide-react'
import { SourceChip, type Source } from '../ui/SourceChip'
import { Spinner } from '../ui/Spinner'
import { formatCall, formatMs } from '../../lib/chat'
import type { ToolCall } from '../../lib/types'

/**
 * One tool call (IMPL M6.6): a pill with the call written Python-style and its time; it opens to show what
 * the tool returned. Live TabPFN tools get the model chip with "· live".
 */
export function ToolBadge({ call }: { call: ToolCall }): React.JSX.Element {
  const running = call.ms === undefined && call.preview === undefined
  return (
    <div className="flex max-w-full flex-wrap items-center gap-1.5">
      <details className="max-w-full">
        <summary className="box-border inline-flex min-h-8 max-w-full cursor-pointer list-none items-center gap-1.5 rounded-2xl bg-raised px-3 py-1 text-xs leading-[1.45] [&::-webkit-details-marker]:hidden">
          <Wrench aria-hidden size={14} strokeWidth={2.2} className="shrink-0" />
          <code className="font-mono text-xs break-words">{formatCall(call.name, call.args)}</code>
          {running ? (
            <Spinner size={12} label="Running" className="shrink-0" />
          ) : (
            call.ms !== undefined && (
              <span className="whitespace-nowrap text-muted">· {formatMs(call.ms)}</span>
            )
          )}
        </summary>
        {call.preview && (
          <pre className="mt-1.5 mb-0 rounded-[12px] bg-raised px-3 py-2.5 font-mono text-xs leading-normal break-words whitespace-pre-wrap text-text-2">
            {call.preview}
          </pre>
        )}
      </details>
      {call.live && <SourceChip source={call.live as Source} live />}
    </div>
  )
}
