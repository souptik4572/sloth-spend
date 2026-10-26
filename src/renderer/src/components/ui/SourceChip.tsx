import { Chip, type ChipSize } from './Chip'
import { gemmaLabel, gemmaWhere } from '../../lib/status'
import { useApp } from '../../store'

/** Which model (or fallback) produced a number or a piece of text. Every model output shows one (spec §9.1). */
export type Source =
  'gemma' | 'tabpfn-v2' | 'tabpfn-3.5' | 'tabpfn-3.5-fast' | 'heuristic' | 'template' | 'rules'

const LABELS: Record<Exclude<Source, 'gemma'>, string> = {
  'tabpfn-v2': 'TabPFN v2',
  'tabpfn-3.5': 'TabPFN-3.5',
  'tabpfn-3.5-fast': 'TabPFN-3.5 Fast',
  heuristic: 'Heuristic',
  template: 'Template',
  rules: 'Rule-based'
}

const HINTS: Partial<Record<Source, string>> = {
  heuristic:
    'TabPFN wasn’t available, so a simple rule scored this. Finish setup for model scores.',
  template: 'Gemma wasn’t available, so this text comes from a fixed template.',
  rules: 'Gemma wasn’t available, so merchant names come from a simple rule.'
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
  // Gemma chips name the Gemma model actually in use and where it ran: "Gemma 4 · local" on the desktop,
  // "Gemma 4 · Gemini API" on the web.
  const gemma = useApp((s) => gemmaLabel(s.health))
  const where = useApp((s) => gemmaWhere(s.health))
  const model = useApp((s) => (s.health?.llm.model_present ? s.health.llm.model : undefined))
  const fallback = source === 'heuristic' || source === 'template' || source === 'rules'
  const base = source === 'gemma' ? (where ? `${gemma} · ${where}` : gemma) : LABELS[source]
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
