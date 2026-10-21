import {
  forwardRef,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes
} from 'react'
import { cn } from '../../lib/cn'

const control =
  'h-11 w-full rounded-full border border-line-strong px-4 text-base text-ink placeholder:text-subtle ' +
  'transition-colors duration-300 ease-out disabled:cursor-not-allowed disabled:opacity-60'

export interface FieldProps {
  label: ReactNode
  hint?: ReactNode
  /** Render the label for screen readers only (chat input). */
  hideLabel?: boolean
  className?: string
  children: (id: string) => ReactNode
}

/** Label + control + optional hint. Labels stay visible unless hideLabel is set. */
export function Field({
  label,
  hint,
  hideLabel,
  className,
  children
}: FieldProps): React.JSX.Element {
  const id = useId()
  return (
    <div className={cn('flex min-w-0 flex-col gap-1.5', className)}>
      <label htmlFor={id} className={hideLabel ? 'sr-only' : 'text-sm font-medium'}>
        {label}
      </label>
      {children(id)}
      {hint && <p className="m-0 text-xs leading-[1.65] text-muted">{hint}</p>}
    </div>
  )
}

export interface TextInputProps extends InputHTMLAttributes<HTMLInputElement> {
  surface?: 'bg' | 'raised'
}

export const TextInput = forwardRef<HTMLInputElement, TextInputProps>(function TextInput(
  { surface = 'bg', className, ...rest },
  ref
) {
  return (
    <input
      ref={ref}
      className={cn(control, surface === 'bg' ? 'bg-bg' : 'bg-raised', className)}
      {...rest}
    />
  )
})

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  surface?: 'bg' | 'raised'
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { surface = 'raised', className, children, ...rest },
  ref
) {
  return (
    <select
      ref={ref}
      className={cn(
        control,
        'cursor-pointer pr-9 pl-3.5',
        surface === 'bg' ? 'bg-bg' : 'bg-raised',
        className
      )}
      {...rest}
    >
      {children}
    </select>
  )
})
