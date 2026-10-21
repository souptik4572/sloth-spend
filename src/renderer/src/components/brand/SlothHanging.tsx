// The Boot hero illustration. Source: src/renderer/src/assets/mascot/sloth-hanging.svg
// (drawn for the pink hero; see design/icons/README.md).
import slothHanging from '../../assets/mascot/sloth-hanging.svg'

export function SlothHanging({
  width = 280,
  className
}: {
  width?: number
  className?: string
}): React.JSX.Element {
  return (
    <img
      src={slothHanging}
      alt="A line drawing of a sloth hanging from a branch"
      width={width}
      height={Math.round((width * 214) / 240)}
      draggable={false}
      className={className}
      style={{ maxWidth: '100%', height: 'auto' }}
    />
  )
}
