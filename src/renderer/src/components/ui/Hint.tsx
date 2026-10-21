import { useId, type ReactNode } from 'react'

/**
 * Dotted-underline term with a tooltip, as the design does for "(q10–q90)" and "Price-rise chance".
 * Focusable, so the explanation reaches keyboard and screen-reader users too.
 */
export function Hint({ text, children }: { text: string; children: ReactNode }): React.JSX.Element {
  const id = useId()
  return (
    <span
      tabIndex={0}
      aria-describedby={id}
      className="group relative cursor-help rounded-sm underline decoration-dotted underline-offset-2"
    >
      {children}
      <span
        role="tooltip"
        id={id}
        className="pointer-events-none invisible absolute bottom-full left-1/2 z-50 mb-2 w-max max-w-[260px] -translate-x-1/2 rounded-tile bg-solid px-3 py-2 text-left text-xs leading-snug font-normal text-on-solid no-underline opacity-0 shadow-[0_2px_4px_var(--shadow)] transition-opacity duration-150 group-hover:visible group-hover:opacity-100 group-focus-visible:visible group-focus-visible:opacity-100"
      >
        {text}
      </span>
    </span>
  )
}
