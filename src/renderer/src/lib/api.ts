import { fetchEventSource } from '@microsoft/fetch-event-source'
import type { RendererConfig } from '../../../preload'
import type { Health } from './types'

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
    onmessage: (ev) => on[ev.event]?.(ev.data ? JSON.parse(ev.data) : null),
    onerror: (err) => {
      throw err
    }
  })
}

export const getHealth = (signal?: AbortSignal): Promise<Health> =>
  req<Health>('GET', '/health', undefined, signal)
