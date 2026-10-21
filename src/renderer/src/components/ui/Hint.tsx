import type { ReactNode } from 'react'

/** Dotted-underline term with a native tooltip, as the design does for "(q10–q90)" and "Price-rise chance". */
export function Hint({ text, children }: { text: string; children: ReactNode }): React.JSX.Element {
  return (
    <abbr title={text} className="cursor-help underline decoration-dotted underline-offset-2">
      {children}
    </abbr>
  )
}
