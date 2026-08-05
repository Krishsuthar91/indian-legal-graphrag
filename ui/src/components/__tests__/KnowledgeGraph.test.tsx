import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { sampleEvidence, samplePaths } from '../../test/fixtures'
import KnowledgeGraph from '../KnowledgeGraph'

const { cyMock, cytoscapeMock } = vi.hoisted(() => {
  const cyMock = {
    on: vi.fn(),
    destroy: vi.fn(),
    layout: vi.fn(() => ({ run: vi.fn() })),
  }
  return { cyMock, cytoscapeMock: vi.fn((_options: unknown) => cyMock) }
})

vi.mock('cytoscape', () => ({ default: cytoscapeMock }))

describe('KnowledgeGraph', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('creates a cytoscape instance with the built elements', () => {
    render(
      <KnowledgeGraph
        evidence={sampleEvidence}
        paths={samplePaths}
        counterAuthorities={sampleExplanationCounterAuthorities()}
      />,
    )
    expect(cytoscapeMock).toHaveBeenCalledTimes(1)
    const options = cytoscapeMock.mock.calls[0][0] as unknown as {
      elements: { data: { id: string } }[]
    }
    expect(options.elements.map((e) => e.data.id)).toContain('sec-302')
    expect(cyMock.on).toHaveBeenCalled()
  })

  it('shows the counter-authority legend when flags are present', () => {
    render(
      <KnowledgeGraph
        evidence={sampleEvidence}
        paths={samplePaths}
        counterAuthorities={sampleExplanationCounterAuthorities()}
      />,
    )
    expect(screen.getAllByText(/counter-authorit/i).length).toBeGreaterThan(0)
  })
})

function sampleExplanationCounterAuthorities() {
  return [{ node_id: 'sec-302', title: 'Punishment for murder', reason: 'overruled', marker: 'overruled', evidence_text: 'x' }]
}
