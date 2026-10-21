import { contextBridge, ipcRenderer } from 'electron'

export interface RendererConfig {
  apiBase: string
  token: string
  version: string
  platform: string
}

// The whole renderer ⇄ main surface. M4 adds the Prior Labs key, M8 telemetry (IMPL M1.6).
const api = {
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
