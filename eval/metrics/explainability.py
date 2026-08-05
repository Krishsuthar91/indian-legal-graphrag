"""Module 10, Part 3 — Explainability metrics.

Each metric consumes an :class:`~src.llm.provenance.ExplanationResult` (plus the
knowledge graph and gold citations) and returns a score in [0, 1].

- Citation Accuracy: how many gold citations are recovered by the answer's
  numbered citations and evidence.
- Hierarchy Correctness: whether the reported ancestor paths match the true
  PART_OF ancestry in the graph.
- Graph Path Accuracy: whether hierarchy-path entries (title / numbering /
  level) agree with the actual graph nodes.
- Provenance Completeness: structural completeness of each evidence entry plus
  recall of the gold citations.
- Evidence Coverage: how much of the reference answer is supported by the
  retrieved evidence text.
- Counter-authority Detection Accuracy: F1 / precision of detected
  counter-authorities against gold expectations.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from eval.dataset import GoldCitation, normalize_citation
from eval.metrics.retrieval import precision_at_k, recall_at_k
from src.llm.provenance import ExplanationResult
from src.retrieval.context import get_ancestor_chain

_TOKEN_RE = re.compile(r"[a-zA-Z0-9']+", re.UNICODE)


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(text or "")}


def _node_anchor(ev) -> str:
    """Normalized 'label numbering' anchor for an evidence node."""
    return normalize_citation(f"{getattr(ev, 'label', '')} {getattr(ev, 'numbering', '')}")


def citation_accuracy(
    result: ExplanationResult,
    gold_citations: Sequence[GoldCitation],
) -> float:
    """Fraction of gold citations matched by retrieved evidence (or citations)."""
    if not gold_citations:
        return 0.0
    gold_keys = {normalize_citation(c.citation_text) for c in gold_citations}
    anchors = [_node_anchor(ev) for ev in result.evidence]
    citation_keys = [normalize_citation(c.citation_text) for c in result.citations]
    matched = 0
    for key in gold_keys:
        if any(gk in key or key in gk for gk in citation_keys):
            matched += 1
            continue
        if any(anchor and (anchor in key or key in anchor) for anchor in anchors):
            matched += 1
    return round(matched / len(gold_keys), 4)


def hierarchy_correctness(
    graph,
    result: ExplanationResult,
) -> float:
    """Fraction of evidence whose reported path equals the true ancestor chain.

    ``result.evidence[i].path`` should be root -> ... -> node. We recompute the
    chain from the graph and require the sequence to match exactly.
    """
    if not result.evidence:
        return 0.0
    correct = 0
    for ev in result.evidence:
        if not graph.get_node(ev.node_id):
            continue
        true_chain = [a["node_id"] for a in reversed(get_ancestor_chain(graph, ev.node_id))]
        true_chain.append(ev.node_id)
        if ev.path == true_chain:
            correct += 1
    return round(correct / len(result.evidence), 4)


def graph_path_accuracy(
    graph,
    result: ExplanationResult,
) -> float:
    """Fraction of hierarchy-path entries consistent with the graph nodes."""
    if not result.hierarchy_paths:
        return 0.0
    total = 0
    correct = 0
    for path in result.hierarchy_paths:
        node_ids = [entry.node_id for entry in path.entries]
        if node_ids:
            expected = [a["node_id"] for a in reversed(get_ancestor_chain(graph, node_ids[-1]))]
            expected.append(node_ids[-1])
            total += 1
            correct += 1 if node_ids == expected else 0
        for entry in path.entries:
            node = graph.get_node(entry.node_id)
            total += 1
            if node is None:
                continue
            ok = (
                entry.title == node.get("title", "")
                and entry.numbering == node.get("numbering", "")
                and entry.level == int(node.get("hierarchy_level", node.get("level", 0)))
            )
            if ok:
                correct += 1
    return round(correct / total, 4) if total else 0.0


_REQUIRED_FIELDS = (
    "node_id",
    "title",
    "text",
    "label",
    "numbering",
    "language",
    "level",
    "dense_score",
    "graph_score",
    "hierarchy_score",
    "final_score",
    "sources",
    "path",
    "snippet",
)


def provenance_completeness(
    result: ExplanationResult,
    gold_citations: Sequence[GoldCitation],
) -> float:
    """0.5 * structural completeness + 0.5 * gold-citation recall."""
    if not result.evidence:
        return 0.0
    structural = 0.0
    for ev in result.evidence:
        present = sum(1 for field in _REQUIRED_FIELDS if getattr(ev, field) not in (None, ""))
        structural += present / len(_REQUIRED_FIELDS)
    structural /= len(result.evidence)

    gold_ids = {c.node_id for c in gold_citations if c.node_id}
    retrieved_ids = [ev.node_id for ev in result.evidence]
    citation_recall = recall_at_k(gold_ids, retrieved_ids, len(retrieved_ids)) if gold_ids else 0.0
    return round(0.5 * structural + 0.5 * citation_recall, 4)


def evidence_coverage(
    result: ExplanationResult,
    reference_answer: str,
) -> float:
    """Fraction of reference-answer tokens covered by the retrieved evidence."""
    answer_tokens = _tokens(reference_answer)
    if not answer_tokens:
        return 0.0
    covered: set[str] = set()
    for ev in result.evidence:
        covered |= _tokens(f"{ev.title} {ev.text} {ev.snippet} {ev.numbering}")
    return round(len(answer_tokens.intersection(covered)) / len(answer_tokens), 4)


def counter_authority_detection_accuracy(
    result: ExplanationResult,
    expected_markers: Sequence[str] | None = None,
) -> dict[str, float]:
    """Precision / recall / F1 of counter-authority detection.

    Without gold expectations, precision is the fraction of detected
    counter-authorities that look like real markers and recall is treated as 1.0
    when nothing was expected and nothing was detected.
    """
    expected = set(expected_markers or [])
    detected = {c.marker for c in result.counter_authorities}
    if not expected and not detected:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    tp = len(expected.intersection(detected)) if expected else len(detected)
    fp = len(detected - expected) if expected else 0
    fn = len(expected - detected) if expected else 0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def citation_precision_at_k(
    result: ExplanationResult,
    gold_citations: Sequence[GoldCitation],
    k: int = 5,
) -> float:
    """Precision of the top-k evidence w.r.t. gold citations (binary relevance)."""
    gold_keys = {normalize_citation(c.citation_text) for c in gold_citations}
    if not gold_keys:
        return 0.0
    relevant = {
        i
        for i, ev in enumerate(result.evidence)
        if any(
            anchor and (anchor in key or key in anchor)
            for anchor in (_node_anchor(ev),)
            for key in gold_keys
        )
    }
    ranked = list(range(len(result.evidence)))
    return precision_at_k(relevant, ranked[:k], k)


def explainability_metrics(
    graph,
    result: ExplanationResult,
    gold_citations: Sequence[GoldCitation],
    reference_answer: str = "",
    expected_markers: Sequence[str] | None = None,
) -> dict[str, float]:
    """Full explainability metric vector for one query."""
    counter = counter_authority_detection_accuracy(result, expected_markers)
    metrics = {
        "citation_accuracy": citation_accuracy(result, gold_citations),
        "hierarchy_correctness": hierarchy_correctness(graph, result),
        "graph_path_accuracy": graph_path_accuracy(graph, result),
        "provenance_completeness": provenance_completeness(result, gold_citations),
        "evidence_coverage": evidence_coverage(result, reference_answer),
        "counter_authority_precision": counter["precision"],
        "counter_authority_recall": counter["recall"],
        "counter_authority_f1": counter["f1"],
    }
    return {key: round(value, 4) for key, value in metrics.items()}
