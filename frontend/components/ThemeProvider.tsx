'use client'

import { createContext, useContext, useEffect, useState } from 'react'

type Theme = 'light' | 'dark' | 'system'

interface ThemeContextType {
  theme: Theme
  setTheme: (theme: Theme) => void
  resolvedTheme: 'light' | 'dark'
  isDark: boolean
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>('system')
  const [resolvedTheme, setResolvedTheme] = useState<'light' | 'dark'>('light')
  const [mounted, setMounted] = useState(false)

  // Initialize theme from localStorage on client-side mount
  useEffect(() => {
    const saved = localStorage.getItem('theme') as Theme
    if (saved) {
      setThemeState(saved)
    }
    setMounted(true)
  }, [])

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme)
    localStorage.setItem('theme', newTheme)
  };

  useEffect(() => {
    if (!mounted) return

    const updateTheme = () => {
      let activeTheme: 'light' | 'dark' = 'light'
      if (theme === 'system') {
        const media = window.matchMedia('(prefers-color-scheme: dark)')
        activeTheme = media.matches ? 'dark' : 'light'
      } else {
        activeTheme = theme
      }

      setResolvedTheme(activeTheme)

      const root = document.documentElement
      if (activeTheme === 'dark') {
        root.classList.add('dark')
      } else {
        root.classList.remove('dark')
      }
    }

    updateTheme()

    if (theme === 'system') {
      const media = window.matchMedia('(prefers-color-scheme: dark)')
      const listener = () => updateTheme()
      media.addEventListener('change', listener)
      return () => media.removeEventListener('change', listener)
    }
  }, [theme, mounted])

  const isDark = resolvedTheme === 'dark'

  return (
    <ThemeContext.Provider value={{ theme, setTheme, resolvedTheme, isDark }}>
      <div className={mounted ? '' : 'invisible'}>{children}</div>
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
