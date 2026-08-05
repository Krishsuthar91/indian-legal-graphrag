import { motion } from 'framer-motion'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { LANGUAGES } from '../hooks/useLocalSettings'

export interface QueryInputValues {
  query: string
  language: string
  topK: number
}

interface QueryInputProps {
  initialQuery?: string
  initialLanguage?: string
  initialTopK?: number
  busy?: boolean
  submitLabel?: string
  onSubmit: (values: QueryInputValues) => void
}

export default function QueryInput({
  initialQuery = '',
  initialLanguage = '',
  initialTopK = 5,
  busy = false,
  submitLabel = 'Ask Question',
  onSubmit,
}: QueryInputProps) {
  const [query, setQuery] = useState(initialQuery)
  const [language, setLanguage] = useState(initialLanguage)
  const [topK, setTopK] = useState(initialTopK)

  const canSubmit = query.trim().length > 0 && !busy

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    onSubmit({ query: query.trim(), language, topK })
  }

  return (
    <motion.form
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      onSubmit={handleSubmit}
      className="w-full"
      aria-label="Ask a legal question"
    >
      <div className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-100 dark:border-slate-700 dark:bg-slate-900 dark:focus-within:ring-indigo-500/20">
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              if (canSubmit) onSubmit({ query: query.trim(), language, topK })
            }
          }}
          rows={3}
          placeholder="Ask about any Indian legal provision, e.g. “What does Section 302 of the IPC say about punishment for murder?”"
          className="w-full resize-none bg-transparent text-sm text-slate-800 outline-none placeholder:text-slate-400 dark:text-slate-100 dark:placeholder:text-slate-500"
        />
        <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-2 dark:border-slate-800">
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            aria-label="Document language"
            className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs text-slate-700 outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
          >
            {LANGUAGES.map((lang) => (
              <option key={lang.code} value={lang.code}>
                {lang.label}
              </option>
            ))}
          </select>
          <select
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            aria-label="Top K evidence"
            className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs text-slate-700 outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
          >
            {[3, 5, 8, 10].map((k) => (
              <option key={k} value={k}>
                Top {k} evidence
              </option>
            ))}
          </select>
          <span className="hidden text-[11px] text-slate-400 sm:inline">
            Enter to ask · Shift+Enter for newline
          </span>
          <button
            type="submit"
            disabled={!canSubmit}
            className="ml-auto rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? 'Working…' : submitLabel}
          </button>
        </div>
      </div>
    </motion.form>
  )
}
