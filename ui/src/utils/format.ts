import type { Confidence } from '../types'

export function formatScore(score: number): string {
  if (!Number.isFinite(score)) return '0%'
  return `${Math.round(score * 100)}%`
}

export function formatDuration(ms: number): string {
  if (!Number.isFinite(ms)) return '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  return `${(ms / 1000).toFixed(2)} s`
}

export function formatNumber(n: number): string {
  return Number.isFinite(n) ? n.toLocaleString() : '0'
}

export function confidenceColor(score: number): string {
  if (score >= 0.7) return '#10b981'
  if (score >= 0.45) return '#f59e0b'
  return '#ef4444'
}

export function confidenceLabel(score: number): string {
  if (score >= 0.7) return 'high'
  if (score >= 0.45) return 'medium'
  return 'low'
}

export function resolveConfidence(confidence: Confidence | undefined): Confidence {
  if (confidence && Number.isFinite(confidence.score)) {
    return { score: confidence.score, label: confidence.label, factors: confidence.factors }
  }
  return { score: 0, label: 'low', factors: {} }
}

export interface FactorDatum {
  key: string
  label: string
  value: number
}

const FACTOR_LABELS: Record<string, string> = {
  base_score: 'Retrieval base',
  keyword_coverage: 'Keyword coverage',
  sufficiency: 'Evidence sufficiency',
  citation_bonus: 'Citation bonus',
}

export function factorData(confidence: Confidence): FactorDatum[] {
  return Object.entries(confidence.factors)
    .map(([key, value]) => {
      const num = typeof value === 'number' ? value : 0
      return {
        key,
        label: FACTOR_LABELS[key] ?? key.replace(/_/g, ' '),
        value: Number.isFinite(num) ? num : 0,
      }
    })
    .filter((d) => ['base_score', 'keyword_coverage', 'sufficiency', 'citation_bonus'].includes(d.key))
}
