"""Pydantic request/response schemas for the QA API (Module 7)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural-language legal question")
    top_k: int | None = Field(default=None, ge=1, le=20, description="Evidence count")
    language: str | None = Field(default=None, description="Optional document language filter")
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=4000)


class ExplainRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)
    language: str | None = None


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class EvidenceSchema(BaseModel):
    node_id: str
    title: str
    text: str
    label: str
    numbering: str
    collection: str
    language: str
    level: int
    dense_score: float
    graph_score: float
    hierarchy_score: float
    final_score: float
    sources: list[str] = Field(default_factory=list)
    path: list[str] = Field(default_factory=list)
    snippet: str = ""


class ReasoningStepSchema(BaseModel):
    step: int
    kind: str
    description: str
    node_ids: list[str] = Field(default_factory=list)
    detail: dict[str, Any] = Field(default_factory=dict)


class HierarchyPathEntrySchema(BaseModel):
    node_id: str
    title: str
    label: str
    level: int
    numbering: str


class HierarchyPathSchema(BaseModel):
    node_id: str
    entries: list[HierarchyPathEntrySchema] = Field(default_factory=list)


class SourceCitationSchema(BaseModel):
    index: int
    node_id: str
    title: str
    label: str
    numbering: str
    score: float
    citation_text: str
    snippet: str


class CounterAuthoritySchema(BaseModel):
    node_id: str
    title: str
    reason: str
    marker: str
    evidence_text: str


class ConfidenceSchema(BaseModel):
    score: float
    label: str
    factors: dict[str, Any] = Field(default_factory=dict)


class ValiditySchema(BaseModel):
    is_valid: bool
    supported: bool
    has_conflicts: bool
    cites_counter_authority: bool
    insufficient_evidence: bool
    reasons: list[str] = Field(default_factory=list)


class RetrievalSummarySchema(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    section_refs: list[str] = Field(default_factory=list)
    dense_hits: int = 0
    graph_hits: int = 0
    hierarchy_propagated: int = 0
    candidates: int = 0
    returned: int = 0
    intent: str = ""
    adaptive_top_k: int | None = None
    retrieval_strategy: str = "fixed"
    ranking_breakdown: dict[str, dict[str, float]] = Field(default_factory=dict)
    duplicates_removed: int = 0
    duplicate_details: list[dict[str, Any]] = Field(default_factory=list)


class ExplanationResponse(BaseModel):
    query: str
    query_language: str
    retrieval: RetrievalSummarySchema = Field(default_factory=RetrievalSummarySchema)
    evidence: list[EvidenceSchema] = Field(default_factory=list)
    reasoning_chain: list[ReasoningStepSchema] = Field(default_factory=list)
    hierarchy_paths: list[HierarchyPathSchema] = Field(default_factory=list)
    citations: list[SourceCitationSchema] = Field(default_factory=list)
    counter_authorities: list[CounterAuthoritySchema] = Field(default_factory=list)
    confidence: ConfidenceSchema = Field(default_factory=ConfidenceSchema)
    validity: ValiditySchema = Field(default_factory=ValiditySchema)
    retrieval_weights: dict[str, float] = Field(default_factory=dict)


class QueryResponse(ExplanationResponse):
    provenance_id: str
    answer: str
    model: str
    duration_ms: float
