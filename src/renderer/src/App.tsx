import { useEffect, useState } from 'react'
import { Wordmark } from './components/brand/Logo'
import { ThemeToggle } from './components/shell/ThemeToggle'
import { KitchenSink } from './screens/KitchenSink'

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
  if (import.meta.env.DEV && hash === '#/kitchen-sink') return <KitchenSink />

  // M0 placeholder. M1 replaces this with the Boot screen and the workspace shell.
  return (
    <div className="flex min-h-screen flex-col bg-bg text-ink">
      <header className="flex min-h-[72px] items-center gap-4 px-6 py-3.5">
        <span className="mr-auto">
          <Wordmark />
        </span>
        <ThemeToggle />
      </header>
      <main className="flex flex-1 flex-col items-start gap-4 px-6 pb-10">
        <h1 className="m-0 text-display-xl">Slow and steady.</h1>
        <p className="m-0 text-lead text-muted">
          The engine and Boot screen arrive in the next milestone.
        </p>
        {import.meta.env.DEV && <a href="#/kitchen-sink">Open the kitchen sink</a>}
      </main>
    </div>
  )
}

export default App
