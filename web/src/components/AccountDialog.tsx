import { useMemo, useState, type FormEvent } from 'react'
import { LogOut, Trash2, X } from 'lucide-react'
import { Button, IconButton } from '@renderer/components/ui/Button'
import { Modal } from '@renderer/components/ui/Modal'
import { Segmented } from '@renderer/components/ui/Segmented'
import { Spinner } from '@renderer/components/ui/Spinner'
import { toast } from '@renderer/lib/toast'
import { api, errorText } from '@web/lib/api'
import { passwordRules } from '@web/lib/password'
import { initials, leave, useSession } from '@web/lib/session'
import { Alert } from './Alert'
import { PasswordRules } from './PasswordRules'
import { PasswordField } from './TextField'

export type AccountSection = 'account' | 'security'

/** "Account" and "Password & security" from the account menu: who you are, your password, other devices, delete. */
export function AccountDialog({
  section,
  onSection,
  onClose
}: {
  section: AccountSection | null
  onSection: (s: AccountSection) => void
  onClose: () => void
}): React.JSX.Element {
  return (
    <Modal open={section !== null} onClose={onClose} labelledBy="acct-h" maxWidth={640}>
      <div className="flex flex-col gap-6">
        <div className="flex items-center gap-3">
          <h2 id="acct-h" className="m-0 mr-auto text-display-tab">
            Your account
          </h2>
          <IconButton icon={X} label="Close" onClick={onClose} />
        </div>
        <Segmented
          label="Section"
          value={section ?? 'account'}
          onChange={onSection}
          options={[
            { value: 'account', label: 'Account' },
            { value: 'security', label: 'Password & security' }
          ]}
        />
        {section === 'security' ? <Security /> : <Profile />}
      </div>
    </Modal>
  )
}

function Profile(): React.JSX.Element | null {
  const user = useSession((s) => s.user)
  const [confirming, setConfirming] = useState(false)
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (!user) return null
  const since = new Date(user.created_at).toLocaleDateString(undefined, {
    month: 'long',
    day: 'numeric',
    year: 'numeric'
  })

  const remove = async (e: FormEvent): Promise<void> => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api('DELETE', '/auth/account', { password })
      leave('Your account and everything in it were deleted.')
    } catch (err) {
      setBusy(false)
      setError(errorText(err))
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-4 rounded-tile bg-card p-4">
        <span
          aria-hidden
          className="flex size-14 shrink-0 items-center justify-center rounded-full bg-accent text-base font-bold text-on-accent"
        >
          {initials(user.name)}
        </span>
        <div className="min-w-0">
          <p className="m-0 text-h3">{user.name}</p>
          <p className="m-0 truncate text-sm text-muted">{user.email}</p>
          <p className="m-0 text-xs text-muted">Member since {since}</p>
        </div>
      </div>
      <p className="m-0 text-sm text-text-2">
        Your statements, merchant edits, chats and reminders live in your own private workspace.
        Nobody else who uses SlothSpend can see them.
      </p>

      <section aria-labelledby="del-h" className="flex flex-col gap-3 border-t border-line pt-6">
        <h3 id="del-h" className="m-0 text-h3">
          Delete account
        </h3>
        <p className="m-0 text-sm text-text-2">
          Deletes your account and your whole workspace — statements, reports, chats, reminders and
          settings. This can’t be undone.
        </p>
        {confirming ? (
          <form onSubmit={remove} noValidate className="flex flex-col gap-3">
            {error && <Alert>{error}</Alert>}
            <PasswordField
              label="Type your password to confirm"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <div className="flex flex-wrap gap-2">
              <Button type="submit" variant="danger" icon={Trash2} disabled={busy || !password}>
                {busy ? 'Deleting…' : 'Delete my account'}
              </Button>
              <Button variant="ghost" onClick={() => setConfirming(false)} disabled={busy}>
                Keep my account
              </Button>
            </div>
          </form>
        ) : (
          <div>
            <Button variant="danger" icon={Trash2} onClick={() => setConfirming(true)}>
              Delete account…
            </Button>
          </div>
        )}
      </section>
    </div>
  )
}

function Security(): React.JSX.Element | null {
  const user = useSession((s) => s.user)
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [busy, setBusy] = useState<'password' | 'others' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const rules = useMemo(() => passwordRules(next, user?.email ?? ''), [next, user?.email])
  if (!user) return null

  const change = async (e: FormEvent): Promise<void> => {
    e.preventDefault()
    if (!current) return setError('Enter your current password.')
    if (!rules.every((r) => r.ok))
      return setError('Choose a new password that meets all three rules.')
    setBusy('password')
    setError(null)
    try {
      await api('POST', '/auth/password', { current, new: next })
      setCurrent('')
      setNext('')
      toast('Password changed. Your other devices were logged out.')
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  const logOutOthers = async (): Promise<void> => {
    setBusy('others')
    try {
      const { ended } = await api<{ ended: number }>('POST', '/auth/logout-others')
      toast(
        ended
          ? `Logged out of ${ended} other ${ended === 1 ? 'device' : 'devices'}.`
          : 'You weren’t logged in anywhere else.'
      )
    } catch (err) {
      toast(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={change} noValidate className="flex flex-col gap-4">
        <h3 className="m-0 text-h3">Change password</h3>
        {error && <Alert>{error}</Alert>}
        <PasswordField
          label="Current password"
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          required
        />
        <PasswordField
          label="New password"
          autoComplete="new-password"
          value={next}
          maxLength={256}
          onChange={(e) => setNext(e.target.value)}
          aria-describedby="acct-rules"
          below={<PasswordRules id="acct-rules" rules={rules} />}
          required
        />
        <div>
          <Button type="submit" variant="solid" disabled={busy !== null}>
            {busy === 'password' ? <Spinner size={16} /> : null}
            {busy === 'password' ? 'Saving…' : 'Save new password'}
          </Button>
        </div>
        <p className="m-0 text-xs text-muted">
          Saving it logs you out on your other devices. You stay logged in here.
        </p>
      </form>

      <section aria-labelledby="dev-h" className="flex flex-col gap-3 border-t border-line pt-6">
        <h3 id="dev-h" className="m-0 text-h3">
          Other devices
        </h3>
        <p className="m-0 text-sm text-text-2">
          Logged in on a computer you no longer use? End every session except this one.
        </p>
        <div>
          <Button
            variant="outline-strong"
            icon={LogOut}
            onClick={() => void logOutOthers()}
            disabled={busy !== null}
          >
            Log out other devices
          </Button>
        </div>
      </section>
    </div>
  )
}
