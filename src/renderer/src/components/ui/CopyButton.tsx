import { useEffect, useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { Button } from './Button'
import { toast } from '../../lib/toast'

/**
 * Copies with the Clipboard API, or — where a browser doesn't offer it (plain http on the web) — the older
 * select-and-copy. Resolves false if neither worked.
 */
async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    /* permission refused: try the fallback */
  }
  const area = document.createElement('textarea')
  area.value = text
  area.setAttribute('readonly', '')
  area.style.position = 'fixed'
  area.style.opacity = '0'
  document.body.appendChild(area)
  area.select()
  try {
    return document.execCommand('copy')
  } catch {
    return false
  } finally {
    area.remove()
  }
}

/** "Copy" → "Copied" for 2 s. Drafts are copied, never sent (spec: inform, never act). */
export function CopyButton({
  text,
  label = 'Copy'
}: {
  text: string
  label?: string
}): React.JSX.Element {
  const [copied, setCopied] = useState(false)
  useEffect(() => {
    if (!copied) return
    const t = setTimeout(() => setCopied(false), 2000)
    return () => clearTimeout(t)
  }, [copied])
  return (
    <Button
      variant="outline-strong"
      icon={copied ? Check : Copy}
      className="px-3.5"
      onClick={() => {
        void copyText(text).then((ok) =>
          ok ? setCopied(true) : toast('Couldn’t copy here. Select the text and copy it yourself.')
        )
      }}
    >
      <span aria-live="polite">{copied ? 'Copied' : label}</span>
    </Button>
  )
}
