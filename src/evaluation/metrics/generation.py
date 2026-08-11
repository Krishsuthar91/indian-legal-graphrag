"""Generation metrics — deterministic, offline quality proxies.

The metrics operate on the raw answer text plus the retrieval explanation and
do not require a second LLM judge:

- Answer Accuracy    token F1 between the answer and the gold answer summary
- Grounding Accuracy fraction of the answer's inline ``[N]`` citations that
                     reference an actually retrieved source, and any section
                     numbers mentioned in the answer are covered by evidence
- Citation Accuracy  expected sections covered by the sources the answer cited
- Faithfulness       fraction of answer content tokens supported by evidence
- Evidence Coverage  fraction of gold-answer tokens supported by evidence
- Hallucination Rate fraction of answer content tokens NOT supported by
                     evidence (1 - faithfulness)

The grounded guard answer (insufficient indexed evidence) scores perfectly on
grounding, citation accuracy, and hallucination because it makes no
unverifiable claims.
"""

from __future__ import annotations

import re

from src.evaluation.sections import section_coverage, section_keys_from_text
from src.llm.service import INSUFFICIENT_EVIDENCE_ANSWER

_TOKEN_RE = re.compile(r"[a-z0-9']+", re.IGNORECASE)

_STOPWORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "of", "in", "on", "at", "to",
        "for", "with", "under", "is", "are", "was", "were", "be", "been",
        "being", "do", "does", "did", "have", "has", "had", "it", "its",
        "this", "that", "these", "those", "what", "which", "who", "whom",
        "how", "when", "where", "why", "not", "no", "as", "by", "from",
    }
)

_INLINE_CITE_RE = re.compile(r"\[\s*(\d{1,3})\s*\]")

_SECTION_IN_ANSWER_RE = re.compile(r"\b(?:section|sec\.?|s\.?)\s*(\d{1,3})", re.IGNORECASE)


def tokens(text: str) -> list[str]:
    """Lowercased word tokens for a text."""
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def content_tokens(text: str) -> set[str]:
    """Lowercased tokens with stopwords removed (used for faithfulness)."""
    return {t for t in tokens(text) if t not in _STOPWORDS and len(t) > 1}


def token_f1(predicted: str, gold: str) -> float:
    """F1 over token sets between the predicted and gold answers."""
    p = set(tokens(predicted))
    g = set(tokens(gold))
    if not p or not g:
        return 0.0
    tp = len(p & g)
    precision = tp / len(p)
    recall = tp / len(g)
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


def answer_accuracy(answer: str, expected_answer: str) -> float:
    """Token-F1 of the answer against the gold answer summary."""
    return token_f1(answer, expected_answer)


def _inline_citations(answer: str) -> list[int]:
    """Source numbers cited inline in the answer (``[1]``, ``[2]``, ...)."""
    return [int(match.group(1)) for match in _INLINE_CITE_RE.finditer(answer or "")]


def _evidence(result) -> list:
    """The explanation's evidence list from an AnswerResult."""
    return list(result.explanation.evidence)


def grounding_accuracy(answer: str, result) -> float:
    """Fraction of the answer's claims that reference retrieved sources.

    Guard answer -> 1.0. Otherwise, inline source citations ``[N]`` must fall
    within the retrieved evidence, and any ``Section N`` mentions in the answer
    must be covered by the evidence sections. When the answer makes no
    verifiable claims, grounding is 1.0 (vacuously sound).
    """
    if (answer or "").strip() == INSUFFICIENT_EVIDENCE_ANSWER:
        return 1.0
    evidence = _evidence(result)
    n_evidence = len(evidence)

    cited = _inline_citations(answer)
    if cited:
        valid = sum(1 for n in cited if 1 <= n <= n_evidence)
        return round(valid / len(cited), 4)

    mentioned = [int(m) for m in _SECTION_IN_ANSWER_RE.findall(answer or "")]
    if mentioned:
        evidence_keys: set[str] = set()
        for ev in evidence:
            evidence_keys.update(section_keys_from_text(ev.numbering))
            evidence_keys.update(section_keys_from_text(ev.title))
        covered = sum(1 for num in mentioned if any(k.startswith(str(num)) for k in evidence_keys))
        return round(covered / len(mentioned), 4)

    return 1.0


def citation_accuracy(item, result) -> float:
    """Expected sections covered by the sources the answer cited.

    The guard answer makes no claims, so it scores 1.0. Otherwise the inline
    ``[N]`` citations are mapped to their evidence sections.
    """
    if (result.answer or "").strip() == INSUFFICIENT_EVIDENCE_ANSWER:
        return 1.0
    evidence = _evidence(result)
    cited = _inline_citations(result.answer)
    if not cited:
        return 0.0
    cited_sections: set[str] = set()
    for n in cited:
        if 1 <= n <= len(evidence):
            ev = evidence[n - 1]
            cited_sections.update(section_keys_from_text(ev.numbering))
            cited_sections.update(section_keys_from_text(ev.title))
    return section_coverage(item.expected_sections, cited_sections)


def faithfulness(answer: str, result) -> float:
    """Fraction of answer content tokens supported by the retrieved evidence."""
    answer_tokens = content_tokens(answer)
    if not answer_tokens:
        return 1.0
    evidence_text = " ".join(
        f"{ev.title} {ev.text} {ev.numbering}" for ev in _evidence(result)
    ).lower()
    supported = sum(1 for token in answer_tokens if token in evidence_text)
    return round(supported / len(answer_tokens), 4)


def evidence_coverage(expected_answer: str, result) -> float:
    """Fraction of gold-answer tokens covered by the retrieved evidence."""
    gold_tokens = content_tokens(expected_answer)
    if not gold_tokens:
        return 0.0
    evidence_text = " ".join(
        f"{ev.title} {ev.text} {ev.numbering}" for ev in _evidence(result)
    ).lower()
    covered = sum(1 for token in gold_tokens if token in evidence_text)
    return round(covered / len(gold_tokens), 4)


def hallucination_rate(answer: str, result) -> float:
    """Fraction of answer content tokens unsupported by the evidence."""
    if (answer or "").strip() == INSUFFICIENT_EVIDENCE_ANSWER:
        return 0.0
    return round(1.0 - faithfulness(answer, result), 4)


def generation_metrics(item, result) -> dict[str, float]:
    """Full per-question generation metric vector."""
    metrics = {
        "answer_accuracy": answer_accuracy(result.answer, item.expected_answer),
        "grounding_accuracy": grounding_accuracy(result.answer, result),
        "citation_accuracy": citation_accuracy(item, result),
        "faithfulness": faithfulness(result.answer, result),
        "evidence_coverage": evidence_coverage(item.expected_answer, result),
        "hallucination_rate": hallucination_rate(result.answer, result),
    }
    return {key: round(value, 4) for key, value in metrics.items()}
