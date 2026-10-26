import { useState, type FormEvent } from 'react'
import { ArrowLeft, KeyRound, MailCheck } from 'lucide-react'
import { Button } from '@renderer/components/ui/Button'
import { Spinner } from '@renderer/components/ui/Spinner'
import { Alert } from '@web/components/Alert'
import { AuthHeader } from '@web/components/AuthHeader'
import { CardLayout, Heading, IconBadge } from '@web/components/Layouts'
import { TextField } from '@web/components/TextField'
import { usePage } from '@web/components/usePage'
import { api, errorText } from '@web/lib/api'
import { isEmail } from '@web/lib/password'
import { Link, useLocation } from '@web/lib/router'

/** Forgot password (Web artboard 13). The answer is the same whether or not the email has an account. */
export function Forgot(): React.JSX.Element {
  const { state } = useLocation()
  const [email, setEmail] = useState(typeof state.email === 'string' ? state.email : '')
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  usePage(sent ? 'Check your inbox' : 'Forgot your password?', sent ? 'fp-h2' : 'fp-h')

  const send = async (e: FormEvent): Promise<void> => {
    e.preventDefault()
    if (!isEmail(email)) {
      setError('Enter an email address like name@example.com.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api('POST', '/auth/password/forgot', { email })
      setSent(true)
      requestAnimationFrame(() => document.getElementById('fp-h2')?.focus())
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg text-ink">
      <AuthHeader />
      <CardLayout labelledBy={sent ? 'fp-h2' : 'fp-h'}>
        {sent ? (
          <>
            <IconBadge icon={MailCheck} tone="success" />
            <div role="status">
              <Heading id="fp-h2" title="Check your inbox.">
                If an account exists for <strong className="text-ink">{email.trim()}</strong>, a
                reset link is on its way. It can take a minute to arrive.
              </Heading>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline-strong" onClick={() => setSent(false)}>
                Use a different email
              </Button>
            </div>
          </>
        ) : (
          <form onSubmit={send} noValidate className="flex flex-col gap-6">
            <IconBadge icon={KeyRound} />
            <Heading id="fp-h" title="Forgot your password?">
              Enter the email you signed up with and we’ll send you a link to choose a new one.
            </Heading>
            {error && <Alert>{error}</Alert>}
            <TextField
              label="Email"
              type="email"
              inputMode="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <Button type="submit" variant="solid" size="lg" className="w-full" disabled={busy}>
              {busy ? <Spinner size={18} /> : null}
              {busy ? 'Sending…' : 'Send reset link'}
            </Button>
          </form>
        )}
        <BackToLogin email={email} />
      </CardLayout>
    </div>
  )
}

export function BackToLogin({ email }: { email?: string }): React.JSX.Element {
  return (
    <Link
      to="/login"
      state={email ? { email } : {}}
      className="inline-flex min-h-11 items-center gap-2 self-start text-sm font-medium text-ink no-underline hover:text-link-hover"
    >
      <ArrowLeft aria-hidden size={16} />
      Back to log in
    </Link>
  )
}
