import { fetchEventSource } from '@microsoft/fetch-event-source'
import type { RendererConfig } from '../../../preload'
import type {
  EngineSettings,
  Health,
  ImportPayload,
  LabelKind,
  Notice,
  Reminder,
  ReminderResult,
  Report,
  SeriesDetail,
  StoredMessage
} from './types'

let cfg: RendererConfig | null = null

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: string
  ) {
    super(`${status}: ${body}`)
  }
}

/**
 * Desktop: the per-launch token (X-Sloth-Token). Web: the session cookie travels by itself, and every request
 * carries the CSRF header the server's gate requires (WEB-IMPL §2.3).
 */
function authHeaders(): Record<string, string> {
  const { token, platform } = config()
  return platform === 'web' ? { 'X-Sloth-CSRF': '1' } : { 'X-Sloth-Token': token }
}

/** On the web a 401 means the session ended (expired, or logged out elsewhere): the web app shows Log in. */
export const SIGNED_OUT_EVENT = 'sloth:signed-out'

function checkSession(status: number): void {
  if (status === 401 && config().platform === 'web')
    window.dispatchEvent(new Event(SIGNED_OUT_EVENT))
}

/** Fetches apiBase + token from main once. Call before any other function here. */
export async function init(): Promise<RendererConfig> {
  cfg = await window.sloth.getConfig()
  return cfg
}

function config(): RendererConfig {
  if (!cfg) throw new Error('api.init() has not run')
  return cfg
}

export async function req<T>(
  method: string,
  path: string,
  body?: unknown,
  signal?: AbortSignal
): Promise<T> {
  const { apiBase } = config()
  const isForm = body instanceof FormData
  const r = await fetch(apiBase + path, {
    method,
    signal,
    headers: {
      ...authHeaders(),
      ...(body !== undefined && !isForm ? { 'Content-Type': 'application/json' } : {})
    },
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body)
  })
  if (!r.ok) {
    checkSession(r.status)
    throw new ApiError(r.status, await r.text())
  }
  return (await r.json()) as T
}

/**
 * POST + server-sent events with the token header (EventSource can't send headers).
 * openWhenHidden keeps streams alive when the window is hidden; errors are thrown, never retried,
 * so a pipeline is never re-run silently.
 */
export function stream(
  path: string,
  body: unknown,
  on: Record<string, (data: unknown) => void>,
  signal?: AbortSignal
): Promise<void> {
  const { apiBase } = config()
  return fetchEventSource(apiBase + path, {
    method: 'POST',
    body: JSON.stringify(body ?? {}),
    signal,
    openWhenHidden: true,
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    onopen: async (r) => {
      // 409 busy, 410 file gone, 422 bad mapping…: surface the engine's own sentence.
      if (!r.ok) {
        checkSession(r.status)
        throw new ApiError(r.status, await r.text())
      }
    },
    onmessage: (ev) => on[ev.event]?.(ev.data ? JSON.parse(ev.data) : null),
    onerror: (err) => {
      throw err
    }
  })
}

export const getHealth = (signal?: AbortSignal): Promise<Health> =>
  req<Health>('GET', '/health', undefined, signal)

/** The engine's user-facing sentence from an error ({"detail": "…"}), or a calm fallback. */
export function errorMessage(
  err: unknown,
  fallback = 'Something went wrong. Please try again.'
): string {
  if (err instanceof ApiError) {
    try {
      const detail = (JSON.parse(err.body) as { detail?: unknown }).detail
      if (typeof detail === 'string') return detail
    } catch {
      /* not JSON */
    }
    return err.status === 0 ? fallback : `${fallback} (${err.status})`
  }
  return fallback
}

// ── audit (IMPL M4.8) ───────────────────────────────────────────────────────

export function uploadStatement(file: File): Promise<ImportPayload> {
  const form = new FormData()
  form.append('file', file, file.name)
  return req<ImportPayload>('POST', '/import', form)
}

export const discardImport = (id: number): Promise<{ ok: boolean }> =>
  req('DELETE', `/import/${id}`)

export const getReport = (): Promise<Report> => req<Report>('GET', '/report')

export interface AuditStatus {
  running: boolean
  file: string | null
  rows: number | null
  /** Seconds since the epoch, on the engine's clock. */
  started_at: number | null
}

/** Is an audit running? A reloaded or second tab follows it (`/audit/follow`) instead of showing old data. */
export const getAuditStatus = (): Promise<AuditStatus> => req<AuditStatus>('GET', '/audit')

export const rescoreReport = (): Promise<{ report: Report }> => req('POST', '/report/rescore')

export const getSeries = (id: number): Promise<SeriesDetail> =>
  req<SeriesDetail>('GET', `/series/${id}`)

export const labelSeries = (id: number, label: LabelKind): Promise<{ report: Report }> =>
  req('POST', `/series/${id}/label`, { label })

export const renameSeries = (
  id: number,
  merchant: string,
  category: string
): Promise<{ report: Report; series_id: number | null }> =>
  req('PATCH', `/series/${id}/merchant`, { merchant, category })

// ── Ask Sloth and drafts (IMPL M6) ─────────────────────────────────────────

export const getChat = (cid: string): Promise<{ messages: StoredMessage[] }> =>
  req('GET', `/chat/${encodeURIComponent(cid)}`)

// ── Reminders and notifications (IMPL M7) ──────────────────────────────────

export const getSettings = (): Promise<EngineSettings> => req('GET', '/settings')

export const listReminders = (): Promise<Reminder[]> => req('GET', '/reminders')

export const createReminder = (seriesId: number, daysBefore?: number): Promise<ReminderResult> =>
  req('POST', '/reminders', { series_id: seriesId, days_before: daysBefore })

export type ReminderAction = 'keep' | 'stop' | 'snooze' | 'cancelled'

export const reminderAction = (
  seriesId: number,
  action: ReminderAction,
  body?: { days?: number; cancelled_on?: string }
): Promise<ReminderResult> => req('POST', `/reminders/${seriesId}/${action}`, body ?? {})

export const notificationsSince = (sinceId: number): Promise<Notice[]> =>
  req('GET', `/notifications?since_id=${sinceId}`)

export const notificationInbox = (): Promise<Notice[]> => req('GET', '/notifications?all=1')

export const markNoticeRead = (id: number): Promise<{ ok: boolean }> =>
  req('POST', `/notifications/${id}/read`)

export const markAllNoticesRead = (): Promise<{ ok: boolean }> =>
  req('POST', '/notifications/read-all')

// ── Settings and privacy (IMPL M8) ─────────────────────────────────────────

export const putSettings = (patch: Partial<EngineSettings>): Promise<EngineSettings> =>
  req('PUT', '/settings', patch)

export const deleteData = (): Promise<{ ok: boolean }> => req('DELETE', '/data')
