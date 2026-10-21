// Shared API types (IMPL §3.3). They mirror the engine's responses; change both in the same commit.
// Types arrive milestone by milestone as the endpoints do.

/** Which model scored a result. TabPFN v2 is the default; 3.5 is the optional key upgrade (IMPL §2 #21). */
export type Scorer = 'tabpfn-v2' | 'tabpfn-3.5' | 'tabpfn-3.5-fast' | 'heuristic'

export type OllamaStatus = 'ready' | 'unreachable' | 'outdated' | 'missing_model'
export type TabpfnStatus = 'cold' | 'downloading' | 'warming' | 'ready' | 'unavailable' | 'error'
/** none = no key stored · active = TabPFN-3.5 in use · failed = still on v2, see error. */
export type UpgradeState = 'none' | 'downloading' | 'active' | 'failed'

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
  tabpfn: {
    status: TabpfnStatus
    /** The TabPFN version in use, once loaded. */
    model: Exclude<Scorer, 'heuristic'> | null
    error: string | null
    upgrade: { state: UpgradeState; error: string | null }
  }
  telemetry: boolean
}
