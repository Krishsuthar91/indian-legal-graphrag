import type { Evidence, HierarchyPath } from '../types'

export interface TreeLayoutNode {
  id: string
  label: string
  title: string
  numbering: string
  level: number
  x: number
  y: number
  children: string[]
  parent?: string
}

export interface TreeLayout {
  nodes: TreeLayoutNode[]
  edges: { id: string; source: string; target: string }[]
  rootIds: string[]
}

const NODE_X = 260
const NODE_Y = 110

export function pruneLayout(
  layout: TreeLayout,
  collapsed: ReadonlySet<string>,
): { nodes: TreeLayoutNode[]; edges: TreeLayout['edges'] } {
  const nodeMap = new Map(layout.nodes.map((n) => [n.id, n]))

  const hasCollapsedAncestor = (id: string): boolean => {
    let cur = nodeMap.get(id)?.parent
    while (cur) {
      if (collapsed.has(cur)) return true
      cur = nodeMap.get(cur)?.parent
    }
    return false
  }

  const nodes = layout.nodes.filter((n) => !hasCollapsedAncestor(n.id))
  const visible = new Set(nodes.map((n) => n.id))
  const edges = layout.edges.filter(
    (e) => visible.has(e.source) && visible.has(e.target),
  )
  return { nodes, edges }
}

export function buildHierarchyLayout(paths: HierarchyPath[]): TreeLayout {
  const nodeMap = new Map<string, TreeLayoutNode>()
  const edges = new Map<string, { id: string; source: string; target: string }>()

  for (const path of paths) {
    for (let i = 0; i < path.entries.length; i++) {
      const entry = path.entries[i]
      if (!nodeMap.has(entry.node_id)) {
        nodeMap.set(entry.node_id, {
          id: entry.node_id,
          label: entry.label,
          title: entry.title,
          numbering: entry.numbering,
          level: entry.level,
          x: 0,
          y: 0,
          children: [],
        })
      }
      if (i > 0) {
        const parent = path.entries[i - 1].node_id
        const node = nodeMap.get(entry.node_id)
        if (node && node.parent === undefined) {
          node.parent = parent
          nodeMap.get(parent)?.children.push(entry.node_id)
        }
        const edgeId = `${parent}->${entry.node_id}`
        if (!edges.has(edgeId)) {
          edges.set(edgeId, { id: edgeId, source: parent, target: entry.node_id })
        }
      }
    }
  }

  const rootIds = [...nodeMap.values()].filter((n) => n.parent === undefined).map((n) => n.id)

  const depthOf = new Map<string, number>()
  const assignDepth = (id: string, depth: number): void => {
    depthOf.set(id, depth)
    for (const child of nodeMap.get(id)!.children) {
      assignDepth(child, depth + 1)
    }
  }
  for (const root of rootIds) {
    assignDepth(root, 0)
  }

  const columns: string[][] = []
  for (const node of nodeMap.values()) {
    const col = depthOf.get(node.id) ?? 0
    if (!columns[col]) columns[col] = []
    columns[col].push(node.id)
  }

  for (let col = 0; col < columns.length; col++) {
    const colNodes = columns[col] ?? []
    colNodes.forEach((id, i) => {
      const node = nodeMap.get(id)!
      node.x = col * NODE_X
      node.y = i * NODE_Y
    })
  }

  const nodes = [...nodeMap.values()]
  const edgeList = [...edges.values()]
  return { nodes, edges: edgeList, rootIds }
}

export interface CytoscapeElementData {
  id: string
  label: string
  type: string
  numbering: string
  level: number
  score: number
}

export type CytoscapeElement =
  | { data: CytoscapeElementData }
  | { data: { id: string; source: string; target: string; kind: string } }

export function buildCytoscapeElements(
  evidence: Evidence[],
  paths: HierarchyPath[],
  counterIds: Set<string>,
): CytoscapeElement[] {
  const elements: CytoscapeElement[] = []
  const seenNodes = new Set<string>()
  const seenEdges = new Set<string>()

  const nodeType = (label: string, level: number): string => {
    const l = label.toLowerCase()
    if (l.includes('case') || l.includes('air') || l.includes('judgment')) return 'case'
    if (l.includes('act') || l.includes('statute') || l.includes('rule') || l.includes('code')) return 'statute'
    if (l.includes('section') || l.includes('rule')) return 'section'
    if (l.includes('clause') || l.includes('sub')) return 'clause'
    return level <= 1 ? 'statute' : level === 2 ? 'section' : 'clause'
  }

  for (const ev of evidence) {
    const type = nodeType(ev.label, ev.level)
    elements.push({
      data: {
        id: ev.node_id,
        label: ev.numbering || ev.title || ev.node_id,
        type,
        numbering: ev.numbering,
        level: ev.level,
        score: ev.final_score,
      },
    })
    seenNodes.add(ev.node_id)
  }

  for (const path of paths) {
    for (let i = 0; i < path.entries.length - 1; i++) {
      const a = path.entries[i]
      const b = path.entries[i + 1]
      const edgeId = `parent:${a.node_id}->${b.node_id}`
      if (seenEdges.has(edgeId)) continue
      seenEdges.add(edgeId)
      elements.push({ data: { id: edgeId, source: a.node_id, target: b.node_id, kind: 'parent' } })
      if (!seenNodes.has(a.node_id)) {
        seenNodes.add(a.node_id)
        elements.push({
          data: {
            id: a.node_id,
            label: a.numbering || a.title || a.node_id,
            type: nodeType(a.label, a.level),
            numbering: a.numbering,
            level: a.level,
            score: 0,
          },
        })
      }
    }
  }

  for (const id of counterIds) {
    if (!seenNodes.has(id)) continue
    for (const ev of evidence) {
      const edgeId = `counter:${ev.node_id}->${id}`
      if (seenEdges.has(edgeId)) continue
      if (ev.node_id === id) continue
      seenEdges.add(edgeId)
      elements.push({ data: { id: edgeId, source: ev.node_id, target: id, kind: 'counter' } })
    }
  }

  return elements
}
