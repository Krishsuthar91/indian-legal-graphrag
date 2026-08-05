import { useState } from 'react'
import type { Evidence, ExplanationResponse, ReasoningStep } from '../types'
import { formatNumber } from '../utils/format'
import ScoreBar from './ScoreBar'

const KIND_COLORS: Record<string, string> = {
  query_parse: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200',
  dense: 'bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300',
  graph: 'bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300',
  hierarchy: 'bg-teal-100 text-teal-700 dark:bg-teal-500/15 dark:text-teal-300',
  fusion: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300',
  verification: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
}

function ReasoningStepRow({ step }: { step: ReasoningStep }) {
  const [open, setOpen] = useState(false)
  const hasIds = step.node_ids.length > 0
  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">
          {step.step}
        </span>
        <span className="mt-1 w-px flex-1 bg-slate-200 dark:bg-slate-700" />
      </div>
      <div className="min-w-0 flex-1 pb-4">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`rounded-full px-2 py-0.5 font-mono text-[11px] font-semibold ${
              KIND_COLORS[step.kind] ?? 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200'
            }`}
          >
            {step.kind}
          </span>
          <p className="text-xs text-slate-700 dark:text-slate-200">{step.description}</p>
          {hasIds && (
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              className="text-[11px] font-medium text-indigo-600 hover:underline dark:text-indigo-400"
            >
              {step.node_ids.length} node(s) {open ? '▾' : '▸'}
            </button>
          )}
        </div>
        {hasIds && open && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {step.node_ids.map((id) => (
              <span
                key={id}
                className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-600 dark:bg-slate-800 dark:text-slate-300"
              >
                {id}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function ScoreBreakdown({ evidence, weights }: { evidence: Evidence[]; weights: Record<string, number> }) {
  const weightEntries = Object.entries(weights ?? {})
  return (
    <div className="space-y-3">
      {weightEntries.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Retrieval weights</span>
          {weightEntries.map(([key, value]) => (
            <span
              key={key}
              className="rounded-full bg-indigo-100 px-2 py-0.5 font-mono text-[11px] text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300"
            >
              {key} = {Number(value).toFixed(2)}
            </span>
          ))}
        </div>
      )}
      {evidence.map((ev) => (
        <div key={ev.node_id} className="rounded-lg border border-slate-100 p-3 dark:border-slate-800">
          <div className="mb-2 flex items-center gap-2">
            <span className="truncate text-xs font-medium text-slate-700 dark:text-slate-200">
              {ev.numbering || ev.node_id} · {ev.title}
            </span>
            <span className="ml-auto shrink-0 font-mono text-xs text-indigo-600 dark:text-indigo-400">
              {formatNumber(ev.final_score * 100)}%
            </span>
          </div>
          <div className="space-y-1">
            <ScoreBar label="Dense" value={ev.dense_score} color="#0ea5e9" />
            <ScoreBar label="Graph" value={ev.graph_score} color="#8b5cf6" />
            <ScoreBar label="Hierarchy" value={ev.hierarchy_score} color="#14b8a6" />
            <ScoreBar label="Final" value={ev.final_score} />
          </div>
        </div>
      ))}
    </div>
  )
}

export default function ProvenancePanel({ explanation }: { explanation: ExplanationResponse }) {
  const retrieval = explanation.retrieval
  const summary: [string, number][] = [
    ['Dense hits', retrieval.dense_hits],
    ['Graph hits', retrieval.graph_hits],
    ['Hierarchy propagated', retrieval.hierarchy_propagated],
    ['Candidates', retrieval.candidates],
    ['Returned', retrieval.returned],
  ]

  return (
    <div className="space-y-6">
      <section>
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Retrieval path
        </h3>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          {summary.map(([label, value]) => (
            <div
              key={label}
              className="rounded-lg border border-slate-100 bg-slate-50 p-2 text-center dark:border-slate-800 dark:bg-slate-800/50"
            >
              <p className="text-lg font-bold text-slate-800 dark:text-slate-100">{formatNumber(value)}</p>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">{label}</p>
            </div>
          ))}
        </div>
        <div className="mt-3 space-y-0">
          {explanation.reasoning_chain.map((step) => (
            <ReasoningStepRow key={step.step} step={step} />
          ))}
        </div>
      </section>
      <section>
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Hybrid score breakdown
        </h3>
        <ScoreBreakdown evidence={explanation.evidence} weights={explanation.retrieval_weights} />
      </section>
    </div>
  )
}
