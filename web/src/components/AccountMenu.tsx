import { useCallback, useId, useRef, useState, type KeyboardEvent } from 'react'
import { LogOut, MonitorDown, Shield, User as UserIcon, type LucideIcon } from 'lucide-react'
import { Popover } from '@renderer/components/ui/Popover'
import { cn } from '@renderer/lib/cn'
import { initials, useSession } from '@web/lib/session'
import { AccountDialog, type AccountSection } from './AccountDialog'

const DESKTOP_APP = 'https://github.com/souptik4572/sloth-spend/releases/latest'

/** The avatar at the end of the workspace top bar and its menu (Web artboard 15). Arrow keys move between items. */
export function AccountMenu(): React.JSX.Element | null {
  const user = useSession((s) => s.user)
  const [open, setOpen] = useState(false)
  const [dialog, setDialog] = useState<AccountSection | null>(null)
  const button = useRef<HTMLButtonElement>(null)
  const list = useRef<HTMLDivElement>(null)
  const id = useId()
  const close = useCallback(() => {
    setOpen(false)
    button.current?.focus()
  }, [])
  if (!user) return null

  const focusItem = (dir: 1 | -1): void => {
    const items = Array.from(list.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [])
    if (!items.length) return
    const i = items.indexOf(document.activeElement as HTMLElement)
    items[(i + dir + items.length) % items.length].focus()
  }
  const onKeyDown = (e: KeyboardEvent): void => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      focusItem(e.key === 'ArrowDown' ? 1 : -1)
    }
  }
  const choose = (fn: () => void) => (): void => {
    setOpen(false)
    fn()
  }

  return (
    <>
      <Popover
        open={open}
        onClose={close}
        width={320}
        anchor={
          <button
            ref={button}
            type="button"
            aria-haspopup="menu"
            aria-expanded={open}
            aria-controls={open ? id : undefined}
            aria-label={`Account: ${user.name}`}
            title={user.email}
            onClick={() => {
              setOpen((o) => !o)
              setTimeout(() => focusItem(1), 0)
            }}
            className={cn(
              'flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-full border-0 bg-accent text-sm font-bold text-on-accent',
              'transition-shadow duration-300',
              open && 'shadow-[0_0_0_2px_var(--bg),0_0_0_4px_var(--ink)]'
            )}
          >
            {initials(user.name)}
          </button>
        }
      >
        <div
          id={id}
          ref={list}
          role="menu"
          aria-label="Account"
          onKeyDown={onKeyDown}
          className="box-border flex flex-col gap-1 rounded-card border border-line bg-bg p-3 shadow-[0_2px_4px_var(--shadow)]"
        >
          <div className="flex items-center gap-3 px-2 pt-2 pb-3">
            <span
              aria-hidden
              className="flex size-11 shrink-0 items-center justify-center rounded-full bg-accent text-sm font-bold text-on-accent"
            >
              {initials(user.name)}
            </span>
            <span className="min-w-0">
              <span className="block text-base leading-tight font-bold">{user.name}</span>
              <span className="block truncate text-small text-muted">{user.email}</span>
            </span>
          </div>
          <Item icon={UserIcon} label="Account" onSelect={choose(() => setDialog('account'))} />
          <Item
            icon={Shield}
            label="Password & security"
            onSelect={choose(() => setDialog('security'))}
          />
          <Item
            icon={MonitorDown}
            label="Get the desktop app"
            hint="Runs entirely on your computer"
            onSelect={choose(() => void window.sloth.openExternal(DESKTOP_APP))}
          />
          <div aria-hidden className="mx-2 my-1.5 h-px bg-line" />
          <Item
            icon={LogOut}
            label="Log out"
            onSelect={choose(() => void useSession.getState().logOut())}
          />
        </div>
      </Popover>
      <AccountDialog section={dialog} onSection={setDialog} onClose={() => setDialog(null)} />
    </>
  )
}

function Item({
  icon: Icon,
  label,
  hint,
  onSelect
}: {
  icon: LucideIcon
  label: string
  hint?: string
  onSelect: () => void
}): React.JSX.Element {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onSelect}
      className={cn(
        'box-border flex w-full cursor-pointer items-center gap-3 rounded-tile border-0 bg-transparent px-3 text-left text-ink',
        'hover:bg-card focus-visible:bg-card',
        hint ? 'min-h-[52px] py-1.5' : 'min-h-11'
      )}
    >
      <Icon aria-hidden size={18} strokeWidth={2} className="shrink-0" />
      {hint ? (
        <span>
          <span className="block text-sm leading-[1.3] font-medium">{label}</span>
          <span className="block text-caption text-muted">{hint}</span>
        </span>
      ) : (
        <span className="text-sm font-medium">{label}</span>
      )}
    </button>
  )
}
