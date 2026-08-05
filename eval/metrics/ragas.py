"""Module 10, Part 4 — RAGAS-style generation metrics.

RAGAS is not a hard dependency, so every metric ships a deterministic offline
implementation that runs without a model download:

- Faithfulness: claim-level support of the answer by retrieved evidence.
- Answer Relevancy: query-answer semantic closeness (embedding cosine).
- Context Recall: how much of the gold context is present in retrieved evidence.
- Context Precision: how relevant the retrieved evidence is to the query.
- Answer Correctness: token F1 + semantic similarity vs. the reference answer.

When the ``ragas`` package is installed, :func:`ragas_available` returns True and
:func:`ragas_context` exposes the native library entry points for real runs.
"""

from __future__ import annotations

import importlib.util
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

from eval.dataset import GoldCitation, normalize_citation
from eval.metrics.semantic import EmbeddingCache
from src.llm.provenance import ExplanationResult

_TOKEN_RE = re.compile(r"[a-zA-Z0-9']+", re.UNICODE)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+", re.UNICODE)
_CONTEXT_THRESHOLD = 0.25


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(text or "")}


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.split(text or "") if s.strip()]


def token_f1(reference: str, candidate: str) -> float:
    """Standard token-overlap F1 between two texts."""
    ref_tokens = _tokens(reference)
    cand_tokens = _tokens(candidate)
    if not ref_tokens or not cand_tokens:
        return 0.0
    common = ref_tokens.intersection(cand_tokens)
    if not common:
        return 0.0
    precision = len(common) / len(cand_tokens)
    recall = len(common) / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


def _evidence_text(result: ExplanationResult) -> str:
    parts: list[str] = []
    for ev in result.evidence:
        snippet = getattr(ev, "snippet", "") or ""
        parts.append(
            f"{getattr(ev, 'title', '')} {getattr(ev, 'text', '')} {snippet} "
            f"{getattr(ev, 'label', '')} {getattr(ev, 'numbering', '')}"
        )
    return " ".join(parts)


def faithfulness(answer: str, result: ExplanationResult) -> float:
    """Fraction of answer sentences supported by the retrieved evidence."""
    answer = (answer or "").strip()
    sentences = _sentences(answer)
    if not sentences:
        return 0.0
    evidence_text = _evidence_text(result).lower()
    evidence_tokens = _tokens(evidence_text)
    supported = 0
    for sentence in sentences:
        sent_tokens = _tokens(sentence)
        if not sent_tokens:
            continue
        if any(token in evidence_text for token in sent_tokens) or sent_tokens.intersection(
            evidence_tokens
        ):
            supported += 1
    return round(supported / len(sentences), 4)


def answer_relevancy(query: str, answer: str, cache: EmbeddingCache) -> float:
    """Semantic closeness between the query and the generated answer."""
    if not answer.strip():
        return 0.0
    return round(cache.relevance(query, answer), 4)


def context_recall(
    gold_citations: Sequence[GoldCitation],
    result: ExplanationResult,
) -> float:
    """Fraction of gold citations recoverable from the retrieved context.

    A gold citation is recovered when the label+numbering anchor of one of the
    retrieved evidence nodes appears inside the gold citation string.
    """
    if not gold_citations:
        return 0.0
    anchors = {
        normalize_citation(f"{getattr(ev, 'label', '')} {getattr(ev, 'numbering', '')}")
        for ev in result.evidence
    }
    gold_keys = {normalize_citation(c.citation_text) for c in gold_citations}
    matched = 0
    for key in gold_keys:
        if any(anchor and (anchor in key or key in anchor) for anchor in anchors):
            matched += 1
    return round(matched / len(gold_keys), 4)


def context_precision(query: str, result: ExplanationResult, cache: EmbeddingCache) -> float:
    """Mean query-relevance of the retrieved evidence (rank-agnostic precision)."""
    if not result.evidence:
        return 0.0
    scores = [
        cache.relevance(
            query,
            f"{getattr(ev, 'title', '')} {getattr(ev, 'text', '')} "
            f"{getattr(ev, 'snippet', '') or ''}",
        )
        for ev in result.evidence
    ]
    return round(sum(scores) / len(scores), 4)


def answer_correctness(
    reference_answer: str,
    answer: str,
    cache: EmbeddingCache,
) -> float:
    """0.5 * token F1 + 0.5 * semantic cosine against the reference answer."""
    if not answer.strip():
        return 0.0
    f1 = token_f1(reference_answer, answer)
    cosine = cache.cosine(reference_answer, answer)
    return round(0.5 * f1 + 0.5 * cosine, 4)


@dataclass
class RAGASMetrics:
    """The five RAGAS-style scores for one generated answer."""

    faithfulness: float
    answer_relevancy: float
    context_recall: float
    context_precision: float
    answer_correctness: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def compute_ragas_metrics(
    query: str,
    answer: str,
    reference_answer: str,
    result: ExplanationResult,
    gold_citations: Sequence[GoldCitation],
    cache: EmbeddingCache | None = None,
) -> RAGASMetrics:
    """Compute the offline RAGAS-style metric vector for one question."""
    cache = cache or EmbeddingCache()
    if result.evidence:
        return RAGASMetrics(
            faithfulness=faithfulness(answer, result),
            answer_relevancy=answer_relevancy(query, answer, cache),
            context_recall=context_recall(gold_citations, result),
            context_precision=context_precision(query, result, cache),
            answer_correctness=answer_correctness(reference_answer, answer, cache),
        )
    return RAGASMetrics(
        faithfulness=0.0,
        answer_relevancy=answer_relevancy(query, answer, cache),
        context_recall=0.0,
        context_precision=0.0,
        answer_correctness=answer_correctness(reference_answer, answer, cache),
    )


def ragas_available() -> bool:
    """True when the optional ``ragas`` package is installed."""
    return importlib.util.find_spec("ragas") is not None


def ragas_context() -> dict[str, Any] | None:
    """Expose the native RAGAS library (for real model-backed runs) or None."""
    if not ragas_available():
        return None
    import ragas  # type: ignore[import-not-found]
    from ragas.metrics import (  # type: ignore[import-not-found]
        answer_correctness,
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

    return {
        "faithfulness": faithfulness,
        "answer_relevancy": answer_relevancy,
        "context_recall": context_recall,
        "context_precision": context_precision,
        "answer_correctness": answer_correctness,
        "version": getattr(ragas, "__version__", "unknown"),
    }
