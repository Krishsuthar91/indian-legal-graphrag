"""Task 21 regression tests — retrieval recall + ranking improvements.

Covers the retrieval-only quality fixes delivered for Task 21:

* Word-boundary section citations (scorer.py) — a reference to "Section 12"
  must not match "Section 1" / "Section 121" via substring.
* Exact section-number candidate injection (explanation.py).
* Definition-first promotion so concept queries surface the defining section.
* Illustration/explanation fragment demotion so prose-numbered ``Section``
  leaves do not win the top rank.

Verification/confidence/grounding/entailment/prompts are untouched; these tests
only assert which evidence section ranks top-k for a retrieval query.
"""

from __future__ import annotations

import pytest

from src.config.settings import settings
from src.embeddings import VectorRetriever
from src.llm import service as svc_mod
from src.llm.explanation import ExplainabilityEngine


@pytest.fixture(scope="module")
def engine_and_graph():
    settings.LLM_PROVIDER = "mock"
    settings.EMBEDDING_FORCE_DETERMINISTIC = True
    graph, store, embedding = svc_mod.get_default_corpus()
    retriever = VectorRetriever(graph, store, embedding)
    eng = ExplainabilityEngine(
        graph,
        vector_retriever=retriever,
        confidence_threshold=settings.QA_CONFIDENCE_THRESHOLD,
    )
    return eng, graph


def top_numbers(engine, graph, query, k=5):
    result = engine.explain(query, top_k=k)

    def numbering(nid):
        return str(graph.get_node(nid).get("numbering", "")).strip()

    return [numbering(ev.node_id) for ev in result.evidence]


def test_exact_section_12_ranks_first(engine_and_graph):
    engine, graph = engine_and_graph
    assert top_numbers(engine, graph, "What is Section 12?", k=1)[0] == "12"


def test_section_12_no_substring_collision(engine_and_graph):
    engine, graph = engine_and_graph
    top = top_numbers(engine, graph, "What is Section 12?", k=1)
    assert "1" not in top and "121" not in top


def test_bare_section_1_ranks_first(engine_and_graph):
    engine, graph = engine_and_graph
    assert top_numbers(engine, graph, "Section 1", k=1)[0] == "1"


def test_coercion_definition_section_surfaces(engine_and_graph):
    engine, graph = engine_and_graph
    assert "15" in top_numbers(engine, graph, "What is coercion?")


def test_consideration_query_ranks_consideration_sections(engine_and_graph):
    engine, graph = engine_and_graph
    # The Indian Contract Act, 1872 has dedicated consideration sections: 2
    # (interpretation / 2(d) consideration definition), 23 (lawful
    # consideration), 25 (agreement without consideration) and 185
    # (consideration not necessary). V2.4.1 query expansion (enabled by default)
    # injects the verified refs "section 2" and "section 25" plus the concept
    # synonym "lawful consideration", so 2 and 25 now outrank 23/185 and
    # section 8 falls out of the top-5.
    #
    # Section 2 and section 25 tie on their composite rank (both carry the exact
    # injected reference); their relative order can flip between runs because
    # candidate accumulation iterates over set-typed collections. Assert the
    # stable top-5 SET (ICA-scoped, no IPC leaks) and that every gold
    # consideration section is present.
    top = top_numbers(engine, graph, "What is consideration?")
    assert set(top) == {"2", "25", "23", "185", "10"}
    assert {"2", "23", "25", "185"} <= set(top)


def test_section_72_ranks_first_not_illustration(engine_and_graph):
    engine, graph = engine_and_graph
    top = top_numbers(engine, graph, "Section 72")
    assert top[0] == "72"
    assert top[0] != "Illustration"
