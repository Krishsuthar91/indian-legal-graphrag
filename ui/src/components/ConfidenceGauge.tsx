import { PolarAngleAxis, RadialBar, RadialBarChart } from 'recharts'
import type { Confidence } from '../types'
import {
  confidenceColor,
  confidenceLabel,
  factorData,
  formatScore,
  resolveConfidence,
} from '../utils/format'

export default function ConfidenceGauge({ confidence }: { confidence: Confidence }) {
  const conf = resolveConfidence(confidence)
  const color = confidenceColor(conf.score)
  const label = conf.label || confidenceLabel(conf.score)
  const value = Math.round(conf.score * 100)
  const data = [{ name: 'confidence', value }]
  const factors = factorData(conf)

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative h-44 w-56">
        <RadialBarChart
          width={224}
          height={150}
          cx="50%"
          cy="92%"
          innerRadius={72}
          outerRadius={104}
          startAngle={200}
          endAngle={-20}
          data={data}
        >
          <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
          <RadialBar
            dataKey="value"
            angleAxisId={0}
            background={{ fill: 'rgba(148,163,184,0.25)' }}
            cornerRadius={8}
            fill={color}
          />
        </RadialBarChart>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center pb-1">
          <span className="text-3xl font-bold text-slate-800 dark:text-slate-100">{value}%</span>
          <span
            className="rounded-full px-2 py-0.5 text-xs font-semibold"
            style={{ color, backgroundColor: `${color}1a` }}
          >
            {label} confidence
          </span>
        </div>
      </div>
      {factors.length > 0 && (
        <div className="w-full space-y-1.5">
          {factors.map((f) => (
            <div key={f.key} className="flex items-center gap-2">
              <span className="w-32 shrink-0 text-xs text-slate-500 dark:text-slate-400">{f.label}</span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${Math.round(f.value * 100)}%`, backgroundColor: color }}
                />
              </div>
              <span className="w-12 shrink-0 text-right font-mono text-xs text-slate-600 dark:text-slate-300">
                {formatScore(f.value)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
