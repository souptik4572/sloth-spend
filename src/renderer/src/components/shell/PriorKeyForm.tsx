import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { CircleCheck, ExternalLink } from 'lucide-react'
import { Button } from '../ui/Button'
import { TextInput } from '../ui/Field'
import { Spinner } from '../ui/Spinner'
import { useApp } from '../../store'

const KEY_URL = 'https://platform.priorlabs.ai'

/**
 * Optional Prior Labs key on the Boot TabPFN row (D-Boot, IMPL §2 #21 / M4.11). Without a key SlothSpend
 * uses TabPFN v2; with one it upgrades to TabPFN-3.5. The key goes to the main process, which encrypts
 * it with the OS keychain and restarts the engine — it is never read back into the renderer.
 */
export function PriorKeyForm(): React.JSX.Element {
  const [saved, setSaved] = useState<boolean | null>(null) // null = still asking main
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState<'save' | 'remove' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const inputId = useId()
  const hintId = useId()
  const upgrade = useApp((s) => s.health?.tabpfn.upgrade)

  useEffect(() => {
    void window.sloth.priorKey.present().then(setSaved)
  }, [])

  useEffect(() => {
    if (editing) input.current?.focus()
  }, [editing])

  const save = async (e: FormEvent): Promise<void> => {
    e.preventDefault()
    const key = input.current?.value ?? ''
    setBusy('save')
    setError(null)
    const result = await window.sloth.priorKey.save(key)
    setBusy(null)
    if (!result.ok) {
      setError(result.error)
      return
    }
    if (input.current) input.current.value = '' // don't keep the secret in the DOM
    setSaved(true)
    setEditing(false)
  }

  const remove = async (): Promise<void> => {
    setBusy('remove')
    setError(null)
    await window.sloth.priorKey.remove()
    setBusy(null)
    setSaved(false)
  }

  if (saved === null) return <></>

  if (saved && !editing) {
    return (
      <div className="flex flex-col gap-2">
        <p className="m-0 flex items-center gap-2 text-sm font-medium">
          <CircleCheck aria-hidden size={16} strokeWidth={2.4} className="shrink-0 text-success" />
          Prior Labs key saved · encrypted on this computer
        </p>
        <p className="m-0 text-sm text-muted">
          {upgrade?.state === 'failed'
            ? `The TabPFN-3.5 upgrade didn’t work (${upgrade.error ?? 'unknown error'}). SlothSpend is still using TabPFN v2.`
            : 'SlothSpend upgrades to TabPFN-3.5 with this key. Remove it to go back to TabPFN v2.'}
        </p>
        <div className="flex flex-wrap gap-2">
          <Button variant="soft" disabled={busy !== null} onClick={() => setEditing(true)}>
            Replace key
          </Button>
          <Button variant="ghost" disabled={busy !== null} onClick={() => void remove()}>
            {busy === 'remove' && <Spinner />}
            Remove
          </Button>
        </div>
      </div>
    )
  }

  return (
    <form className="flex flex-col gap-3" onSubmit={(e) => void save(e)}>
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex min-w-0 flex-[1_1_240px] flex-col gap-1.5">
          <label htmlFor={inputId} className="text-sm font-medium">
            Prior Labs key <span className="font-normal text-muted">(optional)</span>
          </label>
          <TextInput
            id={inputId}
            ref={input}
            type="password"
            placeholder="Paste key"
            autoComplete="off"
            spellCheck={false}
            aria-describedby={hintId}
            aria-invalid={error ? true : undefined}
            disabled={busy !== null}
          />
        </div>
        <Button type="submit" variant="solid" disabled={busy !== null}>
          {busy === 'save' && <Spinner />}
          {busy === 'save' ? 'Saving…' : 'Save key'}
        </Button>
        {saved && (
          <Button variant="ghost" disabled={busy !== null} onClick={() => setEditing(false)}>
            Cancel
          </Button>
        )}
      </div>
      {error && (
        <p role="alert" className="m-0 text-sm font-medium">
          {error}
        </p>
      )}
      <p id={hintId} className="m-0 text-xs leading-[1.65] text-muted">
        Upgrades TabPFN v2 to TabPFN-3.5 (non-commercial license). Stored encrypted on this computer
        and never shown again. It’s a model license, not an app login — skip it and SlothSpend uses
        TabPFN v2.
      </p>
      <p className="m-0 text-sm">
        <button
          type="button"
          onClick={() => void window.sloth.openExternal(KEY_URL)}
          className="inline-flex cursor-pointer items-center gap-1 border-0 bg-transparent p-0 font-medium text-ink underline underline-offset-2 hover:text-link-hover"
        >
          Get a free key at platform.priorlabs.ai
          <ExternalLink aria-hidden size={14} />
        </button>
      </p>
    </form>
  )
}
