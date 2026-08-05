import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import type { QueryResponse } from '../types'
import { confidenceColor, formatDuration } from '../utils/format'
import ConfidenceGauge from './ConfidenceGauge'
import ValidityBadge from './ValidityBadge'

interface AnswerCardProps {
  result: QueryResponse
}

export default function AnswerCard({ result }: AnswerCardProps) {
  const color = confidenceColor(result.confidence?.score ?? 0)
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900"
    >
      <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 px-5 py-3 dark:border-slate-800">
        <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Answer</h2>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 font-mono text-[11px] text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          {result.model}
        </span>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 font-mono text-[11px] text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          {formatDuration(result.duration_ms)}
        </span>
        <span
          className="rounded-full px-2 py-0.5 text-[11px] font-semibold"
          style={{ color, backgroundColor: `${color}1a` }}
        >
          {Math.round((result.confidence?.score ?? 0) * 100)}% confident
        </span>
        <Link
          to={`/provenance/${encodeURIComponent(result.provenance_id)}`}
          className="ml-auto font-mono text-[11px] text-indigo-600 hover:underline dark:text-indigo-400"
        >
          provenance: {result.provenance_id}
        </Link>
      </div>
      <div className="grid gap-6 p-5 lg:grid-cols-[1fr_260px]">
        <div className="space-y-4">
          <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-slate-800 dark:text-slate-100">
            {result.answer}
          </p>
          {result.citations.length > 0 && (
            <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800/50">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Sources
              </p>
              <ul className="space-y-1">
                {result.citations.map((c) => (
                  <li key={c.index} className="text-xs text-slate-600 dark:text-slate-300">
                    <span className="mr-1 inline-flex h-4 w-4 items-center justify-center rounded-full bg-indigo-100 font-mono text-[10px] font-bold text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-300">
                      {c.index}
                    </span>
                    {c.citation_text}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <aside className="space-y-4 border-t border-slate-100 pt-4 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0 dark:border-slate-800">
          <ConfidenceGauge confidence={result.confidence} />
          <ValidityBadge validity={result.validity} />
        </aside>
      </div>
    </motion.div>
  )
}
