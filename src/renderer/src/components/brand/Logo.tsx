// Brand art copied from the design canvas (Boot.dc.html / Import.dc.html).
// Strokes are hard-coded ink on pink or white in both themes, on purpose (IMPL §5.7).

const INK = '#0B051D'

function Face({ strokeWidth }: { strokeWidth: number }): React.JSX.Element {
  return (
    <g
      fill="none"
      stroke={INK}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <ellipse cx="18" cy="19" rx="11" ry="9.5" />
      <path d="M15 9.8c.8-1.3 2-1.8 3-1.5M18.6 9.6c.9-1.1 2-1.4 3-1" />
      <ellipse cx="13.6" cy="18.4" rx="3.2" ry="2.2" transform="rotate(-28 13.6 18.4)" />
      <ellipse cx="22.4" cy="18.4" rx="3.2" ry="2.2" transform="rotate(28 22.4 18.4)" />
      <circle cx="13.9" cy="18.2" r="0.9" fill={INK} stroke="none" />
      <circle cx="22.1" cy="18.2" r="0.9" fill={INK} stroke="none" />
      <ellipse cx="18" cy="21.4" rx="1.4" ry="1" fill={INK} stroke="none" />
      <path d="M16.2 23.8c1.1.8 2.5.8 3.6 0" />
    </g>
  )
}

/** 36 px sloth face on a pink circle — every header. */
export function Logo({ size = 36 }: { size?: number }): React.JSX.Element {
  return (
    <svg aria-hidden width={size} height={size} viewBox="0 0 36 36">
      <circle cx="18" cy="18" r="18" fill="#FFA8CD" />
      <Face strokeWidth={1.8} />
    </svg>
  )
}

/** The face on a white circle — Ask Sloth empty and waiting states (96 px). */
export function SlothAvatar({ size = 96 }: { size?: number }): React.JSX.Element {
  return (
    <svg aria-hidden width={size} height={size} viewBox="0 0 36 36">
      <circle cx="18" cy="18" r="18" fill="#FFFFFF" />
      <Face strokeWidth={1.4} />
    </svg>
  )
}

/** "SlothSpend" wordmark with the logo. */
export function Wordmark(): React.JSX.Element {
  return (
    <span className="flex items-center gap-2.5">
      <Logo />
      <span className="text-xl leading-tight font-bold tracking-[-0.01em]">SlothSpend</span>
    </span>
  )
}
