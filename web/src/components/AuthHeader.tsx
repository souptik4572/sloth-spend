import type { ReactNode } from 'react'
import { Wordmark } from '@renderer/components/brand/Logo'
import { ThemeToggle } from '@renderer/components/shell/ThemeToggle'
import { Link } from '@web/lib/router'

/** The signed-out top bar (Web artboards 10–14): wordmark, an optional prompt + pill, the theme toggle. */
export function AuthHeader({ children }: { children?: ReactNode }): React.JSX.Element {
  return (
    <header className="box-border flex min-h-[72px] flex-wrap items-center gap-x-4 gap-y-3 px-6 py-3.5">
      <Link to="/login" className="mr-auto text-ink no-underline">
        <Wordmark />
      </Link>
      {children}
      <ThemeToggle />
    </header>
  )
}

/** "New to SlothSpend? [Create account]" — the header's switch between log in and sign up. */
export function HeaderSwitch({
  prompt,
  to,
  label
}: {
  prompt: string
  to: string
  label: string
}): React.JSX.Element {
  return (
    <>
      <span className="text-sm text-muted max-sm:hidden">{prompt}</span>
      <Link
        to={to}
        className="inline-flex h-11 items-center rounded-full border border-line-strong px-[18px] text-sm font-medium text-ink no-underline transition-colors duration-300 hover:border-ink"
      >
        {label}
      </Link>
    </>
  )
}
