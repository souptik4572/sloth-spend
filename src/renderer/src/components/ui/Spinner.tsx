import { LoaderCircle } from 'lucide-react'
import { cn } from '../../lib/cn'

export function Spinner({
  size = 16,
  label,
  className
}: {
  size?: number
  label?: string
  className?: string
}): React.JSX.Element {
  return (
    <LoaderCircle
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      size={size}
      strokeWidth={2.4}
      className={cn('animate-spin motion-reduce:animate-none', className)}
    />
  )
}
