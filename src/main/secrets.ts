import { app, safeStorage } from 'electron'
import fs from 'node:fs'
import path from 'node:path'

// Main-process preferences that the engine needs at spawn time (spec §6.3).
// M1 only reads them; saving the Prior Labs key and the telemetry toggle arrives in M4/M8.

interface Prefs {
  priorKey?: string // safeStorage-encrypted, base64
  telemetry?: boolean
}

const file = (): string => path.join(app.getPath('userData'), 'prefs.json')

function read(): Prefs {
  try {
    return JSON.parse(fs.readFileSync(file(), 'utf8')) as Prefs
  } catch {
    return {}
  }
}

export function secretsEnv(): Record<string, string> {
  const p = read()
  const env: Record<string, string> = { SLOTH_TELEMETRY: p.telemetry ? '1' : '0' }
  if (p.priorKey) {
    try {
      env.TABPFN_TOKEN = safeStorage.decryptString(Buffer.from(p.priorKey, 'base64'))
    } catch {
      /* unreadable on this machine: treat as missing */
    }
  }
  return env
}
