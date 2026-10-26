import './bridge' // first: renderer modules read window.sloth when they load
import './styles.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { applyTheme, onThemeChange, type Theme } from '@renderer/lib/theme'
import App from './App'

// The browser's own UI (mobile address bar) follows the theme too.
const syncThemeColor = (t: Theme): void =>
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute('content', t === 'dark' ? '#0B051D' : '#FFFFFF')
onThemeChange(syncThemeColor)
syncThemeColor(applyTheme()) // before the first paint, so the page never flashes the other theme

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
