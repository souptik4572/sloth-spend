import { useMemo, useState, type FormEvent } from 'react'
import { Button } from '@renderer/components/ui/Button'
import { Spinner } from '@renderer/components/ui/Spinner'
import { Alert } from '@web/components/Alert'
import { AuthHeader, HeaderSwitch } from '@web/components/AuthHeader'
import { Heading, SplitLayout } from '@web/components/Layouts'
import { PasswordRules, StrengthMeter } from '@web/components/PasswordRules'
import { Checkbox, PasswordField, TextField } from '@web/components/TextField'
import { usePage } from '@web/components/usePage'
import { api, errorText } from '@web/lib/api'
import { isEmail, passwordRules } from '@web/lib/password'
import { Link, navigate } from '@web/lib/router'

// Until SlothSpend Web has its own legal pages, these point at the project's published notes (set per deploy).
const TERMS_URL =
  import.meta.env.VITE_TERMS_URL ?? 'https://github.com/souptik4572/sloth-spend#inform-never-act'
const PRIVACY_URL =
  import.meta.env.VITE_PRIVACY_URL ??
  'https://github.com/souptik4572/sloth-spend#privacy-where-your-data-goes'

/** Create your account (Web artboard 10). The confirmation link is emailed; no session until it's opened. */
export function Signup(): React.JSX.Element {
  usePage('Create your account', 'su-h')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [agreed, setAgreed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const rules = useMemo(() => passwordRules(password, email), [password, email])

  const submit = async (e: FormEvent): Promise<void> => {
    e.preventDefault()
    const problem = !name.trim()
      ? 'Enter your name.'
      : !isEmail(email)
        ? 'Enter an email address like name@example.com.'
        : !rules.every((r) => r.ok)
          ? 'Choose a password that meets all three rules below it.'
          : !agreed
            ? 'Agree to the Terms and Privacy Policy to create an account.'
            : null
    if (problem) {
      setError(problem)
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api('POST', '/auth/signup', { name, email, password, accept_terms: agreed })
      navigate('/check-email', { state: { email: email.trim().toLowerCase(), kind: 'verify' } })
    } catch (err) {
      setBusy(false)
      setError(errorText(err))
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg text-ink">
      <AuthHeader>
        <HeaderSwitch prompt="Already have an account?" to="/login" label="Log in" />
      </AuthHeader>
      <SplitLayout labelledBy="su-h">
        <Heading id="su-h" size="hero" title="Create your account.">
          Takes a minute. No bank login needed — you upload your own statements.
        </Heading>

        {error && <Alert>{error}</Alert>}

        <form onSubmit={submit} noValidate className="flex flex-col gap-4">
          <TextField
            label="Name"
            autoComplete="name"
            value={name}
            maxLength={80}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <TextField
            label="Email"
            type="email"
            inputMode="email"
            autoComplete="email"
            value={email}
            maxLength={254}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <PasswordField
            label="Password"
            autoComplete="new-password"
            value={password}
            maxLength={256}
            onChange={(e) => setPassword(e.target.value)}
            aria-describedby="su-pw-rules"
            required
            below={
              <>
                <StrengthMeter rules={rules} />
                <PasswordRules id="su-pw-rules" rules={rules} />
              </>
            }
          />
          <Checkbox checked={agreed} onChange={setAgreed} align="start">
            I agree to the{' '}
            <a
              href={TERMS_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-ink"
            >
              Terms
            </a>{' '}
            and{' '}
            <a
              href={PRIVACY_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-ink"
            >
              Privacy Policy
            </a>
            .
          </Checkbox>
          <Button type="submit" variant="solid" size="lg" className="w-full" disabled={busy}>
            {busy ? <Spinner size={18} /> : null}
            {busy ? 'Creating your account…' : 'Create account'}
          </Button>
        </form>

        <p className="m-0 text-center text-small text-muted">
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-ink hover:text-link-hover">
            Log in
          </Link>
        </p>
      </SplitLayout>
    </div>
  )
}
