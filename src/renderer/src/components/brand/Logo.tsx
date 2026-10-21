// Brand art. The SVG files under src/renderer/src/assets are the single source of truth
// (see design/icons/README.md). Colours are fixed ink-on-pink / ink-on-white in both themes.
import logoMark from '../../assets/brand/logo-mark.svg'
import slothAvatar from '../../assets/mascot/sloth-avatar.svg'
import slothAvatarSleepy from '../../assets/mascot/sloth-avatar-sleepy.svg'

/** 36 px sloth face on a pink circle — every header. Decorative: the wordmark names the app. */
export function Logo({ size = 36 }: { size?: number }): React.JSX.Element {
  return <img src={logoMark} alt="" aria-hidden width={size} height={size} draggable={false} />
}

/** The face on a white circle — Ask Sloth empty states (96 px). */
export function SlothAvatar({ size = 96 }: { size?: number }): React.JSX.Element {
  return <img src={slothAvatar} alt="" aria-hidden width={size} height={size} draggable={false} />
}

/** Eyes-closed avatar for waiting and working states ("Reading along with you."). */
export function SlothAvatarSleepy({ size = 96 }: { size?: number }): React.JSX.Element {
  return (
    <img src={slothAvatarSleepy} alt="" aria-hidden width={size} height={size} draggable={false} />
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
