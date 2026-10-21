import { Chip, type ChipSize } from './Chip'
import { gemmaLabel } from '../../lib/status'
import { useApp } from '../../store'

/** Which model (or fallback) produced a number or a piece of text. Every model output shows one (spec §9.1). */
export type Source = 'gemma' | 'tabpfn-3.5' | 'tabpfn-3.5-fast' | 'heuristic' | 'template'

const LABELS: Record<Exclude<Source, 'gemma'>, string> = {
  'tabpfn-3.5': 'TabPFN-3.5',
  'tabpfn-3.5-fast': 'TabPFN-3.5 Fast',
  heuristic: 'Heuristic',
  template: 'Template'
}

const HINTS: Partial<Record<Source, string>> = {
  heuristic:
    'TabPFN-3.5 isn’t set up, so a simple rule scored this. Finish setup for model scores.',
  template: 'Gemma wasn’t available, so this text comes from a fixed template.'
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
  // Gemma chips name whichever Gemma model Ollama is actually running ("Gemma 4 · local", "Gemma 3 · local").
  const gemma = useApp((s) => gemmaLabel(s.health))
  const model = useApp((s) => (s.health?.ollama.model_present ? s.health.ollama.model : undefined))
  const fallback = source === 'heuristic' || source === 'template'
  const base = source === 'gemma' ? `${gemma} · local` : LABELS[source]
  const label = base + (live ? ' · live' : '')
  const hint = source === 'gemma' ? model : HINTS[source]
  return (
    <Chip
      size={size}
      variant={fallback ? 'dashed' : onPanel ? 'raised' : 'tint'}
      title={hint}
      className={onPanel && !fallback ? 'border-raised' : undefined}
    >
      {label}
    </Chip>
  )
}
