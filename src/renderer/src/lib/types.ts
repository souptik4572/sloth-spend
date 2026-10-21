// Shared API types (IMPL §3.3). They mirror the engine's responses; change both in the same commit.
// Types arrive milestone by milestone as the endpoints do.

export type Scorer = 'tabpfn-3.5' | 'tabpfn-3.5-fast' | 'heuristic'

export type OllamaStatus = 'ready' | 'unreachable' | 'outdated' | 'missing_model'
export type TabpfnStatus = 'cold' | 'warming' | 'ready' | 'missing_weights' | 'error'

export interface Health {
  engine: 'ok'
  ollama: {
    status: OllamaStatus
    version: string | null
    /** The installed Gemma model in use, or the one offered for download when none is installed. */
    model: string
    model_present: boolean
    /** Every installed Gemma model, best first. */
    available_models: string[]
    loopback: boolean
  }
  tabpfn: { status: TabpfnStatus; model: Scorer | null; error: string | null }
  telemetry: boolean
}
