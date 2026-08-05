import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import Home from '../Home'

describe('Home', () => {
  it('renders the hero and a query input', () => {
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Ask about any Indian legal provision/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /ask question/i })).toBeInTheDocument()
  })

  it('shows no recent questions section initially', () => {
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    )
    expect(screen.queryByText(/recent questions/i)).not.toBeInTheDocument()
  })
})
