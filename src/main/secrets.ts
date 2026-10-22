import { app, safeStorage } from 'electron'
import fs from 'node:fs'
import path from 'node:path'

// Main-process preferences the engine needs at spawn time (spec §6.3, IMPL M4.12).
// The Prior Labs key is encrypted with the OS keychain (safeStorage) and never sent back to the
// renderer — it only learns whether a key is saved. Saving it upgrades TabPFN v2 → 3.5 (IMPL §2 #21).

interface Prefs {
  priorKey?: string // safeStorage-encrypted, base64
  telemetry?: boolean
}

const MAX_KEY_LENGTH = 4096

const file = (): string => path.join(app.getPath('userData'), 'prefs.json')

function read(): Prefs {
  try {
    return JSON.parse(fs.readFileSync(file(), 'utf8')) as Prefs
  } catch {
    return {}
  }
}

function write(prefs: Prefs): void {
  // Write-then-rename so a crash mid-write can't leave a half-written prefs file.
  const tmp = `${file()}.tmp`
  fs.writeFileSync(tmp, JSON.stringify(prefs), { mode: 0o600 })
  fs.renameSync(tmp, file())
}

export class KeyError extends Error {}

/** Encrypts and stores the key. Throws KeyError with a user-facing message if it can't. */
export function setPriorKey(raw: unknown): void {
  const key = typeof raw === 'string' ? raw.trim() : ''
  if (!key) throw new KeyError('Paste your Prior Labs key first.')
  if (key.length > MAX_KEY_LENGTH || /\s/.test(key)) {
    throw new KeyError(
      'That doesn’t look like a Prior Labs key. Copy it again from platform.priorlabs.ai.'
    )
  }
  if (!safeStorage.isEncryptionAvailable()) {
    throw new KeyError(
      'This computer’s keychain isn’t available, so the key can’t be stored safely.'
    )
  }
  write({ ...read(), priorKey: safeStorage.encryptString(key).toString('base64') })
}

export function hasPriorKey(): boolean {
  return Boolean(read().priorKey)
}

export function clearPriorKey(): void {
  const prefs = read()
  delete prefs.priorKey
  write(prefs)
}

/** Settings › Share performance traces (IMPL M8.1). Off unless the person turned it on. */
export function telemetryOn(): boolean {
  return read().telemetry === true
}

export function setTelemetry(on: boolean): void {
  write({ ...read(), telemetry: on })
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
