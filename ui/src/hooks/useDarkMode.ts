import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'explain.darkMode'

function readInitial(): boolean {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored !== null) return stored === 'true'
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}

export function useDarkMode(): [boolean, (next: boolean) => void] {
  const [dark, setDark] = useState<boolean>(readInitial)

  useEffect(() => {
    const root = document.documentElement
    if (dark) {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
    localStorage.setItem(STORAGE_KEY, String(dark))
  }, [dark])

  const toggle = useCallback((next: boolean) => setDark(next), [])

  return [dark, toggle]
}
