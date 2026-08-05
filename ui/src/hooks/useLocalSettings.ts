import { useCallback, useEffect, useState } from 'react'
import type { LocalSettings } from '../types'

const STORAGE_KEY = 'explain.settings'

export const DEFAULT_SETTINGS: LocalSettings = {
  darkMode: false,
  defaultLanguage: '',
  defaultTopK: 5,
}

export const LANGUAGES: { code: string; label: string }[] = [
  { code: '', label: 'Any language' },
  { code: 'en', label: 'English (en)' },
  { code: 'hi', label: 'Hindi (hi)' },
  { code: 'kn', label: 'Kannada (kn)' },
  { code: 'ta', label: 'Tamil (ta)' },
  { code: 'te', label: 'Telugu (te)' },
  { code: 'ml', label: 'Malayalam (ml)' },
  { code: 'bn', label: 'Bengali (bn)' },
]

function readSettings(): LocalSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULT_SETTINGS
    return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) }
  } catch {
    return DEFAULT_SETTINGS
  }
}

export function useLocalSettings(): {
  settings: LocalSettings
  updateSettings: (patch: Partial<LocalSettings>) => void
} {
  const [settings, setSettings] = useState<LocalSettings>(readSettings)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  }, [settings])

  const updateSettings = useCallback((patch: Partial<LocalSettings>) => {
    setSettings((prev) => ({ ...prev, ...patch }))
  }, [])

  return { settings, updateSettings }
}
