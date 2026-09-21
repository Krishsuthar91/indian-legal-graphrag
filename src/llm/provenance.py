"""Retrieval provenance — evidence, reasoning chain, citations, confidence, validity.

These plain dataclasses are the single source of truth for everything the
explainability engine produces. They serialize to dicts (``dataclasses.asdict``)
for persistence and for the FastAPI response models.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.config.logging_config import get_logger
from src.config.settings import settings

log = get_logger("provenance")

_SECONDS_PER_DAY = 86_400


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
class EvidenceRelevance:
    """LLM-judged relevance of retrieved evidence to the user query."""

    score: float = 0.0
    label: str = "unknown"
    explanation: str = ""


@dataclass
class ClaimResult:
    """Entailment verdict for a single claim against its cited evidence."""

    claim: str = ""
    citation: str = ""
    entailment: float = 0.0
    contradicts: bool = False
    reason: str = ""


@dataclass
class CitationEntailment:
    """Aggregate entailment verdict for all claims in a generated answer."""

    overall_score: float = 0.0
    contradiction_found: bool = False
    claim_results: list[ClaimResult] = field(default_factory=list)
    summary: str = ""


@dataclass
class Validity:
    """Validity flags describing how well the answer is supported."""

    is_valid: bool
    supported: bool
    has_conflicts: bool
    cites_counter_authority: bool
    insufficient_evidence: bool
    reasons: list[str] = field(default_factory=list)
    # Task 4: structured verification badge driven by the verification framework.
    status: str = "unknown"
    reason: str = ""
    support_score: float = 0.0
    relevance_score: float = 0.0
    sufficiency_score: float = 0.0
    contradiction_found: bool = False


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
    ranking_breakdown: dict[str, dict[str, float]] = field(default_factory=dict)
    duplicates_removed: int = 0
    duplicate_details: list[dict[str, Any]] = field(default_factory=list)
    # Phase 3 C4: canonical hierarchy-path preference, per retained node. Kept
    # out of the API schema on purpose — it is diagnostics only (persisted in
    # provenance) and the response format must not change.
    chain_ranking: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Phase 3 C5: adaptive retrieval integration + research diagnostics. All
    # optional/defaulted for backward compatibility: old provenance records
    # (without these keys) load unchanged, and the public API schema is left
    # untouched — these live in provenance for offline evaluation only.
    retrieval_pipeline: list[str] = field(default_factory=list)
    query_intent: str = ""
    retrieved_candidates: int = 0
    ranked_candidates: int = 0
    ranking_weights: dict[str, float] = field(default_factory=dict)
    retrieval_latency_ms: float = 0.0
    ranking_latency_ms: float = 0.0
    total_retrieval_latency_ms: float = 0.0
    latency_breakdown: dict[str, float] = field(default_factory=dict)
    # Phase 4: deterministic legal query expansion diagnostics. Optional /
    # defaulted so old provenance records load unchanged, and kept out of the
    # public API schema alongside the other research diagnostics.
    query_expansion_enabled: bool = False
    expanded_terms: list[str] = field(default_factory=list)
    expanded_concepts: list[str] = field(default_factory=list)
    expansion_reason: str = ""
    # Corpus-aware section-reference diagnostics: which verified references were
    # considered, which exist in the indexed corpus (and were injected), and
    # which were omitted because the section is not present in the corpus.
    section_refs_considered: list[str] = field(default_factory=list)
    section_refs_available: list[str] = field(default_factory=list)
    section_refs_omitted: list[str] = field(default_factory=list)


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
    validity: Validity = field(default_factory=lambda: Validity(False, False, False, False, True))
    retrieval_weights: dict[str, float] = field(default_factory=dict)
    evidence_relevance: EvidenceRelevance = field(
        default_factory=EvidenceRelevance,
    )
    citation_entailment: CitationEntailment = field(
        default_factory=CitationEntailment,
    )
    verification_trace: VerificationTrace | None = None


@dataclass
class VerificationTrace:
    """Structured trace explaining why verification and confidence were assigned.

    This is the read-only audit trail produced by the verification pipeline.
    All fields are plain JSON-serialisable types so the trace can be stored
    verbatim and rendered by any front-end without further transformation.
    """

    verification_status: str = ""
    verification_reason: str = ""
    confidence_score: float = 0.0
    confidence_label: str = ""
    evidence_relevance_score: float = 0.0
    evidence_relevance_label: str = ""
    evidence_sufficiency_score: float = 0.0
    citation_entailment_score: float = 0.0
    contradiction_found: bool = False
    retrieval_base_score: float = 0.0
    final_adjustment: str = ""
    decision_path: list[str] = field(default_factory=list)


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


@dataclass
class ProvenanceCleanup:
    """Outcome of a provenance retention run."""

    removed: int
    remaining: int
    dry_run: bool = False


def _is_provenance_record(path: Path) -> bool:
    """True only for persisted ``AnswerResult`` provenance records.

    Any other JSON (hierarchy, processed, embeddings, evaluation artifacts)
    that could share a directory is not a provenance record and must never be
    touched by cleanup.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return False
    return isinstance(data, dict) and "provenance_id" in data


def _retention_survivors(
    records: list[Path],
    now: float,
    retention_days: int,
    max_files: int,
) -> set[Path]:
    """Return the provenance files a retention run must keep.

    A record survives when it is newer than the retention window *or* when it
    ranks inside the ``max_files`` newest records, so the newest files are
    always preserved. Files that cannot be stat()ed are also kept (never
    delete what cannot be evaluated).
    """

    def mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return float("-inf")

    age_enabled = bool(retention_days and retention_days > 0)
    count_enabled = bool(max_files and max_files > 0)
    if not age_enabled and not count_enabled:
        return set(records)

    survivors: set[Path] = set()
    if age_enabled:
        cutoff = now - retention_days * _SECONDS_PER_DAY
        survivors.update(p for p in records if mtime(p) >= cutoff)
    if count_enabled:
        newest = sorted(records, key=mtime, reverse=True)[:max_files]
        survivors.update(newest)
    return survivors


def cleanup_provenance(
    directory: str | Path | None = None,
    retention_days: int | None = None,
    max_files: int | None = None,
    enabled: bool | None = None,
    *,
    dry_run: bool = False,
    now: float | None = None,
) -> ProvenanceCleanup:
    """Retention-clean the provenance directory (defaults from settings).

    ``ProvenanceStore.cleanup`` is applied to ``settings.QA_PROVENANCE_DIR``
    unless ``directory`` is given. Delegating means every caller keeps a
    single, idempotent cleanup implementation.
    """
    target = Path(directory) if directory is not None else Path(settings.QA_PROVENANCE_DIR)
    return ProvenanceStore(target).cleanup(
        retention_days=retention_days,
        max_files=max_files,
        enabled=enabled,
        dry_run=dry_run,
        now=now,
    )


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
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
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

    def cleanup(
        self,
        retention_days: int | None = None,
        max_files: int | None = None,
        enabled: bool | None = None,
        *,
        dry_run: bool = False,
        now: float | None = None,
    ) -> ProvenanceCleanup:
        """Enforce the provenance retention policy on the store directory.

        Settings supply the defaults; explicit arguments override them. Only
        persisted ``AnswerResult`` provenance records (JSON containing a
        ``provenance_id``) are ever considered, so processed/hierarchy/
        canonical/evaluation artifacts are never touched, and non-provenance
        files in the same directory are never deleted. Idempotent: a second
        run removes nothing.
        """
        retention_days = (
            retention_days if retention_days is not None else settings.PROVENANCE_RETENTION_DAYS
        )
        max_files = max_files if max_files is not None else settings.PROVENANCE_MAX_FILES
        enabled = enabled if enabled is not None else settings.PROVENANCE_CLEANUP_ENABLED
        stamp = time.time() if now is None else now

        if self.directory is None:
            log.info("provenance.cleanup.start", directory=None, enabled=enabled)
            log.info("provenance.cleanup.complete", removed=0, remaining=0)
            print("provenance.cleanup.complete removed=0 remaining=0")
            return ProvenanceCleanup(removed=0, remaining=0, dry_run=dry_run)

        log.info(
            "provenance.cleanup.start",
            directory=str(self.directory),
            retention_days=retention_days,
            max_files=max_files,
            enabled=enabled,
            dry_run=dry_run,
        )
        print(
            f"provenance.cleanup.start directory={self.directory} "
            f"retention_days={retention_days} max_files={max_files} "
            f"enabled={enabled}"
        )

        records = [p for p in sorted(self.directory.glob("*.json")) if _is_provenance_record(p)]

        if not enabled:
            result = ProvenanceCleanup(removed=0, remaining=len(records), dry_run=dry_run)
            log.info(
                "provenance.cleanup.complete",
                removed=0,
                remaining=result.remaining,
                disabled=True,
            )
            print(
                f"provenance.cleanup.complete removed=0 remaining={result.remaining} disabled=True"
            )
            return result

        survivors = _retention_survivors(records, stamp, retention_days, max_files)

        removed = 0
        for path in records:
            if path in survivors:
                continue
            log.info("provenance.cleanup.remove", path=str(path), dry_run=dry_run)
            print(f"provenance.cleanup.remove path={path}")
            if not dry_run:
                try:
                    path.unlink()
                except OSError as exc:
                    log.warning(
                        "provenance.cleanup.remove_failed",
                        path=str(path),
                        error=str(exc),
                    )
                    print(f"provenance.cleanup.remove_failed path={path} error={exc}")
                    continue
            removed += 1

        remaining = len([p for p in self.directory.glob("*.json") if _is_provenance_record(p)])
        result = ProvenanceCleanup(removed=removed, remaining=remaining, dry_run=dry_run)
        log.info(
            "provenance.cleanup.complete",
            removed=result.removed,
            remaining=result.remaining,
            dry_run=dry_run,
        )
        print(f"provenance.cleanup.complete removed={result.removed} remaining={result.remaining}")
        return result
