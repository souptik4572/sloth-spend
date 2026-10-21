import { useMemo, useState } from 'react'
import { Check, CircleAlert, FileText, Pencil } from 'lucide-react'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { Field, Select } from '../ui/Field'
import { cancelMapping, confirmMapping } from '../../lib/audit'
import { cn } from '../../lib/cn'
import type { ColumnRole, Currency, ImportPayload } from '../../lib/types'

const ROLE_LABELS: Record<ColumnRole, string> = {
  date: 'Date',
  description: 'Description',
  amount: 'Amount',
  debit: 'Debit',
  credit: 'Credit',
  type: 'Type (DR/CR)',
  ignore: 'Ignore'
}
const MONEY: ColumnRole[] = ['amount', 'debit', 'credit']
const CURRENCIES: Array<[Currency, string]> = [
  ['USD', 'USD — $'],
  ['INR', 'INR — ₹'],
  ['EUR', 'EUR — €'],
  ['GBP', 'GBP — £']
]

type Requirement = 'found' | 'set' | 'missing'

/** D-Mapper: ask only what the file didn't say, and remember the answer for next time. */
export function ColumnMapper({ pending }: { pending: ImportPayload }): React.JSX.Element {
  const columns = useMemo(() => pending.columns ?? [], [pending.columns])
  const detected = useMemo(() => columns.map((c) => c.role), [columns])
  const [roles, setRoles] = useState<ColumnRole[]>(detected)
  const [currency, setCurrency] = useState<Currency>(pending.currency ?? 'USD')
  const [dayfirst, setDayfirst] = useState(pending.dayfirst ?? false)
  const [debitsPositive, setDebitsPositive] = useState(pending.debits_positive ?? true)
  const [running, setRunning] = useState(false)

  const has = (r: ColumnRole): boolean => roles.includes(r)
  const wasFound = (r: ColumnRole): boolean => detected.includes(r)
  const status = (ok: boolean, found: boolean): Requirement =>
    !ok ? 'missing' : found ? 'found' : 'set'
  const requirements: Array<[string, Requirement]> = [
    [
      'Date',
      status(has('date'), wasFound('date') && roles.indexOf('date') === detected.indexOf('date'))
    ],
    [
      'Description',
      status(
        has('description'),
        wasFound('description') && roles.indexOf('description') === detected.indexOf('description')
      )
    ],
    [
      'Amount, or Debit + Credit',
      status(
        has('amount') || has('debit'),
        MONEY.every((r) => roles.indexOf(r) === detected.indexOf(r)) &&
          (wasFound('amount') || wasFound('debit'))
      )
    ]
  ]
  const duplicates = roles.filter((r, i) => r !== 'ignore' && roles.indexOf(r) !== i)
  const ready = requirements.every(([, s]) => s !== 'missing') && duplicates.length === 0
  const singleAmount = has('amount') && !has('debit') && !has('credit') && !has('type')

  const intro = (pending.missing ?? []).includes('amount')
    ? 'We found the dates and descriptions, but not which column holds the money. Pick it below — we’ll remember this layout next time.'
    : pending.sign_ambiguous
      ? 'Most amounts in this file have no minus sign, so tell us how money going out is written. We’ll remember this layout next time.'
      : 'Check which column is which below — we’ll remember this layout next time.'

  const setRole = (index: number, role: ColumnRole): void =>
    setRoles((rs) => rs.map((r, i) => (i === index ? role : r)))

  const run = (): void => {
    const mapping: Record<string, number> = {}
    roles.forEach((r, i) => {
      if (r !== 'ignore') mapping[r] = i
    })
    setRunning(true)
    void confirmMapping(pending, {
      mapping,
      currency,
      dayfirst,
      debits_positive: singleAmount ? debitsPositive : null
    })
  }

  const preamble = pending.header_row ?? 0
  return (
    <Card as="section" radius="section" aria-labelledby="map-h" className="flex flex-col gap-6 p-8">
      <div className="flex flex-wrap items-start gap-4">
        <div className="min-w-0 flex-[1_1_360px]">
          <h1 id="map-h" className="m-0 text-h2">
            Help SlothSpend read this file
          </h1>
          <p className="mt-2 mb-0 text-base text-text-2">{intro}</p>
        </div>
        <div className="flex items-center gap-2.5 rounded-tile bg-raised px-3.5 py-2.5">
          <FileText aria-hidden size={18} />
          <div>
            <div className="text-sm font-medium">{pending.file_name}</div>
            <div className="text-xs text-muted">
              Header on row {preamble + 1}
              {preamble > 0 && ` · ${preamble} preamble line${preamble === 1 ? '' : 's'} skipped`}
            </div>
          </div>
        </div>
      </div>

      <ul aria-label="Required columns" className="m-0 flex list-none flex-wrap gap-2 p-0">
        {requirements.map(([label, s]) => (
          <li
            key={label}
            className={cn(
              'inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-sm font-medium',
              s === 'found' && 'bg-raised',
              s === 'set' && 'bg-accent text-on-accent',
              s === 'missing' && 'border border-dashed border-ink'
            )}
          >
            {s === 'found' && (
              <Check aria-hidden size={14} strokeWidth={2.6} className="text-success" />
            )}
            {s === 'set' && <Pencil aria-hidden size={14} />}
            {s === 'missing' && <CircleAlert aria-hidden size={14} />}
            {label} · {s === 'found' ? 'found' : s === 'set' ? 'set by you' : 'choose a column'}
          </li>
        ))}
      </ul>

      <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4">
        <Field label="Currency">
          {(id) => (
            <Select
              id={id}
              value={currency}
              onChange={(e) => setCurrency(e.target.value as Currency)}
            >
              {CURRENCIES.map(([code, label]) => (
                <option key={code} value={code}>
                  {label}
                  {pending.currency_detected && code === pending.currency ? ' (detected)' : ''}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Date order">
          {(id) => (
            <Select
              id={id}
              value={dayfirst ? 'day' : 'month'}
              onChange={(e) => setDayfirst(e.target.value === 'day')}
            >
              <option value="day">Day first · 20/10</option>
              <option value="month">Month first · 10/20</option>
            </Select>
          )}
        </Field>
        <label
          className={cn(
            'flex min-h-11 cursor-pointer items-center gap-3 self-end',
            !singleAmount && 'cursor-not-allowed opacity-50'
          )}
        >
          <input
            type="checkbox"
            checked={debitsPositive}
            disabled={!singleAmount}
            onChange={(e) => setDebitsPositive(e.target.checked)}
            className="size-5 accent-[var(--ink)]"
          />
          <span>
            <span className="block text-sm font-medium">Debits are positive</span>
            <span className="block text-xs text-muted">
              {singleAmount
                ? 'Money out shows without a minus sign'
                : 'Only for a single Amount column'}
            </span>
          </span>
        </label>
      </div>

      <div className="flex flex-col gap-2">
        <h2 className="m-0 text-sm font-bold">
          Preview · first {pending.preview?.length ?? 0} rows
        </h2>
        <div className="overflow-x-auto rounded-tile bg-raised">
          <table className="w-full min-w-[860px] border-collapse text-sm tabular-nums">
            <thead>
              <tr className="text-left align-top">
                {columns.map((c, i) => {
                  const money = MONEY.includes(roles[i])
                  return (
                    <th
                      key={c.index}
                      scope="col"
                      className={cn(
                        'border-b border-line px-3 pt-3.5 pb-3 font-medium',
                        money && 'bg-accent-tint'
                      )}
                    >
                      <label
                        htmlFor={`map-col-${i}`}
                        className="block text-xs font-medium text-muted"
                      >
                        {c.name}
                      </label>
                      <select
                        id={`map-col-${i}`}
                        value={roles[i]}
                        onChange={(e) => setRole(i, e.target.value as ColumnRole)}
                        className={cn(
                          'mt-1.5 h-9 cursor-pointer rounded-full bg-raised px-2.5 text-sm text-ink',
                          money ? 'border-2 border-ink font-medium' : 'border border-line-strong',
                          duplicates.includes(roles[i]) && 'border-2 border-dashed'
                        )}
                      >
                        {(Object.keys(ROLE_LABELS) as ColumnRole[]).map((r) => (
                          <option key={r} value={r}>
                            {ROLE_LABELS[r]}
                          </option>
                        ))}
                      </select>
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {(pending.preview ?? []).map((row, r) => (
                <tr key={r}>
                  {row.map((cell, i) => (
                    <td
                      key={i}
                      className={cn(
                        'border-b border-line px-3 py-2.5',
                        MONEY.includes(roles[i]) && 'bg-accent-wash text-right',
                        roles[i] === 'ignore' && 'text-muted'
                      )}
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {duplicates.length > 0 && (
          <p role="alert" className="m-0 text-sm font-medium">
            Each role can only be used once — check{' '}
            {duplicates.map((d) => ROLE_LABELS[d]).join(', ')}.
          </p>
        )}
        <p className="m-0 text-xs leading-[1.65] text-muted">
          Rows with dates we can’t read are skipped and counted. Only money going out is audited;
          money coming in is kept for Ask Sloth.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button variant="solid" size="lg" disabled={!ready || running} onClick={run}>
          Run audit
        </Button>
        <Button variant="ghost" onClick={() => void cancelMapping(pending)} disabled={running}>
          Cancel
        </Button>
      </div>
    </Card>
  )
}
