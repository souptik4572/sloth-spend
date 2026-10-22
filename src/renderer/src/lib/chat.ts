// Pure helpers for Ask Sloth (IMPL M6.5–M6.9): tool badges, draft cards, follow-ups and prompt chips.
import type { ChatTurn, Reminder, Report, Series, StoredMessage, ToolArgs, ToolCall } from './types'

/** Spec §7.9's suggested prompts, in order. */
export const SUGGESTED_PROMPTS = [
  'Why was IronTrap flagged, and did they ever double-charge me?',
  'What will subscriptions cost next month if I cancel StreamFlix and WatchNest?',
  'Which category grew the most this year?',
  'Draft a refund request for the duplicate IronTrap charge.',
  'Remind me three days before IronTrap renews.'
]

/** "Try asking": the suggestions not used in this conversation yet, at most three. */
export function unusedPrompts(turns: ChatTurn[], max = 3): string[] {
  const asked = new Set(turns.map((t) => t.user.trim().toLowerCase()))
  return SUGGESTED_PROMPTS.filter((p) => !asked.has(p.toLowerCase())).slice(0, max)
}

function pyValue(v: unknown): string {
  if (typeof v === 'string') return JSON.stringify(v)
  if (Array.isArray(v)) return `[${v.map(pyValue).join(', ')}]`
  if (v === null || v === undefined) return 'None'
  if (typeof v === 'boolean') return v ? 'True' : 'False'
  return typeof v === 'object' ? JSON.stringify(v) : String(v)
}

const PRIMARY = ['merchant', 'query']

/** get_merchant("IronTrap") · forecast_spend(days=30, exclude_merchants=["StreamFlix UHD", "WatchNest"]) */
export function formatCall(name: string, args: ToolArgs): string {
  // The subject of the call reads first, whatever order the model sent the arguments in.
  const entries = Object.entries(args).sort(
    ([a], [b]) => Number(PRIMARY.includes(b)) - Number(PRIMARY.includes(a))
  )
  const parts = entries.map(([k, v], i) =>
    i === 0 && typeof v === 'string' ? pyValue(v) : `${k}=${pyValue(v)}`
  )
  return `${name}(${parts.join(', ')})`
}

/** 42 ms · 1.4 s */
export function formatMs(ms: number): string {
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`
}

// ── drafts ──────────────────────────────────────────────────────────────────

export interface Draft {
  subject: string
  body: string
}

/** "Subject: …\n\nHello …" → its subject and body; null if it isn't an email. */
export function parseDraft(text: string): Draft | null {
  const m = /^\s*\**Subject:\**\s*(.*)\n?([\s\S]*)$/.exec(text)
  if (!m) return null
  const plain = (s: string): string => s.replace(/\*\*(.+?)\*\*/g, '$1')
  return {
    subject: plain(m[1].replace(/\*+$/, '')).trim(),
    body: plain(m[2].replace(/^\s*\n/, '')).trimEnd()
  }
}

export function draftTitle(subject: string): string {
  if (/refund/i.test(subject)) return 'Refund request'
  if (/cancel/i.test(subject)) return 'Cancellation request'
  return 'Negotiation email'
}

export type Segment = { kind: 'markdown'; text: string } | { kind: 'draft'; text: string }

/**
 * Split an answer into markdown and email drafts. Drafts are fenced blocks starting with "Subject:"
 * (the system prompt asks for that); an unfenced "Subject:" paragraph up to "[Your name]" also counts.
 * An unclosed fence while streaming is still drawn as a draft.
 */
export function splitDrafts(text: string): Segment[] {
  const out: Segment[] = []
  const fence = /```[\w-]*\n([\s\S]*?)(?:```|$)/g
  let last = 0
  let found = false
  for (let m = fence.exec(text); m; m = fence.exec(text)) {
    if (!/^\s*\**Subject:/.test(m[1])) continue
    found = true
    if (m.index > last) out.push({ kind: 'markdown', text: text.slice(last, m.index) })
    out.push({ kind: 'draft', text: m[1].trim() })
    last = m.index + m[0].length
  }
  if (found) {
    if (last < text.length) out.push({ kind: 'markdown', text: text.slice(last) })
  } else {
    const start = text.search(/^\s*\**Subject:/m)
    if (start < 0) return text ? [{ kind: 'markdown', text }] : []
    const sign = text.indexOf('[Your name]', start)
    const end = sign < 0 ? text.length : sign + '[Your name]'.length
    if (start > 0) out.push({ kind: 'markdown', text: text.slice(0, start) })
    out.push({ kind: 'draft', text: text.slice(start, end).trim() })
    if (end < text.length) out.push({ kind: 'markdown', text: text.slice(end) })
  }
  return out.filter((s) => s.kind === 'draft' || s.text.trim())
}

// ── history ─────────────────────────────────────────────────────────────────

/** Stored messages → turns: each user message starts one; tool records and the answer follow it. */
export function turnsFromHistory(messages: StoredMessage[]): ChatTurn[] {
  const turns: ChatTurn[] = []
  for (const m of messages) {
    if (m.role === 'user') {
      turns.push({ id: `h${m.id}`, user: m.content ?? '', tools: [], text: '', streaming: false })
      continue
    }
    const turn = turns[turns.length - 1]
    if (!turn) continue
    if (m.role === 'tool') {
      turn.tools.push({
        name: m.tool_name ?? 'tool',
        args: m.tool_args ?? {},
        preview: (m.content ?? '').slice(0, 300)
      })
    } else {
      turn.text += m.content ?? ''
    }
  }
  return turns
}

// ── follow-ups ──────────────────────────────────────────────────────────────

/** The report's series for a name a tool was called with ("irontrap" → IronTrap Fitness). */
export function matchSeries(name: string, series: Series[]): Series | null {
  const q = name.trim().toLowerCase()
  if (!q) return null
  const byPriority = [...series].sort((a, b) => b.priority - a.priority)
  return (
    byPriority.find((s) => s.merchant.toLowerCase() === q) ??
    byPriority.find(
      (s) => s.merchant.toLowerCase().includes(q) || q.includes(s.merchant.toLowerCase())
    ) ??
    byPriority.find((s) => s.merchant.toLowerCase().split(' ')[0] === q.split(' ')[0]) ??
    null
  )
}

export interface FollowUp {
  label: string
  prompt: string
}

/**
 * Buttons under a finished answer (IMPL M6.8), from the merchants its tools looked at: a refund draft for
 * a double charge, a reminder for a cancellable subscription, a negotiation email for a bill.
 */
export function followUps(
  turn: ChatTurn,
  report: Report | null,
  reminders: Reminder[] = [],
  max = 3
): FollowUp[] {
  if (!report || turn.streaming || turn.error) return []
  const merchants: Series[] = []
  for (const call of turn.tools) {
    const name = call.args.merchant
    if (typeof name !== 'string') continue
    const s = matchSeries(name, report.series)
    if (s && !merchants.includes(s)) merchants.push(s)
  }
  const drafted = parseDraftsIn(turn.text)
  const reminded = turn.tools.some((t) => t.name === 'set_renewal_reminder')
  const out: FollowUp[] = []
  // With several merchants in one answer, each button says which one it is for.
  const named = (label: string, m: string): string =>
    merchants.length > 1 ? `${label} · ${m}` : label
  for (const s of merchants) {
    const m = s.merchant
    if (s.flags.includes('duplicate_charge') && !drafted.has('Refund request')) {
      out.push({
        label: named('Draft refund request', m),
        prompt: `Draft a refund request for the duplicate ${m} charge.`
      })
    }
    const watched = reminders.some((r) => r.series_id === s.id && r.group !== 'done')
    if (
      s.cancellable &&
      s.next_due_date &&
      s.status !== 'user_cancelled' &&
      !reminded &&
      !watched
    ) {
      out.push({
        label: named('Remind me 3 days before', m),
        prompt: `Remind me 3 days before ${m} renews.`
      })
    }
    if (s.kind === 'bill' && !drafted.has('Negotiation email')) {
      out.push({
        label: named('Draft negotiation email', m),
        prompt: `Draft a negotiation email for ${m}.`
      })
    }
  }
  return out.slice(0, max)
}

function parseDraftsIn(text: string): Set<string> {
  const titles = new Set<string>()
  for (const seg of splitDrafts(text)) {
    const d = seg.kind === 'draft' ? parseDraft(seg.text) : null
    if (d) titles.add(draftTitle(d.subject))
  }
  return titles
}

/** The findings table's Ask Sloth (IMPL M5.7): what to pre-fill for a row. */
export function askAbout(s: Series): string {
  return s.flags.length ? `Why was ${s.merchant} flagged?` : `Tell me about ${s.merchant}.`
}

/** A set_renewal_reminder call that worked → its reminder date ("Nov 2, 2026"), for the link-chip. */
export function reminderSetOn(call: ToolCall): string | null {
  if (call.name !== 'set_renewal_reminder' || !call.preview) return null
  if (!/"reminder_set":\s*true/.test(call.preview)) return null
  return /"remind_on":\s*"([^"]+)"/.exec(call.preview)?.[1] ?? 'your chosen day'
}
