import { Moon, Sun } from 'lucide-react'
import { setPref } from '../../lib/theme'
import { useTheme } from '../../lib/useTheme'
import { cn } from '../../lib/cn'

/** Sun/moon pill in every top bar (D-Boot, D-Main). */
export function ThemeToggle(): React.JSX.Element {
  const theme = useTheme()
  const dark = theme === 'dark'
  const slot =
    'flex size-9 items-center justify-center rounded-full transition-[background-color,color] duration-300 ease-out'
  return (
    <button
      type="button"
      aria-label="Dark mode"
      aria-pressed={dark}
      title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
      onClick={() => setPref(dark ? 'light' : 'dark')}
      className="inline-flex h-11 cursor-pointer items-center gap-0.5 rounded-full border border-line-strong bg-transparent p-[3px]"
    >
      <span className={cn(slot, dark ? 'text-muted' : 'bg-solid text-on-solid')}>
        <Sun aria-hidden size={18} />
      </span>
      <span className={cn(slot, dark ? 'bg-solid text-on-solid' : 'text-muted')}>
        <Moon aria-hidden size={18} />
      </span>
    </button>
  )
}
