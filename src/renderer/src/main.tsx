import './styles/index.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { applyTheme } from './lib/theme'
import App from './App'

// Apply the theme before the first paint so the window never flashes the wrong one.
applyTheme()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
