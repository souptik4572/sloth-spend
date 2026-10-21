import { useEffect } from 'react'
import { getHealth } from './api'
import { useApp } from '../store'

/** Polls /health: every second on Boot, every 10 s in the workspace (IMPL M1.8). */
export function useHealthPolling(): void {
  const configured = useApp((s) => s.configured)
  const screen = useApp((s) => s.screen)
  const engine = useApp((s) => s.engine)

  useEffect(() => {
    if (!configured || engine === 'stopped') return // no address yet, or nothing to poll until a restart
    const every = screen === 'boot' || engine === 'starting' ? 1000 : 10_000
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
  }, [configured, screen, engine])
}
