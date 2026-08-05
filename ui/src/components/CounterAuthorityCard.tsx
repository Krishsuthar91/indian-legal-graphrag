import type { CounterAuthority } from '../types'

interface CounterAuthorityCardProps {
  authorities: CounterAuthority[]
}

export default function CounterAuthorityCard({ authorities }: CounterAuthorityCardProps) {
  if (authorities.length === 0) {
    return (
      <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 dark:border-emerald-500/30 dark:bg-emerald-500/5">
        <p className="text-sm text-emerald-800 dark:text-emerald-300">
          No counter-authorities detected in the retrieved evidence.
        </p>
      </div>
    )
  }
  return (
    <div className="space-y-3">
      <p className="text-sm font-medium text-red-700 dark:text-red-300">
        {authorities.length} counter-authorit{authorities.length === 1 ? 'y' : 'ies'} detected
      </p>
      {authorities.map((ca) => (
        <div
          key={`${ca.node_id}-${ca.marker}`}
          className="rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-500/30 dark:bg-red-500/5"
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-red-500 px-2 py-0.5 font-mono text-[11px] font-semibold text-white">
              {ca.marker}
            </span>
            <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">{ca.title}</span>
          </div>
          <p className="mt-1.5 text-xs text-slate-600 dark:text-slate-300">{ca.reason}</p>
          {ca.evidence_text && (
            <p className="mt-2 rounded bg-white/60 p-2 text-xs italic text-slate-600 dark:bg-slate-900/40 dark:text-slate-300">
              “{ca.evidence_text}”
            </p>
          )}
        </div>
      ))}
    </div>
  )
}
