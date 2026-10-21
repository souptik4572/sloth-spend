import { useCallback, useId, useRef, useState, type KeyboardEvent } from 'react'
import { ChevronDown, type LucideIcon } from 'lucide-react'
import { Popover } from './Popover'
import { cn } from '../../lib/cn'

export interface MenuItem {
  label: string
  hint?: string
  disabled?: boolean
  onSelect: () => void
}

export interface MenuProps {
  label: string
  items: MenuItem[]
  icon?: LucideIcon
  size?: 'md' | 'sm'
  align?: 'start' | 'end'
}

/** Text button with a chevron that opens a menu ("Demo data ▾", D-Import). Arrow keys move between items. */
export function Menu({
  label,
  items,
  icon: Icon,
  size = 'md',
  align = 'start'
}: MenuProps): React.JSX.Element {
  const [open, setOpen] = useState(false)
  const listRef = useRef<HTMLUListElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const id = useId()
  const close = useCallback(() => {
    setOpen(false)
    buttonRef.current?.focus()
  }, [])

  const focusItem = (dir: 1 | -1): void => {
    const nodes = Array.from(
      listRef.current?.querySelectorAll<HTMLButtonElement>('button:not([disabled])') ?? []
    )
    if (!nodes.length) return
    const i = nodes.indexOf(document.activeElement as HTMLButtonElement)
    nodes[(i + dir + nodes.length) % nodes.length].focus()
  }

  const onKeyDown = (e: KeyboardEvent): void => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      focusItem(1)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      focusItem(-1)
    }
  }

  return (
    <Popover
      open={open}
      onClose={close}
      align={align}
      width={300}
      anchor={
        <button
          ref={buttonRef}
          type="button"
          aria-haspopup="menu"
          aria-expanded={open}
          aria-controls={open ? id : undefined}
          onClick={() => {
            setOpen((o) => !o)
            setTimeout(() => focusItem(1), 0)
          }}
          className={cn(
            'inline-flex cursor-pointer items-center gap-1.5 rounded-full bg-transparent pr-3 pl-4 font-medium text-ink hover:bg-ink/5',
            size === 'md' ? 'h-11 text-base' : 'h-11 text-sm'
          )}
        >
          {Icon && <Icon aria-hidden size={16} />}
          {label}
          <ChevronDown
            aria-hidden
            size={16}
            className={cn('transition-transform duration-300', open && 'rotate-180')}
          />
        </button>
      }
    >
      <ul
        id={id}
        ref={listRef}
        role="menu"
        aria-label={label}
        onKeyDown={onKeyDown}
        className="m-0 flex list-none flex-col gap-0.5 rounded-card bg-bg p-2 shadow-[0_2px_4px_var(--shadow)] ring-1 ring-line"
      >
        {items.map((item) => (
          <li key={item.label} role="none">
            <button
              type="button"
              role="menuitem"
              disabled={item.disabled}
              onClick={() => {
                item.onSelect()
                close()
              }}
              className="flex min-h-11 w-full cursor-pointer flex-col items-start justify-center rounded-tile px-3 py-2 text-left text-sm font-medium text-ink hover:bg-panel focus-visible:bg-panel disabled:cursor-not-allowed disabled:opacity-50"
            >
              {item.label}
              {item.hint && <span className="text-xs font-normal text-muted">{item.hint}</span>}
            </button>
          </li>
        ))}
      </ul>
    </Popover>
  )
}
