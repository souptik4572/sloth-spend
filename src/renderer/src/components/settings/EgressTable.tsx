import { Chip, type ChipVariant } from '../ui/Chip'
import { useApp } from '../../store'

type Where = 'local' | 'once' | 'optin' | 'network'

const WHERE: Record<Where, [string, ChipVariant]> = {
  local: ['This computer', 'success'],
  once: ['Internet · one time', 'tint'],
  optin: ['Internet · opt-in', 'outline'],
  network: ['Your network', 'outline']
}

interface Row {
  data: string
  where: Where
  dest: string
  when: string
  on: string
}

/** Settings › Privacy: where each kind of data goes (spec §3.3, IMPL M8.2). */
export function EgressTable(): React.JSX.Element {
  // OLLAMA_HOST can point at another machine; then Gemma's inputs leave this computer and the table says so.
  const remoteOllama = useApp((s) => s.health?.llm.loopback === false)
  const gemma: Pick<Row, 'where' | 'dest'> = remoteOllama
    ? { where: 'network', dest: 'Ollama on another computer (OLLAMA_HOST)' }
    : { where: 'local', dest: 'Ollama on 127.0.0.1' }
  const rows: Row[] = [
    {
      data: 'Transactions, merchants, amounts, chats, reminders',
      where: 'local',
      dest: 'Local database in the app-data folder',
      when: 'Always',
      on: '—'
    },
    { data: 'Merchant descriptions → Gemma', ...gemma, when: 'Import', on: 'On' },
    {
      data: 'Reminder and email facts → Gemma',
      ...gemma,
      when: 'A reminder fires or you ask for a draft',
      on: 'On'
    },
    {
      data: 'TabPFN inputs',
      where: 'local',
      dest: 'Local PyTorch',
      when: 'Import and chat',
      on: 'On'
    },
    {
      data: 'TabPFN v2 weights',
      where: 'once',
      dest: 'Hugging Face',
      when: 'First run',
      on: 'Automatic'
    },
    {
      data: 'TabPFN-3.5 weights',
      where: 'once',
      dest: 'Prior Labs (license check) + Hugging Face',
      when: 'Only after you add a key',
      on: 'Off'
    },
    {
      data: 'Gemma weights',
      where: 'once',
      dest: 'Ollama registry',
      when: 'First run',
      on: 'You start it'
    },
    {
      data: 'Span timings, token counts, tool names — no prompt or answer text',
      where: 'optin',
      dest: 'Sentry',
      when: 'Only if traces are on',
      on: 'Off'
    }
  ]
  const cell = 'border-b border-line px-3 py-2.5 align-top'
  return (
    <div className="flex flex-col gap-3">
      <h4 className="m-0 text-base font-bold">Where your data goes</h4>
      <div className="overflow-x-auto rounded-tile bg-card">
        <table className="w-full min-w-[620px] border-collapse text-sm leading-[1.45]">
          <thead>
            <tr className="text-left">
              {['Data', 'Goes to', 'When', 'Default'].map((h, i) => (
                <th
                  key={h}
                  scope="col"
                  className={`border-b border-line px-3 pt-3 pb-2.5 text-xs font-medium text-muted ${i === 0 ? 'pl-4' : ''} ${i === 3 ? 'pr-4' : ''}`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const [label, variant] = WHERE[r.where]
              const last = i === rows.length - 1
              const c = last ? cell.replace('border-b border-line ', '') : cell
              return (
                <tr key={r.data}>
                  <td className={`${c} pl-4`}>{r.data}</td>
                  <td className={c}>
                    <Chip size={22} variant={variant} className="whitespace-nowrap">
                      {label}
                    </Chip>
                    <br />
                    {r.dest}
                  </td>
                  <td className={c}>{r.when}</td>
                  <td className={`${c} pr-4`}>{r.on}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="m-0 text-sm text-text-2">
        After the one-time model downloads, SlothSpend makes no network calls at all unless traces
        are on.
      </p>
    </div>
  )
}
