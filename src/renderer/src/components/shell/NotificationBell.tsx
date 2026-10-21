import { useState } from 'react'
import { Bell } from 'lucide-react'
import { IconButton } from '../ui/Button'
import { Popover } from '../ui/Popover'

/** Bell + inbox popover (D-Notif). M1: the shell only; polling and the inbox list arrive in M7. */
export function NotificationBell(): React.JSX.Element {
  const [open, setOpen] = useState(false)
  return (
    <Popover
      open={open}
      onClose={() => setOpen(false)}
      label="Notifications"
      anchor={
        <IconButton
          icon={Bell}
          label="Notifications, none unread"
          aria-expanded={open}
          onClick={() => setOpen((o) => !o)}
        />
      }
    >
      <section className="flex flex-col gap-3 rounded-card bg-bg p-5 shadow-[0_2px_4px_var(--shadow)]">
        <h2 className="m-0 text-h3">Notifications</h2>
        <p className="m-0 text-sm text-muted">
          Nothing yet. Renewal reminders and statement checks show up here.
        </p>
        <p className="m-0 text-xs text-muted">Reminders fire while SlothSpend is open.</p>
      </section>
    </Popover>
  )
}
