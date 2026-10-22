// Settings (IMPL M8.1–M8.3): engine settings saved 400 ms after a change, and Delete all local data.
import { useCallback, useEffect, useRef, useState } from 'react'
import { useAudit } from '../auditStore'
import { useChat } from '../chatStore'
import { useReminders } from '../remindersStore'
import { deleteData, errorMessage, getSettings, putSettings } from './api'
import { resetNotifications } from './notify'
import { toast } from './toast'
import type { EngineSettings } from './types'
import { refreshHealth } from './useHealthPolling'

export type SettingsSection = 'models' | 'statements' | 'reminders'
export type SaveState = 'saving' | 'saved' | 'error'

const DEBOUNCE_MS = 400

/** The engine's settings while the modal is open; `update` saves after a short pause, per section. */
export function useEngineSettings(open: boolean): {
  settings: EngineSettings | null
  status: Partial<Record<SettingsSection, SaveState>>
  update: (patch: Partial<EngineSettings>, section: SettingsSection) => void
} {
  const [settings, setSettings] = useState<EngineSettings | null>(null)
  const [status, setStatus] = useState<Partial<Record<SettingsSection, SaveState>>>({})
  const pending = useRef<Partial<EngineSettings>>({})
  const sections = useRef(new Set<SettingsSection>())
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  const flush = useCallback(async (): Promise<void> => {
    clearTimeout(timer.current)
    const patch = pending.current
    const touched = [...sections.current]
    pending.current = {}
    sections.current.clear()
    if (!Object.keys(patch).length) return
    const mark = (state: SaveState): void =>
      setStatus((s) => ({ ...s, ...Object.fromEntries(touched.map((k) => [k, state])) }))
    try {
      const saved = await putSettings(patch)
      setSettings(saved)
      mark('saved')
      useReminders.getState().setDemoSeconds(saved.demo_compress_seconds)
      if ('chat_model' in patch) void refreshHealth() // the pills name the model now in use
    } catch (err) {
      mark('error')
      toast(errorMessage(err, 'That setting couldn’t be saved.'))
      setSettings(await getSettings().catch(() => null)) // show what the engine actually has
    }
  }, [])

  useEffect(() => {
    if (!open) return
    let live = true
    void getSettings()
      .then((s) => live && setSettings(s))
      .catch(() => undefined)
    return () => {
      live = false
      void flush() // closing the modal saves anything still waiting
    }
  }, [open, flush])

  const update = useCallback(
    (patch: Partial<EngineSettings>, section: SettingsSection): void => {
      setSettings((s) => (s ? { ...s, ...patch } : s))
      pending.current = { ...pending.current, ...patch }
      sections.current.add(section)
      setStatus((s) => ({ ...s, [section]: 'saving' }))
      clearTimeout(timer.current)
      timer.current = setTimeout(() => void flush(), DEBOUNCE_MS)
    },
    [flush]
  )

  return { settings, status, update }
}

/** Settings › Delete all local data: the engine wipes its tables; every screen goes back to empty. */
export async function deleteAllData(): Promise<boolean> {
  try {
    await deleteData()
  } catch (err) {
    toast(errorMessage(err, 'The data couldn’t be deleted.'))
    return false
  }
  resetNotifications()
  useChat.getState().reset() // a fresh conversation id (sloth.cid)
  const audit = useAudit.getState()
  audit.closeDrawer()
  audit.showEmpty()
  const reminders = useReminders.getState()
  reminders.setReminders([])
  reminders.setInbox([])
  toast('Everything SlothSpend stored on this computer was deleted. Settings and models stay.')
  return true
}
