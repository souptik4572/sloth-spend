import { Circle, CircleAlert, CircleCheck } from 'lucide-react'
import { cn } from '@renderer/lib/cn'
import { strength, type Rule } from '@web/lib/password'

/** The three rules, ticked as they're met; screen readers hear "Done:" / "Still needed:". */
export function PasswordRules({ id, rules }: { id: string; rules: Rule[] }): React.JSX.Element {
  return (
    <ul id={id} className="m-0 flex list-none flex-col gap-1 p-0">
      {rules.map((r) => (
        <li
          key={r.label}
          className={cn('flex items-center gap-2 text-small', r.ok ? 'text-ink' : 'text-muted')}
        >
          {r.ok ? (
            <CircleCheck
              aria-hidden
              size={16}
              strokeWidth={2.4}
              className="shrink-0 text-success"
            />
          ) : (
            <Circle aria-hidden size={16} strokeWidth={2} className="shrink-0 text-subtle" />
          )}
          <span>
            <span className="sr-only">{r.ok ? 'Done: ' : 'Still needed: '}</span>
            {r.label}
          </span>
        </li>
      ))}
    </ul>
  )
}

/** Three segments and a word (Sign up, artboard 10). Decorative: the rules list says the same in words. */
export function StrengthMeter({ rules }: { rules: Rule[] }): React.JSX.Element {
  const { met, label } = strength(rules)
  return (
    <div className="flex items-center gap-2.5">
      <div aria-hidden className="flex flex-auto gap-1">
        {rules.map((r, i) => (
          <span
            key={r.label}
            className={cn(
              'h-1.5 flex-1 rounded-full transition-colors duration-300',
              i < met ? (met === rules.length ? 'bg-success' : 'bg-ink') : 'bg-tint'
            )}
          />
        ))}
      </div>
      <span className="min-w-[84px] text-right text-xs font-medium text-muted" aria-live="polite">
        {label}
      </span>
    </div>
  )
}

/** "Passwords match" under "Type it again" (Reset password, artboard 14). */
export function MatchNote({
  id,
  password,
  confirm
}: {
  id: string
  password: string
  confirm: string
}): React.JSX.Element {
  const empty = confirm.length === 0
  const matches = !empty && confirm === password
  return (
    <p
      id={id}
      aria-live="polite"
      className={cn(
        'm-0 flex items-center gap-2 text-small',
        empty ? 'text-muted' : 'text-ink',
        !empty && !matches && 'font-medium'
      )}
    >
      {matches && (
        <CircleCheck aria-hidden size={16} strokeWidth={2.4} className="shrink-0 text-success" />
      )}
      {!empty && !matches && (
        <CircleAlert aria-hidden size={16} strokeWidth={2.2} className="shrink-0" />
      )}
      {matches
        ? 'Passwords match'
        : empty
          ? 'Type the same password again'
          : 'These don’t match yet'}
    </p>
  )
}
