import { motion } from 'framer-motion'
import { useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import AnswerCard from '../components/AnswerCard'
import LoadingOverlay from '../components/LoadingOverlay'
import ResultView from '../components/ResultView'
import { useProvenance } from '../hooks/useProvenance'
import { toErrorMessage } from '../hooks/useQueryQuestion'

export default function Provenance() {
  const params = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const routeId = params.id ?? searchParams.get('q') ?? ''
  const [input, setInput] = useState(routeId)

  const { data, isLoading, isError, error, refetch } = useProvenance(routeId)

  const handleLookup = () => {
    if (!input.trim()) return
    navigate(`/provenance/${encodeURIComponent(input.trim())}`)
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-8">
      <div className="mx-auto max-w-2xl">
        <h1 className="mb-1 text-2xl font-bold text-slate-900 dark:text-white">Provenance</h1>
        <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
          Retrieve a previously generated answer and its full evidence trail by its
          provenance id (e.g. the id shown on an answer card).
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            handleLookup()
          }}
          className="flex gap-2"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="provenance id"
            className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-white px-4 py-2.5 font-mono text-sm text-slate-800 outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:focus:ring-indigo-500/20"
          />
          <button
            type="submit"
            disabled={!input.trim()}
            className="rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Look up
          </button>
        </form>
      </div>

      {isLoading && <LoadingOverlay label="Loading provenance record…" />}

      {isError && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          role="alert"
          className="mx-auto max-w-2xl rounded-2xl border border-red-200 bg-red-50 p-5 text-center dark:border-red-500/30 dark:bg-red-500/5"
        >
          <p className="text-sm font-semibold text-red-700 dark:text-red-300">Failed to load provenance</p>
          <p className="mt-1 text-sm text-red-600 dark:text-red-400">{toErrorMessage(error)}</p>
          <button
            type="button"
            onClick={() => refetch()}
            className="mt-3 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-500"
          >
            Retry
          </button>
        </motion.div>
      )}

      {!isLoading && data && !isError && (
        <div className="space-y-5">
          <AnswerCard result={data} />
          <ResultView explanation={data} />
        </div>
      )}

      {!isLoading && !routeId && (
        <p className="mx-auto max-w-2xl rounded-2xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
          Enter a provenance id above to inspect a stored answer and its full retrieval
          evidence trail.
        </p>
      )}
    </div>
  )
}
