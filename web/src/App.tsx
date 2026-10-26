import { useEffect } from 'react'
import { WifiOff } from 'lucide-react'
import { Button } from '@renderer/components/ui/Button'
import { Spinner } from '@renderer/components/ui/Spinner'
import { AuthHeader } from '@web/components/AuthHeader'
import { CardLayout, Heading, IconBadge } from '@web/components/Layouts'
import { SIGNED_OUT_EVENT } from '@renderer/lib/api'
import { Redirect, useLocation } from '@web/lib/router'
import { leave, useSession } from '@web/lib/session'
import { CheckEmail } from '@web/screens/CheckEmail'
import { Forgot } from '@web/screens/Forgot'
import { LinkLanding } from '@web/screens/LinkLanding'
import { Login } from '@web/screens/Login'
import { Reset } from '@web/screens/Reset'
import { Signup } from '@web/screens/Signup'
import { Workspace } from '@web/screens/Workspace'

// Screens for people who aren't signed in; a signed-in visit goes to the workspace instead.
const SIGNED_OUT: Record<string, () => React.JSX.Element> = {
  '/login': Login,
  '/signup': Signup,
  '/forgot': Forgot,
  '/check-email': CheckEmail
}

// Email links work either way: they sign in (or switch to) the account they were sent for.
const FROM_EMAIL: Record<string, () => React.JSX.Element> = {
  '/verify/confirm': () => <LinkLanding kind="verify" />,
  '/login/link': () => <LinkLanding kind="link" />,
  '/reset': Reset
}

export default function App(): React.JSX.Element {
  const { path } = useLocation()
  const status = useSession((s) => s.status)

  useEffect(() => {
    void useSession.getState().load()
  }, [])

  // Any API call answered 401 (the session expired, or this account logged out everywhere): back to Log in.
  useEffect(() => {
    const signedOut = (): void => leave('You were logged out. Log in again to carry on.')
    window.addEventListener(SIGNED_OUT_EVENT, signedOut)
    return () => window.removeEventListener(SIGNED_OUT_EVENT, signedOut)
  }, [])

  const FromEmail = FROM_EMAIL[path]
  if (FromEmail) return <FromEmail />
  if (status === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg text-muted" role="status">
        <Spinner size={28} label="Loading SlothSpend" />
      </div>
    )
  }
  if (status === 'offline') return <Offline />
  if (status === 'signed-in') return path === '/' ? <Workspace /> : <Redirect to="/" />
  const Screen = SIGNED_OUT[path]
  return Screen ? <Screen /> : <Redirect to="/login" />
}

function Offline(): React.JSX.Element {
  return (
    <div className="flex min-h-screen flex-col bg-bg text-ink">
      <AuthHeader />
      <CardLayout labelledBy="off-h" centered>
        <IconBadge icon={WifiOff} large />
        <Heading id="off-h" title="Can’t reach SlothSpend.">
          Check your connection. Your data is safe on the server; nothing was lost.
        </Heading>
        <Button
          variant="solid"
          size="lg"
          className="w-full"
          onClick={() => void useSession.getState().load()}
        >
          Try again
        </Button>
      </CardLayout>
    </div>
  )
}
