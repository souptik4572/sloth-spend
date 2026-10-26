import { forwardRef, useId, useState, type InputHTMLAttributes, type ReactNode } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { cn } from '@renderer/lib/cn'

const input =
  'box-border h-[52px] w-full rounded-full bg-raised px-5 font-sans text-base text-ink placeholder:text-subtle ' +
  'transition-colors duration-300 ease-out disabled:opacity-60'

export interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  /** Something on the label's line, right-aligned ("Forgot password?"). */
  aside?: ReactNode
  /** Under the input (password rules, "Passwords match"). */
  below?: ReactNode
  invalid?: boolean
}

/** The 52 px pill input of the web auth designs, with a visible label. */
export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, aside, below, invalid, className, id, ...rest },
  ref
) {
  const auto = useId()
  const inputId = id ?? auto
  return (
    <div className={cn('flex flex-col', below ? 'gap-2' : 'gap-1.5')}>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={inputId} className="text-sm font-medium">
          {label}
        </label>
        {aside}
      </div>
      <input
        ref={ref}
        id={inputId}
        aria-invalid={invalid || undefined}
        className={cn(
          input,
          invalid ? 'border-2 border-ink' : 'border border-line-strong',
          className
        )}
        {...rest}
      />
      {below}
    </div>
  )
})

export interface PasswordFieldProps extends Omit<TextFieldProps, 'type'> {
  /** Controlled visibility, so "Type it again" can follow the same eye button. */
  shown?: boolean
  onShownChange?: (shown: boolean) => void
  toggleLabel?: string
}

/** A password input with the eye button inside it (44 px target). */
export const PasswordField = forwardRef<HTMLInputElement, PasswordFieldProps>(
  function PasswordField(
    {
      label,
      aside,
      below,
      invalid,
      shown,
      onShownChange,
      toggleLabel = 'Show password',
      id,
      ...rest
    },
    ref
  ) {
    const auto = useId()
    const inputId = id ?? auto
    const [own, setOwn] = useState(false)
    const visible = shown ?? own
    const toggle = (): void => (onShownChange ? onShownChange(!visible) : setOwn(!visible))
    return (
      <div className={cn('flex flex-col', below ? 'gap-2' : 'gap-1.5')}>
        <div className="flex items-baseline justify-between gap-3">
          <label htmlFor={inputId} className="text-sm font-medium">
            {label}
          </label>
          {aside}
        </div>
        <div className="relative">
          <input
            ref={ref}
            id={inputId}
            type={visible ? 'text' : 'password'}
            aria-invalid={invalid || undefined}
            className={cn(
              input,
              'pr-[60px]',
              invalid ? 'border-2 border-ink' : 'border border-line-strong'
            )}
            {...rest}
          />
          <button
            type="button"
            onClick={toggle}
            aria-label={toggleLabel}
            aria-pressed={visible}
            aria-controls={inputId}
            className="absolute top-1 right-1 flex size-11 cursor-pointer items-center justify-center rounded-full border-0 bg-transparent text-muted transition-colors hover:bg-ink/5"
          >
            {visible ? <EyeOff aria-hidden size={20} /> : <Eye aria-hidden size={20} />}
          </button>
        </div>
        {below}
      </div>
    )
  }
)

/** "Keep me logged in on this device", "I agree to the Terms…". */
export function Checkbox({
  checked,
  onChange,
  children,
  align = 'center'
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  children: ReactNode
  align?: 'center' | 'start'
}): React.JSX.Element {
  return (
    <label
      className={cn(
        'flex min-h-11 cursor-pointer gap-3 text-sm leading-[1.45] text-text-2',
        align === 'center' ? 'items-center' : 'items-start'
      )}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="m-0 size-5 shrink-0 cursor-pointer accent-[var(--ink)]"
      />
      <span>{children}</span>
    </label>
  )
}
