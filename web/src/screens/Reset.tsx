import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Shield, TriangleAlert } from 'lucide-react'
import { Button } from '@renderer/components/ui/Button'
import { Spinner } from '@renderer/components/ui/Spinner'
import { Alert } from '@web/components/Alert'
import { AuthHeader } from '@web/components/AuthHeader'
import { CardLayout, Heading, IconBadge } from '@web/components/Layouts'
import { MatchNote, PasswordRules } from '@web/components/PasswordRules'
import { PasswordField } from '@web/components/TextField'
import { usePage } from '@web/components/usePage'
import { api, errorText, type User } from '@web/lib/api'
import { passwordRules } from '@web/lib/password'
import { Link, navigate, takeToken } from '@web/lib/router'
import { once, useSession } from '@web/lib/session'
import { BackToLogin } from './Forgot'

type Check =
  { state: 'checking' } | { state: 'ready'; email: string } | { state: 'gone'; message: string }

/** Choose a new password (Web artboard 14), opened from the reset email. Saving logs out other devices. */
export function Reset(): React.JSX.Element {
  const [token] = useState(takeToken)
  const [check, setCheck] = useState<Check>(() =>
    token
      ? { state: 'checking' }
      : { state: 'gone', message: 'This page needs the link from your reset email.' }
  )
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [shown, setShown] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const email = check.state === 'ready' ? check.email : ''
  const rules = useMemo(() => passwordRules(password, email), [password, email])
  usePage(check.state === 'gone' ? 'Link expired' : 'Choose a new password', 'rp-h')

  useEffect(() => {
    if (!token) return
    once(`reset-check:${token}`, () =>
      api<{ email: string }>('POST', '/auth/password/reset/check', { token })
    )
      .then(({ email }) => setCheck({ state: 'ready', email }))
      .catch((err) => setCheck({ state: 'gone', message: errorText(err) }))
  }, [token])

  const save = async (e: FormEvent): Promise<void> => {
    e.preventDefault()
    if (!rules.every((r) => r.ok)) {
      setError('Choose a password that meets all three rules.')
      return
    }
    if (password !== confirm) {
      setError('The two passwords don’t match yet.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const { user } = await api<{ user: User }>('POST', '/auth/password/reset', {
        token,
        password
      })
      useSession.getState().signedIn(user)
      navigate('/', {
        replace: true,
        state: { notice: 'Password saved. Your other devices were logged out.' }
      })
    } catch (err) {
      setBusy(false)
      setError(errorText(err))
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg text-ink">
      <AuthHeader />
      <CardLayout labelledBy="rp-h">
        {check.state === 'checking' && (
          <p role="status" className="m-0 flex items-center gap-2 text-muted">
            <Spinner size={18} /> Checking your link…
          </p>
        )}
        {check.state === 'gone' && (
          <>
            <IconBadge icon={TriangleAlert} />
            <Heading id="rp-h" title="That link didn’t work.">
              {check.message}
            </Heading>
            <Link
              to="/forgot"
              className="flex h-[52px] items-center justify-center rounded-full bg-solid text-base font-medium !text-on-solid no-underline hover:opacity-90"
            >
              Send a new reset link
            </Link>
          </>
        )}
        {check.state === 'ready' && (
          <form onSubmit={save} noValidate className="flex flex-col gap-6">
            <IconBadge icon={Shield} />
            <Heading id="rp-h" title="Choose a new password.">
              For <strong className="text-ink">{email}</strong>. Saving it logs you out on your
              other devices.
            </Heading>
            {error && <Alert>{error}</Alert>}
            <PasswordField
              label="New password"
              autoComplete="new-password"
              value={password}
              maxLength={256}
              onChange={(e) => setPassword(e.target.value)}
              aria-describedby="rp-rules"
              shown={shown}
              onShownChange={setShown}
              toggleLabel="Show passwords"
              below={<PasswordRules id="rp-rules" rules={rules} />}
              required
            />
            <div className="flex flex-col gap-2">
              <label htmlFor="rp-confirm" className="text-sm font-medium">
                Type it again
              </label>
              <input
                id="rp-confirm"
                type={shown ? 'text' : 'password'}
                autoComplete="new-password"
                value={confirm}
                maxLength={256}
                onChange={(e) => setConfirm(e.target.value)}
                aria-describedby="rp-match"
                aria-invalid={(confirm.length > 0 && confirm !== password) || undefined}
                className={
                  'box-border h-[52px] w-full rounded-full bg-raised px-5 font-sans text-base text-ink ' +
                  (confirm.length > 0 && confirm !== password
                    ? 'border-2 border-ink'
                    : 'border border-line-strong')
                }
                required
              />
              <MatchNote id="rp-match" password={password} confirm={confirm} />
            </div>
            <Button type="submit" variant="solid" size="lg" className="w-full" disabled={busy}>
              {busy ? <Spinner size={18} /> : null}
              {busy ? 'Saving…' : 'Save new password'}
            </Button>
          </form>
        )}
        <BackToLogin email={email} />
      </CardLayout>
    </div>
  )
}
