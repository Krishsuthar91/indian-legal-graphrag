import { useCallback, useEffect, useState } from 'react'
import type { RecentQuestion } from '../types'

const STORAGE_KEY = 'explain.recentQuestions'
const MAX_RECENT = 10

function readRecent(): RecentQuestion[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as RecentQuestion[]) : []
  } catch {
    return []
  }
}

export function useRecentQuestions(): {
  recent: RecentQuestion[]
  addRecent: (q: Omit<RecentQuestion, 'timestamp'>) => void
  clearRecent: () => void
} {
  const [recent, setRecent] = useState<RecentQuestion[]>(readRecent)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(recent))
  }, [recent])

  const addRecent = useCallback((q: Omit<RecentQuestion, 'timestamp'>) => {
    setRecent((prev) => {
      const next = [
        { ...q, timestamp: Date.now() },
        ...prev.filter((p) => p.query !== q.query),
      ]
      return next.slice(0, MAX_RECENT)
    })
  }, [])

  const clearRecent = useCallback(() => setRecent([]), [])

  return { recent, addRecent, clearRecent }
}
