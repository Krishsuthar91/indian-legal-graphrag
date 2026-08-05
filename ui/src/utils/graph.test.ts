import { sampleEvidence, samplePaths } from '../test/fixtures'
import { buildCytoscapeElements, buildHierarchyLayout, pruneLayout } from './graph'

describe('buildHierarchyLayout', () => {
  it('builds nodes and parent edges from hierarchy paths', () => {
    const layout = buildHierarchyLayout(samplePaths)
    expect(layout.nodes.map((n) => n.id).sort()).toEqual(['ch-18', 'ipc', 'sec-300', 'sec-302'])
    expect(layout.edges).toHaveLength(3)
    expect(layout.rootIds).toEqual(['ipc'])
    expect(layout.nodes.find((n) => n.id === 'ipc')?.children).toContain('ch-18')
  })

  it('assigns deterministic coordinates with the root on the left', () => {
    const layout = buildHierarchyLayout(samplePaths)
    const ipc = layout.nodes.find((n) => n.id === 'ipc')!
    const ch18 = layout.nodes.find((n) => n.id === 'ch-18')!
    const sec302 = layout.nodes.find((n) => n.id === 'sec-302')!
    expect(sec302.x).toBeGreaterThan(ch18.x)
    expect(ch18.x).toBeGreaterThan(ipc.x)
  })
})

describe('pruneLayout', () => {
  it('hides descendants of collapsed nodes but keeps the collapsed node', () => {
    const layout = buildHierarchyLayout(samplePaths)
    const pruned = pruneLayout(layout, new Set(['ch-18']))
    expect(pruned.nodes.map((n) => n.id).sort()).toEqual(['ch-18', 'ipc'])
    expect(pruned.edges.map((e) => e.id)).toEqual(['ipc->ch-18'])
  })

  it('keeps everything when nothing is collapsed', () => {
    const layout = buildHierarchyLayout(samplePaths)
    expect(pruneLayout(layout, new Set()).nodes).toHaveLength(layout.nodes.length)
  })
})

describe('buildCytoscapeElements', () => {
  it('creates nodes for evidence and hierarchy, plus parent edges', () => {
    const elements = buildCytoscapeElements(sampleEvidence, samplePaths, new Set())
    const nodes = elements.filter((e) => 'position' in e || 'data' in e && !('source' in e.data))
    const nodeIds = nodes.map((n) => (n as { data: { id: string } }).data.id)
    expect(nodeIds).toContain('sec-302')
    expect(nodeIds).toContain('ipc')
    const edgeCount = elements.filter((e) => 'source' in e.data).length
    expect(edgeCount).toBeGreaterThan(0)
  })

  it('adds dashed counter-authority edges for flagged nodes', () => {
    const elements = buildCytoscapeElements(sampleEvidence, samplePaths, new Set(['sec-302']))
    const counterEdges = elements.filter(
      (e) => 'source' in e.data && e.data.kind === 'counter',
    )
    expect(counterEdges.length).toBeGreaterThan(0)
  })
})
