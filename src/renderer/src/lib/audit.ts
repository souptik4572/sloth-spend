// Audit actions (IMPL M5): upload → (mapper) → stream the pipeline → report; corrections; renames.
// Components call these; they keep the audit store in step with the engine.
import { useAudit } from '../auditStore'
import { toast } from './toast'
import {
  ApiError,
  discardImport,
  errorMessage,
  getReport,
  labelSeries,
  renameSeries,
  rescoreReport,
  stream,
  uploadStatement
} from './api'
import type { ImportPayload, LabelKind, Report, StageEvent } from './types'

export type SampleFile = 'main' | 'followup_cancelled' | 'followup_still_charged'

export const SAMPLE_FILES: Record<SampleFile, string> = {
  main: 'sample_bank_12m.csv',
  followup_cancelled: 'followup_cancelled.csv',
  followup_still_charged: 'followup_still_charged.csv'
}

const store = useAudit.getState

/** Back to where the user was: the report if there is one, else the drop zone. */
function settle(): void {
  const { report } = store()
  if (report) store().showReport(report)
  else store().showEmpty()
}

export async function loadReport(): Promise<void> {
  try {
    store().showReport(await getReport())
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) store().showEmpty()
    else store().fail(errorMessage(err, 'Couldn’t load the report.'))
  }
}

/** Stream an audit and land on the report (or an error card). */
async function runPipeline(
  path: string,
  body: unknown,
  file: string,
  rows: number | null
): Promise<void> {
  store().startRun({ path, body, file, rows })
  let finished = false
  try {
    await stream(path, body, {
      stage: (d) => store().stageEvent(d as StageEvent),
      done: (d) => {
        finished = true
        const { report, duplicate } = d as { report: Report; duplicate?: boolean }
        if (duplicate) toast(`${file} is already in your report.`)
        store().showReport(report)
      },
      error: (d) => {
        finished = true
        const { message, stage } = d as { message: string; stage?: string }
        store().fail(message, stage)
      }
    })
    if (!finished) store().fail('The audit stopped before it finished. Please try again.')
  } catch (err) {
    if (err instanceof ApiError && err.status === 409) {
      // Another audit (or a re-score) holds the engine: keep what's on screen.
      toast('An audit is already running.')
      settle()
      return
    }
    store().fail(errorMessage(err, 'The audit couldn’t start.'))
  }
}

/** The error card's Try again: run the same audit again. Rows already stored are not read twice. */
export async function retryLastRun(): Promise<void> {
  const last = store().lastRun
  if (last) await runPipeline(last.path, last.body, last.file, last.rows)
}

export async function importFile(file: File): Promise<void> {
  if (!/\.(csv|txt)$/i.test(file.name)) {
    toast('Choose a CSV statement export (a .csv file).')
    return
  }
  let payload: ImportPayload
  try {
    payload = await uploadStatement(file)
  } catch (err) {
    toast(errorMessage(err, 'That file couldn’t be read.'))
    return
  }
  if (payload.duplicate) {
    toast(`${payload.file_name} is already in your report.`)
    return
  }
  if (payload.needs_mapping) {
    store().startMapping(payload)
    return
  }
  await runPipeline(
    `/import/${payload.import_id}/confirm`,
    {},
    payload.file_name,
    payload.row_count ?? null
  )
}

export interface ConfirmOptions {
  mapping: Record<string, number>
  currency: string
  dayfirst: boolean
  debits_positive: boolean | null
}

export async function confirmMapping(pending: ImportPayload, opts: ConfirmOptions): Promise<void> {
  const body = { ...opts, debits_positive: opts.debits_positive ?? undefined }
  await runPipeline(
    `/import/${pending.import_id}/confirm`,
    body,
    pending.file_name,
    pending.row_count ?? null
  )
}

export async function cancelMapping(pending: ImportPayload): Promise<void> {
  try {
    await discardImport(pending.import_id)
  } catch {
    /* already gone: nothing to undo */
  }
  settle()
}

export async function loadSample(file: SampleFile): Promise<void> {
  await runPipeline('/demo/load-sample', { file }, SAMPLE_FILES[file], null)
}

export function leaveError(): void {
  settle()
}

/** Keep / Not a subscription / It's a subscription → the engine re-scores (≤ 5 s) and returns the report. */
export async function applyLabel(id: number, label: LabelKind): Promise<void> {
  try {
    const { report } = await labelSeries(id, label)
    store().showReport(report)
    store().refreshDrawer()
  } catch (err) {
    toast(errorMessage(err, 'That change couldn’t be saved.'))
  }
}

export async function applyRename(id: number, merchant: string, category: string): Promise<void> {
  try {
    const { report, series_id } = await renameSeries(id, merchant, category)
    store().showReport(report)
    if (series_id !== null && store().drawer) store().openDrawer(series_id)
    store().refreshDrawer()
    toast('Saved. The report was re-scored.')
  } catch (err) {
    toast(errorMessage(err, 'That change couldn’t be saved.'))
  }
}

export async function rescore(): Promise<void> {
  try {
    store().showReport((await rescoreReport()).report)
    toast('Re-scored with TabPFN.')
  } catch (err) {
    toast(errorMessage(err, 'Re-scoring didn’t work.'))
  }
}
