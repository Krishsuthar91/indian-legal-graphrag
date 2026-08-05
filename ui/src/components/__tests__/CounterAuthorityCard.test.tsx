import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { sampleExplanation } from '../../test/fixtures'
import CounterAuthorityCard from '../CounterAuthorityCard'

describe('CounterAuthorityCard', () => {
  it('lists detected counter-authorities with reason and marker', () => {
    render(<CounterAuthorityCard authorities={sampleExplanation.counter_authorities} />)
    expect(screen.getByText('overruled')).toBeInTheDocument()
    expect(screen.getByText(/overruled by a later authority/)).toBeInTheDocument()
    expect(screen.getByText('Punishment for murder')).toBeInTheDocument()
  })

  it('confirms absence of warnings', () => {
    render(<CounterAuthorityCard authorities={[]} />)
    expect(screen.getByText(/no counter-authorities detected/i)).toBeInTheDocument()
  })
})
