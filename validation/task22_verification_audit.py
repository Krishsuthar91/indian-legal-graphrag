"""Task 22 — Verification Failure Audit (analysis only).

Builds an audit harness that reuses the manual-validation service wiring
(``validation.build_service`` -> ``QueryService`` with the real corpus and a
deterministic mock LLM) and, for every supported-expected query, captures the
full retrieval -> ranking -> relevance -> sufficiency -> confidence ->
verification -> grounding-guard decision tree.

No production code is modified. The grounding-guard decision and reason are
evaluated with the service's own methods so the audit is bit-for-bit identical
to what the /query pipeline computes *before* answer generation.

Outputs:
    results/task22_verification_audit.json
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

VALIDATION_DIR = Path(__file__).resolve().parent
CASES_PATH = VALIDATION_DIR / "expected_results.json"
OUT_PATH = REPO / "results" / "task22_verification_audit.json"

ICA = "0d1934142f67c5f5"
IPC = "cf20a14c52127fd5"


def safe(val, default=None):
    try:
        return val()
    except Exception as exc:  # noqa: BLE001
        return f"<err {type(exc).__name__}: {exc}>" if default is None else default


def main() -> None:
    from src.config.settings import settings
    from src.embeddings import VectorRetriever
    from src.llm import service as svc_mod
    from src.llm.explanation import ExplainabilityEngine
    from src.llm.llm import MockLLMClient
    from src.llm.provenance import ProvenanceStore
    from src.llm.service import QueryService

    settings.LLM_PROVIDER = "mock"
    graph, store, embedding = svc_mod.get_default_corpus()
    vector_retriever = VectorRetriever(graph, store, embedding)
    engine = ExplainabilityEngine(
        graph,
        vector_retriever=vector_retriever,
        confidence_threshold=settings.QA_CONFIDENCE_THRESHOLD,
    )
    engine.llm_client = MockLLMClient()
    service = QueryService(
        engine,
        MockLLMClient(),
        ProvenanceStore(),
        top_k=settings.QA_TOP_K,
        confidence_threshold=settings.QA_CONFIDENCE_THRESHOLD,
    )

    doc_slugs = {
        "0d1934142f67c5f5": "ICA (Contract Act)",
        "cf20a14c52127fd5": "IPC (Penal Code)",
    }

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]

    # node metadata (labels / doc) from the graph
    node_meta = {}
    for n in graph.all_nodes():
        nid = n.get("node_id")
        if nid:
            node_meta[nid] = {
                "doc": n.get("document_id"),
                "num": str(n.get("numbering", "")).strip(),
                "label": n.get("label", ""),
                "title": n.get("title", ""),
            }
    engine = service.engine

    def node_type(nid: str) -> str:
        m = node_meta.get(nid, {})
        return m.get("label", "")

    def node_doc(nid: str) -> str:
        return node_meta.get(nid, {}).get("doc", "")

    audit = {}
    for cid, case in cases.items():
        if case.get("expected_status") != "supported":
            continue
        exp = str(case["expected_section"])
        query = case["query"]

        exp_obj = service.explain(query, top_k=5)
        ev = exp_obj.evidence
        top1 = ev[0] if ev else None
        top1_num = str(top1.numbering).strip() if top1 else None
        top1_node = top1.node_id if top1 else None
        top1_doc = node_doc(top1_node) if top1 else ""
        top5_correct = any(str(e.numbering).strip() == exp for e in ev)

        # Is the expected section present in any retrieval/ranking stage
        # (beyond the top-5 evidence window)? Used to split "never retrieved
        # anywhere" (A) from "retrieved but below top-5" (B).
        expected_in_chain = False
        for step in exp_obj.reasoning_chain:
            if step.kind in ("dense", "graph", "hierarchy"):
                for nid in step.node_ids or []:
                    if node_meta.get(nid, {}).get("num", "") == exp:
                        expected_in_chain = True
                        break
            if expected_in_chain:
                break

        vt = exp_obj.verification_trace
        conf = exp_obj.confidence
        facts = conf.factors

        guard_triggered = not service._should_generate_answer(exp_obj)
        guard_reason = service._grounding_guard_reason(exp_obj) if guard_triggered else "PASS"

        doc_ids = []
        doc_titles = []
        node_types = []
        doc_seen = set()
        for e in ev:
            d = node_doc(e.node_id)
            if d and d not in doc_seen:
                doc_seen.add(d)
                doc_ids.append(d)
                doc_titles.append(doc_slugs.get(d, d[:12]))
        for e in ev:
            t = node_type(e.node_id)
            if t:
                node_types.append(t)

        record = {
            "query": query,
            "expected_section": exp,
            # --- retrieval ---
            "retrieval_intent": exp_obj.retrieval.intent,
            "retrieval_query_intent": exp_obj.retrieval.query_intent,
            "retrieval_strategy": exp_obj.retrieval.retrieval_strategy,
            "retrieval_adaptive_top_k": exp_obj.retrieval.adaptive_top_k,
            "retrieval_ranking_weights": exp_obj.retrieval.ranking_weights,
            # --- ranking ---
            "top1_correct": top1_num == exp,
            "top5_correct": top5_correct,
            "expected_in_chain": expected_in_chain,
            "top1_section": top1_num,
            "top1_doc": top1_doc,
            "top1_doc_slug": doc_slugs.get(top1_doc, top1_doc[:12]),
            "retrieved_sections": [str(e.numbering).strip() for e in ev],
            "retrieved_doc_ids": doc_ids,
            "retrieved_doc_titles": doc_titles,
            "retrieved_ranking_scores": [round(e.final_score, 4) for e in ev],
            "ranking_breakdown": exp_obj.retrieval.ranking_breakdown,
            # --- evidence ---
            "evidence_count": len(ev),
            "evidence_lengths": [(len(e.text or ""), e.label) for e in ev],
            "evidence_titles": [e.title for e in ev],
            "evidence_node_types": node_types,
            "evidence_doc_ids": [node_doc(e.node_id) for e in ev],
            "evidence_snippets": [
                (e.title, (e.text or "")[:80], str(e.numbering).strip()) for e in ev[:5]
            ],
            # --- verification ---
            "verification_status": exp_obj.validity.status,
            "verification_reason": exp_obj.validity.reason,
            # --- confidence ---
            "confidence_score": conf.score,
            "confidence_label": conf.label,
            "confidence_factors": {
                "evidence_relevance": facts.get("evidence_relevance", 0.0),
                "evidence_sufficiency": facts.get("evidence_sufficiency", 0.0),
                "citation_entailment": facts.get("citation_entailment", 0.0),
                "retrieval_base": facts.get("retrieval_base", 0.0),
                "contradiction_found": facts.get("contradiction_found", False),
                "final_adjustment": facts.get("final_adjustment", "none"),
                "verification_status": facts.get("verification_status", ""),
            },
            "evidence_relevance": facts.get("evidence_relevance", 0.0),
            "evidence_sufficiency": facts.get("evidence_sufficiency", 0.0),
            "citation_entailment": facts.get("citation_entailment", 0.0),
            "retrieval_base": facts.get("retrieval_base", 0.0),
            # --- verification trace ---
            "verification_trace": {
                "decision_path": (vt.decision_path if vt else []),
                "contradiction_found": (vt.contradiction_found if vt else False),
                "final_adjustment": (vt.final_adjustment if vt else "none"),
                "verification_status": (vt.verification_status if vt else ""),
                "verification_reason": (vt.verification_reason if vt else ""),
            },
            # --- grounding guard ---
            "guard_triggered": guard_triggered,
            "guard_reason": guard_reason,
        }
        audit[cid] = record
        print(
            f"[{cid}] top1={top1_num!r} top1ok={record['top1_correct']} "
            f"rel={record['evidence_relevance']:.3f} "
            f"suf={record['evidence_sufficiency']:.3f} "
            f"conf={record['confidence_score']:.3f} "
            f"status={record['verification_status']} guard={guard_triggered} {guard_reason}"
        )

    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(json.dumps(audit, indent=1), encoding="utf-8")
    print("WROTE", OUT_PATH)


if __name__ == "__main__":
    main()
