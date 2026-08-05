import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Validity } from '../../types'
import ValidityBadge from '../ValidityBadge'

const valid: Validity = {
  is_valid: true,
  supported: true,
  has_conflicts: false,
  cites_counter_authority: false,
  insufficient_evidence: false,
  reasons: ['answer supported by retrieved evidence'],
}

const invalid: Validity = {
  is_valid: false,
  supported: false,
  has_conflicts: true,
  cites_counter_authority: true,
  insufficient_evidence: true,
  reasons: ['insufficient evidence to support the answer'],
}

describe('ValidityBadge', () => {
  it('renders VALID for a supported answer', () => {
    render(<ValidityBadge validity={valid} />)
    expect(screen.getByText('VALID')).toBeInTheDocument()
    expect(screen.getByText(/answer supported by retrieved evidence/)).toBeInTheDocument()
  })

  it('renders INVALID with warning flags', () => {
    render(<ValidityBadge validity={invalid} />)
    expect(screen.getByText('INVALID')).toBeInTheDocument()
    expect(screen.getByText('Counter-authority')).toBeInTheDocument()
    expect(screen.getByText('Insufficient')).toBeInTheDocument()
  })
})
