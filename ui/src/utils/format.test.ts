import {
  confidenceColor,
  confidenceLabel,
  factorData,
  formatDuration,
  formatNumber,
  formatScore,
  resolveConfidence,
} from './format'

describe('formatScore', () => {
  it('renders fractions as percentages', () => {
    expect(formatScore(0.5)).toBe('50%')
    expect(formatScore(1)).toBe('100%')
    expect(formatScore(0)).toBe('0%')
  })
  it('handles non-finite input', () => {
    expect(formatScore(Number.NaN)).toBe('0%')
    expect(formatScore(Number.POSITIVE_INFINITY)).toBe('0%')
  })
})

describe('formatDuration', () => {
  it('renders milliseconds under one second', () => {
    expect(formatDuration(245)).toBe('245 ms')
  })
  it('renders seconds above one second', () => {
    expect(formatDuration(1500)).toBe('1.50 s')
  })
})

describe('formatNumber', () => {
  it('formats with locale separators', () => {
    expect(formatNumber(1200)).toBe('1,200')
  })
})

describe('confidence helpers', () => {
  it('maps scores to colors and labels', () => {
    expect(confidenceColor(0.8)).toBe('#10b981')
    expect(confidenceColor(0.5)).toBe('#f59e0b')
    expect(confidenceColor(0.2)).toBe('#ef4444')
    expect(confidenceLabel(0.8)).toBe('high')
    expect(confidenceLabel(0.5)).toBe('medium')
    expect(confidenceLabel(0.2)).toBe('low')
  })
  it('resolves undefined confidence to zero', () => {
    expect(resolveConfidence(undefined)).toEqual({ score: 0, label: 'low', factors: {} })
  })
})

describe('factorData', () => {
  it('extracts and labels the numeric confidence factors', () => {
    const factors = factorData({
      score: 0.68,
      label: 'medium',
      factors: {
        base_score: 0.7,
        keyword_coverage: 0.66,
        sufficiency: 1,
        citation_bonus: 0.1,
        n_evidence: 2,
      },
    })
    expect(factors).toHaveLength(4)
    expect(factors.find((f) => f.key === 'base_score')?.label).toBe('Retrieval base')
    expect(factors.find((f) => f.key === 'citation_bonus')?.value).toBe(0.1)
  })
})
