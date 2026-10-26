import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@renderer/lib/cn'
import { PromoPanel } from './PromoPanel'

/** Sign up and Log in: the form on the left, the pink "what SlothSpend finds" panel on the right. */
export function SplitLayout({
  labelledBy,
  children
}: {
  labelledBy: string
  children: ReactNode
}): React.JSX.Element {
  return (
    <main className="mx-auto box-border flex w-full max-w-[1312px] flex-1 flex-wrap items-stretch gap-6 px-6 pt-2 pb-8 max-sm:px-4">
      <section
        aria-labelledby={labelledBy}
        className="box-border flex min-w-0 flex-[1_1_480px] items-center justify-center px-4 py-6 max-sm:px-0"
      >
        <div className="flex w-full max-w-[440px] flex-col gap-6">{children}</div>
      </section>
      <PromoPanel />
    </main>
  )
}

/** Check your inbox, Forgot and Reset password: one card in the middle of the page. */
export function CardLayout({
  labelledBy,
  centered = false,
  children
}: {
  labelledBy: string
  centered?: boolean
  children: ReactNode
}): React.JSX.Element {
  return (
    <main className="box-border flex flex-1 items-center justify-center px-4 pt-8 pb-14">
      <section
        aria-labelledby={labelledBy}
        className={cn(
          'box-border flex w-full flex-col gap-6 rounded-section bg-card px-11 py-12 max-sm:px-6 max-sm:py-9',
          centered ? 'max-w-[560px] items-center text-center' : 'max-w-[520px]'
        )}
      >
        {children}
      </section>
    </main>
  )
}

export function IconBadge({
  icon: Icon,
  tone = 'panel',
  large = false
}: {
  icon: LucideIcon
  tone?: 'panel' | 'accent' | 'success'
  large?: boolean
}): React.JSX.Element {
  return (
    <span
      className={cn(
        'flex shrink-0 items-center justify-center rounded-full',
        large ? 'size-20' : 'size-[72px]',
        tone === 'panel' && 'bg-panel text-ink',
        tone === 'accent' && 'bg-accent text-on-accent',
        tone === 'success' && 'bg-success-tint text-success'
      )}
    >
      <Icon aria-hidden size={large ? 36 : 32} strokeWidth={2} />
    </span>
  )
}

/** The page heading plus its one-line explanation. */
export function Heading({
  id,
  size = 'card',
  title,
  children
}: {
  id: string
  size?: 'hero' | 'card'
  title: ReactNode
  children?: ReactNode
}): React.JSX.Element {
  return (
    <div>
      <h1
        id={id}
        tabIndex={-1}
        className={cn(
          'm-0 font-display font-bold outline-none',
          size === 'hero'
            ? 'text-[52px] leading-none max-sm:text-[40px]'
            : 'text-[44px] leading-[1.1] max-sm:text-[36px]'
        )}
      >
        {title}
      </h1>
      {children && <p className="mt-3.5 mb-0 text-base leading-normal text-text-2">{children}</p>}
    </div>
  )
}
