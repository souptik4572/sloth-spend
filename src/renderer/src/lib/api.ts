import { fetchEventSource } from '@microsoft/fetch-event-source'
import type { RendererConfig } from '../../../preload'
import type { Health, ImportPayload, LabelKind, Report, SeriesDetail, StoredMessage } from './types'

let cfg: RendererConfig | null = null

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: string
  ) {
    super(`${status}: ${body}`)
  }
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
  const { apiBase, token } = config()
  const isForm = body instanceof FormData
  const r = await fetch(apiBase + path, {
    method,
    signal,
    headers: {
      'X-Sloth-Token': token,
      ...(body !== undefined && !isForm ? { 'Content-Type': 'application/json' } : {})
    },
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body)
  })
  if (!r.ok) throw new ApiError(r.status, await r.text())
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
  const { apiBase, token } = config()
  return fetchEventSource(apiBase + path, {
    method: 'POST',
    body: JSON.stringify(body ?? {}),
    signal,
    openWhenHidden: true,
    headers: { 'X-Sloth-Token': token, 'Content-Type': 'application/json' },
    onopen: async (r) => {
      // 409 busy, 410 file gone, 422 bad mapping…: surface the engine's own sentence.
      if (!r.ok) throw new ApiError(r.status, await r.text())
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
