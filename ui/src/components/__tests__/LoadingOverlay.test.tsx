import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import LoadingOverlay from '../LoadingOverlay'

describe('LoadingOverlay', () => {
  it('renders the given label with a status role', () => {
    render(<LoadingOverlay label="Retrieving…" />)
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.getByText('Retrieving…')).toBeInTheDocument()
  })
})
