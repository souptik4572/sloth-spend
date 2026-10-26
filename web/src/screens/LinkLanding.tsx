import { useEffect, useState } from 'react'
import { TriangleAlert } from 'lucide-react'
import { Spinner } from '@renderer/components/ui/Spinner'
import { AuthHeader } from '@web/components/AuthHeader'
import { CardLayout, Heading, IconBadge } from '@web/components/Layouts'
import { usePage } from '@web/components/usePage'
import { api, errorText, type User } from '@web/lib/api'
import { Link, navigate, takeToken } from '@web/lib/router'
import { once, useSession } from '@web/lib/session'

const KINDS = {
  verify: {
    path: '/auth/verify',
    working: 'Confirming your email…',
    retry: 'Log in',
    to: '/login'
  },
  link: {
    path: '/auth/link/consume',
    working: 'Logging you in…',
    retry: 'Ask for a new link',
    to: '/login'
  }
} as const

/**
 * Where the email links land: /verify/confirm (confirm the email) and /login/link (passwordless sign-in).
 * Each uses its one-time token and signs in on this device; an expired or used link says so plainly.
 */
export function LinkLanding({ kind }: { kind: keyof typeof KINDS }): React.JSX.Element {
  const k = KINDS[kind]
  const [token] = useState(takeToken)
  const [failed, setFailed] = useState<string | null>(
    token ? null : 'This page needs the link from your email.'
  )
  usePage(failed ? 'Link expired' : k.working.replace('…', ''), 'ln-h')

  useEffect(() => {
    if (!token) return
    once(`${kind}:${token}`, () => api<{ user: User }>('POST', k.path, { token }))
      .then(({ user }) => {
        useSession.getState().signedIn(user)
        navigate('/', { replace: true })
      })
      .catch((err) => setFailed(errorText(err)))
  }, [kind, k.path, token])

  return (
    <div className="flex min-h-screen flex-col bg-bg text-ink">
      <AuthHeader />
      <CardLayout labelledBy="ln-h" centered>
        {failed ? (
          <>
            <IconBadge icon={TriangleAlert} large />
            <Heading id="ln-h" title="That link didn’t work.">
              {failed}
            </Heading>
            <Link
              to={k.to}
              className="flex h-[52px] w-full items-center justify-center rounded-full bg-solid text-base font-medium !text-on-solid no-underline hover:opacity-90"
            >
              {k.retry}
            </Link>
          </>
        ) : (
          <div role="status" className="flex flex-col items-center gap-4">
            <Spinner size={32} />
            <h1 id="ln-h" tabIndex={-1} className="m-0 text-h3 outline-none">
              {k.working}
            </h1>
          </div>
        )}
      </CardLayout>
    </div>
  )
}
