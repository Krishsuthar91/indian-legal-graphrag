import { motion } from 'framer-motion'
import type { ExplanationResponse } from '../types'
import CounterAuthorityCard from './CounterAuthorityCard'
import EvidencePanel from './EvidencePanel'
import HierarchyTree from './HierarchyTree'
import KnowledgeGraph from './KnowledgeGraph'
import ProvenancePanel from './ProvenancePanel'

interface ResultViewProps {
  explanation: ExplanationResponse
}

export default function ResultView({ explanation }: ResultViewProps) {
  const keywords = explanation.retrieval?.keywords ?? []
  return (
    <div className="space-y-5">
      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900"
      >
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Evidence
        </h2>
        <EvidencePanel evidence={explanation.evidence} keywords={keywords} />
      </motion.section>

      <div className="grid gap-5 xl:grid-cols-2">
        <motion.section
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900"
        >
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Document hierarchy
          </h2>
          <HierarchyTree paths={explanation.hierarchy_paths} />
        </motion.section>
        <motion.section
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900"
        >
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Knowledge graph
          </h2>
          <KnowledgeGraph
            evidence={explanation.evidence}
            paths={explanation.hierarchy_paths}
            counterAuthorities={explanation.counter_authorities}
          />
        </motion.section>
      </div>

      {explanation.counter_authorities.length > 0 && (
        <motion.section
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900"
        >
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Counter-authority warnings
          </h2>
          <CounterAuthorityCard authorities={explanation.counter_authorities} />
        </motion.section>
      )}

      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900"
      >
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Provenance
        </h2>
        <ProvenancePanel explanation={explanation} />
      </motion.section>
    </div>
  )
}
