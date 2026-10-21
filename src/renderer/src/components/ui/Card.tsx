import type { ElementType, HTMLAttributes, ReactNode } from 'react'
import { cn } from '../../lib/cn'

export type CardTone = 'bg' | 'card' | 'panel' | 'raised' | 'solid' | 'accent' | 'outlined'
export type CardRadius = 'hero' | 'section' | 'card' | 'tile'

const tones: Record<CardTone, string> = {
  bg: 'bg-bg',
  card: 'bg-card',
  panel: 'bg-panel',
  raised: 'bg-raised',
  solid: 'bg-solid text-on-solid',
  accent: 'bg-accent text-ink',
  outlined: 'bg-bg border border-line'
}

const radii: Record<CardRadius, string> = {
  hero: 'rounded-hero',
  section: 'rounded-section',
  card: 'rounded-card',
  tile: 'rounded-tile'
}

export interface CardProps extends HTMLAttributes<HTMLElement> {
  as?: ElementType
  tone?: CardTone
  radius?: CardRadius
  children?: ReactNode
}

/**
 * Tonal surface. Accent (pink) cards force the light token set on themselves so
 * ink-on-pink stays dark in dark mode — exactly what the design does.
 */
export function Card({
  as: Tag = 'div',
  tone = 'card',
  radius = 'card',
  className,
  children,
  ...rest
}: CardProps): React.JSX.Element {
  return (
    <Tag
      data-theme={tone === 'accent' ? 'light' : undefined}
      className={cn(tones[tone], radii[radius], className)}
      {...rest}
    >
      {children}
    </Tag>
  )
}
