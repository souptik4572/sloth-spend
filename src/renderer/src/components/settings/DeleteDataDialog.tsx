import { useState } from 'react'
import { Trash2 } from 'lucide-react'
import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'
import { Spinner } from '../ui/Spinner'
import { deleteAllData } from '../../lib/settings'

/** The confirmation step of Settings › Delete all local data (IMPL M8.1). */
export function DeleteDataDialog({
  open,
  onClose
}: {
  open: boolean
  onClose: () => void
}): React.JSX.Element {
  const [busy, setBusy] = useState(false)
  const confirm = (): void => {
    setBusy(true)
    void deleteAllData().then((ok) => {
      setBusy(false)
      if (ok) onClose()
    })
  }
  return (
    <Modal open={open} onClose={busy ? () => undefined : onClose} labelledBy="del-h" maxWidth={520}>
      <div className="flex flex-col gap-4">
        <h2 id="del-h" className="m-0 text-h2">
          Delete everything?
        </h2>
        <p className="m-0 text-base">
          Delete everything SlothSpend stored on this computer? Statements, merchant edits, chats
          and reminders. Model downloads stay.
        </p>
        <p className="m-0 text-sm text-muted">This can’t be undone. Your settings are kept.</p>
        <div className="flex flex-wrap justify-end gap-2 pt-2">
          <Button variant="ghost" disabled={busy} onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="danger"
            icon={busy ? undefined : Trash2}
            disabled={busy}
            onClick={confirm}
          >
            {busy && <Spinner />}
            Delete all local data
          </Button>
        </div>
      </div>
    </Modal>
  )
}
