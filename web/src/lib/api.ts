// The web app's API client (WEB-IMPL §2.3): same origin, session cookie, and the CSRF header the gate requires.

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
    public body: Record<string, unknown> = {}
  ) {
    super(detail)
  }

  /** A machine-readable reason some answers carry, e.g. "unverified". */
  get code(): string | undefined {
    return typeof this.body.code === 'string' ? this.body.code : undefined
  }
}

const OFFLINE = 'Can’t reach SlothSpend right now. Check your connection, then try again.'
const FALLBACK = 'Something went wrong. Please try again.'

export async function api<T>(method: string, path: string, body?: unknown): Promise<T> {
  let r: Response
  try {
    r = await fetch(`/api${path}`, {
      method,
      credentials: 'same-origin',
      headers: {
        'X-Sloth-CSRF': '1',
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {})
      },
      body: body === undefined ? undefined : JSON.stringify(body)
    })
  } catch {
    throw new ApiError(0, OFFLINE)
  }
  const data = (await r.json().catch(() => ({}))) as Record<string, unknown>
  if (!r.ok) {
    // FastAPI's own validation errors arrive as a list; the engine's sentences as a string.
    const detail = typeof data.detail === 'string' ? data.detail : FALLBACK
    throw new ApiError(r.status, detail, data)
  }
  return data as T
}

export function errorText(err: unknown): string {
  return err instanceof ApiError ? err.detail : FALLBACK
}

export interface User {
  id: string
  email: string
  name: string
  created_at: string
}
