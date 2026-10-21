// Theme preference is a per-viewer convenience: localStorage, not the engine (IMPL §2 #2).
export type ThemePref = 'system' | 'light' | 'dark'
export type Theme = 'light' | 'dark'

const KEY = 'sloth.theme'
const mq = window.matchMedia('(prefers-color-scheme: dark)')
const listeners = new Set<(t: Theme) => void>()

export function readPref(): ThemePref {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : 'system'
  } catch {
    return 'system'
  }
}

export function currentTheme(): Theme {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}

export function applyTheme(pref: ThemePref = readPref()): Theme {
  const theme: Theme = pref === 'dark' || (pref === 'system' && mq.matches) ? 'dark' : 'light'
  document.documentElement.dataset.theme = theme
  listeners.forEach((fn) => fn(theme))
  return theme
}

export function setPref(pref: ThemePref): Theme {
  try {
    if (pref === 'system') localStorage.removeItem(KEY)
    else localStorage.setItem(KEY, pref)
  } catch {
    /* storage unavailable: the choice lasts for this session only */
  }
  return applyTheme(pref)
}

export function onThemeChange(fn: (t: Theme) => void): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

mq.addEventListener('change', () => {
  if (readPref() === 'system') applyTheme('system')
})
