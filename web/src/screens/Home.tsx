import { useState } from 'react'
import { CircleCheck, LogOut } from 'lucide-react'
import { Wordmark, SlothAvatar } from '@renderer/components/brand/Logo'
import { ThemeToggle } from '@renderer/components/shell/ThemeToggle'
import { Button } from '@renderer/components/ui/Button'
import { CardLayout, Heading } from '@web/components/Layouts'
import { usePage } from '@web/components/usePage'
import { navigate, useLocation } from '@web/lib/router'
import { initials, useSession } from '@web/lib/session'

/**
 * Signed in. The workspace shell (Boot, Audit, Ask Sloth, Reminders and the account menu of artboard 15) is
 * WEB-IMPL W3; until then this confirms the session and offers Log out.
 */
export function Home(): React.JSX.Element {
  usePage('Signed in', 'home-h')
  const user = useSession((s) => s.user)
  const { state } = useLocation()
  const [notice] = useState(typeof state.notice === 'string' ? state.notice : null)
  if (!user) return <></>

  const logOut = async (): Promise<void> => {
    await useSession.getState().logOut()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg text-ink">
      <header className="box-border flex min-h-[72px] flex-wrap items-center gap-x-4 gap-y-3 px-6 py-3.5">
        <span className="mr-auto">
          <Wordmark />
        </span>
        <ThemeToggle />
        <span
          aria-hidden
          className="flex size-11 items-center justify-center rounded-full bg-accent text-sm font-bold text-on-accent"
        >
          {initials(user.name)}
        </span>
      </header>
      <CardLayout labelledBy="home-h" centered>
        <SlothAvatar size={96} />
        <Heading id="home-h" title={`You’re in, ${user.name.split(' ')[0]}.`}>
          Signed in as <strong className="text-ink">{user.email}</strong>. Your audit workspace
          opens here next.
        </Heading>
        {notice && (
          <p
            role="status"
            className="m-0 flex items-center gap-1.5 text-sm font-medium text-success"
          >
            <CircleCheck aria-hidden size={16} strokeWidth={2.4} />
            {notice}
          </p>
        )}
        <Button variant="outline-strong" icon={LogOut} onClick={() => void logOut()}>
          Log out
        </Button>
      </CardLayout>
    </div>
  )
}
