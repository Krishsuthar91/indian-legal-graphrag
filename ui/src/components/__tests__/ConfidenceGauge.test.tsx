import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { sampleExplanation } from '../../test/fixtures'
import ConfidenceGauge from '../ConfidenceGauge'

describe('ConfidenceGauge', () => {
  it('renders the score percentage and label', () => {
    render(<ConfidenceGauge confidence={sampleExplanation.confidence} />)
    expect(screen.getByText('68%')).toBeInTheDocument()
    expect(screen.getByText(/medium confidence/)).toBeInTheDocument()
  })

  it('renders factor breakdown bars', () => {
    render(<ConfidenceGauge confidence={sampleExplanation.confidence} />)
    expect(screen.getByText('Retrieval base')).toBeInTheDocument()
    expect(screen.getByText('Keyword coverage')).toBeInTheDocument()
  })

  it('handles an empty confidence object', () => {
    render(<ConfidenceGauge confidence={{ score: 0, label: 'low', factors: {} }} />)
    expect(screen.getByText('0%')).toBeInTheDocument()
  })
})
