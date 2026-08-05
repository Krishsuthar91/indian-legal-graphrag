import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { sampleEvidence } from '../../test/fixtures'
import EvidencePanel from '../EvidencePanel'

describe('EvidencePanel', () => {
  it('renders evidence items with numbering and scores', () => {
    render(<EvidencePanel evidence={sampleEvidence} keywords={['murder']} />)
    expect(screen.getByText('302')).toBeInTheDocument()
    expect(screen.getByText('300')).toBeInTheDocument()
    expect(screen.getByText('70%')).toBeInTheDocument()
  })

  it('highlights matched keywords', () => {
    render(<EvidencePanel evidence={sampleEvidence} keywords={['murder']} />)
    expect(document.querySelectorAll('mark').length).toBeGreaterThan(0)
  })

  it('shows a placeholder when there is no evidence', () => {
    render(<EvidencePanel evidence={[]} keywords={[]} />)
    expect(screen.getByText(/no evidence retrieved/i)).toBeInTheDocument()
  })

  it('toggles expanded detail on click', async () => {
    const user = userEvent.setup()
    render(<EvidencePanel evidence={sampleEvidence} keywords={['murder']} />)

    expect(screen.getAllByText('Matched text')).toHaveLength(2)

    const header = screen.getByRole('button', { name: /punishment for murder/i })
    expect(header).toHaveAttribute('aria-expanded', 'true')

    await user.click(header)
    expect(header).toHaveAttribute('aria-expanded', 'false')

    await user.click(header)
    expect(header).toHaveAttribute('aria-expanded', 'true')
  })
})
