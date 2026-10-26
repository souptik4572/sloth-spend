import { useState, type FormEvent } from 'react'
import { Mail } from 'lucide-react'
import { Button } from '@renderer/components/ui/Button'
import { Spinner } from '@renderer/components/ui/Spinner'
import { Alert } from '@web/components/Alert'
import { AuthHeader, HeaderSwitch } from '@web/components/AuthHeader'
import { Heading, SplitLayout } from '@web/components/Layouts'
import { Checkbox, PasswordField, TextField } from '@web/components/TextField'
import { usePage } from '@web/components/usePage'
import { api, ApiError, errorText, type User } from '@web/lib/api'
import { isEmail } from '@web/lib/password'
import { Link, navigate, useLocation } from '@web/lib/router'
import { takeNotice, useSession } from '@web/lib/session'

type Busy = 'password' | 'link' | null

/** Log in (Web artboard 12): password or an emailed sign-in link; "Keep me logged in" decides the cookie. */
export function Login(): React.JSX.Element {
  usePage('Log in', 'li-h')
  const { state } = useLocation()
  const [email, setEmail] = useState(typeof state.email === 'string' ? state.email : '')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(true)
  const [busy, setBusy] = useState<Busy>(null)
  const [error, setError] = useState<{ text: string; mismatch: boolean } | null>(() => {
    const notice = typeof state.notice === 'string' ? state.notice : takeNotice()
    return notice ? { text: notice, mismatch: false } : null
  })

  const logIn = async (e: FormEvent): Promise<void> => {
    e.preventDefault()
    if (!isEmail(email) || !password) {
      setError({ text: 'Enter your email and password.', mismatch: false })
      return
    }
    setBusy('password')
    setError(null)
    try {
      const { user } = await api<{ user: User }>('POST', '/auth/login', {
        email,
        password,
        remember
      })
      useSession.getState().signedIn(user)
      navigate('/', { replace: true })
    } catch (err) {
      setBusy(null)
      if (err instanceof ApiError && err.code === 'unverified') {
        navigate('/check-email', { state: { email: email.trim(), kind: 'verify' } })
      } else {
        setError({ text: errorText(err), mismatch: err instanceof ApiError && err.status === 401 })
      }
    }
  }

  const emailLink = async (): Promise<void> => {
    if (!isEmail(email)) {
      setError({
        text: 'Enter your email above first, and we’ll send the link there.',
        mismatch: false
      })
      document.getElementById('li-email')?.focus()
      return
    }
    setBusy('link')
    setError(null)
    try {
      await api('POST', '/auth/link', { email, remember })
      navigate('/check-email', { state: { email: email.trim(), kind: 'link', remember } })
    } catch (err) {
      setBusy(null)
      setError({ text: errorText(err), mismatch: false })
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg text-ink">
      <AuthHeader>
        <HeaderSwitch prompt="New to SlothSpend?" to="/signup" label="Create account" />
      </AuthHeader>
      <SplitLayout labelledBy="li-h">
        <Heading id="li-h" size="hero" title="Welcome back.">
          Log in to see your audit, reminders and Ask Sloth.
        </Heading>

        {error && (
          <Alert>
            {error.mismatch ? (
              <>
                That email and password don’t match. Try again, or{' '}
                <Link to="/forgot" state={{ email }} className="font-bold text-ink">
                  reset your password
                </Link>
                .
              </>
            ) : (
              error.text
            )}
          </Alert>
        )}

        <form onSubmit={logIn} noValidate className="flex flex-col gap-4">
          <TextField
            id="li-email"
            label="Email"
            type="email"
            autoComplete="email"
            inputMode="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <PasswordField
            id="li-pw"
            label="Password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            invalid={error?.mismatch}
            required
            aside={
              <Link
                to="/forgot"
                state={{ email }}
                className="text-sm font-medium text-ink hover:text-link-hover"
              >
                Forgot password?
              </Link>
            }
          />
          <Checkbox checked={remember} onChange={setRemember}>
            Keep me logged in on this device
          </Checkbox>
          <Button
            type="submit"
            variant="solid"
            size="lg"
            className="w-full"
            disabled={busy !== null}
          >
            {busy === 'password' ? <Spinner size={18} /> : null}
            {busy === 'password' ? 'Logging in…' : 'Log in'}
          </Button>
        </form>

        <div aria-hidden className="flex items-center gap-3 text-xs text-muted">
          <span className="h-px flex-auto bg-line" />
          or
          <span className="h-px flex-auto bg-line" />
        </div>

        <Button
          variant="outline"
          size="lg"
          icon={busy === 'link' ? undefined : Mail}
          className="w-full"
          onClick={() => void emailLink()}
          disabled={busy !== null}
        >
          {busy === 'link' ? <Spinner size={18} /> : null}
          {busy === 'link' ? 'Sending…' : 'Email me a sign-in link'}
        </Button>

        <p className="m-0 text-center text-small text-muted">
          New to SlothSpend?{' '}
          <Link to="/signup" className="font-medium text-ink hover:text-link-hover">
            Create an account
          </Link>
        </p>
      </SplitLayout>
    </div>
  )
}
