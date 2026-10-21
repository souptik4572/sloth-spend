import { useEffect } from 'react'
import { getHealth } from './api'
import { useApp } from '../store'

const LOADING = new Set(['cold', 'downloading', 'warming'])

/** Fetch /health once now ("Check again", after a download) and update the store. */
export async function refreshHealth(): Promise<void> {
  try {
    useApp.getState().healthOk(await getHealth(AbortSignal.timeout(4000)))
  } catch {
    useApp.getState().healthFailed()
  }
}

/**
 * Polls /health: every second on Boot, every 2 s while TabPFN is still downloading or warming up,
 * otherwise every 10 s in the workspace (IMPL M1.8).
 */
export function useHealthPolling(): void {
  const configured = useApp((s) => s.configured)
  const screen = useApp((s) => s.screen)
  const engine = useApp((s) => s.engine)
  const loading = useApp((s) => LOADING.has(s.health?.tabpfn.status ?? ''))

  useEffect(() => {
    if (!configured || engine === 'stopped') return // no address yet, or nothing to poll until a restart
    const every = screen === 'boot' || engine === 'starting' ? 1000 : loading ? 2000 : 10_000
    let timer: ReturnType<typeof setTimeout>
    let cancelled = false
    const ctrl = new AbortController()

    const tick = async (): Promise<void> => {
      try {
        const h = await getHealth(AbortSignal.any([ctrl.signal, AbortSignal.timeout(4000)]))
        if (!cancelled) useApp.getState().healthOk(h)
      } catch {
        if (!cancelled) useApp.getState().healthFailed()
      }
      if (!cancelled) timer = setTimeout(tick, every)
    }
    void tick()
    return () => {
      cancelled = true
      ctrl.abort()
      clearTimeout(timer)
    }
  }, [configured, screen, engine, loading])
}
