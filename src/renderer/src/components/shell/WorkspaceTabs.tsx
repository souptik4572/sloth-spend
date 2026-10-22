import { cn } from '../../lib/cn'
import { needsYou } from '../../lib/ui-derive'
import { useReminders } from '../../remindersStore'
import { useApp, type Tab } from '../../store'

const TABS: Array<[Tab, string]> = [
  ['audit', 'Audit'],
  ['reminders', 'Reminders']
]

/** Audit / Reminders in display type (D-Main). The current tab is ink, the other subtle. */
export function WorkspaceTabs(): React.JSX.Element {
  const { tab, setTab } = useApp()
  const waiting = useReminders((s) => needsYou(s.reminders))
  return (
    <nav aria-label="Workspace" className="flex flex-wrap items-baseline gap-x-7 gap-y-1">
      {TABS.map(([id, label]) => (
        <button
          key={id}
          type="button"
          aria-current={tab === id ? 'page' : undefined}
          onClick={() => setTab(id)}
          className={cn(
            'cursor-pointer rounded-tile bg-transparent p-0 text-display-tab transition-colors duration-300 ease-out',
            tab === id ? 'text-ink' : 'text-subtle hover:text-muted'
          )}
        >
          {label}
          {id === 'reminders' && waiting > 0 && (
            <span className="ml-3 inline-flex h-7 items-center rounded-full bg-accent px-3 align-middle text-sm font-bold text-on-accent">
              {waiting} need{waiting === 1 ? 's' : ''} you
            </span>
          )}
        </button>
      ))}
    </nav>
  )
}
