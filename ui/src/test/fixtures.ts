import type {
  Evidence,
  ExplanationResponse,
  HierarchyPath,
  QueryResponse,
  ReasoningStep,
} from '../types'

export const sampleEvidence: Evidence[] = [
  {
    node_id: 'sec-302',
    title: 'Punishment for murder',
    text: 'Whoever commits murder shall be punished with death, or imprisonment for life, and shall also be liable to fine.',
    label: 'Section',
    numbering: '302',
    collection: 'IPC',
    language: 'en',
    level: 3,
    dense_score: 0.8,
    graph_score: 0.6,
    hierarchy_score: 0.5,
    final_score: 0.7,
    sources: ['dense', 'graph', 'hierarchy'],
    path: ['ipc', 'ch-18', 'sec-302'],
    snippet: 'Whoever commits murder shall be punished with death, or imprisonment for life…',
  },
  {
    node_id: 'sec-300',
    title: 'Murder defined',
    text: 'Murder is committed when the act by which the death is caused is done with the intention of causing death.',
    label: 'Section',
    numbering: '300',
    collection: 'IPC',
    language: 'en',
    level: 3,
    dense_score: 0.5,
    graph_score: 0.4,
    hierarchy_score: 0.3,
    final_score: 0.42,
    sources: ['dense'],
    path: ['ipc', 'ch-18', 'sec-300'],
    snippet: 'Murder is committed when the act by which the death is caused…',
  },
]

export const sampleReasoningChain: ReasoningStep[] = [
  {
    step: 1,
    kind: 'query_parse',
    description: 'Parsed the query into keywords and legal references.',
    node_ids: [],
    detail: { keywords: ['murder'], section_refs: [] },
  },
  {
    step: 2,
    kind: 'dense',
    description: 'Semantic vector search returned 2 candidate(s).',
    node_ids: ['sec-302', 'sec-300'],
    detail: { count: 2 },
  },
  {
    step: 3,
    kind: 'graph',
    description: 'Hybrid hierarchical graph retrieval returned 2 candidate(s).',
    node_ids: ['sec-302'],
    detail: { count: 2 },
  },
  {
    step: 4,
    kind: 'hierarchy',
    description: 'Hierarchical evidence propagated from 1 seed(s) to 2 ancestor/descendant node(s).',
    node_ids: ['ipc', 'ch-18'],
    detail: { count: 2 },
  },
  {
    step: 5,
    kind: 'fusion',
    description: 'Fused dense/graph/hierarchy signals into 2 ranked evidence node(s).',
    node_ids: ['sec-302', 'sec-300'],
    detail: { weights: { dense: 0.4, graph: 0.35, hierarchy: 0.25 }, candidates: 2 },
  },
  {
    step: 6,
    kind: 'verification',
    description: 'Confidence 0.68 (medium); valid=True.',
    node_ids: [],
    detail: { confidence: 0.68, validity: true },
  },
]

export const samplePaths: HierarchyPath[] = [
  {
    node_id: 'sec-302',
    entries: [
      { node_id: 'ipc', title: 'Indian Penal Code', label: 'Act', level: 1, numbering: 'IPC' },
      { node_id: 'ch-18', title: 'Offences Against the Human Body', label: 'Chapter', level: 2, numbering: 'XVIII' },
      { node_id: 'sec-302', title: 'Punishment for murder', label: 'Section', level: 3, numbering: '302' },
    ],
  },
  {
    node_id: 'sec-300',
    entries: [
      { node_id: 'ipc', title: 'Indian Penal Code', label: 'Act', level: 1, numbering: 'IPC' },
      { node_id: 'ch-18', title: 'Offences Against the Human Body', label: 'Chapter', level: 2, numbering: 'XVIII' },
      { node_id: 'sec-300', title: 'Murder defined', label: 'Section', level: 3, numbering: '300' },
    ],
  },
]

export const sampleExplanation: ExplanationResponse = {
  query: 'What is the punishment for murder?',
  query_language: 'en',
  retrieval: {
    keywords: ['punishment', 'murder'],
    section_refs: [],
    dense_hits: 2,
    graph_hits: 2,
    hierarchy_propagated: 2,
    candidates: 2,
    returned: 2,
  },
  evidence: sampleEvidence,
  reasoning_chain: sampleReasoningChain,
  hierarchy_paths: samplePaths,
  citations: [
    {
      index: 1,
      node_id: 'sec-302',
      title: 'Punishment for murder',
      label: 'Section',
      numbering: '302',
      score: 0.7,
      citation_text: 'Section 302, "Punishment for murder"',
      snippet: sampleEvidence[0].snippet,
    },
  ],
  counter_authorities: [
    {
      node_id: 'sec-302',
      title: 'Punishment for murder',
      reason: 'statement appears to be overruled by a later authority',
      marker: 'overruled',
      evidence_text: '…was overruled by the Supreme Court…',
    },
  ],
  confidence: {
    score: 0.68,
    label: 'medium',
    factors: {
      base_score: 0.7,
      keyword_coverage: 0.66,
      sufficiency: 1,
      citation_bonus: 0.1,
      n_evidence: 2,
      matched_keywords: ['murder'],
    },
  },
  validity: {
    is_valid: false,
    supported: true,
    has_conflicts: true,
    cites_counter_authority: true,
    insufficient_evidence: false,
    reasons: ['answer supported by retrieved evidence', 'conflicting or qualifying statements detected'],
  },
  retrieval_weights: { dense: 0.4, graph: 0.35, hierarchy: 0.25 },
}

export const sampleQueryResponse: QueryResponse = {
  ...sampleExplanation,
  provenance_id: 'prov-abc-123',
  answer:
    'Section 302 IPC provides for the punishment for murder — death or imprisonment for life, with a fine [1].',
  model: 'mock-llm',
  duration_ms: 245,
}
