import { contextBridge } from 'electron'

// M0: an empty bridge. M1 adds config, shell, engine and secrets calls (IMPL §6 M1.6).
const api = {}

contextBridge.exposeInMainWorld('sloth', api)

export type SlothBridge = typeof api
