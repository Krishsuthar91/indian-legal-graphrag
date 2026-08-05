import { AnimatePresence, motion } from 'framer-motion'
import { useState } from 'react'
import type { Evidence } from '../types'
import { confidenceColor, formatScore } from '../utils/format'
import HighlightText from './HighlightText'
import ScoreBar from './ScoreBar'

interface EvidencePanelProps {
  evidence: Evidence[]
  keywords: string[]
}

export default function EvidencePanel({ evidence, keywords }: EvidencePanelProps) {
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(evidence.slice(0, 2).map((e) => e.node_id)))
  const [showFull, setShowFull] = useState<Set<string>>(new Set())

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  if (evidence.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
        No evidence retrieved for this query.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      {evidence.map((ev) => {
        const isOpen = expanded.has(ev.node_id)
        const full = showFull.has(ev.node_id)
        const color = confidenceColor(ev.final_score)
        return (
          <div
            key={ev.node_id}
            className="overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900"
          >
            <button
              type="button"
              onClick={() => toggle(ev.node_id)}
              className="flex w-full items-center gap-3 px-4 py-3 text-left"
              aria-expanded={isOpen}
            >
              <span className="shrink-0 rounded bg-indigo-100 px-2 py-0.5 font-mono text-xs font-semibold text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-300">
                {ev.numbering || ev.node_id}
              </span>
              <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-800 dark:text-slate-100">
                {ev.title || ev.label}
              </span>
              <span className="shrink-0 font-mono text-xs" style={{ color }}>
                {formatScore(ev.final_score)}
              </span>
              <span className="shrink-0 text-slate-400">{isOpen ? '▾' : '▸'}</span>
            </button>
            <AnimatePresence initial={false}>
              {isOpen && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.18 }}
                  className="border-t border-slate-100 px-4 py-3 dark:border-slate-800"
                >
                  <div className="mb-3 space-y-1.5">
                    <ScoreBar label="Dense" value={ev.dense_score} />
                    <ScoreBar label="Graph" value={ev.graph_score} />
                    <ScoreBar label="Hierarchy" value={ev.hierarchy_score} />
                  </div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                    Matched text
                  </p>
                  <p className="mt-1 text-[13px] leading-relaxed text-slate-700 dark:text-slate-200">
                    <HighlightText
                      text={full ? ev.text : ev.snippet}
                      keywords={keywords}
                    />
                  </p>
                  {!full && ev.text.length > ev.snippet.length && (
                    <button
                      type="button"
                      onClick={() =>
                        setShowFull((prev) => {
                          const next = new Set(prev)
                          next.add(ev.node_id)
                          return next
                        })
                      }
                      className="mt-1 text-xs font-medium text-indigo-600 hover:underline dark:text-indigo-400"
                    >
                      Show full text
                    </button>
                  )}
                  <div className="mt-3 flex flex-wrap gap-1.5 text-[11px]">
                    {ev.sources.map((s) => (
                      <span
                        key={s}
                        className="rounded-full bg-emerald-100 px-2 py-0.5 font-medium text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300"
                      >
                        {s}
                      </span>
                    ))}
                    {ev.language && (
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                        lang: {ev.language}
                      </span>
                    )}
                    {ev.path.length > 1 && (
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 font-mono text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                        {ev.path.length} levels deep
                      </span>
                    )}
                  </div>
                  {ev.path.length > 1 && (
                    <p className="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
                      Path: {ev.path.join(' / ')}
                    </p>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )
      })}
    </div>
  )
}
