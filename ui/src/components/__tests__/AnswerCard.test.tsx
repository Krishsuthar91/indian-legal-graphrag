import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { sampleQueryResponse } from '../../test/fixtures'
import AnswerCard from '../AnswerCard'

describe('AnswerCard', () => {
  it('renders answer, model, duration and confidence', () => {
    render(
      <MemoryRouter>
        <AnswerCard result={sampleQueryResponse} />
      </MemoryRouter>,
    )
    expect(screen.getByText(/Section 302 IPC provides/i)).toBeInTheDocument()
    expect(screen.getByText('mock-llm')).toBeInTheDocument()
    expect(screen.getByText('245 ms')).toBeInTheDocument()
    expect(screen.getByText(/68% confident/)).toBeInTheDocument()
  })

  it('links to the provenance page with the provenance id', () => {
    render(
      <MemoryRouter>
        <AnswerCard result={sampleQueryResponse} />
      </MemoryRouter>,
    )
    const link = screen.getByRole('link', { name: /prov-abc-123/i })
    expect(link).toHaveAttribute('href', '/provenance/prov-abc-123')
  })

  it('lists sources from citations', () => {
    render(
      <MemoryRouter>
        <AnswerCard result={sampleQueryResponse} />
      </MemoryRouter>,
    )
    expect(screen.getByText(/Section 302, "Punishment for murder"/)).toBeInTheDocument()
  })
})
