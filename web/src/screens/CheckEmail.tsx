import { useState } from 'react'
import { Check, MailCheck, RefreshCw } from 'lucide-react'
import { Button } from '@renderer/components/ui/Button'
import { Spinner } from '@renderer/components/ui/Spinner'
import { AuthHeader } from '@web/components/AuthHeader'
import { CardLayout, Heading, IconBadge } from '@web/components/Layouts'
import { usePage } from '@web/components/usePage'
import { api, errorText } from '@web/lib/api'
import { Link, useLocation } from '@web/lib/router'

/**
 * Check your inbox (Web artboard 11), after signing up (`kind: verify`) or "Email me a sign-in link"
 * (`kind: link`). The address comes from the previous screen; after a reload it's gone, so Resend hides.
 */
export function CheckEmail(): React.JSX.Element {
  usePage('Check your inbox', 've-h')
  const { state } = useLocation()
  const email = typeof state.email === 'string' ? state.email : ''
  const kind = state.kind === 'link' ? 'link' : 'verify'
  const [status, setStatus] = useState<'idle' | 'sending' | 'sent' | string>('idle')

  const resend = async (): Promise<void> => {
    setStatus('sending')
    try {
      if (kind === 'link')
        await api('POST', '/auth/link', { email, remember: state.remember !== false })
      else await api('POST', '/auth/verify/resend', { email })
      setStatus('sent')
    } catch (err) {
      setStatus(errorText(err))
    }
  }

  const who = email ? <strong className="text-ink">{email}</strong> : 'your email'
  return (
    <div className="flex min-h-screen flex-col bg-bg text-ink">
      <AuthHeader />
      <CardLayout labelledBy="ve-h" centered>
        <IconBadge icon={MailCheck} tone="accent" large />
        <Heading id="ve-h" title="Check your inbox.">
          {kind === 'link' ? (
            <>
              We sent a sign-in link to {who}. Open it on this device to log in — it works for 15
              minutes.
            </>
          ) : (
            <>We sent a link to {who}. Open it on this device to finish setting up your account.</>
          )}
        </Heading>

        <div className="flex w-full flex-col gap-2.5">
          {email && (
            <Button
              variant="outline"
              size="lg"
              icon={status === 'sending' ? undefined : RefreshCw}
              className="w-full"
              onClick={() => void resend()}
              disabled={status === 'sending'}
            >
              {status === 'sending' ? <Spinner size={18} /> : null}
              Resend link
            </Button>
          )}
          {status === 'sent' && (
            <p
              role="status"
              className="m-0 flex items-center justify-center gap-1.5 text-sm font-medium text-success"
            >
              <Check aria-hidden size={16} strokeWidth={2.4} />
              Sent again. It can take a minute to arrive.
            </p>
          )}
          {status !== 'idle' && status !== 'sending' && status !== 'sent' && (
            <p role="alert" className="m-0 text-sm font-medium">
              {status}
            </p>
          )}
          <Link
            to={kind === 'link' ? '/login' : '/signup'}
            state={kind === 'link' ? { email } : {}}
            className="flex h-11 items-center justify-center rounded-full text-sm font-medium text-ink no-underline hover:bg-ink/5"
          >
            Use a different email
          </Link>
        </div>

        <p className="m-0 text-small text-muted">
          Can’t find it? Check your spam or promotions folder.
        </p>
      </CardLayout>
    </div>
  )
}
