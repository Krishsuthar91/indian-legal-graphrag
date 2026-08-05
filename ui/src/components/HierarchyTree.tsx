import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { HierarchyPath } from '../types'
import { buildHierarchyLayout, pruneLayout } from '../utils/graph'

const LEVEL_COLORS = ['#8b5cf6', '#6366f1', '#3b82f6', '#0ea5e9', '#64748b']

interface TreeNodeData extends Record<string, unknown> {
  label: string
  numbering: string
  title: string
  level: number
  hasChildren: boolean
  isCollapsed: boolean
}

const nodeTypes = {
  hierarchy: ({ data }: NodeProps<Node<TreeNodeData>>) => (
    <div
      className="min-w-[150px] max-w-[210px] rounded-lg border-2 bg-white px-2.5 py-1.5 shadow-sm dark:bg-slate-800"
      style={{ borderColor: LEVEL_COLORS[data.level] ?? LEVEL_COLORS[4] }}
    >
      <div className="flex items-center gap-1.5">
        {data.hasChildren && (
          <span className="shrink-0 text-xs text-slate-400 dark:text-slate-500">
            {data.isCollapsed ? '+' : '−'}
          </span>
        )}
        <span className="truncate font-mono text-xs font-semibold text-slate-700 dark:text-slate-200">
          {data.numbering || data.label}
        </span>
      </div>
      <p className="mt-0.5 line-clamp-2 text-[11px] leading-tight text-slate-500 dark:text-slate-400">
        {data.title || data.label}
      </p>
    </div>
  ),
}

function TreeCanvas({ paths }: { paths: HierarchyPath[] }) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const layout = useMemo(() => buildHierarchyLayout(paths), [paths])
  const { nodes: visibleNodes, edges: visibleEdges } = useMemo(
    () => pruneLayout(layout, collapsed),
    [layout, collapsed],
  )
  const rf = useReactFlow()
  const mounted = useRef(false)

  const nodeMap = useMemo(() => new Map(layout.nodes.map((n) => [n.id, n])), [layout])

  const nodes: Node<TreeNodeData>[] = useMemo(
    () =>
      visibleNodes.map((n) => ({
        id: n.id,
        type: 'hierarchy',
        position: { x: n.x, y: n.y },
        data: {
          label: n.label,
          numbering: n.numbering,
          title: n.title,
          level: n.level,
          hasChildren: n.children.length > 0,
          isCollapsed: collapsed.has(n.id),
        },
      })),
    [visibleNodes, collapsed],
  )

  const edges: Edge[] = useMemo(
    () =>
      visibleEdges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        type: 'default',
        animated: true,
        style: { stroke: '#94a3b8', strokeWidth: 1.5 },
      })),
    [visibleEdges],
  )

  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true
      return
    }
    const t = setTimeout(() => rf.fitView({ padding: 0.2, duration: 300 }), 60)
    return () => clearTimeout(t)
  }, [visibleNodes.length, rf])

  const toggleNode = useCallback(
    (_: unknown, node: Node) => {
      const info = nodeMap.get(node.id)
      if (!info || info.children.length === 0) return
      setCollapsed((prev) => {
        const next = new Set(prev)
        if (next.has(node.id)) {
          next.delete(node.id)
        } else {
          next.add(node.id)
        }
        return next
      })
    },
    [nodeMap],
  )

  const expandAll = () => setCollapsed(new Set())
  const collapseAll = () =>
    setCollapsed(new Set(layout.nodes.filter((n) => n.children.length > 0).map((n) => n.id)))

  if (layout.nodes.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
        No hierarchy paths available.
      </p>
    )
  }

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-500 dark:text-slate-400">
        <span>
          {visibleNodes.length} / {layout.nodes.length} nodes visible
        </span>
        <button
          type="button"
          onClick={expandAll}
          className="rounded border border-slate-300 px-2 py-0.5 hover:bg-slate-100 dark:border-slate-600 dark:hover:bg-slate-800"
        >
          Expand all
        </button>
        <button
          type="button"
          onClick={collapseAll}
          className="rounded border border-slate-300 px-2 py-0.5 hover:bg-slate-100 dark:border-slate-600 dark:hover:bg-slate-800"
        >
          Collapse all
        </button>
        <span className="ml-auto hidden sm:inline">Click a node with +/− to expand/collapse</span>
      </div>
      <div className="h-[420px] w-full overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          onNodeClick={toggleNode}
          minZoom={0.2}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={20} color="#94a3b8" />
          <Controls />
          <MiniMap
            pannable
            zoomable
            nodeColor={(n) =>
              LEVEL_COLORS[((n.data as unknown) as TreeNodeData).level] ?? '#64748b'
            }
          />
        </ReactFlow>
      </div>
    </div>
  )
}

export default function HierarchyTree({ paths }: { paths: HierarchyPath[] }) {
  return (
    <ReactFlowProvider>
      <TreeCanvas paths={paths} />
    </ReactFlowProvider>
  )
}
