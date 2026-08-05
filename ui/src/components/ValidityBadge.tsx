import type { Validity } from '../types'

export default function ValidityBadge({ validity }: { validity: Validity }) {
  const tone = validity.is_valid ? 'valid' : validity.cites_counter_authority ? 'counter' : validity.has_conflicts ? 'conflict' : 'invalid'
  const styles: Record<string, string> = {
    valid: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300',
    counter: 'bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300',
    conflict: 'bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300',
    invalid: 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-300',
  }
  const flags: [string, boolean][] = [
    ['Supported', validity.supported],
    ['Conflicts', validity.has_conflicts],
    ['Counter-authority', validity.cites_counter_authority],
    ['Insufficient', validity.insufficient_evidence],
  ]
  return (
    <div className="space-y-2">
      <span
        className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${styles[tone]}`}
      >
        <span
          className={`h-2 w-2 rounded-full ${
            validity.is_valid ? 'bg-emerald-500' : 'bg-red-500'
          }`}
        />
        {validity.is_valid ? 'VALID' : 'INVALID'}
      </span>
      <div className="flex flex-wrap gap-1.5">
        {flags.map(([label, active]) => (
          <span
            key={label}
            className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-[11px] ${
              active
                ? 'border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200'
                : 'border-transparent text-slate-400 dark:text-slate-600'
            }`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${active ? 'bg-current' : 'bg-slate-300 dark:bg-slate-700'}`} />
            {label}
          </span>
        ))}
      </div>
      {validity.reasons.length > 0 && (
        <ul className="list-inside list-disc space-y-0.5 text-xs text-slate-500 dark:text-slate-400">
          {validity.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
