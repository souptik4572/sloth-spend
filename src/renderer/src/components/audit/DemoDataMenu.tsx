import { Menu } from '../ui/Menu'
import { loadSample } from '../../lib/audit'
import { useAudit } from '../../auditStore'

/** Bundled demo statements (D-Import, D-Main). Follow-ups need the 12-month sample first. */
export function DemoDataMenu({ size = 'md' }: { size?: 'md' | 'sm' }): React.JSX.Element {
  const hasReport = useAudit((s) => s.report !== null)
  return (
    <Menu
      label="Demo data"
      size={size}
      items={[
        {
          label: 'Sample statement',
          hint: '12 months of fictional charges',
          onSelect: () => void loadSample('main')
        },
        {
          label: 'Follow-up: IronTrap cancelled',
          hint: hasReport
            ? 'Oct 16 – Nov 15, no IronTrap charge'
            : 'Load the sample statement first',
          disabled: !hasReport,
          onSelect: () => void loadSample('followup_cancelled')
        },
        {
          label: 'Follow-up: IronTrap still charged',
          hint: hasReport
            ? 'Oct 16 – Nov 15, charged again on Nov 5'
            : 'Load the sample statement first',
          disabled: !hasReport,
          onSelect: () => void loadSample('followup_still_charged')
        }
      ]}
    />
  )
}
