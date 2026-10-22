import { SlidersHorizontal } from 'lucide-react'
import { Wordmark } from '../brand/Logo'
import { IconButton } from '../ui/Button'
import { NotificationBell } from './NotificationBell'
import { StatusPills } from './StatusPills'
import { ThemeToggle } from './ThemeToggle'
import { useApp } from '../../store'

/** Workspace header (D-Main): logo, model pills, theme, bell, settings. */
export function TopBar(): React.JSX.Element {
  const setTab = useApp((s) => s.setTab)
  const openSettings = useApp((s) => s.setSettingsOpen)
  return (
    <header className="flex min-h-[72px] flex-wrap items-center gap-x-4 gap-y-3 px-6 py-3.5">
      <button
        type="button"
        onClick={() => setTab('audit')}
        aria-label="SlothSpend, go to Audit"
        className="mr-auto cursor-pointer rounded-full bg-transparent p-0 text-ink"
      >
        <Wordmark />
      </button>
      <StatusPills />
      <ThemeToggle />
      <NotificationBell />
      <IconButton icon={SlidersHorizontal} label="Settings" onClick={() => openSettings(true)} />
    </header>
  )
}
