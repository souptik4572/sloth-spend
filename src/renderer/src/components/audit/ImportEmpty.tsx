import { useState, type DragEvent } from 'react'
import { FileText, Lock, Upload } from 'lucide-react'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { DemoDataMenu } from './DemoDataMenu'
import { FilePicker } from './FilePicker'
import { importFile, loadSample } from '../../lib/audit'
import { cn } from '../../lib/cn'
import { statementPrivacy } from '../../lib/copy'

const STEPS = [
  ['Audit', 'Find recurring charges, price rises and double charges.'],
  ['Ask', 'Ask Sloth about any charge, in plain language.'],
  ['Remind', 'Get a nudge before a renewal. You decide what to do.'],
  ['Verify', 'Import your next statement to confirm a charge stopped.']
]

/** D-Import: the pink drop zone, "How it works" and the never-cancels line. */
export function ImportEmpty(): React.JSX.Element {
  const [over, setOver] = useState(false)

  const onDrop = (e: DragEvent): void => {
    e.preventDefault()
    setOver(false)
    const file = e.dataTransfer.files[0]
    if (file) void importFile(file)
  }

  return (
    <>
      <Card
        as="section"
        tone="accent"
        radius="hero"
        aria-labelledby="drop-h"
        className={cn(
          'p-4 transition-shadow duration-300',
          over && 'shadow-[0_0_0_3px_var(--accent-edge)]'
        )}
        onDragOver={(e: DragEvent) => {
          e.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
      >
        <div className="flex flex-col items-start gap-6 rounded-[36px] border-2 border-dashed border-ink px-10 py-12">
          <span className="flex size-16 items-center justify-center rounded-full bg-raised">
            <Upload aria-hidden size={28} strokeWidth={2} />
          </span>
          <div>
            <h1 id="drop-h" className="m-0 text-display-xl">
              {over ? 'Let go to read it.' : 'Drop a bank statement here.'}
            </h1>
            <p className="mt-4 mb-0 max-w-[44ch] text-lead">
              A 12-month CSV export from a US or Indian bank. SlothSpend finds recurring charges,
              price rises and double charges, and forecasts next month.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <FilePicker variant="solid" size="lg" icon={FileText}>
              Choose CSV file
            </FilePicker>
            <Button variant="outline" size="lg" onClick={() => void loadSample('main')}>
              Load sample statement
            </Button>
            <DemoDataMenu />
          </div>
          <p className="m-0 flex items-center gap-2 text-sm font-medium">
            <Lock aria-hidden size={16} strokeWidth={2.2} />
            {statementPrivacy()}
          </p>
        </div>
      </Card>

      <section aria-labelledby="how-h" className="flex flex-col gap-4">
        <h2 id="how-h" className="m-0 text-h3">
          How it works
        </h2>
        <ol className="m-0 grid list-none grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-4 p-0">
          {STEPS.map(([title, text], i) => (
            <li key={title} className="flex flex-col gap-2.5 rounded-card bg-panel p-5">
              <span aria-hidden className="font-display text-[43.2px] leading-[0.95] font-bold">
                {i + 1}
              </span>
              <h3 className="m-0 text-base font-bold">{title}</h3>
              <p className="m-0 text-sm text-text-2">{text}</p>
            </li>
          ))}
        </ol>
        <p className="m-0 text-sm text-muted">
          SlothSpend never cancels anything and never contacts anyone. It explains, reminds and
          drafts — you do the cancelling.
        </p>
      </section>
    </>
  )
}
