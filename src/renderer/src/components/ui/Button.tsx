import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '../../lib/cn'

export type ButtonVariant = 'solid' | 'outline' | 'soft' | 'ghost' | 'outline-strong' | 'danger'
export type ButtonSize = 'lg' | 'md'

const variants: Record<ButtonVariant, string> = {
  solid: 'bg-solid text-on-solid border border-solid hover:opacity-90',
  outline: 'bg-transparent text-ink border border-ink hover:bg-ink/5',
  soft: 'bg-raised text-ink border border-line hover:border-line-strong',
  ghost: 'bg-transparent text-ink border border-transparent hover:bg-ink/5',
  'outline-strong': 'bg-transparent text-ink border border-line-strong hover:border-ink',
  danger: 'bg-transparent text-ink border border-ink hover:bg-accent-tint'
}

const sizes: Record<ButtonSize, string> = {
  lg: 'h-[52px] px-5 text-base gap-2',
  md: 'h-11 px-4 text-sm gap-2'
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  icon?: LucideIcon
  iconRight?: LucideIcon
  children?: ReactNode
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = 'soft',
    size = 'md',
    icon: Icon,
    iconRight: IconRight,
    className,
    children,
    type,
    ...rest
  },
  ref
) {
  return (
    <button
      ref={ref}
      type={type ?? 'button'}
      className={cn(
        'inline-flex shrink-0 cursor-pointer items-center justify-center rounded-full font-medium whitespace-nowrap',
        'transition-[background-color,border-color,opacity] duration-300 ease-out',
        'disabled:cursor-not-allowed disabled:opacity-50',
        variants[variant],
        sizes[size],
        className
      )}
      {...rest}
    >
      {Icon && <Icon aria-hidden size={size === 'lg' ? 18 : 16} strokeWidth={2} />}
      {children}
      {IconRight && <IconRight aria-hidden size={16} strokeWidth={2} />}
    </button>
  )
})

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: LucideIcon
  label: string
  bordered?: boolean
}

/** 44 px round icon-only button; `label` becomes its accessible name. */
export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { icon: Icon, label, bordered = true, className, type, ...rest },
  ref
) {
  return (
    <button
      ref={ref}
      type={type ?? 'button'}
      aria-label={label}
      title={label}
      className={cn(
        'relative inline-flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-full text-ink',
        'transition-colors duration-300 ease-out hover:bg-ink/5 disabled:cursor-not-allowed disabled:opacity-50',
        bordered ? 'border border-line-strong' : 'border border-transparent',
        className
      )}
      {...rest}
    >
      <Icon aria-hidden size={20} strokeWidth={2} />
    </button>
  )
})
