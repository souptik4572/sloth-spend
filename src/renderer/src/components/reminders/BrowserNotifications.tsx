import { useState } from 'react'
import { Bell, BellOff } from 'lucide-react'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { askForNotifications, notifyPermission } from '../../lib/notify'
import { isWeb } from '../../lib/platform'

/**
 * SlothSpend Web only: browser notifications need the person's permission (WEB-IMPL W6). Asked from a click;
 * when they're off or unsupported, say where reminders go instead. Nothing shows once they're allowed.
 */
export function BrowserNotifications(): React.JSX.Element | null {
  const [permission, setPermission] = useState(notifyPermission)
  if (!isWeb() || permission === 'granted') return null

  if (permission === 'default') {
    return (
      <Card
        radius="tile"
        className="flex flex-wrap items-center gap-3 py-3 pr-3 pl-4"
        role="region"
        aria-label="Browser notifications"
      >
        <Bell aria-hidden size={20} className="shrink-0" />
        <p className="m-0 min-w-0 flex-[1_1_300px] text-sm">
          <strong className="font-medium">Get a pop-up when a reminder is due.</strong> SlothSpend
          only notifies you about your own reminders.
        </p>
        <Button variant="solid" onClick={() => void askForNotifications().then(setPermission)}>
          Turn on notifications
        </Button>
      </Card>
    )
  }

  return (
    <p className="m-0 flex items-start gap-2.5 text-sm leading-[1.45] text-muted" role="status">
      <BellOff aria-hidden size={18} className="mt-px shrink-0" />
      {permission === 'denied'
        ? 'Browser notifications are off for SlothSpend, so reminders wait in the bell. To get pop-ups, allow notifications for this site in your browser’s settings.'
        : 'This browser can’t show notifications, so reminders wait in the bell.'}
    </p>
  )
}
