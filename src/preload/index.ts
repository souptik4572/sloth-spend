import { contextBridge, ipcRenderer } from 'electron'

export interface RendererConfig {
  apiBase: string
  token: string
  version: string
  platform: string
}

export type KeyResult = { ok: true } | { ok: false; error: string }

// The whole renderer ⇄ main surface (IMPL M1.6). M8 adds telemetry.
const api = {
  /** Prior Labs key for the optional TabPFN-3.5 upgrade. Write-only: the renderer can't read it back. */
  priorKey: {
    present: (): Promise<boolean> => ipcRenderer.invoke('secrets:has'),
    save: (key: string): Promise<KeyResult> => ipcRenderer.invoke('secrets:set', key),
    remove: (): Promise<KeyResult> => ipcRenderer.invoke('secrets:clear')
  },
  getConfig: (): Promise<RendererConfig> => ipcRenderer.invoke('config:get'),
  openExternal: (url: string): Promise<void> => ipcRenderer.invoke('shell:open', url),
  restartEngine: (): Promise<void> => ipcRenderer.invoke('engine:restart'),
  engineLogs: (): Promise<string[]> => ipcRenderer.invoke('engine:logs'),
  onEngineExit: (cb: (code: number | null) => void): (() => void) => {
    const handler = (_: unknown, code: number | null): void => cb(code)
    ipcRenderer.on('engine:exit', handler)
    return () => {
      ipcRenderer.off('engine:exit', handler)
    }
  },
  focusWindow: (): Promise<void> => ipcRenderer.invoke('window:focus'),
  setBackground: (hex: string): Promise<void> => ipcRenderer.invoke('window:bg', hex)
}

contextBridge.exposeInMainWorld('sloth', api)

export type SlothBridge = typeof api
