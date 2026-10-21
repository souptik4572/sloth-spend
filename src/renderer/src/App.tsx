import { useEffect, useState } from 'react'
import { init } from './lib/api'
import { useHealthPolling } from './lib/useHealthPolling'
import { useApp } from './store'
import { Boot } from './screens/Boot'
import { Workspace } from './screens/Workspace'
import { KitchenSink } from './screens/KitchenSink'
import { Toaster } from './components/ui/Toast'

function useHash(): string {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const on = (): void => setHash(window.location.hash)
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return hash
}

function App(): React.JSX.Element {
  const hash = useHash()
  const screen = useApp((s) => s.screen)

  useEffect(() => {
    void init().then((cfg) => useApp.getState().configure(cfg.version))
    return window.sloth.onEngineExit((code) => useApp.getState().engineExited(code))
  }, [])
  useHealthPolling()

  if (import.meta.env.DEV && hash === '#/kitchen-sink') return <KitchenSink />
  return (
    <>
      {screen === 'boot' ? <Boot /> : <Workspace />}
      <Toaster />
    </>
  )
}

export default App
