import { useEffect, useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { Button } from './Button'

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
        void navigator.clipboard.writeText(text).then(() => setCopied(true))
      }}
    >
      <span aria-live="polite">{copied ? 'Copied' : label}</span>
    </Button>
  )
}
