"""Retrieval provenance — evidence, reasoning chain, citations, confidence, validity.

These plain dataclasses are the single source of truth for everything the
explainability engine produces. They serialize to dicts (``dataclasses.asdict``)
for persistence and for the FastAPI response models.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.config.logging_config import get_logger

log = get_logger("provenance")


# ---------------------------------------------------------------------------
# Evidence and explanation building blocks
# ---------------------------------------------------------------------------

@dataclass
class Evidence:
    """A single retrieved node with its per-signal scores and provenance."""

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
    sources: list[str] = field(default_factory=list)
    path: list[str] = field(default_factory=list)  # ancestor chain, root -> node
    snippet: str = ""


@dataclass
class ReasoningStep:
    """One explainable step in the retrieval pipeline."""

    step: int
    kind: str
    description: str
    node_ids: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class HierarchyPathEntry:
    """One node along a hierarchy path."""

    node_id: str
    title: str
    label: str
    level: int
    numbering: str


@dataclass
class HierarchyPath:
    """Full ancestor path (root -> node) for a piece of evidence."""

    node_id: str
    entries: list[HierarchyPathEntry] = field(default_factory=list)


@dataclass
class SourceCitation:
    """A numbered source citation attached to the answer."""

    index: int
    node_id: str
    title: str
    label: str
    numbering: str
    score: float
    citation_text: str
    snippet: str


@dataclass
class CounterAuthority:
    """A detected statement that conflicts with, qualifies, or supersedes the answer."""

    node_id: str
    title: str
    reason: str
    marker: str
    evidence_text: str


@dataclass
class Confidence:
    """Aggregate confidence score with its contributing factors."""

    score: float
    label: str
    factors: dict[str, Any] = field(default_factory=dict)


@dataclass
class Validity:
    """Validity flags describing how well the answer is supported."""

    is_valid: bool
    supported: bool
    has_conflicts: bool
    cites_counter_authority: bool
    insufficient_evidence: bool
    reasons: list[str] = field(default_factory=list)


@dataclass
class RetrievalSummary:
    """Counts from each retrieval stage plus adaptive-retrieval diagnostics."""

    keywords: list[str] = field(default_factory=list)
    section_refs: list[str] = field(default_factory=list)
    dense_hits: int = 0
    graph_hits: int = 0
    hierarchy_propagated: int = 0
    candidates: int = 0
    returned: int = 0
    intent: str = ""
    adaptive_top_k: int | None = None
    retrieval_strategy: str = "fixed"


@dataclass
class ExplanationResult:
    """Everything the explainability engine computed for a query."""

    query: str
    query_language: str
    retrieval: RetrievalSummary = field(default_factory=RetrievalSummary)
    evidence: list[Evidence] = field(default_factory=list)
    reasoning_chain: list[ReasoningStep] = field(default_factory=list)
    hierarchy_paths: list[HierarchyPath] = field(default_factory=list)
    citations: list[SourceCitation] = field(default_factory=list)
    counter_authorities: list[CounterAuthority] = field(default_factory=list)
    confidence: Confidence = field(default_factory=lambda: Confidence(0.0, "low"))
    validity: Validity = field(
        default_factory=lambda: Validity(False, False, False, False, True)
    )
    retrieval_weights: dict[str, float] = field(default_factory=dict)


@dataclass
class AnswerResult:
    """Full answer plus its explanation and provenance."""

    provenance_id: str
    query: str
    answer: str
    model: str
    explanation: ExplanationResult
    duration_ms: float


# ---------------------------------------------------------------------------
# Provenance store
# ---------------------------------------------------------------------------

def _as_dict(obj: Any) -> dict[str, Any]:
    return asdict(obj)


class ProvenanceStore:
    """In-memory provenance records with optional JSON-file persistence."""

    def __init__(self, directory: str | Path | None = None) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self.directory = Path(directory) if directory else None
        if self.directory is not None:
            self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, result: AnswerResult) -> str:
        """Store an AnswerResult, returning its provenance_id."""
        record = _as_dict(result)
        self._records[result.provenance_id] = record
        if self.directory is not None:
            path = self.directory / f"{result.provenance_id}.json"
            path.write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            log.debug("provenance.saved", id=result.provenance_id, path=str(path))
        return result.provenance_id

    def get(self, provenance_id: str) -> dict[str, Any] | None:
        """Return a stored provenance record (as a dict) or None."""
        record = self._records.get(provenance_id)
        if record is not None:
            return record
        if self.directory is not None:
            path = self.directory / f"{provenance_id}.json"
            if path.exists():
                try:
                    record = json.loads(path.read_text(encoding="utf-8"))
                    self._records[provenance_id] = record
                    return record
                except (json.JSONDecodeError, OSError) as exc:
                    log.warning("provenance.load_failed", id=provenance_id, error=str(exc))
        return None

    def list_ids(self, limit: int = 50) -> list[str]:
        """Return the most recently saved provenance ids (in save order)."""
        return list(self._records.keys())[-limit:]
