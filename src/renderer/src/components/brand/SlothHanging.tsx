// The Boot hero illustration, copied from Boot.dc.html. Always drawn on the pink hero.

const INK = '#0B051D'

export function SlothHanging({
  width = 280,
  className
}: {
  width?: number
  className?: string
}): React.JSX.Element {
  return (
    <svg
      role="img"
      aria-label="A line drawing of a sloth hanging from a branch"
      width={width}
      height={(width * 214) / 240}
      viewBox="0 0 240 214"
      fill="none"
      stroke={INK}
      strokeWidth={3}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={{ maxWidth: '100%', height: 'auto' }}
    >
      <path d="M6 34C70 22 150 42 234 28" />
      <path d="M184 31c5-13 18-18 30-14-4 12-17 18-30 14Z" />
      <path d="M60 29c-3-10 2-19 12-22 2 10-3 18-12 22Z" />
      <path d="M92 124C82 96 84 66 96 38" />
      <path d="M148 124c10-28 8-58-4-86" />
      <path d="M91 41c1-6 5-9 10-8" />
      <path d="M139 37c2-6 6-8 11-6" />
      <ellipse cx="120" cy="150" rx="40" ry="44" />
      <path d="M100 188c-5 9-4 18 3 24" />
      <path d="M140 188c5 9 4 18-3 24" />
      <circle cx="120" cy="112" r="30" fill="#FFA8CD" />
      <ellipse cx="120" cy="117" rx="22" ry="17" fill="#FFFFFF" strokeWidth={2.5} />
      <ellipse
        cx="110"
        cy="114"
        rx="7"
        ry="4.5"
        transform="rotate(-25 110 114)"
        fill={INK}
        stroke="none"
      />
      <ellipse
        cx="130"
        cy="114"
        rx="7"
        ry="4.5"
        transform="rotate(25 130 114)"
        fill={INK}
        stroke="none"
      />
      <circle cx="111" cy="113.5" r="1.6" fill="#FFFFFF" stroke="none" />
      <circle cx="129" cy="113.5" r="1.6" fill="#FFFFFF" stroke="none" />
      <ellipse cx="120" cy="122" rx="3.4" ry="2.4" fill={INK} stroke="none" />
      <path d="M114 127c4 3 8 3 12 0" strokeWidth={2.5} />
    </svg>
  )
}
