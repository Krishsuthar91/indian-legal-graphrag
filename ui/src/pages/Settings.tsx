import { motion } from 'framer-motion'
import { API_BASE_URL } from '../api/client'
import { LANGUAGES, useLocalSettings } from '../hooks/useLocalSettings'

interface SettingsProps {
  dark: boolean
  onToggleDark: (next: boolean) => void
}

export default function Settings({ dark, onToggleDark }: SettingsProps) {
  const { settings, updateSettings } = useLocalSettings()

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8">
      <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Settings</h1>

      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900"
      >
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Appearance
        </h2>
        <label className="flex cursor-pointer items-center justify-between">
          <span className="text-sm text-slate-700 dark:text-slate-200">Dark mode</span>
          <button
            type="button"
            onClick={() => onToggleDark(!dark)}
            aria-label="Toggle dark mode"
            aria-pressed={dark}
            className={`relative h-6 w-11 rounded-full transition ${dark ? 'bg-indigo-600' : 'bg-slate-300'}`}
          >
            <span
              className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${
                dark ? 'left-[22px]' : 'left-0.5'
              }`}
            />
          </button>
        </label>
      </motion.section>

      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900"
      >
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Defaults
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300">
              Document language
            </span>
            <select
              value={settings.defaultLanguage}
              onChange={(e) => updateSettings({ defaultLanguage: e.target.value })}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            >
              {LANGUAGES.map((lang) => (
                <option key={lang.code} value={lang.code}>
                  {lang.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300">
              Default top-k evidence
            </span>
            <select
              value={settings.defaultTopK}
              onChange={(e) => updateSettings({ defaultTopK: Number(e.target.value) })}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            >
              {[3, 5, 8, 10].map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </label>
        </div>
      </motion.section>

      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900"
      >
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          API
        </h2>
        <dl className="space-y-2 text-sm">
          <div className="flex items-center justify-between gap-4">
            <dt className="text-slate-500 dark:text-slate-400">Base URL</dt>
            <dd className="font-mono text-xs text-slate-800 dark:text-slate-100">{API_BASE_URL}</dd>
          </div>
          <div className="flex items-center justify-between gap-4">
            <dt className="text-slate-500 dark:text-slate-400">Answer + provenance</dt>
            <dd className="font-mono text-xs text-slate-800 dark:text-slate-100">POST /query</dd>
          </div>
          <div className="flex items-center justify-between gap-4">
            <dt className="text-slate-500 dark:text-slate-400">Retrieval only</dt>
            <dd className="font-mono text-xs text-slate-800 dark:text-slate-100">POST /explain</dd>
          </div>
          <div className="flex items-center justify-between gap-4">
            <dt className="text-slate-500 dark:text-slate-400">Provenance record</dt>
            <dd className="font-mono text-xs text-slate-800 dark:text-slate-100">GET /provenance/&#123;id&#125;</dd>
          </div>
        </dl>
      </motion.section>

      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900"
      >
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          About
        </h2>
        <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-300">
          Explainable Multilingual Hierarchical Graph-RAG with Hybrid Hierarchical Graph
          Retrieval (HHGR). Module 8 React frontend dashboard over the Module 1–7 backend:
          ingestion, hierarchy parsing, knowledge graph, HHGR retrieval, embeddings, and
          explainable LLM answer generation.
        </p>
      </motion.section>
    </div>
  )
}
