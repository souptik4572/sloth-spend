import { lazy, Suspense, useEffect, useState } from 'react'
import { Spinner } from '@renderer/components/ui/Spinner'
import { slots } from '@renderer/lib/platform'
import { toast } from '@renderer/lib/toast'
import { AccountMenu } from '@web/components/AccountMenu'
import { useLocation } from '@web/lib/router'

// The desktop renderer, unchanged: Boot, Audit, Ask Sloth, Reminders, Settings (WEB-IMPL W-D9). Loaded only
// once someone is signed in, so the sign-in screens stay small.
const RendererApp = lazy(() => import('@renderer/App'))

slots.account = AccountMenu

/** Signed in: the workspace, with the account menu in its top bar (Web artboard 15). */
export function Workspace(): React.JSX.Element {
  const { state } = useLocation()
  const [notice] = useState(typeof state.notice === 'string' ? state.notice : null)

  useEffect(() => {
    document.title = 'SlothSpend'
    if (notice) toast(notice) // e.g. "Password saved. Your other devices were logged out."
  }, [notice])

  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-bg text-muted">
          <Spinner size={28} label="Opening your workspace" />
        </div>
      }
    >
      <RendererApp />
    </Suspense>
  )
}
