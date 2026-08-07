export interface Evidence {
  node_id: string
  title: string
  text: string
  label: string
  numbering: string
  collection: string
  language: string
  level: number
  dense_score: number
  graph_score: number
  hierarchy_score: number
  final_score: number
  sources: string[]
  path: string[]
  snippet: string
}

export interface ReasoningStep {
  step: number
  kind: string
  description: string
  node_ids: string[]
  detail: Record<string, unknown>
}

export interface HierarchyPathEntry {
  node_id: string
  title: string
  label: string
  level: number
  numbering: string
}

export interface HierarchyPath {
  node_id: string
  entries: HierarchyPathEntry[]
}

export interface SourceCitation {
  index: number
  node_id: string
  title: string
  label: string
  numbering: string
  score: number
  citation_text: string
  snippet: string
}

export interface CounterAuthority {
  node_id: string
  title: string
  reason: string
  marker: string
  evidence_text: string
}

export interface Confidence {
  score: number
  label: string
  factors: Record<string, unknown>
}

export interface Validity {
  is_valid: boolean
  supported: boolean
  has_conflicts: boolean
  cites_counter_authority: boolean
  insufficient_evidence: boolean
  reasons: string[]
}

export interface RetrievalSummary {
  keywords: string[]
  section_refs: string[]
  dense_hits: number
  graph_hits: number
  hierarchy_propagated: number
  candidates: number
  returned: number
}

export interface ExplanationResponse {
  query: string
  query_language: string
  retrieval: RetrievalSummary
  evidence: Evidence[]
  reasoning_chain: ReasoningStep[]
  hierarchy_paths: HierarchyPath[]
  citations: SourceCitation[]
  counter_authorities: CounterAuthority[]
  confidence: Confidence
  validity: Validity
  retrieval_weights: Record<string, number>
}

export interface QueryResponse extends ExplanationResponse {
  provenance_id: string
  answer: string
  model: string
  duration_ms: number
}

export interface QueryRequest {
  query: string
  top_k?: number
  language?: string
  temperature?: number
  max_tokens?: number
}

export interface ExplainRequest {
  query: string
  top_k?: number
  language?: string
}

export interface DocumentUploadResponse {
  document_id: string
  title: string
  language: string
  num_pages: number
  file_name: string
  nodes_indexed: number
  collections: Record<string, number>
  message: string
}

export interface RecentQuestion {
  query: string
  language: string
  topK: number
  timestamp: number
}

export interface LocalSettings {
  darkMode: boolean
  defaultLanguage: string
  defaultTopK: number
}
