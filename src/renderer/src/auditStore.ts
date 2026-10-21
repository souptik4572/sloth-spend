import { create } from 'zustand'
import type { ImportPayload, Report, StageEvent, StageId } from './lib/types'

/** The Audit tab is a state machine (IMPL M5): empty → mapping → running → report, plus error. */
export type AuditPhase = 'loading' | 'empty' | 'mapping' | 'running' | 'report' | 'error'

export interface RunState {
  file: string
  rows: number | null
  startedAt: number
  stages: Partial<Record<StageId, StageEvent>>
}

export type DrawerSection = 'top' | 'how-to-cancel' | 'negotiate'

interface AuditState {
  phase: AuditPhase
  report: Report | null
  pending: ImportPayload | null
  run: RunState | null
  error: { message: string; stage?: string } | null
  drawer: { id: number; section: DrawerSection } | null
  /** Bumped when the drawer should re-fetch its detail (after a label or rename). */
  drawerVersion: number
  setPhase: (phase: AuditPhase) => void
  showReport: (report: Report) => void
  showEmpty: () => void
  startMapping: (pending: ImportPayload) => void
  startRun: (file: string, rows: number | null) => void
  stageEvent: (ev: StageEvent) => void
  fail: (message: string, stage?: string) => void
  openDrawer: (id: number, section?: DrawerSection) => void
  closeDrawer: () => void
  refreshDrawer: () => void
}

export const useAudit = create<AuditState>((set) => ({
  phase: 'loading',
  report: null,
  pending: null,
  run: null,
  error: null,
  drawer: null,
  drawerVersion: 0,
  setPhase: (phase) => set({ phase }),
  showReport: (report) => set({ phase: 'report', report, pending: null, run: null, error: null }),
  showEmpty: () => set({ phase: 'empty', report: null, pending: null, run: null, error: null }),
  startMapping: (pending) => set({ phase: 'mapping', pending, error: null }),
  startRun: (file, rows) =>
    set({ phase: 'running', run: { file, rows, startedAt: Date.now(), stages: {} }, error: null }),
  stageEvent: (ev) =>
    set((s) => {
      if (!s.run) return s
      const rows = ev.stage === 'parse' && ev.note ? (parseRows(ev.note) ?? s.run.rows) : s.run.rows
      return {
        run: {
          ...s.run,
          rows,
          stages: { ...s.run.stages, [ev.stage]: { ...s.run.stages[ev.stage], ...ev } }
        }
      }
    }),
  fail: (message, stage) => set({ phase: 'error', error: { message, stage }, run: null }),
  openDrawer: (id, section = 'top') => set({ drawer: { id, section } }),
  closeDrawer: () => set({ drawer: null }),
  refreshDrawer: () => set((s) => ({ drawerVersion: s.drawerVersion + 1 }))
}))

/** "410 rows · 2 skipped (unreadable dates)" → 410. */
function parseRows(note: string): number | null {
  const m = /^(\d+) rows/.exec(note)
  return m ? Number(m[1]) : null
}
