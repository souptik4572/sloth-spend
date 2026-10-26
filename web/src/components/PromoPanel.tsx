import type { LucideIcon } from 'lucide-react'
import { Bell, Copy, TrendingUp } from 'lucide-react'
import { SlothAvatar } from '@renderer/components/brand/Logo'
import { cn } from '@renderer/lib/cn'

interface Finding {
  icon: LucideIcon
  iconClass: string
  merchant: string
  detail: string
  chip: string
  chipClass: string
}

// The kind of finding SlothSpend shows, from the bundled sample statement (fictional merchants).
const FINDINGS: Finding[] = [
  {
    icon: Copy,
    iconClass: 'bg-solid text-on-solid',
    merchant: 'IronTrap Fitness',
    detail: 'Charged $49.99 twice — Jul 5 and Jul 6',
    chip: 'Duplicate',
    chipClass: 'bg-accent'
  },
  {
    icon: TrendingUp,
    iconClass: 'bg-tint',
    merchant: 'TuneTide',
    detail: 'Went from $10.99 to $11.99 a month',
    chip: 'Price +9.1%',
    chipClass: 'bg-tint'
  },
  {
    icon: Bell,
    iconClass: 'bg-panel',
    merchant: 'WatchNest',
    detail: 'Renews Nov 20 — you’ll get a reminder 3 days before',
    chip: 'Reminder',
    chipClass: 'border border-line-strong'
  }
]

/** The pink panel beside Sign up and Log in. Ink on pink in both themes, so it pins the light tokens. */
export function PromoPanel(): React.JSX.Element {
  return (
    <aside
      data-theme="light"
      aria-label="About SlothSpend"
      className="box-border flex min-w-0 flex-[1_1_520px] flex-col gap-7 rounded-hero bg-accent p-12 text-ink max-sm:rounded-section max-sm:p-7"
    >
      <div>
        <p className="mt-0 mb-4 inline-flex h-7 items-center rounded-full bg-raised px-3 text-sm font-medium">
          SlothSpend on the web
        </p>
        <h2 className="m-0 font-display text-[52px] leading-none font-bold max-sm:text-[38px]">
          Find the subscriptions you forgot about.
        </h2>
        <p className="mt-4 mb-0 max-w-[34ch] text-lead">
          Upload a year of bank statements. SlothSpend spots price rises and double charges, and
          reminds you before renewals.
        </p>
      </div>
      <ul aria-label="What SlothSpend finds" className="m-0 flex list-none flex-col gap-2.5 p-0">
        {FINDINGS.map((f) => (
          <li
            key={f.merchant}
            className="flex items-center gap-3 rounded-tile bg-raised px-4 py-3.5"
          >
            <span
              className={cn(
                'flex size-9 shrink-0 items-center justify-center rounded-full',
                f.iconClass
              )}
            >
              <f.icon aria-hidden size={16} strokeWidth={2.4} />
            </span>
            <span className="min-w-0 flex-auto">
              <span className="block text-sm font-bold">{f.merchant}</span>
              <span className="block text-small text-text-2">{f.detail}</span>
            </span>
            <span
              className={cn(
                'box-border inline-flex h-6 items-center rounded-full px-2.5 text-xs font-medium whitespace-nowrap',
                f.chipClass
              )}
            >
              {f.chip}
            </span>
          </li>
        ))}
      </ul>
      <div className="mt-auto flex items-end justify-between gap-4">
        <p className="m-0 max-w-[32ch] text-small font-medium">
          SlothSpend informs, never acts. It never cancels anything or contacts anyone for you.
        </p>
        <SlothAvatar size={88} />
      </div>
    </aside>
  )
}
