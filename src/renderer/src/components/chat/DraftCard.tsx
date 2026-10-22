import type { ReactNode } from 'react'
import { CopyButton } from '../ui/CopyButton'
import { SourceChip } from '../ui/SourceChip'
import { cn } from '../../lib/cn'
import { draftTitle, parseDraft } from '../../lib/chat'

/**
 * An email for the user to send themselves (IMPL M6.7, D-Drawer / D-Reminders): title, model chip, Copy, a bold
 * subject and the body. SlothSpend never sends it.
 */
export function DraftCard({
  text,
  source,
  title,
  streaming,
  surface = 'raised',
  children
}: {
  text: string
  source: 'gemma' | 'template'
  title?: string
  streaming?: boolean
  surface?: 'raised' | 'panel'
  /** Extra actions under the body ("Draft … again"). */
  children?: ReactNode
}): React.JSX.Element {
  const draft = parseDraft(text)
  const heading = title ?? (draft ? draftTitle(draft.subject) : 'Draft')
  return (
    <div
      className={cn(
        'flex flex-col gap-3 rounded-tile p-4',
        surface === 'raised' ? 'bg-raised' : 'bg-panel'
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <p className="m-0 mr-auto text-sm font-bold">{heading}</p>
        <SourceChip source={source} />
        {!streaming && (
          <CopyButton text={draft ? `Subject: ${draft.subject}\n\n${draft.body}` : text} />
        )}
      </div>
      <div
        aria-live={streaming ? 'polite' : undefined}
        className="border-t border-line pt-3 text-sm leading-[1.55] whitespace-pre-line text-text-2"
      >
        {draft ? (
          <>
            <strong className="text-ink">Subject: {draft.subject}</strong>
            {'\n\n'}
            {draft.body}
          </>
        ) : (
          text
        )}
        {streaming && <span aria-hidden className="sloth-caret-inline" />}
      </div>
      {children}
      <p className="m-0 text-xs text-muted">Check the dates and amounts, then send it yourself.</p>
    </div>
  )
}
