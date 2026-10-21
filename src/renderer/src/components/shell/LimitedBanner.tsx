import { Info } from 'lucide-react'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { fullyReady, useApp } from '../../store'

/** Shown while Gemma or TabPFN isn't ready (spec §6.1: degraded mode with a banner, never a blank window). */
export function LimitedBanner(): React.JSX.Element | null {
  const { engine, health, setScreen } = useApp()
  if (engine !== 'ok' || fullyReady(health)) return null
  return (
    <Card radius="tile" className="flex flex-wrap items-center gap-3 py-3 pr-3 pl-4" role="status">
      <Info aria-hidden size={20} className="shrink-0" />
      <p className="m-0 min-w-0 flex-[1_1_300px] text-sm">
        <strong className="font-medium">Limited mode:</strong> rule-based merchant names and a
        heuristic scorer. Every result is labelled.
      </p>
      <Button variant="soft" onClick={() => setScreen('boot')}>
        Finish setup
      </Button>
    </Card>
  )
}
