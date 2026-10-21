import './styles/index.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { applyTheme, onThemeChange, type Theme } from './lib/theme'
import App from './App'

// Keep the native window background in step with the theme so resizes never flash the other colour.
const syncWindow = (t: Theme): void =>
  void window.sloth.setBackground(t === 'dark' ? '#0B051D' : '#FFFFFF')
onThemeChange(syncWindow)

// Apply the theme before the first paint so the window never flashes the wrong one.
syncWindow(applyTheme())

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
