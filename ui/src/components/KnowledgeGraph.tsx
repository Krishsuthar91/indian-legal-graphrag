import cytoscape, {
  type Core,
  type EdgeSingular,
  type NodeSingular,
} from 'cytoscape'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { CounterAuthority, Evidence, HierarchyPath } from '../types'
import { formatScore } from '../utils/format'
import { buildCytoscapeElements } from '../utils/graph'

interface KnowledgeGraphProps {
  evidence: Evidence[]
  paths: HierarchyPath[]
  counterAuthorities: CounterAuthority[]
}

interface Tooltip {
  x: number
  y: number
  title: string
  subtitle: string
  lines: string[]
}

const NODE_COLORS: Record<string, string> = {
  statute: '#8b5cf6',
  section: '#3b82f6',
  clause: '#14b8a6',
  case: '#f59e0b',
}

const SHAPES: Record<string, string> = {
  statute: 'hexagon',
  section: 'ellipse',
  clause: 'round-rectangle',
  case: 'rectangle',
}

export default function KnowledgeGraph({
  evidence,
  paths,
  counterAuthorities,
}: KnowledgeGraphProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const cyRef = useRef<Core | null>(null)
  const [tooltip, setTooltip] = useState<Tooltip | null>(null)
  const [relayout, setRelayout] = useState(0)

  const counterIds = useMemo(
    () => new Set(counterAuthorities.map((c) => c.node_id)),
    [counterAuthorities],
  )

  const elements = useMemo(
    () => buildCytoscapeElements(evidence, paths, counterIds),
    [evidence, paths, counterIds],
  )

  useEffect(() => {
    if (!containerRef.current) return
    const stylesheet = [
      {
        selector: 'node',
        style: {
          label: 'data(label)',
          'font-size': 10,
          'text-valign': 'center',
          'text-halign': 'center',
          'text-wrap': 'wrap',
          'text-max-width': 120,
          color: '#1e293b',
          width: 'mapData(score, 0, 1, 40, 80)',
          height: 'mapData(score, 0, 1, 40, 80)',
          'background-color': (ele: NodeSingular) =>
            NODE_COLORS[String(ele.data('type'))] ?? '#64748b',
          'border-color': '#0f172a',
          'border-width': 1.5,
          'border-opacity': 0.35,
          shape: (ele: NodeSingular) => SHAPES[String(ele.data('type'))] ?? 'ellipse',
          'overlay-opacity': 0,
        },
      },
      {
        selector: 'edge',
        style: {
          width: 1.5,
          'curve-style': 'bezier',
          'target-arrow-shape': 'triangle',
          'target-arrow-color': (ele: EdgeSingular) =>
            ele.data('kind') === 'counter' ? '#ef4444' : '#94a3b8',
          'line-color': (ele: EdgeSingular) =>
            ele.data('kind') === 'counter' ? '#ef4444' : '#94a3b8',
          'line-style': (ele: EdgeSingular) =>
            ele.data('kind') === 'counter' ? 'dashed' : 'solid',
          'arrow-scale': 0.7,
        },
      },
    ] as unknown as cytoscape.StylesheetStyle[]

    const cy = cytoscape({
      container: containerRef.current,
      elements: elements as cytoscape.ElementDefinition[],
      minZoom: 0.2,
      maxZoom: 2.5,
      wheelSensitivity: 0.2,
      style: stylesheet,
      layout: { name: 'cose', animate: false, padding: 30 },
    })

    cyRef.current = cy
    cy.on('mouseover', 'node', (evt) => {
      const node = evt.target
      const pos = evt.renderedPosition
      const score = Number(node.data('score') ?? 0)
      setTooltip({
        x: pos.x,
        y: pos.y,
        title: String(node.data('numbering') || node.data('label') || node.data('id')),
        subtitle: String(node.data('type')),
        lines: score > 0 ? [`Score: ${formatScore(score)}`] : ['Retrieval context node'],
      })
    })
    cy.on('mouseout', 'node', () => setTooltip(null))

    return () => {
      cy.destroy()
      cyRef.current = null
    }
  }, [elements])

  useEffect(() => {
    if (relayout === 0 || !cyRef.current) return
    const layout = cyRef.current.layout({ name: 'cose', animate: true, padding: 30 })
    layout.run()
  }, [relayout])

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-500 dark:text-slate-400">
        <span>
          {evidence.length} evidence node{evidence.length === 1 ? '' : 's'}
          {counterAuthorities.length > 0 && (
            <span className="ml-1 font-medium text-red-500">
              · {counterAuthorities.length} counter-authorit{counterAuthorities.length === 1 ? 'y' : 'ies'}
            </span>
          )}
        </span>
        <button
          type="button"
          onClick={() => setRelayout((v) => v + 1)}
          className="rounded border border-slate-300 px-2 py-0.5 hover:bg-slate-100 dark:border-slate-600 dark:hover:bg-slate-800"
        >
          Re-layout
        </button>
        <span className="ml-auto hidden sm:inline">Scroll to zoom · drag to pan · hover for details</span>
      </div>
      <div className="relative h-[420px] w-full overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700">
        <div ref={containerRef} className="h-full w-full" />
        <div className="pointer-events-none absolute bottom-2 left-2 flex flex-col gap-1 rounded-lg bg-white/90 p-2 text-[10px] shadow dark:bg-slate-900/90">
          {Object.entries(NODE_COLORS).map(([type, color]) => (
            <span key={type} className="flex items-center gap-1.5 text-slate-600 dark:text-slate-300">
              <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: color }} />
              {type}
            </span>
          ))}
          <span className="flex items-center gap-1.5 text-slate-600 dark:text-slate-300">
            <span className="h-0.5 w-4 border-t border-dashed border-red-500" />
            counter-authority
          </span>
        </div>
        {tooltip && (
          <div
            className="pointer-events-none absolute z-10 max-w-[220px] rounded-lg bg-slate-900/95 px-3 py-2 text-xs text-white shadow-lg dark:bg-slate-100/95 dark:text-slate-900"
            style={{ left: tooltip.x + 12, top: tooltip.y + 12 }}
            role="tooltip"
          >
            <p className="font-semibold">{tooltip.title}</p>
            <p className="text-[10px] opacity-80">{tooltip.subtitle}</p>
            {tooltip.lines.map((line) => (
              <p key={line} className="mt-0.5 text-[10px] opacity-90">
                {line}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
