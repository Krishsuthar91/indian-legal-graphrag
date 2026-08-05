import { confidenceColor, formatScore } from '../utils/format'

interface ScoreBarProps {
  label: string
  value: number
  color?: string
}

export default function ScoreBar({ label, value, color }: ScoreBarProps) {
  const pct = Math.max(0, Math.min(100, value * 100))
  return (
    <div className="flex items-center gap-2" title={`${label}: ${formatScore(value)}`}>
      <span className="w-20 shrink-0 text-xs text-slate-500 dark:text-slate-400">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: color ?? confidenceColor(value) }}
        />
      </div>
      <span className="w-12 shrink-0 text-right font-mono text-xs text-slate-600 dark:text-slate-300">
        {formatScore(value)}
      </span>
    </div>
  )
}
