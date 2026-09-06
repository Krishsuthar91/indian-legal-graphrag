"""Retrieval failure analysis — classifies why retrieval missed for each query.

For every benchmark question whose retrieval is incomplete (section accuracy
< 1.0 or no evidence retrieved), a ``RetrievalFailureAnalysis`` record is
produced.  The analysis classifies the failure into a typed category and
generates a human-readable reason and recommendation so the evaluation
report can surface actionable insights.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from src.evaluation.sections import (
    matches,
    section_keys_from_text,
)


@dataclass
class RetrievalFailureAnalysis:
    """Structured classification of a single retrieval failure."""

    query: str = ""
    expected_sections: list[str] = field(default_factory=list)
    retrieved_sections: list[str] = field(default_factory=list)
    missing_sections: list[str] = field(default_factory=list)
    extra_sections: list[str] = field(default_factory=list)
    failure_type: str = ""
    failure_reason: str = ""
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable dictionary (``dataclasses.asdict``)."""
        return asdict(self)


_FAILURE_REASONS: dict[str, str] = {
    "missing_section": "Expected section(s) were not retrieved.",
    "wrong_section": "Retrieved sections do not match any expected section.",
    "partial_match": "Some expected sections were retrieved but not all.",
    "low_similarity": "Retrieved evidence has low similarity to the query.",
    "no_evidence": "No evidence was retrieved for the query.",
    "ranking_error": "Expected section was retrieved but ranked too low.",
    "graph_error": "Graph traversal failed to reach the expected section.",
    "chunking_error": "Expected section is missing from the chunk index.",
}

_FAILURE_RECOMMENDATIONS: dict[str, str] = {
    "missing_section": ("Improve retrieval weighting or query expansion."),
    "wrong_section": ("Review section parsing; retrieved nodes may map to incorrect sections."),
    "partial_match": ("Increase top_k or improve ranking so all expected sections surface."),
    "low_similarity": ("Add domain-specific embeddings or synonym expansion for legal queries."),
    "no_evidence": ("Check that the document is fully indexed and the query is within scope."),
    "ranking_error": ("Adjust ranking weights so gold-relevant nodes rank higher."),
    "graph_error": ("Verify parent/child edges in the hierarchy graph."),
    "chunking_error": ("Re-parse the document so the expected section appears as a node."),
}


def _extract_retrieved_section_keys(
    retrieved_evidence: list[dict[str, Any]],
) -> list[str]:
    """Derive normalised section keys from the retrieved evidence dicts."""
    keys: list[str] = []
    for ev in retrieved_evidence:
        numbering = ev.get("numbering", "")
        title = ev.get("title", "")
        keys.extend(sorted(section_keys_from_text(numbering) | section_keys_from_text(title)))
    return keys


def _find_matching_retrieved(
    expected_key: str,
    retrieved_keys: list[str],
    retrieved_scores: list[float],
) -> tuple[bool, int, float]:
    """Check whether *expected_key* matches any retrieved section.

    Returns ``(found, rank_position, score)`` where *rank_position* is the
    1-based rank of the first match (0 if not found) and *score* is its
    corresponding retrieval score.
    """
    seen_ranks: dict[str, int] = {}
    for idx, key in enumerate(retrieved_keys, 1):
        seen_ranks.setdefault(key, idx)

    for idx, key in enumerate(retrieved_keys, 1):
        if matches(expected_key, key):
            score = retrieved_scores[idx - 1] if idx - 1 < len(retrieved_scores) else 0.0
            return True, idx, score
    return False, 0, 0.0


def _analyze_retrieval_failure(
    query: str,
    expected_sections: list[str],
    retrieved_evidence: list[dict[str, Any]],
    *,
    ranking_top_k: int = 5,
    similarity_threshold: float = 0.30,
) -> RetrievalFailureAnalysis:
    """Classify why retrieval failed for a single benchmark question.

    Parameters
    ----------
    query:
        The natural-language question that was asked.
    expected_sections:
        Normalised section keys the benchmark expects (e.g. ``["72"]``).
    retrieved_evidence:
        Evidence dicts produced by the retrieval pipeline (must contain
        at least ``numbering``, ``title``, and ``final_score``).
    ranking_top_k:
        Positions 1..k are considered "well-ranked"; anything beyond this
        is a ranking error when the section *is* present but low.
    similarity_threshold:
        Minimum ``final_score`` for an evidence entry to count as
        "sufficiently similar".
    """
    analysis = RetrievalFailureAnalysis(
        query=query,
        expected_sections=list(expected_sections),
    )

    # --- No evidence at all ------------------------------------------------
    if not retrieved_evidence:
        analysis.failure_type = "no_evidence"
        analysis.failure_reason = _FAILURE_REASONS["no_evidence"]
        analysis.recommendation = _FAILURE_RECOMMENDATIONS["no_evidence"]
        analysis.missing_sections = list(expected_sections)
        return analysis

    retrieved_keys = _extract_retrieved_section_keys(retrieved_evidence)
    analysis.retrieved_sections = retrieved_keys

    retrieved_scores = [float(ev.get("final_score", 0.0)) for ev in retrieved_evidence]

    # --- Check each expected section ----------------------------------------
    missing: list[str] = []
    ranking_errors: list[str] = []

    for exp_key in expected_sections:
        found, rank, score = _find_matching_retrieved(exp_key, retrieved_keys, retrieved_scores)
        if not found:
            missing.append(exp_key)
        elif rank > ranking_top_k:
            ranking_errors.append(exp_key)

    analysis.missing_sections = missing

    # Extra sections = retrieved keys that don't match any expected section
    expected_set = set(expected_sections)
    extra = [
        key
        for key in dict.fromkeys(retrieved_keys)
        if not any(matches(exp, key) for exp in expected_set)
    ]
    analysis.extra_sections = extra

    # --- Classify the dominant failure type ---------------------------------
    all_found = len(missing) == 0

    if all_found and not ranking_errors:
        # All expected sections present and well-ranked — should not be
        # classified as a failure, but handle gracefully.
        analysis.failure_type = "partial_match"
        analysis.failure_reason = _FAILURE_REASONS["partial_match"]
        analysis.recommendation = _FAILURE_RECOMMENDATIONS["partial_match"]
        return analysis

    if len(missing) == len(expected_sections):
        # Nothing expected was found
        if all(s < similarity_threshold for s in retrieved_scores):
            analysis.failure_type = "low_similarity"
            analysis.failure_reason = f"All retrieved scores below {similarity_threshold:.2f}."
            analysis.recommendation = _FAILURE_RECOMMENDATIONS["low_similarity"]
        elif ranking_errors:
            analysis.failure_type = "ranking_error"
            analysis.failure_reason = (
                f"Expected section(s) retrieved but ranked below top-{ranking_top_k}."
            )
            analysis.recommendation = _FAILURE_RECOMMENDATIONS["ranking_error"]
        else:
            # Expected section is absent from results — missing_section
            analysis.failure_type = "missing_section"
            analysis.failure_reason = f"Expected section(s) {expected_sections} not retrieved."
            analysis.recommendation = _FAILURE_RECOMMENDATIONS["missing_section"]
    elif ranking_errors:
        # Some found, some missing due to ranking
        analysis.failure_type = "ranking_error"
        analysis.failure_reason = (
            f"Section(s) {ranking_errors} retrieved but ranked below top-{ranking_top_k}."
        )
        analysis.recommendation = _FAILURE_RECOMMENDATIONS["ranking_error"]
    else:
        # Partial match — some expected sections found, some missing
        analysis.failure_type = "partial_match"
        analysis.failure_reason = f"Missing section(s): {missing}."
        analysis.recommendation = _FAILURE_RECOMMENDATIONS["partial_match"]

    return analysis


def build_failure_analyses(
    query: str,
    expected_sections: list[str],
    retrieved_evidence: list[dict[str, Any]],
    *,
    section_accuracy: float = 1.0,
    ranking_top_k: int = 5,
    similarity_threshold: float = 0.30,
) -> RetrievalFailureAnalysis | None:
    """Return a failure analysis only when retrieval is incomplete.

    Returns ``None`` when *section_accuracy* is 1.0 (all expected sections
    found) so the caller can skip storing a success record.
    """
    if section_accuracy >= 1.0:
        return None
    return _analyze_retrieval_failure(
        query,
        expected_sections,
        retrieved_evidence,
        ranking_top_k=ranking_top_k,
        similarity_threshold=similarity_threshold,
    )


def summarize_failure_types(
    analyses: list[RetrievalFailureAnalysis],
) -> dict[str, dict[str, Any]]:
    """Aggregate failure analyses into a summary table.

    Returns a dict keyed by failure type, each value containing
    ``count``, ``percentage``, ``examples`` (up to 3 queries), and
    ``recommendations`` (unique).
    """
    total = len(analyses)
    if total == 0:
        return {}

    by_type: dict[str, list[RetrievalFailureAnalysis]] = {}
    for a in analyses:
        by_type.setdefault(a.failure_type, []).append(a)

    summary: dict[str, dict[str, Any]] = {}
    for ftype, items in sorted(by_type.items(), key=lambda kv: -len(kv[1])):
        pct = round(len(items) / total * 100, 1)
        examples = [a.query for a in items[:3]]
        recs = list(dict.fromkeys(a.recommendation for a in items))
        summary[ftype] = {
            "count": len(items),
            "percentage": pct,
            "examples": examples,
            "recommendations": recs,
        }
    return summary


def top_recommendations(
    analyses: list[RetrievalFailureAnalysis],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return the most frequent unique recommendations with their counts."""
    counts: dict[str, int] = {}
    for a in analyses:
        if a.recommendation:
            counts[a.recommendation] = counts.get(a.recommendation, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])[:limit]
    return [{"recommendation": rec, "count": cnt} for rec, cnt in ranked]
