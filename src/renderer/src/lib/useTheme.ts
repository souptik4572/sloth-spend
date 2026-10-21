import { useEffect, useState } from 'react'
import { currentTheme, onThemeChange, type Theme } from './theme'

/** The resolved theme ("light" | "dark"), re-rendering when it changes. */
export function useTheme(): Theme {
  const [theme, setTheme] = useState<Theme>(currentTheme)
  useEffect(() => onThemeChange(setTheme), [])
  return theme
}
