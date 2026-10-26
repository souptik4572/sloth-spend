// SlothSpend Web's `window.sloth` (WEB-IMPL §2.4): the browser's answer to everything the desktop renderer asks
// Electron's main process. Imported first in main.tsx, before any renderer module reads it.
import type { SlothBridge } from '../../src/preload'

declare const __SLOTH_VERSION__: string

const web: SlothBridge = {
  kind: 'web',
  // TabPFN-3.5 is the operator's choice on the web (TABPFN_TOKEN on the server); there's no key to manage here.
  priorKey: {
    present: async () => false,
    save: async () => ({ ok: false, error: 'Managed by SlothSpend.' }),
    remove: async () => ({ ok: true })
  },
  // Performance traces are a per-account setting on the web (W7); until then they're off.
  telemetry: {
    get: async () => false,
    set: async () => false
  },
  getConfig: async () => ({
    apiBase: '/api',
    token: '',
    version: __SLOTH_VERSION__,
    platform: 'web'
  }),
  openExternal: async (url) => {
    window.open(url, '_blank', 'noopener,noreferrer')
  },
  // The server isn't ours to restart or read logs from; a lost connection shows the connection banner.
  restartEngine: async () => undefined,
  engineLogs: async () => [],
  onEngineExit: () => () => undefined,
  focusWindow: async () => window.focus(),
  setBackground: async (hex) => {
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', hex)
  }
}

window.sloth = web
