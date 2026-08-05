import { AnimatePresence } from 'framer-motion'
import { useNavigate, useSearchParams } from 'react-router-dom'
import AnswerCard from '../components/AnswerCard'
import LoadingOverlay from '../components/LoadingOverlay'
import QueryInput, { type QueryInputValues } from '../components/QueryInput'
import ResultView from '../components/ResultView'
import { useExplain } from '../hooks/useExplain'
import { useQueryQuestion, toErrorMessage } from '../hooks/useQueryQuestion'
import type { ExplanationResponse, QueryResponse } from '../types'

export default function Explain() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const query = searchParams.get('q') ?? ''
  const language = searchParams.get('lang') ?? ''
  const topK = Number(searchParams.get('top_k') ?? 5)
  const mode = searchParams.get('mode') ?? 'full'

  const request = { query, language: language || undefined, top_k: Number.isFinite(topK) ? topK : 5 }
  const enabled = query.trim().length > 0

  const queryResult = useQueryQuestion(request, enabled && mode === 'full')
  const explainResult = useExplain(request, enabled && mode === 'explain')

  const isExplainOnly = mode === 'explain'

  const answerData = !isExplainOnly ? (queryResult.data as QueryResponse | undefined) : undefined
  const explainData = isExplainOnly ? (explainResult.data as ExplanationResponse | undefined) : undefined
  const active = isExplainOnly ? explainResult : queryResult
  const { isLoading, isError, error, refetch } = active
  const data = answerData ?? explainData

  const handleSubmit = (values: QueryInputValues) => {
    const params = new URLSearchParams()
    params.set('q', values.query)
    if (values.language) params.set('lang', values.language)
    params.set('top_k', String(values.topK))
    params.set('mode', mode)
    navigate(`/explain?${params.toString()}`, { replace: true })
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-8">
      <div className="mx-auto max-w-3xl">
        <QueryInput
          initialQuery={query}
          initialLanguage={language}
          initialTopK={topK}
          busy={isLoading}
          onSubmit={handleSubmit}
        />
        <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-slate-500 dark:text-slate-400">
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={isExplainOnly}
              onChange={(e) => {
                const params = new URLSearchParams(searchParams)
                if (e.target.checked) params.set('mode', 'explain')
                else params.delete('mode')
                navigate(`/explain?${params.toString()}`, { replace: true })
              }}
              className="h-4 w-4 accent-indigo-600"
            />
            Retrieval only (skip LLM)
          </label>
          {isExplainOnly && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">
              Explain mode — no answer generated
            </span>
          )}
        </div>
      </div>

      <AnimatePresence>{isLoading && <LoadingOverlay label="Retrieving and reasoning…" />}</AnimatePresence>

      {enabled && !isLoading && isError && (
        <div
          role="alert"
          className="mx-auto max-w-3xl rounded-2xl border border-red-200 bg-red-50 p-5 text-center dark:border-red-500/30 dark:bg-red-500/5"
        >
          <p className="text-sm font-semibold text-red-700 dark:text-red-300">Something went wrong</p>
          <p className="mt-1 text-sm text-red-600 dark:text-red-400">{toErrorMessage(error)}</p>
          <button
            type="button"
            onClick={() => refetch()}
            className="mt-3 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-500"
          >
            Retry
          </button>
        </div>
      )}

      {enabled && !isLoading && data && (
        <>
          {answerData && <AnswerCard result={answerData} />}
          {isExplainOnly && (
            <div className="mx-auto max-w-3xl rounded-2xl border border-amber-200 bg-amber-50 p-4 text-center text-sm text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
              Retrieval explanation generated without invoking the LLM (POST /explain).
            </div>
          )}
          <ResultView explanation={data} />
        </>
      )}

      {!enabled && (
        <p className="mx-auto max-w-3xl rounded-2xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
          Enter a legal question above to see a fully explained answer with evidence,
          hierarchy, knowledge graph, and provenance.
        </p>
      )}
    </div>
  )
}
