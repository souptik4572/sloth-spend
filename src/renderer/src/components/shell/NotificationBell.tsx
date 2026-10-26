import { useState } from 'react'
import { Bell, CircleCheck, TriangleAlert, type LucideIcon } from 'lucide-react'
import { IconButton } from '../ui/Button'
import { Popover } from '../ui/Popover'
import { cn } from '../../lib/cn'
import { relativeTime } from '../../lib/format'
import { markAllRead, openNotice } from '../../lib/reminders'
import type { Notice } from '../../lib/types'
import { unreadCount, useReminders } from '../../remindersStore'
import { byPlatform } from '../../lib/platform'

const ICON: Record<Notice['kind'], { icon: LucideIcon; tone: string }> = {
  reminder: { icon: Bell, tone: 'bg-tint text-ink' },
  verified: { icon: CircleCheck, tone: 'bg-success-tint text-success' },
  still_charged: { icon: TriangleAlert, tone: 'bg-solid text-on-solid' }
}

function Row({ n, onOpen }: { n: Notice; onOpen: () => void }): React.JSX.Element {
  const unread = !n.read_at
  const alert = n.kind === 'still_charged'
  const { icon: Icon, tone } = ICON[n.kind] ?? ICON.reminder
  return (
    <li>
      <button
        type="button"
        data-theme={alert ? 'light' : undefined}
        onClick={() => {
          openNotice(n)
          onOpen()
        }}
        className={cn(
          'box-border flex min-h-11 w-full cursor-pointer gap-3 rounded-tile border-0 p-3 text-left text-ink',
          alert ? 'bg-accent' : unread ? 'bg-card hover:bg-raised' : 'bg-transparent hover:bg-card'
        )}
      >
        <span
          className={cn(
            'flex size-9 shrink-0 items-center justify-center rounded-full',
            unread || alert ? tone : 'bg-card text-ink'
          )}
        >
          <Icon aria-hidden size={18} strokeWidth={2.2} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline gap-2">
            <span className={cn('mr-auto text-sm', unread ? 'font-bold' : 'font-medium')}>
              {n.title}
            </span>
            <span className={cn('text-xs whitespace-nowrap', alert ? 'text-text-2' : 'text-muted')}>
              {relativeTime(n.created_at)}
            </span>
          </span>
          <span
            className={cn(
              'block text-sm leading-[1.45]',
              unread || alert ? 'text-text-2' : 'text-muted'
            )}
          >
            {n.body}
          </span>
        </span>
        {unread && (
          <span
            role="img"
            aria-label="Unread"
            className="mt-1.5 size-2 shrink-0 rounded-full bg-ink"
          />
        )}
      </button>
    </li>
  )
}

/** Bell + inbox popover (D-Notif). Unread notices show as an accent count on the bell. */
export function NotificationBell(): React.JSX.Element {
  const [open, setOpen] = useState(false)
  const inbox = useReminders((s) => s.inbox)
  const unread = useReminders(unreadCount)
  const close = (): void => setOpen(false)
  return (
    <Popover
      open={open}
      onClose={close}
      label="Notifications"
      anchor={
        <span className="relative inline-flex">
          <IconButton
            icon={Bell}
            label={unread ? `Notifications, ${unread} unread` : 'Notifications, none unread'}
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
          />
          {unread > 0 && (
            <span
              aria-hidden
              className="pointer-events-none absolute -top-0.5 -right-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-accent px-1 text-xs font-bold text-on-accent"
            >
              {unread > 9 ? '9+' : unread}
            </span>
          )}
        </span>
      }
    >
      <section className="flex max-h-[min(640px,calc(100vh-120px))] flex-col gap-3 rounded-card bg-bg p-5 shadow-[0_2px_4px_var(--shadow)]">
        <div className="flex items-center gap-2">
          <h2 className="m-0 mr-auto text-h3">Notifications</h2>
          {unread > 0 && (
            <button
              type="button"
              onClick={() => void markAllRead()}
              className="h-11 cursor-pointer rounded-full border-0 bg-transparent px-3 text-sm font-medium text-ink hover:bg-ink/5"
            >
              Mark all read
            </button>
          )}
        </div>
        {inbox.length ? (
          <ul className="m-0 flex min-h-0 list-none flex-col gap-1 overflow-y-auto p-0">
            {inbox.map((n) => (
              <Row key={n.id} n={n} onOpen={close} />
            ))}
          </ul>
        ) : (
          <p className="m-0 text-sm text-muted">
            Nothing yet. Renewal reminders and statement checks show up here.
          </p>
        )}
        <p className="m-0 text-center text-xs leading-[1.65] text-muted">
          {byPlatform(
            'Reminders fire while SlothSpend is open.',
            'SlothSpend checks reminders even while this tab is closed.'
          )}
        </p>
      </section>
    </Popover>
  )
}
