import { create } from 'zustand'
import type { Health } from './lib/types'
import type { EngineState } from './lib/status'

export type Screen = 'boot' | 'workspace'
export type Tab = 'audit' | 'reminders'

interface AppState {
  /** True once api.init() has the engine address and token. */
  configured: boolean
  version: string
  screen: Screen
  tab: Tab
  settingsOpen: boolean
  engine: EngineState
  exitCode: number | null
  health: Health | null
  configure: (version: string) => void
  setScreen: (s: Screen) => void
  setTab: (t: Tab) => void
  setSettingsOpen: (open: boolean) => void
  healthOk: (h: Health) => void
  healthFailed: () => void
  engineExited: (code: number | null) => void
  engineRestarting: () => void
}

export const useApp = create<AppState>((set) => ({
  configured: false,
  version: '',
  screen: 'boot',
  tab: 'audit',
  settingsOpen: false,
  engine: 'starting',
  exitCode: null,
  health: null,
  configure: (version) => set({ configured: true, version }),
  setScreen: (screen) => set({ screen }),
  setTab: (tab) => set({ tab }),
  setSettingsOpen: (settingsOpen) => set({ settingsOpen }),
  healthOk: (health) => set({ health, engine: 'ok', exitCode: null }),
  // A failed poll before the first success just means "still starting"; after an exit we stay stopped.
  healthFailed: () =>
    set((s) => (s.engine === 'stopped' ? s : { engine: 'starting', health: null })),
  // The workspace stays put (IMPL M9.1): its Engine pill and a modal offer the restart.
  engineExited: (exitCode) => set({ engine: 'stopped', exitCode, health: null }),
  engineRestarting: () => set({ engine: 'starting', exitCode: null, health: null })
}))

/** True when Gemma and TabPFN are both usable — anything less is limited mode. */
export function fullyReady(h: Health | null): boolean {
  return !!h && h.ollama.status === 'ready' && h.tabpfn.status === 'ready'
}
