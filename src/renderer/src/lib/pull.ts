// Ollama model download progress (IMPL M4.11): Ollama streams one progress line per layer
// ("pulling 4e30e2665218", completed, total). The bar shows the sum over layers plus a rolling-rate ETA.

export interface PullEvent {
  status: string
  completed?: number | null
  total?: number | null
}

export interface PullState {
  layers: Record<string, { completed: number; total: number }>
  status: string
}

export const emptyPull = (): PullState => ({ layers: {}, status: 'Starting download…' })

export function reducePull(state: PullState, ev: PullEvent): PullState {
  if (ev.status.startsWith('pulling ') && ev.total) {
    return {
      status: 'Downloading',
      layers: { ...state.layers, [ev.status]: { completed: ev.completed ?? 0, total: ev.total } }
    }
  }
  const status: Record<string, string> = {
    'pulling manifest': 'Starting download…',
    'verifying sha256 digest': 'Checking the download…',
    'writing manifest': 'Finishing up…',
    success: 'Done'
  }
  return { ...state, status: status[ev.status] ?? state.status }
}

export function pullTotals(state: PullState): { completed: number; total: number } {
  const layers = Object.values(state.layers)
  return {
    completed: layers.reduce((s, l) => s + l.completed, 0),
    total: layers.reduce((s, l) => s + l.total, 0)
  }
}

/** Download rate over the last `windowMs` (rolling 10 s, IMPL M4.11). */
export class RateMeter {
  private samples: Array<[number, number]> = []
  constructor(private readonly windowMs = 10_000) {}

  push(atMs: number, bytes: number): void {
    this.samples.push([atMs, bytes])
    while (this.samples.length > 2 && atMs - this.samples[0][0] > this.windowMs)
      this.samples.shift()
  }

  /** Bytes per second, or 0 until there are two samples. */
  rate(): number {
    if (this.samples.length < 2) return 0
    const [t0, b0] = this.samples[0]
    const [t1, b1] = this.samples[this.samples.length - 1]
    return t1 > t0 ? ((b1 - b0) * 1000) / (t1 - t0) : 0
  }
}

/** "About 6 min left" · "Less than a minute left" · "" while unknown. */
export function etaLabel(remainingBytes: number, bytesPerSecond: number): string {
  if (bytesPerSecond <= 0 || remainingBytes <= 0) return ''
  const seconds = remainingBytes / bytesPerSecond
  if (seconds < 60) return 'Less than a minute left'
  const minutes = Math.round(seconds / 60)
  if (minutes < 90) return `About ${minutes} min left`
  return `About ${Math.round(minutes / 60)} h left`
}
