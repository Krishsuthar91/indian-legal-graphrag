import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import QueryInput, { type QueryInputValues } from '../components/QueryInput'
import { useLocalSettings } from '../hooks/useLocalSettings'
import { useRecentQuestions } from '../hooks/useRecentQuestions'

export default function Home() {
  const navigate = useNavigate()
  const { recent, addRecent, clearRecent } = useRecentQuestions()
  const { settings } = useLocalSettings()

  const handleSubmit = (values: QueryInputValues) => {
    addRecent({ query: values.query, language: values.language, topK: values.topK })
    const params = new URLSearchParams()
    params.set('q', values.query)
    if (values.language) params.set('lang', values.language)
    params.set('top_k', String(values.topK))
    navigate(`/explain?${params.toString()}`)
  }

  return (
    <div className="mx-auto max-w-3xl px-4 pt-14 sm:pt-20">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center"
      >
        <span className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 dark:border-indigo-500/30 dark:bg-indigo-500/10 dark:text-indigo-300">
          Explainable · Multilingual · Hierarchical Graph-RAG
        </span>
        <h1 className="mt-4 text-3xl font-bold text-slate-900 sm:text-4xl dark:text-white">
          Ask Indian legal questions.
          <span className="block text-indigo-600 dark:text-indigo-400">Get cited, verifiable answers.</span>
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-sm text-slate-500 dark:text-slate-400">
          Hybrid hierarchical graph retrieval + vector search + an LLM — every answer ships
          with evidence, reasoning, confidence, and a full provenance trail.
        </p>
      </motion.div>

      <div className="mt-8">
        <QueryInput
          initialLanguage={settings.defaultLanguage}
          initialTopK={settings.defaultTopK}
          onSubmit={handleSubmit}
        />
      </div>

      {recent.length > 0 && (
        <motion.section
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.15 }}
          className="mt-10"
        >
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Recent questions
            </h2>
            <button
              type="button"
              onClick={clearRecent}
              className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            >
              Clear
            </button>
          </div>
          <ul className="space-y-2">
            {recent.map((q) => (
              <li key={`${q.query}-${q.timestamp}`}>
                <button
                  type="button"
                  onClick={() => {
                    const params = new URLSearchParams()
                    params.set('q', q.query)
                    if (q.language) params.set('lang', q.language)
                    params.set('top_k', String(q.topK))
                    navigate(`/explain?${params.toString()}`)
                  }}
                  className="flex w-full items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-left text-sm text-slate-700 transition hover:border-indigo-300 hover:shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-indigo-500/50"
                >
                  <span className="truncate">{q.query}</span>
                  <span className="ml-auto shrink-0 font-mono text-[11px] text-slate-400">
                    {new Date(q.timestamp).toLocaleString()}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </motion.section>
      )}
    </div>
  )
}
