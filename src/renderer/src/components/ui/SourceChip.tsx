import { Chip, type ChipSize } from './Chip'

/** Which model (or fallback) produced a number or a piece of text. Every model output shows one (spec §9.1). */
export type Source = 'gemma' | 'tabpfn-3.5' | 'tabpfn-3.5-fast' | 'heuristic' | 'template'

const LABELS: Record<Source, string> = {
  gemma: 'Gemma 4 · local',
  'tabpfn-3.5': 'TabPFN-3.5',
  'tabpfn-3.5-fast': 'TabPFN-3.5 Fast',
  heuristic: 'Heuristic',
  template: 'Template'
}

const HINTS: Partial<Record<Source, string>> = {
  heuristic:
    'TabPFN-3.5 isn’t set up, so a simple rule scored this. Finish setup for model scores.',
  template: 'Gemma 4 wasn’t available, so this text comes from a fixed template.'
}

export interface SourceChipProps {
  source: Source
  /** Adds "· live" for tools that re-ran the model just now. */
  live?: boolean
  /** Raised background (on tinted panels) instead of tint. */
  onPanel?: boolean
  size?: ChipSize
}

export function SourceChip({
  source,
  live,
  onPanel,
  size = 22
}: SourceChipProps): React.JSX.Element {
  const fallback = source === 'heuristic' || source === 'template'
  const label = LABELS[source] + (live ? ' · live' : '')
  return (
    <Chip
      size={size}
      variant={fallback ? 'dashed' : onPanel ? 'raised' : 'tint'}
      title={HINTS[source]}
      className={onPanel && !fallback ? 'border-raised' : undefined}
    >
      {label}
    </Chip>
  )
}
