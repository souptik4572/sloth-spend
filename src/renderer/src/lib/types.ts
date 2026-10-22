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

// ── audit (IMPL §3.2–3.4) ───────────────────────────────────────────────────

export type Currency = 'USD' | 'INR' | 'EUR' | 'GBP'
export type Cadence =
  'weekly' | 'biweekly' | 'monthly' | 'quarterly' | 'annual' | 'irregular' | 'single'
export type FlagId =
  'duplicate_charge' | 'price_creep' | 'overlap' | 'possible_annual' | 'zombie_suspect'
export type SeriesStatus = 'active' | 'keep' | 'not_subscription' | 'user_cancelled'
export type Kind = 'subscription' | 'bill' | 'other'
export type LabelKind = 'subscription' | 'not_subscription' | 'keep'
export type ColumnRole = 'date' | 'description' | 'amount' | 'debit' | 'credit' | 'type' | 'ignore'

export interface Q {
  q10: number
  q50: number
  q90: number
}

export interface DuplicatePair {
  first: string
  second: string
  amount: number
  tx_ids: number[]
}

export interface FlagDetails {
  duplicate_charge?: DuplicatePair[]
  price_creep?: { from: number; to: number; pct: number; since: string }
  overlap?: { category: string; merchants: string[] }
  possible_annual?: { next_due: string }
  zombie_suspect?: { because: string[] }
}

export interface Series {
  id: number
  merchant: string
  category: string
  kind: Kind
  n_charges: number
  first_date: string
  last_date: string
  cadence: Cadence
  cadence_days: number | null
  dom_median: number | null
  last_amount: number
  monthly_equiv: number
  amount_varies: boolean
  recurring_prob: number | null
  scorer: Scorer
  next_due_date: string | null
  fc_q10: number | null
  fc_q50: number | null
  fc_q90: number | null
  hike_prob: number | null
  flags: FlagId[]
  flag_details: FlagDetails
  priority: number
  cancellable: boolean
  status: SeriesStatus
}

export interface ImportInfo {
  id: number
  file_name: string
  row_count: number
  skipped_rows: number
  period_start: string
  period_end: string
  imported_at: string
  verified_count: number
}

export interface ReportMeta {
  generated_at: string
  report_date: string
  currency: Currency
  scorer: Scorer
  monthly_recurring: number
  monthly_subscriptions: number
  monthly_bills: number
  fc30: Q
  potential_savings: number
  zombie_count: number
  dispute_total: number
  flag_counts: Record<FlagId, number>
  flagged_merchants: number
  executive_summary: string
  summary_source: 'gemma' | 'template'
  imports: ImportInfo[]
}

export interface MonthPoint {
  month: string
  subscriptions: number
  all: number
  partial: boolean
  highlights: string[]
}

export interface Report {
  meta: ReportMeta
  series: Series[]
  monthly: MonthPoint[]
  forecast_next: { subscriptions: Q; all: Q }
}

export interface SeriesDetail {
  series: Series
  transactions: { id: number; date: string; amount: number; is_duplicate: boolean }[]
  quantiles: { q: number; amount: number }[]
  similar: { archetype: string; count: number; k: number; runner_up: string | null } | null
  reasons: string[]
  raw_descriptions: string[]
  desc_keys: string[]
  reminder: Reminder | null
}

export interface ImportPayload {
  import_id: number
  duplicate: boolean
  file_name: string
  needs_mapping: boolean
  // Only on a fresh upload (absent when duplicate):
  header_row?: number
  header?: string[]
  mapping?: Partial<Record<Exclude<ColumnRole, 'ignore'>, number>>
  missing?: string[]
  columns?: { index: number; name: string; role: ColumnRole }[]
  preview?: string[][]
  currency?: Currency
  currency_detected?: boolean
  dayfirst?: boolean
  debits_positive?: boolean | null
  sign_ambiguous?: boolean
  row_count?: number
  remembered?: boolean
}

export type StageId =
  | 'parse'
  | 'normalize'
  | 'detect'
  | 'features'
  | 'score'
  | 'forecast'
  | 'flags'
  | 'summary'
  | 'done'

export interface StageEvent {
  stage: StageId
  done: number
  total: number
  note?: string
  source?: string | null
}

// ── Ask Sloth (IMPL M6) ─────────────────────────────────────────────────────

export type ToolArgs = Record<string, unknown>

/** One tool call in a turn, as the badges draw it. `ms`/`preview` arrive with tool_end. */
export interface ToolCall {
  name: string
  args: ToolArgs
  ms?: number
  preview?: string
  /** The scorer for live TabPFN tools (forecast_spend, score_merchant). */
  live?: string
}

export interface ChatTurn {
  id: string
  user: string
  tools: ToolCall[]
  text: string
  streaming: boolean
  error?: string
}

/** GET /chat/{cid}: everything stored, oldest first. */
export interface StoredMessage {
  id: number
  role: 'user' | 'assistant' | 'tool'
  content: string | null
  tool_name: string | null
  tool_args: ToolArgs | null
  created_at: string
}

export type DraftKind = 'cancel_request' | 'refund' | 'negotiate'

export interface DraftDone {
  text: string
  source: 'gemma' | 'template'
  title: string
}

// ── Reminders and notifications (IMPL M7, §3.2) ─────────────────────────────

export type Phase =
  | 'WATCHING'
  | 'REMINDED'
  | 'SNOOZED'
  | 'AWAITING_STATEMENT'
  | 'STILL_CHARGED'
  | 'KEPT'
  | 'EXPIRED'
  | 'STOPPED'
  | 'VERIFIED_STOPPED'

export interface Reminder {
  series_id: number
  merchant: string
  amount: number | null
  cadence: Cadence | null
  monthly_equiv: number | null
  low_confidence: boolean
  cancellable: boolean
  next_due_date: string
  days_left: number | null
  phase: Phase
  group: 'needs_you' | 'watching' | 'done'
  detail: string | null
  days_before: number
  remind_at: string | null
  remind_on: string | null
  reminders_sent: number
  max_reminders: number
  cancelled_on: string | null
  events: { phase: Phase; at: string }[]
  /** STILL_CHARGED: the charge after cancelling; VERIFIED_STOPPED: how far the statements reach. */
  checked: { date: string; amount: number | null } | null
}

export interface ReminderResult {
  series_id: number
  phase: Phase
  remind_at: string | null
  reminder: Reminder | null
  report?: Report
}

export interface Notice {
  id: number
  series_id: number
  kind: 'reminder' | 'verified' | 'still_charged'
  title: string
  body: string
  created_at: string
  read_at: string | null
}

export interface EngineSettings {
  currency: Currency
  chat_model: string | null
  days_before: number
  demo_compress_seconds: number
}
